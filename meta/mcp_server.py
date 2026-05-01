"""
meta/mcp_server.py — Tool registry e dispatch para o MCP Server de Meta Ads.

Expõe:
  get_tools_list() → list[dict]   — lista das 9 tools com name/description/inputSchema
  execute_tool(name, args) → dict — executa a tool e retorna {"ok": True/False, ...}
"""
import base64

import meta.meta_api as _api

# ── Classificação das tools ────────────────────────────────────────────────────
# Tools que não exigem token_key
_NO_TOKEN_TOOLS = {"meta_get_insights", "meta_get_saldo"}

# Tools que exigem token_key
_TOKEN_TOOLS = {
    "meta_listar_campanhas",
    "meta_criar_campanha",
    "meta_criar_conjunto",
    "meta_criar_anuncio",
    "meta_upload_imagem",
    "meta_upload_video",
    "meta_deletar_objeto",
}

_ALL_TOOLS = _NO_TOKEN_TOOLS | _TOKEN_TOOLS


# ── Tool registry ──────────────────────────────────────────────────────────────
def get_tools_list() -> list:
    """Retorna a lista de 9 tool descriptors compatíveis com MCP."""
    return [
        {
            "name": "meta_get_insights",
            "description": "Obtém insights agregados (reach, spend, clicks, leads) de uma conta Meta Ads nos últimos N dias.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "ID da conta de anúncios (ex: act_360347436292903)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Número de dias a considerar (padrão: 7)",
                        "default": 7
                    },
                },
                "required": ["account_id"],
            },
        },
        {
            "name": "meta_get_saldo",
            "description": "Retorna saldo e informações financeiras de uma conta Meta Ads (amount_spent, balance, spend_cap, remaining, currency).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "ID da conta de anúncios (ex: act_360347436292903)"
                    },
                },
                "required": ["account_id"],
            },
        },
        {
            "name": "meta_listar_campanhas",
            "description": "Lista campanhas ativas e pausadas de uma conta Meta Ads.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key": {
                        "type": "string",
                        "description": "Chave da variável de ambiente com o token de acesso (ex: META_ACCESS_TOKEN)"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "ID da conta de anúncios"
                    },
                },
                "required": ["token_key", "account_id"],
            },
        },
        {
            "name": "meta_criar_campanha",
            "description": "Cria uma campanha Meta Ads com status PAUSED. Retorna o campaign_id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key": {
                        "type": "string",
                        "description": "Chave da variável de ambiente com o token"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "ID da conta de anúncios"
                    },
                    "nome": {
                        "type": "string",
                        "description": "Nome da campanha"
                    },
                    "campanha_tipo": {
                        "type": "string",
                        "enum": ["MESSAGES", "ENGAGEMENT"],
                        "description": "Tipo/objetivo da campanha"
                    },
                    "orcamento": {
                        "type": "number",
                        "description": "Orçamento diário em reais"
                    },
                    "cbo": {
                        "type": "boolean",
                        "description": "Usar CBO (orçamento ao nível da campanha). Padrão: true",
                        "default": True
                    },
                },
                "required": ["token_key", "account_id", "nome", "campanha_tipo", "orcamento"],
            },
        },
        {
            "name": "meta_criar_conjunto",
            "description": "Cria um ad set (conjunto de anúncios) com status PAUSED. Retorna o adset_id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key": {
                        "type": "string",
                        "description": "Chave da variável de ambiente com o token"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "ID da conta de anúncios"
                    },
                    "campaign_id": {
                        "type": "string",
                        "description": "ID da campanha pai"
                    },
                    "campanha_tipo": {
                        "type": "string",
                        "enum": ["MESSAGES", "ENGAGEMENT"],
                        "description": "Tipo da campanha (define optimization_goal)"
                    },
                    "publico": {
                        "type": "object",
                        "description": "Configuração de público: {idade_min, idade_max, genero}"
                    },
                    "localizacao": {
                        "type": "object",
                        "description": "Configuração de localização: {paises, cidades}"
                    },
                    "orcamento": {
                        "type": "number",
                        "description": "Orçamento diário em reais (opcional, usado para ENGAGEMENT sem CBO)"
                    },
                },
                "required": ["token_key", "account_id", "campaign_id", "campanha_tipo", "publico", "localizacao"],
            },
        },
        {
            "name": "meta_criar_anuncio",
            "description": "Cria um AdCreative + Ad com status PAUSED. Retorna o ad_id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key": {
                        "type": "string",
                        "description": "Chave da variável de ambiente com o token"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "ID da conta de anúncios"
                    },
                    "adset_id": {
                        "type": "string",
                        "description": "ID do ad set pai"
                    },
                    "page_id": {
                        "type": "string",
                        "description": "Facebook Page ID do cliente"
                    },
                    "creative_ref": {
                        "type": "object",
                        "description": "Referência do criativo: {tipo: 'imagem', hash: '...'} ou {tipo: 'video', video_id: '...'}"
                    },
                    "titulo": {
                        "type": "string",
                        "description": "Título do anúncio"
                    },
                    "texto": {
                        "type": "string",
                        "description": "Texto principal do anúncio"
                    },
                    "cta": {
                        "type": "string",
                        "description": "Call to action: SEND_MESSAGE | LEARN_MORE | SIGN_UP"
                    },
                },
                "required": ["token_key", "account_id", "adset_id", "page_id", "creative_ref", "titulo", "texto", "cta"],
            },
        },
        {
            "name": "meta_upload_imagem",
            "description": "Faz upload de uma imagem (base64) para a biblioteca de mídias da conta Meta. Retorna {'hash': '...'}.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key": {
                        "type": "string",
                        "description": "Chave da variável de ambiente com o token"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "ID da conta de anúncios"
                    },
                    "imagem_base64": {
                        "type": "string",
                        "description": "Imagem codificada em base64"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Nome do arquivo (ex: banner.jpg)"
                    },
                },
                "required": ["token_key", "account_id", "imagem_base64", "filename"],
            },
        },
        {
            "name": "meta_upload_video",
            "description": "Faz upload de um vídeo (base64) para a biblioteca de mídias da conta Meta. Retorna o video_id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key": {
                        "type": "string",
                        "description": "Chave da variável de ambiente com o token"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "ID da conta de anúncios"
                    },
                    "video_base64": {
                        "type": "string",
                        "description": "Vídeo codificado em base64"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Nome do arquivo (ex: video.mp4)"
                    },
                },
                "required": ["token_key", "account_id", "video_base64", "filename"],
            },
        },
        {
            "name": "meta_deletar_objeto",
            "description": "Deleta uma campanha, conjunto ou anúncio Meta Ads pelo ID (útil em rollback).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key": {
                        "type": "string",
                        "description": "Chave da variável de ambiente com o token"
                    },
                    "objeto_id": {
                        "type": "string",
                        "description": "ID do objeto a deletar (campanha, conjunto ou anúncio)"
                    },
                },
                "required": ["token_key", "objeto_id"],
            },
        },
    ]


