# Meta Ads MCP Server — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar servidor MCP para Meta Ads que serve Jake OS (HTTP :5051) e Claude Code (stdio), reutilizando `meta/meta_api.py` sem modificações.

**Architecture:** Servidor Flask único (`meta/mcp_server.py`) com dois modos de transporte selecionados por flag `--stdio`. Modo HTTP expõe `/list` e `/call`. Modo stdio implementa JSON-RPC 2.0 sobre stdin/stdout. Jake OS ganha função `_chamar_mcp_tool` no `app.py` que faz HTTP para o servidor, e as tools são injetadas no `_chat_with_tools`.

**Tech Stack:** Python 3.12, Flask (já instalado), `meta/meta_api.py` (existente), JSON-RPC 2.0 (stdlib), base64 (stdlib).

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `meta/mcp_server.py` | Criar | Servidor MCP (HTTP + stdio), tool registry, dispatch |
| `meta/mcp_client.py` | Criar | Função `chamar_mcp_tool` (cliente HTTP) — separada para ser testável |
| `tests/test_meta_mcp.py` | Criar | Testes do tool registry, endpoints HTTP e cliente |
| `jake_desktop/app.py` | Modificar (linhas ~511-531) | Importar `chamar_mcp_tool` + expandir `_chat_with_tools` |
| `scripts/subir_jake.sh` | Modificar | Subir mcp_server antes do bot (o script atual só sobe o bot Telegram) |
| `/root/.claude/settings.json` | Modificar | Registrar MCP server para Claude Code |

---

## Task 1: Tool registry e lógica de dispatch

**Files:**
- Create: `meta/mcp_server.py`
- Create: `tests/test_meta_mcp.py`

- [ ] **Step 1: Criar estrutura de testes**

```bash
mkdir -p /root/tests
```

- [ ] **Step 2: Escrever testes para o tool registry e dispatch**

Criar `/root/tests/test_meta_mcp.py`:

```python
"""Testes para meta/mcp_server.py — tool registry e dispatch."""
import sys, os
sys.path.insert(0, "/root")

import pytest
from unittest.mock import patch, MagicMock


def test_get_tools_list_returns_expected_tools():
    from meta.mcp_server import get_tools_list
    tools = get_tools_list()
    names = [t["name"] for t in tools]
    assert "meta_get_insights" in names
    assert "meta_get_saldo" in names
    assert "meta_listar_campanhas" in names
    assert "meta_criar_campanha" in names
    assert "meta_upload_imagem" in names
    assert len(tools) == 9


def test_get_tools_list_has_required_fields():
    from meta.mcp_server import get_tools_list
    for tool in get_tools_list():
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"


def test_execute_tool_meta_get_insights_calls_api():
    from meta.mcp_server import execute_tool
    fake_data = {"data": [{"reach": "1000", "spend": "50.00", "clicks": "200", "actions": []}]}
    with patch("meta.meta_api._get_insights", return_value=fake_data):
        result = execute_tool("meta_get_insights", {"account_id": "act_123", "days": 7})
    assert result["ok"] is True
    assert "data" in result


def test_execute_tool_meta_get_insights_none_returns_error():
    from meta.mcp_server import execute_tool
    with patch("meta.meta_api._get_insights", return_value=None):
        result = execute_tool("meta_get_insights", {"account_id": "act_123", "days": 7})
    assert result["ok"] is False
    assert "error" in result


def test_execute_tool_meta_get_saldo_calls_api():
    from meta.mcp_server import execute_tool
    fake = {"amount_spent": 100.0, "balance": 50.0, "spend_cap": 200.0, "remaining": 100.0, "currency": "BRL"}
    with patch("meta.meta_api.get_saldo_conta", return_value=fake):
        result = execute_tool("meta_get_saldo", {"account_id": "act_123"})
    assert result["ok"] is True


def test_execute_tool_meta_listar_campanhas_resolves_token():
    from meta.mcp_server import execute_tool
    fake_campanhas = [{"id": "123", "name": "Campanha Teste", "status": "ACTIVE"}]
    with patch("meta.meta_api._resolve_token", return_value="fake_token"), \
         patch("meta.meta_api.listar_campanhas", return_value=fake_campanhas):
        result = execute_tool("meta_listar_campanhas", {
            "token_key": "META_ACCESS_TOKEN", "account_id": "act_123"
        })
    assert result["ok"] is True
    assert result["data"] == fake_campanhas


def test_execute_tool_unknown_tool_returns_error():
    from meta.mcp_server import execute_tool
    result = execute_tool("tool_que_nao_existe", {})
    assert result["ok"] is False
    assert "desconhecida" in result["error"].lower()


def test_execute_tool_api_exception_returns_error():
    from meta.mcp_server import execute_tool
    with patch("meta.meta_api._get_insights", side_effect=Exception("API falhou")):
        result = execute_tool("meta_get_insights", {"account_id": "act_123"})
    assert result["ok"] is False
    assert "API falhou" in result["error"]


def test_execute_tool_upload_imagem_decodes_base64():
    import base64
    from meta.mcp_server import execute_tool
    fake_bytes = b"fake_image_data"
    b64 = base64.b64encode(fake_bytes).decode()
    with patch("meta.meta_api._resolve_token", return_value="tok"), \
         patch("meta.meta_api.upload_imagem", return_value={"hash": "abc123"}) as mock_upload:
        result = execute_tool("meta_upload_imagem", {
            "token_key": "META_ACCESS_TOKEN",
            "account_id": "act_123",
            "imagem_base64": b64,
            "filename": "test.jpg"
        })
    assert result["ok"] is True
    mock_upload.assert_called_once_with("tok", "act_123", fake_bytes, "test.jpg")
```

