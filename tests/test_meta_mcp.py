"""Testes para meta/mcp_server.py — tool registry e dispatch."""
import sys
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


def test_execute_tool_meta_criar_campanha_returns_campaign_id():
    from meta.mcp_server import execute_tool
    with patch("meta.meta_api._resolve_token", return_value="tok"), \
         patch("meta.meta_api.criar_campanha", return_value="camp_123"):
        result = execute_tool("meta_criar_campanha", {
            "token_key": "META_ACCESS_TOKEN",
            "account_id": "act_123",
            "nome": "Campanha Teste",
            "campanha_tipo": "MESSAGES",
            "orcamento": 50.0,
            "cbo": True,
        })
    assert result["ok"] is True
    assert result["data"]["campaign_id"] == "camp_123"


def test_execute_tool_meta_criar_conjunto_returns_adset_id():
    from meta.mcp_server import execute_tool
    publico = {"idade_min": 18, "idade_max": 65}
    localizacao = {"paises": ["BR"], "cidades": []}
    with patch("meta.meta_api._resolve_token", return_value="tok"), \
         patch("meta.meta_api.criar_conjunto", return_value="adset_456"):
        result = execute_tool("meta_criar_conjunto", {
            "token_key": "META_ACCESS_TOKEN",
            "account_id": "act_123",
            "campaign_id": "camp_123",
            "campanha_tipo": "MESSAGES",
            "publico": publico,
            "localizacao": localizacao,
        })
    assert result["ok"] is True
    assert result["data"]["adset_id"] == "adset_456"


def test_execute_tool_meta_criar_anuncio_returns_ad_id():
    from meta.mcp_server import execute_tool
    creative_ref = {"tipo": "imagem", "hash": "abc123"}
    with patch("meta.meta_api._resolve_token", return_value="tok"), \
         patch("meta.meta_api.criar_anuncio", return_value="ad_789"):
        result = execute_tool("meta_criar_anuncio", {
            "token_key": "META_ACCESS_TOKEN",
            "account_id": "act_123",
            "adset_id": "adset_456",
            "page_id": "page_000",
            "creative_ref": creative_ref,
            "titulo": "Titulo Teste",
            "texto": "Texto do anuncio",
            "cta": "SEND_MESSAGE",
        })
    assert result["ok"] is True
    assert result["data"]["ad_id"] == "ad_789"


def test_execute_tool_meta_upload_video_returns_video_id():
    import base64
    from meta.mcp_server import execute_tool
    fake_bytes = b"fake_video"
    b64 = base64.b64encode(fake_bytes).decode()
    with patch("meta.meta_api._resolve_token", return_value="tok"), \
         patch("meta.meta_api.upload_video", return_value="vid_999") as mock_upload:
        result = execute_tool("meta_upload_video", {
            "token_key": "META_ACCESS_TOKEN",
            "account_id": "act_123",
            "video_base64": b64,
            "filename": "test.mp4",
        })
    assert result["ok"] is True
    assert result["data"]["video_id"] == "vid_999"
    mock_upload.assert_called_once_with("tok", "act_123", fake_bytes, "test.mp4")


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
    assert "data" in data


def test_http_call_unknown_tool(http_client):
    resp = http_client.post("/call", json={"tool": "nao_existe", "args": {}})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is False


def test_http_call_missing_body(http_client):
    resp = http_client.post("/call", json={})
    assert resp.status_code == 400
