#!/usr/bin/env python3
"""
Jake OS – Plataforma SaaS completa.
Acesse via: http://localhost:5050
"""

import os
import io
import json
import base64
import uuid
import webbrowser
import threading
import time
import secrets as _secrets
from datetime import datetime
from zoneinfo import ZoneInfo
from functools import wraps

from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_from_directory

import requests
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

# Carrega .env do projeto ou do diretório pai (ex.: /root/.env)
_basedir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_basedir, ".env"))
load_dotenv(os.path.join(os.path.dirname(_basedir), ".env"))

from openai import OpenAI
import anthropic as _anthropic

import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import meta.meta_api as _meta_api
import brain

_VALID_TOKEN_KEYS = {"META_TOKEN_PILOTI", "META_TOKEN_DENTTO", "META_ACCESS_TOKEN"}


def _get_db():
    """Abre conexão com Neon usando DATABASE_URL do .env."""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido no .env")
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _init_rotina_tables():
    """Cria as tabelas do módulo Rotina se não existirem."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                icon TEXT DEFAULT '✓',
                active BOOLEAN DEFAULT TRUE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id SERIAL PRIMARY KEY,
                habit_id INTEGER REFERENCES habits(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                completed BOOLEAN DEFAULT FALSE,
                notes TEXT,
                UNIQUE(habit_id, date)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS maconha_log (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                used BOOLEAN DEFAULT TRUE,
                period TEXT CHECK(period IN ('dia','noite')),
                UNIQUE(date, period)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS streaks (
                habit_id INTEGER PRIMARY KEY REFERENCES habits(id) ON DELETE CASCADE,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_updated DATE
            )
        """)
        conn.commit()
        _seed_habits(cur, conn)
    finally:
        conn.close()


def _seed_habits(cur, conn):
    """Popula hábitos iniciais se a tabela estiver vazia."""
    cur.execute("SELECT COUNT(*) as c FROM habits")
    if cur.fetchone()["c"] > 0:
        return
    habits = [
        ("Luz natural ao acordar", "MANHÃ", "☀️"),
        ("500ml água ao acordar", "MANHÃ", "💧"),
        ("Passeio com Odin (manhã)", "MANHÃ", "🐕"),
        ("Café da manhã com proteína", "MANHÃ", "🥚"),
        ("Pausa ativa 10h (sem tela)", "TRABALHO", "🧘"),
        ("Almoço sem tela", "TRABALHO", "🍽️"),
        ("Pausa ativa 15h", "TRABALHO", "🧘"),
        ("Encerrei expediente no horário", "TRABALHO", "✅"),
        ("Treinei (academia/bike/caminhada)", "TARDE/NOITE", "🏋️"),
        ("Jantar leve", "TARDE/NOITE", "🥗"),
        ("30 min fora de tela", "TARDE/NOITE", "🎨"),
        ("Tela OFF às 21h30", "TARDE/NOITE", "📵"),
        ("Dormi no horário", "TARDE/NOITE", "😴"),
        ("Meal prep feito", "SEMANA", "🍳"),
        ("Reserva financeira transferida", "SEMANA", "💰"),
        ("Gastos registrados no app", "SEMANA", "📊"),
    ]
    for name, category, icon in habits:
        cur.execute(
            "INSERT INTO habits (name, category, icon) VALUES (%s, %s, %s)",
            (name, category, icon)
        )
    conn.commit()


def _init_social_brief_tables():
    """Cria tabelas do módulo Social Brief se não existirem."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_brief_clientes (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(200) NOT NULL,
                slug VARCHAR(100) UNIQUE NOT NULL,
                nicho VARCHAR(100),
                meta_account_id VARCHAR(100),
                meta_agency VARCHAR(50) DEFAULT 'piloti',
                concorrentes TEXT[] DEFAULT '{}',
                tipos_campanha JSONB DEFAULT '{}',
                ativo BOOLEAN DEFAULT TRUE,
                criado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_brief_geracoes (
                id SERIAL PRIMARY KEY,
                semana_inicio DATE NOT NULL,
                semana_fim DATE NOT NULL,
                html_completo TEXT,
                surge_url VARCHAR(300),
                publicado BOOLEAN DEFAULT FALSE,
                clientes_incluidos JSONB DEFAULT '[]',
                criado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_brief_cliente_dados (
                id SERIAL PRIMARY KEY,
                geracao_id INTEGER REFERENCES social_brief_geracoes(id) ON DELETE CASCADE,
                cliente_id INTEGER REFERENCES social_brief_clientes(id) ON DELETE CASCADE,
                analise_json JSONB,
                dados_meta JSONB,
                criado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _init_nutricao_tables():
    """Cria tabelas de nutrição se não existirem e insere dados iniciais."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nutricao_perfis (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                sexo VARCHAR(1) DEFAULT 'M',
                idade INTEGER,
                peso DECIMAL(5,2),
                altura INTEGER,
                objetivo VARCHAR(50) DEFAULT 'hipertrofia',
                nivel_atividade VARCHAR(50) DEFAULT 'intenso',
                restricoes TEXT[],
                preferencias TEXT,
                aversoes TEXT,
                tmb DECIMAL(8,2),
                get DECIMAL(8,2),
                meta_calorica INTEGER,
                meta_proteina INTEGER,
                meta_carbo INTEGER,
                meta_gordura INTEGER,
                atualizado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nutricao_cardapios (
                id SERIAL PRIMARY KEY,
                semana_inicio DATE NOT NULL,
                semana_fim DATE NOT NULL,
                status VARCHAR(20) DEFAULT 'rascunho',
                cardapio_json JSONB,
                lista_compras_json JSONB,
                criado_em TIMESTAMP DEFAULT NOW(),
                aprovado_em TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nutricao_alimentos_base (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(200) NOT NULL,
                categoria VARCHAR(50),
                congelavel BOOLEAN DEFAULT FALSE,
                favorito BOOLEAN DEFAULT FALSE,
                notas TEXT
            )
        """)
        conn.commit()
        # Perfis iniciais — só insere se tabela vazia
        cur.execute("SELECT COUNT(*) as c FROM nutricao_perfis")
        if cur.fetchone()["c"] == 0:
            cur.execute("""
                INSERT INTO nutricao_perfis (nome, sexo, objetivo, nivel_atividade)
                VALUES ('Bruno', 'M', 'hipertrofia', 'intenso'),
                       ('Camila', 'F', 'hipertrofia', 'intenso')
            """)
            conn.commit()
        # Alimentos base — só insere se tabela vazia
        cur.execute("SELECT COUNT(*) as c FROM nutricao_alimentos_base")
        if cur.fetchone()["c"] == 0:
            alimentos = [
                ('Carne moída', 'proteina', True, True),
                ('Lombo suíno', 'proteina', True, True),
                ('Filé de frango', 'proteina', True, True),
                ('Macarrão', 'carbo', False, True),
                ('Purê de batata', 'carbo', True, True),
                ('Torta de frango', 'lanche', True, True),
                ('Pão de forma', 'lanche', False, True),
                ('Banana', 'fruta', False, True),
                ('Granola', 'lanche', False, True),
                ('Aveia', 'lanche', False, True),
                ('Mel', 'lanche', False, True),
                ('Requeijão', 'lanche', False, True),
                ('Queijo', 'lanche', False, True),
                ('Ovo', 'proteina', False, True),
                ('Bolo de açúcar mascavo', 'lanche', True, True),
                ('Nozes', 'lanche', False, True),
                ('Castanha', 'lanche', False, True),
            ]
            for nome, cat, cong, fav in alimentos:
                cur.execute("""
                    INSERT INTO nutricao_alimentos_base (nome, categoria, congelavel, favorito)
                    VALUES (%s, %s, %s, %s)
                """, (nome, cat, cong, fav))
            conn.commit()
    finally:
        conn.close()


def _init_dr_tables():
    """Cria tabela dr_ofertas se não existir."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dr_ofertas (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(200) NOT NULL,
                nicho VARCHAR(200),
                angulo TEXT,
                hook TEXT,
                promessa TEXT,
                publico TEXT,
                contexto_raw TEXT,
                tipo_funil VARCHAR(50),
                copy_json JSONB,
                script_vsl TEXT,
                angulos_json JSONB,
                lp_html TEXT,
                lp_url VARCHAR(500),
                quiz_html TEXT,
                quiz_url VARCHAR(500),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _init_aportes_table():
    """Cria tabela de aportes de investimento se não existir."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS aportes_investimento (
                id SERIAL PRIMARY KEY,
                mes_ano DATE NOT NULL,
                ativo VARCHAR(50) NOT NULL,
                valor NUMERIC(12,2) NOT NULL CHECK (valor > 0),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_aportes_mes_ano
            ON aportes_investimento(mes_ano)
        """)
        conn.commit()
    finally:
        conn.close()


def _init_ativos_personalizados_table():
    """Cria tabela de ativos personalizados se não existir."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ativos_personalizados (
                id SERIAL PRIMARY KEY,
                key VARCHAR(50) UNIQUE NOT NULL,
                label VARCHAR(100) NOT NULL,
                cor VARCHAR(20) NOT NULL,
                meta NUMERIC(5,2) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    finally:
        conn.close()


# ── NUTRIÇÃO: Cálculos ────────────────────────────────────────────────────────

def _calcular_imc(peso, altura):
    """Retorna IMC arredondado para 1 casa."""
    if not peso or not altura:
        return 0
    return round(float(peso) / ((float(altura) / 100) ** 2), 1)

def _calcular_tmb(sexo, peso, altura, idade):
    """Fórmula Mifflin-St Jeor."""
    if not all([peso, altura, idade]):
        return 0
    base = (10 * float(peso)) + (6.25 * float(altura)) - (5 * int(idade))
    return base + 5 if str(sexo or '').upper() == 'M' else base - 161

def _calcular_get(tmb, nivel_atividade):
    fatores = {'sedentario': 1.2, 'moderado': 1.55, 'intenso': 1.725}
    return float(tmb) * fatores.get(nivel_atividade, 1.55)

def _calcular_macros(objetivo, get, peso):
    """Retorna dict com calorias, proteina, carbo, gordura."""
    if objetivo == 'hipertrofia':
        meta_cal = get + 400
        proteina = float(peso) * 2.0
    elif objetivo == 'emagrecimento':
        meta_cal = get - 400
        proteina = float(peso) * 2.2
    else:  # manutencao
        meta_cal = get
        proteina = float(peso) * 1.8
    gordura = (meta_cal * 0.25) / 9
    carbo = (meta_cal - (proteina * 4) - (gordura * 9)) / 4
    return {
        'calorias': int(meta_cal),
        'proteina': int(proteina),
        'carbo': int(max(carbo, 0)),
        'gordura': int(gordura),
    }


app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SESSION_SECRET") or _secrets.token_hex(32)

# ── Credenciais de acesso ────────────────────────────────────────────────────
_ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL",    "admin@jakeos.local")
_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Jake@2024!")

# ── Auth helper ──────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# ── Rotas públicas ───────────────────────────────────────────────────────────
@app.route("/privacidade")
def privacidade():
    return send_from_directory("static", "privacidade-bruno-zati.html")

# ── Rotas de autenticação ────────────────────────────────────────────────────
@app.route("/login")
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    error = request.args.get("error")
    return render_template("login.html", error=error)

@app.route("/auth/login", methods=["POST"])
def auth_login():
    email    = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    if (email == _ADMIN_EMAIL.strip().lower()
            and _secrets.compare_digest(password, _ADMIN_PASSWORD)):
        session["logged_in"]   = True
        session["user_email"]  = email
        return redirect(url_for("index"))
    return redirect(url_for("login_page") + "?error=1")

@app.route("/auth/logout")
def auth_logout():
    session.clear()
    return redirect(url_for("login_page"))

# ── Painel principal (SPA) ───────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("dashboard.html", user_email=session.get("user_email", ""))

# ── API: hora e data ─────────────────────────────────────────────────────────
_WEEKDAY_PT = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")

@app.route("/api/now")
@login_required
def api_now():
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    wd  = now.weekday()
    return jsonify({
        "time":    now.strftime("%H:%M"),
        "date":    now.strftime("%d/%m/%Y"),
        "weekday": _WEEKDAY_PT[wd],
    })

# ── API: temperatura ─────────────────────────────────────────────────────────
@app.route("/api/weather")
@login_required
def api_weather():
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=-23.55&longitude=-46.63"
            "&current=temperature_2m,relative_humidity_2m"
            "&timezone=America/Sao_Paulo",
            timeout=3,
        )
        if r.ok:
            cur = r.json().get("current", {})
            return jsonify({
                "temp":     round(cur.get("temperature_2m", 0), 1),
                "unit":     "°C",
                "humidity": cur.get("relative_humidity_2m"),
            })
    except Exception:
        pass
    return jsonify({"temp": None, "unit": "°C", "humidity": None})

# ── OpenAI helpers ───────────────────────────────────────────────────────────
def _openai_client():
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    return OpenAI(api_key=key) if key else None

def _send_telegram(text):
    token   = os.environ.get("TELEGRAM_BOT_TOKEN",    "").strip()
    chat_id = (os.environ.get("TELEGRAM_ALERT_CHAT_ID", "").strip()
               or os.environ.get("AUTHORIZED_ID", "").strip())
    if not token or not chat_id:
        return False, "Telegram não configurado"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        return r.ok, "Enviado" if r.ok else r.text
    except Exception as e:
        return False, str(e)

TELEGRAM_TOOL = {
    "type": "function",
    "function": {
        "name": "send_telegram_message",
        "description": "Envia uma mensagem para o Telegram do usuário.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Texto a enviar"}
            },
            "required": ["message"],
        },
    },
}

SYSTEM_PROMPT = (
    "Você é o Jake, um assistente de IA no estilo Jarvis da Stark Industries. "
    "REGRA: Responda SEMPRE apenas em português brasileiro, de forma clara e objetiva. "
    "Quando o usuário pedir para mandar algo no Telegram, use a ferramenta send_telegram_message."
)

def _chat_with_tools(client, messages):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=[TELEGRAM_TOOL],
        tool_choice="auto",
    )
    msg = response.choices[0].message
    if getattr(msg, "tool_calls", None):
        for tc in msg.tool_calls:
            if getattr(tc.function, "name", "") == "send_telegram_message":
                args = json.loads(getattr(tc.function, "arguments", "{}") or "{}")
                ok, detail = _send_telegram(args.get("message", ""))
                messages.append(msg)
                messages.append({
                    "role":         "tool",
                    "tool_call_id": getattr(tc, "id", ""),
                    "content":      "Enviado no Telegram." if ok else f"Falha: {detail}",
                })
                return _chat_with_tools(client, messages)
    return msg.content or ""

# ── API: falar com o Jake ────────────────────────────────────────────────────
@app.route("/api/falar", methods=["POST"])
@login_required
def api_falar():
    client = _openai_client()
    if not client:
        return jsonify({"error": "OPENAI_API_KEY não configurada"}), 500

    # Aceita texto direto (mais rápido, sem Whisper) ou arquivo de áudio
    user_text = None
    if request.is_json:
        user_text = ((request.get_json() or {}).get("text") or "").strip()

    if not user_text:
        audio_file = request.files.get("audio")
        if audio_file and audio_file.filename:
            try:
                audio_bytes = audio_file.read()
                if not audio_bytes:
                    return jsonify({"error": "Áudio vazio"}), 400
                file_like      = io.BytesIO(audio_bytes)
                file_like.name = audio_file.filename or "audio.webm"
                transcript     = client.audio.transcriptions.create(
                    model="whisper-1", file=file_like, language="pt"
                )
                user_text = (transcript.text or "").strip()
            except Exception as e:
                return jsonify({"error": f"Transcrição: {e}"}), 500

    if not user_text:
        return jsonify({"error": "Envie 'text' (JSON) ou arquivo 'audio'"}), 400

    try:
        messages      = [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user",   "content": user_text}]
        response_text = _chat_with_tools(client, messages).strip()
        if not response_text:
            return jsonify({"error": "Resposta vazia"}), 500

        tts = client.audio.speech.create(model="tts-1", voice="onyx", input=response_text)
        audio_out = (getattr(tts, "content", None)
                     or (b"".join(tts.iter_bytes()) if hasattr(tts, "iter_bytes") else b""))
        return jsonify({
            "text":        response_text,
            "audio":       base64.b64encode(audio_out).decode() if audio_out else "",
            "transcribed": user_text,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── API: Gerador de Carrossel (Claude claude-sonnet-4-5) ───────────────────────────
_CAROUSEL_SYSTEM = """\
Você é um Estrategista de Conteúdo Sênior especializado em carrosséis educativos de alto valor para Instagram.

FILOSOFIA:
Você cria conteúdo que ensina algo genuinamente útil. O leitor deve terminar o carrossel sabendo fazer \
ou entender algo que não sabia antes. Autoridade se constrói pelo mérito do conteúdo, não por hype.

REGRAS DE OURO:
1. Cada slide desenvolve UMA ideia central com profundidade — sem superficialidade.
2. Use dados reais, exemplos concretos, números, estudos ou casos sempre que possível.
3. Evite absolutamente: clichês motivacionais, frases de efeito vazias, "você sabia que...", promessas infladas.
4. A narrativa deve ser progressiva: cada slide avança o entendimento, nunca repete.
5. Prefira verbos de ação e linguagem direta. Português do Brasil natural, sem rebuscamento.
6. Zero emojis.

ESTRUTURA DOS 7 SLIDES:
- Slide 1 | GANCHO: Abre com uma afirmação contraintuitiva, dado surpreendente ou insight que quebra uma crença comum. \
Deve criar tensão cognitiva imediata — o leitor para de rolar porque precisa saber mais.
- Slides 2-3 | PROBLEMA: Diagnóstico profundo. Mostre as causas raiz (não os sintomas). \
Por que o problema persiste? Qual o custo real de ignorá-lo? O leitor deve pensar "é exatamente isso que acontece."
- Slides 4-5 | MÉTODO/FRAMEWORK: Entregue o método, framework ou critério de forma acionável e estruturada. \
Nomeie os princípios. Dê exemplos práticos de como aplicar. Seja específico ao ponto de o leitor conseguir \
implementar sem precisar de mais nada.
- Slide 6 | RESULTADO/VALOR: Mostre o resultado concreto de quem aplica o método. \
Use antes/depois, métricas reais ou transformação mensurável. Torne o ganho tangível.
- Slide 7 | CTA: Um próximo passo imediato, concreto e de baixa fricção que o leitor pode fazer HOJE. \
Não prometa milagres. Ofereça a ação lógica mais próxima.

FORMATO DE SAÍDA:
Retorne SOMENTE JSON válido, sem texto antes ou depois:
{"slides":[{"headline":"...","subheadline":"...","tag":"..."}]}
Exatamente 7 itens. Headline: máx 100 caracteres. Subheadline: 90-200 caracteres com conteúdo rico e específico.\
"""

_CAROUSEL_TONE = {
    "agressivo":    "Tom: direto, urgente, sem rodeios. Contraste forte entre dor e ganho. CTA incisivo e imperativo.",
    "elegante":     "Tom: premium, sofisticado e confiante. Vocabulário refinado sem ser pedante. Autoridade pela precisão.",
    "educacional":  "Tom: didático, claro e estruturado. Priorize explicações passo a passo, analogias e exemplos práticos.",
    "storytelling": "Tom: narrativa com começo, tensão e resolução. Use casos, jornada do personagem ou antes/depois para engajar.",
}

_CAROUSEL_AWARENESS = {
    "frio":     "Público FRIO: a pessoa não sabe que tem o problema ou não te conhece. Gancho por curiosidade, dado surpreendente ou problema latente. Zero venda direta no início.",
    "problema": "Público reconhece o PROBLEMA: já sente a dor. Reforce o diagnóstico e o custo de não agir.",
    "solucao":  "Público busca SOLUÇÃO: está comparando caminhos. Diferencie pelo método e pela clareza.",
    "produto":  "Público em fase PRODUTO: compara ofertas. Reforce prova social, resultado e critério de escolha.",
    "oferta":   "Público consciente da OFERTA: pronto para decidir. Remova objeções, destaque urgência/escassez e facilite a ação.",
}

_CAROUSEL_COMPLEXITY = {
    "simples":  "NÍVEL DE LINGUAGEM: Muito simples. Frases curtas. Palavras do dia a dia. Como se estivesse explicando pra alguém sem formação técnica. Sem jargões, sem palavras difíceis. Se usar um conceito, explique com uma analogia concreta.",
    "medio":    "NÍVEL DE LINGUAGEM: Equilibrado. Direto, claro, sem ser básico demais nem técnico demais.",
    "avancado": "NÍVEL DE LINGUAGEM: Avançado. Público que já domina o assunto. Use termos técnicos, conceitos elaborados, referências de mercado, nuances. Profundidade máxima.",
}

_CAROUSEL_TRIGGER = {
    "prova":       "Gatilho principal: PROVA SOCIAL — números, depoimentos, resultados de quem aplicou.",
    "urgencia":    "Gatilho principal: URGÊNCIA — prazo real, decisão agora ou perde.",
    "autoridade":  "Gatilho principal: AUTORIDADE — credenciais, anos de experiência, cases, certificações.",
    "pertenca":    "Gatilho principal: PERTENCIMENTO — quem já está do outro lado, tribo, exclusividade.",
    "curiosidade": "Gatilho principal: CURIOSIDADE — revelar algo inesperado, tensão cognitiva que o leitor precisa resolver.",
}

def _carousel_fallback(theme, tone):
    suffix = {"agressivo": "Quem age sem método perde para quem age com estratégia.", "elegante": "A diferença está nos critérios, não no esforço.", "educacional": "Entender a causa raiz é o primeiro passo para resolver de forma duradoura."}.get(tone, "")
    return [
        {"headline": f"{theme}: o que separa os 5% que dominam dos 95% que tentam", "subheadline": f"Não é talento nem sorte. É um conjunto de decisões que a maioria nunca aprende a tomar. {suffix}", "tag": "GANCHO"},
        {"headline": "O erro está no diagnóstico, não na execução", "subheadline": "A maioria tenta resolver o sintoma enquanto a causa raiz segue intacta. Resultado: ciclo de tentativas sem evolução real.", "tag": "PROBLEMA"},
        {"headline": "Sem critério claro, qualquer caminho parece certo", "subheadline": "A ausência de um framework de decisão transforma esforço em ruído. Trabalho duro sem direção correta não gera resultado, gera esgotamento.", "tag": "PROBLEMA"},
        {"headline": "O framework em 3 camadas que muda o resultado", "subheadline": "1. Defina o problema real (não o aparente). 2. Identifique a alavanca de maior impacto. 3. Execute em ciclos curtos com medição constante.", "tag": "MÉTODO"},
        {"headline": "A alavanca que 9 em cada 10 ignoram", "subheadline": "Concentrar 80% da energia nos 20% de ações que geram resultado é teoria conhecida — mas aplicar exige rejeitar o que parece urgente mas não é importante.", "tag": "FRAMEWORK"},
        {"headline": "Quem aplica esse método muda o resultado em 30 dias", "subheadline": "Não porque é mágico, mas porque elimina o desperdício de energia em ações de baixo retorno. Foco gera velocidade, velocidade gera resultados mensuráveis.", "tag": "VALOR"},
        {"headline": "Seu próximo passo concreto começa aqui", "subheadline": f"Escolha UMA área onde você quer aplicar esse framework em {theme}. Defina o problema real, a alavanca e o ciclo de medição. Comece esta semana.", "tag": "CTA"},
    ]

def _anthropic_client():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return _anthropic.Anthropic(api_key=key) if key else None

@app.route("/api/carousel/copy", methods=["POST"])
@login_required
def api_carousel_copy():
    data  = request.get_json() or {}
    theme = (data.get("theme") or "").strip()
    tone  = data.get("tone", "elegante")
    awareness  = data.get("awareness") or "problema"
    trigger    = data.get("trigger") or "prova"
    num_slides   = max(3, min(10, int(data.get("num_slides") or 7)))
    complexidade = data.get("complexidade") or "medio"
    if len(theme) < 3:
        return jsonify({"error": "Tema muito curto (mínimo 3 caracteres)."}), 400
    tone_hint = _CAROUSEL_TONE.get(tone, _CAROUSEL_TONE["elegante"])
    awareness_hint = _CAROUSEL_AWARENESS.get(awareness, _CAROUSEL_AWARENESS["problema"])
    trigger_hint   = _CAROUSEL_TRIGGER.get(trigger, _CAROUSEL_TRIGGER["prova"])

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    try:
        ctx = brain.contexto(theme)
        system_prompt = _CAROUSEL_SYSTEM
        if ctx:
            system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": "\n".join([
                    f"Tema: {theme}",
                    f"Tom solicitado: {tone}. {tone_hint}",
                    f"Nível de consciência do público: {awareness_hint}",
                    f"Gatilho mental a priorizar: {trigger_hint}",
                    _CAROUSEL_COMPLEXITY.get(complexidade, _CAROUSEL_COMPLEXITY["medio"]),
                    f"Gere exatamente {num_slides} slides com profundidade real de conteúdo.",
                    "Cada subheadline deve ensinar algo específico, com dados ou exemplos concretos.",
                    f"Retorne SOMENTE o JSON: {{\"slides\":[...{num_slides} itens...]}}",
                ]),
            }],
        )
        raw = (msg.content[0].text or "").strip()
        # Extrai o JSON caso venha com texto extra
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("JSON não encontrado na resposta")
        parsed = json.loads(raw[start:end])
        slides = parsed.get("slides", [])
        if len(slides) != num_slides:
            raise ValueError(f"Esperava {num_slides} slides, recebi {len(slides)}")
        slides_texto = "\n\n".join(
            f"**Slide {i+1}:** {str(s)}" for i, s in enumerate(slides)
        )
        brain.salvar(
            modulo="Carrossel",
            titulo=f"Carrossel {theme}",
            inputs={
                "tema": theme,
                "tom": tone,
                "nivel_consciencia": awareness,
                "gatilho": trigger,
            },
            output=slides_texto,
            model="claude-sonnet-4-5",
            cliente=theme,
        )
        return jsonify({"slides": slides, "theme": theme, "tone": tone})
    except Exception as exc:
        return jsonify({"error": str(exc), "slides": _carousel_fallback(theme, tone)}), 500

# ── API: Máquina de Copys ────────────────────────────────────────────────────
_COPYS_SYSTEM = """\
Você é um Copywriter de Alta Conversão, especializado em anúncios pagos para gestores de tráfego brasileiros.
Seu trabalho é criar textos persuasivos e prontos para veicular em anúncios digitais.

REGRAS ABSOLUTAS:
1. Entregue SOMENTE o texto do anúncio — sem introduções, sem explicações, sem comentários sobre a copy.
2. Use português brasileiro natural, direto e impactante.
3. Respeite rigorosamente o framework, a plataforma, o tom e TODAS as variáveis fornecidas.
4. Adapte o formato à plataforma: Meta Ads aceita textos longos; Google Ads exige títulos curtos (30 chars); TikTok/YouTube focam nos primeiros 3 segundos.
5. Para Roteiro de Vídeo: use tópicos numerados com indicação de cena/visual entre colchetes.
6. O CTA informado deve aparecer EXATAMENTE na última linha, sem nenhuma alteração.

NÍVEL DE CONSCIÊNCIA — muda radicalmente o ângulo de entrada:
- Público Frio (Topo): a pessoa não sabe que tem o problema ou não te conhece. Gancho baseado em curiosidade, dado surpreendente ou problema latente. Zero empurrão de venda direta.
- Público Morno (Meio): sabe que tem o problema, está comparando soluções. Diferencie, apresente autoridade e valide com provas sociais ou resultados.
- Público Quente (Fundo): pronto para comprar, só precisa de um empurrão. Remova objeções, destaque urgência/escassez e facilite a decisão.

