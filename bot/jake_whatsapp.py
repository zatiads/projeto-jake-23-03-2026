"""
jake_whatsapp.py — Bot Jake no WhatsApp via Evolution API.
Flask :5051 recebe webhooks. APScheduler dispara crons internos.
"""
import os
import sys
import json
import time
import logging

# Garantir que /root está no path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

from flask import Flask, request, jsonify
import anthropic
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from bot.whatsapp_handlers import (
    send_text, jid_to_chat_id,
    carregar_historico, salvar_mensagem,
    get_grupos, encontrar_grupo,
    resumo_gestor, financeiro_context,
    verificar_conexao, download_media_bytes,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
AUTHORIZED_JID     = os.environ.get("WA_AUTHORIZED_JID", "").strip()
AUTHORIZED_NUMBER  = os.environ.get("WA_AUTHORIZED_NUMBER", "").strip()
WEBHOOK_SECRET     = os.environ.get("EVOLUTION_WEBHOOK_SECRET", "").strip()
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "").strip()
SP_TZ              = pytz.timezone("America/Sao_Paulo")

# ── Prompt (copiado literalmente de bot/jake_telegram.py) ─────────────────────
PROMPT_ANALISTA = """Voce e Jake - a inteligencia artificial mais avancada em marketing digital do Brasil. Voce e o parceiro estrategico do Bruno, gestor de trafego com carteira de clientes em educacao, saude e servicos.

SUAS COMPETENCIAS (dominio absoluto):
- Trafego pago: Meta Ads, Google Ads, TikTok Ads - estrutura, otimizacao, escala
- Analise de metricas: ROI, ROAS, CPA, CPL, CTR, frequencia, saturacao de publico
- Funis de vendas: topo, meio e fundo - diagnostico e correcao
- Copywriting de alta conversao: anuncios, paginas, WhatsApp, e-mail
- Lancamentos digitais: PLs, perpetuos, eventos online, simposios, webinarios
- Estrategia de conteudo: Instagram, YouTube, TikTok, WhatsApp
- CRO (otimizacao de conversao): landing pages, criativos, ofertas
- Posicionamento de marca e diferenciacao competitiva
- Psicologia do consumidor e gatilhos mentais
- Gestao de agencia: precificacao, processos, retencao de clientes

COMO VOCE RESPONDE:
- Direto ao ponto. Sem enrolacao, sem resposta generica.
- Quando receber metricas, diagnostica o problema real e da o proximo passo concreto.
- Quando receber contexto de cliente, pensa como dono do negocio, nao como executor.
- Usa dados e referencias reais quando possivel.
- Fala como um socio inteligente, nao como um assistente.
- Quando a pergunta for estrategica, pensa em 3 camadas: o que fazer HOJE, essa SEMANA e esse MES.
- NUNCA diz "depende" sem explicar de que depende e qual a sua recomendacao.
- NUNCA use a palavra 'automacao'.

Sempre chame o Bruno de 'Patrao'.

SUAS FUNCOES OPERACIONAIS — VOCE TEM ESSAS CAPACIDADES E ELAS FUNCIONAM:
- SUBIR ANUNCIOS: "sobe [link drive] para [cliente], R$XX" → voce baixa o criativo do Google Drive e sobe nas contas Meta dos clientes. JA IMPLEMENTADO.
- PAUSAR CAMPANHAS: "pausa as campanhas do [cliente]" → voce lista e pausa. JA IMPLEMENTADO.
- ATIVAR CAMPANHAS: "ativa as campanhas do [cliente]" → voce lista e ativa. JA IMPLEMENTADO.

IMPORTANTE — NUNCA diga que nao tem funcoes novas ou que nao recebeu nada novo. Voce e um sistema que roda em servidor, nao um chat comum. Suas funcionalidades sao codigo real rodando no VPS — voce nao precisa "receber" nada no contexto do chat para ter essas capacidades. Elas ja estao implementadas no servidor e funcionam quando voce recebe os comandos certos.

Quando o Patrao disser que te deu novas funcoes, confirme e explique o que voce consegue fazer agora. Nao questione, nao negue."""

PROMPT_GESTOR = """Você é um parser de comandos de gestão de tráfego. Analise a mensagem e retorne SOMENTE um JSON válido (sem markdown, sem texto extra) com esta estrutura:

{
  "intencao": "subir_anuncio" | "pausar_campanha" | "ativar_campanha" | "desconhecida",
  "drive_link": "URL completa do Google Drive ou null",
  "clientes": ["lista", "de", "nomes", "mencionados"],
  "orcamento": numero_float_ou_null,
  "campanha_tipo": "MESSAGES" | "ENGAGEMENT" | "PURCHASE" | null
}

Regras:
- Se mencionar "sobe", "subir", "upload", "anuncio" com link do Drive → subir_anuncio
- Se mencionar "pausa", "pausar", "desativa" → pausar_campanha
- Se mencionar "ativa", "ativar", "liga", "retoma" → ativar_campanha
- campanha_tipo padrão: MESSAGES se não informado e intencao = subir_anuncio
- Extraia o valor em R$ como orcamento float (ex: "R$30" → 30.0)
- clientes: lista exatamente como o usuário escreveu, em minúsculas
- NUNCA inclua "jake" na lista de clientes — Jake é o nome do assistente, não um cliente
- Se a mensagem não citar nenhum cliente real, retorne clientes: []"""


def interpretar_comando(texto: str) -> dict:
    """Interpreta mensagem do Bruno e retorna dict de intenção. Nunca lança exceção."""
    import json as _json
    try:
        raw = chamar_claude(PROMPT_GESTOR, texto)
        # Limpar possível markdown
        raw = raw.strip()
        if "```" in raw:
            # Remove markdown code fences — extract content between first ``` pair
            parts = raw.split("```")
            if len(parts) >= 3:
                raw = parts[1]
            elif len(parts) == 2:
                raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return _json.loads(raw.strip())
    except Exception:
        return {"intencao": "desconhecida", "drive_link": None, "clientes": [], "orcamento": None, "campanha_tipo": None}


def _buscar_clientes_db() -> list:
    """Busca todos os clientes ativos do banco. Retorna lista de dicts."""
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_root, ".env"))
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, nome, agencia, account_id, token_key, orcamento_diario, publico_salvo_id, publico_salvo_nome FROM ad_client_profiles ORDER BY nome")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Erro ao buscar clientes: {e}")
        return []


def resolver_clientes(nomes: list) -> dict:
    """
    Faz fuzzy match dos nomes digitados contra o banco.
    Retorna:
      {
        "confirmados": [{"id": ..., "nome": ..., ...}],
        "ambiguos": [{"digitado": "...", "candidato": {...}, "score": 0.85}],
        "nao_encontrados": ["nome1", ...]
      }
    """
    from difflib import SequenceMatcher
    clientes_db = _buscar_clientes_db()
    confirmados, ambiguos, nao_encontrados = [], [], []

    for nome_digitado in nomes:
        nd = nome_digitado.lower().strip()
        melhor_score = 0.0
        melhor_cliente = None

        for c in clientes_db:
            score = SequenceMatcher(None, nd, c["nome"].lower()).ratio()
            # Bonus se o nome digitado está contido no nome do cliente
            if nd in c["nome"].lower():
                score = max(score, 0.85)
            if score > melhor_score:
                melhor_score = score
                melhor_cliente = c

        if melhor_score >= 0.80 and melhor_cliente:
            confirmados.append(melhor_cliente)
        elif melhor_score >= 0.50 and melhor_cliente:
            ambiguos.append({"digitado": nome_digitado, "candidato": melhor_cliente, "score": melhor_score})
        else:
            nao_encontrados.append(nome_digitado)

    return {"confirmados": confirmados, "ambiguos": ambiguos, "nao_encontrados": nao_encontrados}


# ── Claude ────────────────────────────────────────────────────────────────────
_anthropic_client = None

def get_claude():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client

