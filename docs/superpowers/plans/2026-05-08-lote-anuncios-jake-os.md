# Builder de Anúncios em Lote — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar aba "Lote" no módulo Anúncios do Jake OS que permite criar até 1 campanha × 10 conjuntos × 10 criativos (100 anúncios) com builder visual em 3 colunas, copy via Claude e progresso em tempo real via SSE.

**Architecture:** Backend Flask com 5 novos endpoints (POST payload → GET SSE stream, preview URL, tmp-preview, copy-lote) e modificações em meta_api.py (carrossel + nome no adset). Frontend em `lote.js` separado (IIFE, ~400 linhas) + HTML + CSS. Estado do lote fica em `_lote_payloads` (dict em memória no processo Flask).

**Tech Stack:** Flask (Python), SSE (text/event-stream), EventSource (browser), Meta Ads API v21.0, Claude claude-sonnet-4-6, psycopg2 (Neon PostgreSQL), CSS Grid/Flexbox

**Spec:** `docs/superpowers/specs/2026-05-08-lote-anuncios-jake-os-design.md`

---

## File Map

| Arquivo | Tipo | Responsabilidade |
|---------|------|-----------------|
| `meta/meta_api.py` | Modifica | `criar_conjunto` aceita `nome`; `criar_anuncio` suporta carrossel |
| `jake_desktop/app.py` | Modifica | `_lote_payloads` dict + 5 novos endpoints + `upload-criativo` aceita `tmp_uuid` |
| `jake_desktop/static/css/anuncios.css` | Modifica | CSS para layout 3 colunas do builder |
| `jake_desktop/templates/dashboard.html` | Modifica | Tab "Lote" + div `anu-tab-lote` com HTML do builder |
| `jake_desktop/static/js/lote.js` | Cria | Toda lógica do builder (estado, eventos, upload, SSE) |
| `jake_desktop/tests/test_lote_api.py` | Cria | Testes das rotas de lote |

---

## Task 1: DB migration + meta_api.py

**Files:**
- Modify: `meta/meta_api.py:366-423`
- Test: `jake_desktop/tests/test_lote_api.py` (criar junto com Task 2)

- [ ] **Step 1: Rodar migration no banco**

```bash
cd /root
/root/venv/bin/python3 -c "
from core.db import get_conn
conn = get_conn()
cur = conn.cursor()
cur.execute(\"ALTER TABLE ad_publish_log ADD COLUMN IF NOT EXISTS lote_id VARCHAR(36)\")
conn.commit()
conn.close()
print('OK — lote_id adicionado')
"
```
Expected: `OK — lote_id adicionado`

- [ ] **Step 2: Adicionar parâmetro `nome` em `criar_conjunto`**

Em `meta/meta_api.py`, linha 366, modificar a assinatura:

```python
def criar_conjunto(token: str, account_id: str, campaign_id: str,
                   campanha_tipo: str, publico: dict, localizacao: dict,
                   orcamento: float = None, optimization_goal: str = None,
                   pixel_id: str = None, nome: str = None) -> str:
```

E linha ~397, substituir:
```python
"name": f"Conjunto - {campanha_tipo}",
```
por:
```python
"name": nome or f"Conjunto - {campanha_tipo}",
```

- [ ] **Step 3: Adicionar suporte a carrossel em `criar_anuncio`**

Em `meta/meta_api.py`, após o bloco `else:` do vídeo (linha ~456), adicionar novo `elif` antes do bloco de criação do creative. Substituir toda a lógica if/else por:

```python
cta_value = {"value": {"link": link_url}} if link_url and cta != "SEND_MESSAGE" else {}

if creative_ref["tipo"] == "imagem":
    link_data = {
        "image_hash": creative_ref["hash"],
        "message": texto,
        "name": titulo,
        "call_to_action": {"type": cta, **cta_value},
    }
    if link_url and cta != "SEND_MESSAGE":
        link_data["link"] = link_url
    story_spec = {"page_id": page_id, "link_data": link_data}

elif creative_ref["tipo"] == "video":
    video_data = {
        "video_id": creative_ref["video_id"],
        "message": texto,
        "title": titulo,
        "call_to_action": {"type": cta, **cta_value},
    }
    if link_url and cta != "SEND_MESSAGE":
        video_data["link"] = link_url
    story_spec = {"page_id": page_id, "video_data": video_data}

elif creative_ref["tipo"] == "carrossel":
    child_attachments = [
        {
            "link": link_url,
            "image_hash": card["hash"],
            "call_to_action": {"type": cta, "value": {"link": link_url}},
        }
        for card in creative_ref["cards"]
    ]
    link_data = {
        "link": link_url,
        "child_attachments": child_attachments,
        "multi_share_optimized": True,
        # Sem call_to_action top-level — cada card define o seu
    }
    story_spec = {"page_id": page_id, "link_data": link_data}

else:
    raise ValueError(f"creative_ref.tipo desconhecido: {creative_ref['tipo']}")
```

- [ ] **Step 4: Verificar sintaxe**

```bash
/root/venv/bin/python3 -c "import ast; ast.parse(open('/root/meta/meta_api.py').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd /root
git add meta/meta_api.py
git commit -m "feat(meta-api): criar_conjunto aceita nome; criar_anuncio suporta carrossel"
```

---

## Task 2: Backend — endpoints de lote

**Files:**
- Modify: `jake_desktop/app.py` (após linha ~3500, antes das rotas de `/api/criativos/`)
- Create: `jake_desktop/tests/test_lote_api.py`

### 2a: Testes das rotas (TDD)

- [ ] **Step 1: Criar arquivo de testes**

Criar `/root/jake_desktop/tests/test_lote_api.py`:

```python
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
            {"indice": "0-1", "tipo": "video", "descricao": "Vídeo depoimento"},
        ]
    }
    mock_cliente = {"nome": "Teste", "segmento": "saude", "campanha_tipo": "PURCHASE"}
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps([
            {"indice": "0-0", "titulo": "Título A", "texto": "Texto A"},
            {"indice": "0-1", "titulo": "Título B", "texto": "Texto B"},
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
    assert 'Formato não suportado' in r.get_json()['error']


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
```

- [ ] **Step 2: Rodar testes para confirmar falha**

```bash
cd /root/jake_desktop
/root/venv/bin/pytest tests/test_lote_api.py -v 2>&1 | head -40
```
Expected: FAIL — rotas não existem ainda.

### 2b: Implementar endpoints

- [ ] **Step 3: Adicionar `_lote_payloads` e imports no topo de app.py**

Após as outras declarações de variável global no topo de `jake_desktop/app.py` (procurar por `_VALID_TOKEN_KEYS`), adicionar:

```python
import glob as _glob
import threading as _threading
import requests as _requests_lib

_lote_payloads: dict = {}   # lote_token → payload dict (em memória)
_TMP_DIR = "/tmp"           # diretório para arquivos temporários de preview
```

> Nota: `requests` provavelmente já está importado como `import requests`. Use o alias `_requests_lib` apenas para o `preview-url`; cheque se `requests` já existe no arquivo antes de adicionar o import.

- [ ] **Step 4: Implementar `POST /api/anuncios/publicar-lote`**

Adicionar em `jake_desktop/app.py` após a rota `anuncios_publicar`:

```python
@app.route("/api/anuncios/publicar-lote", methods=["POST"])
@login_required
def anuncios_publicar_lote():
    """Etapa 1: valida payload, armazena em memória, retorna lote_token."""
    d = request.get_json() or {}
    if not d.get("cliente_id"):
        return jsonify({"error": "cliente_id obrigatório"}), 400
    if not d.get("conjuntos"):
        return jsonify({"error": "conjuntos não podem ser vazios"}), 400
    lote_token = str(uuid.uuid4())
    _lote_payloads[lote_token] = d
    return jsonify({"lote_token": lote_token})
```

> `uuid` provavelmente não está importado — adicionar `import uuid` no topo do arquivo se necessário.

- [ ] **Step 5: Implementar `GET /api/anuncios/publicar-lote/stream/<lote_token>`**