- [ ] **Step 3: Rodar testes para confirmar que falham (módulo não existe)**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_meta_mcp.py -v 2>&1 | head -30
```
Esperado: `ModuleNotFoundError` ou `ImportError`

- [ ] **Step 4: Criar `meta/mcp_server.py` com registry e dispatch**

```python
"""
Meta Ads MCP Server.

Dois modos de transporte:
  - padrão: HTTP Flask na porta 5051
  - --stdio: JSON-RPC 2.0 via stdin/stdout (para Claude Code)
"""
import sys
import json
import base64
import argparse

import meta.meta_api as _api

# ── Tool registry ─────────────────────────────────────────────────────────────

def get_tools_list() -> list:
    return [
        {
            "name": "meta_get_insights",
            "description": "Relatório de alcance, cliques, leads e CPL da conta Meta Ads nos últimos N dias.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "ID da conta (ex: act_360347436292903)"},
                    "days":       {"type": "integer", "description": "Número de dias (padrão: 7)", "default": 7},
                },
                "required": ["account_id"],
            },
        },
        {
            "name": "meta_get_saldo",
            "description": "Saldo financeiro da conta Meta Ads: gasto, saldo, limite e restante.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "ID da conta (ex: act_360347436292903)"},
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
                    "token_key":  {"type": "string", "description": "Chave do token: META_TOKEN_PILOTI | META_TOKEN_DENTTO | META_ACCESS_TOKEN"},
                    "account_id": {"type": "string"},
                },
                "required": ["token_key", "account_id"],
            },
        },
        {
            "name": "meta_criar_campanha",
            "description": "Cria campanha Meta Ads em status PAUSED.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key":      {"type": "string"},
                    "account_id":     {"type": "string"},
                    "nome":           {"type": "string"},
                    "campanha_tipo":  {"type": "string", "description": "MESSAGES ou ENGAGEMENT"},
                    "orcamento":      {"type": "number", "description": "Orçamento diário em R$"},
                    "cbo":            {"type": "boolean", "description": "Orçamento no nível da campanha (padrão: true)", "default": True},
                },
                "required": ["token_key", "account_id", "nome", "campanha_tipo", "orcamento"],
            },
        },
        {
            "name": "meta_criar_conjunto",
            "description": "Cria ad set em status PAUSED com segmentação de público e localização.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key":     {"type": "string"},
                    "account_id":    {"type": "string"},
                    "campaign_id":   {"type": "string"},
                    "campanha_tipo": {"type": "string", "description": "MESSAGES ou ENGAGEMENT"},
                    "publico":       {
                        "type": "object",
                        "description": '{"idade_min": 18, "idade_max": 65, "genero": [1,2]}',
                        "properties": {
                            "idade_min": {"type": "integer"},
                            "idade_max": {"type": "integer"},
                            "genero":    {"type": "array", "items": {"type": "integer"}},
                        },
                    },
                    "localizacao": {
                        "type": "object",
                        "description": '{"paises": ["BR"], "cidades": [{"key": "...", "radius": 15, "distance_unit": "kilometer"}]}',
                    },
                    "orcamento": {"type": "number", "description": "Obrigatório para ENGAGEMENT (R$)"},
                },
                "required": ["token_key", "account_id", "campaign_id", "campanha_tipo", "publico", "localizacao"],
            },
        },
        {
            "name": "meta_criar_anuncio",
            "description": "Cria AdCreative + Ad em status PAUSED.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key":    {"type": "string"},
                    "account_id":   {"type": "string"},
                    "adset_id":     {"type": "string"},
                    "page_id":      {"type": "string", "description": "Facebook Page ID do cliente"},
                    "creative_ref": {
                        "type": "object",
                        "description": '{"tipo": "imagem", "hash": "..."} ou {"tipo": "video", "video_id": "..."}',
                    },
                    "titulo":  {"type": "string"},
                    "texto":   {"type": "string"},
                    "cta":     {"type": "string", "description": "SEND_MESSAGE | LEARN_MORE | SIGN_UP"},
                },
                "required": ["token_key", "account_id", "adset_id", "page_id", "creative_ref", "titulo", "texto", "cta"],
            },
        },
        {
            "name": "meta_upload_imagem",
            "description": "Faz upload de imagem e retorna o hash para uso em criativos.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key":     {"type": "string"},
                    "account_id":    {"type": "string"},
                    "imagem_base64": {"type": "string", "description": "Imagem codificada em base64"},
                    "filename":      {"type": "string", "description": "Nome do arquivo (ex: banner.jpg)"},
                },
                "required": ["token_key", "account_id", "imagem_base64", "filename"],
            },
        },
        {
            "name": "meta_upload_video",
            "description": "Faz upload de vídeo (aguarda status=ready) e retorna video_id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key":    {"type": "string"},
                    "account_id":   {"type": "string"},
                    "video_base64": {"type": "string", "description": "Vídeo codificado em base64"},
                    "filename":     {"type": "string"},
                },
                "required": ["token_key", "account_id", "video_base64", "filename"],
            },
        },
        {
            "name": "meta_deletar_objeto",
            "description": "Deleta campanha, conjunto ou anúncio pelo ID (usado em rollback).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token_key":  {"type": "string"},
                    "objeto_id":  {"type": "string", "description": "ID do objeto a deletar"},
                },
                "required": ["token_key", "objeto_id"],
            },
        },
    ]