GATILHO MENTAL — deve ser o fio condutor do texto inteiro, não apenas uma menção:
- Urgência: prazo real se esgotando, decisão agora ou perde.
- Escassez: vagas/unidades limitadas, exclusividade.
- Prova Social: números, depoimentos, resultados de outros clientes.
- Autoridade: credenciais, anos de experiência, cases, certificações do especialista.
- Curiosidade: revelar algo inesperado, criar tensão cognitiva que o leitor precisa resolver.

TAMANHO — regra inviolável:
- Curta (Stories/Reels): 1 gancho + 1 benefício + CTA. Máximo 3 frases. Copy leve, ritmo acelerado.
- Média (Feed Meta): 3-4 parágrafos com gancho, desenvolvimento, prova e CTA. Tom conversacional.
- Longa (Texto Persuasivo): copy completa com gancho forte, identificação com a dor, apresentação da solução, provas, quebra de objeção e CTA poderoso. 600-1200 caracteres.

EMOJIS:
- Sim: use emojis estrategicamente para destacar benefícios e criar ritmo visual. Não exagere.
- Não: zero emojis. Texto limpo, sem nenhum caractere especial decorativo.

FRAMEWORKS — COMO APLICAR:
- AIDA: Bloco de Atenção → Interesse (contexto/dados) → Desejo (benefício emocional) → Ação (CTA direto).
- PAS: Nomear a dor sem rodeios → Agitar (consequências de ignorar) → Solução com o produto.
- Storytelling Rápido: micro-história em 3 atos (situação → virada → resultado) + CTA.
- Oferta Direta / Varejo: preço / desconto em destaque → benefício principal → urgência + CTA.
- Quebra de Objeção: validar a dúvida do remarketing → rebater com prova/garantia → CTA urgente.
- Roteiro de Vídeo: gancho visual nos 3s → desenvolvimento em tópicos falados → CTA final.
"""

_COPYS_PLATFORM_HINTS = {
    "Meta Ads (Facebook/Instagram)": (
        "Formato Meta Ads: separe o texto em 3 partes com os rótulos exatos: "
        "[TEXTO PRINCIPAL] (copy principal, pode ser longa), "
        "[TÍTULO] (máx 40 chars, impacto imediato), "
        "[DESCRIÇÃO] (máx 30 chars, complemento do título)."
    ),
    "Google Ads (Rede de Pesquisa)": (
        "Formato Google Ads: gere exatamente com os rótulos: "
        "[TÍTULO 1] (máx 30 chars), [TÍTULO 2] (máx 30 chars), [TÍTULO 3] (máx 30 chars), "
        "[DESCRIÇÃO 1] (máx 90 chars), [DESCRIÇÃO 2] (máx 90 chars). "
        "Inclua a palavra-chave principal nos títulos. Conte os caracteres com rigor."
    ),
    "TikTok Ads": (
        "Formato TikTok: gancho nos primeiros 3 segundos é CRÍTICO. "
        "Texto principal curto (máx 100 chars), linguagem jovem e ritmo acelerado. "
        "Separe: [LEGENDA] e [TEXTO NA TELA] (se roteiro)."
    ),
    "YouTube In-Stream": (
        "Formato YouTube In-Stream: os primeiros 5 segundos determinam se o usuário pula. "
        "Use os rótulos de tempo: [0-5s GANCHO], [6-15s DESENVOLVIMENTO], [16-30s OFERTA+CTA]."
    ),
}

@app.route("/api/copys/gerar", methods=["POST"])
@login_required
def api_copys_gerar():
    data              = request.get_json() or {}
    plataforma        = (data.get("plataforma")       or "Meta Ads (Facebook/Instagram)").strip()
    framework         = (data.get("framework")        or "AIDA").strip()
    tom               = (data.get("tom")              or "Curto, Seco e Direto ao Ponto").strip()
    nicho             = (data.get("nicho")            or "").strip()
    oferta            = (data.get("oferta")           or "").strip()
    profissao         = (data.get("profissao")        or "").strip()
    nivel_consciencia = (data.get("nivel_consciencia") or "Público Frio (Topo)").strip()
    gatilho           = (data.get("gatilho")          or "Urgência").strip()
    tamanho           = (data.get("tamanho")          or "Média (Feed)").strip()
    cta               = (data.get("cta")              or "").strip()
    usar_emojis       = data.get("usar_emojis", False)
    variacao          = data.get("variacao", False)

    if len(oferta) < 10:
        return jsonify({"error": "Descreva melhor a oferta / produto (mínimo 10 caracteres)."}), 400

    platform_hint = _COPYS_PLATFORM_HINTS.get(plataforma, "")
    emoji_instrucao = "Sim — use emojis estrategicamente" if usar_emojis else "Não — zero emojis, texto 100% limpo"

    linhas = [
        "═══ BRIEFING DA COPY ═══",
        f"Plataforma: {plataforma}",
        platform_hint,
        f"Framework / Estrutura: {framework}",
        f"Tom de Voz: {tom}",
        f"Nível de Consciência do Público: {nivel_consciencia}",
        f"Gatilho Mental Foco: {gatilho}",
        f"Tamanho da Copy: {tamanho}",
        f"Usar Emojis: {emoji_instrucao}",
        f"Especialista / Profissão: {profissao if profissao else 'Não informado'}",
        f"Nicho / Público-Alvo: {nicho if nicho else 'Geral'}",
        f"A Oferta / Produto: {oferta}",
        f"CTA Exato a usar: {cta if cta else 'Crie um CTA adequado ao contexto'}",
        "",
    ]

    if variacao:
        linhas.append(
            "INSTRUÇÃO ESPECIAL — VARIAÇÃO A/B: Crie uma copy com ângulo COMPLETAMENTE DIFERENTE "
            "da geração anterior. Mude o gancho de entrada, a estrutura narrativa, o vocabulário e "
            "a abordagem emocional. O objetivo é gerar uma alternativa para teste A/B que transmita "
            "a mesma oferta por um caminho totalmente diferente. Surpreenda."
        )
    else:
        linhas.append("Gere agora a copy de alta conversão seguindo EXATAMENTE todas as especificações acima.")

    user_msg = "\n".join(filter(None, linhas))

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada no servidor."}), 500

    try:
        ctx = brain.contexto(nicho)
        system_prompt = _COPYS_SYSTEM
        if ctx:
            system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        copy_text = (msg.content[0].text or "").strip()
        if not copy_text:
            return jsonify({"error": "A IA retornou uma resposta vazia."}), 500
        brain.salvar(
            modulo="Copys",
            titulo=f"Copy {plataforma} {framework}",
            inputs={
                "plataforma": plataforma,
                "framework": framework,
                "tom": tom,
                "nicho": nicho,
                "oferta": oferta,
                "profissao": profissao,
                "nivel_consciencia": nivel_consciencia,
                "gatilho": gatilho,
                "tamanho": tamanho,
            },
            output=copy_text,
            model="claude-sonnet-4-6",
            cliente=nicho,
        )
        return jsonify({"copy": copy_text, "variacao": variacao})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# ── API: Meta Insights para Relatórios ──────────────────────────────────────
import re as _re

_meta_insights_cache: dict = {}   # account_id → {"ts": float, "data": dict}
_META_CACHE_TTL = 1800            # 30 minutos

# Tokens por agência (expansível)
_META_TOKENS = {
    "piloti": lambda: os.environ.get("META_TOKEN_PILOTI", "").strip(),
    "dentto": lambda: os.environ.get("META_TOKEN_DENTTO", "").strip(),
}

@app.route("/api/relatorios/insights/<agency>/<account_id>")
@login_required
def api_relatorios_insights(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    cache_key = f"{agency}:{account_id}"
    now = time.time()
    if cache_key in _meta_insights_cache:
        cached = _meta_insights_cache[cache_key]
        if now - cached["ts"] < _META_CACHE_TTL:
            return jsonify(cached["data"])

    token_fn = _META_TOKENS.get(agency)
    token = token_fn() if token_fn else ""
    if not token:
        return jsonify({"error": f"Token da agência '{agency}' não configurado"}), 500

    def _find_action(arr, *types):
        """Percorre um array de actions e retorna o value do primeiro type encontrado."""
        for entry in (arr or []):
            if entry.get("action_type") in types:
                try:
                    return float(entry.get("value", 0) or 0)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/insights",
            params={
                "fields": "spend,impressions,clicks,reach,cpm,ctr,frequency,"
                          "actions,cost_per_action_type",
                "date_preset": "last_7d",
                "access_token": token,
            },
            timeout=15,
        )
        if not r.ok:
            err = r.json().get("error", {})
            return jsonify({"error": err.get("message", f"Meta API {r.status_code}")}), 502

        data = r.json().get("data", [])
        if not data:
            result = {
                "spend": 0.0, "impressions": 0, "clicks": 0, "reach": 0,
                "leads": 0,          "lead_cost": 0.0,
                "messaging": 0,      "messaging_cost": 0.0,
                "profile_visits": 0, "profile_visit_cost": 0.0,
                "purchases": 0,
                "ctr": "0.00", "cpm": "0.00", "frequency": "1.00", "empty": True,
            }
            _meta_insights_cache[cache_key] = {"ts": now, "data": result}
            return jsonify(result)

        row      = data[0]
        actions  = row.get("actions") or []
        costs    = row.get("cost_per_action_type") or []

        # ── Extrações com fallback seguro ────────────────────────────
        leads          = int(_find_action(actions, "lead"))
        lead_cost      = _find_action(costs,   "lead")

        profile_visits      = int(_find_action(actions, "instagram_profile_visit"))
        profile_visit_cost  = _find_action(costs,   "instagram_profile_visit")

        # Fallback: campanhas OUTCOME_TRAFFIC (Turbinar/boost) reportam visitas como link_click
        if profile_visits == 0:
            try:
                # Passo 1: pega IDs das campanhas OUTCOME_TRAFFIC
                rc = requests.get(
                    f"https://graph.facebook.com/v21.0/{account_id}/campaigns",
                    params={"fields": "objective", "access_token": token},
                    timeout=10,
                )
                traffic_ids = [
                    c["id"] for c in rc.json().get("data", [])
                    if c.get("objective") == "OUTCOME_TRAFFIC"
                ]
                # Passo 2: query direta de insights por campanha (evita dados incorretos do embed)
                traffic_clicks = 0
                traffic_spend  = 0.0
                for cid in traffic_ids:
                    ri = requests.get(
                        f"https://graph.facebook.com/v21.0/{cid}/insights",
                        params={
                            "fields": "spend,actions",
                            "date_preset": "last_7d",
                            "access_token": token,
                        },
                        timeout=10,
                    )
                    ri_row = (ri.json().get("data") or [{}])[0]
                    traffic_clicks += int(_find_action(ri_row.get("actions") or [], "link_click"))
                    traffic_spend  += float(ri_row.get("spend", 0) or 0)
                print(f"[Jake debug] traffic_ids={traffic_ids} clicks={traffic_clicks} spend={traffic_spend}")
                if traffic_clicks > 0:
                    profile_visits     = traffic_clicks
                    profile_visit_cost = traffic_spend / traffic_clicks
            except Exception as _e:
                print(f"[Jake debug] fallback erro: {_e}")

        messaging      = int(_find_action(
            actions,
            "onsite_conversion.messaging_conversation_started_7d",
            "onsite_conversion.messaging_conversation_started",
        ))
        messaging_cost = _find_action(
            costs,
            "onsite_conversion.messaging_conversation_started_7d",
            "onsite_conversion.messaging_conversation_started",
        )

        purchases = int(_find_action(actions, "purchase", "omni_purchase"))

        # Diagnóstico: todos os action_types retornados
        raw_actions = {a.get("action_type"): a.get("value") for a in actions}

        result = {
            "spend":              float(row.get("spend", 0) or 0),
            "impressions":        int(row.get("impressions", 0) or 0),
            "clicks":             int(row.get("clicks", 0) or 0),
            "reach":              int(row.get("reach", 0) or 0),
            "leads":              leads,
            "lead_cost":          lead_cost,
            "messaging":          messaging,
            "messaging_cost":     messaging_cost,
            "profile_visits":     profile_visits,
            "profile_visit_cost": profile_visit_cost,
            "purchases":          purchases,
            "ctr":                row.get("ctr", "0.00"),
            "cpm":                row.get("cpm", "0.00"),
            "frequency":          row.get("frequency", "1.00"),
            "_actions":           raw_actions,
        }
        _meta_insights_cache[cache_key] = {"ts": now, "data": result}
        return jsonify(result)

    except requests.Timeout:
        return jsonify({"error": "Timeout na Meta API"}), 504
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# ── API: Debug — action_types brutos de uma conta Meta ──────────────────────
@app.route("/api/relatorios/debug/<agency>/<account_id>")
@login_required
def api_relatorios_debug(agency, account_id):
    import re as _re2
    if not _re2.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID inválido"}), 400
    token_fn = _META_TOKENS.get(agency)
    token = token_fn() if token_fn else ""
    if not token:
        return jsonify({"error": f"Token da agência '{agency}' não configurado"}), 500
    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/insights",
            params={
                "fields": "spend,actions,cost_per_action_type",
                "date_preset": "last_7d",
                "access_token": token,
            },
            timeout=15,
        )
        data = r.json().get("data", [])
        if not data:
            return jsonify({"info": "Sem dados nos últimos 7 dias", "raw": r.json()})
        row = data[0]
        account_result = {
            "nivel": "conta",
            "spend": row.get("spend"),
            "actions": row.get("actions", []),
            "cost_per_action_type": row.get("cost_per_action_type", []),
        }

        # Busca também por campanha para encontrar dados de Turbinar/boost
        r2 = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/campaigns",
            params={
                "fields": "name,objective,insights.date_preset(last_7d){spend,actions,cost_per_action_type}",
                "access_token": token,
            },
            timeout=15,
        )
        campaigns = []
        for c in r2.json().get("data", []):
            ins = (c.get("insights") or {}).get("data", [{}])
            ins_row = ins[0] if ins else {}
            if float(ins_row.get("spend", 0) or 0) > 0:
                campaigns.append({
                    "nome": c.get("name"),
                    "objetivo": c.get("objective"),
                    "spend": ins_row.get("spend"),
                    "actions": ins_row.get("actions", []),
                    "cost_per_action_type": ins_row.get("cost_per_action_type", []),
                })

        return jsonify({"account": account_result, "campaigns": campaigns})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# ── Vault Obsidian — helpers ────────────────────────────────────────────────

import unicodedata as _unicodedata

def _slug(name: str) -> str:
    """Normaliza nome para uso como path: lowercase, sem acentos, espaços→hífens."""
    n = _unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if _unicodedata.category(c) != "Mn")
    return _re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")

_VAULT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jake-brain", "Clientes")

def _vault_ler_contexto(nome: str) -> str:
    """Lê o .md mais recente de jake-brain/Clientes/<slug>/Performance/"""
    slug = _slug(nome)
    pasta = os.path.join(_VAULT_ROOT, slug, "Performance")
    if not os.path.isdir(pasta):
        return ""
    arquivos = sorted([f for f in os.listdir(pasta) if f.endswith(".md")], reverse=True)
    if not arquivos:
        return ""
    try:
        with open(os.path.join(pasta, arquivos[0]), encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def _vault_salvar_snapshot(nome: str, metricas: dict, metricas_anterior: dict, delta: dict, analise: str):
    """Salva snapshot semanal em jake-brain/Clientes/<slug>/Performance/YYYY-WXX.md"""
    from datetime import date
    slug  = _slug(nome)
    pasta = os.path.join(_VAULT_ROOT, slug, "Performance")
    os.makedirs(pasta, exist_ok=True)
    hoje   = date.today()
    semana = hoje.strftime("%Y-W%W")
    path   = os.path.join(pasta, f"{semana}.md")
    linhas_met = "\n".join(
        f"| {k} | {v} | {metricas_anterior.get(k,'--')} | {delta.get(k,'--')} |"
        for k, v in metricas.items()
    )
    conteudo = f"""# Performance — {nome} — {semana}

**Data de análise:** {hoje.isoformat()}

## Métricas
| Métrica | Atual | Anterior | Delta |
|---|---|---|---|
{linhas_met}

## Análise IA
{analise}
"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(conteudo)
    except Exception as e:
        print(f"[Jake vault] erro ao salvar snapshot: {e}")

# ── API: Análise IA para Relatórios ──────────────────────────────────────────
@app.route("/api/relatorios/analise", methods=["POST"])
@login_required
def api_relatorios_analise():
    data              = request.get_json() or {}
    nome              = (data.get("nome") or "").strip()
    metricas          = data.get("metricas") or {}
    metricas_anterior = data.get("metricas_anterior") or {}
    delta             = data.get("delta") or {}

    client = _anthropic_client()
    if not client:
        return jsonify({"analise": ""})

    metricas_str = "\n".join(f"- {k}: {v}" for k, v in metricas.items())

    # Contexto histórico do vault Obsidian
    contexto_vault = _vault_ler_contexto(nome)
    bloco_vault = (
        f"\n\nContexto histórico do cliente (semanas anteriores):\n{contexto_vault[:800]}"
        if contexto_vault else ""
    )

    # Comparação com semana anterior
    bloco_anterior = ""
    if metricas_anterior:
        ant_str   = "\n".join(f"- {k}: {v}" for k, v in metricas_anterior.items())
        delta_str = "\n".join(f"- {k}: {v}" for k, v in delta.items()) if delta else ""
        bloco_anterior = (
            f"\n\nSemana anterior:\n{ant_str}"
            + (f"\n\nVariação (atual vs anterior):\n{delta_str}" if delta_str else "")
        )

    prompt = (
        f"Você é analista de tráfego pago. Gere uma análise BREVE (2-3 frases, máximo 140 palavras) "
        f"sobre os resultados das campanhas Meta Ads de '{nome}' nos últimos 7 dias.\n\n"
        f"Dados atuais:\n{metricas_str}"
        f"{bloco_anterior}"
        f"{bloco_vault}\n\n"
        f"Seja direto, profissional, em português brasileiro. "
        f"Destaque o principal resultado, compare com semana anterior se disponível, e dê UMA recomendação prática. "
        f"NÃO use markdown, asteriscos, negrito ou formatação. Apenas texto corrido simples."
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        analise = (msg.content[0].text or "").strip()
        if metricas:
            _vault_salvar_snapshot(nome, metricas, metricas_anterior, delta, analise)
        return jsonify({"analise": analise})
    except Exception as exc:
        return jsonify({"analise": "", "error": str(exc)})


# ── API: Performance — Saldo ────────────────────────────────────────────────

_perf_saldo_cache: dict = {}
_PERF_SALDO_TTL = 1800  # 30 min

@app.route("/api/performance/saldo/<agency>/<account_id>")
@login_required
def api_performance_saldo(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    token_fn = _META_TOKENS.get(agency)
    if not token_fn:
        return jsonify({"error": "Agência não encontrada"}), 404

    cache_key = f"saldo:{agency}:{account_id}"
    now = time.time()
    if cache_key in _perf_saldo_cache:
        cached = _perf_saldo_cache[cache_key]
        if now - cached["ts"] < _PERF_SALDO_TTL:
            return jsonify(cached["data"])

    token = token_fn()
    if not token:
        return jsonify({"error": "Token da agência não configurado"}), 500

    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}",
            params={"fields": "amount_spent,balance,spend_cap,currency", "access_token": token},
            timeout=15,
        )
        if not r.ok:
            err = r.json().get("error", {})
            return jsonify({"error": err.get("message", f"Meta API {r.status_code}")}), 502
        data = r.json()
        amount_spent = float(data.get("amount_spent", 0) or 0) / 100
        balance      = float(data.get("balance", 0) or 0) / 100
        spend_cap    = float(data.get("spend_cap", 0) or 0) / 100
        remaining    = max(0.0, spend_cap - amount_spent) if spend_cap else balance
        result = {
            "amount_spent": round(amount_spent, 2),
            "balance":      round(balance, 2),
            "spend_cap":    round(spend_cap, 2),
            "remaining":    round(remaining, 2),
            "currency":     data.get("currency", "BRL"),
            "alerta":       remaining < 150.0,
        }
        _perf_saldo_cache[cache_key] = {"ts": now, "data": result}
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── API: Performance — Alerta de Saldo ─────────────────────────────────────

_alerta_sent_cache: dict = {}  # account_id -> timestamp último envio
_ALERTA_TTL = 3600  # 1 hora

@app.route("/api/performance/alerta-saldo", methods=["POST"])
@login_required
def api_performance_alerta_saldo():
    data       = request.get_json() or {}
    account_id = (data.get("account_id") or "").strip()
    nome       = (data.get("nome") or "conta").strip()
    agency     = (data.get("agency") or "").strip()
    saldo      = data.get("saldo", 0)

    now = time.time()
    last = _alerta_sent_cache.get(account_id, 0)
    if now - last < _ALERTA_TTL:
        return jsonify({"ok": True, "dedup": True})

    msg = f"⚠️ Patrão, saldo baixo em {nome} ({agency}): R$ {float(saldo):,.2f}"
    ok, detail = _send_telegram(msg)
    _alerta_sent_cache[account_id] = now
    return jsonify({"ok": ok, "detail": detail})


# ── API: Performance — Semana Anterior ─────────────────────────────────────

def _extract_insights_row(row: dict) -> dict:
    """Extrai métricas de uma linha de insights da Meta API."""
    actions = row.get("actions") or []
    costs   = row.get("cost_per_action_type") or []

    def _fa(arr, *types):
        for entry in (arr or []):
            if entry.get("action_type") in types:
                try:
                    return float(entry.get("value", 0) or 0)
                except Exception:
                    return 0.0
        return 0.0

    leads     = int(_fa(actions, "lead"))
    messaging = int(_fa(actions,
        "onsite_conversion.messaging_conversation_started_7d",
        "onsite_conversion.messaging_conversation_started"))
    purchases = int(_fa(actions, "purchase", "omni_purchase"))
    profile_visits = int(_fa(actions, "instagram_profile_visit"))
    spend     = float(row.get("spend", 0) or 0)

    return {
        "spend":          round(spend, 2),
        "impressions":    int(row.get("impressions", 0) or 0),
        "clicks":         int(row.get("clicks", 0) or 0),
        "reach":          int(row.get("reach", 0) or 0),
        "cpm":            row.get("cpm", "0.00"),
        "ctr":            row.get("ctr", "0.00"),
        "frequency":      row.get("frequency", "1.00"),
        "leads":          leads,
        "messaging":      messaging,
        "purchases":      purchases,
        "profile_visits": profile_visits,
    }


def _fetch_meta_period(account_id: str, token: str, since: str, until: str) -> dict:
    """Busca insights de um período específico (since/until em YYYY-MM-DD)."""
    r = requests.get(
        f"https://graph.facebook.com/v21.0/{account_id}/insights",
        params={
            "fields": "spend,impressions,clicks,reach,cpm,ctr,frequency,actions,cost_per_action_type",
            "time_range": '{"since":"' + since + '","until":"' + until + '"}',
            "access_token": token,
        },
        timeout=15,
    )
    if not r.ok:
        return {}
    data = r.json().get("data", [])
    if not data:
        return {"spend": 0, "impressions": 0, "clicks": 0, "reach": 0,
                "leads": 0, "messaging": 0, "purchases": 0, "profile_visits": 0,
                "cpm": "0.00", "ctr": "0.00", "frequency": "1.00"}
    return _extract_insights_row(data[0])


@app.route("/api/performance/semana-anterior/<agency>/<account_id>")
@login_required
def api_performance_semana_anterior(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    token_fn = _META_TOKENS.get(agency)
    if not token_fn:
        return jsonify({"error": "Agência não encontrada"}), 404
    token = token_fn()
    if not token:
        return jsonify({"error": "Token da agência não configurado"}), 500

    from datetime import date, timedelta
    today          = date.today()
    since_atual    = (today - timedelta(days=6)).isoformat()
    until_atual    = today.isoformat()
    since_anterior = (today - timedelta(days=13)).isoformat()
    until_anterior = (today - timedelta(days=7)).isoformat()

    try:
        atual    = _fetch_meta_period(account_id, token, since_atual, until_atual)
        anterior = _fetch_meta_period(account_id, token, since_anterior, until_anterior)
        return jsonify({"atual": atual, "anterior": anterior})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── API: Fábrica de Criativos (Texto + Imagem) ─────────────────────────────────

def _parse_creative_variants(raw: str) -> list[dict]:
    """
    Tenta extrair uma lista de {headline, subheadline} a partir de um JSON retornado pela IA.
    """
    try:
        raw = raw.strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("JSON não encontrado na resposta")
        slice_ = raw[start:end]
        parsed = json.loads(slice_)
        if not isinstance(parsed, list):
            raise ValueError("JSON não é uma lista")
        variants: list[dict] = []
        for item in parsed[:5]:
            hl = str(item.get("headline", "")).strip()
            sh = str(item.get("subheadline", "")).strip()
            if hl:
                variants.append({"headline": hl, "subheadline": sh})
        if not variants:
            raise ValueError("Nenhuma variação válida encontrada")
        while len(variants) < 5:
            variants.append(variants[-1])
        return variants
    except Exception as exc:  # pragma: no cover - diagnóstico
        print("[Jake] Erro ao parsear variantes de criativos:", exc, raw[:400])
        raise


def _generate_creative_texts(niche: str, campaign_focus: str, engine: str) -> list[dict]:
    focus_label = {
        "whatsapp": "campanhas de mensagem no WhatsApp (objetivo leads/contato)",
        "conversion": "conversões diretas (vendas/checkout)",
        "awareness": "reconhecimento de marca e lembrança",
    }.get(campaign_focus, "campanhas de mensagem no WhatsApp (objetivo leads/contato)")

    system_prompt = (
        "Você é um copywriter especialista em anúncios para Meta Ads focados em campanhas de mensagem.\n\n"
        "Gere EXATAMENTE 5 variações, cada uma com:\n"
        '- \"headline\": promessa curta, agressiva e clara (máx. 55 caracteres).\n'
        '- \"subheadline\": texto de apoio de 1 a 2 frases, focado em benefício e próximo da linguagem do público.\n\n'
        "Contexto:\n"
        f"- Público/nicho: {niche}\n"
        f"- Foco da campanha: {focus_label}\n\n"
        "Responda APENAS em JSON, no formato:\n\n"
        '[\n  { "headline": "...", "subheadline": "..." },\n  ... (total 5 itens)\n]\n'
    )

    if engine == "claude":
        client = _anthropic_client()
        if not client:
            raise RuntimeError("ANTHROPIC_API_KEY não configurada para o motor de texto.")
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=900,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": "Gere as 5 variações em português brasileiro conforme instruções, respondendo apenas com o JSON.",
            }],
        )
        raw = (msg.content[0].text or "").strip()
        return _parse_creative_variants(raw)
    else:
        client = _openai_client()
        if not client:
            raise RuntimeError("OPENAI_API_KEY não configurada para o motor de texto.")
        resp = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.8,
            max_tokens=900,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Gere as 5 variações em português brasileiro conforme instruções, em JSON."},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
        return _parse_creative_variants(raw)


