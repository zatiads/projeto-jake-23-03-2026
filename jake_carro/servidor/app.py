"""
Jake no Carro — servidor do computador de bordo (central Android do HB20).

Serviço próprio (127.0.0.1:5055, systemd jake-carro), separado do Jake OS:
reiniciar um não derruba o outro. Exposto em https://carro.amiartejoias.com.br.

Fluxo: app grava áudio → /carro/comando → transcrição (OpenAI) → GPT decide a
ação em JSON → Edge TTS gera a fala → app executa (Maps, Spotify, mídia).
"""
import base64
import json
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import requests
from flask import Flask, jsonify, request, send_file

import consultas

BASE = Path(__file__).resolve().parent
APK_DIR = BASE.parent / "releases"
FUSO = ZoneInfo("America/Sao_Paulo")

TOKEN = os.environ.get("JAKE_CARRO_TOKEN", "").strip()
MODELO = os.environ.get("JAKE_CARRO_MODELO", "gpt-4.1-mini")
MODELO_STT = os.environ.get("JAKE_CARRO_STT", "gpt-4o-mini-transcribe")
EDGE_BIN = os.environ.get("JAKE_EDGE_TTS", "/opt/edge-tts/bin/edge-tts")
EDGE_VOZ = os.environ.get("JAKE_CARRO_VOZ", "pt-BR-AntonioNeural")
EDGE_RITMO = os.environ.get("JAKE_CARRO_VOZ_RITMO", "+8%")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

_openai = None


def ia():
    """Cliente OpenAI (único ponto da IA — trocar de modelo/fornecedor é aqui)."""
    global _openai
    if _openai is None:
        from openai import OpenAI
        # No carro, esperar muito é pior que errar: 10 s e só 1 nova tentativa.
        _openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "").strip(), timeout=10, max_retries=1)
    return _openai


# ── Banco ─────────────────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"].strip(),
                            cursor_factory=psycopg2.extras.RealDictCursor)


def criar_tabelas():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carro_lugares (
                id SERIAL PRIMARY KEY,
                apelido TEXT NOT NULL UNIQUE,
                endereco TEXT NOT NULL,
                criado_em TIMESTAMPTZ DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS carro_log (
                id SERIAL PRIMARY KEY,
                criado_em TIMESTAMPTZ DEFAULT now(),
                sessao TEXT,
                ouvido TEXT,
                fala TEXT,
                acao TEXT,
                parametros JSONB,
                ms_stt INT,
                ms_ia INT,
                ms_voz INT
            );
        """)


_lugares_cache = {"ts": 0, "dados": []}


def _carregar_lugares():
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("SELECT apelido, endereco FROM carro_lugares ORDER BY apelido")
            _lugares_cache["dados"] = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        app.logger.warning("lugares indisponíveis: %s", e)


def lugares():
    """Lugares salvos; recarrega em segundo plano pra o banco nunca atrasar um comando."""
    if time.time() - _lugares_cache["ts"] > 300:
        _lugares_cache["ts"] = time.time()
        threading.Thread(target=_carregar_lugares, daemon=True).start()
    return _lugares_cache["dados"]


def registrar(**campos):
    def _grava():
        try:
            with get_db() as conn, conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO carro_log (sessao, ouvido, fala, acao, parametros, ms_stt, ms_ia, ms_voz)
                       VALUES (%(sessao)s, %(ouvido)s, %(fala)s, %(acao)s, %(parametros)s,
                               %(ms_stt)s, %(ms_ia)s, %(ms_voz)s)""",
                    {**campos, "parametros": json.dumps(campos.get("parametros") or {})})
        except Exception as e:
            app.logger.warning("log falhou: %s", e)
    threading.Thread(target=_grava, daemon=True).start()


# ── Auth ──────────────────────────────────────────────────────────────────────

