"""
whatsapp_handlers.py — Helpers para o bot WhatsApp do Jake.
Sem estado global — todas as funções são puras ou usam conexões efêmeras.
"""
import os
import json
import logging
from datetime import date, datetime

import requests
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# ── Config (lida do ambiente em tempo de chamada) ────────────────────────────

def _evo_base() -> str:
    return os.environ.get("EVOLUTION_BASE_URL", "http://localhost:8081").rstrip("/")

def _evo_key() -> str:
    return os.environ.get("EVOLUTION_API_KEY", "")

def _wa_instance() -> str:
    return os.environ.get("WA_INSTANCE", "jake")

def _db():
    url = os.environ.get("DATABASE_URL", "")
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)

# ── Envio de mensagens ────────────────────────────────────────────────────────

def send_text(jid: str, text: str) -> bool:
    """Envia mensagem de texto para um JID via Evolution API. Retorna True se OK."""
    url = f"{_evo_base()}/message/sendText/{_wa_instance()}"
    # v1.x usa número sem @s.whatsapp.net e payload com textMessage
    number = jid.split("@")[0] if "@" in jid else jid
    try:
        resp = requests.post(
            url,
            headers={"apikey": _evo_key(), "Content-Type": "application/json"},
            json={"number": number, "textMessage": {"text": text}},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"send_text failed to {jid}: {e}")
        return False

# ── Histórico no DB ───────────────────────────────────────────────────────────

def jid_to_chat_id(jid: str) -> int:
    """Converte JID WhatsApp em chat_id inteiro. Ex: '5511999@s.whatsapp.net' → 5511999"""
    return int(jid.split("@")[0])

def carregar_historico(chat_id: int, limite: int = 40) -> list:
    """Retorna lista [{role, content}] do DB para namespace 'whatsapp'."""
    try:
        conn = _db()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT role, content FROM conversa "
                "WHERE chat_id=%s AND namespace='whatsapp' "
                "ORDER BY criado_em DESC LIMIT %s",
                (chat_id, limite),
            )
            rows = cur.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"carregar_historico error: {e}")
        return []

def salvar_mensagem(chat_id: int, role: str, content: str):
    """Persiste mensagem no DB com namespace 'whatsapp'."""
    try:
        conn = _db()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO conversa (chat_id, role, content, namespace) VALUES (%s,%s,%s,'whatsapp')",
                (chat_id, role, content),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"salvar_mensagem error: {e}")

# ── Grupos ────────────────────────────────────────────────────────────────────