def _file_to_data_url(f) -> str:
    """Converte um arquivo enviado via formulário em data URL."""
    content = f.read()
    mime = f.mimetype or "image/jpeg"
    b64 = base64.b64encode(content).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _generate_kontext(instruction: str, input_image_data_url: str, token: str) -> str:
    """Edita uma imagem com Flux Kontext Pro. Retorna URL da imagem editada."""
    headers = {**_replicate_headers(), "Prefer": "wait=120"}
    resp = requests.post(
        f"{_REPLICATE_BASE}/models/black-forest-labs/flux-kontext-pro/predictions",
        headers=headers,
        json={"input": {
            "prompt": instruction,
            "input_image": input_image_data_url,
            "output_format": "webp",
            "output_quality": 90,
        }},
        timeout=120,
    )
    if not resp.ok:
        raise ValueError(f"Replicate Kontext {resp.status_code}: {resp.text[:300]}")
    pred = resp.json()
    if pred.get("status") == "succeeded":
        out = pred.get("output")
        return out[0] if isinstance(out, list) else out
    get_url = (pred.get("urls") or {}).get("get", "")
    hdrs = {"Authorization": headers["Authorization"]}
    for _ in range(30):
        time.sleep(4)
        p = requests.get(get_url, headers=hdrs, timeout=15).json()
        if p.get("status") == "succeeded":
            out = p.get("output")
            return out[0] if isinstance(out, list) else out
        if p.get("status") == "failed":
            raise ValueError("Kontext: geração falhou")
    raise ValueError("Kontext: timeout")


