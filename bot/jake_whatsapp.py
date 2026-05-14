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
    verificar_conexao,
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

Sempre chame o Bruno de 'Patrao'."""

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
- clientes: lista exatamente como o usuário escreveu, em minúsculas"""


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
        cur.execute("SELECT id, nome, agencia, account_id, token_key FROM ad_client_profiles ORDER BY nome")
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

def _eh_financeiro(texto: str) -> bool:
    t = texto.lower()
    return any(k in t for k in _KEYWORDS_FINANCEIRO)

def _eh_grupo(texto: str) -> bool:
    t = texto.lower()
    return sum(1 for k in _KEYWORDS_GRUPO if k in t) >= 2

# ── Handler de mensagem ────────────────────────────────────────────────────────

def processar_mensagem(sender_jid: str, texto: str):
    """Processa mensagem do Bruno e envia resposta."""
    chat_id = jid_to_chat_id(sender_jid)
    historico = carregar_historico(chat_id)

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

    # Intencao: financeiro - injeta contexto no prompt
    prompt = PROMPT_ANALISTA
    mensagem_claude = texto
    if _eh_financeiro(texto):
        ctx = financeiro_context()
        mensagem_claude = f"DADOS FINANCEIROS DO SISTEMA:\n{ctx}\n\nPERGUNTA DO PATRAO: {texto}"

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

    if not texto:
        return jsonify({"ok": True})

    # Processar em background para nao bloquear o webhook
    import threading
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

def _configurar_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=SP_TZ)

    # Resumo Gestor as 17h todos os dias
    scheduler.add_job(
        _enviar_resumo_gestor,
        CronTrigger(hour=17, minute=0, timezone=SP_TZ),
        id="resumo_gestor",
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