def chamar_claude(prompt_sistema: str, mensagem: str, historico: list = None) -> str:
    """Chama Claude com retry para 529 (overloaded). Retorna texto da resposta."""
    messages = list(historico or []) + [{"role": "user", "content": mensagem}]
    for attempt in range(3):
        try:
            resp = get_claude().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=prompt_sistema,
                messages=messages,
            )
            return resp.content[0].text
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    return "Deu ruim no cerebro, Patrao. Tenta de novo daqui a pouco."

# ── Roteamento de intencao ─────────────────────────────────────────────────────

_KEYWORDS_FINANCEIRO = [
    "gastei", "gasto", "receita", "despesa", "saldo", "financeiro",
    "dinheiro", "transacao", "quanto entrou", "quanto saiu", "mes",
]

_KEYWORDS_GRUPO = ["manda", "envia", "grupo", "bom dia", "boa semana", "boa tarde", "boa noite"]

_KEYWORDS_CLIENTES = [
    "cliente", "clientes", "carteira", "orçamento", "orcamento", "investimento",
    "objetivo", "meta ads", "campanha", "campanhas", "agencia", "agência",
    "dentto", "piloti", "quanto investe", "quanto tá investindo", "quanto ta investindo",
    "quais clientes", "lista de clientes", "meus clientes", "portfólio", "portfolio",
]

def _eh_financeiro(texto: str) -> bool:
    t = texto.lower()
    return any(k in t for k in _KEYWORDS_FINANCEIRO)

def _eh_grupo(texto: str) -> bool:
    t = texto.lower()
    return sum(1 for k in _KEYWORDS_GRUPO if k in t) >= 2

def _eh_sobre_clientes(texto: str) -> bool:
    t = texto.lower()
    return any(k in t for k in _KEYWORDS_CLIENTES)