_WRITE_TOOLS = {
    "meta_listar_campanhas", "meta_criar_campanha", "meta_criar_conjunto",
    "meta_criar_anuncio", "meta_upload_imagem", "meta_upload_video", "meta_deletar_objeto",
}
_READ_TOOLS = {"meta_get_insights", "meta_get_saldo"}


def execute_tool(name: str, args: dict) -> dict:
    """Executa uma tool MCP. Retorna {"ok": True, "data": ...} ou {"ok": False, "error": ...}."""
    if name not in _READ_TOOLS and name not in _WRITE_TOOLS:
        return {"ok": False, "error": f"Tool desconhecida: {name}"}
    try:
        # ── Ferramentas de leitura (sem token_key) ────────────────────────────
        if name == "meta_get_insights":
            result = _api._get_insights(args["account_id"], days=int(args.get("days", 7)))
            if result is None:
                return {"ok": False, "error": "Sem dados retornados pela Meta API"}
            return {"ok": True, "data": result}

        if name == "meta_get_saldo":
            result = _api.get_saldo_conta(args["account_id"])
            if result is None:
                return {"ok": False, "error": "Sem dados retornados pela Meta API"}
            return {"ok": True, "data": result}

        # ── Ferramentas de escrita (com token_key) ────────────────────────────
        token = _api._resolve_token(args["token_key"])

        if name == "meta_listar_campanhas":
            campanhas = _api.listar_campanhas(token, args["account_id"])
            return {"ok": True, "data": campanhas}

        if name == "meta_criar_campanha":
            campaign_id = _api.criar_campanha(
                token, args["account_id"], args["campanha_tipo"],
                args["nome"], float(args["orcamento"]), bool(args.get("cbo", True))
            )
            return {"ok": True, "data": {"campaign_id": campaign_id}}

        if name == "meta_criar_conjunto":
            adset_id = _api.criar_conjunto(
                token, args["account_id"], args["campaign_id"],
                args["campanha_tipo"], args["publico"], args["localizacao"],
                float(args["orcamento"]) if args.get("orcamento") else None
            )
            return {"ok": True, "data": {"adset_id": adset_id}}

        if name == "meta_criar_anuncio":
            ad_id = _api.criar_anuncio(
                token, args["account_id"], args["adset_id"], args["page_id"],
                args["creative_ref"], args["titulo"], args["texto"], args["cta"]
            )
            return {"ok": True, "data": {"ad_id": ad_id}}

        if name == "meta_upload_imagem":
            img_bytes = base64.b64decode(args["imagem_base64"])
            result = _api.upload_imagem(token, args["account_id"], img_bytes, args["filename"])
            return {"ok": True, "data": result}

        if name == "meta_upload_video":
            vid_bytes = base64.b64decode(args["video_base64"])
            video_id = _api.upload_video(token, args["account_id"], vid_bytes, args["filename"])
            return {"ok": True, "data": {"video_id": video_id}}

        if name == "meta_deletar_objeto":
            _api.deletar_objeto_meta(token, args["objeto_id"])
            return {"ok": True, "data": {"deleted": args["objeto_id"]}}

    except Exception as e:
        return {"ok": False, "error": str(e)}
