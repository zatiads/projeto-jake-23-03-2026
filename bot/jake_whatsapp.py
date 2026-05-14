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

import time as _time

# ── Sessões de conversa (estado por JID) ──────────────────────────────────────
_sessoes: dict = {}
_TTL_SESSAO = 600  # 10 minutos


def _get_sessao(jid: str):
    s = _sessoes.get(jid)
    if s and _time.time() > s["expira_em"]:
        _sessoes.pop(jid, None)
        return None
    return s


def _set_sessao(jid: str, estado: str, payload: dict):
    _sessoes[jid] = {
        "estado":    estado,
        "payload":   payload,
        "expira_em": _time.time() + _TTL_SESSAO,
    }


def _limpar_sessao(jid: str):
    _sessoes.pop(jid, None)


_KEYWORDS_GESTOR = [
    "sobe", "subir", "upload", "anuncio", "anúncio",
    "pausa", "pausar", "ativa", "ativar", "drive.google",
    "campanha", "campanhas",
]

def _eh_gestor_cmd(texto: str) -> bool:
    t = texto.lower()
    return any(k in t for k in _KEYWORDS_GESTOR)


def _formatar_resumo_subida(clientes: list, orcamento: float, campanha_tipo: str, campanha_nome: str) -> str:
    linhas = [f"Vou subir *{campanha_nome}* para:"]
    for c in clientes:
        linhas.append(f"  • {c['nome']} ({c['account_id']})")
    linhas.append(f"Orçamento: R${orcamento:.0f}/dia cada | Tipo: {campanha_tipo}")
    linhas.append("Confirma? (sim/não)")
    return "\n".join(linhas)


def _formatar_resultado_stream(eventos: list, total_clientes: int) -> str:
    ok = [e for e in eventos if e.get("tipo") == "concluido" or e.get("status") == "ok"]
    erros = [e for e in eventos if e.get("tipo") == "erro" or e.get("status") == "erro"]
    linhas = [f"Anúncio subido! {len(ok)}/{total_clientes} concluídos"]
    for e in ok:
        camp = e.get("campanha_id", "")
        nome = e.get("cliente", "")
        linhas.append(f"  ✅ {nome}" + (f" (camp. {camp})" if camp else ""))
    for e in erros:
        nome = e.get("cliente", "")
        msg = e.get("erro", e.get("message", "erro"))
        linhas.append(f"  ❌ {nome}: {msg}")
    return "\n".join(linhas)


def _montar_confirmacao_final(sender_jid: str, destino: str, cmd: dict, clientes: list):
    intencao = cmd["intencao"]

    if intencao == "subir_anuncio":
        drive_link    = cmd.get("drive_link") or ""
        arquivo_local = cmd.get("arquivo_local") or ""
        if not drive_link and not arquivo_local:
            _set_sessao(sender_jid, "aguardando_drive_link", {"cmd": cmd, "clientes": clientes})
            send_text(destino, "Me manda o link do Google Drive do criativo.")
            return
        orcamento = cmd.get("orcamento")
        if not orcamento:
            orcamento = clientes[0].get("orcamento_diario") if clientes else None
        if not orcamento:
            send_text(destino, "Qual o orçamento diário por cliente? (ex: R$30)")
            _set_sessao(sender_jid, "aguardando_orcamento", {"cmd": cmd, "clientes": clientes})
            return
        campanha_tipo = cmd.get("campanha_tipo") or "MESSAGES"
        import datetime
        campanha_nome = cmd.get("campanha_nome") or f"WA {datetime.date.today().strftime('%d/%m')}"
        resumo = _formatar_resumo_subida(clientes, float(orcamento), campanha_tipo, campanha_nome)
        send_text(destino, resumo)
        _set_sessao(sender_jid, "aguardando_confirmacao_subida", {
            "cmd": cmd, "clientes": clientes,
            "orcamento":      float(orcamento),
            "campanha_tipo":  campanha_tipo,
            "campanha_nome":  campanha_nome,
            "drive_link":     drive_link,
            "arquivo_local":  arquivo_local,
        })

    elif intencao in ("pausar_campanha", "ativar_campanha"):
        from bot.gestor_whatsapp import get_gestor
        acao = "pausar" if intencao == "pausar_campanha" else "ativar"
        try:
            gestor = get_gestor()
            todas_campanhas = []
            for c in clientes:
                camps = gestor.listar_campanhas(c["account_id"], c["token_key"])
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

    _PALAVRAS_SUBIR = ["sobe", "subir", "upload", "anuncio", "anúncio", "criativo"]
    if intencao == "desconhecida":
        txt = texto.lower()
        if any(p in txt for p in _PALAVRAS_SUBIR):
            # Parece querer subir anúncio mas faltam detalhes — inicia conversa guiada
            _set_sessao(sender_jid, "aguardando_cliente", {"cmd": {"intencao": "subir_anuncio", "drive_link": None, "orcamento": None, "campanha_tipo": "MESSAGES"}})
            send_text(destino, "Pra qual cliente você quer subir? Me passa o nome.")
        else:
            send_text(destino, "Não entendi o comando, Patrão. Tenta: 'Sobe [link drive] para [cliente], R$30' ou 'Pausa campanhas do [cliente]'")
        return

    nomes = cmd.get("clientes") or []
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


