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


# ── Gestor IA WA — funções de aprovação e resumo ─────────────────────────────

def _verificar_varredura_pendente() -> dict | None:
    """Consulta gestor_estado. Retorna {'varredura_id': X, 'id': Y} ou None."""
    try:
        conn = _db()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, varredura_id
                FROM gestor_estado
                WHERE status = 'aguardando'
                ORDER BY criado_em DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"_verificar_varredura_pendente error: {e}")
        return None


def _marcar_estado_resolvido(estado_id: int):
    """Marca gestor_estado como aprovado."""
    try:
        conn = _db()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE gestor_estado
                SET status='aprovado', resolvido_em=NOW()
                WHERE id=%s
            """, (estado_id,))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"_marcar_estado_resolvido error: {e}")


def formatar_resumo_gestor(acoes: list, alertas: list, total_contas: int, varredura_id: int) -> str | None:
    """
    Formata mensagem matinal do Gestor IA para WA.
    Retorna None se não há ações nem alertas (silêncio).
    """
    from datetime import date as _date
    hoje = _date.today().strftime("%d/%m")

    if not acoes and not alertas:
        return None

    linhas = [f"🤖 *Gestor IA — {hoje}*"]
    linhas.append("")

    _TIPO_LABEL = {
        "pausar_ad":        "⏸️ PAUSAR AD",
        "reativar_ad":      "▶️ REATIVAR AD",
        "escalar_orcamento":"📈 ESCALAR ORCAMENTO +15%",
        "reduzir_orcamento":"📉 REDUZIR ORCAMENTO -20%",
        "duplicar_ad":      "📋 DUPLICAR AD",
    }

    _ALERTA_EMOJI = {
        "SALDO_CRITICO":    "💰",
        "ZERO_CONV":        "❌",
        "FREQ_ALTA":        "🔄",
        "SEM_VEICULACAO":   "😴",
        "LEARNING_TRAVADO": "🔒",
        "CPL_SEMANAL":      "📊",
    }

    if acoes:
        linhas.append(f"Analisei {total_contas} contas. *{len(acoes)} {'ação' if len(acoes) == 1 else 'ações'} para aprovar:*")
        linhas.append("")
        for a in acoes:
            label = _TIPO_LABEL.get(a["tipo"], a["tipo"].upper())
            linhas.append(f"*{a['numero_na_varredura']}. {label}* — {a['cliente_nome']}")
            linhas.append(f"   {a['motivo']}")
            linhas.append("")
    else:
        linhas.append(f"✅ Analisei {total_contas} contas. Sem ações necessárias.")
        linhas.append("")

    if alertas:
        linhas.append("⚠️ *Alertas:*")
        for al in alertas:
            motivo = al['motivo']
            prefixo = motivo.split(":")[0].strip()
            emoji = _ALERTA_EMOJI.get(prefixo, "•")
            linhas.append(f"{emoji} *{al['cliente_nome']}:* {motivo.split(':', 1)[-1].strip()}")
        linhas.append("")

    if acoes:
        linhas.append('Responda *"ok"* para aprovar tudo ou *"cancela N"* para cancelar uma ação.')
        linhas.append("⏳ Expira em 4h.")

    return "\n".join(linhas)


def enviar_resumo_gestor(varredura_id: int):
    """Busca ações pendentes e alertas da varredura e envia mensagem WA."""
    import os as _os
    destino = _os.environ.get("WA_AUTHORIZED_NUMBER", "").strip()
    if not destino:
        logger.warning("WA_AUTHORIZED_NUMBER nao configurado — resumo nao enviado")
        return

    try:
        conn = _db()
        try:
            cur = conn.cursor()
            cur2 = conn.cursor()
            cur2.execute("SELECT COUNT(*) AS total FROM ad_client_profiles WHERE gestor_ativo=TRUE")
            total_contas = cur2.fetchone()["total"]

            cur.execute("""
                SELECT ga.numero_na_varredura, ga.tipo, ga.entidade_nome,
                       ga.motivo, acp.nome as cliente_nome
                FROM gestor_acoes ga
                JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
                WHERE ga.varredura_id = %s AND ga.status = 'pendente'
                  AND ga.numero_na_varredura IS NOT NULL
                ORDER BY ga.numero_na_varredura
            """, (varredura_id,))
            acoes = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT ga.tipo, ga.entidade_nome, ga.motivo, acp.nome as cliente_nome
                FROM gestor_acoes ga
                JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
                WHERE ga.varredura_id = %s AND ga.tipo LIKE 'alerta%%'
                ORDER BY ga.executado_em
            """, (varredura_id,))
            alertas = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"enviar_resumo_gestor DB error: {e}")
        return

    msg = formatar_resumo_gestor(acoes, alertas, total_contas, varredura_id)
    if msg:
        send_text(destino, msg)


