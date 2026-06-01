import sys, pytest
sys.path.insert(0, '/root/jake_desktop')
from unittest.mock import MagicMock, patch, call


def _mock_conn(rows=None, one=None):
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    if rows is not None:
        cur.fetchall.return_value = rows
    if one is not None:
        cur.fetchone.return_value = one
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


def test_palavra_do_dia_retorna_existente(client):
    """Se já existe palavra para hoje no banco, retorna sem chamar Claude."""
    row = {
        "id": 1, "palavra": "leverage", "classe_gramatical": "verb",
        "definicao_pt": "Aproveitar ao máximo", "exemplo_en": "We leverage data to grow.",
        "fonetica": "/ˈlevərɪdʒ/", "categoria": "marketing",
        "data_exibicao": "2026-06-01", "estudada": False
    }
    conn = _mock_conn(one=row)
    with patch("app._get_db", return_value=conn):
        resp = client.get("/api/ingles/palavra-do-dia")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["palavra"] == "leverage"


def test_palavra_do_dia_gera_quando_nao_existe(client):
    """Se não existe palavra para hoje, chama Claude e persiste."""
    conn = _mock_conn(one=None)
    # segundo fetchone para o INSERT RETURNING id
    conn.cursor().fetchone.side_effect = [None, {"id": 2}]

    palavra_gerada = {
        "palavra": "nurture", "classe_gramatical": "verb",
        "definicao_pt": "Cultivar relacionamentos", "exemplo_en": "Nurture your leads.",
        "fonetica": "/ˈnɜːrtʃər/"
    }
    mock_msg = MagicMock()
    import json
    mock_msg.content[0].text = json.dumps(palavra_gerada)

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.return_value = mock_msg

    with patch("app._get_db", return_value=conn), \
         patch("app._anthropic_client", return_value=mock_anthropic):
        resp = client.get("/api/ingles/palavra-do-dia")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["palavra"] == "nurture"


def test_init_ingles_tables_cria_tabelas():
    """_init_ingles_tables() deve executar CREATE TABLE IF NOT EXISTS para as 3 tabelas."""
    conn = _mock_conn()
    with patch("app._get_db", return_value=conn):
        import app
        app._init_ingles_tables()
    sql_calls = " ".join(str(c) for c in conn.cursor().execute.call_args_list)
    assert "ingles_palavras" in sql_calls
    assert "ingles_sessoes" in sql_calls
    assert "ingles_atividades" in sql_calls
    conn.commit.assert_called_once()
    conn.close.assert_called_once()