```python
@app.route("/api/anuncios/publicar-lote/stream/<lote_token>")
@login_required
def anuncios_publicar_lote_stream(lote_token):
    """Etapa 2: processa lote sequencialmente via SSE."""
    payload = _lote_payloads.pop(lote_token, None)

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    def gerar():
        if payload is None:
            yield _sse({"tipo": "erro_fatal", "erro": "Lote não encontrado ou já processado"})
            return

        cliente_id   = payload["cliente_id"]
        camp_nome    = payload.get("campanha_nome", "Campanha Jake OS")
        camp_tipo    = payload.get("campanha_tipo", "MESSAGES")
        orcamento_total = float(payload.get("orcamento_diario_total", 0))
        conjuntos    = payload["conjuntos"]
        lote_id      = payload.get("lote_id", lote_token)
        n_conjuntos  = len(conjuntos)

        try:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("SELECT * FROM ad_client_profiles WHERE id = %s", (cliente_id,))
            cliente = cur.fetchone(); conn.close()
        except Exception as e:
            yield _sse({"tipo": "erro_fatal", "erro": f"Erro ao buscar cliente: {e}"})
            return
        if not cliente:
            yield _sse({"tipo": "erro_fatal", "erro": "Cliente não encontrado"})
            return

        token_key = cliente["token_key"]
        if token_key not in _VALID_TOKEN_KEYS:
            yield _sse({"tipo": "erro_fatal", "erro": "token_key inválido"}); return
        token      = os.getenv(token_key, "")
        account_id = cliente["account_id"]
        page_id    = cliente.get("page_id", "")
        link_url   = cliente.get("link_url") or ""
        localizacao = cliente.get("localizacao_json") or {}
        opt_goal   = cliente.get("optimization_goal") or None
        pixel_id   = cliente.get("pixel_id") or None

        cbo = camp_tipo not in ("ENGAGEMENT", "PURCHASE")
        try:
            campaign_id = _meta_api.criar_campanha(
                token, account_id, camp_tipo, camp_nome, orcamento_total, cbo=cbo
            )
            yield _sse({"tipo": "campanha_ok", "campaign_id": campaign_id})
        except Exception as e:
            yield _sse({"tipo": "erro_fatal", "erro": str(e)}); return

        total = sum(len(c.get("criativos", [])) for c in conjuntos)
        sucesso = 0; falha = 0

        for ci, conjunto in enumerate(conjuntos):
            audience_id = conjunto.get("audience_id")
            publico = cliente.get("publico_json") or {}
            if audience_id:
                try:
                    conn2 = _get_db(); cur2 = conn2.cursor()
                    cur2.execute("SELECT targeting_json FROM ad_audiences WHERE id=%s", (audience_id,))
                    row = cur2.fetchone(); conn2.close()
                    if row and row["targeting_json"]:
                        publico = row["targeting_json"]
                except Exception:
                    pass

            orcamento_conj = (orcamento_total / n_conjuntos) if camp_tipo in ("ENGAGEMENT", "PURCHASE") else None
            try:
                adset_id = _meta_api.criar_conjunto(
                    token, account_id, campaign_id, camp_tipo, publico, localizacao,
                    orcamento=orcamento_conj, optimization_goal=opt_goal,
                    pixel_id=pixel_id, nome=conjunto.get("nome")
                )
                yield _sse({"tipo": "conjunto_ok", "conjunto_idx": ci, "adset_id": adset_id})
            except Exception as e:
                yield _sse({"tipo": "conjunto_erro", "conjunto_idx": ci, "erro": str(e)})
                falha += len(conjunto.get("criativos", []))
                continue

            for ri, criativo in enumerate(conjunto.get("criativos", [])):
                copy = criativo.get("copy", {})
                try:
                    ad_id = _meta_api.criar_anuncio(
                        token, account_id, adset_id, page_id,
                        criativo["creative_ref"],
                        copy.get("titulo", ""), copy.get("texto", ""),
                        copy.get("cta", "SEND_MESSAGE"),
                        link_url=link_url
                    )
                    try:
                        conn3 = _get_db(); cur3 = conn3.cursor()
                        cur3.execute("""
                            INSERT INTO ad_publish_log
                                (cliente_id, account_id, campaign_id, adset_id, ad_id,
                                 status, audience_id, lote_id, payload_json)
                            VALUES (%s,%s,%s,%s,%s,'sucesso',%s,%s,%s)
                        """, (cliente_id, account_id, campaign_id, adset_id, ad_id,
                              audience_id, lote_id, json.dumps(criativo)))
                        conn3.commit(); conn3.close()
                    except Exception:
                        pass
                    sucesso += 1
                    yield _sse({"tipo": "anuncio_ok", "conjunto_idx": ci,
                                "criativo_idx": ri, "ad_id": ad_id})
                except Exception as e:
                    falha += 1
                    yield _sse({"tipo": "anuncio_erro", "conjunto_idx": ci,
                                "criativo_idx": ri, "erro": str(e)})

        yield _sse({"tipo": "fim", "total": total, "sucesso": sucesso, "falha": falha})

    return app.response_class(
        gerar(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
```

- [ ] **Step 6: Implementar `POST /api/anuncios/preview-url`**

```python
@app.route("/api/anuncios/preview-url", methods=["POST"])
@login_required
def anuncios_preview_url():
    """Baixa URL externa, detecta tipo, salva em /tmp, retorna tmp_uuid."""
    d = request.get_json() or {}
    url = (d.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url obrigatória"}), 400

    MAX_SIZE = 50 * 1024 * 1024  # 50MB
    try:
        resp = requests.get(url, timeout=30, stream=True)
        content_type = resp.headers.get("Content-Type", "")
        content_length = int(resp.headers.get("Content-Length", 0) or 0)
        if content_length > MAX_SIZE:
            return jsonify({"error": "Arquivo muito grande (máx 50MB)"}), 400

        if content_type.startswith("image/"):
            tipo = "imagem"
            ext  = content_type.split("/")[1].split(";")[0].strip() or "jpg"
        elif content_type.startswith("video/"):
            tipo = "video"
            ext  = content_type.split("/")[1].split(";")[0].strip() or "mp4"
        else:
            return jsonify({"error": "Formato não suportado. Use imagem ou vídeo."}), 400

        tmp_uuid_val = str(uuid.uuid4())
        tmp_path = os.path.join(_TMP_DIR, f"{tmp_uuid_val}.{ext}")
        size = 0
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                size += len(chunk)
                if size > MAX_SIZE:
                    f.close()
                    os.remove(tmp_path)
                    return jsonify({"error": "Arquivo muito grande (máx 50MB)"}), 400
                f.write(chunk)

        # Apagar em 30 minutos
        _threading.Timer(1800, lambda p=tmp_path: os.path.exists(p) and os.remove(p)).start()

        return jsonify({"tmp_uuid": tmp_uuid_val, "tipo": tipo, "ok": True})
    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout ao acessar a URL (30s)"}), 400
    except Exception as e:
        return jsonify({"error": f"Não foi possível acessar a URL: {e}"}), 400
```

- [ ] **Step 7: Implementar `GET /api/anuncios/tmp-preview/<uuid>`**

```python
@app.route("/api/anuncios/tmp-preview/<tmp_uuid_val>")
@login_required
def anuncios_tmp_preview(tmp_uuid_val):
    """Serve arquivo temporário de preview."""
    # Sanitize: apenas alphanum e hífens (UUID format)
    import re
    if not re.match(r'^[a-f0-9\-]{36}$', tmp_uuid_val):
        return jsonify({"error": "uuid inválido"}), 400
    matches = _glob.glob(os.path.join(_TMP_DIR, f"{tmp_uuid_val}.*"))
    if not matches:
        return jsonify({"error": "Preview não encontrado ou expirado"}), 404
    from flask import send_file
    return send_file(matches[0])
```

- [ ] **Step 8: Implementar `POST /api/anuncios/copy-lote`**