def _generate_creative_images(mode: str, image_engine: str, prompt: str, image_file):
    """
    Gera até 5 imagens (ou reutiliza a mesma) dependendo do modo.
    Retorna lista de data URLs.
    """
    images: list[str] = []

    # Kontext: upload + instrução → edição consistente da imagem de referência
    if mode == "upload" and image_file and prompt:
        replicate_token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
        if replicate_token:
            try:
                image_file.seek(0)
                input_data_url = _file_to_data_url(image_file)
                edited_url = _generate_kontext(prompt, input_data_url, replicate_token)
                edited_data_url = _url_to_data_url(edited_url)
                return [edited_data_url] * 5
            except Exception as exc:
                print("[Jake] Kontext falhou, usando imagem original:", exc)
                image_file.seek(0)
        # fallback: devolve imagem original
        try:
            image_file.seek(0)
            data_url = _file_to_data_url(image_file)
            return [data_url] * 5
        except Exception as exc:
            print("[Jake] Erro ao converter imagem de upload:", exc)
            return []

    # Upload sem instrução: devolve a foto base em todos os criativos
    if mode == "upload" and image_file:
        try:
            data_url = _file_to_data_url(image_file)
            images = [data_url] * 5
            return images
        except Exception as exc:
            print("[Jake] Erro ao converter imagem de upload:", exc)
            return []

    # Prompt: gera uma imagem sintética e replica para os 5 cards.
    if mode == "prompt" and prompt:
        # 1️⃣ Flux 1.1 Pro via Replicate
        replicate_token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
        if replicate_token and image_engine == "flux":
            try:
                image_url = _generate_flux(prompt, replicate_token)
                data_url = _url_to_data_url(image_url)
                images = [data_url] * 5
                return images
            except Exception as flux_err:  # pragma: no cover - diagnóstico
                print("[Jake] Flux (Fábrica de Criativos) falhou, tentando fallback:", flux_err)

        # 2️⃣ Fallback com DALL-E 3 (ou uso como pseudo-Imagen 4)
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_key:
            try:
                client = OpenAI(api_key=openai_key)
                final_prompt = f"{prompt}. {_IMG_MASTER_STYLE}"
                resp = client.images.generate(
                    model="dall-e-3",
                    prompt=final_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                image_url = resp.data[0].url
                data_url = _url_to_data_url(image_url)
                images = [data_url] * 5
                return images
            except Exception as e:  # pragma: no cover - diagnóstico
                print("[Jake] DALL-E fallback (Fábrica de Criativos) falhou:", e)

    return images


@app.route("/api/generate-creative", methods=["POST"])
@login_required
def api_generate_creative():
    """
    Endpoint da Fábrica de Criativos.

    Recebe multipart/form-data com:
    - mode: 'prompt' ou 'upload'
    - image_engine: 'flux' ou 'imagen4'
    - text_engine: 'claude' ou 'gpt4o'
    - campaign_focus: 'whatsapp' | 'conversion' | 'awareness'
    - niche: string
    - prompt: (se mode = prompt)
    - image: arquivo (se mode = upload)
    """
    mode = (request.form.get("mode") or "prompt").strip()
    image_engine = (request.form.get("image_engine") or "flux").strip()
    text_engine = (request.form.get("text_engine") or "claude").strip()
    campaign_focus = (request.form.get("campaign_focus") or "whatsapp").strip()
    niche = (request.form.get("niche") or "").strip()
    prompt = (request.form.get("prompt") or "").strip()
    image_file = request.files.get("image")

    if not niche:
        return jsonify({"error": "Preencha o público/nicho antes de gerar."}), 400

    if mode == "prompt" and not prompt:
        return jsonify({"error": "Descreva a cena do criativo (prompt)."}), 400

    if mode == "upload" and (not image_file or not image_file.filename):
        return jsonify({"error": "Envie uma imagem base no modo Upload."}), 400

    try:
        texts = _generate_creative_texts(niche, campaign_focus, text_engine)
    except Exception as exc:
        return jsonify({"error": f"Falha ao gerar textos: {exc}"}), 500

    try:
        images = _generate_creative_images(mode, image_engine, prompt, image_file)
    except Exception as exc:
        print("[Jake] Erro ao gerar imagens (Fábrica de Criativos):", exc)
        images = []

    creatives = []
    for i in range(5):
        t = texts[i] if i < len(texts) else texts[-1]
        img = images[i] if i < len(images) else (images[0] if images else None)
        creatives.append({
            "id": i + 1,
            "headline": t.get("headline", ""),
            "subheadline": t.get("subheadline", ""),
            "image": img,
        })

    # Detecta se o caminho Kontext foi usado
    effective_image_engine = image_engine
    if mode == "upload" and prompt:
        effective_image_engine = "kontext"

    return jsonify({
        "creatives": creatives,
        "meta": {
            "mode": mode,
            "image_engine": effective_image_engine,
            "text_engine": text_engine,
            "campaign_focus": campaign_focus,
        },
    })

# ── Engenheiro de Prompts ─────────────────────────────────────────────────────

_PROMPT_ENGINEER_SYSTEM = """Você é um Engenheiro de Prompts Sênior com mais de 20 anos de experiência criando prompts estruturados de alta performance para os mais diversos contextos: marketing, tecnologia, educação, jurídico, criativo, negócios e muito mais.

Seu fluxo de trabalho tem DUAS ETAPAS obrigatórias:

---

**ETAPA 1 — PERGUNTAS ESTRATÉGICAS**

Quando o usuário apresentar uma ideia ou projeto, você NUNCA gera o prompt direto. Primeiro, você faz de 5 a 7 perguntas estratégicas e objetivas para entender:
- O objetivo principal do prompt
- O público-alvo ou destinatário
- O contexto de uso (plataforma, ferramenta, situação)
- Tom e linguagem desejados
- Restrições ou requisitos específicos
- Exemplos de resultados esperados (se houver)

Formate as perguntas assim (JSON obrigatório):
{"type":"questions","questions":["Pergunta 1?","Pergunta 2?","Pergunta 3?","Pergunta 4?","Pergunta 5?"]}

---

**ETAPA 2 — GERAÇÃO DO PROMPT ESTRUTURADO**

Após o usuário responder, gere o prompt final:

{"type":"prompt","title":"Título descritivo curto (máx 50 chars)","prompt":"O prompt completo e estruturado aqui, rico em detalhes, com persona se aplicável, contexto, formato de saída esperado, restrições e exemplos relevantes."}

---

**REGRAS:**
- Responda SEMPRE em português brasileiro
- Nunca gere o prompt sem fazer as perguntas primeiro
- Se a resposta for insuficiente, faça perguntas de refinamento (mesma estrutura JSON)
- Fora dos JSONs, pode conversar normalmente — o texto será exibido como mensagem normal"""


@app.route("/api/prompts/sessoes", methods=["GET"])
@login_required
def prompts_listar_sessoes():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, titulo, criado_em, atualizado_em FROM prompt_sessions "
            "ORDER BY atualizado_em DESC LIMIT 100"
        )
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify({"sessoes": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/prompts/sessoes", methods=["POST"])
@login_required
def prompts_criar_sessao():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO prompt_sessions (titulo) VALUES (NULL) RETURNING id, criado_em, atualizado_em"
        )
        row = dict(cur.fetchone())
        conn.commit()
        return jsonify(row)
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/prompts/sessoes/<int:sid>/mensagens", methods=["GET"])
@login_required
def prompts_listar_mensagens(sid):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, role, content, criado_em FROM prompt_messages "
            "WHERE session_id = %s ORDER BY criado_em ASC",
            (sid,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify({"mensagens": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/prompts/sessoes/<int:sid>/chat", methods=["POST"])
@login_required
def prompts_chat(sid):
    d = request.get_json() or {}
    user_msg = (d.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Mensagem vazia"}), 400

    conn = _get_db()
    try:
        cur = conn.cursor()

        # Verifica que a sessão existe
        cur.execute("SELECT id FROM prompt_sessions WHERE id = %s", (sid,))
        if not cur.fetchone():
            return jsonify({"error": "Sessão não encontrada"}), 404

        # Carrega histórico
        cur.execute(
            "SELECT role, content FROM prompt_messages "
            "WHERE session_id = %s ORDER BY criado_em ASC",
            (sid,)
        )
        history = [{"role": r["role"], "content": r["content"]} for r in cur.fetchall()]

        # Adiciona nova mensagem do usuário ao histórico
        history.append({"role": "user", "content": user_msg})

        # Chama Claude
        client = _anthropic_client_46()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_PROMPT_ENGINEER_SYSTEM,
            messages=history
        )
        reply = response.content[0].text

        # Salva par user + assistant
        cur.execute(
            "INSERT INTO prompt_messages (session_id, role, content) VALUES (%s, %s, %s)",
            (sid, "user", user_msg)
        )
        cur.execute(
            "INSERT INTO prompt_messages (session_id, role, content) VALUES (%s, %s, %s)",
            (sid, "assistant", reply)
        )

        # Atualiza atualizado_em da sessão
        cur.execute(
            "UPDATE prompt_sessions SET atualizado_em = NOW() WHERE id = %s", (sid,)
        )
        conn.commit()
        return jsonify({"reply": reply})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/prompts/sessoes/<int:sid>/titulo", methods=["PATCH"])
@login_required
def prompts_atualizar_titulo(sid):
    d = request.get_json() or {}
    titulo = (d.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"error": "Título vazio"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prompt_sessions SET titulo = %s, atualizado_em = NOW() WHERE id = %s",
            (titulo, sid)
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/prompts/sessoes/<int:sid>", methods=["DELETE"])
@login_required
def prompts_deletar_sessao(sid):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM prompt_sessions WHERE id = %s", (sid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ── Inicialização ────────────────────────────────────────────────────────────
def _local_ip():
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

# ── Prompt mestre cinematográfico ────────────────────────────────────────────
_IMG_MASTER_STYLE = (
    "Cinematic ultra-realistic editorial photograph, 8K. "
    "Hyperdetailed textures, dramatic chiaroscuro lighting — deep rich shadows contrasted with luminous practicals. "
    "Shot on Hasselblad medium format, 50mm f/1.4, shallow depth of field with smooth bokeh. "
    "Award-winning commercial photography, magazine cover quality. "
    "No text, no watermarks, no logos, no UI mockups."
)

def _carousel_image_style_suffix(style_visual: str, mix_reality: str, palette: str) -> str:
    """Monta sufixo de estilo para geração de imagem do carrossel."""
    style_map = {
        "editorial": "Editorial realista, revista de negócios, luz natural e composição limpa.",
        "luxo": "High fashion, moda e luxo, estética de campanha premium, tecidos e ambientes refinados.",
        "cyberpunk": "Futurista cyberpunk, neon, tecnologia e humano fundidos, cenários distópicos.",
        "documental": "Documentário, fotografia crua, realismo sem retoque excessivo.",
        "retrato": "Retrato editorial, foco no rosto e expressão, fundo suave.",
        "produto": "Fotografia de produto, foco no objeto, fundo neutro ou lifestyle.",
    }
    mix_map = {
        "leve": "Leve toque digital: reflexos ou partículas sutis, mantendo o real dominante.",
        "medio": "Mistura equilibrada: elementos digitais/holográficos integrados à cena real — dados, luzes volumétricas, UI flutuante.",
        "forte": "Mistura forte real × IA: cenário real com personagens ou objetos claramente digitais, hologramas, circuitos visíveis.",
    }
    palette_map = {
        "neutro": "Paleta neutra, tons de cinza e bege, destaque sutil em uma cor.",
        "quente": "Paleta quente: âmbar, dourado, laranja suave, sensação acolhedora.",
        "frio": "Paleta fria: azul, teal, prata, sensação tecnológica.",
        "neon": "Neon: roxo, rosa elétrico, ciano, alto contraste.",
        "pb": "Preto e branco, alto contraste, cinematográfico.",
    }
    a = style_map.get(style_visual or "", style_map["editorial"])
    b = mix_map.get(mix_reality or "", mix_map["medio"])
    c = palette_map.get(palette or "", palette_map["neutro"])
    return f"{a} {b} Colorização: {c}"

def _url_to_data_url(url: str) -> str:
    resp = requests.get(url, timeout=60)
    mime = resp.headers.get("content-type", "image/webp")
    b64  = base64.b64encode(resp.content).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def _generate_flux(prompt: str, token: str, style_suffix: str | None = None) -> str:
    """Generate image with Flux 1.1 Pro via Replicate. Returns image URL."""
    import time as _time
    final_prompt = f"{prompt}. {_IMG_MASTER_STYLE}"
    if style_suffix:
        final_prompt = f"{final_prompt}. {style_suffix}"
    resp = requests.post(
        "https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro/predictions",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "wait=60",
        },
        json={
            "input": {
                "prompt": final_prompt,
                "aspect_ratio": "4:5",
                "output_format": "webp",
                "output_quality": 92,
                "safety_tolerance": 2,
                "prompt_upsampling": True,
            }
        },
        timeout=75,
    )
    if not resp.ok:
        detail = ""
        try:
            data = resp.json()
            detail = str(data.get("detail") or data.get("error") or "")[:200]
        except Exception:
            detail = resp.text[:200]
        lower_detail = detail.lower()
        if resp.status_code == 429 or "throttled" in lower_detail or "rate limit" in lower_detail:
            raise RuntimeError(
                "Replicate: limite de velocidade atingido. "
                "Com saldo baixo (< US$5), o limite é de 6 requisições por minuto com burst de 1. "
                "Gere menos slides por vez (ex.: 1–3) ou espere alguns segundos antes de tentar novamente."
            )
        raise RuntimeError(f"Replicate {resp.status_code}: {detail}")

    pred = resp.json()
    # Synchronous path
    if pred.get("status") == "succeeded":
        out = pred.get("output")
        return (out[0] if isinstance(out, list) else out)

    # Async polling fallback
    get_url = (pred.get("urls") or {}).get("get")
    if get_url:
        for _ in range(25):
            _time.sleep(3)
            p = requests.get(get_url, headers={"Authorization": f"Bearer {token}"}, timeout=10).json()
            if p.get("status") == "succeeded":
                out = p.get("output")
                return (out[0] if isinstance(out, list) else out)
            if p.get("status") in ("failed", "canceled"):
                raise RuntimeError(f"Flux falhou: {p.get('error', 'desconhecido')}")
    raise RuntimeError("Flux: timeout após polling.")

# ── Geração de imagens (apenas Replicate / Flux 1.1 Pro) ─────────────────────
@app.route("/api/carousel/generate-image", methods=["POST"])
@login_required
def api_carousel_generate_image():
    data         = request.get_json() or {}
    prompt       = (data.get("prompt") or "").strip()
    headline     = (data.get("headline") or "").strip()
    subheadline  = (data.get("subheadline") or "").strip()
    tag          = (data.get("tag") or "").strip()
    style_visual = (data.get("style_visual") or "").strip() or None
    mix_reality  = (data.get("mix_reality") or "").strip() or None
    palette      = (data.get("palette") or "").strip() or None
    modelo       = (data.get("modelo") or "flux-1.1-pro").strip()

    replicate_token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not replicate_token:
        return jsonify({"error": "Configure REPLICATE_API_TOKEN no .env para gerar imagens."}), 500

    # Gerar prompt via Claude se tiver contexto do slide
    if headline and not prompt:
        client = _anthropic_client()
        if client:
            try:
                ctx = f"Headline: {headline}"
                if subheadline: ctx += f"\nSubheadline: {subheadline}"
                if tag:         ctx += f"\nTag/seção: {tag}"
                style_hint = style_visual or "editorial realista"
                msg = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=150,
                    messages=[{"role": "user", "content":
                        f"Crie um prompt de imagem em inglês para um slide de carrossel do Instagram com este conteúdo:\n{ctx}\n\n"
                        f"Estilo visual: {style_hint}. Paleta: {palette or 'neutro'}.\n"
                        f"Regras: sem texto na imagem, foco em composição visual impactante, "
                        f"fotorrealista ou semi-realista, formato quadrado (1:1). "
                        f"Retorne APENAS o prompt em inglês, sem explicações."
                    }],
                )
                prompt = (msg.content[0].text or "").strip()
            except Exception:
                pass

    if not prompt and headline:
        prompt = headline + (". " + subheadline if subheadline else "")

    if len(prompt) < 5:
        return jsonify({"error": "Prompt muito curto."}), 400

    style_suffix = _carousel_image_style_suffix(style_visual, mix_reality, palette)
    full_prompt  = (prompt + " " + style_suffix).strip()

    try:
        if modelo in _CRIATIVOS_MODELOS_IMAGEM:
            slug    = _CRIATIVOS_MODELOS_IMAGEM[modelo]
            headers = _replicate_headers()
            headers["Prefer"] = "wait=60"
            resp = requests.post(
                f"{_REPLICATE_BASE}/models/{slug}/predictions",
                headers=headers,
                json={"input": {"prompt": full_prompt, "aspect_ratio": "1:1",
                                "output_format": "png"}},
                timeout=90,
            )
            if not resp.ok:
                return jsonify({"error": f"Replicate {resp.status_code}: {resp.text[:300]}"}), 500
            pred = resp.json()
            if pred.get("status") == "succeeded":
                out = pred.get("output")
                image_url = out[0] if isinstance(out, list) else out
            else:
                # polling
                get_url = (pred.get("urls") or {}).get("get", "")
                hdrs = {"Authorization": headers["Authorization"]}
                image_url = None
                for _ in range(20):
                    time.sleep(3)
                    p = requests.get(get_url, headers=hdrs, timeout=15).json()
                    if p.get("status") == "succeeded":
                        out = p.get("output")
                        image_url = out[0] if isinstance(out, list) else out
                        break
                    if p.get("status") == "failed":
                        return jsonify({"error": "Replicate: geração falhou"}), 500
                if not image_url:
                    return jsonify({"error": "Timeout na geração da imagem"}), 500
        else:
            image_url = _generate_flux(full_prompt, replicate_token)

        data_url = _url_to_data_url(image_url)
        return jsonify({"dataUrl": data_url, "prompt": prompt, "model": modelo})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: Financeiro Pessoal — Análise IA ────────────────────────────────────
@app.route("/api/financeiro/analise", methods=["POST"])
@login_required
def financeiro_analise():
    data = request.get_json(force=True) or {}
    mes        = data.get("mes", "este mês")
    receita    = data.get("receita", 0)
    despesas   = data.get("despesas", 0)
    saldo      = data.get("saldo", 0)
    receita_ant = data.get("receita_ant", 0)
    desp_ant   = data.get("desp_ant", 0)

    var_receita = ""
    if receita_ant > 0:
        pct = ((receita - receita_ant) / receita_ant) * 100
        var_receita = f"As receitas variaram {pct:+.1f}% em relação ao mês anterior."

    prompt = f"""Você é Jake, o assistente financeiro pessoal do Bruno. Analise os dados abaixo e forneça
uma análise direta, honesta e perspicaz sobre a saúde financeira em {mes}.
Use linguagem objetiva e tom de consultor financeiro. Máximo de 3 parágrafos curtos.

Dados de {mes}:
- Receita total: R$ {receita:,.2f}
- Despesas totais: R$ {despesas:,.2f}
- Saldo do mês: R$ {saldo:,.2f}
- Taxa de comprometimento: {(despesas/receita*100) if receita else 0:.1f}% da receita
- Comparativo: receita anterior R$ {receita_ant:,.2f} / despesas anteriores R$ {desp_ant:,.2f}
{var_receita}

CONTEXTO DO PLANO FINANCEIRO 2026 (use para contextualizar a análise):
- Meta principal: juntar R$ 30.000 até dezembro/2026 + vender carro atual por R$ 10k = comprar carro à vista
- Divisão ideal da sobra mensal: R$ 3.333 para reserva do carro (CDB liquidez diária XP) + restante para carteira de investimentos
- Carteira XP recomendada: 30% Tesouro Selic, 25% CDB, 15% LCI/LCA, 20% IVVB11, 10% GOLD11
- Roadmap R$1M: aportar R$ 2.500/mês a partir de jan/2027 (após comprar o carro)
- Regra de ouro: aporte sai no dia 5, antes de qualquer gasto. Não tocar na reserva do carro.

Com base no saldo deste mês, comente se o Bruno está no ritmo para bater a meta do carro.
Seja específico com os números. Dê pelo menos 1 recomendação prática alinhada ao plano."""

    ant_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if ant_key:
        try:
            client = _anthropic.Anthropic(api_key=ant_key)
            msg = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            analise = msg.content[0].text
            brain.salvar(
                modulo="Financeiro",
                titulo=f"Análise financeira {mes}",
                inputs={
                    "mes": mes,
                    "receita": receita,
                    "despesas": despesas,
                    "saldo": saldo,
                    "receita_anterior": receita_ant,
                    "despesas_anteriores": desp_ant,
                },
                output=analise,
                model="claude-sonnet-4-5",
            )
            return jsonify({"analise": analise})
        except Exception as e:
            pass

    if openai_key:
        try:
            client = OpenAI(api_key=openai_key)
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            analise = resp.choices[0].message.content
            brain.salvar(
                modulo="Financeiro",
                titulo=f"Análise financeira {mes}",
                inputs={
                    "mes": mes,
                    "receita": receita,
                    "despesas": despesas,
                    "saldo": saldo,
                    "receita_anterior": receita_ant,
                    "despesas_anteriores": desp_ant,
                },
                output=analise,
                model="gpt-4o",
            )
            return jsonify({"analise": analise})
        except Exception as e:
            pass

    # Fallback local
    saldo_emoji = "✅" if saldo >= 0 else "⚠️"
    taxa = (despesas / receita * 100) if receita else 0
    analise = (
        f"{saldo_emoji} Em <strong>{mes}</strong>, você faturou <strong>R$ {receita:,.2f}</strong> "
        f"e gastou <strong>R$ {despesas:,.2f}</strong>, resultando em saldo de "
        f"<strong>R$ {saldo:,.2f}</strong>. "
        f"Sua taxa de comprometimento foi de <strong>{taxa:.1f}%</strong> da receita."
    )
    return jsonify({"analise": analise})


# ── Financeiro: CRUD Transações ──────────────────────────────────────────────

@app.route("/api/financeiro/transacoes", methods=["GET"])
@login_required
def financeiro_listar_transacoes():
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute(
            "SELECT id, descricao, valor, tipo, categoria, recorrente, data::text "
            "FROM fin_transacoes ORDER BY data DESC"
        )
        rows = cur.fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/transacoes", methods=["POST"])
@login_required
def financeiro_criar_transacao():
    d = request.get_json() or {}
    for campo in ["descricao", "valor", "tipo", "categoria", "data"]:
        if not d.get(campo):
            return jsonify({"error": f"Campo obrigatório: {campo}"}), 400
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO fin_transacoes (descricao,valor,tipo,categoria,recorrente,data) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (d["descricao"], d["valor"], d["tipo"], d["categoria"],
             d.get("recorrente", False), d["data"])
        )
        novo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/transacoes/<int:tid>", methods=["PUT"])
@login_required
def financeiro_atualizar_transacao(tid):
    d = request.get_json() or {}
    campos_validos = ["descricao", "valor", "tipo", "categoria", "recorrente", "data"]
    campos = {k: v for k, v in d.items() if k in campos_validos}
    if not campos:
        return jsonify({"error": "Nenhum campo válido"}), 400
    try:
        conn = _get_db()
        cur  = conn.cursor()
        sets   = ", ".join(f"{k} = %s" for k in campos)
        valores = list(campos.values()) + [tid]
        cur.execute(f"UPDATE fin_transacoes SET {sets} WHERE id = %s", valores)
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/transacoes/<int:tid>", methods=["DELETE"])
@login_required
def financeiro_deletar_transacao(tid):
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("DELETE FROM fin_transacoes WHERE id = %s", (tid,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Financeiro: CRUD Raio-X ──────────────────────────────────────────────────

@app.route("/api/financeiro/raiox", methods=["GET"])
@login_required
def financeiro_get_raiox():
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("SELECT id, nome, grupo, valores FROM fin_raiox ORDER BY grupo, id")
        rows = cur.fetchall()
        conn.close()
        resultado = {"entradas": [], "fixas": [], "variaveis": []}
        for r in rows:
            resultado[r["grupo"]].append({
                "id": r["id"], "nome": r["nome"], "valores": r["valores"]
            })
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/raiox", methods=["PUT"])
@login_required
def financeiro_salvar_raiox():
    d = request.get_json() or {}
    try:
        conn = _get_db()
        cur  = conn.cursor()
        if not d:
            return jsonify({"error": "Payload vazio"}), 400
        cur.execute("DELETE FROM fin_raiox")
        for grupo in ["entradas", "fixas", "variaveis"]:
            for item in d.get(grupo, []):
                cur.execute(
                    "INSERT INTO fin_raiox (nome, grupo, valores) VALUES (%s, %s, %s)",
                    (item["nome"], grupo, json.dumps(item["valores"]))
                )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Financeiro: Aportes de Investimento ──────────────────────────────────────

_ATIVOS_VALIDOS = {"tesouro_selic", "cdb", "lci_lca", "ivvb11", "gold11"}


@app.route("/api/financeiro/aportes", methods=["GET"])
@login_required
def financeiro_listar_aportes():
    try:
        conn = _get_db()
        try:
            cur  = conn.cursor()
            cur.execute("""
                SELECT id, mes_ano::text, ativo, valor
                FROM aportes_investimento
                ORDER BY mes_ano DESC, id DESC
            """)
            rows = cur.fetchall()
        finally:
            conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/aportes", methods=["POST"])
@login_required
def financeiro_criar_aporte():
    d = request.get_json(force=True) or {}
    mes_ano = d.get("mes_ano")
    ativo   = d.get("ativo")
    valor   = d.get("valor")
    if not mes_ano:
        return jsonify({"error": "mes_ano obrigatório"}), 400
    if ativo not in _ATIVOS_VALIDOS and not ativo.startswith('custom_'):
        return jsonify({"error": f"ativo inválido: {ativo}"}), 400
    if ativo.startswith('custom_'):
        try:
            _conn = _get_db()
            try:
                _cur = _conn.cursor()
                _cur.execute("SELECT key FROM ativos_personalizados WHERE key = %s", (ativo,))
                if not _cur.fetchone():
                    return jsonify({"error": f"ativo inválido: {ativo}"}), 400
            finally:
                _conn.close()
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    try:
        valor = float(valor)
        if valor <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "valor deve ser > 0"}), 400
    try:
        conn = _get_db()
        try:
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO aportes_investimento (mes_ano, ativo, valor)
                VALUES (DATE_TRUNC('month', %s::date), %s, %s)
                RETURNING id
            """, (mes_ano, ativo, valor))
            novo_id = cur.fetchone()["id"]
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True, "id": novo_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/aportes/<int:aid>", methods=["DELETE"])
@login_required
def financeiro_deletar_aporte(aid):
    try:
        conn = _get_db()
        try:
            cur  = conn.cursor()
            cur.execute("DELETE FROM aportes_investimento WHERE id = %s", (aid,))
            conn.commit()
            rowcount = cur.rowcount
        finally:
            conn.close()
        if rowcount == 0:
            return jsonify({"error": "not found"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Financeiro: Ativos Personalizados ────────────────────────────────────────

_ATIVOS_FIXOS = [
    {"key": "tesouro_selic", "label": "Tesouro Selic", "cor": "#00e5ff", "meta": 30},
    {"key": "cdb",           "label": "CDB",           "cor": "#ffd740", "meta": 25},
    {"key": "lci_lca",       "label": "LCI/LCA",       "cor": "#69f0ae", "meta": 15},
    {"key": "ivvb11",        "label": "IVVB11",         "cor": "#ff5252", "meta": 20},
    {"key": "gold11",        "label": "GOLD11",         "cor": "#7c4dff", "meta": 10},
]
_KEYS_FIXAS   = {a["key"] for a in _ATIVOS_FIXOS}
_PALETA_CUSTOM = ['#ff8a65', '#ce93d8', '#80deea', '#a5d6a7', '#ffcc02', '#ef9a9a']


def _gerar_key_ativo(label):
    import re
    slug = re.sub(r'[^a-z0-9 ]', '', label.lower().strip())
    slug = re.sub(r'\s+', '_', slug).strip('_')
    return ('custom_' + slug)[:50]


@app.route("/api/financeiro/ativos", methods=["GET"])
@login_required
def financeiro_listar_ativos():
    try:
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT key, label, cor, meta FROM ativos_personalizados ORDER BY id ASC")
            rows = cur.fetchall()
        finally:
            conn.close()
        result = [{**a, "fixo": True} for a in _ATIVOS_FIXOS]
        result += [{"key": r["key"], "label": r["label"], "cor": r["cor"],
                    "meta": float(r["meta"]), "fixo": False} for r in rows]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/ativos", methods=["POST"])
@login_required
def financeiro_criar_ativo():
    d     = request.get_json(force=True) or {}
    label = (d.get("label") or "").strip()
    if not label:
        return jsonify({"error": "label obrigatório"}), 400
    if len(label) > 100:
        return jsonify({"error": "label muito longo (máx 100)"}), 400
    try:
        meta = float(d.get("meta") or 0)
        if not (0 <= meta <= 100):
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "meta deve ser entre 0 e 100"}), 400
    key = _gerar_key_ativo(label)
    if key in _KEYS_FIXAS:
        return jsonify({"error": f"Ativo com nome similar já existe (key: {key})"}), 400
    try:
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS n FROM ativos_personalizados")
            n = cur.fetchone()["n"]
            cor = _PALETA_CUSTOM[int(n) % len(_PALETA_CUSTOM)]
            cur.execute("""
                INSERT INTO ativos_personalizados (key, label, cor, meta)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (key) DO NOTHING
                RETURNING id
            """, (key, label, cor, meta))
            row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()
        if not row:
            return jsonify({"error": f"Ativo com nome similar já existe (key: {key})"}), 400
        ativo = {"key": key, "label": label, "cor": cor, "meta": meta, "fixo": False}
        return jsonify({"ok": True, "ativo": ativo})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/ativos/<string:key>", methods=["DELETE"])
@login_required
def financeiro_deletar_ativo(key):
    if key in _KEYS_FIXAS:
        return jsonify({"error": "ativo fixo não pode ser removido"}), 400
    try:
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM ativos_personalizados WHERE key = %s", (key,))
            conn.commit()
            rowcount = cur.rowcount
        finally:
            conn.close()
        if rowcount == 0:
            return jsonify({"error": "not found"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: Site Architect — geração de landing page ─────────────────────────────

_SITE_ARCH_SYSTEM = """\
Você é um Site Architect especialista em landing pages de alta conversão.

OBJETIVO:
- Receber uma URL de referência (layout base) e o contexto de negócio do usuário.
- Entregar UMA landing page completa, em HTML + TailwindCSS, moderna, responsiva e limpa.
- Manter a estrutura de seções da referência (Hero, Benefícios, Prova Social, FAQ, Rodapé),
  mas SEM copiar código ou textos literalmente.

REGRAS:
1. Use SOMENTE TailwindCSS (classes utilitárias) — não use CSS em <style>.
2. Não importe fontes externas; use system fonts (font-sans).
3. Estrutura básica:
   <html lang="pt-BR">
     <head> (meta + título + link Tailwind via CDN)
     <body class="bg-slate-950 text-slate-50 ..."> ... </body>
   </html>
4. Seções mínimas:
   - Hero com headline forte, subheadline e call-to-action.
   - Seção de benefícios / features.
   - Seção de prova social (depoimentos, métricas ou logos).
   - Seção de FAQ.
   - Rodapé simples.
5. Substitua completamente qualquer texto da referência pela copy do usuário (hero_copy, extra_copy, contexto).
6. Nunca use textos genéricos como "Lorem ipsum".
7. Saída: retorne APENAS o HTML final, pronto para ser salvo como index.html.
"""


def _save_data_url_image(kind: str, data_url: str, index: int | None = None) -> str | None:
    """
    Salva uma imagem enviada como data URL em static/uploads/architect
    e retorna a URL pública (/static/...).
    """
    if not data_url or not isinstance(data_url, str) or "," not in data_url:
        return None
    try:
        header, b64 = data_url.split(",", 1)
        mime = "image/png"
        if header.startswith("data:") and ";base64" in header:
            mime = header[5:header.index(";base64")] or "image/png"
        ext = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }.get(mime, "png")

        # Garante diretório
        base_dir = os.path.join(app.static_folder, "uploads", "architect")
        os.makedirs(base_dir, exist_ok=True)

        suffix = f"_{index}" if index is not None else ""
        filename = f"{int(time.time())}_{kind}{suffix}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(base_dir, filename)

        with open(filepath, "wb") as f:
            f.write(base64.b64decode(b64))

        # Caminho público
        return f"/static/uploads/architect/{filename}"
    except Exception:
        return None


def _anthropic_client_46():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return _anthropic.Anthropic(api_key=key) if key else None


@app.route("/api/site-architect/generate", methods=["POST"])
@login_required
def api_site_arch_generate():
    """
    Gera uma landing page completa (HTML+Tailwind) a partir de:
    - URL de referência (para entender seções)
    - contexto de negócio e copy
    - metadados de assets (logo/hero/gallery) em data URLs (opcionais)
    """
    data = request.get_json(force=True) or {}
    ref_url = (data.get("reference_url") or "").strip()
    contexto = (data.get("business_context") or "").strip()
    hero_copy = (data.get("hero_copy") or "").strip()
    extra_copy = (data.get("extra_copy") or "").strip()
    template_kind = (data.get("template_kind") or "").strip() or "lead"
    assets = data.get("assets") or {}

    if not any((ref_url, contexto, hero_copy)):
        return jsonify({"error": "Preencha pelo menos URL de referência, contexto ou hero copy."}), 400

    client = _anthropic_client_46()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada para o Site Architect."}), 500

    template_hints = {
        "lead": (
            "Tipo de página: CAPTURA DE LEADS.\n"
            "Foque em formulário ou botão de WhatsApp como ação principal, promessa forte no hero, "
            "seção de benefícios enxuta e prova social objetiva.\n"
        ),
        "lancamento": (
            "Tipo de página: LANÇAMENTO / FUNIL.\n"
            "Inclua seções claras de promessa, prova social forte, módulo para detalhes do evento/curso, "
            "bônus e garantia. Crie sensação de urgência real e estrutura pensando em tráfego frio/morno.\n"
        ),
        "servico-local": (
            "Tipo de página: SERVIÇO LOCAL.\n"
            "Destaque endereço/região atendida, fotos do espaço, depoimentos locais, mapa ou instruções de "
            "como chegar e foco em agendamento (botão de WhatsApp ou telefone visível o tempo todo).\n"
        ),
        "saas": (
            "Tipo de página: SOFTWARE / SAAS.\n"
            "Use blocos de features claros, captura de e-mail para teste grátis, comparativo rápido com "
            "a forma antiga de fazer, seção de pricing simples e prova social com logos/métricas.\n"
        ),
        "ecommerce": (
            "Tipo de página: E‑COMMERCE SIMPLES (1 PRODUTO).\n"
            "Hero com foto forte do produto, benefícios em bullets, seção de detalhes/tabela, prova social "
            "com reviews e um bloco de perguntas frequentes focado em objeções de compra.\n"
        ),
    }
    template_hint = template_hints.get(template_kind, template_hints["lead"])

    # resumo textual + URLs dos assets
    logo_present = bool(assets.get("logo"))
    hero_present = bool(assets.get("hero"))
    gallery_list = assets.get("gallery") or []
    benefits_list = assets.get("benefits") or []
    social_list = assets.get("social") or []
    gallery_len = len(gallery_list)
    benefits_len = len(benefits_list)
    social_len = len(social_list)

    logo_url = _save_data_url_image("logo", assets.get("logo")) if logo_present else None
    hero_url = _save_data_url_image("hero", assets.get("hero")) if hero_present else None
    gallery_urls: list[str] = []
    for idx, item in enumerate(gallery_list[:6]):
        url = _save_data_url_image("gallery", item, index=idx + 1)
        if url:
            gallery_urls.append(url)

    benefits_urls: list[str] = []
    for idx, item in enumerate(benefits_list[:6]):
        url = _save_data_url_image("benefits", item, index=idx + 1)
        if url:
            benefits_urls.append(url)

    social_urls: list[str] = []
    for idx, item in enumerate(social_list[:6]):
        url = _save_data_url_image("social", item, index=idx + 1)
        if url:
            social_urls.append(url)

    assets_summary_lines = [
        "Resumo dos assets visuais disponíveis:",
        f"- Logotipo enviado: {'sim' if logo_present else 'não'}",
        f"- Banner principal enviado: {'sim' if hero_present else 'não'}",
        f"- Imagens de produto/serviço na galeria: {gallery_len}",
        f"- Imagens específicas para BENEFÍCIOS: {benefits_len}",
        f"- Imagens específicas para PROVA SOCIAL / RESULTADOS: {social_len}",
        "",
        "URLs de imagem já hospedadas (use-as diretamente nos elementos <img src=\"...\"> do HTML gerado, sem buscar imagens novas):",
        f"- LOGO_URL: {logo_url or '[nenhum logotipo enviado]'}",
        f"- HERO_URL: {hero_url or '[nenhum banner principal enviado]'}",
        "- GALLERY_URLS (use em cards/seção de produtos/serviços):",
    ]
    for u in gallery_urls:
        assets_summary_lines.append(f"  - {u}")
    assets_summary_lines.append("- BENEFITS_URLS (use como ícones/fotos na seção de Benefícios):")
    for u in benefits_urls:
        assets_summary_lines.append(f"  - {u}")
    assets_summary_lines.append("- SOCIAL_PROOF_URLS (use em depoimentos, prints de resultado, logos de clientes na seção de Prova Social):")
    for u in social_urls:
        assets_summary_lines.append(f"  - {u}")
    assets_summary_lines.append(
        "Orientação: se LOGO_URL existir, use-o no cabeçalho/nav da página. "
        "Se HERO_URL existir, use como imagem principal na seção Hero (banner do topo). "
        "Use GALLERY_URLS em cards ou grades na seção de produtos/serviços, BENEFITS_URLS na seção de benefícios "
        "e SOCIAL_PROOF_URLS na seção de prova social/resultados, sem inventar URLs adicionais."
    )
    assets_summary = "\n".join(assets_summary_lines)

    # Se tiver URL de referência, tentamos trazer o HTML bruto só para dar contexto estrutural ao modelo.
    reference_snippet = ""
    if ref_url:
        try:
            r = requests.get(ref_url, timeout=8)
            if r.ok:
                txt = r.text
                # Limitamos o HTML para não estourar contexto.
                reference_snippet = txt[:6000]
        except Exception:
            reference_snippet = ""

    user_instructions = "\n".join(
        [
            f"URL de referência (se disponível): {ref_url or 'não fornecida'}",
            "",
            template_hint,
            "",
            assets_summary,
            "",
            "HTML bruto (trecho) da referência, se carregado com sucesso:",
            reference_snippet or "[não carregado ou indisponível]",
            "",
            "Contexto do negócio:",
            contexto or "[não informado]",
            "",
            "Copy principal (Hero):",
            hero_copy or "[não informado]",
            "",
            "Outras informações relevantes (benefícios, provas, objeções etc.):",
            extra_copy or "[não informado]",
            "",
            "Gere agora o HTML completo seguindo as regras do sistema.",
        ]
    )

    try:
        ctx = brain.contexto(contexto[:80])
        system_prompt = _SITE_ARCH_SYSTEM
        if ctx:
            system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_instructions}],
        )
        html = (msg.content[0].text or "").strip()
        brain.salvar(
            modulo="Site Architect",
            titulo=f"Landing Page — {template_kind or 'custom'}",
            inputs={"business_context": contexto, "hero_copy": hero_copy, "template_kind": template_kind},
            output=html,
            model="claude-sonnet-4-6",
            cliente=contexto[:80],
        )
        return jsonify({"html": html})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/site-architect/refine", methods=["POST"])
@login_required
def api_site_arch_refine():
    """
    Recebe o HTML atual + uma instrução de chat e devolve
    uma nova versão do HTML com o ajuste aplicado.
    Ex.: "mude a cor dos botões para verde".
    """
    data = request.get_json(force=True) or {}
    instruction = (data.get("instruction") or "").strip()
    html = (data.get("html") or "").strip()
    if not html or not instruction:
        return jsonify({"error": "Envie 'html' e 'instruction'."}), 400

    client = _anthropic_client_46()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada para o Site Architect."}), 500

    refine_prompt = (
        "Você receberá o HTML atual de uma landing page e uma instrução de edição.\n"
        "Ajuste SOMENTE o necessário no HTML para cumprir a instrução, mantendo o resto intacto.\n"
        "Retorne apenas o novo HTML completo, sem explicações.\n\n"
        f"Instrução do usuário: {instruction}\n\n"
        "HTML atual:\n"
        f"{html}\n"
    )

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=_SITE_ARCH_SYSTEM,
            messages=[{"role": "user", "content": refine_prompt}],
        )
        new_html = (msg.content[0].text or "").strip()
        brain.salvar(
            modulo="Site Architect",
            titulo=f"Refinamento — {instruction[:50]}",
            inputs={"instrucao": instruction[:300] if instruction else ""},
            output=new_html,
            model="claude-sonnet-4-6",
        )
        return jsonify(
            {
                "html": new_html,
                "summary": f"Ajuste aplicado: {instruction}",
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/site-architect/export", methods=["POST"])
@login_required
def api_site_arch_export():
    """
    Exporta o HTML atual como um index.html pronto para deploy.

    A lógica de download é feita no front-end (Blob + link temporário),
    então aqui retornamos apenas JSON com o conteúdo.
    """
    data = request.get_json(force=True) or {}
    html = (data.get("html") or "").strip()
    if not html:
        return jsonify({"error": "Envie o HTML para exportação."}), 400
    return jsonify({"filename": "index.html", "html": html})


@app.route("/api/site-architect/export-react", methods=["POST"])
@login_required
def api_site_arch_export_react():
    """
    Converte o HTML em um componente React simples (TSX) usando dangerouslySetInnerHTML.
    É a forma mais segura de preservar a estrutura Tailwind sem tentar "reactificar" tudo.
    """
    data = request.get_json(force=True) or {}
    html = (data.get("html") or "").strip()
    component_name_raw = (data.get("component_name") or "LandingGenerated").strip()
    if not html:
        return jsonify({"error": "Envie o HTML para exportação React."}), 400

    # Sanitiza nome do componente para PascalCase
    safe_name = "".join(ch if ch.isalnum() else " " for ch in component_name_raw).title().replace(" ", "")
    if not safe_name:
        safe_name = "LandingGenerated"

    # Escapa caracteres problemáticos dentro do template string
    esc_html = html.replace("`", "\\`").replace("${", "\\${")

    code = f"""import React from "react";

type Props = {{
  // Você pode passar props aqui no futuro se quiser tornar a landing dinâmica
}};

const {safe_name}: React.FC<Props> = () => {{
  return (
    <div
      dangerouslySetInnerHTML={{{{{ __html: `{esc_html}` }}}}}
    />
  );
}};

export default {safe_name};
"""
    filename = f"{safe_name}.tsx"
    return jsonify({"filename": filename, "code": code})


def _deploy_to_vercel(project_name: str, index_html: str) -> tuple[bool, str, dict]:
    """
    Esqueleto de integração com a API da Vercel.

    Fluxo esperado:
    1. Criar um deployment com 1 arquivo (index.html) via API REST:
       POST https://api.vercel.com/v13/deployments
       Headers:
         - Authorization: Bearer VERCEL_TOKEN
         - Content-Type: application/json
       Body (simplificado):
         {
           "name": "<project_name>",
           "files": [{ "file": "index.html", "data": "<conteúdo do HTML>" }],
           "projectSettings": { "framework": "static" }
         }
    2. A Vercel devolve a URL do preview e, se o projeto estiver conectado a um domínio,
       também o domínio final.
    """
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token:
        return (
            False,
            "Configure VERCEL_TOKEN no .env para publicar automaticamente.",
            {},
        )
    payload = {
        "name": project_name or "jake-architect-site",
        "files": [
            {
                "file": "index.html",
                "data": index_html,
            }
        ],
        "projectSettings": {
            "framework": "static",
        },
    }
    try:
        r = requests.post(
            "https://api.vercel.com/v13/deployments",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=40,
        )
        if not r.ok:
            try:
                err = r.json()
            except Exception:
                err = {"error": r.text}
            return False, f"Vercel API {r.status_code}: {err.get('error') or err}", err
        data = r.json()
        url = data.get("url")
        inspector = data.get("inspectorUrl") or f"https://vercel.com/{url}" if url else ""
        return True, url or inspector or "Deploy criado.", data
    except Exception as exc:
        return False, f"Falha na chamada para a Vercel: {exc}", {}


@app.route("/api/site-architect/deploy", methods=["POST"])
@login_required
def api_site_arch_deploy():
    """
    Cria um deploy estático na Vercel com base em um index.html.

    - Requer VERCEL_TOKEN no .env.
    - project_name é opcional (usa um nome padrão quando vazio).
    """
    data = request.get_json(force=True) or {}
    html = (data.get("html") or "").strip()
    project_name = (data.get("project_name") or "jake-architect-site").strip()
    if not html:
        return jsonify({"error": "Envie o HTML para publicar."}), 400

    ok, msg, extra = _deploy_to_vercel(project_name, html)
    if not ok:
        hint = (
            "Você pode exportar o index.html e subir manualmente na Vercel "
            "caso prefira configurar o projeto pelo painel web."
        )
        return jsonify({"error": msg, "hint": hint}), 502

    return jsonify(
        {
            "message": "Deploy criado com sucesso.",
            "url": extra.get("url"),
            "inspectorUrl": extra.get("inspectorUrl"),
            "project": project_name,
        }
    )



# ══════════════════════════════════════════════════════════════════════════
#  ABA SUBIR ANÚNCIOS — CRUD de perfis de clientes
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/anuncios/clientes", methods=["GET"])
@login_required
def anuncios_listar_clientes():
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, nome, agencia, account_id, token_key, page_id, whatsapp,
                   segmento, campanha_tipo, localizacao_json, publico_json,
                   orcamento_diario, campanha_id_existente
            FROM ad_client_profiles ORDER BY agencia, nome
        """)
        rows = cur.fetchall()
        conn.close()
        return jsonify({"clientes": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/clientes", methods=["POST"])
@login_required
def anuncios_criar_cliente():
    d = request.get_json() or {}
    obrigatorios = ["nome", "agencia", "account_id", "token_key", "localizacao_json"]
    faltando = [f for f in obrigatorios if not d.get(f)]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios: {faltando}"}), 400
    if d["token_key"] not in _VALID_TOKEN_KEYS:
        return jsonify({"error": f"token_key inválido. Válidos: {list(_VALID_TOKEN_KEYS)}"}), 400
    if d["agencia"] not in ("piloti", "dentto", "freelance"):
        return jsonify({"error": "agencia deve ser piloti, dentto ou freelance"}), 400

    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO ad_client_profiles
                (nome, agencia, account_id, token_key, page_id, whatsapp, segmento,
                 campanha_tipo, localizacao_json, publico_json, orcamento_diario,
                 campanha_id_existente)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            d["nome"], d["agencia"], d["account_id"], d["token_key"],
            d.get("page_id"), d.get("whatsapp"), d.get("segmento"),
            d.get("campanha_tipo", "MESSAGES"),
            json.dumps(d["localizacao_json"]),
            json.dumps(d.get("publico_json") or {}),
            d.get("orcamento_diario"), d.get("campanha_id_existente")
        ))
        novo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/clientes/<int:cid>", methods=["PUT"])
@login_required
def anuncios_atualizar_cliente(cid):
    d = request.get_json() or {}
    if "token_key" in d and d["token_key"] not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400

    campos, valores = [], []
    mapa = {
        "nome": "nome", "agencia": "agencia", "account_id": "account_id",
        "token_key": "token_key", "page_id": "page_id", "whatsapp": "whatsapp",
        "segmento": "segmento", "campanha_tipo": "campanha_tipo",
        "orcamento_diario": "orcamento_diario", "campanha_id_existente": "campanha_id_existente"
    }
    for k, col in mapa.items():
        if k in d:
            campos.append(f"{col} = %s")
            valores.append(d[k])
    for jk in ("localizacao_json", "publico_json"):
        if jk in d:
            campos.append(f"{jk} = %s")
            valores.append(json.dumps(d[jk]))
    if not campos:
        return jsonify({"error": "Nenhum campo para atualizar"}), 400

    campos.append("atualizado_em = NOW()")
    valores.append(cid)
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute(f"UPDATE ad_client_profiles SET {', '.join(campos)} WHERE id = %s", valores)
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/clientes/<int:cid>", methods=["DELETE"])
@login_required
def anuncios_deletar_cliente(cid):
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("DELETE FROM ad_client_profiles WHERE id = %s", (cid,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
#  ABA SUBIR ANÚNCIOS — Meta API (campanhas, upload, copy, publicar)
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/anuncios/campanhas/<account_id>")
@login_required
def anuncios_listar_campanhas(account_id):
    token_key = request.args.get("token_key", "META_ACCESS_TOKEN")
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500
    try:
        campanhas = _meta_api.listar_campanhas(token, account_id)
        return jsonify({"campanhas": campanhas})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/upload-criativo", methods=["POST"])
@login_required
def anuncios_upload_criativo():
    if "arquivo" not in request.files:
        return jsonify({"error": "Campo 'arquivo' ausente"}), 400
    arquivo    = request.files["arquivo"]
    account_id = request.form.get("account_id", "")
    token_key  = request.form.get("token_key", "META_ACCESS_TOKEN")
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    if not account_id:
        return jsonify({"error": "account_id obrigatório"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    filename   = arquivo.filename or "criativo"
    file_bytes = arquivo.read()
    mime       = arquivo.content_type or ""
    try:
        if "video" in mime or filename.lower().endswith(".mp4"):
            video_id = _meta_api.upload_video(token, account_id, file_bytes, filename)
            return jsonify({"tipo": "video", "video_id": video_id, "ok": True})
        else:
            resultado = _meta_api.upload_imagem(token, account_id, file_bytes, filename)
            return jsonify({"tipo": "imagem", "hash": resultado["hash"], "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/copy", methods=["POST"])
@login_required
def anuncios_gerar_copy():
    d            = request.get_json() or {}
    imagem_b64   = d.get("imagem_base64", "")
    mime_type    = d.get("mime_type", "image/jpeg")
    cliente_nome = d.get("cliente_nome", "cliente")
    camp_tipo    = d.get("campanha_tipo", "MESSAGES")
    segmento     = d.get("segmento", "")

    cta_sugerido = "SEND_MESSAGE" if camp_tipo == "MESSAGES" else "LEARN_MORE"
    objetivo_txt = "gerar mensagens no WhatsApp" if camp_tipo == "MESSAGES" else "gerar engajamento"

    system = (
        "Você é especialista em copywriting para anúncios do Facebook/Instagram. "
        "Crie copies curtas, diretas e persuasivas em português brasileiro. "
        "Retorne APENAS um JSON válido, sem markdown ou texto adicional."
    )
    prompt = (
        f"Analise este criativo de anúncio para '{cliente_nome}'"
        + (f" (segmento: {segmento})" if segmento else "")
        + f". Objetivo: {objetivo_txt}.\n"
        "Crie:\n"
        "- titulo: até 40 caracteres, chamativo\n"
        "- texto: até 125 caracteres, copy persuasiva\n"
        f"- cta: use exatamente '{cta_sugerido}'\n\n"
        'Responda APENAS com JSON: {"titulo":"...","texto":"...","cta":"..."}'
    )

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    try:
        ctx = brain.contexto(cliente_nome)
        if ctx:
            system = system + f"\n\n## Briefing do Cliente\n{ctx}"
        content = []
        if imagem_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime_type, "data": imagem_b64}
            })
        content.append({"type": "text", "text": prompt})

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": content}]
        )
        raw = msg.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json\n"):
                raw = raw[5:]
        resultado = json.loads(raw)
        brain.salvar(
            modulo="Anuncios",
            titulo=f"Copy {cliente_nome} — {camp_tipo}",
            inputs={"cliente_nome": cliente_nome, "camp_tipo": camp_tipo, "segmento": segmento},
            output=f"Título: {resultado.get('titulo')}\n\nTexto: {resultado.get('texto')}\n\nCTA: {resultado.get('cta')}",
            model="claude-sonnet-4-6",
            cliente=cliente_nome,
        )
        return jsonify(resultado)
    except json.JSONDecodeError:
        return jsonify({"error": "IA retornou formato inválido"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/publicar", methods=["POST"])
@login_required
def anuncios_publicar():
    d                 = request.get_json() or {}
    cliente_id        = d.get("cliente_id")
    campanha_exist_id = d.get("campanha_existente_id")
    campanha_nome     = d.get("campanha_nome", "Campanha Jake OS")
    orcamento         = float(d.get("orcamento_diario", 0))
    creative_ref      = d.get("creative_ref", {})
    copy_data         = d.get("copy", {})

    if not cliente_id:
        return jsonify({"error": "cliente_id obrigatório"}), 400
    if not creative_ref:
        return jsonify({"error": "creative_ref obrigatório"}), 400
    if not copy_data.get("titulo") or not copy_data.get("texto"):
        return jsonify({"error": "copy.titulo e copy.texto obrigatórios"}), 400

    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("SELECT * FROM ad_client_profiles WHERE id = %s", (cliente_id,))
        cliente = cur.fetchone()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar cliente: {e}"}), 500

    if not cliente:
        return jsonify({"error": "Cliente não encontrado"}), 404

    localizacao = cliente.get("localizacao_json") or {}
    tem_loc = localizacao and (localizacao.get("paises") or localizacao.get("cidades"))
    if not tem_loc:
        return jsonify({"error": "Localização não configurada — publicação bloqueada"}), 400

    page_id = cliente.get("page_id", "")
    if not page_id:
        return jsonify({"error": "page_id não configurado no perfil do cliente"}), 400

    token_key  = cliente["token_key"]
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token      = os.getenv(token_key, "")
    account_id = cliente["account_id"]
    camp_tipo  = cliente.get("campanha_tipo", "MESSAGES")
    publico    = cliente.get("publico_json") or {}

    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    campaign_id = adset_id = ad_id = None
    try:
        if campanha_exist_id:
            campaign_id = campanha_exist_id
        else:
            cbo = camp_tipo == "MESSAGES"
            campaign_id = _meta_api.criar_campanha(
                token, account_id, camp_tipo, campanha_nome, orcamento, cbo=cbo
            )

        try:
            adset_id = _meta_api.criar_conjunto(
                token, account_id, campaign_id, camp_tipo, publico, localizacao,
                orcamento=(orcamento if camp_tipo == "ENGAGEMENT" else None)
            )
        except Exception as e2:
            if not campanha_exist_id:
                _meta_api.deletar_objeto_meta(token, campaign_id)
            raise Exception(f"Falha no conjunto (campanha removida): {e2}")

        try:
            ad_id = _meta_api.criar_anuncio(
                token, account_id, adset_id, page_id, creative_ref,
                copy_data["titulo"], copy_data["texto"],
                copy_data.get("cta", "SEND_MESSAGE")
            )
        except Exception as e3:
            _meta_api.deletar_objeto_meta(token, adset_id)
            if not campanha_exist_id:
                _meta_api.deletar_objeto_meta(token, campaign_id)
            raise Exception(f"Falha no anúncio (conjunto e campanha removidos): {e3}")

        try:
            conn = _get_db()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO ad_publish_log
                    (cliente_id, account_id, campaign_id, adset_id, ad_id, status, payload_json)
                VALUES (%s,%s,%s,%s,%s,'sucesso',%s)
            """, (cliente_id, account_id, campaign_id, adset_id, ad_id, json.dumps(d)))
            conn.commit()
            conn.close()
        except Exception:
            pass

        return jsonify({
            "ok": True,
            "campaign_id": campaign_id,
            "adset_id": adset_id,
            "ad_id": ad_id,
            "msg": "Anúncio criado com status PAUSADO. Ative no Gerenciador da Meta para publicar."
        })

    except Exception as e:
        try:
            conn = _get_db()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO ad_publish_log
                    (cliente_id, account_id, campaign_id, adset_id, ad_id, status, erro_msg, payload_json)
                VALUES (%s,%s,%s,%s,%s,'erro',%s,%s)
            """, (cliente_id, account_id, campaign_id, adset_id, ad_id, str(e), json.dumps(d)))
            conn.commit()
            conn.close()
        except Exception:
            pass
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
#  FÁBRICA DE CRIATIVOS v2
# ══════════════════════════════════════════════════════════════════════════
import math as _math

_CRIATIVOS_MODOS = {"anuncios", "criativo", "psicodelico", "pessoas", "cena"}

_CRIATIVOS_MODELOS_IMAGEM = {
    "flux-1.1-pro":     "black-forest-labs/flux-1.1-pro",
    "flux-dev":         "black-forest-labs/flux-dev",
    "recraft-v3":       "recraft-ai/recraft-v3",
    "ideogram-v3-turbo":"ideogram-ai/ideogram-v3-turbo",
    "imagen-4":         "google/imagen-4",
}

_CRIATIVOS_MODELOS_VIDEO = {
    "wan-t2v-fast":  ("wavespeedai/wan-2.2-t2v-480p", "t2v"),
    "wan-5b-fast":   ("wavespeedai/wan-2.2-t2v-720p", "t2v"),
    "hailuo-02":     ("minimax/hailuo-02",             "t2v"),
    "seedance-lite": ("bytedance/seedance-1-lite",     "t2v"),
    "runway-gen4":   ("runwayml/gen4-turbo",           "t2v"),
    "wan-i2v-fast":  ("wavespeedai/wan-2.2-i2v-480p", "i2v"),
}

# Taxa estimada em USD por segundo de GPU por modelo
_CUSTO_POR_SEGUNDO = {
    "wan-t2v-fast":  0.0030,
    "wan-5b-fast":   0.0050,
    "hailuo-02":     0.0080,
    "seedance-lite": 0.0035,
    "runway-gen4":   0.0200,
    "wan-i2v-fast":  0.0030,
}

_CRIATIVOS_SYSTEM_PROMPTS = {
    "anuncios": (
        "You are an expert commercial photographer and ad creative director specializing in Meta Ads and Google Ads. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: studio lighting, commercial photography style, trust-inspiring composition, clean backgrounds, "
        "specific camera/lens (Canon EOS R5, 85mm f/1.4), warm color grading. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "criativo": (
        "You are an expert creative director and editorial photographer. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: conceptual art, bold composition, editorial/National Geographic style, dynamic lighting, "
        "color contrast, visual narrative, storytelling. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "psicodelico": (
        "You are an expert AI artist specializing in psychedelic and surrealist visual art. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: fractal geometry, neon/vibrant colors, DMT-inspired visuals, kaleidoscope patterns, "
        "liquid geometry, cosmic themes, ultra-detailed, 8K resolution, surrealist dreamscape. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "pessoas": (
        "You are an expert portrait and fashion photographer. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: hyperrealistic skin texture, subsurface scattering, Rembrandt or natural window lighting, "
        "Canon EOS R5 85mm f/1.2, shallow depth of field, authentic candid expressions, photojournalism style. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "cena": (
        "You are an expert landscape and architectural photographer. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: cinematic wide angle (16mm), leading lines, volumetric light, golden hour, atmospheric haze, "
        "rule of thirds, long exposure, National Geographic / award-winning landscape style. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
}

_REPLICATE_BASE = "https://api.replicate.com/v1"


def _replicate_headers():
    token = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN não configurado no .env")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@app.route("/api/criativos/upload-imagem", methods=["POST"])
@login_required
def criativos_upload_imagem():
    if "arquivo" not in request.files:
        return jsonify({"error": "Campo 'arquivo' ausente"}), 400
    arquivo = request.files["arquivo"]
    file_bytes = arquivo.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        return jsonify({"error": "Arquivo muito grande. Limite: 10 MB"}), 413
    mime = arquivo.content_type or "image/jpeg"
    if mime not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        return jsonify({"error": "Tipo de arquivo não suportado. Use JPEG, PNG, WebP ou GIF"}), 415
    # base64 para análise via Claude
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    # Upload para Replicate Files API para uso como URL em I2V
    try:
        headers = _replicate_headers()
        headers.pop("Content-Type")  # multipart não usa Content-Type JSON
        resp = requests.post(
            f"{_REPLICATE_BASE}/files",
            headers={"Authorization": headers["Authorization"]},
            files={"content": (arquivo.filename or "upload", file_bytes, mime)},
            timeout=30,
        )
        if not resp.ok:
            return jsonify({"error": f"Replicate upload: {resp.text[:200]}"}), 500
        url = resp.json().get("urls", {}).get("get") or resp.json().get("url", "")
        return jsonify({"url": url, "base64": b64, "mime_type": mime, "ok": True})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


_CRIATIVOS_SYSTEM_PROMPT_KONTEXT = (
    "You are an expert in AI image editing. "
    "The user has a reference image and wants to modify it. "
    "Transform the user's simple request into a clear EDITING INSTRUCTION. "
    "Format: describe ONLY what should change, never the whole image. "
    "Use direct action verbs: 'Change', 'Replace', 'Remove', 'Add', 'Keep'. "
    "Always add: 'Keep the [unchanged elements] exactly the same.' "
    "Example output: 'Change the product label text to focus on postpartum women. "
    "Keep the product, lighting, background and composition exactly the same.' "
    "Maximum 2 sentences. Always in English."
)


@app.route("/api/criativos/expandir-prompt", methods=["POST"])
@login_required
def criativos_expandir_prompt():
    d = request.get_json() or {}
    prompt         = (d.get("prompt") or "").strip()
    modo           = d.get("modo", "criativo")
    tipo           = d.get("tipo", "imagem")
    tem_referencia = bool(d.get("tem_referencia", False))
    if not prompt:
        return jsonify({"error": "Campo 'prompt' obrigatório"}), 400
    if modo not in _CRIATIVOS_MODOS:
        return jsonify({"error": f"modo inválido. Válidos: {list(_CRIATIVOS_MODOS)}"}), 400

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    if tem_referencia:
        system = _CRIATIVOS_SYSTEM_PROMPT_KONTEXT
        user_msg = f"Transform this editing request into a Kontext instruction: {prompt}"
    else:
        tipo_hint = " Optimize for motion, camera movement, and temporal consistency." if tipo == "video" else ""
        system = _CRIATIVOS_SYSTEM_PROMPTS[modo] + tipo_hint
        user_msg = f"Expand this prompt: {prompt}"

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        prompt_expandido = msg.content[0].text.strip()
        brain.salvar(
            modulo="Criativos",
            titulo=f"Prompt expandido {modo} {tipo}" + (" [kontext]" if tem_referencia else ""),
            inputs={"prompt": prompt, "modo": modo, "tipo": tipo, "tem_referencia": tem_referencia},
            output=prompt_expandido,
            model="claude-sonnet-4-6",
        )
        return jsonify({"prompt_expandido": prompt_expandido})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/criativos/analisar-referencia", methods=["POST"])
@login_required
def criativos_analisar_referencia():
    d = request.get_json() or {}
    b64  = d.get("imagem_base64", "")
    mime = d.get("mime_type", "image/jpeg")
    if not b64:
        return jsonify({"error": "imagem_base64 obrigatório"}), 400

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    system = (
        "You are an expert visual analyst and prompt engineer. "
        "Analyze the image and return ONLY valid JSON with two fields: "
        "'prompt_sugerido' (English prompt 50-120 words to recreate this visual style) and "
        "'modo_sugerido' (one of: anuncios, criativo, psicodelico, pessoas, cena). "
        "No markdown, no explanation, just the JSON object."
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text",  "text": "Analyze this image and return the JSON."},
            ]}],
        )
        raw = msg.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json\n"):
                raw = raw[5:]
        result = json.loads(raw)
        # Validar modo_sugerido
        if result.get("modo_sugerido") not in _CRIATIVOS_MODOS:
            result["modo_sugerido"] = "criativo"
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({"error": "IA retornou formato inválido"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/criativos/gerar-imagem", methods=["POST"])
@login_required
def criativos_gerar_imagem():
    d = request.get_json() or {}
    prompt         = (d.get("prompt_expandido") or "").strip()
    modelo         = d.get("modelo", "flux-1.1-pro")
    imagem_url     = (d.get("imagem_url") or "").strip()
    tem_referencia = bool(d.get("tem_referencia", False))

    if not prompt:
        return jsonify({"error": "prompt_expandido obrigatório"}), 400

    # Modo Kontext: ignora o modelo enviado e usa flux-kontext-pro
    if tem_referencia and imagem_url:
        try:
            url = _generate_kontext(prompt, imagem_url, os.environ.get("REPLICATE_API_TOKEN", "").strip())
            brain.salvar(
                modulo="Criativos",
                titulo="Imagem editada flux-kontext-pro",
                inputs={"modelo": "flux-kontext-pro", "prompt": prompt, "input_image": imagem_url},
                output=url,
                model="flux-kontext-pro",
            )
            return jsonify({"url": url, "ok": True})
        except Exception as e:
            return jsonify({"error": f"Kontext Pro: {e}"}), 500

    if modelo not in _CRIATIVOS_MODELOS_IMAGEM:
        return jsonify({"error": f"modelo inválido. Válidos: {list(_CRIATIVOS_MODELOS_IMAGEM)}"}), 400

    slug = _CRIATIVOS_MODELOS_IMAGEM[modelo]
    try:
        headers = _replicate_headers()
        headers["Prefer"] = "wait=60"
        resp = requests.post(
            f"{_REPLICATE_BASE}/models/{slug}/predictions",
            headers=headers,
            json={"input": {"prompt": prompt, "aspect_ratio": "4:5",
                            "output_format": "webp", "output_quality": 90}},
            timeout=90,
        )
        if not resp.ok:
            return jsonify({"error": f"Replicate {resp.status_code}: {resp.text[:300]}"}), 500
        pred = resp.json()
        # Caminho síncrono (Prefer: wait)
        if pred.get("status") == "succeeded":
            out = pred.get("output")
            url = out[0] if isinstance(out, list) else out
            brain.salvar(
                modulo="Criativos",
                titulo=f"Imagem gerada {modelo}",
                inputs={"modelo": modelo, "prompt": prompt},
                output=url,
                model=modelo,
            )
            return jsonify({"url": url, "ok": True})
        # Fallback polling (raro)
        get_url = (pred.get("urls") or {}).get("get", "")
        hdrs = {"Authorization": headers["Authorization"]}
        for _ in range(20):
            time.sleep(3)
            p = requests.get(get_url, headers=hdrs, timeout=15).json()
            if p.get("status") == "succeeded":
                out = p.get("output")
                url = out[0] if isinstance(out, list) else out
                brain.salvar(
                    modulo="Criativos",
                    titulo=f"Imagem gerada {modelo}",
                    inputs={"modelo": modelo, "prompt": prompt},
                    output=url,
                    model=modelo,
                )
                return jsonify({"url": url, "ok": True})
            if p.get("status") == "failed":
                return jsonify({"error": p.get("error", "Geração falhou")}), 500
        return jsonify({"error": "Timeout na geração de imagem"}), 500
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/criativos/gerar-video", methods=["POST"])
@login_required
def criativos_gerar_video():
    d = request.get_json() or {}
    prompt     = (d.get("prompt_expandido") or "").strip()
    modelo     = d.get("modelo", "wan-t2v-fast")
    imagem_url = d.get("imagem_url")
    if not prompt:
        return jsonify({"error": "prompt_expandido obrigatório"}), 400
    if modelo not in _CRIATIVOS_MODELOS_VIDEO:
        return jsonify({"error": f"modelo inválido. Válidos: {list(_CRIATIVOS_MODELOS_VIDEO)}"}), 400

    slug, tipo = _CRIATIVOS_MODELOS_VIDEO[modelo]
    if tipo == "i2v" and not imagem_url:
        return jsonify({"error": "imagem_url obrigatório para modelos I2V"}), 400

    input_payload = {"prompt": prompt}
    if tipo == "i2v":
        input_payload["image"] = imagem_url

    try:
        headers = _replicate_headers()
        resp = requests.post(
            f"{_REPLICATE_BASE}/models/{slug}/predictions",
            headers=headers,
            json={"input": input_payload},
            timeout=30,
        )
        if not resp.ok:
            return jsonify({"error": f"Replicate {resp.status_code}: {resp.text[:300]}"}), 500
        pred = resp.json()
        prediction_id = pred.get("id")
        brain.salvar(
            modulo="Criativos",
            titulo=f"Vídeo iniciado {modelo}",
            inputs={"modelo": modelo, "prompt": prompt},
            output=f"prediction_id: {prediction_id}",
            model=modelo,
        )
        return jsonify({"prediction_id": prediction_id, "ok": True})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/criativos/status/<prediction_id>")
@login_required
def criativos_status(prediction_id):
    import re as _re
    if not _re.fullmatch(r'[a-zA-Z0-9]+', prediction_id or ''):
        return jsonify({"status": "failed", "error": "prediction_id inválido"}), 400
    try:
        headers = _replicate_headers()
        resp = requests.get(
            f"{_REPLICATE_BASE}/predictions/{prediction_id}",
            headers={"Authorization": headers["Authorization"]},
            timeout=15,
        )
        if not resp.ok:
            return jsonify({"status": "failed", "error": resp.text[:200]}), 500
        pred = resp.json()
        status = pred.get("status", "starting")
        url = None
        predict_time = None
        custo_usd = None
        if status == "succeeded":
            out = pred.get("output")
            url = out[0] if isinstance(out, list) else out
            metrics = pred.get("metrics") or {}
            predict_time = metrics.get("predict_time")
        return jsonify({
            "status": status,
            "url": url,
            "error": pred.get("error"),
            "predict_time": predict_time,
        })
    except RuntimeError as e:
        return jsonify({"status": "failed", "error": str(e)}), 500
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 500


@app.route("/api/criativos/pastas", methods=["GET"])
@login_required
def criativos_listar_pastas():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome, criado_em FROM creative_folders ORDER BY nome")
        rows = cur.fetchall()
        return jsonify({"pastas": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/criativos/pastas", methods=["POST"])
@login_required
def criativos_criar_pasta():
    d = request.get_json() or {}
    nome = (d.get("nome") or "").strip()
    if not nome:
        return jsonify({"error": "nome obrigatório"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO creative_folders (nome) VALUES (%s) RETURNING id", (nome,))
        novo_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/criativos/pastas/<int:pid>", methods=["DELETE"])
@login_required
def criativos_deletar_pasta(pid):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as n FROM creative_history WHERE folder_id = %s", (pid,))
        count = cur.fetchone()["n"]
        cur.execute("DELETE FROM creative_folders WHERE id = %s", (pid,))
        conn.commit()
        return jsonify({"ok": True, "criativos_desvinculados": count})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/criativos/historico", methods=["GET"])
@login_required
def criativos_listar_historico():
    folder_id = request.args.get("folder_id")
    tipo      = request.args.get("tipo")
    try:
        page  = max(1, int(request.args.get("page", 1)))
        limit = min(50, max(1, int(request.args.get("limit", 20))))
        if folder_id:
            folder_id = int(folder_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Parâmetros de paginação inválidos"}), 400
    offset    = (page - 1) * limit
    where, params = [], []
    if folder_id:
        where.append("folder_id = %s"); params.append(folder_id)
    if tipo in ("imagem", "video"):
        where.append("tipo = %s"); params.append(tipo)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as total FROM creative_history {where_sql}", params)
        total = cur.fetchone()["total"]
        cur.execute(
            f"SELECT id, tipo, modo, modelo, prompt_original, prompt_expandido, url_resultado, folder_id, criado_em "
            f"FROM creative_history {where_sql} ORDER BY criado_em DESC LIMIT %s OFFSET %s",
            params + [limit, offset]
        )
        items = [dict(r) for r in cur.fetchall()]
        return jsonify({"items": items, "total": total, "page": page, "pages": _math.ceil(total/limit) if total else 1})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/criativos/historico", methods=["POST"])
@login_required
def criativos_salvar_historico():
    d = request.get_json() or {}
    required = ["tipo", "modo", "modelo", "prompt_original", "prompt_expandido", "url_resultado"]
    missing = [f for f in required if not d.get(f)]
    if missing:
        return jsonify({"error": f"Campos obrigatórios: {missing}"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        predict_time = d.get("predict_time_s")
        custo_usd = None
        if predict_time and d.get("modelo") in _CUSTO_POR_SEGUNDO:
            custo_usd = round(predict_time * _CUSTO_POR_SEGUNDO[d["modelo"]], 4)
        cur.execute(
            "INSERT INTO creative_history (tipo,modo,modelo,prompt_original,prompt_expandido,url_resultado,folder_id,predict_time_s,custo_usd) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (d["tipo"], d["modo"], d["modelo"], d["prompt_original"],
             d["prompt_expandido"], d["url_resultado"], d.get("folder_id"),
             predict_time, custo_usd)
        )
        novo_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/criativos/custos")
@login_required
def criativos_custos():
    conn = _get_db()
    try:
        cur = conn.cursor()
        # Gasto total do mês atual
        cur.execute(
            "SELECT COALESCE(SUM(custo_usd),0) as total, COUNT(*) as geracoes "
            "FROM creative_history "
            "WHERE custo_usd IS NOT NULL "
            "AND DATE_TRUNC('month', criado_em) = DATE_TRUNC('month', NOW())"
        )
        mes = cur.fetchone()
        # Últimas 20 gerações com custo registrado
        cur.execute(
            "SELECT modelo, prompt_original, predict_time_s, custo_usd, criado_em::text "
            "FROM creative_history "
            "WHERE custo_usd IS NOT NULL "
            "ORDER BY criado_em DESC LIMIT 20"
        )
        historico = [dict(r) for r in cur.fetchall()]
        return jsonify({
            "mes_total_usd": float(mes["total"]),
            "mes_geracoes": int(mes["geracoes"]),
            "historico": historico,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/criativos/historico/<int:hid>", methods=["DELETE"])
@login_required
def criativos_deletar_historico(hid):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM creative_history WHERE id = %s", (hid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/criativos/historico/<int:hid>/pasta", methods=["PATCH"])
@login_required
def criativos_mover_pasta(hid):
    d = request.get_json() or {}
    folder_id = d.get("folder_id")  # pode ser None para "sem pasta"
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE creative_history SET folder_id = %s WHERE id = %s", (folder_id, hid))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


def _open_browser_delayed(port, delay=2):
    time.sleep(delay)
    webbrowser.open(f"http://localhost:{port}")

@app.route("/api/rotina/hoje", methods=["GET"])
@login_required
def rotina_hoje():
    from datetime import date
    today = date.today().isoformat()
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM habits WHERE active = TRUE ORDER BY category, id")
        habits = list(cur.fetchall())
        if not habits:
            return jsonify([])
        ids = [h["id"] for h in habits]
        cur.execute(
            "SELECT habit_id, completed FROM habit_logs WHERE date = %s AND habit_id = ANY(%s)",
            (today, ids)
        )
        logs = {r["habit_id"]: r["completed"] for r in cur.fetchall()}
        cur.execute(
            "SELECT habit_id, current_streak, best_streak FROM streaks WHERE habit_id = ANY(%s)",
            (ids,)
        )
        streaks = {r["habit_id"]: r for r in cur.fetchall()}
        result = []
        for h in habits:
            hid = h["id"]
            result.append({
                "id": hid,
                "name": h["name"],
                "category": h["category"],
                "icon": h["icon"],
                "completed": logs.get(hid, False),
                "current_streak": streaks.get(hid, {}).get("current_streak", 0),
                "best_streak": streaks.get(hid, {}).get("best_streak", 0),
            })
        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/rotina/check", methods=["POST"])
@login_required
def rotina_check():
    from datetime import date, timedelta
    data = request.get_json()
    habit_id = data.get("habit_id")
    if not habit_id:
        return jsonify({"error": "habit_id required"}), 400
    log_date = data.get("date", date.today().isoformat())
    completed = data.get("completed", True)
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO habit_logs (habit_id, date, completed)
            VALUES (%s, %s, %s)
            ON CONFLICT (habit_id, date) DO UPDATE SET completed = EXCLUDED.completed
        """, (habit_id, log_date, completed))
        cur.execute("""
            SELECT date FROM habit_logs
            WHERE habit_id = %s AND completed = TRUE
            ORDER BY date DESC
        """, (habit_id,))
        rows = [r["date"] for r in cur.fetchall()]
        current_streak = 0
        if rows:
            check = date.today()
            for d in rows:
                if d >= check - timedelta(days=1):
                    current_streak += 1
                    check = d
                else:
                    break
        cur.execute("""
            INSERT INTO streaks (habit_id, current_streak, best_streak, last_updated)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (habit_id) DO UPDATE SET
                current_streak = EXCLUDED.current_streak,
                best_streak = GREATEST(streaks.best_streak, EXCLUDED.current_streak),
                last_updated = EXCLUDED.last_updated
        """, (habit_id, current_streak, current_streak, date.today().isoformat()))
        conn.commit()
        return jsonify({"ok": True, "current_streak": current_streak})
    finally:
        conn.close()


@app.route("/api/rotina/streaks", methods=["GET"])
@login_required
def rotina_streaks():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT h.id, h.name, h.icon, h.category,
                   COALESCE(s.current_streak, 0) as current_streak,
                   COALESCE(s.best_streak, 0) as best_streak
            FROM habits h
            LEFT JOIN streaks s ON s.habit_id = h.id
            WHERE h.active = TRUE
            ORDER BY s.current_streak DESC NULLS LAST
        """)
        return jsonify(list(cur.fetchall()))
    finally:
        conn.close()


@app.route("/api/rotina/semana", methods=["GET"])
@login_required
def rotina_semana():
    from datetime import date, timedelta
    today = date.today()
    days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT date::text, COUNT(*) FILTER (WHERE completed = TRUE) as done,
                   COUNT(*) as total
            FROM habit_logs
            WHERE date = ANY(%s)
            GROUP BY date ORDER BY date
        """, (days,))
        logs = {r["date"]: {"done": r["done"], "total": r["total"]} for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) as c FROM habits WHERE active = TRUE")
        total_habits = cur.fetchone()["c"]
        result = []
        for d in days:
            result.append({
                "date": d,
                "done": logs.get(d, {}).get("done", 0),
                "total": total_habits,
            })
        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/rotina/maconha", methods=["POST"])
@login_required
def rotina_maconha_post():
    from datetime import date
    data = request.get_json()
    log_date = data.get("date", date.today().isoformat())
    period = data.get("period", "noite")
    if period not in ("dia", "noite"):
        return jsonify({"error": "period must be 'dia' or 'noite'"}), 400
    used = data.get("used", True)
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO maconha_log (date, used, period)
            VALUES (%s, %s, %s)
            ON CONFLICT (date, period) DO UPDATE SET used = EXCLUDED.used
        """, (log_date, used, period))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/rotina/maconha/mes", methods=["GET"])
@login_required
def rotina_maconha_mes():
    from datetime import date
    today = date.today()
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT date::text, period, used FROM maconha_log
            WHERE EXTRACT(MONTH FROM date) = %s AND EXTRACT(YEAR FROM date) = %s
            ORDER BY date DESC
        """, (today.month, today.year))
        return jsonify(list(cur.fetchall()))
    finally:
        conn.close()


# ── Social Brief — helpers de coleta ────────────────────────────────────────

def _sb_buscar_meta_ads(meta_account_id, meta_agency="piloti"):
    """
    Busca top 10 criativos por CTR na última semana via Meta Ads API.
    Retorna dict com 'periodo', 'criativos', 'resumo'.
    """
    import re as _re_meta
    if not meta_account_id or not _re_meta.match(r'^act_\d+$', meta_account_id):
        return {"erro": "meta_account_id inválido", "criativos": [], "resumo": {}}

    token_fn = _META_TOKENS.get(meta_agency)
    if not token_fn:
        return {"erro": f"Agência '{meta_agency}' não configurada", "criativos": [], "resumo": {}}
    token = token_fn()
    if not token:
        return {"erro": "Token Meta não configurado", "criativos": [], "resumo": {}}

    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{meta_account_id}/ads",
            params={
                "fields": (
                    "id,name,"
                    "creative{id,name,thumbnail_url,body,title,call_to_action_type},"
                    "insights.date_preset(last_7d)"
                    "{impressions,clicks,ctr,spend,cpm,actions,cost_per_action_type}"
                ),
                "limit": 50,
                "access_token": token,
            },
            timeout=20,
        )
        if not r.ok:
            err = r.json().get("error", {})
            return {"erro": err.get("message", f"Meta API {r.status_code}"), "criativos": [], "resumo": {}}

        ads_raw = r.json().get("data", [])
        criativos = []

        def _find_act(arr, *types):
            for e in arr:
                if e.get("action_type") in types:
                    try:
                        return float(e.get("value", 0) or 0)
                    except Exception:
                        return 0.0
            return 0.0

        for ad in ads_raw:
            insights_data = ad.get("insights", {}).get("data", [])
            if not insights_data:
                continue
            ins = insights_data[0]
            ctr = float(ins.get("ctr") or 0)
            cliques = int(ins.get("clicks") or 0)
            impressoes = int(ins.get("impressions") or 0)
            gasto = float(ins.get("spend") or 0)

            actions = ins.get("actions") or []
            costs = ins.get("cost_per_action_type") or []

            leads = _find_act(
                actions,
                "onsite_conversion.messaging_conversation_started_7d",
                "messaging_message_sends",
                "onsite_conversion.total_messaging_connection",
                "lead",
            )
            cpl = _find_act(
                costs,
                "onsite_conversion.messaging_conversation_started_7d",
                "messaging_message_sends",
                "lead",
            )

            creative = ad.get("creative") or {}
            criativo_nome = creative.get("name") or ad.get("name", "")
            criativo_body = creative.get("body") or creative.get("title") or ""
            criativos.append({
                "id": ad.get("id", ""),
                "nome": criativo_nome,
                "body": criativo_body[:120] if criativo_body else "",
                "thumbnail_url": creative.get("thumbnail_url", ""),
                "ctr": round(ctr, 2),
                "cliques": cliques,
                "impressoes": impressoes,
                "gasto": round(gasto, 2),
                "cpl": round(cpl, 2),
                "leads": int(leads),
                "tipo_campanha": creative.get("call_to_action_type", ""),
            })

        criativos.sort(key=lambda x: x["ctr"], reverse=True)
        criativos = criativos[:10]

        total_gasto = sum(c["gasto"] for c in criativos)
        total_leads = int(sum(c["leads"] for c in criativos))
        media_ctr = round(sum(c["ctr"] for c in criativos) / len(criativos), 2) if criativos else 0

        from datetime import date as _date_meta, timedelta as _td_meta
        hoje = _date_meta.today()
        inicio = (hoje - _td_meta(days=7)).isoformat()
        fim = hoje.isoformat()

        return {
            "periodo": {"inicio": inicio, "fim": fim},
            "criativos": criativos,
            "resumo": {
                "total_gasto": round(total_gasto, 2),
                "total_leads": total_leads,
                "media_ctr": media_ctr,
                "melhor_criativo": criativos[0] if criativos else {},
                "pior_criativo": criativos[-1] if criativos else {},
            }
        }
    except Exception as e:
        return {"erro": str(e), "criativos": [], "resumo": {}}


def _sb_buscar_concorrentes(nicho, concorrentes):
    """
    Pesquisa concorrentes via DuckDuckGo.
    Retorna dict com 'conteudo_pesquisa'.
    """
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        from datetime import date as _dc
        ano = _dc.today().year
        resultados = []
        queries = []
        for conc in (concorrentes or [])[:3]:
            queries.append(f"{conc} Instagram anúncios tráfego pago")
        queries.append(f"{nicho} tráfego pago criativos {ano}")
        queries.append(f"{nicho} hooks copy anúncios Meta Ads")

        with DDGS() as ddg:
            for query in queries:
                try:
                    res = list(ddg.text(query, max_results=3))
                    for r in res:
                        resultados.append(f"[{query}] {r.get('title','')} — {r.get('body','')}")
                except Exception:
                    pass

        return {"conteudo_pesquisa": "\n".join(resultados[:20])}
    except Exception as e:
        return {"conteudo_pesquisa": f"Erro na pesquisa: {e}"}


def _sb_ler_perfil_html(slug):
    """
    Tenta ler arquivo HTML de análise do cliente em static/reports/{slug}_relatorio.html.
    Extrai texto via BeautifulSoup. Retorna string vazia se não encontrar.
    """
    try:
        from bs4 import BeautifulSoup
        caminhos = [
            os.path.join(_basedir, "static", "reports", f"{slug}_relatorio.html"),
            os.path.join(_basedir, "static", "uploads", f"{slug}_relatorio.html"),
            os.path.join(_basedir, "static", f"{slug}_relatorio.html"),
        ]
        for caminho in caminhos:
            if os.path.exists(caminho):
                with open(caminho, "r", encoding="utf-8", errors="ignore") as f:
                    html = f.read()
                soup = BeautifulSoup(html, "html.parser")
                texto = soup.get_text(separator=" ", strip=True)
                return texto[:4000]
        return ""
    except Exception:
        return ""


def _sb_gerar_analise_claude(cliente, dados_meta, perfil_texto, conteudo_pesquisa):
    """
    Chama Claude Sonnet para gerar análise completa do cliente.
    Retorna dict parseado do JSON retornado pelo modelo.
    """
    _ant = _anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    system_prompt = (
        "Você é um estrategista sênior de tráfego pago especializado em performance de "
        "criativos para Meta Ads e social media. Analise os dados e retorne APENAS JSON "
        "válido, sem markdown, sem texto adicional, sem blocos de código.\n\n"
        "IMPORTANTE sobre perfil_publico: baseie EXCLUSIVAMENTE nos dados reais de "
        "performance da semana (criativos com mais leads/menor CPL). "
        "genero_predominante = gênero que gerou mais leads na semana. "
        "faixa_etaria = faixa com melhor CPL ou mais leads. "
        "melhor_posicionamento = placement (IG Reels, IG Feed, IG Stories, FB Feed) "
        "do criativo #1 do ranking. Se não houver dados suficientes, responda 'A apurar'.\n\n"
        "Estrutura obrigatória:\n"
        "IMPORTANTE: ranking_criativos deve conter os 5 melhores criativos (posições 1 a 5). "
        "Se houver menos de 5 criativos disponíveis, inclua todos os existentes.\n"
        '{"resumo_semana":"análise em 3-4 linhas",'
        '"ranking_criativos":[{"posicao":1,"nome":"...","thumbnail_url":"...",'
        '"destaque":"por que performou em 1 frase","metricas":{"ctr":"2.45%",'
        '"cliques":1203,"cpl":"R$ 12,50","gasto":"R$ 150,00","leads":42}}],'
        '"o_que_funcionou":["insight 1","insight 2","insight 3"],'
        '"o_que_nao_funcionou":["ponto 1","ponto 2"],'
        '"perfil_publico":{"genero_predominante":"...","faixa_etaria":"...",'
        '"melhor_posicionamento":"...","cpl_medio":"R$ X,XX"},'
        '"hooks_sugeridos":{"localizacao":["hook 1","hook 2","hook 3"],'
        '"genero":["hook 1","hook 2","hook 3"],"idade":["hook 1","hook 2","hook 3"],'
        '"dor_principal":["hook 1","hook 2","hook 3"]},'
        '"ctas_sugeridos":{"mensagem":["CTA 1","CTA 2"],"visita_perfil":["CTA 1","CTA 2"],'
        '"lead":["CTA 1","CTA 2"]},'
        '"sugestoes_criativos":[{"tipo":"video/imagem/carrossel","conceito":"...",'
        '"hook":"...","formato":"Reels 9:16 / Feed 1:1 / Stories"}]}'
    )
    user_prompt = (
        f"Cliente: {cliente['nome']}\n"
        f"Nicho: {cliente.get('nicho', 'não informado')}\n\n"
        f"=== META ADS — ÚLTIMA SEMANA ===\n{json.dumps(dados_meta, ensure_ascii=False)}\n\n"
        f"=== PERFIL HISTÓRICO DO PÚBLICO ===\n{perfil_texto or 'Não disponível'}\n\n"
        f"Hooks e CTAs devem ser específicos para o nicho {cliente.get('nicho', '')}.\n"
        f"Valores monetários em formato brasileiro (R$ X,XX).\n"
        f"Lembre: leads = mensagens iniciadas no WhatsApp."
    )
    _fallback = {
        "resumo_semana": "Análise indisponível.",
        "ranking_criativos": [],
        "o_que_funcionou": [],
        "o_que_nao_funcionou": [],
        "perfil_publico": {},
        "hooks_sugeridos": {},
        "ctas_sugeridos": {},
        "sugestoes_criativos": [],
    }
    try:
        resp = _ant.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=8192,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except json.JSONDecodeError:
        _fallback["resumo_semana"] = "Análise indisponível (erro de formato)."
        return _fallback
    except Exception as e:
        _fallback["resumo_semana"] = f"Erro na análise: {str(e)}"
        return _fallback


def _sb_gerar_html_portal(todos_dados, semana_inicio, semana_fim):
    """
    Gera HTML autocontido com todos os clientes. Login screen + sidebar + seções por cliente.
    todos_dados: list de {'cliente': dict, 'analise': dict, 'dados_meta': dict}
    """
    import html as _html_mod
    _e = _html_mod.escape

    login_user = os.environ.get("SOCIAL_BRIEF_LOGIN", "social")
    login_senha = os.environ.get("SOCIAL_BRIEF_SENHA", "piloti2026")
    primeiro_slug = todos_dados[0]["cliente"]["slug"] if todos_dados else "cliente"

    from datetime import date as _date_html
    hoje_str = _date_html.today().strftime("%d/%m/%Y")

    secoes_html = ""
    menu_items_html = ""

    for item in todos_dados:
        cl = item["cliente"]
        an = item["analise"]
        dm = item["dados_meta"]
        slug = cl["slug"]

        menu_items_html += (
            f'<a class="menu-item" data-slug="{_e(slug)}" href="#" '
            f'onclick="mostrarCliente(\'{_e(slug)}\'); return false;">'
            f'{_e(cl["nome"])}</a>'
        )

        resumo_meta = dm.get("resumo", {})
        total_gasto = resumo_meta.get("total_gasto", 0)
        media_ctr = resumo_meta.get("media_ctr", 0)
        total_leads = resumo_meta.get("total_leads", 0)
        perf_pub = an.get("perfil_publico", {})
        cpl_medio = perf_pub.get("cpl_medio", "—")

        # ── Ranking criativos ──────────────────────────────────────────
        ranking_html = ""
        for i, cri in enumerate(an.get("ranking_criativos", [])[:5]):
            met = cri.get("metricas", {})
            thumb = cri.get("thumbnail_url", "")
            body_text = cri.get("body", "") or ""
            if thumb:
                thumb_tag = (
                    f'<img src="{_e(thumb)}" alt="criativo" '
                    f'style="width:64px;height:64px;object-fit:cover;border-radius:4px;'
                    f'flex-shrink:0;border:1px solid rgba(255,107,0,0.3);">'
                )
            elif body_text:
                thumb_tag = (
                    f'<div style="width:64px;min-height:64px;background:#1a1a1a;border-radius:4px;'
                    f'flex-shrink:0;border:1px solid rgba(255,107,0,0.3);padding:6px;'
                    f'font-size:9px;color:#bbb;line-height:1.4;overflow:hidden;">'
                    f'{_e(body_text[:80])}</div>'
                )
            else:
                thumb_tag = (
                    f'<div style="width:64px;height:64px;background:#1e1e1e;border-radius:4px;'
                    f'flex-shrink:0;border:1px solid #2a2a2a;display:flex;align-items:center;'
                    f'justify-content:center;font-size:18px;color:#333;">📷</div>'
                )
            max_ctr_raw = an.get("ranking_criativos", [{}])[0].get("metricas", {}).get("ctr", 1) or 1
            ctr_raw = met.get("ctr", 0) or 0
            try:
                bar_pct = int(float(str(ctr_raw).replace("%", "").strip() or 0) /
                              float(str(max_ctr_raw).replace("%", "").strip() or 1) * 100)
            except Exception:
                bar_pct = 100 if i == 0 else 60
            ranking_html += (
                f'<div style="display:flex;align-items:center;gap:14px;padding:14px 0;'
                f'border-bottom:1px solid #1e1e1e;">'
                f'<div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:700;'
                f'font-size:22px;color:#FF6B00;width:24px;flex-shrink:0;">#{i+1}</div>'
                f'{thumb_tag}'
                f'<div style="flex:1;min-width:0;">'
                f'<div style="font-size:13px;font-weight:600;color:#F5F5F0;white-space:nowrap;'
                f'overflow:hidden;text-overflow:ellipsis;">{_e(cri.get("nome",""))}</div>'
                f'<div style="font-size:12px;color:#888;margin:2px 0 6px;">{_e(cri.get("destaque",""))}</div>'
                f'<div style="display:flex;gap:10px;flex-wrap:wrap;">'
                f'<span style="font-size:11px;color:#FF6B00;font-weight:600;">CTR {_e(str(met.get("ctr","—")))}</span>'
                f'<span style="font-size:11px;color:#bbb;">Cliques {_e(str(met.get("cliques","—")))}</span>'
                f'<span style="font-size:11px;color:#bbb;">CPL {_e(str(met.get("cpl","—")))}</span>'
                f'<span style="font-size:11px;color:#bbb;">Gasto {_e(str(met.get("gasto","—")))}</span>'
                f'</div>'
                f'<div style="height:3px;background:#1e1e1e;border-radius:1px;margin-top:6px;">'
                f'<div style="height:100%;width:{bar_pct}%;background:#FF6B00;border-radius:1px;"></div></div>'
                f'</div></div>'
            )

        # ── O que funcionou / não ──────────────────────────────────────
        fun_html = "".join(
            f'<div style="padding:10px 0;border-bottom:1px solid #1e1e1e;font-size:13px;color:#bbb;">'
            f'<span style="color:#4caf50;margin-right:8px;">◆</span>{_e(x)}</div>'
            for x in an.get("o_que_funcionou", [])
        )
        nao_fun_html = "".join(
            f'<div style="padding:10px 0;border-bottom:1px solid #1e1e1e;font-size:13px;color:#bbb;">'
            f'<span style="color:#FF6B00;margin-right:8px;">◆</span>{_e(x)}</div>'
            for x in an.get("o_que_nao_funcionou", [])
        )

        # ── Sugestões de criativos ─────────────────────────────────────
        sug_html = "".join(
            f'<div style="background:#141414;border:1px solid rgba(255,107,0,0.2);border-radius:4px;'
            f'padding:20px;margin-bottom:12px;position:relative;overflow:hidden;">'
            f'<div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;"></div>'
            f'<div style="font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#FF6B00;'
            f'font-weight:600;margin-bottom:8px;font-family:\'Barlow Condensed\',sans-serif;">'
            f'{_e(sg.get("tipo","")).upper()}</div>'
            f'<div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:700;font-size:18px;'
            f'color:#F5F5F0;margin-bottom:6px;letter-spacing:-0.5px;">{_e(sg.get("conceito",""))}</div>'
            f'<div style="font-size:13px;color:#888;margin-bottom:4px;">'
            f'<span style="color:#bbb;font-weight:600;">Hook:</span> {_e(sg.get("hook",""))}</div>'
            f'<div style="font-size:12px;color:#666;">'
            f'<span style="color:#888;font-weight:600;">Formato:</span> {_e(sg.get("formato",""))}</div>'
            f'</div>'
            for sg in an.get("sugestoes_criativos", [])[:4]
        )

        _fb = '<div style="font-size:13px;color:#444;padding:8px 0;">—</div>'

        secoes_html += f'''
<div class="cliente-secao" id="cliente-{_e(slug)}" style="display:none;">

  <!-- Header -->
  <div style="position:relative;overflow:hidden;background:#0D0D0D;
              border:1px solid rgba(255,107,0,0.15);border-radius:4px;
              padding:36px 32px;margin-bottom:20px;">
    <div style="position:absolute;inset:0;background-image:
      linear-gradient(rgba(255,107,0,0.04) 1px,transparent 1px),
      linear-gradient(90deg,rgba(255,107,0,0.04) 1px,transparent 1px);
      background-size:50px 50px;pointer-events:none;"></div>
    <div style="position:absolute;top:16px;right:24px;
                font-family:'Barlow Condensed',sans-serif;font-size:80px;font-weight:900;
                color:rgba(255,107,0,0.04);line-height:1;letter-spacing:-4px;pointer-events:none;">
      BRIEF</div>
    <div style="position:relative;z-index:1;">
      <div style="font-size:10px;letter-spacing:5px;text-transform:uppercase;color:#FF6B00;
                  font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:8px;">
        {_e(cl.get("nicho","—"))} &nbsp;·&nbsp; Semana {_e(semana_inicio)} — {_e(semana_fim)}</div>
      <div style="font-family:'Barlow Condensed',sans-serif;font-weight:900;
                  font-size:clamp(32px,4vw,52px);text-transform:uppercase;
                  letter-spacing:-1px;color:#F5F5F0;line-height:1;margin-bottom:20px;">
        {_e(cl["nome"])}</div>
      <div style="display:flex;gap:40px;flex-wrap:wrap;">
        <div>
          <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;
                       font-size:28px;color:#FF6B00;display:block;">R$ {total_gasto:,.2f}</span>
          <span style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#888;">Gasto</span>
        </div>
        <div>
          <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;
                       font-size:28px;color:#F5F5F0;display:block;">{_e(str(media_ctr))}%</span>
          <span style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#888;">CTR Médio</span>
        </div>
        <div>
          <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;
                       font-size:28px;color:#00C2FF;display:block;">{_e(str(total_leads))}</span>
          <span style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#888;">Leads</span>
        </div>
        <div>
          <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;
                       font-size:28px;color:#F5F5F0;display:block;">{_e(str(cpl_medio))}</span>
          <span style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#888;">CPL Médio</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Resumo -->
  <div style="background:#141414;border:1px solid #1e1e1e;border-radius:4px;padding:24px;
              margin-bottom:16px;position:relative;overflow:hidden;">
    <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;opacity:0.4;"></div>
    <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#FF6B00;
                font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:14px;">
      📝 Resumo da Semana</div>
    <p style="font-size:14px;color:#bbb;line-height:1.8;margin:0;">{_e(an.get("resumo_semana",""))}</p>
  </div>

  <!-- Ranking + Funcionou -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
    <div style="background:#141414;border:1px solid #1e1e1e;border-radius:4px;padding:24px;
                position:relative;overflow:hidden;">
      <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;"></div>
      <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#FF6B00;
                  font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:16px;">
        🏆 Ranking de Criativos</div>
      {ranking_html or _fb}
    </div>
    <div style="display:grid;grid-template-rows:1fr 1fr;gap:16px;">
      <div style="background:#141414;border:1px solid #1e1e1e;border-radius:4px;padding:20px;
                  position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#4caf50;opacity:0.7;"></div>
        <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#4caf50;
                    font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:12px;">
          ◆ O que funcionou</div>
        {fun_html or _fb}
      </div>
      <div style="background:#141414;border:1px solid #1e1e1e;border-radius:4px;padding:20px;
                  position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;opacity:0.7;"></div>
        <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#FF6B00;
                    font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:12px;">
          ◆ O que não funcionou</div>
        {nao_fun_html or _fb}
      </div>
    </div>
  </div>

  <!-- Sugestões de criativos -->
  <div style="background:#141414;border:1px solid #1e1e1e;border-radius:4px;padding:24px;
              margin-bottom:16px;position:relative;overflow:hidden;">
    <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;"></div>
    <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#FF6B00;
                font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:20px;">
      🎨 Sugestões de Criativos</div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;">
      {sug_html or _fb}
    </div>
  </div>

  <!-- Referências de Criativos -->
  <div style="background:#141414;border:1px solid rgba(255,107,0,0.2);border-radius:4px;padding:24px;
              margin-bottom:32px;position:relative;overflow:hidden;">
    <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;opacity:0.6;"></div>
    <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#FF6B00;
                font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:16px;">
      🎯 Referências de Criativos / Inspiração</div>
    <div style="font-size:13px;color:#444;font-style:italic;padding:20px 0;text-align:center;
                border:1px dashed #2a2a2a;border-radius:4px;">
      Em breve — adicione referências, @ de perfis e links de inspiração aqui.
    </div>
  </div>

</div>'''

    css = (
        '*{box-sizing:border-box;margin:0;padding:0;}'
        'html{scroll-behavior:smooth;}'
        "body{font-family:'Barlow',sans-serif;background:#0D0D0D;color:#F5F5F0;overflow-x:hidden;}"
        'a{text-decoration:none;color:inherit;}'
        '#tela-login{position:fixed;inset:0;background:#0D0D0D;display:flex;align-items:center;'
        'justify-content:center;z-index:9999;}'
        '.login-bg{position:absolute;inset:0;background-image:'
        'linear-gradient(rgba(255,107,0,0.05) 1px,transparent 1px),'
        'linear-gradient(90deg,rgba(255,107,0,0.05) 1px,transparent 1px);'
        'background-size:60px 60px;}'
        '.login-box{position:relative;z-index:1;width:360px;text-align:center;}'
        ".login-kicker{font-family:'Barlow Condensed',sans-serif;font-size:11px;letter-spacing:5px;"
        'text-transform:uppercase;color:#FF6B00;margin-bottom:16px;}'
        ".login-title{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:52px;"
        'text-transform:uppercase;letter-spacing:-1px;color:#F5F5F0;line-height:1;margin-bottom:32px;}'
        '.login-line{width:40px;height:2px;background:#FF6B00;margin:0 auto 32px;}'
        '.login-input{width:100%;background:#141414;border:1px solid rgba(255,107,0,0.3);border-radius:4px;'
        "padding:14px 16px;font-size:14px;color:#F5F5F0;margin-bottom:12px;outline:none;font-family:'Barlow',sans-serif;}"
        '.login-input::placeholder{color:#444;}'
        '.login-input:focus{border-color:#FF6B00;}'
        '.login-btn{width:100%;background:#FF6B00;color:#0D0D0D;border:none;border-radius:4px;padding:14px;'
        "font-family:'Barlow Condensed',sans-serif;font-size:16px;font-weight:700;letter-spacing:3px;"
        'text-transform:uppercase;cursor:pointer;transition:opacity .2s;}'
        '.login-btn:hover{opacity:.85;}'
        '#erro-login{display:none;color:#FF6B00;font-size:12px;margin-top:10px;letter-spacing:1px;}'
        '#app{display:none;min-height:100vh;}'
        '.sidebar{width:220px;background:#0a0a0a;border-right:1px solid rgba(255,107,0,0.15);'
        'padding:0;position:fixed;height:100vh;overflow-y:auto;left:0;top:0;display:flex;flex-direction:column;}'
        '.sidebar-logo{padding:24px 20px;border-bottom:1px solid #1a1a1a;}'
        ".sidebar-brand{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:18px;"
        'letter-spacing:4px;text-transform:uppercase;color:#FF6B00;}'
        '.sidebar-tagline{font-size:10px;color:#444;letter-spacing:2px;text-transform:uppercase;margin-top:4px;}'
        '.sidebar-week{padding:14px 20px;font-size:11px;color:#555;letter-spacing:1px;'
        'border-bottom:1px solid #1a1a1a;text-transform:uppercase;}'
        '.sidebar-section{padding:16px 20px 8px;font-size:9px;letter-spacing:3px;'
        'text-transform:uppercase;color:#333;font-weight:600;}'
        ".menu-item{display:block;padding:10px 20px;font-size:13px;color:#666;cursor:pointer;"
        "border-left:2px solid transparent;transition:all .15s;font-family:'Barlow',sans-serif;}"
        '.menu-item:hover{color:#F5F5F0;background:rgba(255,107,0,0.06);border-left-color:rgba(255,107,0,0.4);}'
        '.menu-item.ativo{color:#FF6B00;background:rgba(255,107,0,0.08);border-left-color:#FF6B00;}'
        '.sidebar-footer{margin-top:auto;padding:16px 20px;border-top:1px solid #1a1a1a;}'
        '.btn-logout{background:transparent;color:#444;border:1px solid #2a2a2a;border-radius:3px;'
        'padding:8px 16px;cursor:pointer;font-size:11px;letter-spacing:2px;text-transform:uppercase;'
        "width:100%;font-family:'Barlow Condensed',sans-serif;font-weight:600;transition:all .2s;}"
        '.btn-logout:hover{color:#FF6B00;border-color:#FF6B00;}'
        '.main-content{margin-left:220px;padding:32px;min-height:100vh;background:#0D0D0D;}'
        '@media(max-width:900px){'
        '.sidebar{display:none;}'
        '.main-content{margin-left:0;padding:20px;}}'
    )

    html = (
        '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'<title>Piloti — Social Brief · {_e(semana_inicio)} a {_e(semana_fim)}</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@300;400;600;700;800;900&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n'
        '</head>\n<body>\n\n'
        '<!-- LOGIN -->\n'
        '<div id="tela-login">\n'
        '  <div class="login-bg"></div>\n'
        '  <div class="login-box">\n'
        '    <div class="login-kicker">Piloti Agency</div>\n'
        '    <div class="login-title">Social Brief</div>\n'
        '    <div class="login-line"></div>\n'
        '    <input id="inp-login" class="login-input" type="text" placeholder="Usuário" autocomplete="username" />\n'
        '    <input id="inp-senha" class="login-input" type="password" placeholder="Senha"\n'
        '      onkeydown="if(event.key===\'Enter\')tentarLogin()" autocomplete="current-password" />\n'
        '    <button class="login-btn" onclick="tentarLogin()">Entrar</button>\n'
        '    <div id="erro-login">Credenciais inválidas.</div>\n'
        '  </div>\n'
        '</div>\n\n'
        '<!-- APP -->\n'
        '<div id="app">\n'
        '  <div class="sidebar">\n'
        '    <div class="sidebar-logo">\n'
        '      <div class="sidebar-brand">Piloti</div>\n'
        '      <div class="sidebar-tagline">Social Brief Semanal</div>\n'
        '    </div>\n'
        f'    <div class="sidebar-week">📅 {_e(semana_inicio)} — {_e(semana_fim)}</div>\n'
        '    <div class="sidebar-section">Clientes</div>\n'
        f'    {menu_items_html}\n'
        '    <div class="sidebar-footer">\n'
        '      <button class="btn-logout" onclick="logout()">↩ Sair</button>\n'
        '    </div>\n'
        '  </div>\n'
        f'  <div class="main-content">{secoes_html}</div>\n'
        '</div>\n\n'
        '<script>\n'
        f'var LOGIN="{_e(login_user)}";var SENHA="{_e(login_senha)}";\n'
        f'var PRIMEIRO="{_e(primeiro_slug)}";\n'
        'function tentarLogin(){{\n'
        '  var u=document.getElementById("inp-login").value;\n'
        '  var s=document.getElementById("inp-senha").value;\n'
        '  if(u===LOGIN&&s===SENHA){{\n'
        '    localStorage.setItem("piloti_brief_auth","ok");\n'
        '    document.getElementById("tela-login").style.display="none";\n'
        '    document.getElementById("app").style.display="flex";\n'
        '    mostrarCliente(PRIMEIRO);\n'
        '  }}else{{document.getElementById("erro-login").style.display="block";}}\n'
        '}}\n'
        'function verificarLogin(){{\n'
        '  if(localStorage.getItem("piloti_brief_auth")==="ok"){{\n'
        '    document.getElementById("tela-login").style.display="none";\n'
        '    document.getElementById("app").style.display="flex";\n'
        '    mostrarCliente(PRIMEIRO);\n'
        '  }}\n'
        '}}\n'
        'function logout(){{localStorage.removeItem("piloti_brief_auth");location.reload();}}\n'
        'function mostrarCliente(slug){{\n'
        '  document.querySelectorAll(".cliente-secao").forEach(function(s){{s.style.display="none";}});\n'
        '  var el=document.getElementById("cliente-"+slug);if(el)el.style.display="block";\n'
        '  document.querySelectorAll(".menu-item").forEach(function(m){{m.classList.remove("ativo");}});\n'
        "  var mi=document.querySelector(\".menu-item[data-slug='\"+slug+\"']\");if(mi)mi.classList.add(\"ativo\");\n"
        '}}\n'
        'function copiar(btn){{\n'
        '  var t=btn.getAttribute("data-text");\n'
        '  navigator.clipboard.writeText(t).then(function(){{\n'
        '    var o=btn.innerHTML;btn.innerHTML="\u2713";\n'
        '    setTimeout(function(){{btn.innerHTML=o;}},2000);\n'
        '  }});\n'
        '}}\n'
        'window.onload=function(){{verificarLogin();}};\n'
        '</script>\n</body>\n</html>'
    )
    return html


def _sb_publicar_surge(html):
    """
    Publica HTML no Surge.sh via CLI.
    Retorna URL publicada.
    """
    import subprocess
    import tempfile
    surge_url = os.environ.get("SURGE_URL", "piloti-brief.surge.sh")
    surge_token = os.environ.get("SURGE_TOKEN", "")
    if not surge_token or surge_token == "CONFIGURE_ME":
        raise ValueError("SURGE_TOKEN não configurado no .env. Execute 'surge token' para obtê-lo.")

    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = os.path.join(tmpdir, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)
        cmd = ["surge", tmpdir, surge_url, "--token", surge_token]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            raise RuntimeError(f"Surge error: {result.stderr or result.stdout}")
    return f"https://{surge_url}"


# ── Social Brief — CRUD de clientes ─────────────────────────────────────────

@app.route("/api/social-brief/clientes", methods=["GET"])
@login_required
def sb_clientes_list():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM social_brief_clientes ORDER BY nome")
        clientes = [dict(r) for r in cur.fetchall()]
        for c in clientes:
            if c.get("concorrentes") is None:
                c["concorrentes"] = []
            if c.get("tipos_campanha") is None:
                c["tipos_campanha"] = {}
        return jsonify({"clientes": clientes})
    finally:
        conn.close()


@app.route("/api/social-brief/clientes", methods=["POST"])
@login_required
def sb_clientes_create():
    data = request.get_json()
    if not data or not data.get("nome") or not data.get("slug"):
        return jsonify({"error": "nome e slug obrigatórios"}), 400
    import re as _re_slug
    if not _re_slug.match(r'^[a-z0-9-]+$', data["slug"]):
        return jsonify({"error": "slug deve conter apenas letras minúsculas, números e hifens"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO social_brief_clientes
               (nome, slug, nicho, meta_account_id, meta_agency,
                concorrentes, tipos_campanha, ativo)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",
            (
                data["nome"], data["slug"],
                data.get("nicho", ""),
                data.get("meta_account_id", ""),
                data.get("meta_agency", "piloti"),
                data.get("concorrentes", []),
                json.dumps(data.get("tipos_campanha", {})),
                data.get("ativo", True),
            )
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"ok": True, "id": new_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/social-brief/clientes/<int:cid>", methods=["PUT"])
@login_required
def sb_clientes_update(cid):
    data = request.get_json()
    if not data:
        return jsonify({"error": "body obrigatório"}), 400
    if not data.get("nome") or not data.get("slug"):
        return jsonify({"error": "nome e slug obrigatórios"}), 400
    import re as _re_put
    if not _re_put.match(r'^[a-z0-9-]+$', data["slug"]):
        return jsonify({"error": "slug deve conter apenas letras minúsculas, números e hifens"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE social_brief_clientes SET
               nome=%s, slug=%s, nicho=%s,
               meta_account_id=%s, meta_agency=%s,
               concorrentes=%s, tipos_campanha=%s, ativo=%s
               WHERE id=%s""",
            (
                data.get("nome"), data.get("slug"),
                data.get("nicho", ""),
                data.get("meta_account_id", ""),
                data.get("meta_agency", "piloti"),
                data.get("concorrentes", []),
                json.dumps(data.get("tipos_campanha", {})),
                data.get("ativo", True),
                cid,
            )
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/social-brief/clientes/<int:cid>", methods=["DELETE"])
@login_required
def sb_clientes_delete(cid):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM social_brief_clientes WHERE id=%s", (cid,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "cliente não encontrado"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/social-brief/ultima-geracao", methods=["GET"])
@login_required
def sb_ultima_geracao():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, semana_inicio, semana_fim, surge_url, publicado, criado_em "
            "FROM social_brief_geracoes ORDER BY criado_em DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"geracao": None})
        g = dict(row)
        g["semana_inicio"] = str(g["semana_inicio"])
        g["semana_fim"] = str(g["semana_fim"])
        g["criado_em"] = str(g["criado_em"])
        return jsonify({"geracao": g})
    finally:
        conn.close()


@app.route("/api/social-brief/gerar", methods=["GET"])
@login_required
def sb_gerar_portal():
    """Endpoint SSE: gera portal completo com todos os clientes ativos."""
    from flask import stream_with_context, Response as _Response
    from datetime import date as _date_sse, timedelta as _td_sse

    def _generate():
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM social_brief_clientes WHERE ativo=TRUE ORDER BY nome")
            clientes = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

        if not clientes:
            yield f"data: {json.dumps({'status': 'erro', 'mensagem': 'Nenhum cliente ativo cadastrado'})}\n\n"
            return

        todos_dados = []
        total = len(clientes)

        for i, cliente in enumerate(clientes):
            progresso = int((i / total) * 80)

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'etapa': 'Buscando Meta Ads...', 'progresso': progresso})}\n\n"
            dados_meta = _sb_buscar_meta_ads(
                cliente.get("meta_account_id", ""),
                cliente.get("meta_agency", "piloti")
            )

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'etapa': 'Lendo perfil...', 'progresso': progresso + 2})}\n\n"
            perfil_texto = _sb_ler_perfil_html(cliente["slug"])

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'etapa': 'Pesquisando concorrentes...', 'progresso': progresso + 4})}\n\n"
            pesquisa = _sb_buscar_concorrentes(
                cliente.get("nicho", ""),
                cliente.get("concorrentes") or []
            )

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'etapa': 'Gerando análise com Claude...', 'progresso': progresso + 6})}\n\n"
            analise = _sb_gerar_analise_claude(
                cliente, dados_meta,
                perfil_texto,
                pesquisa.get("conteudo_pesquisa", "")
            )

            todos_dados.append({"cliente": cliente, "analise": analise, "dados_meta": dados_meta})

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'status': 'concluido', 'progresso': int(((i + 1) / total) * 80)})}\n\n"
            time.sleep(1)

        yield f"data: {json.dumps({'etapa': 'Gerando HTML final...', 'progresso': 85})}\n\n"

        hoje = _date_sse.today()
        dia_seg = hoje - _td_sse(days=hoje.weekday())
        semana_inicio = dia_seg.strftime("%d/%m/%Y")
        semana_fim = (dia_seg + _td_sse(days=6)).strftime("%d/%m/%Y")
        html_portal = _sb_gerar_html_portal(todos_dados, semana_inicio, semana_fim)

        conn = _get_db()
        geracao_id = None
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO social_brief_geracoes
                   (semana_inicio, semana_fim, html_completo, publicado, clientes_incluidos)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    dia_seg.isoformat(),
                    (dia_seg + _td_sse(days=6)).isoformat(),
                    html_portal,
                    False,
                    json.dumps([{"id": d["cliente"]["id"], "nome": d["cliente"]["nome"]} for d in todos_dados]),
                )
            )
            geracao_id = cur.fetchone()["id"]
            for item in todos_dados:
                cur.execute(
                    """INSERT INTO social_brief_cliente_dados
                       (geracao_id, cliente_id, analise_json, dados_meta)
                       VALUES (%s, %s, %s, %s)""",
                    (geracao_id, item["cliente"]["id"],
                     json.dumps(item["analise"]), json.dumps(item["dados_meta"]))
                )
            conn.commit()
        finally:
            conn.close()

        yield f"data: {json.dumps({'etapa': 'Publicando no Surge...', 'progresso': 90})}\n\n"

        try:
            url = _sb_publicar_surge(html_portal)
            conn2 = _get_db()
            try:
                cur2 = conn2.cursor()
                cur2.execute(
                    "UPDATE social_brief_geracoes SET surge_url=%s, publicado=TRUE WHERE id=%s",
                    (url, geracao_id)
                )
                conn2.commit()
            finally:
                conn2.close()
            yield f"data: {json.dumps({'status': 'finalizado', 'url': url, 'progresso': 100})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'finalizado_sem_surge', 'erro_surge': str(e), 'geracao_id': geracao_id, 'progresso': 100})}\n\n"

    return _Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/social-brief/republicar", methods=["POST"])