def get_grupos() -> list:
    """
    Carrega config de grupos. Tenta config/wa_grupos.json primeiro,
    depois WA_GRUPOS_JSON do .env. Retorna lista de dicts.
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "wa_grupos.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao ler wa_grupos.json: {e}")

    raw = os.environ.get("WA_GRUPOS_JSON", "[]")
    try:
        return json.loads(raw)
    except Exception:
        return []

def encontrar_grupo(nome: str) -> dict | None:
    """Busca grupo por nome (case-insensitive). Retorna dict ou None."""
    nome_lower = nome.strip().lower()
    for g in get_grupos():
        if g.get("nome", "").lower() == nome_lower:
            return g
    return None

# ── Resumo Gestor IA ──────────────────────────────────────────────────────────

def resumo_gestor() -> str:
    """
    Consulta gestor_varreduras + gestor_acoes do dia e formata resumo com emojis.
    Retorna string pronta para enviar via WhatsApp.
    """
    hoje = date.today()
    try:
        conn = _db()
        try:
            cur = conn.cursor()

            # Varreduras do dia
            cur.execute(
                """
                SELECT contas_total, contas_ok, contas_acao, contas_erro, status
                FROM gestor_varreduras
                WHERE executado_em::date = %s
                ORDER BY executado_em DESC
                LIMIT 5
                """,
                (hoje,),
            )
            varreduras = cur.fetchall()

            # Ações do dia
            cur.execute(
                """
                SELECT ga.tipo, ga.entidade_nome, acp.nome as cliente_nome, ga.status
                FROM gestor_acoes ga
                JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
                WHERE ga.executado_em::date = %s
                ORDER BY ga.executado_em DESC
                LIMIT 20
                """,
                (hoje,),
            )
            acoes = cur.fetchall()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"resumo_gestor DB error: {e}")
        return "Erro ao consultar o banco de dados."

    if not varreduras and not acoes:
        return "Sem atividades registradas hoje."

    linhas = [f"*Resumo do dia — Jake OS* ({hoje.strftime('%d/%m')})"]

    if varreduras:
        v = varreduras[0]
        linhas.append(
            f"Varredura: {v['contas_ok']}/{v['contas_total']} contas OK"
            + (f", {v['contas_acao']} ações" if v["contas_acao"] else "")
            + (f", {v['contas_erro']} erros" if v["contas_erro"] else "")
        )

    if acoes:
        sucesso = sum(1 for a in acoes if a["status"] == "sucesso")
        erro = sum(1 for a in acoes if a["status"] != "sucesso")
        linhas.append(f"{sucesso} ações executadas" + (f"  {erro} com erro" if erro else ""))

        # Listar até 3 ações relevantes
        for a in acoes[:3]:
            linhas.append(f"  • {a['tipo']} — {a['entidade_nome']} ({a['cliente_nome']})")

    return "\n".join(linhas)

# ── Contexto financeiro ────────────────────────────────────────────────────────

def financeiro_context() -> str:
    """
    Retorna string com resumo das transações do mês atual para passar ao Claude.
    """
    hoje = date.today()
    try:
        conn = _db()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT descricao, valor, tipo, categoria, data::text
                FROM fin_transacoes
                WHERE EXTRACT(YEAR FROM data) = %s AND EXTRACT(MONTH FROM data) = %s
                ORDER BY data DESC
                """,
                (hoje.year, hoje.month),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"financeiro_context DB error: {e}")
        return "(erro ao consultar transações)"

    if not rows:
        return f"(nenhuma transação registrada em {hoje.strftime('%B/%Y')})"

    receitas = sum(r["valor"] for r in rows if r["tipo"] == "receita")
    despesas = sum(r["valor"] for r in rows if r["tipo"] == "despesa")
    saldo = receitas - despesas

    linhas = [
        f"TRANSAÇÕES DE {hoje.strftime('%B/%Y').upper()}:",
        f"Receitas: R$ {receitas:,.2f} | Despesas: R$ {despesas:,.2f} | Saldo: R$ {saldo:,.2f}",
        "",
    ]
    for r in rows[:20]:
        sinal = "+" if r["tipo"] == "receita" else "-"
        linhas.append(f"{r['data']} | {sinal}R${r['valor']:.2f} | {r['categoria']} | {r['descricao']}")

    return "\n".join(linhas)

# ── Download de mídia ────────────────────────────────────────────────────────

def download_media_bytes(msg_key: dict, msg_content: dict) -> tuple[bytes, str] | None:
    """
    Baixa mídia de uma mensagem WhatsApp via Evolution API getBase64FromMediaMessage.
    Retorna (bytes, mimetype) ou None se falhar.
    msg_key: o dict 'key' da mensagem (id, remoteJid, fromMe)
    msg_content: o dict 'message' da mensagem (imageMessage, videoMessage, etc.)
    """
    try:
        resp = requests.post(
            f"{_evo_base()}/chat/getBase64FromMediaMessage/{_wa_instance()}",
            headers={"apikey": _evo_key(), "Content-Type": "application/json"},
            json={"message": {"key": msg_key, "message": msg_content}},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        b64 = data.get("base64") or data.get("data", {}).get("base64", "")
        mimetype = data.get("mimetype") or data.get("data", {}).get("mimetype", "")
        if not b64:
            logger.error(f"download_media: sem base64 na resposta: {data}")
            return None
        import base64 as _b64
        return _b64.b64decode(b64), mimetype
    except Exception as e:
        logger.error(f"download_media error: {e}")
        return None


# ── Verificar conexão WhatsApp ─────────────────────────────────────────────────

def verificar_conexao() -> str:
    """Retorna estado da conexão: 'open', 'close', 'connecting' ou 'unknown'."""
    try:
        resp = requests.get(
            f"{_evo_base()}/instance/connectionState/{_wa_instance()}",
            headers={"apikey": _evo_key()},
            timeout=5,
        )
        data = resp.json()
        return data.get("instance", {}).get("state", "unknown")
    except Exception as e:
        logger.error(f"verificar_conexao error: {e}")
        return "unknown"