```

- [ ] **Step 5: Rodar testes para confirmar que passam**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_meta_mcp.py -v
```
Esperado: todos os testes PASS

- [ ] **Step 6: Commit**

```bash
cd /root && git add meta/mcp_server.py tests/test_meta_mcp.py && git commit -m "feat(meta): mcp_server tool registry + dispatch + testes"
```

---

## Task 2: Modo HTTP (Flask) no mcp_server

**Files:**
- Modify: `meta/mcp_server.py` — adicionar bloco HTTP ao final do arquivo

- [ ] **Step 1: Escrever testes para os endpoints HTTP**

Adicionar ao final de `/root/tests/test_meta_mcp.py`:

```python
# ── Testes HTTP ────────────────────────────────────────────────────────────────

@pytest.fixture
def http_client():
    from meta.mcp_server import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_http_list_returns_tools(http_client):
    resp = http_client.get("/list")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "tools" in data
    assert len(data["tools"]) == 9


def test_http_call_get_insights_success(http_client):
    fake = {"data": [{"reach": "500", "spend": "20.00", "clicks": "100", "actions": []}]}
    with patch("meta.meta_api._get_insights", return_value=fake):
        resp = http_client.post("/call", json={
            "tool": "meta_get_insights",
            "args": {"account_id": "act_123", "days": 7}
        })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


def test_http_call_unknown_tool(http_client):
    resp = http_client.post("/call", json={"tool": "nao_existe", "args": {}})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is False


def test_http_call_missing_body(http_client):
    resp = http_client.post("/call", json={})
    assert resp.status_code == 400
```