def autenticado(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        dado = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        dado = dado or request.args.get("t", "")
        if not TOKEN or dado != TOKEN:
            return jsonify(erro="não autorizado"), 401
        return f(*args, **kwargs)
    return decorated


# ── Limite de uso: segura um app vazado de torrar a conta da OpenAI ───────────

from collections import deque

_janelas = {}


def limitado(por_hora):
    """Recusa (429) quando a rota passa de `por_hora` pedidos na última hora."""
    def deco(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            fila = _janelas.setdefault(f.__name__, deque())
            agora = time.time()
            while fila and agora - fila[0] > 3600:
                fila.popleft()
            if len(fila) >= por_hora:
                app.logger.warning("limite de uso: %s passou de %d/h", f.__name__, por_hora)
                return jsonify(erro="muitos pedidos, espera um pouco"), 429
            fila.append(agora)
            return f(*args, **kwargs)
        return decorated
    return deco


# ── Voz ───────────────────────────────────────────────────────────────────────

_tts = {"proc": None, "trava": threading.Lock()}


def _voz_worker(texto):
    """Fala pelo processo fixo (tts_worker.py); None se ele não estiver de pé."""
    with _tts["trava"]:
        proc = _tts["proc"]
        if proc is None or proc.poll() is not None:
            python_tts = Path(EDGE_BIN).parent / "python"
            proc = _tts["proc"] = subprocess.Popen(
                [str(python_tts), str(BASE / "tts_worker.py")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        proc.stdin.write(json.dumps({"texto": texto, "voz": EDGE_VOZ, "ritmo": EDGE_RITMO}) + "\n")
        proc.stdin.flush()
        return proc.stdout.readline().strip()


ESTILO_VOZ = ("Fale em português do Brasil, sotaque brasileiro natural. Você é o Jake, o assistente de IA do carro, "
              "estilo JARVIS: voz calma, confiante e elegante, com bom humor discreto. Ritmo ágil, dicção limpa.")


def voz_openai(texto):
    """Mesma voz da conversa em tempo real (VOZ_RT), pra o Jake não trocar de 'pessoa'."""
    r = ia().audio.speech.create(model="gpt-4o-mini-tts", voice=os.environ.get("JAKE_CARRO_VOZ_RT", "cedar"),
                                 input=texto[:600], instructions=ESTILO_VOZ, response_format="mp3")
    return base64.b64encode(r.content).decode()


def voz_b64(texto):
    """mp3 da fala em base64: voz da OpenAI; se falhar, Edge TTS; se tudo falhar, vazio (o app usa a voz local)."""
    if not texto.strip():
        return ""
    try:
        return voz_openai(texto)
    except Exception as e:
        app.logger.warning("voz openai falhou: %s", e)
    try:
        audio = _voz_worker(texto[:600])
        if audio:
            return audio
    except Exception as e:
        app.logger.warning("tts_worker erro: %s", e)
        _tts["proc"] = None
    try:
        proc = subprocess.run(
            [EDGE_BIN, "--voice", EDGE_VOZ, f"--rate={EDGE_RITMO}", "--text", texto[:600]],
            capture_output=True, timeout=12)
        if proc.returncode == 0 and proc.stdout:
            return base64.b64encode(proc.stdout).decode()
        app.logger.warning("edge-tts falhou: %s", proc.stderr[:200])
    except Exception as e:
        app.logger.warning("edge-tts erro: %s", e)
    return ""


def transcrever(arquivo):
    resp = ia().audio.transcriptions.create(
        model=MODELO_STT,
        file=(arquivo.filename or "fala.m4a", arquivo.read(), arquivo.mimetype or "audio/mp4"),
        language="pt",  # sem "prompt": com ele a transcrição oscilava de 0,6 s pra até 2,5 s
    )
    return (resp.text or "").strip()


# ── Spotify (Web API, só busca) ───────────────────────────────────────────────

_spotify = {"token": "", "expira": 0}


def spotify_uri(busca, tipo):
    cid = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    seg = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    if not (cid and seg and busca):
        return ""
    try:
        if time.time() > _spotify["expira"]:
            r = requests.post("https://accounts.spotify.com/api/token",
                              data={"grant_type": "client_credentials"},
                              auth=(cid, seg), timeout=6)
            r.raise_for_status()
            _spotify["token"] = r.json()["access_token"]
            _spotify["expira"] = time.time() + r.json().get("expires_in", 3600) - 60
        tipo_api = {"musica": "track", "artista": "artist",
                    "playlist": "playlist", "album": "album"}.get(tipo, "track")
        r = requests.get("https://api.spotify.com/v1/search",
                         params={"q": busca, "type": tipo_api, "limit": 5, "market": "BR"},
                         headers={"Authorization": f"Bearer {_spotify['token']}"}, timeout=6)
        r.raise_for_status()
        itens = r.json().get(f"{tipo_api}s", {}).get("items") or []
        itens = [i for i in itens if i]
        return itens[0]["uri"] if itens else ""
    except Exception as e:
        app.logger.warning("spotify busca falhou: %s", e)
        return ""


# ── Clima ─────────────────────────────────────────────────────────────────────

CODIGOS_CLIMA = {0: "céu limpo", 1: "quase limpo", 2: "parcialmente nublado", 3: "nublado",
                 45: "neblina", 48: "neblina", 51: "garoa", 53: "garoa", 55: "garoa forte",
                 61: "chuva fraca", 63: "chuva", 65: "chuva forte", 80: "pancadas de chuva",
                 81: "pancadas de chuva", 82: "temporal", 95: "trovoada", 96: "trovoada", 99: "trovoada"}


def clima(lat, lon):
    if not (lat and lon):
        return ""
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "timezone": "America/Sao_Paulo",
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,precipitation_probability_max", "forecast_days": 1,
        }, timeout=4)
        d = r.json()
        atual = d["current"]
        return (f"{round(atual['temperature_2m'])}°C, "
                f"{CODIGOS_CLIMA.get(atual['weather_code'], 'tempo variado')}, "
                f"máxima de {round(d['daily']['temperature_2m_max'][0])}°C, "
                f"chance de chuva {d['daily']['precipitation_probability_max'][0]}%")
    except Exception:
        return ""


# ── Cérebro ───────────────────────────────────────────────────────────────────

PERSONA = """Você é o Jake, o computador de bordo do carro do Bruno (um HB20 2013). Chame ele de "patrão".
Ele está DIRIGINDO: responda sempre em português do Brasil, falado, curto (no máximo 2 frases, idealmente 1),
natural, com bom humor leve, sem listas, sem emojis, sem markdown, sem links. Números por extenso só quando curtos.
O Bruno é dono de uma agência de tráfego pago (Meta Ads) e trabalha remoto; gosta de viagens e trilhas."""

INSTRUCOES = """Decida UMA ação para o app executar:
- navegar: ele quer ir a algum lugar. parametros.destino = endereço ou nome do lugar o mais completo possível
  (use os lugares salvos quando ele citar o apelido). Ele mora em Varginha (sul de Minas): nome de lugar
  ambíguo = o mais perto de Varginha (ex: "São Tomé" = São Tomé das Letras, MG). Nunca invente nome de
  estabelecimento: pedido genérico ("o shopping", "um posto", "farmácia") vai genérico ("shopping, Varginha, MG";
  "posto de gasolina") que o Maps acha o mais perto. parametros.app = "waze" só se
  ele pedir Waze, senão "maps".
- tocar_musica: tocar algo no Spotify. parametros.busca = o que buscar, parametros.tipo = musica|artista|playlist|album.
  Só um nome (ex: "coloca Freud", "toca Matuê") = artista. "musica" só quando ele citar o título de uma música
  (ex: "toca Evidências"); nesse caso ponha título e artista na busca se ele disser. Pedido de estilo/clima = playlist.
- midia: controlar o que está tocando. parametros.comando = pausar|continuar|proxima|anterior.
- consultar: precisa buscar dado antes de responder. "fala" = frase curta de espera
  (ex: "Deixa eu dar uma olhada, patrão.", "Só um segundo que eu puxo aqui."). parametros.consulta =
  pesquisa (notícias, qualquer coisa atual ou que precise da internet; parametros.pergunta = o que pesquisar, bem completo)
  | meta (números de anúncios/campanhas/leads de um cliente; parametros.cliente = nome do cliente como na lista de
  contas abaixo; parametros.periodo = hoje|ontem|esta_semana|ultimos_7_dias|este_mes|mes_passado, padrão ontem)
  | agenda (compromissos, reuniões, prazos, pagamentos, "o que eu preciso lembrar"; parametros.periodo =
  hoje|amanha|esta_semana|proxima_semana|este_mes). Em parametros.pergunta repita a pergunta dele.
- responder: só conversar/responder algo que você já sabe (a resposta vai em "fala").
- nada: não entendeu ou ruído; peça pra repetir em "fala".
Campos de parametros que não se aplicam ficam como string vazia.
"fala" é o que você diz em voz alta enquanto executa (ex: "Bora, patrão. Rota pro escritório.")."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["fala", "acao", "parametros"],
    "properties": {
        "fala": {"type": "string"},
        "acao": {"type": "string", "enum": ["navegar", "tocar_musica", "midia", "consultar", "responder", "nada"]},
        "parametros": {
            "type": "object",
            "additionalProperties": False,
            "required": ["destino", "app", "busca", "tipo", "comando", "consulta", "pergunta", "cliente", "periodo"],
            "properties": {
                "destino": {"type": "string"},
                "app": {"type": "string", "enum": ["maps", "waze", ""]},
                "busca": {"type": "string"},
                "tipo": {"type": "string", "enum": ["musica", "artista", "playlist", "album", ""]},
                "comando": {"type": "string", "enum": ["pausar", "continuar", "proxima", "anterior", ""]},
                "consulta": {"type": "string", "enum": ["pesquisa", "meta", "agenda", ""]},
                "pergunta": {"type": "string"},
                "cliente": {"type": "string"},
                "periodo": {"type": "string", "enum": ["hoje", "ontem", "amanha", "esta_semana", "proxima_semana",
                                                       "ultimos_7_dias", "este_mes", "mes_passado", ""]},
            },
        },
    },
}

_sessoes = {}  # sessao -> {"ts": float, "msgs": [...]}


def contexto():
    agora = datetime.now(FUSO)
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    txt = f"Agora: {dias[agora.weekday()]}, {agora:%d/%m/%Y %H:%M}."
    lug = lugares()
    if lug:
        txt += "\nLugares salvos: " + "; ".join(f"{l['apelido']} = {l['endereco']}" for l in lug)
    clientes = consultas.nomes_clientes()
    if clientes:
        txt += "\nContas de anúncio (clientes): " + "; ".join(clientes)
    return txt


def decidir(texto, sessao):
    s = _sessoes.get(sessao)
    if not s or time.time() - s["ts"] > 900:
        s = {"msgs": []}
    historico = s["msgs"][-6:]
    msgs = [{"role": "system", "content": f"{PERSONA}\n\n{INSTRUCOES}\n\n{contexto()}"},
            *historico, {"role": "user", "content": texto}]
    resp = ia().chat.completions.create(
        model=MODELO, messages=msgs, temperature=0.6, max_tokens=250,
        response_format={"type": "json_schema",
                         "json_schema": {"name": "acao_carro", "strict": True, "schema": SCHEMA}})
    dado = json.loads(resp.choices[0].message.content)
    lembrar(sessao, texto, dado["fala"])
    return dado


def lembrar(sessao, pergunta, resposta):
    s = _sessoes.get(sessao)
    historico = s["msgs"] if s and time.time() - s["ts"] <= 900 else []
    historico += [{"role": "user", "content": pergunta}, {"role": "assistant", "content": resposta}]
    _sessoes[sessao] = {"ts": time.time(), "msgs": historico[-6:]}


def falar_dados(pergunta, dados, sessao=""):
    """Transforma dados crus (Meta, agenda) numa resposta falada curta."""
    resp = ia().chat.completions.create(
        model=MODELO, temperature=0.5, max_tokens=220,
        messages=[{"role": "system", "content": PERSONA + "\nAqui pode usar até 3 frases curtas. Só os fatos que "
                   "ele perguntou: sem conselho, sem julgamento ('tá devagar', 'dá pra melhorar'), sem oferecer ajuda e "
                   "sem pergunta no final. Em números de anúncio diga sempre: quanto gastou, quantos resultados "
                   "(conversas e/ou leads) e o custo por resultado; campanha só se ele perguntar. Valores em reais "
                   "arredondados ('uns 310 reais', 'uns 35 reais cada'). Datas e horas do jeito natural ('quinta às 10')."},
                  {"role": "user", "content": f"{contexto()}\n\nPergunta do patrão: {pergunta}\n\nDados:\n{dados}"}])
    return resp.choices[0].message.content.strip()


# ── Rotas ─────────────────────────────────────────────────────────────────────

def versao_apk():
    arquivo = APK_DIR / "versao.json"
    if arquivo.exists():
        return json.loads(arquivo.read_text())
    return {"versao": 0, "nome": ""}


@app.get("/carro/saude")
def saude():
    return jsonify(ok=True)


@app.get("/carro/config")
@autenticado
def config():
    return jsonify(spotify_client_id=os.environ.get("SPOTIFY_CLIENT_ID", "").strip(),
                   app=versao_apk())


ESTADO = BASE / "estado.json"


def _primeira_do_dia():
    """True só na primeira saudação de cada dia (guarda a data em estado.json)."""
    hoje = datetime.now(FUSO).strftime("%Y-%m-%d")
    try:
        estado = json.loads(ESTADO.read_text())
    except Exception:
        estado = {}
    if estado.get("ultima_saudacao_completa") == hoje:
        return False
    estado["ultima_saudacao_completa"] = hoje
    ESTADO.write_text(json.dumps(estado))
    return True


@app.get("/carro/saudacao")
@autenticado
@limitado(30)
def saudacao():
    agora = datetime.now(FUSO)
    lat, lon = request.args.get("lat"), request.args.get("lon")
    if request.args.get("teste") != "1" and not _primeira_do_dia():
        pedido = (f"{contexto()}\nO patrão voltou pro carro (já te cumprimentou hoje). Diga só um oi curtíssimo "
                  "e pergunte pra onde vamos, uma frase.")
    else:
        if not (lat and lon):
            lat, lon = consultas.VARGINHA
            lugar = "Varginha"
        else:
            lugar = consultas.cidade(lat, lon) or "Varginha"
        tempo = clima(lat, lon)
        try:
            hoje = consultas.agenda("hoje")
        except Exception as e:
            app.logger.warning("agenda na saudação falhou: %s", e)
            hoje = ""
        if hoje.startswith(("SEM ACESSO", "A agenda ainda")):
            hoje = ""
        cumprimento = "Boa noite" if agora.hour < 5 else "Bom dia" if agora.hour < 12 else "Boa tarde" if agora.hour < 18 else "Boa noite"
        pedido = (f"Primeira vez que o carro liga hoje. Agora são {agora:%H:%M}.\nCidade: {lugar}."
                  + (f"\nClima: {tempo}." if tempo else "")
                  + (f"\n{hoje}" if hoje else "\nAgenda: indisponível — NÃO fale de compromissos.")
                  + f"\nComece com \"{cumprimento}, patrão!\", diga a cidade e o clima (temperatura agora; de manhã "
                    "e à tarde também a máxima e a chance de chuva), e se houver agenda acima diga quantos "
                    "compromissos tem hoje e qual o próximo. Termine perguntando pra onde vamos. Até 4 frases "
                    "curtas. Nunca invente compromisso nem cliente.")
    try:
        resp = ia().chat.completions.create(
            model=MODELO, temperature=0.9, max_tokens=200,
            messages=[{"role": "system", "content": PERSONA}, {"role": "user", "content": pedido}])
        fala = resp.choices[0].message.content.strip()
    except Exception as e:
        app.logger.warning("saudação falhou: %s", e)
        periodo = "Boa noite" if agora.hour < 5 else "Bom dia" if agora.hour < 12 else "Boa tarde" if agora.hour < 18 else "Boa noite"
        fala = f"{periodo}, patrão! Pra onde vamos?"
    return jsonify(fala=fala, audio_b64=voz_b64(fala))


@app.post("/carro/comando")
@autenticado
@limitado(150)
def comando():
    sessao = request.form.get("sessao") or str(uuid.uuid4())
    t0 = time.time()
    texto = (request.form.get("texto") or "").strip()
    if not texto and "audio" in request.files:
        try:
            texto = transcrever(request.files["audio"])
        except Exception as e:
            app.logger.warning("transcrição falhou: %s", e)
            fala = "Não consegui te ouvir direito, patrão. Fala de novo?"
            return jsonify(ouvido="", fala=fala, audio_b64=voz_b64(fala), acao="nada", parametros={})
    t1 = time.time()
    if not texto:
        fala = "Não peguei nada, patrão. Repete pra mim?"
        return jsonify(ouvido="", fala=fala, audio_b64=voz_b64(fala), acao="nada", parametros={})

    try:
        dado = decidir(texto, sessao)
    except Exception as e:
        app.logger.warning("ia falhou: %s", e)
        dado = {"fala": "Deu um tilt aqui no meu cérebro, patrão. Tenta de novo?",
                "acao": "nada", "parametros": {}}
    t2 = time.time()

    params = dado["parametros"]
    if dado["acao"] == "tocar_musica":
        params["uri"] = spotify_uri(params.get("busca", ""), params.get("tipo", ""))
    audio = voz_b64(dado["fala"])
    t3 = time.time()

    ms = lambda a, b: int((b - a) * 1000)
    registrar(sessao=sessao, ouvido=texto, fala=dado["fala"], acao=dado["acao"], parametros=params,
              ms_stt=ms(t0, t1), ms_ia=ms(t1, t2), ms_voz=ms(t2, t3))
    return jsonify(ouvido=texto, fala=dado["fala"], audio_b64=audio, acao=dado["acao"],
                   parametros=params, sessao=sessao,
                   ms={"ouvir": ms(t0, t1), "pensar": ms(t1, t2), "voz": ms(t2, t3)})


@app.post("/carro/consulta")
@autenticado
@limitado(80)
def consulta():
    """2ª etapa de 'consultar': o app já falou a frase de espera e chama isto em paralelo."""
    p = request.get_json(force=True, silent=True) or {}
    sessao = p.get("sessao", "")
    tipo, pergunta = p.get("consulta", ""), p.get("pergunta", "")
    t0 = time.time()
    try:
        if tipo == "pesquisa":
            fala = falar_dados(pergunta, consultas.pesquisar(ia(), MODELO, pergunta))
        elif tipo == "meta":
            fala = falar_dados(pergunta, consultas.meta(p.get("cliente", ""), p.get("periodo", "")))
        elif tipo == "agenda":
            fala = falar_dados(pergunta, consultas.agenda(p.get("periodo", "")))
        else:
            fala = "Não sei consultar isso ainda, patrão."
    except Exception as e:
        app.logger.warning("consulta %s falhou: %s", tipo, e)
        fala = "Não consegui puxar isso agora, patrão. Tenta daqui a pouco."
    t1 = time.time()
    audio = voz_b64(fala)
    lembrar(sessao, pergunta, fala)
    registrar(sessao=sessao, ouvido=f"[{tipo}] {pergunta}", fala=fala, acao="consulta", parametros=p,
              ms_stt=0, ms_ia=int((t1 - t0) * 1000), ms_voz=int((time.time() - t1) * 1000))
    return jsonify(fala=fala, audio_b64=audio, ms=int((time.time() - t0) * 1000))


# ── Cockpit (página animada que o app abre em tela cheia) ────────────────────

COCKPIT = BASE / "cockpit"


@app.get("/carro/cockpit/")
@app.get("/carro/cockpit/<path:arquivo>")
def cockpit(arquivo="index.html"):
    """Arquivos do cockpit: só visual, sem dado pessoal — os dados vêm de /carro/painel com token."""
    alvo = (COCKPIT / arquivo).resolve()
    if not str(alvo).startswith(str(COCKPIT.resolve())) or not alvo.is_file():
        return jsonify(erro="não achei"), 404
    resp = send_file(alvo)
    resp.headers["Cache-Control"] = "no-cache"  # sempre confere se tem versão nova
    return resp


_painel = {"ts": 0, "chave": "", "dados": {}}


@app.get("/carro/painel")
@autenticado
@limitado(120)
def painel():
    """Dados do cockpit: cidade, clima e agenda de hoje (cache de 10 min)."""
    lat = request.args.get("lat") or consultas.VARGINHA[0]
    lon = request.args.get("lon") or consultas.VARGINHA[1]
    chave = f"{float(lat):.2f},{float(lon):.2f}"
    if time.time() - _painel["ts"] < 600 and _painel["chave"] == chave:
        return jsonify(_painel["dados"])
    dados = {"cidade": consultas.cidade(lat, lon) or "Varginha", "clima": None, "agenda": []}
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "timezone": "America/Sao_Paulo",
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,precipitation_probability_max,sunrise,sunset", "forecast_days": 1}, timeout=5).json()
        dados["sol"] = {"nasce": r["daily"]["sunrise"][0], "poe": r["daily"]["sunset"][0]}
        dados["clima"] = {"agora": round(r["current"]["temperature_2m"]),
                          "max": round(r["daily"]["temperature_2m_max"][0]),
                          "chuva": r["daily"]["precipitation_probability_max"][0],
                          "texto": CODIGOS_CLIMA.get(r["current"]["weather_code"], "")}
    except Exception as e:
        app.logger.warning("clima do painel falhou: %s", e)
    try:
        dados["agenda"] = consultas.agenda_itens("hoje")
    except Exception as e:
        app.logger.warning("agenda do painel falhou: %s", e)
    _painel.update(ts=time.time(), chave=chave, dados=dados)
    return jsonify(dados)


# ── Realtime (voz em tempo real, igual ao modo voz do ChatGPT) ────────────────
# O cockpit abre uma conexão WebRTC direto com a OpenAI usando uma chave temporária (1 min pra conectar).
# A IA chama "ferramentas": as do carro (rota, música) o app executa; as de dados (Meta, agenda, internet)
# passam por /carro/realtime/ferramenta.

MODELO_RT = os.environ.get("JAKE_CARRO_MODELO_RT", "gpt-realtime-mini")
VOZ_RT = os.environ.get("JAKE_CARRO_VOZ_RT", "cedar")

INSTRUCOES_RT = """Você está numa conversa por voz, ao vivo, dentro do carro. Fale sempre em português do Brasil, com sotaque
brasileiro natural, voz calma e confiante, estilo JARVIS: elegante, direto e com bom humor discreto.
Respostas curtíssimas (1 ou 2 frases): ele está dirigindo. Nunca leia listas, links ou markdown.
Quando ele pedir algo que uma ferramenta resolve, chame a ferramenta (não só descreva):
- navegar: ir a algum lugar. Lugar ambíguo = o mais perto de Varginha (sul de Minas). Use os lugares salvos pelo apelido.
  Pedido genérico ("um posto", "o shopping") vai genérico + cidade. Diga uma frase curta tipo "Bora, patrão. Rota pra X."
- tocar_musica: só um nome = artista; título de música = musica; estilo/clima = playlist.
- controlar_midia: pausar, continuar, próxima, anterior.
- consultar_meta / consultar_agenda / pesquisar_internet: ANTES de chamar diga uma frase de espera bem curta
  ("Só um segundo, patrão."). Com o resultado, responda só os fatos pedidos: no Meta diga gasto, resultados e custo por
  resultado, valores arredondados; sem conselho e sem pergunta no final.
Se não entendeu, peça pra repetir em poucas palavras."""

FERRAMENTAS_RT = [
    {"type": "function", "name": "navegar", "description": "Abre o Google Maps (ou Waze) navegando até o destino.",
     "parameters": {"type": "object", "properties": {
         "destino": {"type": "string", "description": "Endereço ou nome do lugar, o mais completo possível"},
         "app": {"type": "string", "enum": ["maps", "waze"]}}, "required": ["destino"]}},
    {"type": "function", "name": "tocar_musica", "description": "Toca algo no Spotify.",
     "parameters": {"type": "object", "properties": {
         "busca": {"type": "string"}, "tipo": {"type": "string", "enum": ["musica", "artista", "playlist", "album"]}},
         "required": ["busca", "tipo"]}},
    {"type": "function", "name": "controlar_midia", "description": "Controla o que está tocando.",
     "parameters": {"type": "object", "properties": {
         "comando": {"type": "string", "enum": ["pausar", "continuar", "proxima", "anterior"]}}, "required": ["comando"]}},
    {"type": "function", "name": "consultar_meta",
     "description": "Números de anúncios do Meta Ads de um cliente (gasto, conversas, leads, custo por resultado).",
     "parameters": {"type": "object", "properties": {
         "cliente": {"type": "string", "description": "Nome do cliente como na lista de contas"},
         "periodo": {"type": "string", "enum": ["hoje", "ontem", "esta_semana", "ultimos_7_dias", "este_mes", "mes_passado"]}},
         "required": ["cliente", "periodo"]}},
    {"type": "function", "name": "consultar_agenda", "description": "Compromissos, reuniões, prazos e pagamentos do Google Agenda.",
     "parameters": {"type": "object", "properties": {
         "periodo": {"type": "string", "enum": ["hoje", "amanha", "esta_semana", "proxima_semana", "este_mes"]}},
         "required": ["periodo"]}},
    {"type": "function", "name": "pesquisar_internet", "description": "Pesquisa na internet: notícias, fatos atuais, qualquer coisa que você não saiba.",
     "parameters": {"type": "object", "properties": {"pergunta": {"type": "string"}}, "required": ["pergunta"]}},
]


# Preço do gpt-realtime-mini por 1 milhão de tokens (US$). Atualizar se a OpenAI mudar.
PRECO_RT = {"texto": 0.60, "texto_cache": 0.06, "audio": 10.00, "audio_cache": 0.30,
            "texto_saida": 2.40, "audio_saida": 20.00}
TETO_USD = float(os.environ.get("JAKE_CARRO_TETO_USD", "15"))


def custo_resposta(u):
    """Custo (US$) de uma resposta da voz em tempo real a partir do 'usage' que a OpenAI devolve."""
    ent, sai = u.get("input_token_details") or {}, u.get("output_token_details") or {}
    cache = ent.get("cached_tokens_details") or {}
    txt_c, aud_c = cache.get("text_tokens", 0), cache.get("audio_tokens", 0)
    tokens = {"texto": ent.get("text_tokens", 0) - txt_c, "texto_cache": txt_c,
              "audio": ent.get("audio_tokens", 0) - aud_c, "audio_cache": aud_c,
              "texto_saida": sai.get("text_tokens", 0), "audio_saida": sai.get("audio_tokens", 0)}
    return sum(max(0, n) * PRECO_RT[k] for k, n in tokens.items()) / 1_000_000


def gasto_mes():
    return _ler_estado().get("gasto_rt", {}).get(datetime.now(FUSO).strftime("%Y-%m"), 0.0)


@app.post("/carro/realtime/uso")
@autenticado
@limitado(2000)
def realtime_uso():
    """O cockpit manda o 'usage' de cada resposta; aqui soma o gasto do mês."""
    u = (request.get_json(force=True, silent=True) or {}).get("usage") or {}
    custo = custo_resposta(u)
    estado = _ler_estado()
    mes = datetime.now(FUSO).strftime("%Y-%m")
    gastos = estado.setdefault("gasto_rt", {})
    gastos[mes] = round(gastos.get(mes, 0.0) + custo, 5)
    ESTADO.write_text(json.dumps(estado))
    return jsonify(mes=mes, gasto_usd=gastos[mes], teto_usd=TETO_USD)


@app.get("/carro/uso")
@autenticado
def uso():
    return jsonify(mes=datetime.now(FUSO).strftime("%Y-%m"), gasto_usd=round(gasto_mes(), 2), teto_usd=TETO_USD)


@app.post("/carro/realtime/sessao")
@autenticado
@limitado(60)
def realtime_sessao():
    """Chave temporária pro cockpit conectar direto na OpenAI, já com personalidade, contexto e ferramentas."""
    if gasto_mes() >= TETO_USD:  # bateu o teto do mês: o cockpit cai no modo reserva (bem mais barato)
        return jsonify(erro="teto do mês atingido"), 429
    corpo = {"session": {
        "type": "realtime", "model": MODELO_RT,
        "instructions": f"{PERSONA}\n\n{INSTRUCOES_RT}\n\n{contexto()}",
        "audio": {
            "input": {"transcription": {"model": "gpt-4o-mini-transcribe", "language": "pt"},
                      "turn_detection": {"type": "semantic_vad", "eagerness": "high"},
                      "noise_reduction": {"type": "far_field"}},
            "output": {"voice": VOZ_RT}},
        "tools": FERRAMENTAS_RT, "tool_choice": "auto"}}
    try:
        r = requests.post("https://api.openai.com/v1/realtime/client_secrets", json=corpo, timeout=10,
                          headers={"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '').strip()}"})
        r.raise_for_status()
        d = r.json()
        return jsonify(chave=d["value"], expira=d.get("expires_at"), modelo=MODELO_RT)
    except Exception as e:
        app.logger.warning("realtime sessão falhou: %s", e)
        return jsonify(erro="sem tempo real agora"), 502


@app.post("/carro/realtime/ferramenta")
@autenticado
@limitado(150)
def realtime_ferramenta():
    """Executa as ferramentas de dados que a IA pediu e devolve o resultado em texto pra ela falar."""
    p = request.get_json(force=True, silent=True) or {}
    nome, a = p.get("nome", ""), p.get("args") or {}
    t0 = time.time()
    try:
        if nome == "consultar_meta":
            saida = (consultas.meta(a.get("cliente", ""), a.get("periodo", "ontem"))
                     + "\nResponda em até 2 frases dizendo: quanto gastou (arredondado), quantos resultados "
                       "(conversas iniciadas contam como leads) e o custo por resultado.")
        elif nome == "consultar_agenda":
            saida = consultas.agenda(a.get("periodo", "hoje"))
        elif nome == "pesquisar_internet":
            saida = consultas.pesquisar(ia(), MODELO, a.get("pergunta", ""))
        elif nome == "tocar_musica":
            saida = spotify_uri(a.get("busca", ""), a.get("tipo", ""))
        else:
            saida = "ferramenta desconhecida"
    except Exception as e:
        app.logger.warning("ferramenta %s falhou: %s", nome, e)
        saida = "Não consegui puxar isso agora."
    registrar(sessao="realtime", ouvido=f"[{nome}] {json.dumps(a, ensure_ascii=False)}", fala=str(saida)[:500],
              acao=nome, parametros=a, ms_stt=0, ms_ia=int((time.time() - t0) * 1000), ms_voz=0)
    return jsonify(saida=saida)


# ── Avisos que o Jake dá sozinho (o cockpit pergunta a cada 2 min) ────────────

LIMITE_SALDO = float(os.environ.get("META_ALERTA_SALDO_LIMITE", "150"))


def _ler_estado():
    try:
        return json.loads(ESTADO.read_text())
    except Exception:
        return {}


@app.get("/carro/avisos")
@autenticado
@limitado(60)
def avisos():
    """No máximo 1 aviso por vez, cada um uma vez só: compromisso em 15 min, saldo baixo no Meta, chuva chegando."""
    agora = datetime.now(FUSO)
    if not 6 <= agora.hour < 23:
        return jsonify(aviso=None)
    lat = request.args.get("lat") or consultas.VARGINHA[0]
    lon = request.args.get("lon") or consultas.VARGINHA[1]
    estado = _ler_estado()
    dados = estado.setdefault("avisos_dados", {})
    hoje = agora.strftime("%Y-%m-%d")
    for k in [k for k, v in dados.items() if v < (agora - timedelta(days=2)).strftime("%Y-%m-%d")]:
        dados.pop(k)

    candidatos = []
    try:
        for e in consultas.compromissos_em(16):
            candidatos.append((f"agenda:{e['id']}", f"Patrão, {e['titulo']} começa em {e['minutos']} minutos."))
    except Exception as e:
        app.logger.warning("aviso agenda: %s", e)
    try:
        for c in consultas.saldos_baixos(LIMITE_SALDO):
            texto = (f"Patrão, a conta da {c['nome']} tá sem saldo no Meta, os anúncios vão parar." if c["saldo"] < 1
                     else f"Patrão, a conta da {c['nome']} tá com só {round(c['saldo'])} reais de saldo no Meta.")
            candidatos.append((f"saldo:{c['id']}:{hoje}", texto))
    except Exception as e:
        app.logger.warning("aviso saldo: %s", e)
    try:
        vai, chance = consultas.chuva_chegando(lat, lon)
        if vai:
            candidatos.append((f"chuva:{hoje}:{agora.hour // 3}",
                               f"Patrão, {chance}% de chance de chuva na próxima hora. Bom deixar o farol ligado."))
    except Exception as e:
        app.logger.warning("aviso chuva: %s", e)

    if request.args.get("teste") == "1":  # só lista, sem marcar como dado nem gerar voz
        return jsonify(candidatos=[{"id": c, "texto": t} for c, t in candidatos])
    for chave, texto in candidatos:
        if chave in dados:
            continue
        dados[chave] = hoje
        ESTADO.write_text(json.dumps(estado))
        registrar(sessao="aviso", ouvido=chave, fala=texto, acao="aviso", parametros={},
                  ms_stt=0, ms_ia=0, ms_voz=0)
        return jsonify(aviso={"id": chave, "texto": texto, "audio_b64": voz_b64(texto)})
    ESTADO.write_text(json.dumps(estado))
    return jsonify(aviso=None)


_rotas = {}


@app.get("/carro/rota")
@autenticado
@limitado(60)
def rota():
    """Rota pro mini mapa: acha o destino (Nominatim) e traça o caminho (OSRM). Cache por destino."""
    lat, lon, para = request.args.get("lat"), request.args.get("lon"), (request.args.get("para") or "").strip()
    if not (lat and lon and para):
        return jsonify(erro="faltou origem ou destino"), 400
    chave = f"{float(lat):.2f},{float(lon):.2f}|{para.lower()}"
    if chave in _rotas:
        return jsonify(_rotas[chave])
    try:
        g = requests.get("https://nominatim.openstreetmap.org/search", params={
            "q": para, "format": "json", "limit": 1, "countrycodes": "br",
            "viewbox": f"{float(lon) - 3},{float(lat) + 3},{float(lon) + 3},{float(lat) - 3}"},
            headers={"User-Agent": "jake-carro/1.0"}, timeout=6).json()
        if not g:
            return jsonify(erro="destino não encontrado"), 404
        dlat, dlon = float(g[0]["lat"]), float(g[0]["lon"])
        r = requests.get(f"https://router.project-osrm.org/route/v1/driving/{lon},{lat};{dlon},{dlat}",
                         params={"overview": "simplified", "geometries": "geojson"}, timeout=8).json()
        trajeto = r["routes"][0]
        minutos = round(trajeto["duration"] / 60)
        dados = {"pontos": [[c[1], c[0]] for c in trajeto["geometry"]["coordinates"]],
                 "km": round(trajeto["distance"] / 1000),
                 "tempo": f"{minutos // 60}h{minutos % 60:02d}" if minutos >= 60 else f"{minutos} min"}
    except Exception as e:
        app.logger.warning("rota falhou: %s", e)
        return jsonify(erro="sem rota agora"), 502
    _rotas[chave] = dados
    return jsonify(dados)


@app.get("/carro/apk")
@autenticado
def apk():
    return _enviar_apk()


@app.get("/b/<codigo>")
def apk_curto(codigo):
    """Link curto pra digitar no navegador da central (JAKE_CARRO_CODIGO_APK=codigo:AAAA-MM-DD)."""
    valor = os.environ.get("JAKE_CARRO_CODIGO_APK", "")
    certo, _, validade = valor.partition(":")
    if not certo or codigo != certo or datetime.now(FUSO).strftime("%Y-%m-%d") > validade:
        time.sleep(1)  # freia quem tenta adivinhar
        return jsonify(erro="link inválido ou vencido"), 404
    return _enviar_apk()


def _enviar_apk():
    info = versao_apk()
    arquivo = APK_DIR / info.get("nome", "")
    if not info.get("nome") or not arquivo.exists():
        return jsonify(erro="nenhum APK publicado"), 404
    return send_file(arquivo, mimetype="application/vnd.android.package-archive",
                     as_attachment=True, download_name="jake-carro.apk")


criar_tabelas()
_carregar_lugares()
threading.Thread(target=consultas.contas_meta, daemon=True).start()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("JAKE_CARRO_PORTA", "5055")))
