"""Testes TDD para as rotas /api/performance/*"""
import sys, json, pytest
sys.path.insert(0, '/root/jake_desktop')
from unittest.mock import MagicMock, patch, mock_open


@pytest.fixture
def client():
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.secret_key = 'test-secret'
    flask_app._perf_saldo_cache.clear()
    with flask_app.app.test_client() as c:
        with c.session_transaction() as sess:
            sess['logged_in'] = True
        yield c


def _mock_meta_saldo(balance=15000, amount_spent=120000, spend_cap=150000, currency="BRL"):
    """Meta API response para saldo (valores em centavos)."""
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = {
        "balance": str(balance),
        "amount_spent": str(amount_spent),
        "spend_cap": str(spend_cap),
        "currency": currency,
        "id": "act_123",
    }
    return resp


# ── GET /api/performance/saldo ──────────────────────────────────────────────

def test_saldo_retorna_campos_esperados(client):
    with patch("app.requests.get", return_value=_mock_meta_saldo()) as mock_get:
        r = client.get("/api/performance/saldo/piloti/act_123456789")
        assert r.status_code == 200
        d = r.get_json()
        assert "balance" in d
        assert "amount_spent" in d
        assert "remaining" in d
        assert "alerta" in d


def test_saldo_alerta_true_quando_abaixo_150(client):
    # remaining = (spend_cap - amount_spent) / 100 = (15000 - 14000) / 100 = 100.0 < 150
    mock = _mock_meta_saldo(balance=10000, amount_spent=140000, spend_cap=150000)
    with patch("app.requests.get", return_value=mock):
        r = client.get("/api/performance/saldo/piloti/act_123456789")
        d = r.get_json()
        assert d["alerta"] is True


def test_saldo_alerta_false_quando_acima_150(client):
    # remaining = (200000 - 120000) / 100 = 800.0 > 150
    mock = _mock_meta_saldo(amount_spent=120000, spend_cap=200000)
    with patch("app.requests.get", return_value=mock):
        r = client.get("/api/performance/saldo/piloti/act_123456789")
        d = r.get_json()
        assert d["alerta"] is False


def test_saldo_account_id_invalido(client):
    r = client.get("/api/performance/saldo/piloti/123invalido")
    assert r.status_code == 400


def test_saldo_agencia_invalida(client):
    r = client.get("/api/performance/saldo/agencia_inexistente/act_123456789")
    assert r.status_code == 500