- [ ] **Step 2: Rodar os novos testes para confirmar que falham**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_meta_mcp.py::test_http_list_returns_tools -v
```
Esperado: FAIL — `create_app` não existe ainda

- [ ] **Step 3: Adicionar modo HTTP ao `meta/mcp_server.py`**

Adicionar ao final do arquivo (após a função `execute_tool`):

```python
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
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
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
                content = [{"type": "text", "text": json.dumps(result["data"], ensure_ascii=False)}]
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

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdio", action="store_true", help="Modo JSON-RPC stdio (Claude Code)")
    parser.add_argument("--port", type=int, default=5051)
    args_cli = parser.parse_args()

    if args_cli.stdio:
        run_stdio()
    else:
        app = create_app()
        app.run(host="127.0.0.1", port=args_cli.port)
```

- [ ] **Step 4: Rodar todos os testes**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_meta_mcp.py -v
```
Esperado: todos PASS

- [ ] **Step 5: Smoke test manual do modo HTTP**

```bash
cd /root && PYTHONPATH=/root /root/venv/bin/python meta/mcp_server.py &
sleep 2
curl -s http://localhost:5051/list | python3 -m json.tool | head -20
kill %1
```
Esperado: JSON com lista de 9 tools

- [ ] **Step 6: Commit**

```bash
cd /root && git add meta/mcp_server.py tests/test_meta_mcp.py && git commit -m "feat(meta): modo HTTP Flask + stdio JSON-RPC no mcp_server"
```

---

## Task 3: Cliente MCP + integração Jake OS

**Files:**
- Create: `meta/mcp_client.py`
- Modify: `jake_desktop/app.py` — linhas ~505-531 (área do `_chat_with_tools`)

> Antes de modificar app.py, leia as linhas 505-535 com o Read tool para confirmar o contexto atual.

- [ ] **Step 1: Escrever testes para `chamar_mcp_tool` (importando do módulo real)**

Adicionar ao final de `/root/tests/test_meta_mcp.py`:

```python
# ── Testes meta/mcp_client.py ──────────────────────────────────────────────────

def test_chamar_mcp_tool_sucesso():
    """chamar_mcp_tool faz POST para localhost:5051/call e retorna resultado."""
    from meta.mcp_client import chamar_mcp_tool
    import requests as req_lib
    with patch.object(req_lib, "post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "data": {"campanhas": []}}
        mock_post.return_value = mock_resp
        result = chamar_mcp_tool("meta_listar_campanhas", {"token_key": "META_ACCESS_TOKEN", "account_id": "act_123"})
    assert result["ok"] is True
    mock_post.assert_called_once_with(
        "http://localhost:5051/call",
        json={"tool": "meta_listar_campanhas", "args": {"token_key": "META_ACCESS_TOKEN", "account_id": "act_123"}},
        timeout=10,
    )


def test_chamar_mcp_tool_servidor_offline():
    """chamar_mcp_tool retorna {"ok": False} se servidor não estiver rodando."""
    from meta.mcp_client import chamar_mcp_tool
    import requests as req_lib
    with patch.object(req_lib, "post", side_effect=Exception("Connection refused")):
        result = chamar_mcp_tool("meta_get_insights", {"account_id": "act_123"})
    assert result["ok"] is False
    assert "Connection refused" in result["error"]
```

- [ ] **Step 2: Rodar testes para confirmar que falham (módulo não existe)**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_meta_mcp.py::test_chamar_mcp_tool_sucesso -v
```
Esperado: `ModuleNotFoundError` — `meta.mcp_client` não existe

- [ ] **Step 3: Criar `meta/mcp_client.py`**

```python
"""Cliente HTTP para o Meta MCP Server (localhost:5051)."""
import requests


