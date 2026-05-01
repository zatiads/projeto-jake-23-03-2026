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
