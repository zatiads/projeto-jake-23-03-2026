import json
import os
import re as _re
import time

from flask import Blueprint, jsonify, request

from .shared import get_db, login_required, anthropic_client

bp = Blueprint('planejador', __name__)


# ══════════════════════════════════════════════════════════════════════════
#  ABA PLANEJADOR DE CAMPANHAS
# ══════════════════════════════════════════════════════════════════════════

_planejador_payloads = {}   # {token: payload} — two-phase SSE

_PLANEJADOR_OBJETIVOS = {"MESSAGES", "ENGAGEMENT", "PURCHASE"}
_PLANEJADOR_CTA       = {"MESSAGES": "WHATSAPP_MESSAGE", "PURCHASE": "SHOP_NOW", "ENGAGEMENT": "LEARN_MORE"}
_PLANEJADOR_LABEL     = {"MESSAGES": "Mensagens", "ENGAGEMENT": "Engajamento", "PURCHASE": "Conversões"}

_PLANEJADOR_PROMPT = """\
Você é o Jake, assistente de tráfego pago. Extraia parâmetros de campanha Meta Ads a partir da conversa.

CLIENTES DISPONÍVEIS:
{clientes_txt}

PARÂMETROS JÁ EXTRAÍDOS:
{params_txt}

CONVERSA:
{conversa_txt}

Retorne APENAS JSON válido (sem markdown):
{{
  "resposta": "<mensagem amigável, direta, em português — máximo 2 frases>",
  "params": {{
    "cliente_id": <int ou null>,
    "cliente_nome": "<string ou null>",
    "campanha_nome": "<string ou null — auto-gerar se null e pronto=true>",
    "objetivo": "<MESSAGES|ENGAGEMENT|PURCHASE ou null>",
    "drive_link": "<URL do Google Drive ou null>",
    "orcamento_diario": <float ou null>,
    "publico_descricao": "<descrição livre do público ou null>",
    "copy_titulo": "<string ou null>",
    "copy_texto": "<string ou null>"
  }},
  "duvidas": ["<campo faltando>"],
  "pronto": <true somente se cliente_id, objetivo, drive_link e orcamento_diario estão todos preenchidos>
}}

Regras:
- Preserve params já extraídos — só atualize se o usuário corrigir explicitamente
- Se cliente não identificado na lista, coloque cliente_id: null e pergunte
- Se pronto=true e copy_titulo/copy_texto são null, gere copy baseado no cliente e objetivo
- Seja conciso
"""


@bp.route("/api/planejador/interpretar", methods=["POST"])
@login_required
def planejador_interpretar():
    d        = request.get_json() or {}
    messages = d.get("messages", [])
    params   = d.get("params", {})

    # Buscar clientes para contexto
    conn = None
    clientes = []
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT id, nome, agencia, campanha_tipo FROM ad_client_profiles ORDER BY nome")
        clientes = cur.fetchall()
    except Exception:
        pass
    finally:
        try: conn.close()
        except Exception: pass

    clientes_txt = "\n".join(
        f"- id={c['id']} | {c['nome']} ({c.get('agencia','')}) | tipo padrão: {c.get('campanha_tipo','')}"
        for c in clientes
    ) or "(nenhum cliente cadastrado)"

    params_txt  = json.dumps(params, ensure_ascii=False)
    conversa_txt = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )

    prompt = _PLANEJADOR_PROMPT.format(
        clientes_txt=clientes_txt,
        params_txt=params_txt,
        conversa_txt=conversa_txt,
    )

    try:
        client = anthropic_client()
        if not client:
            return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()

        # Extrair JSON — Claude pode envolver em markdown
        if "```" in raw:
            import re as _re
            m = _re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
            raw = m.group(1).strip() if m else raw
        try:
            result = json.loads(raw)
        except Exception:
            import re as _re
            m = _re.search(r'\{[\s\S]*\}', raw)
            if m:
                result = json.loads(m.group(0))
            else:
                return jsonify({"error": "Não consegui interpretar. Pode reformular?"}), 200

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Erro ao interpretar: {e}"}), 500


