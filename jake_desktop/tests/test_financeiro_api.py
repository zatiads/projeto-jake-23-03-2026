"""Testes TDD para as 6 rotas /api/financeiro/*"""
import sys, json, pytest
sys.path.insert(0, '/root/jake_desktop')
from unittest.mock import MagicMock, patch


def _mock_conn(rows=None, novo_id=None):
    """Retorna mock de conexão psycopg2 com RealDictCursor."""
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    if rows is not None:
        cur.fetchall.return_value = rows
    if novo_id is not None:
        cur.fetchone.return_value = {"id": novo_id}
    return conn


@pytest.fixture
def client():
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.secret_key = 'test-secret'
    with flask_app.app.test_client() as c:
        with c.session_transaction() as sess:
            sess['logged_in'] = True
        yield c


@pytest.fixture
def client_anonimo():
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.secret_key = 'test-secret'
    with flask_app.app.test_client() as c:
        yield c


# ── GET /api/financeiro/transacoes ──────────────────────────────────────────

def test_listar_transacoes(client):
    row = {"id": 1, "descricao": "Dentto", "valor": 4300.0,
           "tipo": "Entrada", "categoria": "Fixa", "recorrente": True, "data": "2026-01-05"}
    with patch("app._get_db", return_value=_mock_conn(rows=[row])):
        resp = client.get("/api/financeiro/transacoes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data[0]["descricao"] == "Dentto"


# ── POST /api/financeiro/transacoes ─────────────────────────────────────────

def test_criar_transacao(client):
    with patch("app._get_db", return_value=_mock_conn(novo_id=45)):
        resp = client.post("/api/financeiro/transacoes", json={
            "descricao": "Nova entrada", "valor": 500.0,
            "tipo": "Entrada", "categoria": "Fixa", "data": "2026-03-01"
        })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == 45
    assert body["ok"] is True


def test_criar_transacao_campo_faltando(client):
    with patch("app._get_db", return_value=_mock_conn()):
        resp = client.post("/api/financeiro/transacoes", json={"descricao": "incompleto"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── PUT /api/financeiro/transacoes/<id> ─────────────────────────────────────

def test_atualizar_transacao(client):
    with patch("app._get_db", return_value=_mock_conn()):
        resp = client.put("/api/financeiro/transacoes/1", json={"valor": 5000.0})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# ── DELETE /api/financeiro/transacoes/<id> ───────────────────────────────────

def test_deletar_transacao(client):
    with patch("app._get_db", return_value=_mock_conn()):
        resp = client.delete("/api/financeiro/transacoes/1")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# ── GET /api/financeiro/raiox ────────────────────────────────────────────────

def test_get_raiox(client):
    rows = [{"id": 1, "nome": "Dentto", "grupo": "entradas",
             "valores": [4300,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950]}]
    with patch("app._get_db", return_value=_mock_conn(rows=rows)):
        resp = client.get("/api/financeiro/raiox")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "entradas" in data and "fixas" in data and "variaveis" in data
    assert data["entradas"][0]["nome"] == "Dentto"


# ── PUT /api/financeiro/raiox ────────────────────────────────────────────────

def test_salvar_raiox(client):
    payload = {
        "entradas": [{"nome": "Dentto", "valores": [4300,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950]}],
        "fixas": [],
        "variaveis": []
    }
    with patch("app._get_db", return_value=_mock_conn()):
        resp = client.put("/api/financeiro/raiox", json=payload)
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_rotas_requerem_login(client_anonimo):
    for url, method in [
        ("/api/financeiro/transacoes", "GET"),
        ("/api/financeiro/transacoes", "POST"),
        ("/api/financeiro/raiox", "GET"),
        ("/api/financeiro/raiox", "PUT"),
    ]:
        resp = getattr(client_anonimo, method.lower())(url, json={})
        assert resp.status_code in (302, 401), f"{method} {url} deveria redirecionar"


# ── _init_aportes_table ───────────────────────────────────────────────────────

def test_init_aportes_table_cria_tabela(client):
    conn_mock = _mock_conn()
    with patch("app._get_db", return_value=conn_mock):
        import app as flask_app
        flask_app._init_aportes_table()
    conn_mock.cursor().execute.assert_called()
    conn_mock.commit.assert_called_once()
    conn_mock.close.assert_called_once()


# ── GET /api/financeiro/aportes ──────────────────────────────────────────────

def test_listar_aportes(client):
    rows = [
        {"id": 1, "mes_ano": "2026-04-01", "ativo": "ivvb11", "valor": 113.0},
        {"id": 2, "mes_ano": "2026-04-01", "ativo": "tesouro_selic", "valor": 170.0},
    ]
    with patch("app._get_db", return_value=_mock_conn(rows=rows)):
        resp = client.get("/api/financeiro/aportes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["ativo"] == "ivvb11"


def test_listar_aportes_anonimo_retorna_401(client_anonimo):
    resp = client_anonimo.get("/api/financeiro/aportes")
    assert resp.status_code in (401, 302)


# ── POST /api/financeiro/aportes ─────────────────────────────────────────────

def test_criar_aporte_valido(client):
    with patch("app._get_db", return_value=_mock_conn(novo_id=7)):
        resp = client.post("/api/financeiro/aportes", json={
            "mes_ano": "2026-04-01",
            "ativo": "ivvb11",
            "valor": 113.0
        })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["id"] == 7


def test_criar_aporte_ativo_invalido(client):
    resp = client.post("/api/financeiro/aportes", json={
        "mes_ano": "2026-04-01",
        "ativo": "bitcoin",
        "valor": 100.0
    })
    assert resp.status_code == 400


def test_criar_aporte_valor_zero(client):
    resp = client.post("/api/financeiro/aportes", json={
        "mes_ano": "2026-04-01",
        "ativo": "cdb",
        "valor": 0
    })
    assert resp.status_code == 400


def test_criar_aporte_sem_campos(client):
    resp = client.post("/api/financeiro/aportes", json={"ativo": "cdb"})
    assert resp.status_code == 400


# ── DELETE /api/financeiro/aportes/<id> ──────────────────────────────────────

def test_deletar_aporte_existente(client):
    conn_mock = _mock_conn()
    conn_mock.cursor.return_value.rowcount = 1
    with patch("app._get_db", return_value=conn_mock):
        resp = client.delete("/api/financeiro/aportes/1")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_deletar_aporte_nao_existente(client):
    conn_mock = _mock_conn()
    conn_mock.cursor.return_value.rowcount = 0
    with patch("app._get_db", return_value=conn_mock):
        resp = client.delete("/api/financeiro/aportes/999")
    assert resp.status_code == 404