# ── Dispatch ───────────────────────────────────────────────────────────────────
def execute_tool(name: str, args: dict) -> dict:
    """
    Executa a tool pelo nome, passando args.
    Retorna {"ok": True, ...dados...} em caso de sucesso,
    ou {"ok": False, "error": "..."} em caso de falha.
    """
    # Verificação antecipada: tool desconhecida
    if name not in _ALL_TOOLS:
        return {"ok": False, "error": f"Tool desconhecida: {name}"}

    try:
        # ── NO TOKEN TOOLS (sem token_key) ────────────────────────────────────
        if name == "meta_get_insights":
            account_id = args["account_id"]
            data = _api._get_insights(account_id, days=int(args.get("days", 7)))
            if data is None:
                return {"ok": False, "error": "Sem dados retornados pela Meta API"}
            return {"ok": True, "data": data}

        if name == "meta_get_saldo":
            account_id = args["account_id"]
            data = _api.get_saldo_conta(account_id)
            if data is None:
                return {"ok": False, "error": "Sem dados retornados pela Meta API"}
            return {"ok": True, "data": data}

        # ── TOKEN TOOLS (com token_key) ───────────────────────────────────────
        token = _api._resolve_token(args["token_key"])

        if name == "meta_listar_campanhas":
            campanhas = _api.listar_campanhas(token, args["account_id"])
            return {"ok": True, "data": campanhas}

        if name == "meta_criar_campanha":
            campaign_id = _api.criar_campanha(
                token,
                args["account_id"],
                args["campanha_tipo"],
                args["nome"],
                float(args["orcamento"]),
                cbo=bool(args.get("cbo", True)),
            )
            return {"ok": True, "data": {"campaign_id": campaign_id}}

        if name == "meta_criar_conjunto":
            adset_id = _api.criar_conjunto(
                token,
                args["account_id"],
                args["campaign_id"],
                args["campanha_tipo"],
                args["publico"],
                args["localizacao"],
                orcamento=args.get("orcamento"),
            )
            return {"ok": True, "data": {"adset_id": adset_id}}

        if name == "meta_criar_anuncio":
            ad_id = _api.criar_anuncio(
                token,
                args["account_id"],
                args["adset_id"],
                args["page_id"],
                args["creative_ref"],
                args["titulo"],
                args["texto"],
                args["cta"],
            )
            return {"ok": True, "data": {"ad_id": ad_id}}

        if name == "meta_upload_imagem":
            imagem_bytes = base64.b64decode(args["imagem_base64"])
            result = _api.upload_imagem(token, args["account_id"], imagem_bytes, args["filename"])
            return {"ok": True, "data": result}

        if name == "meta_upload_video":
            video_bytes = base64.b64decode(args["video_base64"])
            video_id = _api.upload_video(token, args["account_id"], video_bytes, args["filename"])
            return {"ok": True, "data": {"video_id": video_id}}

        if name == "meta_deletar_objeto":
            _api.deletar_objeto_meta(token, args["objeto_id"])
            return {"ok": True, "data": {"deleted": args["objeto_id"]}}

    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Modo HTTP (Flask) ─────────────────────────────────────────────────────────