def _context_clientes() -> str:
    """Monta resumo da carteira de clientes do banco para injetar no contexto."""
    try:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT nome, agencia, account_id, campanha_tipo, orcamento_diario,
                   link_url, publico_salvo_nome
            FROM ad_client_profiles ORDER BY agencia, nome
        """)
        rows = cur.fetchall()
        conn.close()

        _TIPO_LABEL = {"MESSAGES": "Leads/WhatsApp", "ENGAGEMENT": "Engajamento/Instagram", "PURCHASE": "Compras"}
        linhas = ["CARTEIRA DE CLIENTES DO BRUNO:"]
        agencia_atual = None
        for r in rows:
            ag = r["agencia"] or "Sem agência"
            if ag != agencia_atual:
                linhas.append(f"\n[{ag.upper()}]")
                agencia_atual = ag
            orc_mensal = round(float(r["orcamento_diario"] or 0) * 30)
            tipo = _TIPO_LABEL.get(r["campanha_tipo"] or "", r["campanha_tipo"] or "—")
            linhas.append(
                f"  • {r['nome']} | R${orc_mensal}/mês | {tipo}"
                + (f" | público: {r['publico_salvo_nome']}" if r.get('publico_salvo_nome') else "")
            )
        return "\n".join(linhas)
    except Exception as e:
        logger.error(f"_context_clientes error: {e}")
        return ""

import time as _time

# ── Sessões de conversa (estado por JID) ──────────────────────────────────────
_sessoes: dict = {}
_TTL_SESSAO = 600  # 10 minutos
_sessoes_lock = __import__("threading").Lock()
_SESSOES_FILE = "/tmp/jake_wa_sessoes.json"

# Contexto recente após upload — persiste 30min para "ativa ela" funcionar sem reperguntar cliente
_ultimo_contexto: dict = {}  # jid -> {clientes, campanha_id, campanha_nome, ts}
_TTL_CONTEXTO = 1800


def _salvar_sessoes():
    """Persiste sessões em disco para sobreviver a restarts."""
    try:
        with open(_SESSOES_FILE, "w") as f:
            json.dump(_sessoes, f)
    except Exception:
        pass


def _carregar_sessoes():
    """Restaura sessões do disco na inicialização."""
    global _sessoes
    try:
        with open(_SESSOES_FILE) as f:
            dados = json.load(f)
        agora = _time.time()
        _sessoes = {jid: s for jid, s in dados.items() if s.get("expira_em", 0) > agora}
    except Exception:
        _sessoes = {}


_carregar_sessoes()


def _get_sessao(jid: str):
    with _sessoes_lock:
        s = _sessoes.get(jid)
        if s and _time.time() > s["expira_em"]:
            _sessoes.pop(jid, None)
            _salvar_sessoes()
            return None
        return s


def _set_sessao(jid: str, estado: str, payload: dict):
    with _sessoes_lock:
        _sessoes[jid] = {
            "estado":    estado,
            "payload":   payload,
            "expira_em": _time.time() + _TTL_SESSAO,
        }
        _salvar_sessoes()


def _limpar_sessao(jid: str):
    with _sessoes_lock:
        _sessoes.pop(jid, None)
        _salvar_sessoes()


_KEYWORDS_GESTOR = [
    "sobe", "subir", "upload", "anuncio", "anúncio",
    "pausa", "pausar", "ativa", "ativar", "drive.google",
    "campanha", "campanhas",
    "escolher público", "escolher publico", "mudar público", "mudar publico",
    "outro público", "outro publico", "listar públicos", "listar publicos",
]

def _eh_gestor_cmd(texto: str) -> bool:
    t = texto.lower()
    return any(k in t for k in _KEYWORDS_GESTOR)


def _parse_estrutura(texto: str) -> dict | None:
    """Parseia notação X-Y-Z (campanhas-conjuntos-criativos). Retorna dict ou None se inválido."""
    import re as _re_est
    m = _re_est.match(r'^(\d+)[x\-](\d+)[x\-](\d+)$', texto.strip())
    if not m:
        return None
    c, cs, cr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if c < 1 or cs < 1 or cr < 1 or c > 10 or cs > 10 or cr > 50:
        return None
    return {"campanhas": c, "conjuntos": cs, "criativos": cr}


_TIPO_LABEL = {"MESSAGES": "Mensagem", "ENGAGEMENT": "Engajamento", "PURCHASE": "Conversão"}
_CTA_LABEL  = {
    "MESSAGES":   "Clique e fale com a gente no WhatsApp!",
    "ENGAGEMENT": "Clique e saiba mais!",
    "PURCHASE":   "Clique e garanta agora!",
}


def _gerar_copy_aida(arquivo_local: str, campanha_tipo: str, segmento: str, cliente_nome: str) -> dict:
    """Analisa o criativo com Claude Vision e gera copy AIDA estruturada."""
    import base64, re as _re_copy
    ext = os.path.splitext(arquivo_local)[1].lower()
    tipo_label = {"MESSAGES": "mensagens no WhatsApp", "ENGAGEMENT": "engajamento", "PURCHASE": "conversões"}.get(campanha_tipo, "mensagens")
    cta_label  = _CTA_LABEL.get(campanha_tipo, "Clique e fale com a gente no WhatsApp!")
    cta_val    = "WHATSAPP_MESSAGE" if campanha_tipo == "MESSAGES" else "LEARN_MORE"

    prompt_txt = (
        f"Você é um copywriter especialista em Meta Ads no Brasil.\n"
        f"Cliente: {cliente_nome} | Segmento: {segmento or 'não informado'} | Objetivo: {tipo_label}\n\n"
        f"Analise este criativo e escreva uma copy persuasiva no modelo AIDA:\n"
        f"- titulo: headline de até 40 caracteres (Atenção)\n"
        f"- texto: corpo com Interesse + Desejo + Ação, até 200 caracteres.\n"
        f"  Termine SEMPRE com: \"{cta_label}\"\n\n"
        f'Responda APENAS com JSON: {{"titulo":"...","texto":"..."}}'
    )

    messages: list = []
    if ext not in (".mp4", ".mov", ".avi", ".webm"):
        try:
            with open(arquivo_local, "rb") as f:
                img_b64 = base64.standard_b64encode(f.read()).decode()
            mime = "image/png" if ext == ".png" else "image/gif" if ext == ".gif" else "image/jpeg"
            messages = [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": img_b64}},
                {"type": "text", "text": prompt_txt},
            ]}]
        except Exception:
            messages = [{"role": "user", "content": prompt_txt + "\n(imagem indisponível — gere copy genérica para o segmento)"}]
    else:
        messages = [{"role": "user", "content": prompt_txt + "\n(criativo em vídeo — gere copy genérica para o segmento)"}]

    def _parse_copy(raw: str) -> dict | None:
        m = _re_copy.search(r'\{.*\}', raw, _re_copy.DOTALL)
        if m:
            data = json.loads(m.group())
            if data.get("titulo") or data.get("texto"):
                return {
                    "titulo": (data.get("titulo") or "")[:40],
                    "texto":  (data.get("texto")  or "")[:300],
                    "cta":    cta_val,
                }
        return None

    # Tenta Anthropic (Claude Vision)
    if ANTHROPIC_API_KEY:
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=400, messages=messages)
            result = _parse_copy(resp.content[0].text.strip())
            if result:
                return result
        except Exception as e:
            logger.warning(f"_gerar_copy_aida (Anthropic) falhou: {e}")

    # Fallback: OpenAI GPT-4o Vision
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            import openai as _openai
            import base64 as _b64
            oai = _openai.OpenAI(api_key=openai_key)
            # Monta mensagem para OpenAI
            if ext not in (".mp4", ".mov", ".avi", ".webm"):
                with open(arquivo_local, "rb") as f:
                    img_b64 = _b64.standard_b64encode(f.read()).decode()
                mime = "image/png" if ext == ".png" else "image/gif" if ext == ".gif" else "image/jpeg"
                oai_content = [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                    {"type": "text", "text": prompt_txt},
                ]
            else:
                oai_content = prompt_txt + "\n(criativo em vídeo — gere copy genérica para o segmento)"
            oai_resp = oai.chat.completions.create(
                model="gpt-4o",
                max_tokens=400,
                messages=[{"role": "user", "content": oai_content}],
            )
            result = _parse_copy(oai_resp.choices[0].message.content.strip())
            if result:
                return result
        except Exception as e:
            logger.warning(f"_gerar_copy_aida (OpenAI fallback) falhou: {e}")

    return {"titulo": "", "texto": "", "cta": cta_val}


def _formatar_resumo_subida(clientes: list, orcamento: float, campanha_tipo: str, campanha_nome: str,
                             estrutura: dict | None = None, orcamento_por_conjunto: float | None = None,
                             copy: dict | None = None) -> str:
    linhas = [f"🚀 *{campanha_nome}*", ""]
    for c in clientes:
        pub_nome = c.get("publico_salvo_nome") or "—"
        linhas.append(f"👤 {c['nome']}")
        linhas.append(f"   🎯 Público: {pub_nome}")
        linhas.append("")
    if orcamento_por_conjunto:
        linhas.append(f"💰 R${orcamento:.0f}/dia (R${orcamento_por_conjunto:.0f} por conjunto)")
    else:
        linhas.append(f"💰 R${orcamento:.0f}/dia")
    linhas.append(f"📣 Tipo: {_TIPO_LABEL.get(campanha_tipo, campanha_tipo)}")
    if estrutura:
        linhas.append(f"📊 {estrutura['campanhas']}-{estrutura['conjuntos']}-{estrutura['criativos']}")
    linhas.append("")
    linhas.append("✅ Confirma? (sim/não)")
    return "\n".join(linhas)


def _formatar_resultado_stream(eventos: list, total_clientes: int) -> str:
    ok = [e for e in eventos if e.get("tipo") == "concluido" or e.get("status") == "ok"]
    erros = [e for e in eventos if e.get("tipo") == "erro" or e.get("status") == "erro"]
    linhas = [f"Anúncio subido! {len(ok)}/{total_clientes} concluídos"]
    for e in ok:
        camp = e.get("campanha_id", "")
        nome = e.get("cliente", "")
        ads = e.get("ads", 1)
        sufixo = f" — {ads} anúncio(s)" if ads and ads > 1 else ""
        linhas.append(f"  ✅ {nome}{sufixo}" + (f" (camp. {camp})" if camp else ""))
    for e in erros:
        nome = e.get("cliente", "")
        msg = e.get("erro", e.get("message", "erro"))
        linhas.append(f"  ❌ {nome}: {msg}")
    return "\n".join(linhas)


def _montar_confirmacao_final(sender_jid: str, destino: str, cmd: dict, clientes: list):
    intencao = cmd["intencao"]

    if intencao == "subir_anuncio":
        # 1. Estrutura da campanha (X-Y-Z)
        estrutura = cmd.get("estrutura")
        if not estrutura:
            _set_sessao(sender_jid, "aguardando_estrutura", {"cmd": cmd, "clientes": clientes})
            send_text(destino, "📊 Qual a estrutura da campanha? (ex: 1-1-7 = 1 campanha, 1 conjunto, 7 criativos)")
            return

        # Total de arquivos = conjuntos × criativos_por_conjunto
        num_conjuntos   = estrutura.get("conjuntos", 1)
        cri_por_conjunto = estrutura.get("criativos", 1)
        num_criativos   = num_conjuntos * cri_por_conjunto

        # 2. Criativos (arquivos ou drive link)
        drive_link     = cmd.get("drive_link") or ""
        arquivo_local  = cmd.get("arquivo_local") or ""
        arquivos_locais = [a for a in (cmd.get("arquivos_locais") or []) if a]
        if arquivo_local and arquivo_local not in arquivos_locais:
            arquivos_locais.insert(0, arquivo_local)
        cmd["arquivos_locais"] = arquivos_locais

        label = f"{num_criativos} criativos ({num_conjuntos} conjunto(s) × {cri_por_conjunto})" if num_conjuntos > 1 else f"{num_criativos} criativo(s)"

        total_files = len(arquivos_locais) + (1 if drive_link else 0)
        if total_files == 0:
            if num_criativos == 1:
                _set_sessao(sender_jid, "aguardando_drive_link", {"cmd": cmd, "clientes": clientes})
                send_text(destino, "📸 Envia o criativo (imagem/vídeo aqui ou link do Google Drive).")
            else:
                _set_sessao(sender_jid, "aguardando_criativos", {"cmd": cmd, "clientes": clientes})
                send_text(destino, f"📸 Envia os {label} (0/{num_criativos} recebidos).")
            return

        if total_files < num_criativos:
            faltam = num_criativos - total_files
            _set_sessao(sender_jid, "aguardando_criativos", {"cmd": cmd, "clientes": clientes})
            send_text(destino, f"📸 Recebido! ({total_files}/{num_criativos}) — envia mais {faltam}.")
            return

        # 3. Orçamento — sempre pergunta, nunca puxa do banco
        orcamento = cmd.get("orcamento")
        if not orcamento:
            _hint = " (pode dizer ex: 30 ou 30, sendo 15 em cada conjunto)" if num_conjuntos > 1 else ""
            send_text(destino, f"💰 Qual o orçamento diário da campanha?{_hint}")
            _set_sessao(sender_jid, "aguardando_orcamento", {"cmd": cmd, "clientes": clientes})
            return

        # 4. Público salvo obrigatório
        sem_publico = [c["nome"] for c in clientes if not c.get("publico_salvo_id")]
        if sem_publico:
            nomes = ", ".join(sem_publico)
            send_text(destino, f"Não posso subir — cliente(s) sem Público Salvo configurado: {nomes}\nCadastra o ID do público no Jake OS (aba Anúncios → editar cliente) antes de tentar de novo.")
            return

        campanha_tipo = cmd.get("campanha_tipo") or "MESSAGES"
        import datetime
        # Nomenclatura estruturada: Cliente | Tipo | Mês26
        _tipo_lbl = _TIPO_LABEL.get(campanha_tipo, campanha_tipo)
        _MESES_PT = {"Jan":"Jan","Feb":"Fev","Mar":"Mar","Apr":"Abr","May":"Mai","Jun":"Jun","Jul":"Jul","Aug":"Ago","Sep":"Set","Oct":"Out","Nov":"Nov","Dec":"Dez"}
        _mes_en   = datetime.date.today().strftime("%b")
        _mes_ano  = _MESES_PT.get(_mes_en, _mes_en) + datetime.date.today().strftime("%y")  # Mai26
        _nome_base = clientes[0]["nome"] if len(clientes) == 1 else "Multi"
        campanha_nome = cmd.get("campanha_nome") or f"{_tipo_lbl} | {_mes_ano}"
        orcamento_por_conjunto = cmd.get("orcamento_por_conjunto") or None

        # Gera copy via IA para cada criativo (se ainda não gerado)
        _segmento = clientes[0].get("segmento", "") if clientes else ""
        copies_list = cmd.get("copies_list") or []
        if arquivos_locais and len(copies_list) < len(arquivos_locais):
            send_text(destino, f"🤖 Analisando {len(arquivos_locais)} criativo(s) e gerando copies...")
            copies_list = []
            _copy_falhou = False
            for _arq in arquivos_locais:
                _c = _gerar_copy_aida(_arq, campanha_tipo, _segmento, _nome_base)
                if not _c.get("titulo") and not _c.get("texto"):
                    _copy_falhou = True
                copies_list.append(_c)
            cmd["copies_list"] = copies_list
            if _copy_falhou:
                send_text(destino, "⚠️ Não consegui gerar as copies automaticamente (IA indisponível). Você pode confirmar assim mesmo e editar depois, ou me mandar os textos agora.")
        # copy principal = primeiro criativo (para exibição na confirmação)
        copy = copies_list[0] if copies_list else (cmd.get("copy") or {})

        resumo = _formatar_resumo_subida(clientes, float(orcamento), campanha_tipo, campanha_nome, estrutura, orcamento_por_conjunto, copy=copy)
        send_text(destino, resumo)

        # Mostra todas as copies se houver conteúdo gerado
        _copies_com_conteudo = [cp for cp in copies_list if cp.get("titulo") or cp.get("texto")]
        if _copies_com_conteudo:
            linhas_copies = ["✍️ *Copies por criativo:*", ""]
            for i_c, cp in enumerate(copies_list, 1):
                linhas_copies.append(f"*Criativo {i_c}:*")
                if cp.get("titulo"):
                    linhas_copies.append(f"*{cp['titulo']}*")
                if cp.get("texto"):
                    linhas_copies.append(cp["texto"])
                linhas_copies.append("")
            linhas_copies.append("Se quiser trocar alguma copy, me avisa qual criativo e manda o texto novo.")
            send_text(destino, "\n".join(linhas_copies))
        _set_sessao(sender_jid, "aguardando_confirmacao_subida", {
            "cmd": cmd, "clientes": clientes,
            "orcamento":               float(orcamento),
            "orcamento_por_conjunto":  float(orcamento_por_conjunto) if orcamento_por_conjunto else None,
            "campanha_tipo":           campanha_tipo,
            "campanha_nome":           campanha_nome,
            "drive_link":              drive_link,
            "arquivo_local":           arquivo_local,
            "arquivos_locais":         arquivos_locais,
            "estrutura":               estrutura,
            "copy":                    copy,
            "copies_list":             copies_list,
        })

    elif intencao in ("pausar_campanha", "ativar_campanha"):
        from bot.gestor_whatsapp import get_gestor
        acao = "pausar" if intencao == "pausar_campanha" else "ativar"
        campanha_id_ctx = cmd.get("_campanha_id_ctx", "")
        campanha_nome_ctx = cmd.get("_campanha_nome_ctx", "")
        try:
            gestor = get_gestor()
            todas_campanhas = []
            for c in clientes:
                camps = gestor.listar_campanhas(c["account_id"], c["token_key"])
                # Se temos campanha_id do contexto, filtra só essa — não lista todas
                if campanha_id_ctx:
                    camps_filtradas = [cp for cp in camps if cp["id"] == campanha_id_ctx]
                    # Se não achou por ID (ex: status mudou), tenta pelo nome
                    if not camps_filtradas and campanha_nome_ctx:
                        camps_filtradas = [cp for cp in camps if cp.get("name", "") == campanha_nome_ctx]
                else:
                    status_filtro = "ACTIVE" if acao == "pausar" else "PAUSED"
                    camps_filtradas = [cp for cp in camps if cp.get("status") == status_filtro or cp.get("effective_status") == status_filtro]
                for cp in camps_filtradas:
                    cp["_cliente"] = c
                todas_campanhas.extend(camps_filtradas)

            if not todas_campanhas:
                send_text(destino, f"Nenhuma campanha para {acao} encontrada nos clientes informados.")
                return

            nomes_camps = "\n".join(f"  • {cp['name']} ({cp['_cliente']['nome']})" for cp in todas_campanhas[:10])
            send_text(destino, f"Vou {acao} {len(todas_campanhas)} campanha(s):\n{nomes_camps}\nConfirma? (sim/não)")
            _set_sessao(sender_jid, f"aguardando_confirmacao_{acao}", {
                "campanhas": todas_campanhas,
                "clientes": clientes,
            })
        except Exception as e:
            send_text(destino, f"Erro ao buscar campanhas: {e}")


def _processar_gestor_cmd(sender_jid: str, texto: str):
    """Interpreta comando de gestor, resolve clientes e pede confirmação."""
    destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid

    cmd = interpretar_comando(texto)
    intencao = cmd.get("intencao", "desconhecida")

    _PALAVRAS_SUBIR   = ["sobe", "subir", "upload", "anuncio", "anúncio", "criativo"]
    _PALAVRAS_PUBLICO = ["escolher público", "escolher publico", "mudar público", "mudar publico",
                         "outro público", "outro publico", "listar públicos", "listar publicos"]
    if intencao == "desconhecida":
        txt = texto.lower()
        if any(p in txt for p in _PALAVRAS_PUBLICO):
            _set_sessao(sender_jid, "aguardando_cliente_publico", {"cmd": {"intencao": "escolher_publico"}})
            send_text(destino, "Pra qual cliente você quer escolher o público?")
            return
        if any(p in txt for p in _PALAVRAS_SUBIR):
            # Parece querer subir anúncio mas faltam detalhes — inicia conversa guiada
            _set_sessao(sender_jid, "aguardando_cliente", {"cmd": {"intencao": "subir_anuncio", "drive_link": None, "orcamento": None, "campanha_tipo": "MESSAGES"}})
            send_text(destino, "Pra qual cliente você quer subir? Me passa o nome.")
        else:
            send_text(destino, "Não entendi o comando, Patrão. Tenta: 'Sobe [link drive] para [cliente], R$30' ou 'Pausa campanhas do [cliente]'")
        return

    nomes = cmd.get("clientes") or []
    if not nomes:
        # Para ativar/pausar: tenta usar contexto recente do último upload
        if intencao in ("pausar_campanha", "ativar_campanha"):
            ctx = _ultimo_contexto.get(sender_jid)
            if ctx and _time.time() - ctx["ts"] < _TTL_CONTEXTO:
                cmd["_campanha_id_ctx"] = ctx["campanha_id"]
                cmd["_campanha_nome_ctx"] = ctx["campanha_nome"]
                nomes = [c["nome"] for c in ctx["clientes"]]
        if not nomes:
            # Intenção identificada mas sem clientes — pergunta
            _set_sessao(sender_jid, "aguardando_cliente", {"cmd": cmd})
            send_text(destino, "Pra qual cliente? Me passa o nome.")
            return

    resolucao = resolver_clientes(nomes)

    if resolucao["nao_encontrados"]:
        nomes_str = ", ".join(resolucao["nao_encontrados"])
        send_text(destino, f"Não encontrei: {nomes_str}. Verifica o nome ou lista os clientes com 'lista clientes'.")
        return

    if resolucao["ambiguos"]:
        amb = resolucao["ambiguos"][0]
        _set_sessao(sender_jid, "aguardando_confirmacao_clientes", {
            "cmd": cmd,
            "confirmados": resolucao["confirmados"],
            "ambiguos": resolucao["ambiguos"],
            "ambiguo_atual": 0,
        })
        cand = amb["candidato"]
        send_text(destino, f"Encontrei *{cand['nome']}* para '{amb['digitado']}', é esse? (sim/não)")
        return

    clientes = resolucao["confirmados"]
    _montar_confirmacao_final(sender_jid, destino, cmd, clientes)


def _listar_publicos_para_cliente(sender_jid: str, destino: str, cliente: dict, cmd: dict):
    """Busca públicos salvos de um cliente via Jake OS e pede escolha."""
    try:
        from bot.gestor_whatsapp import get_gestor
        gestor = get_gestor()
        publicos = gestor.listar_publicos_salvos(cliente["id"])
    except Exception as e:
        send_text(destino, f"Erro ao buscar públicos: {e}")
        return
    if not publicos:
        send_text(destino, f"Nenhum público salvo encontrado em *{cliente['nome']}*. Cria um no Gerenciador de Anúncios primeiro.")
        return
    linhas = [f"Públicos salvos de *{cliente['nome']}*:"]
    for i, p in enumerate(publicos, 1):
        linhas.append(f"  {i}. {p['nome']}")
    linhas.append("Qual número?")
    _set_sessao(sender_jid, "aguardando_escolha_publico", {
        "publicos": publicos,
        "cliente": cliente,
        "cmd": cmd,
    })
    send_text(destino, "\n".join(linhas))


def _processar_confirmacao(sender_jid: str, texto: str, sessao: dict):
    """Processa resposta do Bruno em uma sessão de confirmação ativa."""
    destino   = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid
    estado    = sessao["estado"]
    payload   = sessao["payload"]
    import re as _re_resp
    resposta  = texto.lower().strip()
    negativo  = bool(_re_resp.search(r'\b(não|nao|cancela|cancel)\b', resposta)) or resposta == "n"
    positivo  = bool(_re_resp.search(r'\b(sim|yes|ok|confirma)\b', resposta)) or resposta == "s"

    # ── Estrutura da campanha (X-Y-Z) ────────────────────────────────────────
    if estado == "aguardando_estrutura":
        estrutura = _parse_estrutura(texto)
        if not estrutura:
            send_text(destino, "Formato inválido. Use X-Y-Z, ex: 1-1-7 (campanhas-conjuntos-criativos).")
            return
        payload["cmd"]["estrutura"] = estrutura
        clientes = payload.get("clientes", [])
        _limpar_sessao(sender_jid)
        _montar_confirmacao_final(sender_jid, destino, payload["cmd"], clientes)
        return

    # ── Coleta de múltiplos criativos ────────────────────────────────────────
    if estado == "aguardando_criativos":
        # Aqui chegam textos durante a coleta — ignora se não for cancelamento
        if negativo:
            _limpar_sessao(sender_jid)
            send_text(destino, "❌ Cancelado, Patrão.")
            return
        estrutura = payload["cmd"].get("estrutura", {})
        num_criativos = estrutura.get("criativos", 1)
        recebidos = len(payload["cmd"].get("arquivos_locais") or [])
        send_text(destino, f"Aguardando criativos... ({recebidos}/{num_criativos} recebidos). Envia os arquivos ou diz 'cancela'.")
        return

    # ── Escolha de público salvo ──────────────────────────────────────────────
    if estado == "aguardando_cliente_publico":
        nome = texto.strip()
        resolucao = resolver_clientes([nome])
        if resolucao["nao_encontrados"]:
            send_text(destino, f"Não encontrei '{nome}'. Verifica o nome.")
            return
        if resolucao["ambiguos"]:
            amb = resolucao["ambiguos"][0]
            cand = amb["candidato"]
            _set_sessao(sender_jid, "aguardando_confirmacao_cliente_publico", {
                "cmd": payload["cmd"], "candidato": cand,
            })
            send_text(destino, f"Encontrei *{cand['nome']}*, é esse? (sim/não)")
            return
        cliente = resolucao["confirmados"][0]
        _listar_publicos_para_cliente(sender_jid, destino, cliente, payload["cmd"])
        return

    if estado == "aguardando_confirmacao_cliente_publico":
        if negativo:
            _limpar_sessao(sender_jid)
            send_text(destino, "❌ Cancelado, Patrão.")
            return
        if positivo:
            _listar_publicos_para_cliente(sender_jid, destino, payload["candidato"], payload["cmd"])
        else:
            send_text(destino, "Responde sim ou não, Patrão.")
        return

    if estado == "aguardando_escolha_publico":
        import re as _re_pub
        m = _re_pub.match(r'^(\d+)$', texto.strip())
        if not m:
            send_text(destino, "Responde com o número da opção, Patrão.")
            return
        idx = int(m.group(1)) - 1
        publicos = payload.get("publicos", [])
        if idx < 0 or idx >= len(publicos):
            send_text(destino, f"Número inválido. Escolhe entre 1 e {len(publicos)}.")
            return
        escolhido = publicos[idx]
        # Guardar escolha na sessão do lote pendente ou confirmar
        sessao_lote = payload.get("sessao_lote")
        if sessao_lote:
            # Atualiza o cmd da sessão de lote pendente com o público escolhido
            sessao_lote["cmd"]["publico_salvo_id_override"] = escolhido["id"]
            sessao_lote["cmd"]["publico_salvo_nome_override"] = escolhido["nome"]
            _limpar_sessao(sender_jid)
            send_text(destino, f"Público selecionado: *{escolhido['nome']}*\nAgora pode continuar com a subida.")
        else:
            _limpar_sessao(sender_jid)
            send_text(destino, f"Público *{escolhido['nome']}* selecionado (ID: {escolhido['id']}).\nUse esse ID ao subir o próximo anúncio para esse cliente.")
        return

    # ── Estados de coleta de dados (aceitam qualquer texto) ──────────────────
    if estado == "aguardando_cliente":
        nome = texto.strip()
        resolucao = resolver_clientes([nome])
        if resolucao["nao_encontrados"]:
            send_text(destino, f"Não encontrei '{nome}'. Tenta outro nome ou 'lista clientes'.")
            return
        if resolucao["ambiguos"]:
            amb = resolucao["ambiguos"][0]
            cand = amb["candidato"]
            payload["pendente_cliente"] = cand
            _set_sessao(sender_jid, "aguardando_confirmacao_cliente_guiado", payload)
            send_text(destino, f"Encontrei *{cand['nome']}*, é esse? (sim/não)")
            return
        cliente = resolucao["confirmados"][0]
        payload["clientes"] = [cliente]
        _limpar_sessao(sender_jid)
        _montar_confirmacao_final(sender_jid, destino, payload["cmd"], [cliente])
        return

    if estado == "aguardando_confirmacao_cliente_guiado":
        if negativo:
            _limpar_sessao(sender_jid)
            send_text(destino, "Cancelado. Me passa o nome certo do cliente.")
            return
        if positivo:
            cliente = payload.pop("pendente_cliente")
            payload["clientes"] = [cliente]
            _limpar_sessao(sender_jid)
            _montar_confirmacao_final(sender_jid, destino, payload["cmd"], [cliente])
        else:
            send_text(destino, "Responde sim ou não, Patrão.")
        return

    if estado == "aguardando_drive_link":
        link = texto.strip()
        _PALAVRAS_MIDIA = ["imagem", "foto", "vídeo", "video", "arquivo", "direto", "aqui", "mando", "manda"]
        quer_midia = any(p in link.lower() for p in _PALAVRAS_MIDIA) and "drive.google" not in link
        if quer_midia:
            _set_sessao(sender_jid, "aguardando_midia", payload)
            send_text(destino, "📸 Pode mandar! Envia a imagem ou vídeo direto aqui.")
            return
        if "drive.google" not in link:
            send_text(destino, "Não parece um link do Google Drive. Manda o link completo ou envia a imagem/vídeo direto aqui.")
            return
        payload["cmd"]["drive_link"] = link
        clientes = payload.get("clientes", [])
        _limpar_sessao(sender_jid)
        _montar_confirmacao_final(sender_jid, destino, payload["cmd"], clientes)
        return

    # ── Aguardando orçamento (aceita qualquer texto) ─────────────────────────
    if estado == "aguardando_orcamento":
        import re as _re_orc
        # Detectar formato "30, sendo 15 em cada conjunto" ou "15 por conjunto"
        _m_conj = _re_orc.search(r'(\d+(?:[,.]\d+)?)\s*(?:por|em\s+cada?)\s+conjunto', texto.lower())
        numeros = _re_orc.findall(r'\d+(?:[,.]\d+)?', texto)
        if not numeros:
            send_text(destino, "Não entendi o valor. Manda só o número, ex: 30")
            return
        orcamento = float(numeros[0].replace(",", "."))
        orcamento_por_conjunto = float(_m_conj.group(1).replace(",", ".")) if _m_conj else None
        payload["cmd"]["orcamento"] = orcamento
        if orcamento_por_conjunto:
            payload["cmd"]["orcamento_por_conjunto"] = orcamento_por_conjunto
        _limpar_sessao(sender_jid)
        _montar_confirmacao_final(sender_jid, destino, payload["cmd"], payload["clientes"])
        return

    if negativo:
        _limpar_sessao(sender_jid)
        send_text(destino, "❌ Cancelado, Patrão.")
        return

    if not positivo:
        send_text(destino, "Responde sim ou não, Patrão.")
        return

    # ── Confirmação de cliente ambíguo ────────────────────────────────────────
    if estado == "aguardando_confirmacao_clientes":
        idx       = payload["ambiguo_atual"]
        ambiguos  = payload["ambiguos"]
        amb       = ambiguos[idx]
        confirmados = payload["confirmados"] + [amb["candidato"]]
        idx += 1

        if idx < len(ambiguos):
            payload["confirmados"] = confirmados
            payload["ambiguo_atual"] = idx
            _set_sessao(sender_jid, "aguardando_confirmacao_clientes", payload)
            prox = ambiguos[idx]
            send_text(destino, f"E *{prox['candidato']['nome']}* para '{prox['digitado']}', é esse? (sim/não)")
        else:
            _limpar_sessao(sender_jid)
            _montar_confirmacao_final(sender_jid, destino, payload["cmd"], confirmados)
        return

    # ── Confirmação final de subida ───────────────────────────────────────────
    if estado == "aguardando_confirmacao_subida":
        _limpar_sessao(sender_jid)
        send_text(destino, "⏳ Subindo anúncios... aguarda, Patrão.")
        _set_sessao(sender_jid, "executando", {})

        def _executar():
            try:
                from bot.gestor_whatsapp import get_gestor
                gestor = get_gestor()
                cliente_ids = [c["id"] for c in payload["clientes"]]
                _est = payload.get("estrutura") or {}
                _drive = payload.get("drive_link") or None
                _arq_local = payload.get("arquivo_local") or None
                _arqs = payload.get("arquivos_locais") or None
                logger.info(f"_executar: drive={_drive!r} arquivo_local={_arq_local!r} arquivos_locais={_arqs!r}")
                if not _drive and not _arq_local and not _arqs:
                    send_text(destino, "❌ Erro interno: criativos não encontrados. Reinicia o fluxo e envia as imagens de novo, Patrão.")
                    return
                dados = gestor.subir_anuncio(
                    cliente_ids=cliente_ids,
                    drive_url=_drive,
                    orcamento=payload["orcamento"],
                    campanha_nome=payload["campanha_nome"],
                    campanha_tipo=payload["campanha_tipo"],
                    arquivo_local=_arq_local,
                    arquivos_locais=_arqs,
                    num_conjuntos=_est.get("conjuntos", 1),
                    cri_por_conjunto=_est.get("criativos", 1),
                    orcamento_por_conjunto=payload.get("orcamento_por_conjunto") or None,
                    copy=payload.get("copy") or {},
                    copies_list=payload.get("copies_list") or [],
                )
                mc_token = dados["mc_token"]
                eventos = gestor.consumir_stream(mc_token)
                resultado = _formatar_resultado_stream(eventos, len(payload["clientes"]))
                send_text(destino, resultado)
                # Salva contexto recente para "ativa ela" funcionar sem reperguntar cliente
                ok_eventos = [e for e in eventos if e.get("tipo") == "concluido" or e.get("status") == "ok"]
                if ok_eventos:
                    _ultimo_contexto[sender_jid] = {
                        "clientes": payload["clientes"],
                        "campanha_id": ok_eventos[0].get("campanha_id", ""),
                        "campanha_nome": payload.get("campanha_nome", ""),
                        "ts": _time.time(),
                    }
            except Exception as e:
                send_text(destino, f"Erro ao subir anúncios: {e}")
            finally:
                _limpar_sessao(sender_jid)

        import threading as _threading
        _threading.Thread(target=_executar, daemon=True).start()
        return

    # ── Confirmação de pausar/ativar ──────────────────────────────────────────
    if estado in ("aguardando_confirmacao_pausar", "aguardando_confirmacao_ativar"):
        acao = "pausar" if "pausar" in estado else "ativar"
        _limpar_sessao(sender_jid)
        campanhas = payload["campanhas"]
        send_text(destino, f"Executando... {len(campanhas)} campanha(s)")

        def _executar_status():
            try:
                from bot.gestor_whatsapp import get_gestor
                gestor = get_gestor()
                ok, erros = 0, 0
                for cp in campanhas:
                    try:
                        if acao == "pausar":
                            gestor.pausar_campanha(cp["id"], cp["_cliente"]["token_key"])
                        else:
                            gestor.ativar_campanha(cp["id"], cp["_cliente"]["token_key"])
                        ok += 1
                    except Exception:
                        erros += 1
                msg = f"{ok}/{len(campanhas)} campanhas {'pausadas' if acao == 'pausar' else 'ativadas'}"
                if erros:
                    msg += f" ({erros} com erro)"
                send_text(destino, msg)
            except Exception as e:
                send_text(destino, f"Erro: {e}")

        import threading as _threading2
        _threading2.Thread(target=_executar_status, daemon=True).start()
        return

    # ── Estado executando — aguardar ──────────────────────────────────────────
    if estado == "executando":
        send_text(destino, "Ainda processando o lote anterior, aguarda, Patrão...")
        return


# ── Handler de mídia ──────────────────────────────────────────────────────────

_MIME_EXT_MAP_WA = {
    "image/jpeg": ".jpg", "image/png": ".png", "video/mp4": ".mp4",
}

def processar_midia(sender_jid: str, msg_key: dict, message: dict, tipo_midia: str):
    """Processa imagem/vídeo recebido via WhatsApp — inicia fluxo guiado de subida."""
    import uuid as _uuid_m
    destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid

    # Se já tem lote em execução, recusar
    sessao = _get_sessao(sender_jid)
    if sessao and sessao.get("estado") == "executando":
        send_text(destino, "Ainda processando o lote anterior, aguarda, Patrão...")
        return

    # Baixar bytes do arquivo
    result = download_media_bytes(msg_key, message)
    if not result:
        send_text(destino, "Não consegui baixar o arquivo. Tenta enviar de novo, Patrão.")
        return

    media_bytes, mimetype = result
    mime_base = mimetype.split(";")[0].strip() if mimetype else ""
    ext = _MIME_EXT_MAP_WA.get(mime_base)
    if not ext:
        ext = ".jpg" if tipo_midia == "imageMessage" else ".mp4"

    # Salvar em /tmp
    tmp_path = f"/tmp/wa_media_{_uuid_m.uuid4()}{ext}"
    try:
        with open(tmp_path, "wb") as fh:
            fh.write(media_bytes)
    except Exception as e:
        logger.error(f"processar_midia: erro ao salvar tmp: {e}")
        send_text(destino, "Erro interno ao salvar arquivo. Tenta de novo, Patrão.")
        return

    # Se há sessão aguardando criativos — seção crítica atômica para evitar race condition
    with _sessoes_lock:
        _s = _sessoes.get(sender_jid)
        if _s and _s.get("estado") == "aguardando_criativos":
            _payload = _s["payload"]
            _arquivos = _payload["cmd"].get("arquivos_locais") or []
            _arquivos.append(tmp_path)
            _payload["cmd"]["arquivos_locais"] = _arquivos
            _est = (_payload["cmd"].get("estrutura") or {})
            _num = _est.get("conjuntos", 1) * _est.get("criativos", 1)
            _rec = len(_arquivos)
            if _rec >= _num:
                _clientes = _payload.get("clientes", [])
                _cmd = _payload["cmd"]
                _sessoes.pop(sender_jid, None)
                _acao = ("confirmar", _rec, _num, _cmd, _clientes)
            else:
                _s["expira_em"] = _time.time() + _TTL_SESSAO
                _acao = ("aguardar", _rec, _num, None, None)
        else:
            _acao = None

    if _acao:
        tipo, rec, num, cmd_, clientes_ = _acao
        if tipo == "confirmar":
            _montar_confirmacao_final(sender_jid, destino, cmd_, clientes_)
        # "aguardar" — sem mensagem por imagem para não flodar
        return

    # Se há sessão aguardando mídia (cliente já selecionado), continuar de onde parou
    if sessao and sessao.get("estado") == "aguardando_midia":
        payload = sessao["payload"]
        payload["cmd"]["arquivo_local"] = tmp_path
        payload["cmd"]["drive_link"] = None
        clientes = payload.get("clientes", [])
        _limpar_sessao(sender_jid)
        send_text(destino, "📸 Arquivo recebido!")
        _montar_confirmacao_final(sender_jid, destino, payload["cmd"], clientes)
        return

    # Iniciar fluxo guiado — pedir nome do cliente
    cmd = {
        "intencao":      "subir_anuncio",
        "drive_link":    None,
        "arquivo_local": tmp_path,
        "orcamento":     None,
        "campanha_tipo": "MESSAGES",
    }
    _set_sessao(sender_jid, "aguardando_cliente", {"cmd": cmd})
    send_text(destino, "Recebi o arquivo! Pra qual cliente você quer subir?")


# ── Handler de mensagem ────────────────────────────────────────────────────────

import re as _re_slash
_APROVACAO_RE = _re_slash.compile(r'^(ok|cancela\s+\d+)$', _re_slash.IGNORECASE)


def _processar_slash_cmd(sender_jid: str, texto: str) -> bool:
    """
    Processa slash-commands (/gestor, /saldo, etc.).
    Retorna True se processou, False se não era slash-command.
    """
    from bot.whatsapp_handlers import (
        cmd_saldo, cmd_historico, cmd_status_cliente, cmd_relatorio,
        _verificar_varredura_pendente, enviar_resumo_gestor,
    )
    destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid
    texto_limpo = texto.strip()

    if not texto_limpo.startswith("/"):
        return False

    partes = texto_limpo.split(None, 1)
    cmd = partes[0].lower()
    args = partes[1] if len(partes) > 1 else ""

    if cmd == "/saldo":
        cmd_saldo(destino)

    elif cmd == "/historico":
        cmd_historico(destino)

    elif cmd == "/relatorio":
        cmd_relatorio(destino)

    elif cmd == "/status":
        if args:
            cmd_status_cliente(destino, args)
        else:
            send_text(destino, "Uso: /status [nome do cliente]")

    elif cmd == "/gestor":
        estado = _verificar_varredura_pendente()
        if estado:
            send_text(destino, f"Ha acoes pendentes de aprovacao (varredura #{estado['varredura_id']}). Responda 'ok' ou 'cancela N' primeiro.")
        else:
            send_text(destino, "Iniciando varredura manual...")
            import threading
            def _run():
                try:
                    from meta.gestor_agente import main
                    main()
                except Exception as e:
                    logger.error(f"[/gestor] erro: {e}")
                    send_text(destino, f"Erro na varredura: {e}")
            threading.Thread(target=_run, daemon=True).start()

    elif cmd == "/pausa":
        if args:
            _processar_gestor_cmd(sender_jid, f"pausa {args}")
        else:
            send_text(destino, "Uso: /pausa [nome do cliente]")

    elif cmd == "/ativa":
        if args:
            _processar_gestor_cmd(sender_jid, f"ativa {args}")
        else:
            send_text(destino, "Uso: /ativa [nome do cliente]")

    else:
        send_text(destino, f"Comando '{cmd}' nao reconhecido. Disponiveis: /gestor /saldo /status /relatorio /pausa /ativa /historico")

    return True


def processar_mensagem(sender_jid: str, texto: str):
    """Processa mensagem do Bruno e envia resposta."""
    chat_id = jid_to_chat_id(sender_jid)
    historico = carregar_historico(chat_id)

    # 1. Slash-commands (ANTES de qualquer outra verificação)
    if _processar_slash_cmd(sender_jid, texto):
        return

    # 2. Aprovação do gestor (sem sessão ativa E padrão ok/cancela)
    if _APROVACAO_RE.match(texto.strip()):
        sessao_check = _get_sessao(sender_jid)
        if not sessao_check:
            from bot.whatsapp_handlers import _verificar_varredura_pendente, processar_aprovacao
            if _verificar_varredura_pendente():
                destino_ap = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid
                processar_aprovacao(texto.strip(), destino_ap)
                return

    # Verificar sessão ativa (confirmação pendente)
    sessao = _get_sessao(sender_jid)
    if sessao:
        _processar_confirmacao(sender_jid, texto, sessao)
        return

    # Detectar resposta órfã (sessão expirou por restart do serviço)
    import re as _re_orfao
    destino_orfao = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid
    _t = texto.strip()
    if _re_orfao.match(r'^\d+[x\-]\d+[x\-]\d+$', _t):
        send_text(destino_orfao, "⚠️ Minha sessão expirou, Patrão (o serviço reiniciou). Repete o comando do início — manda o criativo ou o link do Drive de novo.")
        return
    if _re_orfao.match(r'^\d+(?:[,\.]\d+)?$', _t) and float(_t.replace(',', '.')) < 10000:
        # Número solto — pode ser orçamento de sessão perdida; só avisa se não for óbvio contexto de conversa
        pass  # não interrompe para não bloquear usos legítimos

    # Intenção: comando de gestor
    if _eh_gestor_cmd(texto):
        _processar_gestor_cmd(sender_jid, texto)
        return

    # Intencao: enviar para grupo
    if _eh_grupo(texto):
        grupos = get_grupos()
        grupo_encontrado = None
        for g in grupos:
            if g["nome"].lower() in texto.lower():
                grupo_encontrado = g
                break

        if grupo_encontrado:
            ok = send_text(grupo_encontrado["jid"], grupo_encontrado["msg"])
            resposta = (
                f"Mensagem enviada para o grupo {grupo_encontrado['nome']}, Patrao!"
                if ok else
                f"Falha ao enviar para {grupo_encontrado['nome']}. Evolution API offline?"
            )
            destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid
            send_text(destino, resposta)
            salvar_mensagem(chat_id, "user", texto)
            salvar_mensagem(chat_id, "assistant", resposta)
            return

    # Intencao: financeiro ou clientes — injeta contexto no prompt
    prompt = PROMPT_ANALISTA
    mensagem_claude = texto
    contextos = []
    if _eh_financeiro(texto):
        ctx = financeiro_context()
        if ctx:
            contextos.append(f"DADOS FINANCEIROS DO SISTEMA:\n{ctx}")
    if _eh_sobre_clientes(texto):
        ctx = _context_clientes()
        if ctx:
            contextos.append(ctx)
    if contextos:
        mensagem_claude = "\n\n".join(contextos) + f"\n\nPERGUNTA DO PATRAO: {texto}"

    resposta = chamar_claude(prompt, mensagem_claude, historico)

    # Fallback para grupo via Claude
    if _eh_grupo(texto) and "nao esta configurado" not in resposta.lower():
        grupos = get_grupos()
        for g in grupos:
            if g["nome"].lower() in texto.lower():
                send_text(g["jid"], g["msg"])
                break
        else:
            resposta = "Patrao, esse grupo nao ta configurado ainda. Adiciona no config/wa_grupos.json."

    # Enviar primeiro, salvar depois (DB não pode bloquear a resposta)
    destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid
    send_text(destino, resposta)
    salvar_mensagem(chat_id, "user", texto)
    salvar_mensagem(chat_id, "assistant", resposta)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    # Verificar secret se configurado
    if WEBHOOK_SECRET:
        incoming = request.headers.get("x-webhook-secret", "")
        if incoming != WEBHOOK_SECRET:
            return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}

    # Apenas processar messages.upsert (v1.x) ou MESSAGES_UPSERT (v2.x)
    event = data.get("event", "")
    if event not in ("messages.upsert", "MESSAGES_UPSERT"):
        return jsonify({"ok": True})

    # v1.x: data pode ser lista ou dict
    raw_data = data.get("data", {})
    msg_data = raw_data[0] if isinstance(raw_data, list) else raw_data
    key = msg_data.get("key", {})

    # Ignorar mensagens enviadas pelo proprio bot
    if key.get("fromMe"):
        return jsonify({"ok": True})

    sender_jid = key.get("remoteJid", "")

    # Debug: logar JID recebido
    logger.info(f"Webhook recebido: sender_jid={sender_jid!r} authorized={AUTHORIZED_JID!r} fromMe={key.get('fromMe')}")

    # Apenas responder ao usuario autorizado
    if sender_jid != AUTHORIZED_JID:
        logger.info(f"JID nao autorizado, ignorando: {sender_jid!r}")
        return jsonify({"ok": True})

    message = msg_data.get("message", {})
    texto = (
        message.get("conversation")
        or message.get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()

    # Detectar mídia (imagem ou vídeo)
    _MIME_EXT_MAP = {
        "image/jpeg": ".jpg", "image/png": ".png",
        "video/mp4": ".mp4",
    }
    tipo_midia = None
    if message.get("imageMessage"):
        tipo_midia = "imageMessage"
    elif message.get("videoMessage"):
        tipo_midia = "videoMessage"

    if not texto and not tipo_midia:
        return jsonify({"ok": True})

    # Processar em background para nao bloquear o webhook
    import threading

    if tipo_midia:
        def _run_midia():
            try:
                processar_midia(sender_jid, msg_data.get("key", {}), message, tipo_midia)
            except Exception as e:
                logger.error(f"Erro em processar_midia: {e}", exc_info=True)
        threading.Thread(target=_run_midia, daemon=True).start()
    else:
        def _run():
            try:
                processar_mensagem(sender_jid, texto)
            except Exception as e:
                logger.error(f"Erro em processar_mensagem: {e}", exc_info=True)
        threading.Thread(target=_run, daemon=True).start()

    return jsonify({"ok": True})

@app.route("/health")
def health():
    return jsonify({"ok": True, "wa_status": verificar_conexao()})

# ── APScheduler — crons ───────────────────────────────────────────────────────

def _enviar_resumo_gestor():
    """Cron das 17h: envia resumo do Gestor IA para o Bruno."""
    if not AUTHORIZED_JID:
        logger.warning("WA_AUTHORIZED_JID nao configurado - resumo nao enviado")
        return
    logger.info("Enviando resumo diario do Gestor IA...")
    resumo = resumo_gestor()
    destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else AUTHORIZED_JID
    send_text(destino, resumo)

def _enviar_mensagem_grupo(grupo: dict):
    """Cron agendado: envia mensagem para um grupo configurado."""
    logger.info(f"Enviando mensagem agendada para grupo {grupo['nome']}")
    send_text(grupo["jid"], grupo["msg"])

def _limpar_tmp_midia():
    """Remove arquivos wa_media_* do /tmp com mais de 1 hora."""
    import glob as _glob_tmp
    agora = _time.time()
    removidos = 0
    for f in _glob_tmp.glob("/tmp/wa_media_*"):
        try:
            if agora - os.path.getmtime(f) > 3600:
                os.remove(f)
                removidos += 1
        except Exception:
            pass
    if removidos:
        logger.info(f"_limpar_tmp_midia: {removidos} arquivo(s) removido(s)")


def _expirar_pendentes():
    """Expira ações pendentes com mais de 4h sem aprovação."""
    try:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"],
                                cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute("""
            UPDATE gestor_acoes
            SET status='expirado', expirado_em=NOW()
            WHERE status='pendente'
              AND executado_em < NOW() - INTERVAL '4 hours'
        """)
        n_acoes = cur.rowcount
        cur.execute("""
            UPDATE gestor_estado
            SET status='expirado', resolvido_em=NOW()
            WHERE status='aguardando'
              AND criado_em < NOW() - INTERVAL '4 hours'
        """)
        n_estados = cur.rowcount
        conn.commit()
        conn.close()
        if n_acoes or n_estados:
            logger.info(f"_expirar_pendentes: {n_acoes} acoes e {n_estados} estados expirados")
    except Exception as e:
        logger.error(f"_expirar_pendentes error: {e}")


def _configurar_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=SP_TZ)

    # Limpeza de arquivos temporários de mídia a cada hora
    scheduler.add_job(
        _limpar_tmp_midia,
        "interval", hours=1,
        id="limpar_tmp_midia",
        replace_existing=True,
    )

    # Expirar pendentes a cada 30min
    scheduler.add_job(
        _expirar_pendentes,
        "interval", minutes=30,
        id="expirar_pendentes",
        replace_existing=True,
    )

    # Mensagens agendadas para grupos
    grupos = get_grupos()
    DIAS_MAP = {
        "mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu",
        "fri": "fri", "sat": "sat", "sun": "sun",
    }
    for i, grupo in enumerate(grupos):
        cron_time = grupo.get("cron", "")
        dias = grupo.get("dias", [])
        if not cron_time or not dias:
            continue
        try:
            hora, minuto = cron_time.split(":")
            dia_semana = ",".join(DIAS_MAP.get(d, d) for d in dias)
            scheduler.add_job(
                _enviar_mensagem_grupo,
                CronTrigger(day_of_week=dia_semana, hour=int(hora), minute=int(minuto), timezone=SP_TZ),
                args=[grupo],
                id=f"grupo_{i}_{grupo['nome']}",
                replace_existing=True,
            )
            logger.info(f"Agendado: grupo '{grupo['nome']}' as {cron_time} nos dias {dias}")
        except Exception as e:
            logger.error(f"Erro ao agendar grupo {grupo.get('nome')}: {e}")

    return scheduler

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY nao configurada - encerrando")
        sys.exit(1)

    # Verificar conexao WhatsApp
    estado = verificar_conexao()
    if estado == "open":
        logger.info("WhatsApp conectado")
    elif estado == "close":
        logger.warning("WhatsApp desconectado. Reconecte via QR em http://localhost:8081")
    else:
        logger.warning(f"WhatsApp status: {estado} (Evolution API pode estar inicializando)")

    # Iniciar scheduler
    scheduler = _configurar_scheduler()
    scheduler.start()
    logger.info(f"APScheduler iniciado com {len(scheduler.get_jobs())} job(s)")

    # Iniciar Flask
    logger.info("Jake WhatsApp iniciando na porta 5052...")
    app.run(host="0.0.0.0", port=5052, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