@login_required
def sb_republicar():
    """Republica o portal usando os dados já salvos da última geração — sem chamar Meta Ads nem Claude."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        # Pega a última geração
        cur.execute(
            "SELECT id, semana_inicio, semana_fim FROM social_brief_geracoes ORDER BY criado_em DESC LIMIT 1"
        )
        ger = cur.fetchone()
        if not ger:
            return jsonify({"error": "Nenhuma geração encontrada. Gere o portal primeiro."}), 404

        geracao_id = ger["id"]
        semana_inicio = ger["semana_inicio"].strftime("%d/%m/%Y") if hasattr(ger["semana_inicio"], "strftime") else str(ger["semana_inicio"])
        semana_fim = ger["semana_fim"].strftime("%d/%m/%Y") if hasattr(ger["semana_fim"], "strftime") else str(ger["semana_fim"])

        # Carrega dados dos clientes salvos
        cur.execute(
            """SELECT sbc.*, sbd.analise_json, sbd.dados_meta
               FROM social_brief_cliente_dados sbd
               JOIN social_brief_clientes sbc ON sbc.id = sbd.cliente_id
               WHERE sbd.geracao_id = %s ORDER BY sbc.nome""",
            (geracao_id,)
        )
        rows = cur.fetchall()
        if not rows:
            return jsonify({"error": "Dados da geração não encontrados."}), 404

        todos_dados = [
            {
                "cliente": {k: v for k, v in dict(r).items() if k not in ("analise_json", "dados_meta")},
                "analise": r["analise_json"] if isinstance(r["analise_json"], dict) else json.loads(r["analise_json"] or "{}"),
                "dados_meta": r["dados_meta"] if isinstance(r["dados_meta"], dict) else json.loads(r["dados_meta"] or "{}"),
            }
            for r in rows
        ]
    finally:
        conn.close()

    html_portal = _sb_gerar_html_portal(todos_dados, semana_inicio, semana_fim)
    try:
        url = _sb_publicar_surge(html_portal)
        conn2 = _get_db()
        try:
            cur2 = conn2.cursor()
            cur2.execute(
                "UPDATE social_brief_geracoes SET html_completo=%s, surge_url=%s, publicado=TRUE WHERE id=%s",
                (html_portal, url, geracao_id)
            )
            conn2.commit()
        finally:
            conn2.close()
        return jsonify({"ok": True, "url": url, "geracao_id": geracao_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/social-brief/download/<int:geracao_id>", methods=["GET"])
@login_required
def sb_download_html(geracao_id):
    """Permite baixar o HTML de uma geração específica."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT html_completo FROM social_brief_geracoes WHERE id=%s", (geracao_id,)
        )
        row = cur.fetchone()
        if not row or not row["html_completo"]:
            return jsonify({"error": "Geração não encontrada"}), 404
        from flask import make_response
        resp = make_response(row["html_completo"])
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        resp.headers["Content-Disposition"] = f'attachment; filename="piloti-brief-{geracao_id}.html"'
        return resp
    finally:
        conn.close()