def create_app():
    from flask import Flask, jsonify, request as flask_request
    app = Flask(__name__)

    @app.route("/list", methods=["GET"])
    def route_list():
        return jsonify({"tools": get_tools_list()})

    @app.route("/call", methods=["POST"])
    def route_call():
        body = flask_request.get_json(silent=True)
        if not body or "tool" not in body:
            from flask import abort
            abort(400)
        result = execute_tool(body["tool"], body.get("args") or {})
        return jsonify(result)

    return app


# ── Modo stdio (JSON-RPC 2.0) ─────────────────────────────────────────────────

def run_stdio():
    """Loop JSON-RPC 2.0 sobre stdin/stdout — protocolo MCP para Claude Code."""
    import sys
    import json as _json
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = _json.loads(line)
        except _json.JSONDecodeError:
            sys.stdout.write(_json.dumps({
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }) + "\n")
            sys.stdout.flush()
            continue

        if not isinstance(req, dict):
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        # Handshake MCP
        if method == "initialize":
            resp = {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "meta-ads", "version": "1.0.0"},
                },
            }
        elif method == "notifications/initialized":
            continue  # notificação sem resposta
        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": get_tools_list()}}
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args  = params.get("arguments") or {}
            result = execute_tool(tool_name, tool_args)
            if result["ok"]:
                content = [{"type": "text", "text": _json.dumps(result["data"], ensure_ascii=False)}]
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": content}}
            else:
                resp = {
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32000, "message": result["error"]},
                }
        else:
            resp = {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        sys.stdout.write(_json.dumps(resp) + "\n")
        sys.stdout.flush()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdio", action="store_true", help="Modo JSON-RPC stdio (Claude Code)")
    parser.add_argument("--port", type=int, default=5051)
    args_cli = parser.parse_args()

    if args_cli.stdio:
        run_stdio()
    else:
        app = create_app()
        app.run(host="127.0.0.1", port=args_cli.port)