```python
@app.route("/api/anuncios/copy-lote", methods=["POST"])
@login_required
def anuncios_copy_lote():
    """Gera N copies via Claude para o lote."""
    d = request.get_json() or {}
    cliente_id  = d.get("cliente_id")
    camp_tipo   = d.get("campanha_tipo", "MESSAGES")
    criativos   = d.get("criativos", [])
    if not cliente_id or not criativos:
        return jsonify({"error": "cliente_id e criativos obrigatórios"}), 400

    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute("SELECT nome, segmento FROM ad_client_profiles WHERE id=%s", (cliente_id,))
        cliente = cur.fetchone(); conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    nome_cliente = (cliente or {}).get("nome", "cliente")
    segmento     = (cliente or {}).get("segmento", "")
    objetivo_txt = {
        "MESSAGES": "gerar mensagens no WhatsApp",
        "ENGAGEMENT": "gerar engajamento no post",
        "PURCHASE": "gerar conversões/vendas na landing page",
    }.get(camp_tipo, "gerar conversões")
    cta_sugerido = "SEND_MESSAGE" if camp_tipo == "MESSAGES" else "LEARN_MORE"

    lista_txt = "\n".join(
        f"- indice: {c['indice']}, tipo: {c['tipo']}, descrição: {c.get('descricao','(sem descrição)')}"
        for c in criativos
    )
    prompt = f"""Cliente: {nome_cliente} | Segmento: {segmento} | Objetivo: {objetivo_txt}

Gere {len(criativos)} copies distintas para anúncios Meta Ads. Uma copy por criativo listado abaixo.
Cada copy deve ter:
- titulo: máx 40 caracteres, impactante
- texto: máx 125 caracteres, direto ao ponto com CTA implícito ({cta_sugerido})

Criativos:
{lista_txt}

Responda SOMENTE com JSON válido, no formato:
[{{"indice": "X-X", "titulo": "...", "texto": "..."}}]"""

    try:
        resp = _anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        # Extrair JSON do response (pode vir com markdown ```json)
        import re
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        copies = json.loads(match.group(0) if match else raw)
        return jsonify({"copies": copies})
    except Exception as e:
        return jsonify({"error": f"Erro ao gerar copies: {e}"}), 500
```

- [ ] **Step 9: Modificar `upload-criativo` para aceitar `tmp_uuid`**

No início da função `anuncios_upload_criativo`, substituir:

```python
def anuncios_upload_criativo():
    if "arquivo" not in request.files:
        return jsonify({"error": "Campo 'arquivo' ausente"}), 400
    arquivo    = request.files["arquivo"]