def chamar_mcp_tool(tool_name: str, args: dict) -> dict:
    """Chama o Meta MCP Server em localhost:5051. Retorna {"ok": bool, ...}."""
    try:
        r = requests.post(
            "http://localhost:5051/call",
            json={"tool": tool_name, "args": args},
            timeout=10,
        )
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

- [ ] **Step 4: Rodar os testes do cliente para confirmar que passam**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_meta_mcp.py::test_chamar_mcp_tool_sucesso tests/test_meta_mcp.py::test_chamar_mcp_tool_servidor_offline -v
```
Esperado: 2 PASS

- [ ] **Step 5: Commit do cliente**

```bash
cd /root && git add meta/mcp_client.py tests/test_meta_mcp.py && git commit -m "feat(meta): mcp_client.py com chamar_mcp_tool + testes"
```

- [ ] **Step 6: Ler linhas atuais do app.py para ter contexto antes de editar**

Ler `/root/jake_desktop/app.py` linhas 500-535.

- [ ] **Step 7: Adicionar import do cliente e `META_MCP_TOOLS` no app.py**

Adicionar logo após a linha `SYSTEM_PROMPT = (...)` (após linha ~509) e antes de `def _chat_with_tools`:

```python
from meta.mcp_client import chamar_mcp_tool as _chamar_mcp_tool

# Nota: apenas 3 tools expostas ao Jake chat (leitura + listar).
# As tools de criação/upload são usadas via Claude Code.
META_MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "meta_get_insights",
            "description": "Relatório de alcance, cliques, leads e CPL da conta Meta Ads nos últimos N dias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"},
                    "days":       {"type": "integer", "default": 7},
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "meta_get_saldo",
            "description": "Saldo financeiro da conta Meta Ads.",
            "parameters": {
                "type": "object",
                "properties": {"account_id": {"type": "string"}},
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "meta_listar_campanhas",
            "description": "Lista campanhas ativas/pausadas de uma conta Meta Ads.",
            "parameters": {
                "type": "object",
                "properties": {
                    "token_key":  {"type": "string"},
                    "account_id": {"type": "string"},
                },
                "required": ["token_key", "account_id"],
            },
        },
    },
]
```

- [ ] **Step 7-cont: Modificar `_chat_with_tools` para incluir as Meta tools e tratar as chamadas**

Substituir a função `_chat_with_tools` existente (linhas ~511-531):

```python
def _chat_with_tools(client, messages):
    all_tools = [TELEGRAM_TOOL] + META_MCP_TOOLS
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=all_tools,
        tool_choice="auto",
    )
    msg = response.choices[0].message
    if getattr(msg, "tool_calls", None):
        messages.append(msg)
        for tc in msg.tool_calls:
            fn_name = getattr(tc.function, "name", "")
            args = json.loads(getattr(tc.function, "arguments", "{}") or "{}")
            if fn_name == "send_telegram_message":
                ok, detail = _send_telegram(args.get("message", ""))
                content = "Enviado no Telegram." if ok else f"Falha: {detail}"
            elif fn_name.startswith("meta_"):
                result = _chamar_mcp_tool(fn_name, args)
                content = json.dumps(result, ensure_ascii=False)
            else:
                content = f"Tool desconhecida: {fn_name}"
            messages.append({
                "role": "tool",
                "tool_call_id": getattr(tc, "id", ""),
                "content": content,
            })
        return _chat_with_tools(client, messages)
    return msg.content or ""
```

- [ ] **Step 8: Rodar todos os testes**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_meta_mcp.py -v
```
Esperado: todos PASS

- [ ] **Step 9: Smoke test manual — verificar que o Jake OS importa sem erros**

```bash
cd /root/jake_desktop && PYTHONPATH=/root /root/venv/bin/python -c "import app; print('OK')"
```
Esperado: `OK`

