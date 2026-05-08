"""Testes TDD para rotas /api/anuncios/*-lote e /api/anuncios/preview-url"""
import sys, json, uuid, pytest
sys.path.insert(0, '/root/jake_desktop')
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.secret_key = 'test-secret'
    with flask_app.app.test_client() as c:
        with c.session_transaction() as sess:
            sess['logged_in'] = True
        yield c


# ── POST /api/anuncios/publicar-lote ───────────────────────────────────────

def test_publicar_lote_retorna_lote_token(client):
    payload = {
        "cliente_id": 1,
        "campanha_nome": "Teste",
        "campanha_tipo": "MESSAGES",
        "orcamento_diario_total": 30.0,
        "lote_id": str(uuid.uuid4()),
        "conjuntos": [
            {
                "nome": "Conj 1",
                "audience_id": None,
                "criativos": [
                    {"creative_ref": {"tipo": "imagem", "hash": "abc"},
                     "copy": {"titulo": "T", "texto": "X", "cta": "SEND_MESSAGE"}}
                ]
            }
        ]
    }
    with patch('app._get_db'):
        r = client.post('/api/anuncios/publicar-lote',
                        json=payload, content_type='application/json')
    assert r.status_code == 200
    data = r.get_json()
    assert 'lote_token' in data
    assert len(data['lote_token']) == 36   # UUID format


def test_publicar_lote_sem_cliente_id_retorna_400(client):
    r = client.post('/api/anuncios/publicar-lote',
                    json={"conjuntos": []}, content_type='application/json')
    assert r.status_code == 400


def test_publicar_lote_conjuntos_vazios_retorna_400(client):
    r = client.post('/api/anuncios/publicar-lote',
                    json={"cliente_id": 1, "conjuntos": []}, content_type='application/json')
    assert r.status_code == 400


# ── POST /api/anuncios/copy-lote ───────────────────────────────────────────

def test_copy_lote_retorna_copies_por_indice(client):
    payload = {
        "cliente_id": 1,
        "campanha_tipo": "PURCHASE",
        "criativos": [
            {"indice": "0-0", "tipo": "imagem", "descricao": "Foto produto"},
            {"indice": "0-1", "tipo": "video", "descricao": "Video depoimento"},
        ]
    }
    mock_cliente = {"nome": "Teste", "segmento": "saude", "campanha_tipo": "PURCHASE"}
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps([
            {"indice": "0-0", "titulo": "Titulo A", "texto": "Texto A"},
            {"indice": "0-1", "titulo": "Titulo B", "texto": "Texto B"},
        ]))
    ]
    conn_mock = MagicMock()
    cur_mock = MagicMock()
    conn_mock.cursor.return_value = cur_mock
    cur_mock.fetchone.return_value = mock_cliente

    with patch('app._get_db', return_value=conn_mock), \
         patch('app._anthropic_client') as mock_ant:
        mock_ant.messages.create.return_value = mock_response
        r = client.post('/api/anuncios/copy-lote',
                        json=payload, content_type='application/json')
    assert r.status_code == 200
    data = r.get_json()
    assert 'copies' in data
    assert len(data['copies']) == 2
    assert data['copies'][0]['indice'] == '0-0'


# ── POST /api/anuncios/preview-url ─────────────────────────────────────────

def test_preview_url_rejeita_content_type_invalido(client):
    mock_resp = MagicMock()
    mock_resp.headers = {'Content-Type': 'application/pdf'}
    mock_resp.status_code = 200
    mock_resp.iter_content = lambda chunk_size: iter([b'data'])

    with patch('app.requests.get', return_value=mock_resp):
        r = client.post('/api/anuncios/preview-url',
                        json={"url": "http://example.com/doc.pdf"},
                        content_type='application/json')
    assert r.status_code == 400
    assert 'Formato' in r.get_json()['error']


def test_preview_url_imagem_retorna_tmp_uuid(client, tmp_path, monkeypatch):
    import app
    monkeypatch.setattr(app, '_TMP_DIR', str(tmp_path))

    mock_resp = MagicMock()
    mock_resp.headers = {'Content-Type': 'image/jpeg', 'Content-Length': '1000'}
    mock_resp.status_code = 200
    mock_resp.iter_content = lambda chunk_size: iter([b'\xff\xd8\xff'])  # JPEG magic bytes

    with patch('app.requests.get', return_value=mock_resp):
        r = client.post('/api/anuncios/preview-url',
                        json={"url": "http://example.com/foto.jpg"},
                        content_type='application/json')
    assert r.status_code == 200
    data = r.get_json()
    assert 'tmp_uuid' in data
    assert data['tipo'] == 'imagem'