def _processar_confirmacao(sender_jid: str, texto: str, sessao: dict):
    """Processa resposta do Bruno em uma sessão de confirmação ativa."""
    destino   = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid
    estado    = sessao["estado"]
    payload   = sessao["payload"]
    resposta  = texto.lower().strip()
    negativo  = any(r in resposta for r in ["não", "nao", "n", "cancela", "cancel"])
    positivo  = any(r in resposta for r in ["sim", "s", "yes", "ok", "confirma"])

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
        if "drive.google" not in link and "drive.google.com" not in link:
            send_text(destino, "Não parece um link do Google Drive. Manda o link completo.")
            return
        payload["cmd"]["drive_link"] = link
        clientes = payload.get("clientes", [])
        _limpar_sessao(sender_jid)
        _montar_confirmacao_final(sender_jid, destino, payload["cmd"], clientes)
        return

    if negativo:
        _limpar_sessao(sender_jid)
        send_text(destino, "Cancelado, Patrão.")
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

    # ── Aguardando orçamento ──────────────────────────────────────────────────
    if estado == "aguardando_orcamento":
        import re as _re_orc
        m = _re_orc.search(r'[\d,.]+', texto)
        if not m:
            send_text(destino, "Não entendi o valor. Manda só o número, ex: 30")
            return
        orcamento = float(m.group().replace(",", "."))
        payload["cmd"]["orcamento"] = orcamento
        _limpar_sessao(sender_jid)
        _montar_confirmacao_final(sender_jid, destino, payload["cmd"], payload["clientes"])
        return

    # ── Confirmação final de subida ───────────────────────────────────────────
    if estado == "aguardando_confirmacao_subida":
        _limpar_sessao(sender_jid)
        send_text(destino, "Subindo anúncios... aguarda, Patrão.")
        _set_sessao(sender_jid, "executando", {})

        def _executar():
            try:
                from bot.gestor_whatsapp import get_gestor
                gestor = get_gestor()
                cliente_ids = [c["id"] for c in payload["clientes"]]
                dados = gestor.subir_anuncio(
                    cliente_ids=cliente_ids,
                    drive_url=payload.get("drive_link") or None,
                    orcamento=payload["orcamento"],
                    campanha_nome=payload["campanha_nome"],
                    campanha_tipo=payload["campanha_tipo"],
                    arquivo_local=payload.get("arquivo_local") or None,
                )
                mc_token = dados["mc_token"]
                eventos = gestor.consumir_stream(mc_token)
                resultado = _formatar_resultado_stream(eventos, len(payload["clientes"]))
                send_text(destino, resultado)
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

def processar_mensagem(sender_jid: str, texto: str):
    """Processa mensagem do Bruno e envia resposta."""
    chat_id = jid_to_chat_id(sender_jid)
    historico = carregar_historico(chat_id)

    # Verificar sessão ativa (confirmação pendente)
    sessao = _get_sessao(sender_jid)
    if sessao:
        _processar_confirmacao(sender_jid, texto, sessao)
        return

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