try:
    from meta.gestor.executor import executar_aprovadas  # noqa: F401
except Exception:
    executar_aprovadas = None  # type: ignore


def processar_aprovacao(texto: str, destino: str):
    """Processa resposta de aprovação: 'ok' ou 'cancela N'."""
    import re as _re

    estado = _verificar_varredura_pendente()
    if not estado:
        send_text(destino, "Sem acoes pendentes de aprovacao no momento.")
        return

    varredura_id = estado["varredura_id"]
    estado_id = estado["id"]

    canceladas = []
    texto_limpo = texto.strip().lower()

    if texto_limpo == "ok":
        canceladas = []
    else:
        m = _re.match(r"^cancela\s+(\d+)$", texto_limpo)
        if m:
            n = int(m.group(1))
            # Validar se N existe
            try:
                conn_check = _db()
                cur_check = conn_check.cursor()
                cur_check.execute(
                    "SELECT COUNT(*) FROM gestor_acoes WHERE varredura_id=%s AND status='pendente' AND numero_na_varredura=%s",
                    (varredura_id, n),
                )
                existe = cur_check.fetchone()[0] > 0
                cur_check.execute(
                    "SELECT COUNT(*) FROM gestor_acoes WHERE varredura_id=%s AND status='pendente' AND numero_na_varredura IS NOT NULL",
                    (varredura_id,),
                )
                total = cur_check.fetchone()[0]
                conn_check.close()
                if not existe:
                    send_text(destino, f"So tem {total} acao(es) numerada(s). Manda 'ok' para aprovar ou ignore para cancelar tudo em 4h.")
                    return
            except Exception:
                pass
            canceladas = [n]
        else:
            send_text(destino, 'Nao entendi. Responda "ok" para aprovar tudo ou "cancela N" para cancelar uma acao.')
            return

    try:
        resultado = executar_aprovadas(varredura_id=varredura_id, canceladas=canceladas)
        _marcar_estado_resolvido(estado_id)

        partes = []
        if resultado["ok"]:
            partes.append(f"{resultado['ok']} acao(es) executada(s)")
        if resultado["canceladas"]:
            partes.append(f"{resultado['canceladas']} cancelada(s)")
        if resultado["erro"]:
            partes.append(f"{resultado['erro']} com erro")

        msg = "Gestor IA: " + ", ".join(partes) + "." if partes else "Gestor IA: nenhuma acao executada."
        send_text(destino, msg)
    except Exception as e:
        logger.error(f"processar_aprovacao error: {e}")
        send_text(destino, f"Erro ao executar acoes: {e}")


# ── Comandos slash ─────────────────────────────────────────────────────────────

