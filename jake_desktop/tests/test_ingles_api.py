import sys, pytest, json
sys.path.insert(0, '/root/jake_desktop')
from unittest.mock import MagicMock, patch


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
    with patch("app._get_db", return_value=conn), \
         patch("app._anthropic_client") as mock_claude:
        resp = client.get("/api/ingles/palavra-do-dia")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["palavra"] == "leverage"
    mock_claude.assert_not_called()


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
    mock_anthropic.messages.create.assert_called_once()


def test_audio_palavra(client):
    """GET /api/ingles/palavra/audio?palavra=leverage retorna base64 de áudio."""
    mock_tts = MagicMock()
    mock_tts.content = b"fake-audio-bytes"

    mock_openai = MagicMock()
    mock_openai.audio.speech.create.return_value = mock_tts

    with patch("app._openai_client", return_value=mock_openai):
        resp = client.get("/api/ingles/palavra/audio?palavra=leverage")
    assert resp.status_code == 200
    data = resp.get_json()
    import base64
    expected = base64.b64encode(b"fake-audio-bytes").decode()
    assert data["audio"] == expected


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
    # Migration v2 adds a second commit (one for CREATE TABLE, one for ALTER/INDEX)
    assert conn.commit.call_count >= 2
    conn.close.assert_called_once()


def test_listar_sessoes(client):
    """GET /api/ingles/sessoes retorna lista."""
    rows = [{"id": 1, "tema": "marketing", "mensagens": [], "created_at": "2026-06-01"}]
    with patch("app._get_db", return_value=_mock_conn(rows=rows)):
        resp = client.get("/api/ingles/sessoes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["tema"] == "marketing"


def test_criar_sessao(client):
    """POST /api/ingles/sessoes cria sessão com tema."""
    conn = _mock_conn(one={"id": 5})
    with patch("app._get_db", return_value=conn):
        resp = client.post("/api/ingles/sessoes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 5
    assert "tema" in data
    temas_validos = ["marketing and advertising", "travel and places", "business and entrepreneurship", "daily life and routines", "technology and innovation"]
    assert data["tema"] in temas_validos


def test_chat_sessao(client):
    """POST /api/ingles/sessoes/1/chat retorna resposta da IA."""
    sessao = {"id": 1, "tema": "marketing", "mensagens": []}
    conn = _mock_conn(one=sessao)

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="That's a great question about marketing!")]
    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.return_value = mock_msg

    with patch("app._get_db", return_value=conn), \
         patch("app._anthropic_client", return_value=mock_anthropic):
        resp = client.post("/api/ingles/sessoes/1/chat",
                           json={"mensagem": "What do you think about paid traffic?"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "resposta" in data
    assert len(data["resposta"]) > 0


def test_registrar_atividade(client):
    """POST /api/ingles/atividade registra atividade."""
    conn = _mock_conn()
    with patch("app._get_db", return_value=conn):
        resp = client.post("/api/ingles/atividade",
                           json={"tipo": "word_studied"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    conn.commit.assert_called_once()


def test_registrar_atividade_tipo_invalido(client):
    """POST /api/ingles/atividade rejeita tipo inválido."""
    resp = client.post("/api/ingles/atividade",
                       json={"tipo": "hacking_stuff"})
    assert resp.status_code == 400


def test_progresso(client):
    """GET /api/ingles/progresso retorna streak, total e calendario."""
    from datetime import date
    conn_mock = _mock_conn()
    conn_mock.cursor().fetchall.side_effect = [
        [{"data_atividade": date.today()}],  # atividades para streak/calendario
        [],                                    # sessoes
    ]
    conn_mock.cursor().fetchone.return_value = {"total": 5}
    with patch("app._get_db", return_value=conn_mock):
        resp = client.get("/api/ingles/progresso")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "streak" in data
    assert "total_palavras" in data
    assert "calendario" in data
    assert data["streak"] == 1
    assert data["total_palavras"] == 5


# ── Fixtures for palavras-do-dia tests ────────────────────────────────────────

@pytest.fixture
def app_client():
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.secret_key = 'test-secret'
    with flask_app.app.test_client() as c:
        with c.session_transaction() as sess:
            sess['logged_in'] = True
        yield c


@pytest.fixture
def mock_db():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    with patch("app._get_db", return_value=conn):
        yield conn, cur


def test_palavras_do_dia_retorna_lista(app_client, mock_db):
    """GET /api/ingles/palavras-do-dia retorna lista de até 10 palavras."""
    mock_conn, mock_cur = mock_db
    import datetime
    hoje = datetime.date.today()
    mock_cur.fetchone.return_value = {"count": 10}
    mock_cur.fetchall.return_value = [
        {"id": i, "palavra": f"word{i}", "classe_gramatical": "noun",
         "definicao_pt": f"def{i}", "exemplo_en": f"ex{i}",
         "fonetica": f"/w{i}/", "categoria": "cotidiano",
         "data_exibicao": hoje, "estudada": False, "created_at": "2026-06-01", "posicao": i}
        for i in range(1, 11)
    ]
    r = app_client.get("/api/ingles/palavras-do-dia")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) == 10
    assert data[0]["palavra"] == "word1"


def test_palavras_do_dia_gera_quando_vazio(app_client, mock_db):
    """GET /api/ingles/palavras-do-dia chama Claude quando banco está vazio."""
    mock_conn, mock_cur = mock_db
    mock_cur.fetchone.return_value = {"count": 0}
    words_json = json.dumps([
        {"palavra": f"word{i}", "classe_gramatical": "noun",
         "definicao_pt": f"def{i}", "exemplo_en": f"ex{i}",
         "fonetica": f"/w{i}/", "categoria": "cotidiano"}
        for i in range(1, 11)
    ])
    mock_cur.fetchall.return_value = [
        {"id": i, "palavra": f"word{i}", "classe_gramatical": "noun",
         "definicao_pt": f"def{i}", "exemplo_en": f"ex{i}",
         "fonetica": f"/w{i}/", "categoria": "cotidiano",
         "data_exibicao": "2026-06-01", "estudada": False, "created_at": "2026-06-01", "posicao": i}
        for i in range(1, 11)
    ]
    with patch("app._anthropic_client") as mock_claude:
        mock_claude.return_value.messages.create.return_value.content = [
            MagicMock(text=words_json)
        ]
        r = app_client.get("/api/ingles/palavras-do-dia")
    assert r.status_code == 200
    mock_claude.return_value.messages.create.assert_called_once()