- [ ] **Step 10: Commit**

```bash
cd /root && git add jake_desktop/app.py && git commit -m "feat(jake-os): injeção Meta MCP tools no chat GPT-4o via mcp_client"
```

---

## Task 4: Startup e configuração

**Files:**
- Modify: `scripts/subir_jake.sh`
- Modify: `/root/.claude/settings.json`

- [ ] **Step 1: Ler `scripts/subir_jake.sh` atual**

Confirmar conteúdo atual antes de editar.

- [ ] **Step 2: Adicionar startup do mcp_server ao `subir_jake.sh`**

Substituir o conteúdo de `/root/scripts/subir_jake.sh`:

```bash
#!/bin/bash
# Sobe o Jake no Telegram em background.
# OBRIGATÓRIO: usar o venv e PYTHONPATH=/root (projeto organizado em bot/, meta/, core/).
cd /root

# Sobe o Meta MCP Server (HTTP :5051)
pkill -f "mcp_server.py" 2>/dev/null; sleep 1
PYTHONPATH=/root nohup /root/venv/bin/python3 /root/meta/mcp_server.py >> /root/logs/meta_mcp.log 2>&1 &
echo $! > /tmp/meta_mcp.pid
echo "Meta MCP Server iniciado. PID: $(cat /tmp/meta_mcp.pid)"

# Sobe o bot Telegram principal
pkill -f "jake_telegram.py" 2>/dev/null; sleep 2
PYTHONPATH=/root nohup /root/venv/bin/python3 /root/jake_telegram.py >> /root/logs/jake.log 2>&1 &
echo "Jake iniciado. PID: $!"
echo "Log: tail -f /root/logs/jake.log"
```

- [ ] **Step 3: Garantir que o diretório de logs existe**

```bash
mkdir -p /root/logs
```

- [ ] **Step 4: Adicionar `mcpServers` ao `/root/.claude/settings.json`**

Ler o arquivo atual, depois adicionar a chave `mcpServers`. O arquivo atual contém as chaves `extraKnownMarketplaces`, `bashTimeout`, `ignorePatterns`, `enabledPlugins`. Adicionar `mcpServers` como nova chave:

```json
{
  "extraKnownMarketplaces": { ... },
  "bashTimeout": 300000,
  "ignorePatterns": [ ... ],
  "enabledPlugins": { ... },
  "mcpServers": {
    "meta-ads": {
      "command": "/root/venv/bin/python3",
      "args": ["/root/meta/mcp_server.py", "--stdio"],
      "env": {}
    }
  }
}
```

- [ ] **Step 5: Testar o startup script**

```bash
bash /root/scripts/subir_jake.sh 2>&1 | head -10
sleep 2
curl -s http://localhost:5051/list | python3 -m json.tool | grep '"name"' | head -5
```
Esperado: lista de tool names na saída do curl

- [ ] **Step 6: Verificar que Claude Code reconhece o MCP server (reload necessário)**

Após editar settings.json, recarregar o Claude Code. No próximo start de sessão, verificar:
```
/mcp
```
Esperado: `meta-ads` listado com 9 tools disponíveis

- [ ] **Step 7: Commit final**

```bash
cd /root && git add scripts/subir_jake.sh /root/.claude/settings.json && git commit -m "feat(infra): subir_jake.sh sobe Meta MCP Server + settings.json claude code"
```

---

## Verificação final

- [ ] Subir tudo com `bash /root/scripts/subir_jake.sh`
- [ ] Confirmar MCP server rodando: `curl http://localhost:5051/list`
- [ ] No Jake OS chat, pedir: "qual o saldo da conta act_360347436292903?" — deve retornar dados reais
- [ ] No Claude Code, digitar `/mcp` e confirmar `meta-ads` listado
- [ ] Rodar suite de testes: `cd /root && /root/venv/bin/python -m pytest tests/ -v`