def cmd_saldo(destino: str):
    """Lista saldo de todas as contas ativas."""
    import os as _os, requests as _req, sys as _sys
    if "/root" not in _sys.path:
        _sys.path.insert(0, "/root")
    from meta.meta_api import _resolve_token

    GRAPH_URL = "https://graph.facebook.com/v21.0"
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            SELECT nome, agencia, account_id, token_key
            FROM ad_client_profiles WHERE gestor_ativo=TRUE ORDER BY agencia, nome
        """)
        contas = cur.fetchall()
        conn.close()
    except Exception as e:
        send_text(destino, f"Erro ao buscar contas: {e}")
        return

    linhas = ["Saldo das contas ativas:"]
    agencia_atual = None
    for c in contas:
        if c["agencia"] != agencia_atual:
            agencia_atual = c["agencia"]
            linhas.append(f"\n[{agencia_atual.upper()}]")
        try:
            token = _resolve_token(c["token_key"])
            resp = _req.get(
                f"{GRAPH_URL}/{c['account_id']}",
                params={"fields": "amount_spent,spend_cap,balance", "access_token": token},
                timeout=10,
            )
            d = resp.json()
            spent = float(d.get("amount_spent") or 0) / 100
            cap = float(d.get("spend_cap") or 0) / 100
            bal = float(d.get("balance") or 0) / 100
            remaining = max(0.0, cap - spent) if cap else bal
            linhas.append(f"  {c['nome']}: R${remaining:.0f} restante")
        except Exception:
            linhas.append(f"  {c['nome']}: erro ao buscar")

    send_text(destino, "\n".join(linhas))


def cmd_historico(destino: str):
    """Últimas 10 ações do gestor com status."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            SELECT ga.tipo, ga.entidade_nome, ga.status, ga.executado_em,
                   acp.nome as cliente_nome
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE ga.tipo NOT LIKE 'alerta%%'
            ORDER BY ga.executado_em DESC LIMIT 10
        """)
        acoes = cur.fetchall()
        conn.close()
    except Exception as e:
        send_text(destino, f"Erro: {e}")
        return

    if not acoes:
        send_text(destino, "Nenhuma acao registrada ainda.")
        return

    _STATUS_ICON = {"sucesso": "V", "erro": "X", "pendente": "...", "cancelado": "-", "expirado": "~"}
    linhas = ["Historico do Gestor IA (ultimas 10):"]
    for a in acoes:
        icon = _STATUS_ICON.get(a["status"], "?")
        data = a["executado_em"].strftime("%d/%m %H:%M") if a["executado_em"] else "?"
        linhas.append(f"[{icon}] {a['tipo']} — {a['entidade_nome']} ({a['cliente_nome']}) {data}")

    send_text(destino, "\n".join(linhas))


def cmd_status_cliente(destino: str, nome_cliente: str):
    """Métricas rápidas de um cliente."""
    import sys as _sys
    if "/root" not in _sys.path:
        _sys.path.insert(0, "/root")

    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nome, agencia, account_id, token_key, campanha_tipo
            FROM ad_client_profiles
            WHERE LOWER(nome) LIKE %s AND gestor_ativo=TRUE LIMIT 1
        """, (f"%{nome_cliente.lower()}%",))
        conta = cur.fetchone()
        conn.close()
    except Exception as e:
        send_text(destino, f"Erro: {e}")
        return

    if not conta:
        send_text(destino, f"Cliente '{nome_cliente}' nao encontrado.")
        return

    try:
        from meta.meta_api import _resolve_token
        from meta.gestor.coletor import _buscar_insights_ads, _buscar_saldo, _agregar_conta
        token = _resolve_token(conta["token_key"])
        rows = _buscar_insights_ads(token, conta["account_id"])
        saldo = _buscar_saldo(token, conta["account_id"])
        metricas = _agregar_conta(rows, conta["campanha_tipo"] or "MESSAGES")

        top = metricas.get("top_ads", [{}])[0] if metricas.get("top_ads") else {}
        linhas = [
            f"Status: {conta['nome']}",
            f"CPL medio: R${metricas.get('cpl_medio') or '—'}",
            f"Saldo: R${saldo.get('remaining', 0):.0f}",
            f"Top ad: {top.get('ad_name', '—')} (CPL R${top.get('cpl', '—')})",
            f"Total conversoes 30d: {metricas.get('total_conversoes', 0)}",
        ]
        send_text(destino, "\n".join(linhas))
    except Exception as e:
        send_text(destino, f"Erro ao buscar metricas: {e}")


def cmd_relatorio(destino: str):
    """Resumo da semana em texto no WA."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            SELECT ga.tipo, ga.entidade_nome, ga.status, acp.nome as cliente_nome, acp.agencia
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE ga.executado_em >= NOW() - INTERVAL '7 days'
              AND ga.tipo NOT LIKE 'alerta%%'
              AND ga.status = 'sucesso'
            ORDER BY ga.executado_em DESC
        """)
        acoes = cur.fetchall()
        conn.close()
    except Exception as e:
        send_text(destino, f"Erro: {e}")
        return

    if not acoes:
        send_text(destino, "Nenhuma acao executada nos ultimos 7 dias.")
        return

    por_agencia: dict = {}
    for a in acoes:
        ag = a["agencia"] or "—"
        por_agencia.setdefault(ag, []).append(a)

    linhas = ["Relatorio semanal — ultimos 7 dias:"]
    for ag, lista in por_agencia.items():
        linhas.append(f"\n[{ag.upper()}] {len(lista)} acoes")
        for a in lista[:5]:
            linhas.append(f"  V {a['tipo']} — {a['entidade_nome']} ({a['cliente_nome']})")
        if len(lista) > 5:
            linhas.append(f"  ... e mais {len(lista)-5}")

    linhas.append("\nPDF completo disponivel no Jake OS > Relatorios.")
    send_text(destino, "\n".join(linhas))
