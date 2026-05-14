"""Testes para bot/gestor_whatsapp.py"""
import pytest
from unittest.mock import patch, MagicMock


def _make_gestor():
    """Instancia GestorJakeOS com Jake OS URL mockado."""
    from bot.gestor_whatsapp import GestorJakeOS
    return GestorJakeOS(base_url="http://localhost:5050", email="admin@jakeos.local", senha="Jake@2024!")


def test_login_sucesso():
    gestor = _make_gestor()
    mock_resp = MagicMock()
    mock_resp.url = "http://localhost:5050/"
    mock_resp.status_code = 200

    with patch.object(gestor._session, "post", return_value=mock_resp):
        result = gestor.login()
    assert result is True


def test_login_falha():
    gestor = _make_gestor()
    mock_resp = MagicMock()
    mock_resp.url = "http://localhost:5050/login?error=1"

    with patch.object(gestor._session, "post", return_value=mock_resp):
        result = gestor.login()
    assert result is False


def test_subir_anuncio_retorna_mc_token():
    gestor = _make_gestor()
    gestor._autenticado = True

    mock_preparar = MagicMock()
    mock_preparar.json.return_value = {"mc_token": "abc-123", "clientes": 2}
    mock_preparar.status_code = 200

    with patch.object(gestor._session, "post", return_value=mock_preparar):
        result = gestor.subir_anuncio(
            cliente_ids=[1, 2],
            drive_url="https://drive.google.com/file/d/XYZ/view",
            orcamento=30.0,
            campanha_nome="Teste WA",
            campanha_tipo="MESSAGES",
        )
    assert result["mc_token"] == "abc-123"


def test_listar_campanhas():
    gestor = _make_gestor()
    gestor._autenticado = True

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"campanhas": [{"id": "123", "name": "Camp A", "status": "ACTIVE"}]}
    mock_resp.status_code = 200

    with patch.object(gestor._session, "get", return_value=mock_resp):
        result = gestor.listar_campanhas(account_id="act_123", token_key="META_TOKEN_PILOTI")
    assert len(result) == 1
    assert result[0]["id"] == "123"


def test_pausar_campanha():
    gestor = _make_gestor()
    gestor._autenticado = True

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_resp.status_code = 200

    with patch.object(gestor._session, "patch", return_value=mock_resp):
        result = gestor.pausar_campanha(campaign_id="123", token_key="META_TOKEN_PILOTI")
    assert result is True


def test_ativar_campanha():
    gestor = _make_gestor()
    gestor._autenticado = True

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_resp.status_code = 200

    with patch.object(gestor._session, "patch", return_value=mock_resp):
        result = gestor.ativar_campanha(campaign_id="123", token_key="META_TOKEN_PILOTI")
    assert result is True