@bp.route("/api/planejador/transcrever", methods=["POST"])
@login_required
def planejador_transcrever():
    audio_file = request.files.get("audio")
    if not audio_file or not audio_file.filename:
        return jsonify({"error": "Arquivo de áudio obrigatório"}), 400

    try:
        from openai import OpenAI as _OpenAI
        oai = _OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        audio_bytes = audio_file.read()
        file_like      = io.BytesIO(audio_bytes)
        file_like.name = audio_file.filename or "audio.webm"
        transcript = oai.audio.transcriptions.create(
            model="whisper-1", file=file_like, language="pt"
        )
        return jsonify({"text": transcript.text})
    except Exception as e:
        return jsonify({"error": f"Erro na transcrição: {e}"}), 500


@bp.route("/api/planejador/subir", methods=["POST"])
@login_required
def planejador_subir():
    """Fase 1: valida payload, armazena em memória, retorna token."""
    d = request.get_json() or {}
    cliente_id     = d.get("cliente_id")
    objetivo       = d.get("objetivo", "")
    drive_link     = (d.get("drive_link") or "").strip()
    orcamento      = d.get("orcamento_diario")
    campanha_nome  = d.get("campanha_nome") or ""
    copy_titulo    = d.get("copy_titulo") or ""
    copy_texto     = d.get("copy_texto") or ""

    if not cliente_id:
        return jsonify({"error": "cliente_id obrigatório"}), 400
    if objetivo not in _PLANEJADOR_OBJETIVOS:
        return jsonify({"error": f"objetivo deve ser: {', '.join(_PLANEJADOR_OBJETIVOS)}"}), 400
    if not drive_link:
        return jsonify({"error": "drive_link obrigatório"}), 400
    if not orcamento:
        return jsonify({"error": "orcamento_diario obrigatório"}), 400

    conn = None
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT * FROM ad_client_profiles WHERE id = %s", (cliente_id,))
        cliente = cur.fetchone()
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar cliente: {e}"}), 500
    finally:
        try: conn.close()
        except Exception: pass

    if not cliente:
        return jsonify({"error": "Cliente não encontrado"}), 404
    if not cliente.get("publico_json"):
        return jsonify({"error": "Público não configurado neste cliente."}), 400
    if not cliente.get("page_id"):
        return jsonify({"error": "page_id não configurado neste cliente"}), 400
    if not cliente.get("localizacao_json"):
        return jsonify({"error": "Localização não configurada neste cliente"}), 400

    import datetime as _dt
    now = _dt.datetime.now()
    if not campanha_nome:
        campanha_nome = f"{cliente['nome']} — {_PLANEJADOR_LABEL.get(objetivo, objetivo)} {now.strftime('%b/%y')}"

    token = str(uuid.uuid4())
    _planejador_payloads[token] = {
        "cliente":       dict(cliente),
        "objetivo":      objetivo,
        "drive_link":    drive_link,
        "orcamento":     float(orcamento),
        "campanha_nome": campanha_nome,
        "copy_titulo":   copy_titulo,
        "copy_texto":    copy_texto,
    }

    def _cleanup():
        _planejador_payloads.pop(token, None)
    threading.Timer(1800, _cleanup).start()

    return jsonify({"token": token})


@bp.route("/api/planejador/subir/stream/<pl_token>")
@login_required
def planejador_subir_stream(pl_token):
    """Fase 2: SSE — baixa Drive, faz upload no Meta, cria campanha."""
    payload = _planejador_payloads.pop(pl_token, None)

    def _sse_pl(data: dict) -> str:
        return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

    def _gerar():
        if not payload:
            yield _sse_pl({"status": "erro", "msg": "Token inválido ou expirado"})
            return

        cliente     = payload["cliente"]
        objetivo    = payload["objetivo"]