# ── NUTRIÇÃO: Rotas Perfis ────────────────────────────────────────────────────

@app.route("/api/nutricao/perfis")
@login_required
def nutricao_get_perfis():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM nutricao_perfis ORDER BY id")
        perfis = [dict(r) for r in cur.fetchall()]
        for p in perfis:
            if p.get('peso') and p.get('altura'):
                p['imc'] = _calcular_imc(p['peso'], p['altura'])
            else:
                p['imc'] = None
            # converter Decimal para float para JSON
            for k in ['peso', 'altura', 'tmb', 'get', 'meta_calorica',
                      'meta_proteina', 'meta_carbo', 'meta_gordura']:
                if p.get(k) is not None:
                    p[k] = float(p[k])
        return jsonify({'perfis': perfis})
    finally:
        conn.close()


@app.route("/api/nutricao/perfis/<int:perfil_id>", methods=["POST"])
@login_required
def nutricao_update_perfil(perfil_id):
    data = request.get_json() or {}
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM nutricao_perfis WHERE id = %s", (perfil_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'perfil não encontrado'}), 404
        perfil = dict(row)

        # Atualiza campos enviados
        campos = ['idade', 'peso', 'altura', 'objetivo', 'nivel_atividade',
                  'preferencias', 'aversoes']
        for campo in campos:
            if campo in data:
                perfil[campo] = data[campo]

        # Recalcula TMB/GET/macros
        tmb = _calcular_tmb(
            perfil.get('sexo', 'M'),
            perfil.get('peso'), perfil.get('altura'), perfil.get('idade')
        )
        get = _calcular_get(tmb, perfil.get('nivel_atividade', 'intenso'))
        macros = _calcular_macros(
            perfil.get('objetivo', 'hipertrofia'), get, perfil.get('peso', 70)
        )

        if tmb > 0:
            cur.execute("""
                UPDATE nutricao_perfis SET
                    idade=%s, peso=%s, altura=%s, objetivo=%s,
                    nivel_atividade=%s, preferencias=%s, aversoes=%s,
                    tmb=%s, get=%s, meta_calorica=%s, meta_proteina=%s,
                    meta_carbo=%s, meta_gordura=%s, atualizado_em=NOW()
                WHERE id=%s
            """, (
                perfil.get('idade'), perfil.get('peso'), perfil.get('altura'),
                perfil.get('objetivo'), perfil.get('nivel_atividade'),
                perfil.get('preferencias'), perfil.get('aversoes'),
                tmb, get, macros['calorias'], macros['proteina'],
                macros['carbo'], macros['gordura'],
                perfil_id
            ))
        else:
            cur.execute("""
                UPDATE nutricao_perfis SET
                    idade=%s, peso=%s, altura=%s, objetivo=%s,
                    nivel_atividade=%s, preferencias=%s, aversoes=%s,
                    atualizado_em=NOW()
                WHERE id=%s
            """, (
                perfil.get('idade'), perfil.get('peso'), perfil.get('altura'),
                perfil.get('objetivo'), perfil.get('nivel_atividade'),
                perfil.get('preferencias'), perfil.get('aversoes'),
                perfil_id
            ))
        conn.commit()
        return jsonify({'ok': True, 'tmb': tmb, 'get': get, **macros})
    finally:
        conn.close()