```

por:

```python
def anuncios_upload_criativo():
    tmp_uuid_val = request.form.get("tmp_uuid", "").strip()
    account_id   = request.form.get("account_id", "")
    token_key    = request.form.get("token_key", "META_ACCESS_TOKEN")
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    if not account_id:
        return jsonify({"error": "account_id obrigatório"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    # Caminho via tmp_uuid (criativo importado por URL)
    if tmp_uuid_val:
        import re
        if not re.match(r'^[a-f0-9\-]{36}$', tmp_uuid_val):
            return jsonify({"error": "tmp_uuid inválido"}), 400
        matches = _glob.glob(os.path.join(_TMP_DIR, f"{tmp_uuid_val}.*"))
        if not matches:
            return jsonify({"error": "Arquivo temporário não encontrado ou expirado"}), 404
        tmp_path = matches[0]
        ext = os.path.splitext(tmp_path)[1].lower()
        filename = f"url_import{ext}"
        with open(tmp_path, "rb") as f:
            file_bytes = f.read()
        mime = "video/mp4" if ext == ".mp4" else "image/jpeg"
        try:
            if "video" in mime:
                video_id = _meta_api.upload_video(token, account_id, file_bytes, filename)
                os.remove(tmp_path)
                return jsonify({"tipo": "video", "video_id": video_id, "ok": True})
            else:
                resultado = _meta_api.upload_imagem(token, account_id, file_bytes, filename)
                os.remove(tmp_path)
                return jsonify({"tipo": "imagem", "hash": resultado["hash"], "ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Caminho normal via upload de arquivo
    if "arquivo" not in request.files:
        return jsonify({"error": "Campo 'arquivo' ou 'tmp_uuid' ausente"}), 400
    arquivo = request.files["arquivo"]
```

> **Atenção:** após inserir esse bloco, remover a duplicação das variáveis `account_id`, `token_key`, `token` que já existiam no código original (agora movidas para o topo).

- [ ] **Step 10: Verificar sintaxe**

```bash
/root/venv/bin/python3 -c "import ast; ast.parse(open('/root/jake_desktop/app.py').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 11: Rodar testes**

```bash
cd /root/jake_desktop
/root/venv/bin/pytest tests/test_lote_api.py -v
```
Expected: todos os testes PASS (ou pelo menos sem erros de import).

- [ ] **Step 12: Commit**

```bash
cd /root
git add jake_desktop/app.py jake_desktop/tests/test_lote_api.py
git commit -m "feat(lote): endpoints publicar-lote, preview-url, tmp-preview, copy-lote"
```

---

## Task 3: CSS para o builder de lote

**Files:**
- Modify: `jake_desktop/static/css/anuncios.css`

- [ ] **Step 1: Adicionar CSS do builder no final de `anuncios.css`**

```css
/* ── Builder de Lote ─────────────────────────────── */
.lote-topo { display:grid; grid-template-columns:1fr 1fr 1fr auto; gap:.75rem; align-items:end; margin-bottom:1rem; padding-bottom:1rem; border-bottom:1px solid rgba(0,229,255,.1); }
.lote-contador { font-family:var(--ff-h); font-size:.8rem; color:rgba(0,229,255,.6); white-space:nowrap; padding-top:.3rem; }
.lote-colunas { display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem; min-height:400px; }
.lote-col { display:flex; flex-direction:column; gap:.5rem; }
.lote-col-header { font-family:var(--ff-h); font-size:.8rem; letter-spacing:.08em; text-transform:uppercase; color:rgba(0,229,255,.5); padding:.4rem .6rem; border-bottom:1px solid rgba(0,229,255,.08); display:flex; align-items:center; justify-content:space-between; }
.lote-col-body { flex:1; display:flex; flex-direction:column; gap:.5rem; overflow-y:auto; }
.lote-card { background:rgba(0,229,255,.03); border:1px solid rgba(0,229,255,.1); border-radius:8px; padding:.75rem; cursor:pointer; transition:border-color .2s,background .2s; }
.lote-card:hover { border-color:rgba(0,229,255,.3); background:rgba(0,229,255,.06); }
.lote-card.active { border-color:rgba(0,229,255,.5); background:rgba(0,229,255,.08); }
.lote-card.erro { border-color:rgba(255,82,82,.4); }
.lote-card-titulo { font-size:.85rem; color:#e0e0e0; margin-bottom:.3rem; display:flex; align-items:center; gap:.4rem; }
.lote-card-meta { font-size:.72rem; color:rgba(176,190,197,.4); }
.lote-card-actions { display:flex; gap:.3rem; margin-top:.4rem; }
.lote-tipo-btns { display:flex; gap:.3rem; margin-bottom:.5rem; flex-wrap:wrap; }
.lote-tipo-btn { background:rgba(0,0,0,.2); border:1px solid rgba(0,229,255,.15); color:rgba(176,190,197,.6); border-radius:6px; padding:.25rem .6rem; font-size:.75rem; cursor:pointer; transition:all .2s; }
.lote-tipo-btn.active { background:rgba(0,229,255,.12); border-color:rgba(0,229,255,.4); color:#00e5ff; }
.lote-slot-preview { width:100%; max-height:120px; object-fit:cover; border-radius:6px; border:1px solid rgba(0,229,255,.15); margin-top:.4rem; display:block; }
.lote-carrossel-cards { display:flex; gap:.3rem; flex-wrap:wrap; margin-top:.4rem; }
.lote-carrossel-thumb { width:48px; height:48px; object-fit:cover; border-radius:4px; border:1px solid rgba(0,229,255,.2); }
.lote-url-row { display:flex; gap:.4rem; align-items:center; }
.lote-url-row .anu-input { flex:1; }
.lote-rodape { display:flex; justify-content:space-between; align-items:center; margin-top:1rem; padding-top:1rem; border-top:1px solid rgba(0,229,255,.1); }
.lote-btn-gerar { background:rgba(105,240,174,.08); border:1px solid rgba(105,240,174,.25); color:#69f0ae; border-radius:8px; padding:.55rem 1.2rem; font-size:.85rem; cursor:pointer; transition:all .2s; }
.lote-btn-gerar:hover { background:rgba(105,240,174,.15); }
.lote-btn-publicar { background:linear-gradient(135deg,rgba(0,229,255,.15),rgba(105,240,174,.1)); border:1px solid rgba(0,229,255,.35); color:#00e5ff; border-radius:10px; padding:.7rem 1.8rem; font-family:var(--ff-h); font-size:.95rem; cursor:pointer; transition:all .2s; }
.lote-btn-publicar:hover:not(:disabled) { background:linear-gradient(135deg,rgba(0,229,255,.25),rgba(105,240,174,.18)); box-shadow:0 0 20px rgba(0,229,255,.12); }
.lote-btn-publicar:disabled { opacity:.35; cursor:not-allowed; }
/* Modal de progresso SSE */
.lote-progress-modal { max-width:560px; }
.lote-progress-title { font-family:var(--ff-h); color:#00e5ff; margin:0 0 1rem; font-size:1.1rem; }
.lote-progress-log { background:rgba(0,0,0,.3); border-radius:8px; padding:.75rem 1rem; max-height:260px; overflow-y:auto; font-size:.8rem; line-height:1.8; color:#b0bec5; font-family:monospace; }
.lote-progress-log .ok { color:#69f0ae; }
.lote-progress-log .erro { color:#ff5252; }
.lote-progress-log .info { color:#00e5ff; }
.lote-progress-bar-wrap { margin:.75rem 0; }
.lote-progress-bar { height:6px; background:rgba(0,229,255,.1); border-radius:3px; overflow:hidden; }
.lote-progress-fill { height:100%; background:linear-gradient(90deg,#00e5ff,#69f0ae); transition:width .4s; }
.lote-progress-stats { font-size:.78rem; color:rgba(176,190,197,.5); margin-top:.3rem; }
.lote-publico-row { display:flex; align-items:center; gap:.5rem; }
.lote-publico-row .anu-select { flex:1; }
```

- [ ] **Step 2: Verificar que o arquivo não quebrou**

```bash
wc -l /root/jake_desktop/static/css/anuncios.css
```
Expected: número maior que 81 (linhas anteriores + novas)

- [ ] **Step 3: Commit**

```bash
cd /root
git add jake_desktop/static/css/anuncios.css
git commit -m "feat(lote): CSS do builder de lote em 3 colunas"
```

---

## Task 4: HTML — tab Lote

**Files:**
- Modify: `jake_desktop/templates/dashboard.html` (linha ~514-516, tab buttons; linha ~684, após anu-tab-publicos)

- [ ] **Step 1: Adicionar botão da tab Lote**

Na linha 516 de `dashboard.html`, após o botão "Públicos Salvos":

```html
<button class="anu-btn-secondary anu-tab-btn" data-tab="lote" onclick="anuSwitchTab('lote')" style="font-size:13px">Lote ⚡</button>
```

- [ ] **Step 2: Adicionar a div `anu-tab-lote` após `anu-tab-publicos`**

Após o fechamento de `</div><!-- /anu-tab-publicos -->` (linha ~684), inserir:

```html
<!-- Tab: Lote -->
<div id="anu-tab-lote" style="display:none">
  <!-- Topo: configurações da campanha -->
  <div class="lote-topo">
    <label class="anu-label">Nome da campanha
      <input type="text" id="lote-camp-nome" class="anu-input" placeholder="Campanha Maio 2026">
    </label>
    <label class="anu-label">Tipo de campanha
      <select id="lote-camp-tipo" class="anu-select">
        <option value="MESSAGES">Mensagem (WhatsApp)</option>
        <option value="ENGAGEMENT">Engajamento</option>
        <option value="PURCHASE">Conversão (Purchase)</option>
      </select>
    </label>
    <label class="anu-label">Orçamento total (R$/dia)
      <input type="number" id="lote-orcamento" class="anu-input" placeholder="50.00" step="0.01" min="1">
    </label>
    <div class="lote-contador" id="lote-contador">0 × 0 = 0 anúncios</div>
  </div>

  <!-- 3 colunas -->
  <div class="lote-colunas">
    <!-- Col 1: Conjuntos -->
    <div class="lote-col">
      <div class="lote-col-header">
        <span>Conjuntos</span>
        <button class="anu-btn-icon" id="lote-btn-add-conjunto" title="Adicionar conjunto">+</button>
      </div>
      <div class="lote-col-body" id="lote-conjuntos-body"></div>
    </div>
    <!-- Col 2: Criativos -->
    <div class="lote-col">
      <div class="lote-col-header">
        <span id="lote-criativos-header">Criativos</span>
        <button class="anu-btn-icon" id="lote-btn-add-criativo" title="Adicionar criativo" style="display:none">+</button>
      </div>
      <div class="lote-col-body" id="lote-criativos-body">
        <div class="anu-empty-state" style="height:auto;padding:2rem 0">
          <div class="anu-empty-text" style="font-size:.82rem">Selecione um conjunto</div>
        </div>
      </div>
    </div>
    <!-- Col 3: Copy -->
    <div class="lote-col">
      <div class="lote-col-header">
        <span id="lote-copy-header">Copy</span>
      </div>
      <div class="lote-col-body" id="lote-copy-body">
        <div class="anu-empty-state" style="height:auto;padding:2rem 0">
          <div class="anu-empty-text" style="font-size:.82rem">Selecione um criativo</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Rodapé -->
  <div class="lote-rodape">
    <button class="lote-btn-gerar" id="lote-btn-gerar-copies">✦ Gerar todas as copies</button>
    <button class="lote-btn-publicar" id="lote-btn-publicar" disabled>🚀 Publicar Lote</button>
  </div>

  <!-- Modal de progresso SSE -->
  <div class="anu-modal-overlay hidden" id="lote-modal-progresso">
    <div class="anu-modal lote-progress-modal">
      <h3 class="lote-progress-title">Publicando lote...</h3>
      <div class="lote-progress-bar-wrap">
        <div class="lote-progress-bar"><div class="lote-progress-fill" id="lote-prog-fill" style="width:0%"></div></div>
        <div class="lote-progress-stats" id="lote-prog-stats">Iniciando...</div>
      </div>
      <div class="lote-progress-log" id="lote-prog-log"></div>
      <div class="anu-modal-actions" style="margin-top:1rem">
        <button class="anu-btn-secondary hidden" id="lote-prog-fechar">Fechar</button>
      </div>
    </div>
  </div>
</div><!-- /anu-tab-lote -->
```

- [ ] **Step 3: Atualizar `anuSwitchTab` em `anuncios.js` para incluir `'lote'`**

No início de `jake_desktop/static/js/anuncios.js`, a função `anuSwitchTab` itera sobre `['publicar', 'publicos']`. Mudar para:

```javascript
window.anuSwitchTab = function(tab) {
  ['publicar', 'publicos', 'lote'].forEach(function(t) {
    var el  = document.getElementById('anu-tab-' + t);
    var btn = document.querySelector('[data-tab="' + t + '"]');
    if (el)  el.style.display = (t === tab) ? '' : 'none';
    if (btn) btn.classList.toggle('active', t === tab);
  });
  if (tab === 'publicos') carregarPublicos();
  if (tab === 'lote' && typeof loteInit === 'function') loteInit();
};
```

- [ ] **Step 4: Verificar página carrega sem erros**

Reiniciar Jake OS e abrir no browser. Aba "Lote ⚡" deve aparecer. Clicar nela deve mostrar o layout (sem JS ainda — as colunas estarão visíveis mas vazias).

```bash
lsof -ti:5050 | xargs kill -9 2>/dev/null; sleep 1
PYTHONPATH=/root nohup /root/venv/bin/python3 /root/jake_desktop/app.py >> /root/logs/jake_desktop.log 2>&1 &
sleep 2 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/
```
Expected: `302`

- [ ] **Step 5: Commit**

```bash
cd /root
git add jake_desktop/templates/dashboard.html jake_desktop/static/js/anuncios.js
git commit -m "feat(lote): tab Lote no dashboard + HTML do builder 3 colunas"
```

---

## Task 5: lote.js — estado e conjuntos

**Files:**
- Create: `jake_desktop/static/js/lote.js`
- Modify: `jake_desktop/templates/dashboard.html` (adicionar `<script src="/static/js/lote.js">`)

- [ ] **Step 1: Adicionar script tag no dashboard.html**

Antes do fechamento de `</body>` ou junto com os outros scripts do módulo anúncios:

```html
<script src="/static/js/lote.js"></script>
```

- [ ] **Step 2: Criar `/root/jake_desktop/static/js/lote.js` com estado e conjuntos**

```javascript
/* ──────────────────────────────────────────────────────
   Jake OS — Builder de Anúncios em Lote
────────────────────────────────────────────────────── */
(function () {
  'use strict';

  // ── Estado ─────────────────────────────────────────
  var _conjuntos = [];       // [{nome, audience_id, criativos:[]}]
  var _conjIdx   = null;     // índice do conjunto ativo
  var _criatIdx  = null;     // índice do criativo ativo
  var _publicos  = [];       // cache de públicos salvos
  var _cliente   = null;     // cliente ativo (objeto)
  var MAX_CONJ   = 10;
  var MAX_CRIAT  = 10;

  // ── Helpers ────────────────────────────────────────
  function _val(id)       { var el=document.getElementById(id); return el?el.value:''; }
  function _set(id, v)    { var el=document.getElementById(id); if(el) el.value=v||''; }
  function _el(id)        { return document.getElementById(id); }
  function _show(id)      { var el=_el(id); if(el) el.classList.remove('hidden'); }
  function _hide(id)      { var el=_el(id); if(el) el.classList.add('hidden'); }

  // ── Init (chamado por anuSwitchTab) ────────────────
  window.loteInit = function() {
    // Carregar cliente ativo de anuncios.js (variável global exposta)
    if (typeof window._anuClienteAtivo !== 'undefined') {
      _cliente = window._anuClienteAtivo;
    }
    _carregarPublicos();
    _renderTopo();
    _renderConjuntos();
    _renderCriativos();
    _renderCopy();
    _bindEvents();
  };

  function _renderTopo() {
    if (_cliente) {
      _set('lote-camp-tipo', _cliente.campanha_tipo || 'MESSAGES');
    }
    _atualizarContador();
  }

  function _atualizarContador() {
    var nConj  = _conjuntos.length;
    var nCriat = _conjuntos.reduce(function(s,c){ return s+c.criativos.length; }, 0);
    var el = _el('lote-contador');
    if (el) el.textContent = nConj + ' conjuntos × ' + (nConj ? Math.round(nCriat/nConj*10)/10 : 0) + ' criativos ≈ ' + nCriat + ' anúncios';
    _atualizarBotaoPublicar();
  }

  function _atualizarBotaoPublicar() {
    var btn = _el('lote-btn-publicar');
    if (!btn) return;
    var ok = _conjuntos.length > 0 && _conjuntos.every(function(c) {
      return c.criativos.length > 0 && c.criativos.every(function(r) {
        return r.creative_ref && r.copy && r.copy.titulo && r.copy.texto;
      });
    });
    btn.disabled = !ok;
    btn.title = ok ? '' : 'Preencha todos os criativos e copies antes de publicar';
  }

  // ── Públicos ───────────────────────────────────────
  function _carregarPublicos() {
    if (!_cliente) return;
    fetch('/api/anuncios/audiences?account_id=' + (_cliente.account_id || ''))
      .then(function(r){ return r.json(); })
      .then(function(d){ _publicos = d.audiences || []; })
      .catch(function(){});
  }

  function _pubOptions(selected) {
    var opts = '<option value="">— padrão do perfil —</option>';
    _publicos.forEach(function(p) {
      opts += '<option value="'+p.id+'"'+(p.id===selected?' selected':'')+'>'+p.nome+'</option>';
    });
    return opts;
  }

  // ── Renderizar Conjuntos ───────────────────────────
  function _renderConjuntos() {
    var body = _el('lote-conjuntos-body');
    if (!body) return;
    if (_conjuntos.length === 0) {
      body.innerHTML = '<div class="anu-empty-state" style="height:auto;padding:1.5rem 0"><div class="anu-empty-text" style="font-size:.82rem">Clique + para adicionar um conjunto</div></div>';
      return;
    }
    body.innerHTML = _conjuntos.map(function(c, i) {
      var isActive = i === _conjIdx;
      return '<div class="lote-card'+(isActive?' active':'') +'" onclick="loteSelConj('+i+')">' +
        '<div class="lote-card-titulo">'+
          '<span>'+c.nome+'</span>'+
          '<span style="margin-left:auto;font-size:.7rem;color:rgba(176,190,197,.4)">'+c.criativos.length+' criativos</span>'+
        '</div>'+
        '<div class="lote-publico-row">'+
          '<select class="anu-select" style="font-size:.75rem" onchange="loteSetPublico('+i+',this.value)" onclick="event.stopPropagation()">'+_pubOptions(c.audience_id)+'</select>'+
        '</div>'+
        '<div class="lote-card-actions">'+
          '<button class="anu-btn-icon" onclick="event.stopPropagation();loteRenomearConj('+i+')" title="Renomear">✎</button>'+
          '<button class="anu-btn-icon" style="color:rgba(255,82,82,.5)" onclick="event.stopPropagation();loteRemoverConj('+i+')" title="Remover">✕</button>'+
        '</div>'+
      '</div>';
    }).join('');
  }

  window.loteSelConj = function(i) {
    _conjIdx  = i;
    _criatIdx = null;
    _renderConjuntos();
    _renderCriativos();
    _renderCopy();
  };

  window.loteSetPublico = function(i, val) {
    _conjuntos[i].audience_id = val ? parseInt(val) : null;
  };

  window.loteRenomearConj = function(i) {
    var novo = prompt('Nome do conjunto:', _conjuntos[i].nome);
    if (novo && novo.trim()) { _conjuntos[i].nome = novo.trim(); _renderConjuntos(); }
  };

  window.loteRemoverConj = function(i) {
    if (!confirm('Remover conjunto "'+_conjuntos[i].nome+'" e todos os seus criativos?')) return;
    _conjuntos.splice(i, 1);
    if (_conjIdx >= _conjuntos.length) _conjIdx = _conjuntos.length ? _conjuntos.length-1 : null;
    _criatIdx = null;
    _renderConjuntos(); _renderCriativos(); _renderCopy();
    _atualizarContador();
  };

  function _adicionarConjunto() {
    if (_conjuntos.length >= MAX_CONJ) { alert('Máximo de '+MAX_CONJ+' conjuntos.'); return; }
    var n = _conjuntos.length + 1;
    _conjuntos.push({ nome: 'Conjunto ' + n, audience_id: null, criativos: [] });
    _conjIdx  = _conjuntos.length - 1;
    _criatIdx = null;
    _renderConjuntos(); _renderCriativos(); _renderCopy();
    _atualizarContador();
  }

  // ── Renderizar Criativos ───────────────────────────
  function _renderCriativos() {
    var body   = _el('lote-criativos-body');
    var header = _el('lote-criativos-header');
    var btnAdd = _el('lote-btn-add-criativo');
    if (!body) return;

    if (_conjIdx === null) {
      body.innerHTML = '<div class="anu-empty-state" style="height:auto;padding:2rem 0"><div class="anu-empty-text" style="font-size:.82rem">Selecione um conjunto</div></div>';
      if (header) header.textContent = 'Criativos';
      if (btnAdd) btnAdd.style.display = 'none';
      return;
    }
    var conj = _conjuntos[_conjIdx];
    if (header) header.textContent = 'Criativos — ' + conj.nome;
    if (btnAdd) btnAdd.style.display = '';

    if (conj.criativos.length === 0) {
      body.innerHTML = '<div class="anu-empty-state" style="height:auto;padding:1.5rem 0"><div class="anu-empty-text" style="font-size:.82rem">Clique + para adicionar um criativo</div></div>';
      return;
    }
    body.innerHTML = conj.criativos.map(function(r, i) {
      var isActive = i === _criatIdx;
      var tipoIcon = {imagem:'🖼', video:'🎬', url:'🔗', carrossel:'🎠'}[r.tipo] || '?';
      var temCopy  = r.copy && r.copy.titulo && r.copy.texto;
      var temRef   = !!r.creative_ref;
      return '<div class="lote-card'+(isActive?' active':'') + (!temRef||!temCopy?' erro':'') + '" onclick="loteSelCriat('+i+')">' +
        '<div class="lote-card-titulo">' +
          tipoIcon + ' Criativo ' + (i+1) +
          (temRef ? ' <span style="color:#69f0ae;font-size:.7rem">✓ upload</span>' : ' <span style="color:#ff5252;font-size:.7rem">✕ sem criativo</span>') +
          (temCopy ? ' <span style="color:#69f0ae;font-size:.7rem">✓ copy</span>' : ' <span style="color:#ffd740;font-size:.7rem">! sem copy</span>') +
        '</div>' +
        '<div class="lote-card-actions">' +
          '<button class="anu-btn-icon" style="color:rgba(255,82,82,.5)" onclick="event.stopPropagation();loteRemoverCriat('+i+')" title="Remover">✕</button>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  window.loteSelCriat = function(i) {
    _criatIdx = i;
    _renderCriativos();
    _renderCopy();
  };

  window.loteRemoverCriat = function(i) {
    _conjuntos[_conjIdx].criativos.splice(i, 1);
    if (_criatIdx >= _conjuntos[_conjIdx].criativos.length) _criatIdx = null;
    _renderCriativos(); _renderCopy();
    _atualizarContador();
  };

  function _adicionarCriativo() {
    if (_conjIdx === null) return;
    var conj = _conjuntos[_conjIdx];
    if (conj.criativos.length >= MAX_CRIAT) { alert('Máximo de '+MAX_CRIAT+' criativos por conjunto.'); return; }
    conj.criativos.push({ tipo: 'imagem', creative_ref: null, copy: { titulo:'', texto:'', cta: _ctaPadrao() } });
    _criatIdx = conj.criativos.length - 1;
    _renderCriativos();
    _renderCopy();
    _atualizarContador();
  }

  function _ctaPadrao() {
    return _val('lote-camp-tipo') === 'MESSAGES' ? 'SEND_MESSAGE' : 'LEARN_MORE';
  }

  // ── Renderizar Copy ────────────────────────────────
  function _renderCopy() {
    var body   = _el('lote-copy-body');
    var header = _el('lote-copy-header');
    if (!body) return;

    if (_conjIdx === null || _criatIdx === null) {
      body.innerHTML = '<div class="anu-empty-state" style="height:auto;padding:2rem 0"><div class="anu-empty-text" style="font-size:.82rem">Selecione um criativo</div></div>';
      if (header) header.textContent = 'Copy';
      return;
    }
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    if (header) header.textContent = 'Copy — Criativo ' + (_criatIdx+1);

    body.innerHTML =
      '<div id="lote-criativo-upload-area"></div>' +
      '<label class="anu-label" style="margin-top:.75rem">Título (máx 40)<input type="text" id="lote-copy-titulo" class="anu-input" maxlength="40" placeholder="Título do anúncio" value="'+_esc(r.copy.titulo||'')+'"></label>' +
      '<label class="anu-label">Texto (máx 125)<textarea id="lote-copy-texto" class="anu-textarea" rows="3" maxlength="125" placeholder="Texto do anúncio">'+_esc(r.copy.texto||'')+'</textarea></label>' +
      '<label class="anu-label">CTA<select id="lote-copy-cta" class="anu-select">' +
        '<option value="SEND_MESSAGE"'+(r.copy.cta==='SEND_MESSAGE'?' selected':'')+'>Enviar mensagem</option>' +
        '<option value="LEARN_MORE"'+(r.copy.cta==='LEARN_MORE'?' selected':'')+'>Saiba mais</option>' +
        '<option value="SIGN_UP"'+(r.copy.cta==='SIGN_UP'?' selected':'')+'>Cadastre-se</option>' +
        '<option value="SHOP_NOW"'+(r.copy.cta==='SHOP_NOW'?' selected':'')+'>Comprar agora</option>' +
      '</select></label>';

    // Renderizar área de upload do criativo
    _renderUploadArea(r);

    // Bind copy fields
    ['lote-copy-titulo','lote-copy-texto','lote-copy-cta'].forEach(function(id) {
      var el = _el(id);
      if (el) el.addEventListener('change', _saveCopyField);
      if (el && id !== 'lote-copy-cta') el.addEventListener('input', _saveCopyField);
    });
  }

  function _esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'); }

  function _saveCopyField() {
    if (_conjIdx === null || _criatIdx === null) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    r.copy.titulo = _val('lote-copy-titulo');
    r.copy.texto  = _val('lote-copy-texto');
    r.copy.cta    = _val('lote-copy-cta');
    _renderCriativos();   // atualiza badges ✓/✕
    _atualizarBotaoPublicar();
  }

  // ── Bind Events ────────────────────────────────────
  function _bindEvents() {
    var btnConj = _el('lote-btn-add-conjunto');
    if (btnConj) btnConj.onclick = _adicionarConjunto;

    var btnCriat = _el('lote-btn-add-criativo');
    if (btnCriat) btnCriat.onclick = _adicionarCriativo;

    var btnGerar = _el('lote-btn-gerar-copies');
    if (btnGerar) btnGerar.onclick = _gerarCopies;

    var btnPublicar = _el('lote-btn-publicar');
    if (btnPublicar) btnPublicar.onclick = _publicarLote;
  }

  // (continua em Task 6: upload; Task 7: gerar copies; Task 8: SSE publicar)

  // Expor referência ao cliente ativo para sincronização com anuncios.js
  // anuncios.js deve chamar: window._anuClienteAtivo = clienteObj; ao selecionar cliente
  // (implementado em Task 6 junto com ajuste em anuncios.js)

})();
```

- [ ] **Step 3: Expor cliente ativo em anuncios.js**

Em `/root/jake_desktop/static/js/anuncios.js`, na função `renderSidebar` ou onde o cliente é selecionado (procurar por `_clienteAtivo =`), adicionar após a atribuição:

```javascript
window._anuClienteAtivo = _clienteAtivo;
```

- [ ] **Step 4: Verificar no browser**

Reiniciar Jake OS. Abrir aba Lote. Deve aparecer layout 3 colunas. Clicar "+ Conjunto" deve adicionar cards na coluna 1.

- [ ] **Step 5: Commit**

```bash
cd /root
git add jake_desktop/static/js/lote.js jake_desktop/static/js/anuncios.js jake_desktop/templates/dashboard.html
git commit -m "feat(lote): lote.js estado + conjuntos + criativos + copy UI"
```

---

## Task 6: lote.js — upload de criativos

**Files:**
- Modify: `jake_desktop/static/js/lote.js` (adicionar funções de upload)

- [ ] **Step 1: Adicionar função `_renderUploadArea` e handlers de upload**

Dentro do IIFE de `lote.js`, adicionar após `_renderCopy`:

```javascript
  // ── Upload de Criativos ────────────────────────────
  function _renderUploadArea(r) {
    var area = _el('lote-criativo-upload-area');
    if (!area) return;

    var tiposHTML = ['imagem','video','url','carrossel'].map(function(t) {
      var icon = {imagem:'🖼',video:'🎬',url:'🔗',carrossel:'🎠'}[t];
      return '<button class="lote-tipo-btn'+(r.tipo===t?' active':'')+'" onclick="loteTipoChange(\''+t+'\')">'+ icon +' '+t+'</button>';
    }).join('');

    var uploadHTML = '';
    if (r.tipo === 'imagem' || r.tipo === 'video') {
      uploadHTML =
        '<div class="anu-dropzone" onclick="document.getElementById(\'lote-file-input\').click()">' +
          '<input type="file" id="lote-file-input" class="anu-file-hidden" accept="'+(r.tipo==='video'?'video/*':'image/*')+'">' +
          '<span class="anu-dropzone-icon">'+(r.tipo==='video'?'🎬':'🖼')+'</span>' +
          '<p>'+(r.creative_ref ? 'Criativo enviado ✓ — clique para trocar' : 'Clique para selecionar '+r.tipo)+'</p>' +
        '</div>' +
        (r.preview ? '<img class="lote-slot-preview" src="'+r.preview+'">' : '');
    } else if (r.tipo === 'url') {
      uploadHTML =
        '<div class="lote-url-row">' +
          '<input type="text" id="lote-url-input" class="anu-input" placeholder="https://...jpg ou .mp4" value="'+(r._url||'')+'">' +
          '<button class="anu-btn-secondary" onclick="lotePreviewUrl()">Pré-visualizar</button>' +
        '</div>' +
        (r.preview ? '<img class="lote-slot-preview" src="'+r.preview+'"><br><button class="anu-btn-primary" style="margin-top:.4rem;font-size:.8rem" onclick="loteConfirmarUrl()">✓ Confirmar e enviar</button>' : '');
    } else if (r.tipo === 'carrossel') {
      var thumbs = (r.creative_ref && r.creative_ref.cards ? r.creative_ref.cards : []).map(function(card) {
        return '<img class="lote-carrossel-thumb" src="'+(card._preview||'')+'">'; // preview local
      }).join('');
      uploadHTML =
        '<div class="lote-carrossel-cards" id="lote-carrossel-thumbs">' + thumbs + '</div>' +
        '<button class="anu-btn-secondary" style="margin-top:.4rem;font-size:.8rem" onclick="document.getElementById(\'lote-carrossel-input\').click()">+ Adicionar imagem</button>' +
        '<input type="file" id="lote-carrossel-input" class="anu-file-hidden" accept="image/*">';
    }

    area.innerHTML = '<div class="lote-tipo-btns">' + tiposHTML + '</div>' + uploadHTML;

    // Bind file input
    var fi = _el('lote-file-input');
    if (fi) fi.onchange = function() { if(this.files[0]) _uploadArquivo(this.files[0]); };
    var ci = _el('lote-carrossel-input');
    if (ci) ci.onchange = function() { if(this.files[0]) _uploadCarrosselCard(this.files[0]); };
  }

  window.loteTipoChange = function(tipo) {
    if (_conjIdx === null || _criatIdx === null) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    r.tipo = tipo;
    r.creative_ref = null;
    r.preview = null;
    r._url = null;
    _renderCopy();
  };

  function _getCriatCliente() {
    return _cliente || {};
  }

  function _uploadArquivo(file) {
    if (_conjIdx === null || _criatIdx === null) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    var c = _getCriatCliente();
    var fd = new FormData();
    fd.append('arquivo', file);
    fd.append('account_id', c.account_id || '');
    fd.append('token_key', c.token_key || 'META_ACCESS_TOKEN');

    var area = _el('lote-criativo-upload-area');
    if (area) area.innerHTML += '<div class="anu-copy-loading"><span class="anu-spinner"></span> Enviando...</div>';

    fetch('/api/anuncios/upload-criativo', { method:'POST', body: fd })
      .then(function(resp){ return resp.json(); })
      .then(function(d) {
        if (d.error) { alert('Erro upload: ' + d.error); return; }
        r.creative_ref = d;
        r.preview = URL.createObjectURL(file);
        _renderCriativos();
        _renderCopy();
        _atualizarBotaoPublicar();
      })
      .catch(function(e){ alert('Erro de rede: ' + e); });
  }

  function _uploadCarrosselCard(file) {
    if (_conjIdx === null || _criatIdx === null) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    var c = _getCriatCliente();
    var fd = new FormData();
    fd.append('arquivo', file);
    fd.append('account_id', c.account_id || '');
    fd.append('token_key', c.token_key || 'META_ACCESS_TOKEN');

    fetch('/api/anuncios/upload-criativo', { method:'POST', body: fd })
      .then(function(resp){ return resp.json(); })
      .then(function(d) {
        if (d.error) { alert('Erro upload: ' + d.error); return; }
        if (!r.creative_ref) r.creative_ref = { tipo: 'carrossel', cards: [] };
        r.creative_ref.cards.push({ hash: d.hash, _preview: URL.createObjectURL(file) });
        _renderCriativos();
        _renderCopy();
        _atualizarBotaoPublicar();
      })
      .catch(function(e){ alert('Erro de rede: ' + e); });
  }

  window.lotePreviewUrl = function() {
    if (_conjIdx === null || _criatIdx === null) return;
    var url = _val('lote-url-input');
    if (!url) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    r._url = url;

    fetch('/api/anuncios/preview-url', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url: url})
    })
    .then(function(resp){ return resp.json(); })
    .then(function(d) {
      if (d.error) { alert('Erro: ' + d.error); return; }
      r._tmp_uuid = d.tmp_uuid;
      r._tipo_url = d.tipo;
      r.preview = '/api/anuncios/tmp-preview/' + d.tmp_uuid;
      _renderCopy();
    })
    .catch(function(e){ alert('Erro de rede: ' + e); });
  };

  window.loteConfirmarUrl = function() {
    if (_conjIdx === null || _criatIdx === null) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    if (!r._tmp_uuid) return;
    var c = _getCriatCliente();
    var fd = new FormData();
    fd.append('tmp_uuid', r._tmp_uuid);
    fd.append('account_id', c.account_id || '');
    fd.append('token_key', c.token_key || 'META_ACCESS_TOKEN');

    fetch('/api/anuncios/upload-criativo', { method:'POST', body: fd })
      .then(function(resp){ return resp.json(); })
      .then(function(d) {
        if (d.error) { alert('Erro upload: ' + d.error); return; }
        r.creative_ref = d;
        r.tipo = d.tipo;
        _renderCriativos();
        _renderCopy();
        _atualizarBotaoPublicar();
      })
      .catch(function(e){ alert('Erro de rede: ' + e); });
  };
```

- [ ] **Step 2: Verificar no browser**

Selecionar um conjunto, adicionar criativo, mudar tipo para "imagem", fazer upload de uma imagem. Deve aparecer preview e badge "✓ upload".

- [ ] **Step 3: Commit**

```bash
cd /root
git add jake_desktop/static/js/lote.js
git commit -m "feat(lote): upload de criativos (imagem, video, URL, carrossel)"
```

---

## Task 7: lote.js — geração de copies

**Files:**
- Modify: `jake_desktop/static/js/lote.js`

- [ ] **Step 1: Implementar `_gerarCopies`**

```javascript
  // ── Gerar Copies ───────────────────────────────────
  function _gerarCopies() {
    if (!_cliente) { alert('Selecione um cliente primeiro.'); return; }
    var todos = [];
    _conjuntos.forEach(function(conj, ci) {
      conj.criativos.forEach(function(r, ri) {
        todos.push({ indice: ci+'-'+ri, tipo: r.tipo, descricao: r._url ? 'Criativo importado de URL' : 'Criativo '+r.tipo });
      });
    });
    if (todos.length === 0) { alert('Adicione criativos antes de gerar copies.'); return; }

    var btn = _el('lote-btn-gerar-copies');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Gerando...'; }

    fetch('/api/anuncios/copy-lote', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        cliente_id: _cliente.id,
        campanha_tipo: _val('lote-camp-tipo'),
        criativos: todos
      })
    })
    .then(function(r){ return r.json(); })
    .then(function(d) {
      if (d.error) { alert('Erro: ' + d.error); return; }
      (d.copies || []).forEach(function(cp) {
        var parts = cp.indice.split('-');
        var ci = parseInt(parts[0]), ri = parseInt(parts[1]);
        if (_conjuntos[ci] && _conjuntos[ci].criativos[ri]) {
          _conjuntos[ci].criativos[ri].copy = {
            titulo: cp.titulo || '',
            texto:  cp.texto  || '',
            cta:    _ctaPadrao()
          };
        }
      });
      _renderCriativos();
      _renderCopy();
      _atualizarBotaoPublicar();
    })
    .catch(function(e){ alert('Erro de rede: ' + e); })
    .finally(function() {
      if (btn) { btn.disabled = false; btn.textContent = '✦ Gerar todas as copies'; }
    });
  }
```

- [ ] **Step 2: Testar no browser**

Adicionar 2 conjuntos × 2 criativos, clicar "Gerar todas as copies". Campos de título/texto devem ser preenchidos automaticamente.

- [ ] **Step 3: Commit**

```bash
cd /root
git add jake_desktop/static/js/lote.js
git commit -m "feat(lote): geração de copies via Claude para todos os slots"
```

---

## Task 8: lote.js — publicação via SSE

**Files:**
- Modify: `jake_desktop/static/js/lote.js`

- [ ] **Step 1: Implementar `_publicarLote` com EventSource**

```javascript
  // ── Publicar Lote via SSE ──────────────────────────
  function _publicarLote() {
    if (!_cliente) { alert('Selecione um cliente.'); return; }

    var conjuntosPayload = _conjuntos.map(function(conj) {
      return {
        nome:        conj.nome,
        audience_id: conj.audience_id || null,
        criativos:   conj.criativos.map(function(r) {
          return { creative_ref: r.creative_ref, copy: r.copy };
        })
      };
    });

    var loteId = _uuid4();
    var payload = {
      cliente_id:           _cliente.id,
      campanha_nome:        _val('lote-camp-nome') || 'Campanha Jake OS',
      campanha_tipo:        _val('lote-camp-tipo'),
      orcamento_diario_total: parseFloat(_val('lote-orcamento')) || 0,
      lote_id:              loteId,
      conjuntos:            conjuntosPayload
    };

    // Etapa 1: POST para armazenar payload
    fetch('/api/anuncios/publicar-lote', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    })
    .then(function(r){ return r.json(); })
    .then(function(d) {
      if (d.error) { alert('Erro: ' + d.error); return; }
      _abrirModalProgresso();
      // Etapa 2: GET SSE stream
      var es = new EventSource('/api/anuncios/publicar-lote/stream/' + d.lote_token);
      var totalAnuncios = conjuntosPayload.reduce(function(s,c){ return s+c.criativos.length; }, 0);
      var feito = 0;

      es.onmessage = function(e) {
        var ev = JSON.parse(e.data);
        _logProgresso(ev);
        if (ev.tipo === 'anuncio_ok' || ev.tipo === 'anuncio_erro') {
          feito++;
          var pct = Math.round(feito / totalAnuncios * 100);
          var fill = _el('lote-prog-fill');
          var stats = _el('lote-prog-stats');
          if (fill) fill.style.width = pct + '%';
          if (stats) stats.textContent = feito + ' / ' + totalAnuncios + ' anúncios processados';
        }
        if (ev.tipo === 'fim' || ev.tipo === 'erro_fatal') {
          es.close();
          _finalizarProgresso(ev);
        }
      };
      es.onerror = function() {
        es.close();
        _logProgresso({tipo:'anuncio_erro', erro:'Conexão interrompida'});
        _finalizarProgresso({tipo:'fim', total:0, sucesso:0, falha:0});
      };
    })
    .catch(function(e){ alert('Erro de rede: ' + e); });
  }

  function _abrirModalProgresso() {
    var overlay = _el('lote-modal-progresso');
    if (overlay) overlay.classList.remove('hidden');
    var log = _el('lote-prog-log');
    if (log) log.innerHTML = '';
    var fill = _el('lote-prog-fill');
    if (fill) fill.style.width = '0%';
    var stats = _el('lote-prog-stats');
    if (stats) stats.textContent = 'Iniciando...';
    _hide('lote-prog-fechar');
  }

  function _logProgresso(ev) {
    var log = _el('lote-prog-log');
    if (!log) return;
    var cls = 'info', txt = '';
    if (ev.tipo === 'campanha_ok')   { cls='ok';   txt='✓ Campanha criada: ' + ev.campaign_id; }
    else if (ev.tipo === 'conjunto_ok')  { cls='ok';   txt='✓ Conjunto '+(ev.conjunto_idx+1)+' criado: ' + ev.adset_id; }
    else if (ev.tipo === 'conjunto_erro'){ cls='erro';  txt='✕ Conjunto '+(ev.conjunto_idx+1)+' falhou: ' + ev.erro; }
    else if (ev.tipo === 'anuncio_ok')   { cls='ok';   txt='✓ Anúncio '+(ev.criativo_idx+1)+' do conjunto '+(ev.conjunto_idx+1)+': ' + ev.ad_id; }
    else if (ev.tipo === 'anuncio_erro') { cls='erro';  txt='✕ Anúncio '+(ev.criativo_idx+1)+' do conjunto '+(ev.conjunto_idx+1)+': ' + ev.erro; }
    else if (ev.tipo === 'erro_fatal')   { cls='erro';  txt='✕ Erro fatal: ' + ev.erro; }
    else if (ev.tipo === 'fim')          { cls='info';  txt='━━ Finalizado: '+ev.sucesso+' criados, '+ev.falha+' falhas'; }
    var line = document.createElement('div');
    line.className = cls;
    line.textContent = txt;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
  }

  function _finalizarProgresso(ev) {
    var stats = _el('lote-prog-stats');
    var title = _el('lote-modal-progresso') && _el('lote-modal-progresso').querySelector('.lote-progress-title');
    if (title) title.textContent = ev.tipo === 'erro_fatal' ? 'Erro na publicação' : 'Publicação concluída';
    if (stats && ev.tipo === 'fim') stats.textContent = ev.sucesso + ' anúncios criados, ' + ev.falha + ' falhas';
    var fill = _el('lote-prog-fill');
    if (fill && ev.tipo === 'fim') fill.style.width = '100%';
    _show('lote-prog-fechar');
    var btn = _el('lote-prog-fechar');
    if (btn) btn.onclick = function() {
      var overlay = _el('lote-modal-progresso');
      if (overlay) overlay.classList.add('hidden');
    };
  }

  function _uuid4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random()*16|0, v = c==='x'?r:(r&0x3|0x8);
      return v.toString(16);
    });
  }
```

- [ ] **Step 2: Teste end-to-end manual**

1. Selecionar cliente Vielife na sidebar
2. Clicar na aba "Lote ⚡"
3. Adicionar 1 conjunto
4. Adicionar 1 criativo (imagem), fazer upload
5. Clicar "Gerar todas as copies"
6. Verificar que copy foi preenchida
7. Clicar "Publicar Lote"
8. Modal de progresso deve abrir e mostrar eventos em tempo real
9. Ao fim, mostrar "Publicação concluída: 1 criado, 0 falhas"

- [ ] **Step 3: Verificar no Gerenciador de Anúncios da Meta**

O anúncio deve aparecer com status PAUSED na conta correta.

- [ ] **Step 4: Commit final**

```bash
cd /root
git add jake_desktop/static/js/lote.js
git commit -m "feat(lote): publicação em lote via SSE com progresso em tempo real"
```

---

## Task 9: Restart e validação final

- [ ] **Step 1: Reiniciar Jake OS**

```bash
lsof -ti:5050 | xargs kill -9 2>/dev/null; sleep 1
PYTHONPATH=/root nohup /root/venv/bin/python3 /root/jake_desktop/app.py >> /root/logs/jake_desktop.log 2>&1 &
sleep 2 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/
```
Expected: `302`

- [ ] **Step 2: Rodar todos os testes**

```bash
cd /root/jake_desktop
/root/venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: todos PASS (ou mesmo resultado de antes mais os novos testes).

- [ ] **Step 3: Commit de encerramento**

```bash
cd /root
git add -A
git status   # confirmar que só arquivos esperados estão staged
git commit -m "feat(lote): builder de anúncios em lote completo

- Meta de desempenho configurável (Grupo A)
- Pixel ID no perfil do cliente (Grupo A)
- Públicos carregam na aba Publicar (Grupo A)
- Builder 3 colunas: conjuntos × criativos × copy
- Upload: imagem, vídeo, URL (preview + confirm), carrossel
- Copy via Claude por slot, editável
- Publicação via SSE com progresso em tempo real
- Endpoint copy-lote, preview-url, tmp-preview, publicar-lote

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
