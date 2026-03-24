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
    assert r.status_code == 404


# ── POST /api/performance/alerta-saldo ──────────────────────────────────────

def test_alerta_saldo_envia_telegram(client):
    with patch("app._send_telegram", return_value=(True, "Enviado")) as mock_tg:
        import app as flask_app
        flask_app._alerta_sent_cache.clear()
        r = client.post("/api/performance/alerta-saldo",
                        json={"agency": "piloti", "account_id": "act_111", "nome": "TestClient", "saldo": 80.0})
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d.get("dedup") is not True
        mock_tg.assert_called_once()


def test_alerta_saldo_deduplica_dentro_de_1h(client):
    import app as flask_app, time as _t
    flask_app._alerta_sent_cache["act_222"] = _t.time()  # simula envio recente
    with patch("app._send_telegram") as mock_tg:
        r = client.post("/api/performance/alerta-saldo",
                        json={"agency": "piloti", "account_id": "act_222", "nome": "TestClient", "saldo": 80.0})
        assert r.status_code == 200
        d = r.get_json()
        assert d.get("dedup") is True
        mock_tg.assert_not_called()


def test_alerta_saldo_reenvia_apos_1h(client):
    import app as flask_app, time as _t
    flask_app._alerta_sent_cache["act_333"] = _t.time() - 3700  # 1h atrás
    with patch("app._send_telegram", return_value=(True, "Enviado")) as mock_tg:
        r = client.post("/api/performance/alerta-saldo",
                        json={"agency": "piloti", "account_id": "act_333", "nome": "TestClient", "saldo": 80.0})
        d = r.get_json()
        assert d.get("dedup") is not True
        mock_tg.assert_called_once()


# ── GET /api/performance/semana-anterior ────────────────────────────────────

def _mock_insights_resp(spend="320.00", messaging=27):
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = {"data": [{
        "spend": spend,
        "impressions": "50000",
        "clicks": "800",
        "reach": "18000",
        "cpm": "6.40",
        "ctr": "1.60",
        "frequency": "2.78",
        "actions": [{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": str(messaging)}],
        "cost_per_action_type": [{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": str(float(spend)/messaging)}],
    }]}
    return resp


def test_semana_anterior_retorna_atual_e_anterior(client):
    with patch("app.requests.get", return_value=_mock_insights_resp()):
        r = client.get("/api/performance/semana-anterior/piloti/act_123456789")
        assert r.status_code == 200
        d = r.get_json()
        assert "atual" in d
        assert "anterior" in d
        assert "spend" in d["atual"]
        assert "spend" in d["anterior"]


def test_semana_anterior_account_id_invalido(client):
    r = client.get("/api/performance/semana-anterior/piloti/invalido")
    assert r.status_code == 400


def test_semana_anterior_agencia_invalida(client):
    r = client.get("/api/performance/semana-anterior/agencia_x/act_123456789")
    assert r.status_code == 404


# ── /api/relatorios/analise enriquecida ─────────────────────────────────────

def test_analise_aceita_delta_no_payload(client):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="Boa performance esta semana.")]
    with patch("app._anthropic_client") as mock_client_fn, \
         patch("os.path.isdir", return_value=False), \
         patch("os.makedirs"), \
         patch("builtins.open", mock_open(read_data="")):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_client_fn.return_value = mock_client
        r = client.post("/api/relatorios/analise", json={
            "nome": "HiperClin",
            "metricas": {"Gasto": "R$ 320,00", "Leads": 27},
            "metricas_anterior": {"Gasto": "R$ 290,00", "Leads": 22},
            "delta": {"Gasto": "+10,3%", "Leads": "+22,7%"},
        })
        assert r.status_code == 200
        d = r.get_json()
        assert "analise" in d
        assert len(d["analise"]) > 0
        call_args = mock_client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        assert any(word in prompt_text.lower() for word in ["anterior", "variação", "delta", "comparação"])


def test_analise_salva_snapshot_no_vault(client):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="Análise gerada.")]
    m = mock_open()
    with patch("app._anthropic_client") as mock_client_fn, \
         patch("os.path.isdir", return_value=False), \
         patch("os.makedirs") as mock_mkdir, \
         patch("builtins.open", m):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_client_fn.return_value = mock_client
        r = client.post("/api/relatorios/analise", json={
            "nome": "HiperClin",
            "metricas": {"Gasto": "R$ 320,00"},
            "metricas_anterior": {"Gasto": "R$ 290,00"},
            "delta": {"Gasto": "+10,3%"},
        })
        assert r.status_code == 200
        mock_mkdir.assert_called()
        m.assert_called()