@app.route("/api/nutricao/gerar-cardapio", methods=["POST"])
@login_required
def nutricao_gerar_cardapio():
    import json as _json
    from datetime import date, timedelta

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    conn = _get_db()
    try:
        cur = conn.cursor()

        # Buscar perfis
        cur.execute("SELECT * FROM nutricao_perfis ORDER BY id LIMIT 2")
        perfis = {p['nome'].lower(): dict(p) for p in cur.fetchall()}
        bruno = perfis.get('bruno', {})
        camila = perfis.get('camila', {})

        # Buscar alimentos favoritos
        cur.execute("SELECT nome, categoria FROM nutricao_alimentos_base WHERE favorito=true ORDER BY categoria")
        alimentos = cur.fetchall()
        proteinas = [a['nome'] for a in alimentos if a['categoria'] == 'proteina']
        carbos = [a['nome'] for a in alimentos if a['categoria'] == 'carbo']
        lanches = [a['nome'] for a in alimentos if a['categoria'] == 'lanche']

        # Semana atual
        hoje = date.today()
        segunda = hoje - timedelta(days=hoje.weekday())
        domingo = segunda + timedelta(days=6)

        def fmt_perfil(p, nome, sexo_label):
            peso = float(p.get('peso') or 75)
            altura = int(p.get('altura') or 175)
            idade = int(p.get('idade') or 28)
            tmb = float(p.get('tmb') or 0)
            get_val = float(p.get('get') or 0)
            meta_cal = int(p.get('meta_calorica') or 0)
            meta_prot = int(p.get('meta_proteina') or 0)
            meta_carbo = int(p.get('meta_carbo') or 0)
            meta_gord = int(p.get('meta_gordura') or 0)
            imc = _calcular_imc(peso, altura)
            return f"""=== {nome.upper()} ({sexo_label}, academia intensa) ===
Idade: {idade} anos | Peso: {peso}kg | Altura: {altura}cm | IMC: {imc}
TMB: {tmb:.0f} kcal | GET: {get_val:.0f} kcal | Meta: {meta_cal} kcal/dia
Proteína: {meta_prot}g | Carbo: {meta_carbo}g | Gordura: {meta_gord}g
Objetivo: Hipertrofia — ganho de massa muscular"""

        system_prompt = """Você é um nutricionista especializado em hipertrofia e ganho de massa muscular. Crie cardápios práticos, saborosos e com foco em alimentos fáceis de preparar e congelar. Retorne APENAS JSON válido, sem markdown, sem explicações."""

        user_prompt = f"""Crie um cardápio semanal completo (7 dias) para 2 pessoas:

{fmt_perfil(bruno, 'Bruno', 'homem')}

{fmt_perfil(camila, 'Camila', 'mulher')}

=== ALIMENTOS QUE JÁ USAM E GOSTAM ===
Proteínas: {', '.join(proteinas)}
Carbos: {', '.join(carbos)}
Lanches: {', '.join(lanches)}
Sem restrições alimentares.

=== REGRAS OBRIGATÓRIAS ===
1. Priorizar alimentos que já conhecem, misturando com no mínimo 3 refeições novas
2. Café da manhã: rotacionar entre pão com requeijão/queijo, banana com granola/mel/aveia, ovo
3. Almoço e janta: prato principal + acompanhamento + verdura. Indicar se é congelável
4. Café da tarde: lanche nutritivo, congelável quando possível
5. Suco diário: 1 por dia para encher 1 garrafinha (300-500ml), sucos funcionais
6. Fruta do dia: 1 fruta diferente por dia
7. Porções diferentes para Bruno e Camila conforme suas metas calóricas
8. Incluir receitas detalhadas de pratos novos
9. Tempo de preparo realista (pessoas que trabalham)

Semana de {segunda.strftime('%d/%m')} a {domingo.strftime('%d/%m/%Y')}.

Estrutura JSON obrigatória:
{{
  "semana": "{segunda.strftime('%d/%m')} a {domingo.strftime('%d/%m/%Y')}",
  "resumo": {{
    "bruno": {{"calorias_dia": 0, "proteina_dia": "0g", "carbo_dia": "0g", "gordura_dia": "0g"}},
    "camila": {{"calorias_dia": 0, "proteina_dia": "0g", "carbo_dia": "0g", "gordura_dia": "0g"}}
  }},
  "dias": [
    {{
      "dia": "Segunda-feira",
      "refeicoes": {{
        "cafe_manha": {{"descricao": "...", "bruno": {{"porcao": "...", "calorias": 0}}, "camila": {{"porcao": "...", "calorias": 0}}}},
        "almoco": {{"prato_principal": "...", "acompanhamento": "...", "verdura": "...", "congelavel": true, "tempo_preparo": "30min", "bruno": {{"porcao": "...", "calorias": 0, "proteina": "0g"}}, "camila": {{"porcao": "...", "calorias": 0, "proteina": "0g"}}}},
        "cafe_tarde": {{"descricao": "...", "congelavel": true, "bruno": {{"porcao": "...", "calorias": 0}}, "camila": {{"porcao": "...", "calorias": 0}}}},
        "janta": {{"prato_principal": "...", "acompanhamento": "...", "congelavel": true, "tempo_preparo": "25min", "bruno": {{"porcao": "...", "calorias": 0, "proteina": "0g"}}, "camila": {{"porcao": "...", "calorias": 0, "proteina": "0g"}}}},
        "suco_dia": {{"nome": "...", "ingredientes": ["..."], "beneficio": "..."}},
        "fruta_dia": "..."
      }}
    }}
  ],
  "dicas_preparo": ["..."],
  "receitas_detalhadas": [
    {{"nome": "...", "ingredientes": [{{"item": "...", "quantidade": "..."}}], "modo_preparo": ["passo 1"], "rende": "...", "tempo": "...", "congelavel": true, "validade_freezer": "..."}}
  ]
}}"""

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=16000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        texto = msg.content[0].text.strip()
        # Extrair JSON de possível bloco markdown do Claude
        match = _re.search(r'```(?:json)?\s*([\s\S]*?)```', texto)
        if match:
            texto = match.group(1).strip()
        cardapio_json = _json.loads(texto)

        # Salvar no banco com status 'revisao'
        cur.execute("""
            INSERT INTO nutricao_cardapios
                (semana_inicio, semana_fim, status, cardapio_json)
            VALUES (%s, %s, 'revisao', %s)
            RETURNING id
        """, (segunda, domingo, _json.dumps(cardapio_json)))
        cardapio_id = cur.fetchone()['id']
        conn.commit()

        return jsonify({
            'ok': True,
            'id': cardapio_id,
            'cardapio': cardapio_json,
            'semana_inicio': str(segunda),
            'semana_fim': str(domingo),
        })

    except _json.JSONDecodeError as e:
        return jsonify({'error': f'Claude retornou JSON inválido: {str(e)}'}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route("/api/nutricao/cardapios")
@login_required
def nutricao_listar_cardapios():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, semana_inicio, semana_fim, status, criado_em, aprovado_em
            FROM nutricao_cardapios ORDER BY criado_em DESC LIMIT 20
        """)
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            for k in ['semana_inicio', 'semana_fim']:
                if d.get(k):
                    d[k] = str(d[k])
            for k in ['criado_em', 'aprovado_em']:
                if d.get(k):
                    d[k] = d[k].isoformat()
            rows.append(d)
        return jsonify({'cardapios': rows})
    finally:
        conn.close()


@app.route("/api/nutricao/cardapios/<int:cardapio_id>")
@login_required
def nutricao_get_cardapio(cardapio_id):
    import json as _json
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM nutricao_cardapios WHERE id = %s", (cardapio_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'não encontrado'}), 404
        d = dict(row)
        for k in ['semana_inicio', 'semana_fim']:
            if d.get(k): d[k] = str(d[k])
        for k in ['criado_em', 'aprovado_em']:
            if d.get(k): d[k] = d[k].isoformat()
        return jsonify(d)
    finally:
        conn.close()


@app.route("/api/nutricao/cardapios/<int:cardapio_id>/aprovar", methods=["PATCH"])
@login_required
def nutricao_aprovar_cardapio(cardapio_id):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE nutricao_cardapios
            SET status='aprovado', aprovado_em=NOW()
            WHERE id=%s
            RETURNING cardapio_json
        """, (cardapio_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return jsonify({'error': 'não encontrado'}), 404
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route("/api/nutricao/cardapios/<int:cardapio_id>/editar-refeicao", methods=["PATCH"])
@login_required
def nutricao_editar_refeicao(cardapio_id):
    import json as _json
    data = request.get_json() or {}
    dia_nome = data.get('dia')           # ex: 'Segunda-feira'
    tipo = data.get('refeicao')          # ex: 'almoco'
    novo_conteudo = data.get('novo_conteudo', {})

    if not dia_nome or not tipo:
        return jsonify({'error': 'campos obrigatórios: dia, refeicao, novo_conteudo'}), 400

    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT cardapio_json FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'não encontrado'}), 404

        import copy
        cardapio = copy.deepcopy(row['cardapio_json']) if row['cardapio_json'] else {}
        dia_encontrado = False
        for dia in cardapio.get('dias', []):
            if dia.get('dia') == dia_nome:
                if 'refeicoes' not in dia:
                    dia['refeicoes'] = {}
                dia['refeicoes'][tipo] = novo_conteudo
                dia_encontrado = True
                break

        if not dia_encontrado:
            return jsonify({'error': f'dia não encontrado: {dia_nome}'}), 404

        cur.execute("""
            UPDATE nutricao_cardapios
            SET cardapio_json=%s, status='revisao'
            WHERE id=%s
        """, (_json.dumps(cardapio), cardapio_id))
        conn.commit()
        return jsonify({'ok': True, 'cardapio': cardapio})
    finally:
        conn.close()


