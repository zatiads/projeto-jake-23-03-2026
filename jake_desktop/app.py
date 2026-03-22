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

from flask import Flask, render_template, jsonify, request, session, redirect, url_for

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
    awareness = data.get("awareness") or "problema"
    trigger   = data.get("trigger") or "prova"
    if len(theme) < 3:
        return jsonify({"error": "Tema muito curto (mínimo 3 caracteres)."}), 400
    tone_hint = _CAROUSEL_TONE.get(tone, _CAROUSEL_TONE["elegante"])
    awareness_hint = _CAROUSEL_AWARENESS.get(awareness, _CAROUSEL_AWARENESS["problema"])
    trigger_hint   = _CAROUSEL_TRIGGER.get(trigger, _CAROUSEL_TRIGGER["prova"])

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=_CAROUSEL_SYSTEM,
            messages=[{
                "role": "user",
                "content": "\n".join([
                    f"Tema: {theme}",
                    f"Tom solicitado: {tone}. {tone_hint}",
                    f"Nível de consciência do público: {awareness_hint}",
                    f"Gatilho mental a priorizar: {trigger_hint}",
                    "Gere os 7 slides com profundidade real de conteúdo.",
                    "Cada subheadline deve ensinar algo específico, com dados ou exemplos concretos.",
                    'Retorne SOMENTE o JSON: {"slides":[...7 itens...]}',
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
        if len(slides) != 7:
            raise ValueError(f"Esperava 7 slides, recebi {len(slides)}")
        slides_texto = "\n\n".join(
            f"**Slide {i+1}:** {str(s)}" for i, s in enumerate(slides)
        )
        brain.salvar(
            modulo="Carrossel",
            titulo=f"Carrossel {theme}",
            inputs={
                "tema": theme,
                "tom": tone,
                "awareness": awareness,
                "gatilho": trigger,
            },
            output=slides_texto,
            model="claude-sonnet-4-5",
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
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=_COPYS_SYSTEM,
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

# ── API: Análise IA para Relatórios ──────────────────────────────────────────
@app.route("/api/relatorios/analise", methods=["POST"])
@login_required
def api_relatorios_analise():
    data    = request.get_json() or {}
    nome    = (data.get("nome") or "").strip()
    metricas = data.get("metricas") or {}

    client = _anthropic_client()
    if not client:
        return jsonify({"analise": ""})

    metricas_str = "\n".join(f"- {k}: {v}" for k, v in metricas.items())
    prompt = (
        f"Você é analista de tráfego pago. Gere uma análise BREVE (2-3 frases, máximo 120 palavras) "
        f"sobre os resultados das campanhas Meta Ads de '{nome}' nos últimos 7 dias.\n\n"
        f"Dados:\n{metricas_str}\n\n"
        f"Seja direto, profissional, em português brasileiro. "
        f"Destaque o principal resultado e dê UMA recomendação prática. "
        f"NÃO use markdown, asteriscos, negrito ou formatação. Apenas texto corrido simples."
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=220,
            messages=[{"role": "user", "content": prompt}],
        )
        return jsonify({"analise": (msg.content[0].text or "").strip()})
    except Exception as exc:
        return jsonify({"analise": "", "error": str(exc)})


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


def _generate_creative_images(mode: str, image_engine: str, prompt: str, image_file):
    """
    Gera até 5 imagens (ou reutiliza a mesma) dependendo do modo.
    Retorna lista de data URLs.
    """
    images: list[str] = []

    # Upload: devolve a mesma foto base em todos os criativos (lado a lado com as promessas).
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

    return jsonify({
        "creatives": creatives,
        "meta": {
            "mode": mode,
            "image_engine": image_engine,
            "text_engine": text_engine,
            "campaign_focus": campaign_focus,
        },
    })

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
    data   = request.get_json() or {}
    prompt = (data.get("prompt") or "").strip()
    style_visual = (data.get("style_visual") or "").strip() or None
    mix_reality  = (data.get("mix_reality") or "").strip() or None
    palette      = (data.get("palette") or "").strip() or None

    if len(prompt) < 5:
        return jsonify({"error": "Prompt muito curto."}), 400

    replicate_token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not replicate_token:
        return jsonify({"error": "Configure REPLICATE_API_TOKEN no .env para gerar imagens."}), 500

    style_suffix = _carousel_image_style_suffix(style_visual, mix_reality, palette)
    try:
        image_url = _generate_flux(prompt, replicate_token, style_suffix=style_suffix)
        data_url  = _url_to_data_url(image_url)
        return jsonify({"dataUrl": data_url, "prompt": prompt, "model": "flux-1.1-pro"})
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

    prompt = f"""Você é Jake, o assistente financeiro pessoal. Analise os dados abaixo e forneça
um parágrafo direto, honesto e perspicaz sobre a saúde financeira do usuário em {mes}.
Use linguagem objetiva e tom de consultor financeiro profissional. Máximo de 3 parágrafos curtos.

Dados de {mes}:
- Receita total: R$ {receita:,.2f}
- Despesas totais: R$ {despesas:,.2f}
- Saldo: R$ {saldo:,.2f}
- Taxa de comprometimento: {(despesas/receita*100) if receita else 0:.1f}% da receita
- Comparativo: receita anterior R$ {receita_ant:,.2f} / despesas anteriores R$ {desp_ant:,.2f}
{var_receita}

Seja específico com os números. Dê pelo menos 1 recomendação prática."""

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
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=_SITE_ARCH_SYSTEM,
            messages=[{"role": "user", "content": user_instructions}],
        )
        html = (msg.content[0].text or "").strip()
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


@app.route("/api/criativos/expandir-prompt", methods=["POST"])
@login_required
def criativos_expandir_prompt():
    d = request.get_json() or {}
    prompt = (d.get("prompt") or "").strip()
    modo   = d.get("modo", "criativo")
    tipo   = d.get("tipo", "imagem")
    if not prompt:
        return jsonify({"error": "Campo 'prompt' obrigatório"}), 400
    if modo not in _CRIATIVOS_MODOS:
        return jsonify({"error": f"modo inválido. Válidos: {list(_CRIATIVOS_MODOS)}"}), 400

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    system = _CRIATIVOS_SYSTEM_PROMPTS[modo]
    tipo_hint = " Optimize for motion, camera movement, and temporal consistency." if tipo == "video" else ""
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=system + tipo_hint,
            messages=[{"role": "user", "content": f"Expand this prompt: {prompt}"}],
        )
        prompt_expandido = msg.content[0].text.strip()
        brain.salvar(
            modulo="Criativos",
            titulo=f"Prompt expandido {modo} {tipo}",
            inputs={"prompt": prompt, "modo": modo, "tipo": tipo},
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
    prompt  = (d.get("prompt_expandido") or "").strip()
    modelo  = d.get("modelo", "flux-1.1-pro")
    if not prompt:
        return jsonify({"error": "prompt_expandido obrigatório"}), 400
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
        # Fallback polling (raro) — usa time já importado no topo do arquivo
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
        if status == "succeeded":
            out = pred.get("output")
            url = out[0] if isinstance(out, list) else out
        return jsonify({"status": status, "url": url, "error": pred.get("error")})
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
        cur.execute(
            "INSERT INTO creative_history (tipo,modo,modelo,prompt_original,prompt_expandido,url_resultado,folder_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (d["tipo"], d["modo"], d["modelo"], d["prompt_original"],
             d["prompt_expandido"], d["url_resultado"], d.get("folder_id"))
        )
        novo_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        conn.rollback()
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
    app.run(host="0.0.0.0", port=port, debug=debug)