@app.route("/api/nutricao/lista-compras/<int:cardapio_id>", methods=["POST"])
@login_required
def nutricao_gerar_lista_compras(cardapio_id):
    import json as _json

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT cardapio_json FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'cardápio não encontrado'}), 404

        cardapio_json = row['cardapio_json']

        # Resumo compacto do cardápio (só refeições, sem receitas/macros detalhados)
        resumo_dias = []
        for dia in (cardapio_json.get("dias") or []):
            ref = dia.get("refeicoes", {})
            resumo_dias.append(
                f"{dia.get('dia','')}: "
                f"café={ref.get('cafe_manha',{}).get('descricao','')} | "
                f"almoço={ref.get('almoco',{}).get('prato_principal','')} + {ref.get('almoco',{}).get('acompanhamento','')} + {ref.get('almoco',{}).get('verdura','')} | "
                f"lanche={ref.get('cafe_tarde',{}).get('descricao','')} | "
                f"janta={ref.get('janta',{}).get('prato_principal','')} + {ref.get('janta',{}).get('acompanhamento','')} | "
                f"suco={ref.get('suco_dia',{}).get('ingredientes',[])} | "
                f"fruta={ref.get('fruta_dia','')}"
            )
        cardapio_resumo = "\n".join(resumo_dias)

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system="Você é um assistente de compras. Analise o cardápio semanal e retorne APENAS JSON com a lista de compras consolidada, agrupada por categoria de supermercado, com quantidades somadas para a semana toda (2 pessoas). Sem markdown, sem texto adicional.",
            messages=[{"role": "user", "content": f"""Cardápio da semana (2 pessoas):
{cardapio_resumo}

Retorne JSON nessa estrutura:
{{
  "categorias": [
    {{"nome": "Proteínas", "emoji": "🥩", "itens": [{{"item": "Filé de frango", "quantidade": "1,5kg", "observacao": "para a semana toda"}}]}},
    {{"nome": "Carboidratos", "emoji": "🌾", "itens": [...]}},
    {{"nome": "Laticínios", "emoji": "🧀", "itens": [...]}},
    {{"nome": "Frutas", "emoji": "🍎", "itens": [...]}},
    {{"nome": "Verduras e Legumes", "emoji": "🥦", "itens": [...]}},
    {{"nome": "Lanches e Extras", "emoji": "🧁", "itens": [...]}},
    {{"nome": "Temperos e Condimentos", "emoji": "🧂", "itens": [...]}}
  ],
  "total_estimado_itens": 0,
  "dica": "dica rápida de organização das compras"
}}"""}]
        )

        texto = msg.content[0].text.strip()
        match = _re.search(r'```(?:json)?\s*([\s\S]*?)```', texto)
        if match:
            texto = match.group(1).strip()
        lista_json = _json.loads(texto)

        cur.execute("""
            UPDATE nutricao_cardapios
            SET lista_compras_json=%s WHERE id=%s
        """, (_json.dumps(lista_json), cardapio_id))
        conn.commit()

        return jsonify({'ok': True, 'lista': lista_json})
    except _json.JSONDecodeError as e:
        conn.rollback()
        return jsonify({'error': f'JSON inválido: {str(e)}'}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route("/api/nutricao/exportar-whatsapp/<int:cardapio_id>")
@login_required
def nutricao_exportar_whatsapp(cardapio_id):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT lista_compras_json, semana_inicio, semana_fim FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row or not row['lista_compras_json']:
            return jsonify({'error': 'lista de compras não gerada ainda'}), 404

        lista = row['lista_compras_json']
        sem_ini = str(row['semana_inicio'])[:10] if row['semana_inicio'] else '—'
        sem_fim = str(row['semana_fim'])[:10] if row['semana_fim'] else '—'

        # Formatar datas dd/mm
        def fmt_data(d):
            if not d or d == '—':
                return d or '—'
            parts = d.split('-')
            return f"{parts[2]}/{parts[1]}" if len(parts) == 3 else d

        linhas = [
            f"🛒 *LISTA DE COMPRAS — Semana {fmt_data(sem_ini)} a {fmt_data(sem_fim)}*",
            "_Cardápio de hipertrofia para 2 pessoas_",
            "",
        ]

        for cat in lista.get('categorias', []):
            if not cat.get('itens'):
                continue
            linhas.append(f"{cat.get('emoji', '•')} *{cat['nome'].upper()}*")
            for item in cat['itens']:
                qtd = f" — {item['quantidade']}" if item.get('quantidade') else ''
                linhas.append(f"☐ {item.get('item', '?')}{qtd}")
            linhas.append("")

        if lista.get('dica'):
            linhas.append(f"💡 _{lista['dica']}_")
            linhas.append("")

        linhas.append("✅ _Gerado pelo Jake OS • Piloti_")

        return jsonify({'texto': '\n'.join(linhas), 'sucesso': True})
    finally:
        conn.close()


@app.route("/api/nutricao/exportar-pdf/<int:cardapio_id>")
@login_required
def nutricao_exportar_pdf(cardapio_id):
    from html import escape as _he
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row:
            return "Cardápio não encontrado", 404

        cardapio = row['cardapio_json'] or {}
        sem_ini = str(row['semana_inicio'])[:10] if row['semana_inicio'] else ''
        sem_fim = str(row['semana_fim'])[:10] if row['semana_fim'] else ''

        def fmt_data(d):
            if not d or d == '—':
                return d or '—'
            parts = d.split('-')
            return f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else d

        # Montar HTML das refeições por dia
        dias_html = ""
        for dia in cardapio.get('dias', []):
            r = dia.get('refeicoes', {})
            dias_html += f"""
            <div class="dia">
              <h3 class="dia-nome">{_he(str(dia.get('dia', '') or ''))}</h3>
              <table>
                <thead><tr><th>Refeição</th><th>Descrição</th><th>Bruno</th><th>Camila</th></tr></thead>
                <tbody>"""

            for tipo, label in [('cafe_manha','☀️ Café da Manhã'), ('almoco','🍽 Almoço'),
                                 ('cafe_tarde','🫖 Café da Tarde'), ('janta','🌙 Janta')]:
                ref = r.get(tipo, {})
                if not ref: continue
                if tipo in ('almoco', 'janta'):
                    descricao = f"{_he(str(ref.get('prato_principal','—') or '—'))}<br><small>{_he(str(ref.get('acompanhamento','') or ''))} {_he(str(ref.get('verdura','') or ''))}</small>"
                    congelavel = ' 🧊' if ref.get('congelavel') else ''
                    descricao += f"<br><small>{_he(str(ref.get('tempo_preparo','') or ''))}{congelavel}</small>"
                    bruno_info = f"{_he(str(ref.get('bruno',{}).get('porcao','—') or '—'))}<br><small>{_he(str(ref.get('bruno',{}).get('calorias','—') or '—'))} kcal | {_he(str(ref.get('bruno',{}).get('proteina','—') or '—'))}</small>"
                    camila_info = f"{_he(str(ref.get('camila',{}).get('porcao','—') or '—'))}<br><small>{_he(str(ref.get('camila',{}).get('calorias','—') or '—'))} kcal | {_he(str(ref.get('camila',{}).get('proteina','—') or '—'))}</small>"
                else:
                    descricao = _he(str(ref.get('descricao', '—') or '—'))
                    congelavel = ' 🧊' if ref.get('congelavel') else ''
                    descricao += congelavel
                    bruno_info = f"{_he(str(ref.get('bruno',{}).get('porcao','—') or '—'))}<br><small>{_he(str(ref.get('bruno',{}).get('calorias','—') or '—'))} kcal</small>"
                    camila_info = f"{_he(str(ref.get('camila',{}).get('porcao','—') or '—'))}<br><small>{_he(str(ref.get('camila',{}).get('calorias','—') or '—'))} kcal</small>"

                dias_html += f"<tr><td><b>{label}</b></td><td>{descricao}</td><td>{bruno_info}</td><td>{camila_info}</td></tr>"

            suco = r.get('suco_dia', {})
            fruta = r.get('fruta_dia', '')
            if suco:
                ingredientes = ', '.join(_he(str(ing or '')) for ing in suco.get('ingredientes', []))
                dias_html += f"<tr><td>🥤 Suco</td><td>{_he(str(suco.get('nome','—') or '—'))}<br><small>{ingredientes}</small></td><td colspan='2'>{_he(str(suco.get('beneficio','') or ''))}</td></tr>"
            if fruta:
                dias_html += f"<tr><td>🍎 Fruta</td><td colspan='3'>{_he(str(fruta or ''))}</td></tr>"

            dias_html += "</tbody></table></div>"

        # Receitas detalhadas
        receitas_html = ""
        for rec in cardapio.get('receitas_detalhadas', []):
            ingredientes_li = ''.join(f"<li>{_he(str(i.get('item','') or ''))} — {_he(str(i.get('quantidade','') or ''))}</li>" for i in rec.get('ingredientes', []))
            passos_li = ''.join(f"<li>{_he(str(p or ''))}</li>" for p in rec.get('modo_preparo', []))
            congelavel = ' 🧊 Congelável' if rec.get('congelavel') else ''
            receitas_html += f"""
            <div class="receita">
              <h4>{_he(str(rec.get('nome','') or ''))}{congelavel}</h4>
              <p><small>⏱ {_he(str(rec.get('tempo','') or ''))} • Rende: {_he(str(rec.get('rende','') or ''))} • Freezer: {_he(str(rec.get('validade_freezer','') or ''))}</small></p>
              <div class="receita-cols">
                <div><strong>Ingredientes</strong><ul>{ingredientes_li}</ul></div>
                <div><strong>Modo de Preparo</strong><ol>{passos_li}</ol></div>
              </div>
            </div>"""

        # Dicas
        dicas_html = ''.join(f"<li>{_he(str(d or ''))}</li>" for d in cardapio.get('dicas_preparo', []))

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Cardápio — {_he(fmt_data(sem_ini))} a {_he(fmt_data(sem_fim))}</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12px; color: #1a1a1a; margin: 0; padding: 20px; }}
  h1 {{ color: #2e7d32; font-size: 22px; margin-bottom: 4px; }}
  h2 {{ color: #388e3c; font-size: 16px; border-bottom: 2px solid #81c784; padding-bottom: 4px; margin-top: 24px; }}
  h3.dia-nome {{ background: #e8f5e9; padding: 8px 12px; color: #1b5e20; font-size: 14px; margin: 16px 0 6px; border-left: 4px solid #43a047; }}
  h4 {{ color: #2e7d32; margin: 10px 0 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 11px; }}
  th {{ background: #43a047; color: white; padding: 6px 8px; text-align: left; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }}
  tr:nth-child(even) td {{ background: #f9fbe7; }}
  .receita {{ background: #f1f8e9; border-radius: 6px; padding: 12px; margin-bottom: 12px; }}
  .receita-cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  ul, ol {{ padding-left: 18px; margin: 4px 0; }}
  li {{ margin-bottom: 2px; }}
  .dicas {{ background: #fff8e1; padding: 12px; border-radius: 6px; }}
  footer {{ text-align: center; color: #999; font-size: 10px; margin-top: 24px; border-top: 1px solid #eee; padding-top: 8px; }}
  @media print {{
    body {{ padding: 10px; }}
    h3.dia-nome {{ page-break-before: auto; }}
    .receita {{ page-break-inside: avoid; }}
  }}
</style>
</head>
<body>
  <h1>🥗 Cardápio Semanal</h1>
  <p><strong>Semana:</strong> {_he(fmt_data(sem_ini))} a {_he(fmt_data(sem_fim))} &nbsp;|&nbsp; <strong>Bruno &amp; Camila</strong> &nbsp;|&nbsp; Foco: Hipertrofia</p>
  <h2>📅 Cardápio Dia a Dia</h2>
  {dias_html}
  <h2>👨‍🍳 Receitas Detalhadas</h2>
  {receitas_html}
  <h2>💡 Dicas de Preparo e Congelamento</h2>
  <div class="dicas"><ul>{dicas_html}</ul></div>
  <footer>Gerado pelo Jake OS &nbsp;•&nbsp; Piloti &nbsp;•&nbsp; {_he(fmt_data(sem_ini))} a {_he(fmt_data(sem_fim))}</footer>
</body>
</html>"""

        from flask import Response
        return Response(
            html,
            mimetype='text/html',
            headers={'Content-Disposition': f'inline; filename=cardapio_{sem_ini}.html'}
        )
    finally:
        conn.close()


# ── DR: CRUD OFERTAS ──────────────────────────────────────────────────────────

@app.route("/api/dr/ofertas", methods=["GET"])
@login_required
def dr_listar_ofertas():
    try:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, nicho, tipo_funil, lp_url, quiz_url, "
            "created_at::text, updated_at::text FROM dr_ofertas ORDER BY updated_at DESC"
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dr/ofertas", methods=["POST"])
@login_required
def dr_criar_oferta():
    d = request.get_json() or {}
    if not d.get("nome"):
        return jsonify({"error": "Campo obrigatório: nome"}), 400
    try:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO dr_ofertas
               (nome, nicho, angulo, hook, promessa, publico, contexto_raw, tipo_funil)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (d["nome"], d.get("nicho"), d.get("angulo"), d.get("hook"),
             d.get("promessa"), d.get("publico"), d.get("contexto_raw"), d.get("tipo_funil", "vsl_direto"))
        )
        novo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dr/ofertas/<int:oid>", methods=["GET"])
@login_required
def dr_carregar_oferta(oid):
    try:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM dr_ofertas WHERE id = %s", (oid,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "Oferta não encontrada"}), 404
        return jsonify(dict(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dr/ofertas/<int:oid>", methods=["DELETE"])
@login_required
def dr_deletar_oferta(oid):
    try:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM dr_ofertas WHERE id = %s", (oid,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dr/gerar-copy", methods=["POST"])
@login_required
def dr_gerar_copy():
    import json as _json
    d = request.get_json() or {}
    oferta_id = d.get("oferta_id")
    contexto  = d.get("contexto_raw", "")
    produto   = d.get("produto", d.get("nome", ""))
    publico   = d.get("publico", "")
    nicho     = d.get("nicho", "")
    angulo    = d.get("angulo", "")
    hook      = d.get("hook", "")
    promessa  = d.get("promessa", "")
    tipo_funil = d.get("tipo_funil", "vsl_direto")

    prompt = f"""Você é um especialista em Direct Response e copywriting de alta conversão para o mercado brasileiro.

Analise o contexto da oferta vencedora abaixo e gere copy adaptada para o produto do usuário.
Escreva em português do Brasil. Seja direto, persuasivo e use linguagem de conversão real.

CONTEXTO DA OFERTA VENCEDORA:
{contexto}

PRODUTO: {produto}
NICHO: {nicho}
ÂNGULO: {angulo}
HOOK PRINCIPAL: {hook}
PROMESSA CENTRAL: {promessa}
PÚBLICO-ALVO: {publico}
TIPO DE FUNIL: {tipo_funil}

Retorne APENAS um JSON válido com esta estrutura exata (sem texto antes ou depois, sem markdown):
{{
  "copy": {{
    "headline": "headline principal impactante",
    "subheadline": "subheadline de suporte",
    "bullets": ["benefício 1", "benefício 2", "benefício 3", "benefício 4", "benefício 5"],
    "cta": "texto do botão CTA",
    "anuncio_curto": "copy curta para anúncio (até 125 chars)",
    "anuncio_medio": "copy média para anúncio (até 300 chars)",
    "anuncio_longo": "copy longa para anúncio (até 600 chars)"
  }},
  "script_vsl": {{
    "hook": "abertura que para o scroll (15-30 segundos)",
    "problema": "amplificação do problema que o público enfrenta",
    "agitacao": "consequências de não resolver o problema agora",
    "solucao": "apresentação da solução (produto) como saída",
    "prova": "provas sociais, resultados, depoimentos sugeridos",
    "oferta": "detalhes da oferta: preço, bônus, o que está incluso",
    "garantia": "garantia e redução de risco",
    "cta": "chamada para ação final urgente"
  }},
  "angulos": [
    {{"titulo": "Ângulo 1", "descricao": "descrição do ângulo", "hook": "hook para este ângulo"}},
    {{"titulo": "Ângulo 2", "descricao": "descrição do ângulo", "hook": "hook para este ângulo"}},
    {{"titulo": "Ângulo 3", "descricao": "descrição do ângulo", "hook": "hook para este ângulo"}}
  ]
}}"""

    try:
        client = _anthropic_client_46()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        result = _json.loads(raw)

        if oferta_id:
            conn = _get_db()
            cur = conn.cursor()
            cur.execute(
                """UPDATE dr_ofertas SET copy_json=%s, script_vsl=%s, angulos_json=%s,
                   updated_at=NOW() WHERE id=%s""",
                (_json.dumps(result.get("copy", {})),
                 _json.dumps(result.get("script_vsl", {})),
                 _json.dumps(result.get("angulos", [])),
                 oferta_id)
            )
            conn.commit()
            conn.close()

        return jsonify(result)
    except _json.JSONDecodeError as e:
        return jsonify({"error": f"Claude retornou JSON inválido: {str(e)}", "raw": raw[:300]}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _dr_fetch_html(url):
    """Faz fetch de uma URL e retorna (html, erro)."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=10
        )
        if resp.status_code != 200:
            return None, f"Status HTTP {resp.status_code}"
        html = resp.text
        import re as _re
        texto_visivel = _re.sub(r'<[^>]+>', ' ', html)
        texto_visivel = _re.sub(r'\s+', ' ', texto_visivel).strip()
        if len(texto_visivel) < 500:
            return None, "Conteúdo insuficiente — página pode usar renderização JS pesada"
        return html, None
    except requests.exceptions.Timeout:
        return None, "Timeout ao carregar URL"
    except Exception as e:
        return None, str(e)


def _dr_prompt_lp(contexto_oferta, hotmart_url, video_url, pixel_id, preco, estrutura_original=None):
    """Monta o prompt para geração de LP HTML completa."""
    ref = f"\nESTRUTURA DA LP ORIGINAL PARA INSPIRAÇÃO:\n{estrutura_original[:3000]}" if estrutura_original else ""
    return f"""Você é um especialista em Direct Response e desenvolvimento web.
Gere uma landing page HTML completa, autocontida e mobile-first para uma oferta de DR.

CONTEXTO DA OFERTA:
{contexto_oferta}

CONFIGURAÇÕES:
- Link do Checkout (Hotmart): {hotmart_url}
- URL do Vídeo VSL: {video_url}
- Pixel ID Meta: {pixel_id}
- Preço: {preco}
{ref}

REQUISITOS OBRIGATÓRIOS:
1. HTML único autocontido (CSS inline + JS inline, sem dependências externas)
2. Mobile-first (breakpoint 768px)
3. Meta Pixel no <head> com o Pixel ID fornecido (fbq('init', '{pixel_id}'); fbq('track', 'PageView');)
4. Player de vídeo: embed do YouTube ou Vimeo com o URL fornecido
5. Seção hero: headline + subheadline impactantes baseadas no contexto
6. Lista de benefícios (bullets) — mínimo 5 itens
7. 3 depoimentos/provas sociais com nome, resultado e texto
8. Timer de escassez: usar localStorage para definir data de expiração fixa (72h da primeira visita). NÃO usar countdown que reseta — é dark pattern.
   JS para timer:
   var KEY='dr_exp'; var stored=localStorage.getItem(KEY);
   var exp=stored?new Date(stored):new Date(Date.now()+72*3600000);
   if(!stored) localStorage.setItem(KEY,exp.toISOString());
9. Bloco de preço com botão CTA → {hotmart_url}?utm_source=meta&utm_medium=cpc&utm_campaign=dr
10. Paleta dark moderna: fundo escuro (#0a0a0a ou similar), destaques em cor vibrante (verde, azul ou laranja)
11. Sem frameworks CSS externos (sem Bootstrap, sem Tailwind)
12. Tag <title> com o nome do produto

Retorne APENAS o código HTML completo, começando com <!DOCTYPE html> e terminando com </html>.
Sem texto antes ou depois, sem markdown, sem explicações."""


@app.route("/api/dr/clonar-lp", methods=["POST"])
@login_required
def dr_clonar_lp():
    import json as _json
    d = request.get_json() or {}
    url_original = d.get("url_original", "")
    oferta_id    = d.get("oferta_id")
    hotmart_url  = d.get("hotmart_url", "#")
    video_url    = d.get("video_url", "")
    pixel_id     = d.get("pixel_id", "")
    preco        = d.get("preco", "")

    contexto = d.get("contexto_raw") or ""
    if not contexto and oferta_id:
        try:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("SELECT * FROM dr_ofertas WHERE id=%s", (oferta_id,))
            row = cur.fetchone(); conn.close()
            if row:
                o = dict(row)
                contexto = f"Produto: {o.get('nome')}\nNicho: {o.get('nicho')}\nÂngulo: {o.get('angulo')}\nHook: {o.get('hook')}\nPromessa: {o.get('promessa')}\nPúblico: {o.get('publico')}"
        except Exception:
            pass

    fallback_msg = None
    estrutura_original = None

    if url_original:
        html_orig, erro = _dr_fetch_html(url_original)
        if erro:
            fallback_msg = f"Não foi possível carregar a URL original ({erro}) — LP gerada do zero com base no contexto."
        else:
            estrutura_original = html_orig

    try:
        prompt = _dr_prompt_lp(contexto, hotmart_url, video_url, pixel_id, preco, estrutura_original)
        client = _anthropic_client_46()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )
        lp_html = msg.content[0].text.strip()
        if lp_html.startswith("```"):
            lp_html = lp_html.split("```")[1]
            if lp_html.startswith("html"): lp_html = lp_html[4:]
            lp_html = lp_html.rsplit("```", 1)[0].strip()

        if oferta_id:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("UPDATE dr_ofertas SET lp_html=%s, updated_at=NOW() WHERE id=%s", (lp_html, oferta_id))
            conn.commit(); conn.close()

        return jsonify({"html": lp_html, "fallback_msg": fallback_msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dr/gerar-lp", methods=["POST"])
@login_required
def dr_gerar_lp():
    import json as _json
    d = request.get_json() or {}
    oferta_id   = d.get("oferta_id")
    hotmart_url = d.get("hotmart_url", "#")
    video_url   = d.get("video_url", "")
    pixel_id    = d.get("pixel_id", "")
    preco       = d.get("preco", "")
    contexto    = d.get("contexto_raw", "")

    if not contexto and oferta_id:
        try:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("SELECT * FROM dr_ofertas WHERE id=%s", (oferta_id,))
            row = cur.fetchone(); conn.close()
            if row:
                o = dict(row)
                contexto = f"Produto: {o.get('nome')}\nNicho: {o.get('nicho')}\nÂngulo: {o.get('angulo')}\nHook: {o.get('hook')}\nPromessa: {o.get('promessa')}\nPúblico: {o.get('publico')}"
                if o.get('copy_json'):
                    try:
                        cp = _json.loads(o['copy_json']) if isinstance(o['copy_json'], str) else o['copy_json']
                        contexto += f"\nHeadline: {cp.get('headline','')}\nBullets: {'; '.join(cp.get('bullets',[]))}"
                    except Exception:
                        pass
        except Exception:
            pass

    try:
        prompt = _dr_prompt_lp(contexto, hotmart_url, video_url, pixel_id, preco)
        client = _anthropic_client_46()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )
        lp_html = msg.content[0].text.strip()
        if lp_html.startswith("```"):
            lp_html = lp_html.split("```")[1]
            if lp_html.startswith("html"): lp_html = lp_html[4:]
            lp_html = lp_html.rsplit("```", 1)[0].strip()

        if oferta_id:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("UPDATE dr_ofertas SET lp_html=%s, updated_at=NOW() WHERE id=%s", (lp_html, oferta_id))
            conn.commit(); conn.close()

        return jsonify({"html": lp_html})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dr/deploy-lp", methods=["POST"])
@login_required
def dr_deploy_lp():
    d = request.get_json() or {}
    html = d.get("html", "")
    oferta_id = d.get("oferta_id")
    if not html:
        return jsonify({"error": "HTML vazio"}), 400
    ok, url, info = _deploy_to_vercel("jake-dr-lp", html)
    if not ok:
        return jsonify({"error": f"Deploy falhou: {info}"}), 500
    if oferta_id:
        try:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("UPDATE dr_ofertas SET lp_url=%s, updated_at=NOW() WHERE id=%s", (url, oferta_id))
            conn.commit(); conn.close()
        except Exception:
            pass
    return jsonify({"url": url, "ok": True})


def _dr_prompt_quiz(contexto_oferta, redirect_url, estrutura_original=None):
    """Monta prompt para geração de quiz HTML completo."""
    ref = f"\nESTRUTURA DO QUIZ ORIGINAL PARA INSPIRAÇÃO:\n{estrutura_original[:3000]}" if estrutura_original else ""
    return f"""Você é especialista em quiz funnels de alta conversão para Direct Response.
Gere um quiz HTML completo, autocontido e mobile-first.

CONTEXTO DA OFERTA:
{contexto_oferta}

URL DE REDIRECT (após quiz): {redirect_url}
{ref}

REQUISITOS:
1. HTML único autocontido (CSS inline + JS inline)
2. Mobile-first, design atrativo e moderno
3. 4 perguntas com 3-4 opções cada (baseadas no nicho/problema da oferta)
4. Barra de progresso visual (ex: "Pergunta 2 de 4")
5. Campo de email ANTES de revelar o resultado (label: "Para onde enviar sua análise personalizada?")
6. 3 perfis de resultado baseados nas respostas (Perfil A, B, C)
7. Cada perfil tem: título, texto descritivo, e botão CTA → {redirect_url}
8. JS puro para lógica de navegação entre perguntas e cálculo de perfil
9. Animação suave de transição entre perguntas (fade ou slide)
10. Paleta de cores vibrante e moderna, fundo escuro ou claro (escolha o que converter mais)
11. Sem frameworks externos

Retorne APENAS o código HTML completo começando com <!DOCTYPE html>.
Sem texto antes ou depois, sem markdown."""


@app.route("/api/dr/clonar-quiz", methods=["POST"])
@login_required
def dr_clonar_quiz():
    d = request.get_json() or {}
    url_original = d.get("url_original", "")
    oferta_id    = d.get("oferta_id")
    redirect_url = d.get("redirect_url", "#")

    contexto = d.get("contexto_raw", "")
    if not contexto and oferta_id:
        try:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("SELECT * FROM dr_ofertas WHERE id=%s", (oferta_id,))
            row = cur.fetchone(); conn.close()
            if row:
                o = dict(row)
                contexto = f"Produto: {o.get('nome')}\nNicho: {o.get('nicho')}\nÂngulo: {o.get('angulo')}\nPromessa: {o.get('promessa')}\nPúblico: {o.get('publico')}"
        except Exception:
            pass

    fallback_msg = None
    estrutura_original = None

    if url_original:
        html_orig, erro = _dr_fetch_html(url_original)
        if erro:
            fallback_msg = f"Não foi possível carregar o quiz original ({erro}) — quiz gerado com estrutura base."
        else:
            estrutura_original = html_orig

    try:
        prompt = _dr_prompt_quiz(contexto, redirect_url, estrutura_original)
        client = _anthropic_client_46()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )
        quiz_html = msg.content[0].text.strip()
        if quiz_html.startswith("```"):
            quiz_html = quiz_html.split("```")[1]
            if quiz_html.startswith("html"): quiz_html = quiz_html[4:]
            quiz_html = quiz_html.rsplit("```", 1)[0].strip()

        if oferta_id:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("UPDATE dr_ofertas SET quiz_html=%s, updated_at=NOW() WHERE id=%s", (quiz_html, oferta_id))
            conn.commit(); conn.close()

        return jsonify({"html": quiz_html, "fallback_msg": fallback_msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dr/deploy-quiz", methods=["POST"])
@login_required
def dr_deploy_quiz():
    d = request.get_json() or {}
    html = d.get("html", "")
    oferta_id = d.get("oferta_id")
    if not html:
        return jsonify({"error": "HTML vazio"}), 400
    ok, url, info = _deploy_to_vercel("jake-dr-quiz", html)
    if not ok:
        return jsonify({"error": f"Deploy falhou: {info}"}), 500
    if oferta_id:
        try:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("UPDATE dr_ofertas SET quiz_url=%s, updated_at=NOW() WHERE id=%s", (url, oferta_id))
            conn.commit(); conn.close()
        except Exception:
            pass
    return jsonify({"url": url, "ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    ip   = _local_ip()
    print(f"\n  Jake OS")
    print(f"  Local : http://localhost:{port}")
    if ip:
        print(f"  Rede  : http://{ip}:{port}")
    print(f"  Login : {_ADMIN_EMAIL} / {_ADMIN_PASSWORD}")
    print("  Mantenha esta janela aberta.\n")
    if os.environ.get("OPEN_BROWSER", "").lower() in ("1", "true", "yes"):
        threading.Thread(target=_open_browser_delayed, args=(port,), daemon=True).start()
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    _init_rotina_tables()
    _init_social_brief_tables()
    _init_nutricao_tables()
    _init_dr_tables()
    _init_aportes_table()
    _init_ativos_personalizados_table()
    # APScheduler: Social Brief automático toda segunda às 08h
    try:
        from apscheduler.schedulers.background import BackgroundScheduler as _BGScheduler
        def _job_social_brief():
            with app.app_context():
                from datetime import date as _dj, timedelta as _tdj
                conn = _get_db()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM social_brief_clientes WHERE ativo=TRUE ORDER BY nome")
                    clientes = [dict(r) for r in cur.fetchall()]
                finally:
                    conn.close()
                if not clientes:
                    print("[Social Brief] Nenhum cliente ativo")
                    return
                todos_dados = []
                for cliente in clientes:
                    try:
                        dm = _sb_buscar_meta_ads(cliente.get("meta_account_id",""), cliente.get("meta_agency","piloti"))
                        pt = _sb_ler_perfil_html(cliente["slug"])
                        pq = _sb_buscar_concorrentes(cliente.get("nicho",""), cliente.get("concorrentes") or [])
                        an = _sb_gerar_analise_claude(cliente, dm, pt, pq.get("conteudo_pesquisa",""))
                        todos_dados.append({"cliente": cliente, "analise": an, "dados_meta": dm})
                        time.sleep(2)
                    except Exception as e:
                        print(f"[Social Brief] Erro cliente {cliente['nome']}: {e}")
                if todos_dados:
                    hoje = _dj.today()
                    seg = hoje - _tdj(days=hoje.weekday())
                    html = _sb_gerar_html_portal(todos_dados, seg.strftime("%d/%m/%Y"), (seg + _tdj(days=6)).strftime("%d/%m/%Y"))
                    # Salva geração no banco
                    geracao_id = None
                    conn2 = _get_db()
                    try:
                        cur2 = conn2.cursor()
                        cur2.execute(
                            """INSERT INTO social_brief_geracoes
                               (semana_inicio, semana_fim, html_completo, publicado, clientes_incluidos)
                               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                            (
                                seg.isoformat(),
                                (seg + _tdj(days=6)).isoformat(),
                                html,
                                False,
                                json.dumps([{"id": d["cliente"]["id"], "nome": d["cliente"]["nome"]} for d in todos_dados]),
                            )
                        )
                        geracao_id = cur2.fetchone()["id"]
                        for item in todos_dados:
                            cur2.execute(
                                """INSERT INTO social_brief_cliente_dados
                                   (geracao_id, cliente_id, analise_json, dados_meta)
                                   VALUES (%s, %s, %s, %s)""",
                                (geracao_id, item["cliente"]["id"],
                                 json.dumps(item["analise"]), json.dumps(item["dados_meta"]))
                            )
                        conn2.commit()
                    except Exception as e:
                        conn2.rollback()
                        print(f"[Social Brief] Erro ao salvar no banco: {e}")
                    finally:
                        conn2.close()
                    # Publica no Surge e atualiza URL
                    try:
                        url = _sb_publicar_surge(html)
                        print(f"[Social Brief] Portal publicado: {url}")
                        if geracao_id:
                            conn3 = _get_db()
                            try:
                                cur3 = conn3.cursor()
                                cur3.execute(
                                    "UPDATE social_brief_geracoes SET surge_url=%s, publicado=TRUE WHERE id=%s",
                                    (url, geracao_id)
                                )
                                conn3.commit()
                            finally:
                                conn3.close()
                    except Exception as e:
                        print(f"[Social Brief] Erro ao publicar: {e}")
        _sched = _BGScheduler(timezone="America/Sao_Paulo")
        _sched.add_job(_job_social_brief, "cron", day_of_week="mon", hour=8, minute=0)
        _sched.start()
        print("[Social Brief] Agendador ativo — toda segunda às 08h")
    except Exception as _sched_err:
        print(f"[Social Brief] Aviso: agendador não iniciado — {_sched_err}")
    app.run(host="0.0.0.0", port=port, debug=debug)
