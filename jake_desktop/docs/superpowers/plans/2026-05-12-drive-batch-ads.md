# Drive Batch Ads — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Drive Batch" tab to the Anuncios module that lets the user paste a public Google Drive folder link, auto-generate AI copies per image via Claude Vision, configure N adsets with budget and creative count, and publish to one or multiple Meta Ads clients via SSE stream.

**Architecture:** 6 new Flask endpoints in `app.py` (listar, campanhas, iniciar-copies, gerar-copies/stream, preparar, drive/stream), a new `drive-batch.js` IIFE, HTML wizard with 4 steps, and CSS styles. Drive accessed via REST API with public API key (`GOOGLE_API_KEY` in `.env`). Two SSE streams: one for copy generation, one for publishing. Same patterns as existing lote/multi-cliente.

**Tech Stack:** Flask, `requests` (Drive API v3 + Meta API), `anthropic` SDK (Claude Vision, already imported), vanilla JS ES5 IIFE, PostgreSQL via psycopg2.

---

## Context for Implementers

### File locations
- Main Flask app: `/root/jake_desktop/app.py` (~6900 lines — read in sections, never all at once)
- Dashboard HTML: `/root/jake_desktop/templates/dashboard.html`
- Anuncios JS: `/root/jake_desktop/static/js/anuncios.js`
- Anuncios CSS: `/root/jake_desktop/static/css/anuncios.css`
- Meta API helpers: `/root/meta/meta_api.py`
- New file to create: `/root/jake_desktop/static/js/drive-batch.js`

### Key globals already in app.py (lines 43-45)
```python
_VALID_TOKEN_KEYS = {"META_TOKEN_PILOTI", "META_TOKEN_DENTTO", "META_ACCESS_TOKEN", "META_TOKEN_VIELIFE"}
_lote_payloads: dict = {}   # shared in-memory token store
_TMP_DIR = "/tmp"
```

### Confirmed meta_api.py signatures
```python
_meta_api.upload_imagem(token, account_id, file_bytes, filename)  # → {"hash": "..."}
_meta_api.criar_campanha(token, account_id, camp_tipo, nome, orcamento, cbo=True)  # → campaign_id
_meta_api.criar_conjunto(token, account_id, campaign_id, camp_tipo, publico, localizacao,
                         orcamento=None, optimization_goal=None, pixel_id=None, nome=None)  # → adset_id
_meta_api.criar_anuncio(token, account_id, adset_id, page_id, creative_ref,
                        titulo, texto, cta, link_url="")  # → ad_id
# creative_ref for image: {"tipo": "imagem", "hash": "..."}
_meta_api.deletar_objeto_meta(token, object_id)  # → None
```

### Important: internal conversions (do NOT convert manually)
- `criar_campanha` and `criar_conjunto` both convert R$ → centavos internally (`int(orcamento * 100)`) — pass R$ float directly
- `criar_campanha` maps `campanha_tipo` to Meta objective internally via `_OBJETIVO_MAP` — pass the tipo string as-is
- `_get_db()` uses `cursor_factory=psycopg2.extras.RealDictCursor` — row access by column name always works

### CBO logic (important for multiple adsets)
- `MESSAGES` → `cbo=True`: budget at campaign level = `num_conjuntos × orcamento_por_conjunto`; adsets get `orcamento=None`
- `PURCHASE` / `ENGAGEMENT` → `cbo=False`: campaign gets no budget; each adset gets `orcamento=orcamento_por_conjunto`

### CTA mapping
```python
_CAMP_CTA = {"MESSAGES": "SEND_MESSAGE", "PURCHASE": "SHOP_NOW", "ENGAGEMENT": "LEARN_MORE"}
```

### Claude Vision pattern (already used in /api/anuncios/copy)
```python
client = _anthropic_client()  # returns _anthropic.Anthropic(api_key=...)
msg = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=300,
    system="...",
    messages=[{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_string}},
        {"type": "text", "text": "..."}
    ]}]
)
raw = msg.content[0].text.strip()
```

### SSE pattern (bare generator, no stream_with_context)
```python
def _gerar():
    yield "data: " + json.dumps({"status": "..."}) + "\n\n"

return app.response_class(
    _gerar(),
    mimetype="text/event-stream",
    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
)
```

### Where to insert in app.py
Add new Drive Batch section **after** the multi-cliente block (which ends around line 3855). Look for the comment `# ABA SUBIR ANÚNCIOS — Builder de Lote` and insert BEFORE it.

### Tab switching in anuncios.js (lines 18-27)
```javascript
window.anuSwitchTab = function(tab) {
  ['publicar', 'publicos', 'lote', 'multi'].forEach(function(t) { ... });
  if (tab === 'lote' && typeof loteInit === 'function') loteInit();
  if (tab === 'multi' && typeof mcInit === 'function') mcInit();
```
Add `'drive'` to the array and call `window.driveBatchInit()` for that tab.

### Tab HTML location in dashboard.html
Tab buttons are around line 491-494. Tab content divs end at `</div><!-- /anu-tab-multi -->` around line 829. Add new button after line 494 and new div after line 829.

---

## Task 1: Backend — `/drive/listar` and `/drive/campanhas` endpoints

**Files:**
- Modify: `/root/jake_desktop/app.py` (insert before `# ABA SUBIR ANÚNCIOS — Builder de Lote` comment)

### What these endpoints do
- `POST /api/anuncios/drive/listar`: takes a Google Drive folder URL, lists image files via Drive API v3 with public API key
- `GET /api/anuncios/drive/campanhas?cliente_id=X`: fetches active/paused Meta campaigns for a client's account

- [ ] **Step 1: Find insertion point**

Run: `grep -n "ABA SUBIR ANÚNCIOS — Builder de Lote" /root/jake_desktop/app.py`
Note the line number. Insert the new block 2 lines above it (after the multi-cliente section ends).

- [ ] **Step 2: Add the Drive Batch section header and two endpoints**

Find the line with `# ABA SUBIR ANÚNCIOS — Builder de Lote` in app.py and insert BEFORE it:

```python
# ══════════════════════════════════════════════════════════════════════════
#  ABA DRIVE BATCH — Publicar lote via Google Drive
# ══════════════════════════════════════════════════════════════════════════

_DRIVE_MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/png":  ".png",
    "image/webp": ".webp",
    "image/gif":  ".gif",
}


@app.route("/api/anuncios/drive/listar", methods=["POST"])
@login_required
def drive_listar():
    """Lista arquivos de imagem de uma pasta pública do Google Drive."""
    d = request.get_json() or {}
    url = (d.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL obrigatória"}), 400

    # Extrair folder_id da URL
    folder_id = None
    if "/folders/" in url:
        folder_id = url.split("/folders/")[1].split("?")[0].split("/")[0]
    elif "id=" in url:
        from urllib.parse import urlparse, parse_qs
        folder_id = parse_qs(urlparse(url).query).get("id", [None])[0]
    if not folder_id:
        return jsonify({"error": "Não foi possível extrair o ID da pasta. Use um link no formato drive.google.com/drive/folders/..."}), 400

    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return jsonify({"error": "GOOGLE_API_KEY não configurada no servidor"}), 500

    try:
        resp = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            params={
                "q": f"'{folder_id}' in parents",
                "fields": "files(id,name,mimeType,thumbnailLink)",
                "key": api_key,
                "pageSize": 100,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return jsonify({"error": f"Erro ao acessar Google Drive: {e}"}), 500

    files = [
        {"id": f["id"], "name": f["name"], "thumbnailLink": f.get("thumbnailLink", ""),
         "ext": _DRIVE_MIME_EXT.get(f["mimeType"], ".jpg"), "mimeType": f["mimeType"]}
        for f in data.get("files", [])
        if f.get("mimeType") in _DRIVE_MIME_EXT
    ]
    if not files:
        return jsonify({"error": "Nenhuma imagem encontrada na pasta (suporta JPG, PNG, WebP, GIF)"}), 400

    return jsonify({"files": files, "total": len(files)})


@app.route("/api/anuncios/drive/campanhas")
@login_required
def drive_campanhas():
    """Busca campanhas ativas/pausadas de um cliente para seleção na UI."""
    cliente_id = request.args.get("cliente_id")
    if not cliente_id:
        return jsonify({"error": "cliente_id obrigatório"}), 400

    conn = None
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT account_id, token_key FROM ad_client_profiles WHERE id = %s",
            (cliente_id,)
        )
        row = cur.fetchone()
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar cliente: {e}"}), 500
    finally:
        try: conn.close()
        except Exception: pass

    if not row:
        return jsonify({"error": "Cliente não encontrado"}), 404

    account_id = row["account_id"]
    token_key  = row["token_key"]
    token      = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"Token '{token_key}' não configurado"}), 500

    try:
        resp = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/campaigns",
            params={
                "fields": "id,name,effective_status",
                "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED"]}]',
                "access_token": token,
                "limit": 50,
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            return jsonify({"error": data["error"].get("message", "Erro Meta API")}), 400
        campanhas = [{"id": c["id"], "name": c["name"], "status": c.get("effective_status", "")}
                     for c in data.get("data", [])]
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar campanhas: {e}"}), 500

    return jsonify({"campanhas": campanhas})

```

- [ ] **Step 3: Restart Jake OS and test listar endpoint manually**

```bash
cd /root/jake_desktop && pkill -f "python app.py" 2>/dev/null; sleep 1
source .venv/bin/activate && nohup python app.py > /tmp/jakeos.log 2>&1 &
sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/login
```
Expected: 200

```bash
# Test with a real public Drive folder URL (use the sheet folder Bruno already has)
curl -s -b cookies.txt -c cookies.txt -X POST http://localhost:5050/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@jakeos.local","password":"Jake@2024!"}' | head -50
```
Then test listar:
```bash
curl -s -b cookies.txt -X POST http://localhost:5050/api/anuncios/drive/listar \
  -H "Content-Type: application/json" \
  -d '{"url":"https://drive.google.com/drive/folders/PASTE_A_PUBLIC_FOLDER_ID_HERE"}' | python3 -m json.tool
```
Expected: `{"files": [...], "total": N}` or `{"error": "GOOGLE_API_KEY não configurada no servidor"}` if key not set yet (that's OK — key is added in a later step or by Bruno).

- [ ] **Step 4: Commit**

```bash
cd /root/jake_desktop
git add app.py
git commit -m "feat(drive-batch): endpoints listar e campanhas"
```

---

## Task 2: Backend — iniciar-copies + gerar-copies/stream endpoints

**Files:**
- Modify: `/root/jake_desktop/app.py` (add after drive_campanhas, still in Drive Batch section)

### What these endpoints do
- `POST /api/anuncios/drive/iniciar-copies`: stores file list + config in `_lote_payloads`, returns `copies_token`
- `GET /api/anuncios/drive/gerar-copies/stream/<copies_token>`: SSE stream — for each file, downloads from Drive, saves to `/tmp`, calls Claude Vision, emits copy event

- [ ] **Step 1: Add iniciar-copies endpoint**

Add after `drive_campanhas` in app.py:

```python
@app.route("/api/anuncios/drive/iniciar-copies", methods=["POST"])
@login_required
def drive_iniciar_copies():
    """Armazena lista de arquivos em memória e retorna token para o stream de geração de copies."""
    d = request.get_json() or {}
    files = d.get("files") or []
    campanha_tipo = d.get("campanha_tipo", "MESSAGES")
    cliente_id    = d.get("cliente_id")

    if not files:
        return jsonify({"error": "Lista de arquivos vazia"}), 400
    if campanha_tipo not in ("MESSAGES", "PURCHASE", "ENGAGEMENT"):
        return jsonify({"error": "campanha_tipo inválido"}), 400

    # Buscar nome do cliente para usar no prompt (opcional, melhora copy)
    cliente_nome = ""
    if cliente_id:
        conn = None
        try:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("SELECT nome FROM ad_client_profiles WHERE id = %s", (cliente_id,))
            row = cur.fetchone()
            if row:
                cliente_nome = row["nome"]
        except Exception:
            pass
        finally:
            try: conn.close()
            except Exception: pass

    copies_token = str(uuid.uuid4())
    _lote_payloads[copies_token] = {
        "files":          files,
        "campanha_tipo":  campanha_tipo,
        "cliente_nome":   cliente_nome,
    }
    def _cleanup():
        _lote_payloads.pop(copies_token, None)
    threading.Timer(1800, _cleanup).start()

    return jsonify({"copies_token": copies_token})
```

- [ ] **Step 2: Add gerar-copies/stream endpoint**

Add immediately after `drive_iniciar_copies`:

```python
_COPY_PROMPTS = {
    "MESSAGES": (
        "Você é especialista em copywriting para anúncios de WhatsApp. "
        "Analise a imagem e crie uma copy persuasiva focada em gerar mensagens no WhatsApp. "
        "Retorne APENAS JSON válido, sem markdown: "
        '{"titulo": "string máx 40 chars", "texto": "string máx 125 chars"}'
    ),
    "PURCHASE": (
        "Você é especialista em copywriting de conversão. "
        "Analise a imagem e crie uma copy focada em venda direta com urgência. "
        "Retorne APENAS JSON válido, sem markdown: "
        '{"titulo": "string máx 40 chars", "texto": "string máx 125 chars"}'
    ),
    "ENGAGEMENT": (
        "Você é especialista em copywriting de engajamento. "
        "Analise a imagem e crie uma copy instigante que gere curtidas e comentários. "
        "Retorne APENAS JSON válido, sem markdown: "
        '{"titulo": "string máx 40 chars", "texto": "string máx 125 chars"}'
    ),
}


@app.route("/api/anuncios/drive/gerar-copies/stream/<copies_token>")
@login_required
def drive_gerar_copies_stream(copies_token):
    """SSE: para cada arquivo do Drive, baixa, gera copy com Claude Vision, emite evento."""
    payload = _lote_payloads.pop(copies_token, None)

    def _sse(data: dict) -> str:
        return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

    def _gerar():
        if not payload:
            yield _sse({"event": "erro", "index": 0, "msg": "Token inválido ou expirado"})
            return

        files         = payload["files"]
        camp_tipo     = payload["campanha_tipo"]
        cliente_nome  = payload.get("cliente_nome", "")
        total         = len(files)
        system_prompt = _COPY_PROMPTS.get(camp_tipo, _COPY_PROMPTS["MESSAGES"])
        if cliente_nome:
            system_prompt += f"\n\nCliente: {cliente_nome}"

        api_key = os.getenv("GOOGLE_API_KEY", "")
        client  = _anthropic_client()

        for idx, f in enumerate(files):
            file_id   = f["id"]
            file_name = f["name"]
            mime_type = f.get("mimeType", "image/jpeg")
            ext       = _DRIVE_MIME_EXT.get(mime_type, ".jpg")

            # 1. Baixar imagem do Drive
            try:
                dl_resp = requests.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}",
                    params={"alt": "media", "key": api_key},
                    timeout=30,
                )
                dl_resp.raise_for_status()
                file_bytes = dl_resp.content
            except Exception as e:
                yield _sse({"event": "erro", "index": idx, "file_id": file_id, "msg": f"Download falhou: {e}"})
                continue

            # 2. Salvar em /tmp com TTL de 30 min
            tmp_uuid_val = str(uuid.uuid4())
            tmp_path     = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{ext}")
            try:
                with open(tmp_path, "wb") as fp:
                    fp.write(file_bytes)
            except Exception as e:
                yield _sse({"event": "erro", "index": idx, "file_id": file_id, "msg": f"Erro ao salvar tmp: {e}"})
                continue

            def _cleanup_tmp(path=tmp_path):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
            threading.Timer(1800, _cleanup_tmp).start()

            # 3. Gerar copy com Claude Vision
            if not client:
                yield _sse({"event": "erro", "index": idx, "file_id": file_id, "msg": "ANTHROPIC_API_KEY não configurada"})
                continue
            try:
                b64 = base64.b64encode(file_bytes).decode("utf-8")
                msg = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=300,
                    system=system_prompt,
                    messages=[{"role": "user", "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}},
                        {"type": "text", "text": "Gere a copy para este criativo."},
                    ]}]
                )
                raw = msg.content[0].text.strip()
                if "```" in raw:
                    raw = raw.split("```")[1]
                    if raw.startswith("json\n"):
                        raw = raw[5:]
                resultado = json.loads(raw)
                titulo = resultado.get("titulo", "")
                texto  = resultado.get("texto", "")
            except Exception as e:
                yield _sse({"event": "erro", "index": idx, "file_id": file_id,
                            "tmp_uuid": tmp_uuid_val, "ext": ext, "msg": f"Erro IA: {e}"})
                continue

            yield _sse({
                "event":    "copy",
                "index":    idx,
                "file_id":  file_id,
                "file_name": file_name,
                "tmp_uuid": tmp_uuid_val,
                "ext":      ext,
                "titulo":   titulo,
                "texto":    texto,
            })

        yield _sse({"event": "concluido", "total": total})

    return app.response_class(
        _gerar(),
        mimetype="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
```

- [ ] **Step 3: Restart and test manually**

```bash
pkill -f "python app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && source .venv/bin/activate && nohup python app.py > /tmp/jakeos.log 2>&1 &
sleep 3 && tail -5 /tmp/jakeos.log
```
Expected: Flask running on port 5050, no import errors.

Test iniciar-copies returns a token:
```bash
curl -s -b cookies.txt -X POST http://localhost:5050/api/anuncios/drive/iniciar-copies \
  -H "Content-Type: application/json" \
  -d '{"files":[{"id":"fake","name":"test.jpg","mimeType":"image/jpeg"}],"campanha_tipo":"MESSAGES"}' | python3 -m json.tool
```
Expected: `{"copies_token": "<uuid>"}` (even though the file id is fake, the endpoint just stores and returns a token)

- [ ] **Step 4: Commit**

```bash
cd /root/jake_desktop
git add app.py
git commit -m "feat(drive-batch): iniciar-copies e gerar-copies/stream com Claude Vision"
```

---

## Task 3: Backend — preparar + drive/stream endpoints

**Files:**
- Modify: `/root/jake_desktop/app.py` (add after gerar-copies/stream, still in Drive Batch section)

### What these endpoints do
- `POST /api/anuncios/drive/preparar`: validates full publish payload, checks tmp files exist, stores in `_lote_payloads`
- `GET /api/anuncios/drive/stream/<token>`: SSE stream — for each client, creates campaign+adsets+ads on Meta

- [ ] **Step 1: Add preparar endpoint**

Add after `drive_gerar_copies_stream`:

```python
@app.route("/api/anuncios/drive/preparar", methods=["POST"])
@login_required
def drive_preparar():
    """Valida payload completo, verifica arquivos tmp, armazena em memória, retorna token."""
    d             = request.get_json() or {}
    cliente_ids   = d.get("cliente_ids") or []
    mode          = d.get("mode", "single")
    campanha_cfg  = d.get("campanha") or {}
    conjuntos_cfg = d.get("conjuntos") or {}
    camp_tipo     = d.get("campanha_tipo", "MESSAGES")
    copies        = d.get("copies") or []

    # Validação básica
    if not cliente_ids:
        return jsonify({"error": "Selecione ao menos um cliente"}), 400
    if not copies:
        return jsonify({"error": "Lista de copies vazia"}), 400

    try:
        num_conj   = int(conjuntos_cfg.get("num", 0))
        criat_por  = int(conjuntos_cfg.get("criativos_por", 0))
        orcamento  = float(conjuntos_cfg.get("orcamento", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Configuração de conjuntos inválida"}), 400

    if num_conj < 1 or criat_por < 1:
        return jsonify({"error": "Número de conjuntos e criativos por conjunto devem ser >= 1"}), 400
    if num_conj * criat_por != len(copies):
        return jsonify({
            "error": f"{num_conj} conjuntos × {criat_por} criativos = {num_conj * criat_por}, mas há {len(copies)} copies"
        }), 400

    # Buscar clientes no banco
    conn = None
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, agencia, account_id, token_key, page_id, link_url, "
            "campanha_tipo, optimization_goal, pixel_id, localizacao_json, publico_json, "
            "campanha_id_existente "
            "FROM ad_client_profiles WHERE id = ANY(%s)",
            (cliente_ids,)
        )
        clientes = [dict(c) for c in cur.fetchall()]
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar clientes: {e}"}), 500
    finally:
        try: conn.close()
        except Exception: pass

    if len(clientes) != len(cliente_ids):
        return jsonify({"error": "Um ou mais clientes não encontrados"}), 404

    # Validar campanha salva para modo multi com tipo=salva
    if mode == "multi" and campanha_cfg.get("tipo") == "salva":
        sem_campanha = [c["nome"] for c in clientes if not c.get("campanha_id_existente")]
        if sem_campanha:
            return jsonify({"error": f"Clientes sem campanha salva: {', '.join(sem_campanha)}"}), 400

    # Validar campos obrigatórios por cliente
    erros = []
    for c in clientes:
        if not c.get("account_id"):
            erros.append(f"{c['nome']}: account_id não configurado")
        if not c.get("page_id"):
            erros.append(f"{c['nome']}: page_id não configurado")
        if c.get("token_key") not in _VALID_TOKEN_KEYS:
            erros.append(f"{c['nome']}: token_key inválido")
        loc = c.get("localizacao_json") or {}
        if not (loc.get("paises") or loc.get("cidades")):
            erros.append(f"{c['nome']}: localização não configurada")
    if erros:
        return jsonify({"error": "Clientes com configuração incompleta", "detalhes": erros}), 400

    # Verificar arquivos tmp no disco
    for cp in copies:
        tmp_uuid_val = cp.get("tmp_uuid", "")
        ext          = cp.get("ext", ".jpg")
        tmp_path     = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{ext}")
        if not os.path.exists(tmp_path):
            return jsonify({"error": "Arquivos expirados — regere as copies antes de publicar", "expired": True}), 400

    # Armazenar payload
    db_token = str(uuid.uuid4())
    _lote_payloads[db_token] = {
        "clientes":     clientes,
        "mode":         mode,
        "campanha_cfg": campanha_cfg,
        "conjuntos":    {"num": num_conj, "orcamento": orcamento, "criativos_por": criat_por},
        "camp_tipo":    camp_tipo,
        "copies":       copies,
    }
    def _cleanup_token():
        _lote_payloads.pop(db_token, None)
    threading.Timer(1800, _cleanup_token).start()

    return jsonify({
        "token": db_token,
        "resumo": {
            "clientes":   len(clientes),
            "conjuntos":  num_conj,
            "total_ads":  len(clientes) * num_conj * criat_por,
        }
    })
```

- [ ] **Step 2: Add drive/stream endpoint**

Add immediately after `drive_preparar`:

```python
@app.route("/api/anuncios/drive/stream/<db_token>")
@login_required
def drive_stream(db_token):
    """SSE: para cada cliente, cria campanha+conjuntos+anúncios no Meta Ads."""
    payload = _lote_payloads.pop(db_token, None)

    def _sse(data: dict) -> str:
        return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

    _CAMP_CTA = {"MESSAGES": "SEND_MESSAGE", "PURCHASE": "SHOP_NOW", "ENGAGEMENT": "LEARN_MORE"}

    def _gerar():
        if not payload:
            yield _sse({"status": "erro", "msg": "Token inválido ou expirado"})
            return

        clientes     = payload["clientes"]
        campanha_cfg = payload["campanha_cfg"]
        conjuntos    = payload["conjuntos"]
        camp_tipo    = payload["camp_tipo"]
        copies       = payload["copies"]
        num_conj     = conjuntos["num"]
        criat_por    = conjuntos["criativos_por"]
        orcamento    = conjuntos["orcamento"]
        camp_nome    = campanha_cfg.get("nome", "Campanha Drive Batch")
        cta          = _CAMP_CTA.get(camp_tipo, "SEND_MESSAGE")
        cbo          = (camp_tipo == "MESSAGES")

        all_tmp_paths = set()

        for idx_c, cliente in enumerate(clientes):
            nome         = cliente["nome"]
            account_id   = cliente["account_id"]
            token_key    = cliente["token_key"]
            token_val    = os.getenv(token_key, "")
            page_id      = cliente.get("page_id", "")
            localizacao  = cliente.get("localizacao_json") or {}
            publico      = cliente.get("publico_json") or {}
            opt_goal     = cliente.get("optimization_goal") or None
            pixel_id     = cliente.get("pixel_id") or None
            link_url     = cliente.get("link_url") or ""

            if not token_val:
                yield _sse({"status": "erro", "msg": f"{nome}: token não encontrado", "cliente": nome})
                continue

            yield _sse({"status": "publicando", "msg": f"Iniciando {nome}...", "cliente": nome})

            # Resolver campaign_id
            newly_created_campaign = False
            campaign_id = None
            try:
                tipo_camp = campanha_cfg.get("tipo", "nova")
                if tipo_camp == "existente":
                    campaign_id = campanha_cfg["id"]
                elif tipo_camp == "salva":
                    campaign_id = cliente.get("campanha_id_existente")
                    if not campaign_id:
                        yield _sse({"status": "erro", "msg": f"{nome}: campanha_id_existente não definida", "cliente": nome})
                        continue
                else:  # nova
                    # Para MESSAGES (CBO): budget total = num_conj × orcamento
                    camp_budget = (num_conj * orcamento) if cbo else orcamento
                    campaign_id = _meta_api.criar_campanha(
                        token_val, account_id, camp_tipo, camp_nome, camp_budget, cbo=cbo
                    )
                    newly_created_campaign = True
            except Exception as e:
                yield _sse({"status": "erro", "msg": f"{nome}: erro ao criar campanha: {e}", "cliente": nome})
                continue

            # Criar conjuntos e anúncios
            created_adset_ids = []
            client_error = False

            for i in range(num_conj):
                slice_start = i * criat_por
                adset_copies = copies[slice_start: slice_start + criat_por]

                yield _sse({
                    "status": "publicando",
                    "msg":    f"{nome} — Conjunto {i+1}/{num_conj}",
                    "cliente": nome,
                })

                try:
                    adset_orcamento = orcamento if not cbo else None
                    adset_id = _meta_api.criar_conjunto(
                        token_val, account_id, campaign_id, camp_tipo,
                        publico, localizacao,
                        orcamento=adset_orcamento,
                        optimization_goal=opt_goal,
                        pixel_id=pixel_id,
                        nome=f"Conjunto {i+1} — {camp_nome}",
                    )
                    created_adset_ids.append(adset_id)
                except Exception as e:
                    # Rollback adsets já criados
                    for aid in created_adset_ids:
                        try: _meta_api.deletar_objeto_meta(token_val, aid)
                        except Exception: pass
                    if newly_created_campaign:
                        try: _meta_api.deletar_objeto_meta(token_val, campaign_id)
                        except Exception: pass
                    yield _sse({"status": "erro", "msg": f"{nome} — Conjunto {i+1} falhou: {e}", "cliente": nome})
                    client_error = True
                    break

                # Criar anúncios dentro do conjunto
                for cp in adset_copies:
                    tmp_uuid_val = cp.get("tmp_uuid", "")
                    ext          = cp.get("ext", ".jpg")
                    titulo       = cp.get("titulo", "")
                    texto        = cp.get("texto", "")
                    tmp_path     = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{ext}")
                    all_tmp_paths.add(tmp_path)

                    try:
                        with open(tmp_path, "rb") as fp:
                            file_bytes = fp.read()
                        filename = f"drive_batch_{tmp_uuid_val}{ext}"

                        upload_result = _meta_api.upload_imagem(token_val, account_id, file_bytes, filename)
                        creative_ref  = {"tipo": "imagem", "hash": upload_result["hash"]}

                        ad_id = _meta_api.criar_anuncio(
                            token_val, account_id, adset_id, page_id,
                            creative_ref, titulo, texto, cta, link_url=link_url,
                        )

                        # Log
                        try:
                            conn = _get_db(); cur = conn.cursor()
                            cur.execute("""
                                INSERT INTO ad_publish_log
                                    (cliente_id, account_id, campaign_id, adset_id, ad_id,
                                     status, audience_id, payload_json)
                                VALUES (%s,%s,%s,%s,%s,'sucesso',NULL,%s)
                            """, (cliente["id"], account_id, campaign_id, adset_id, ad_id,
                                  json.dumps({"titulo": titulo, "texto": texto})))
                            conn.commit()
                        except Exception:
                            pass
                        finally:
                            try: conn.close()
                            except Exception: pass

                        yield _sse({"status": "ok", "msg": f"Ad criado: {titulo[:30]}", "cliente": nome})

                    except Exception as e:
                        try:
                            conn = _get_db(); cur = conn.cursor()
                            cur.execute("""
                                INSERT INTO ad_publish_log
                                    (cliente_id, account_id, campaign_id, adset_id, ad_id,
                                     status, audience_id, erro_msg, payload_json)
                                VALUES (%s,%s,%s,%s,NULL,'erro',NULL,%s,%s)
                            """, (cliente["id"], account_id, campaign_id, adset_id, str(e),
                                  json.dumps({"titulo": titulo, "texto": texto})))
                            conn.commit()
                        except Exception:
                            pass
                        finally:
                            try: conn.close()
                            except Exception: pass
                        yield _sse({"status": "erro", "msg": f"Ad '{titulo[:20]}' falhou: {e}", "cliente": nome})

            if not client_error:
                yield _sse({"status": "ok", "msg": f"{nome} concluído ✓", "cliente": nome})

        # Limpar todos os arquivos tmp
        for tmp_path in all_tmp_paths:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

        yield _sse({"status": "concluido"})

    return app.response_class(
        _gerar(),
        mimetype="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
```

- [ ] **Step 3: Restart and smoke test**

```bash
pkill -f "python app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && source .venv/bin/activate && nohup python app.py > /tmp/jakeos.log 2>&1 &
sleep 3 && tail -5 /tmp/jakeos.log
```
Expected: no import errors, Flask running.

Test preparar returns 400 for missing data:
```bash
curl -s -b cookies.txt -X POST http://localhost:5050/api/anuncios/drive/preparar \
  -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
```
Expected: `{"error": "Selecione ao menos um cliente"}`

- [ ] **Step 4: Commit**

```bash
cd /root/jake_desktop
git add app.py
git commit -m "feat(drive-batch): preparar e drive/stream com publicação Meta Ads"
```

---

## Task 4: HTML — Tab button + 4-step wizard

**Files:**
- Modify: `/root/jake_desktop/templates/dashboard.html`

### What to add
A new tab button "Drive 📂" and a `<div id="anu-tab-drive">` with the 4-step wizard.

- [ ] **Step 1: Add tab button**

Find line with:
```html
<button class="anu-btn-secondary anu-tab-btn" data-tab="multi" onclick="anuSwitchTab('multi')" style="font-size:13px">Multi-Cliente</button>
```
Add AFTER it:
```html
              <button class="anu-btn-secondary anu-tab-btn" data-tab="drive" onclick="anuSwitchTab('drive')" style="font-size:13px">Drive 📂</button>
```

- [ ] **Step 2: Add wizard HTML div**

Find `</div><!-- /anu-tab-multi -->` and add AFTER it:

```html
            <div id="anu-tab-drive" style="display:none">

              <!-- Stepper header -->
              <div class="mc-stepper">
                <div class="db-step active" data-step="1"><span class="mc-step-num">1</span> Drive</div>
                <div class="db-step" data-step="2"><span class="mc-step-num">2</span> Conjuntos</div>
                <div class="db-step" data-step="3"><span class="mc-step-num">3</span> Copies</div>
                <div class="db-step" data-step="4"><span class="mc-step-num">4</span> Publicar</div>
              </div>

              <!-- Passo 1: Drive + Cliente -->
              <div id="db-passo-1">
                <div style="display:flex;flex-direction:column;gap:12px;max-width:520px;">
                  <label class="anu-label">Link da pasta do Google Drive
                    <div style="display:flex;gap:8px;margin-top:4px;">
                      <input type="text" id="db-drive-url" class="anu-input" placeholder="https://drive.google.com/drive/folders/..." style="flex:1">
                      <button class="anu-btn-secondary" onclick="dbCarregarDrive()" id="db-btn-carregar" style="white-space:nowrap">Carregar</button>
                    </div>
                    <div id="db-drive-status" style="font-size:11px;color:rgba(176,190,197,.4);margin-top:4px;"></div>
                  </label>

                  <div id="db-drive-preview" style="display:none">
                    <div style="font-size:12px;color:rgba(176,190,197,.5);margin-bottom:6px" id="db-drive-count"></div>
                    <div id="db-drive-thumbs" style="display:flex;flex-wrap:wrap;gap:6px;max-height:160px;overflow-y:auto;margin-bottom:12px;"></div>
                  </div>

                  <div id="db-cliente-section" style="display:none">
                    <label class="anu-label">Modo
                      <div style="display:flex;gap:12px;margin-top:4px;">
                        <label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;">
                          <input type="radio" name="db-mode" value="single" checked onchange="dbModoChange()"> Um cliente
                        </label>
                        <label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;">
                          <input type="radio" name="db-mode" value="multi" onchange="dbModoChange()"> Vários clientes
                        </label>
                      </div>
                    </label>

                    <div id="db-single-cliente" style="margin-top:8px;">
                      <label class="anu-label">Cliente
                        <select id="db-cliente-select" class="anu-input" style="margin-top:4px;"></select>
                      </label>
                    </div>

                    <div id="db-multi-clientes" style="display:none;margin-top:8px;">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <span style="font-size:13px;font-weight:600">Selecione os clientes</span>
                        <div style="display:flex;gap:6px;">
                          <button class="anu-btn-secondary" style="font-size:11px" onclick="dbSelecionarAgencia('dentto')">Dentto</button>
                          <button class="anu-btn-secondary" style="font-size:11px" onclick="dbSelecionarAgencia('piloti')">Piloti</button>
                          <button class="anu-btn-secondary" style="font-size:11px" onclick="dbLimparClientes()">Limpar</button>
                        </div>
                      </div>
                      <div id="db-lista-clientes" style="display:flex;flex-direction:column;gap:6px;max-height:300px;overflow-y:auto;"></div>
                    </div>
                  </div>
                </div>
                <button class="anu-btn-primary" style="margin-top:16px" onclick="dbIrPasso(2)" id="db-btn-passo2" disabled>Próximo →</button>
              </div>

              <!-- Passo 2: Campanha + Conjuntos -->
              <div id="db-passo-2" style="display:none">
                <div style="display:flex;flex-direction:column;gap:12px;max-width:520px;">

                  <label class="anu-label">Tipo de campanha
                    <select id="db-camp-tipo" class="anu-input" style="margin-top:4px;" onchange="dbCampTipoChange()">
                      <option value="MESSAGES">Mensagens (WhatsApp)</option>
                      <option value="PURCHASE">Compra / Conversão</option>
                      <option value="ENGAGEMENT">Engajamento</option>
                    </select>
                  </label>

                  <div id="db-campanha-section">
                    <label class="anu-label">Campanha
                      <div style="display:flex;gap:12px;margin-top:4px;flex-wrap:wrap;">
                        <label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;">
                          <input type="radio" name="db-camp-tipo-sel" value="nova" checked onchange="dbCampSelChange()"> Nova campanha
                        </label>
                        <label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;" id="db-existente-opt">
                          <input type="radio" name="db-camp-tipo-sel" value="existente" onchange="dbCampSelChange()"> Campanha existente
                        </label>
                        <label id="db-salva-opt" style="display:none;align-items:center;gap:6px;font-size:13px;cursor:pointer;">
                          <input type="radio" name="db-camp-tipo-sel" value="salva" onchange="dbCampSelChange()"> Usar campanha salva de cada cliente
                        </label>
                      </div>
                    </label>

                    <div id="db-camp-nova" style="margin-top:8px;">
                      <input type="text" id="db-camp-nome" class="anu-input" placeholder="Nome da campanha">
                    </div>

                    <div id="db-camp-existente" style="display:none;margin-top:8px;">
                      <button class="anu-btn-secondary" onclick="dbBuscarCampanhas()" style="font-size:12px">Buscar campanhas ativas</button>
                      <div id="db-campanhas-lista" style="margin-top:8px;display:flex;flex-direction:column;gap:4px;max-height:200px;overflow-y:auto;"></div>
                    </div>
                  </div>

                  <div style="display:flex;gap:12px;flex-wrap:wrap;">
                    <label class="anu-label" style="flex:1;min-width:120px;">Nº de conjuntos
                      <input type="number" id="db-num-conj" class="anu-input" placeholder="3" min="1" oninput="dbValidarConfig()" style="margin-top:4px;">
                    </label>
                    <label class="anu-label" style="flex:1;min-width:120px;">Criativos por conjunto
                      <input type="number" id="db-criat-por" class="anu-input" placeholder="10" min="1" oninput="dbValidarConfig()" style="margin-top:4px;">
                    </label>
                    <label class="anu-label" style="flex:1;min-width:120px;">Orçamento por conjunto (R$)
                      <input type="number" id="db-orcamento" class="anu-input" placeholder="10" min="1" step="0.01" style="margin-top:4px;">
                    </label>
                  </div>
                  <div id="db-config-status" style="font-size:12px;color:rgba(176,190,197,.4);"></div>
                </div>
                <div style="display:flex;gap:8px;margin-top:16px;">
                  <button class="anu-btn-secondary" onclick="dbIrPasso(1)">← Voltar</button>
                  <button class="anu-btn-primary" onclick="dbIrPasso(3)" id="db-btn-passo3" disabled>Próximo →</button>
                </div>
              </div>

              <!-- Passo 3: Gerar Copies -->
              <div id="db-passo-3" style="display:none">
                <div id="db-copies-idle">
                  <p style="font-size:13px;color:rgba(176,190,197,.5);margin-bottom:12px;">O Jake vai analisar cada imagem e gerar título + texto automaticamente. Você pode editar antes de publicar.</p>
                  <button class="anu-btn-primary" onclick="dbGerarCopies()" id="db-btn-gerar">Gerar Copies ✨</button>
                </div>
                <div id="db-copies-progresso" style="display:none;">
                  <div style="font-size:13px;font-weight:600;margin-bottom:8px" id="db-copies-counter">Gerando 0/0...</div>
                  <div style="width:100%;height:4px;background:rgba(176,190,197,.1);border-radius:2px;margin-bottom:16px;">
                    <div id="db-copies-bar" style="height:100%;background:#00b4d8;border-radius:2px;width:0%;transition:width .3s;"></div>
                  </div>
                </div>
                <div id="db-copies-grid" style="display:none;margin-top:12px;">
                  <div id="db-copies-rows" style="display:flex;flex-direction:column;gap:12px;max-height:500px;overflow-y:auto;margin-bottom:16px;"></div>
                  <div style="display:flex;gap:8px;">
                    <button class="anu-btn-secondary" onclick="dbIrPasso(2)">← Voltar</button>
                    <button class="anu-btn-primary" onclick="dbIrPasso(4)" id="db-btn-passo4">Revisar →</button>
                  </div>
                </div>
              </div>

              <!-- Passo 4: Revisar + Publicar -->
              <div id="db-passo-4" style="display:none">
                <div id="db-resumo" style="background:rgba(176,190,197,.05);border-radius:8px;padding:12px;margin-bottom:16px;font-size:13px;"></div>
                <div id="db-breakdown" style="font-size:12px;color:rgba(176,190,197,.5);margin-bottom:16px;"></div>
                <div id="db-pub-progresso" style="display:none;margin-bottom:16px;">
                  <div style="font-size:13px;font-weight:600;margin-bottom:8px">Publicando...</div>
                  <div id="db-pub-lista" style="display:flex;flex-direction:column;gap:4px;font-size:12px;max-height:300px;overflow-y:auto;"></div>
                </div>
                <div id="db-expired-msg" style="display:none;padding:12px;background:rgba(255,100,100,.1);border-radius:8px;margin-bottom:12px;font-size:13px;color:#ff6464;">
                  Arquivos expiraram (30 min). <button class="anu-btn-secondary" style="font-size:11px;margin-left:8px;" onclick="dbIrPasso(3);dbGerarCopies()">Regerar copies</button>
                </div>
                <div style="display:flex;gap:8px;">
                  <button class="anu-btn-secondary" onclick="dbIrPasso(3)" id="db-btn-voltar4">← Voltar</button>
                  <button class="anu-btn-primary" onclick="dbPublicar()" id="db-btn-publicar">Publicar Tudo 🚀</button>
                </div>
              </div>

            </div><!-- /anu-tab-drive -->
```

- [ ] **Step 3: Add script tag for drive-batch.js**

Find the existing multi-cliente script tag (something like `<script src="{{ url_for('static', filename='js/multi-cliente.js') }}">`). Add AFTER it:
```html
    <script src="{{ url_for('static', filename='js/drive-batch.js') }}"></script>
```

- [ ] **Step 4: Verify HTML renders without JS errors**

Restart Jake OS and open http://localhost:5050/#anuncios in browser. Click the "Drive 📂" tab. You should see the wizard HTML (Step 1 content visible). No console errors about missing elements.

- [ ] **Step 5: Commit**

```bash
cd /root/jake_desktop
git add templates/dashboard.html
git commit -m "feat(drive-batch): HTML do wizard 4 passos e botão de aba"
```

---

## Task 5: JS — drive-batch.js

**Files:**
- Create: `/root/jake_desktop/static/js/drive-batch.js`

### What this file does
IIFE exporting `window.driveBatchInit`. Manages wizard state (4 steps), fetches client list, handles Drive folder loading, handles SSE copy generation stream, editable copy grid, and SSE publish stream.

- [ ] **Step 1: Create drive-batch.js**

```javascript
/* drive-batch.js — Drive Batch Ads wizard */
(function () {
  'use strict';

  // ── State ────────────────────────────────────────────────────────────────
  var _clientes    = [];   // all ad_client_profiles
  var _selecionados = [];  // selected client ids (multi mode)
  var _driveFiles  = [];   // [{id, name, thumbnailLink, ext, mimeType}]
  var _copies      = [];   // [{file_id, file_name, tmp_uuid, ext, titulo, texto}] (one per image)
  var _campanha    = {};   // {tipo, id, nome}
  var _conjuntos   = {};   // {num, orcamento, criativos_por}
  var _campTipo    = 'MESSAGES';
  var _pubToken    = null;
  var _copiesLoaded = false;

  // ── Init ─────────────────────────────────────────────────────────────────
  window.driveBatchInit = function () {
    if (!_clientes.length) _carregarClientes();
    _irPasso(1);
    _atualizarSalvaOpt();
  };

  function _carregarClientes() {
    fetch('/api/anuncios/clientes')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _clientes = data.clientes || [];
        _renderizarClienteSelect();
        _renderizarListaClientes();
      });
  }

  function _renderizarClienteSelect() {
    var sel = document.getElementById('db-cliente-select');
    if (!sel) return;
    sel.innerHTML = _clientes.map(function (c) {
      return '<option value="' + c.id + '">' + c.nome + ' (' + c.agencia + ')</option>';
    }).join('');
  }

  function _renderizarListaClientes() {
    var el = document.getElementById('db-lista-clientes');
    if (!el) return;
    el.innerHTML = _clientes.map(function (c) {
      return '<label style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:rgba(176,190,197,.05);border-radius:6px;cursor:pointer;font-size:13px;">' +
        '<input type="checkbox" value="' + c.id + '" onchange="dbToggleCliente(' + c.id + ')" style="accent-color:#00b4d8">' +
        '<span>' + c.nome + '</span>' +
        '<span style="font-size:11px;color:rgba(176,190,197,.4)">(' + c.agencia + ')</span>' +
        '</label>';
    }).join('');
  }

  // ── Step navigation ───────────────────────────────────────────────────────
  function _irPasso(n) {
    [1, 2, 3, 4].forEach(function (i) {
      var p = document.getElementById('db-passo-' + i);
      if (p) p.style.display = (i === n) ? '' : 'none';
      var s = document.querySelector('.db-step[data-step="' + i + '"]');
      if (s) s.classList.toggle('active', i === n);
    });
    if (n === 4) _renderizarResumo();
  }
  window.dbIrPasso = _irPasso;

  // ── Passo 1: Drive loading ────────────────────────────────────────────────
  window.dbCarregarDrive = function () {
    var url = (document.getElementById('db-drive-url').value || '').trim();
    if (!url) return;
    var btn    = document.getElementById('db-btn-carregar');
    var status = document.getElementById('db-drive-status');
    btn.disabled = true;
    status.textContent = 'Carregando...';

    fetch('/api/anuncios/drive/listar', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: url}),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        btn.disabled = false;
        if (data.error) { status.textContent = '✗ ' + data.error; return; }
        _driveFiles = data.files || [];
        _copies = [];
        _copiesLoaded = false;
        status.textContent = '✓ ' + _driveFiles.length + ' imagens encontradas';
        _renderizarThumbs();
        document.getElementById('db-drive-preview').style.display = '';
        document.getElementById('db-cliente-section').style.display = '';
        document.getElementById('db-btn-passo2').disabled = false;
      })
      .catch(function (e) {
        btn.disabled = false;
        status.textContent = '✗ Erro: ' + e.message;
      });
  };

  function _renderizarThumbs() {
    var el = document.getElementById('db-drive-thumbs');
    var count = document.getElementById('db-drive-count');
    if (!el) return;
    count.textContent = _driveFiles.length + ' imagens';
    el.innerHTML = _driveFiles.slice(0, 30).map(function (f) {
      var src = f.thumbnailLink || '';
      return src
        ? '<img src="' + src + '" style="width:48px;height:48px;object-fit:cover;border-radius:4px;" title="' + f.name + '">'
        : '<div style="width:48px;height:48px;background:rgba(176,190,197,.1);border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:10px;color:rgba(176,190,197,.4)">IMG</div>';
    }).join('');
    if (_driveFiles.length > 30) {
      el.innerHTML += '<div style="font-size:11px;color:rgba(176,190,197,.3);align-self:center">+' + (_driveFiles.length - 30) + ' mais</div>';
    }
  }

  window.dbModoChange = function () {
    var modo = document.querySelector('input[name="db-mode"]:checked');
    if (!modo) return;
    document.getElementById('db-single-cliente').style.display = modo.value === 'single' ? '' : 'none';
    document.getElementById('db-multi-clientes').style.display = modo.value === 'multi' ? '' : 'none';
    _atualizarSalvaOpt();
  };

  function _atualizarSalvaOpt() {
    var modo = document.querySelector('input[name="db-mode"]:checked');
    var salvaOpt = document.getElementById('db-salva-opt');
    if (salvaOpt) salvaOpt.style.display = (modo && modo.value === 'multi') ? 'flex' : 'none';
  }

  window.dbToggleCliente = function (id) {
    var idx = _selecionados.indexOf(id);
    if (idx >= 0) _selecionados.splice(idx, 1);
    else _selecionados.push(id);
  };

  window.dbSelecionarAgencia = function (agencia) {
    _selecionados = _clientes.filter(function (c) {
      return c.agencia === agencia;
    }).map(function (c) { return c.id; });
    var checkboxes = document.querySelectorAll('#db-lista-clientes input[type="checkbox"]');
    checkboxes.forEach(function (cb) {
      cb.checked = _selecionados.indexOf(parseInt(cb.value)) >= 0;
    });
  };

  window.dbLimparClientes = function () {
    _selecionados = [];
    var checkboxes = document.querySelectorAll('#db-lista-clientes input[type="checkbox"]');
    checkboxes.forEach(function (cb) { cb.checked = false; });
  };

  // ── Passo 2: Configuração ─────────────────────────────────────────────────
  window.dbCampTipoChange = function () {
    _campTipo = document.getElementById('db-camp-tipo').value || 'MESSAGES';
    dbValidarConfig();
  };

  window.dbCampSelChange = function () {
    var tipo = document.querySelector('input[name="db-camp-tipo-sel"]:checked');
    if (!tipo) return;
    document.getElementById('db-camp-nova').style.display     = tipo.value === 'nova' ? '' : 'none';
    document.getElementById('db-camp-existente').style.display = tipo.value === 'existente' ? '' : 'none';
  };

  window.dbBuscarCampanhas = function () {
    var modo = document.querySelector('input[name="db-mode"]:checked');
    var clienteId;
    if (modo && modo.value === 'single') {
      clienteId = document.getElementById('db-cliente-select').value;
    } else {
      clienteId = _selecionados[0];
    }
    if (!clienteId) { alert('Selecione um cliente primeiro.'); return; }

    var lista = document.getElementById('db-campanhas-lista');
    lista.innerHTML = '<div style="font-size:12px;color:rgba(176,190,197,.4)">Buscando...</div>';

    fetch('/api/anuncios/drive/campanhas?cliente_id=' + clienteId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { lista.innerHTML = '<div style="color:#ff6464;font-size:12px">✗ ' + data.error + '</div>'; return; }
        var camps = data.campanhas || [];
        lista.innerHTML = camps.map(function (c) {
          return '<label style="display:flex;align-items:center;gap:8px;padding:6px 8px;background:rgba(176,190,197,.05);border-radius:4px;cursor:pointer;font-size:12px;">' +
            '<input type="radio" name="db-camp-sel" value="' + c.id + '">' +
            '<span>' + c.name + '</span>' +
            '<span style="font-size:10px;color:rgba(176,190,197,.3)">(' + c.status + ')</span>' +
            '</label>';
        }).join('') || '<div style="font-size:12px;color:rgba(176,190,197,.4)">Nenhuma campanha encontrada.</div>';
      });
  };

  window.dbValidarConfig = function () {
    var num   = parseInt(document.getElementById('db-num-conj').value) || 0;
    var criat = parseInt(document.getElementById('db-criat-por').value) || 0;
    var total = _driveFiles.length;
    var status = document.getElementById('db-config-status');
    var btn    = document.getElementById('db-btn-passo3');

    if (num > 0 && criat > 0) {
      var calc = num * criat;
      if (calc === total) {
        status.textContent = '✓ ' + num + ' conjuntos × ' + criat + ' criativos = ' + calc + ' imagens ✓';
        status.style.color = '#4caf50';
        if (btn) btn.disabled = false;
      } else {
        status.textContent = '✗ ' + num + ' × ' + criat + ' = ' + calc + ', mas a pasta tem ' + total + ' imagens';
        status.style.color = '#ff6464';
        if (btn) btn.disabled = true;
      }
    } else {
      status.textContent = '';
      if (btn) btn.disabled = true;
    }
  };

  // ── Passo 3: Gerar copies ─────────────────────────────────────────────────
  window.dbGerarCopies = function () {
    var modo = document.querySelector('input[name="db-mode"]:checked');
    var clienteId;
    if (modo && modo.value === 'single') {
      clienteId = document.getElementById('db-cliente-select').value;
    } else {
      clienteId = _selecionados[0];
    }

    document.getElementById('db-copies-idle').style.display = 'none';
    document.getElementById('db-copies-progresso').style.display = '';
    document.getElementById('db-copies-grid').style.display = 'none';
    _copies = [];
    _copiesLoaded = false;

    var total   = _driveFiles.length;
    var counter = document.getElementById('db-copies-counter');
    var bar     = document.getElementById('db-copies-bar');
    var done    = 0;

    // Fase 1: iniciar-copies (stores file list, returns token)
    fetch('/api/anuncios/drive/iniciar-copies', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        files: _driveFiles,
        campanha_tipo: _campTipo,
        cliente_id: clienteId,
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { alert('Erro: ' + data.error); _resetCopiesUI(); return; }

        // Fase 2: SSE stream
        var es = new EventSource('/api/anuncios/drive/gerar-copies/stream/' + data.copies_token);

        es.addEventListener('copy', function (e) {
          var d = JSON.parse(e.data);
          done++;
          counter.textContent = 'Gerando ' + done + '/' + total + '...';
          bar.style.width = Math.round((done / total) * 100) + '%';
          _copies.push({
            file_id:   d.file_id,
            file_name: d.file_name,
            tmp_uuid:  d.tmp_uuid,
            ext:       d.ext,
            titulo:    d.titulo,
            texto:     d.texto,
          });
          _renderizarCopyRow(d, _copies.length - 1);
        });

        es.addEventListener('erro', function (e) {
          var d = JSON.parse(e.data);
          done++;
          counter.textContent = 'Gerando ' + done + '/' + total + '...';
          bar.style.width = Math.round((done / total) * 100) + '%';
          // Add placeholder copy with error message
          _copies.push({
            file_id:   d.file_id,
            file_name: '',
            tmp_uuid:  d.tmp_uuid || '',
            ext:       d.ext || '.jpg',
            titulo:    '',
            texto:     '',
          });
          _renderizarCopyRowErro(d, _copies.length - 1);
        });

        es.addEventListener('concluido', function () {
          es.close();
          document.getElementById('db-copies-progresso').style.display = 'none';
          document.getElementById('db-copies-grid').style.display = '';
          _copiesLoaded = true;
        });

        es.onerror = function () {
          es.close();
          _resetCopiesUI();
          alert('Erro na geração de copies. Tente novamente.');
        };
      });
  };

  function _resetCopiesUI() {
    document.getElementById('db-copies-idle').style.display = '';
    document.getElementById('db-copies-progresso').style.display = 'none';
  }

  function _renderizarCopyRow(d, idx) {
    var grid = document.getElementById('db-copies-rows');
    if (!grid) return;
    grid.style.display = '';
    // Look up thumbnailLink from _driveFiles by file_id
    var driveFile = _driveFiles.filter(function (f) { return f.id === d.file_id; })[0];
    var thumb = (driveFile && driveFile.thumbnailLink)
      ? '<img src="' + driveFile.thumbnailLink + '" style="width:48px;height:48px;object-fit:cover;border-radius:4px;flex-shrink:0;">'
      : '<div style="width:48px;height:48px;background:rgba(176,190,197,.1);border-radius:4px;flex-shrink:0;"></div>';
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:10px;align-items:flex-start;padding:10px;background:rgba(176,190,197,.05);border-radius:6px;';
    row.innerHTML = thumb +
      '<div style="flex:1;display:flex;flex-direction:column;gap:6px;">' +
        '<div style="font-size:11px;color:rgba(176,190,197,.3)">' + (d.file_name || '') + '</div>' +
        '<input type="text" class="anu-input db-copy-titulo" data-idx="' + idx + '" ' +
               'value="' + _esc(d.titulo) + '" placeholder="Título" style="font-size:12px;" ' +
               'oninput="dbUpdateCopy(' + idx + ',\'titulo\',this.value)">' +
        '<textarea class="anu-input db-copy-texto" data-idx="' + idx + '" rows="2" ' +
                  'placeholder="Texto" style="font-size:12px;resize:vertical;" ' +
                  'oninput="dbUpdateCopy(' + idx + ',\'texto\',this.value)">' + _esc(d.texto) + '</textarea>' +
      '</div>';
    grid.appendChild(row);
  }

  function _renderizarCopyRowErro(d, idx) {
    var grid = document.getElementById('db-copies-rows');
    if (!grid) return;
    grid.style.display = '';
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:10px;align-items:flex-start;padding:10px;background:rgba(255,100,100,.05);border-radius:6px;border:1px solid rgba(255,100,100,.1);';
    row.innerHTML =
      '<div style="flex:1;display:flex;flex-direction:column;gap:6px;">' +
        '<div style="font-size:11px;color:#ff6464">✗ Erro: ' + (d.msg || '') + '. Preencha manualmente:</div>' +
        '<input type="text" class="anu-input db-copy-titulo" data-idx="' + idx + '" ' +
               'placeholder="Título" style="font-size:12px;" ' +
               'oninput="dbUpdateCopy(' + idx + ',\'titulo\',this.value)">' +
        '<textarea class="anu-input db-copy-texto" data-idx="' + idx + '" rows="2" ' +
                  'placeholder="Texto" style="font-size:12px;resize:vertical;" ' +
                  'oninput="dbUpdateCopy(' + idx + ',\'texto\',this.value)"></textarea>' +
      '</div>';
    grid.appendChild(row);
  }

  window.dbUpdateCopy = function (idx, field, value) {
    if (_copies[idx]) _copies[idx][field] = value;
  };

  // ── Passo 4: Resumo + Publicar ────────────────────────────────────────────
  function _renderizarResumo() {
    var modo     = document.querySelector('input[name="db-mode"]:checked');
    var modoVal  = modo ? modo.value : 'single';
    var numClientes = modoVal === 'single' ? 1 : _selecionados.length;
    var num      = parseInt(document.getElementById('db-num-conj').value) || 0;
    var criat    = parseInt(document.getElementById('db-criat-por').value) || 0;
    var orc      = parseFloat(document.getElementById('db-orcamento').value) || 0;
    var total    = numClientes * num * criat;

    var resumoEl = document.getElementById('db-resumo');
    if (resumoEl) {
      resumoEl.innerHTML =
        '<strong>' + numClientes + '</strong> cliente(s) × ' +
        '<strong>' + num + '</strong> conjuntos × ' +
        '<strong>' + criat + '</strong> criativos = ' +
        '<strong>' + total + '</strong> publicações' +
        '<br><small style="color:rgba(176,190,197,.4)">R$ ' + orc.toFixed(2) + ' por conjunto</small>';
    }

    var breakdownEl = document.getElementById('db-breakdown');
    if (breakdownEl) {
      var lines = [];
      for (var i = 0; i < num; i++) {
        var start = i * criat + 1;
        var end   = (i + 1) * criat;
        lines.push('Conjunto ' + (i + 1) + ': imagens ' + start + '–' + end);
      }
      breakdownEl.textContent = lines.join(' | ');
    }

    document.getElementById('db-expired-msg').style.display = 'none';
    document.getElementById('db-btn-publicar').disabled = false;
    document.getElementById('db-btn-voltar4').disabled = false;
  }

  window.dbPublicar = function () {
    var modo    = document.querySelector('input[name="db-mode"]:checked');
    var modoVal = modo ? modo.value : 'single';
    var clienteIds;
    if (modoVal === 'single') {
      clienteIds = [parseInt(document.getElementById('db-cliente-select').value)];
    } else {
      clienteIds = _selecionados.slice();
    }
    if (!clienteIds.length) { alert('Selecione ao menos um cliente.'); return; }

    var campTipoSel = document.querySelector('input[name="db-camp-tipo-sel"]:checked');
    var campSel     = campTipoSel ? campTipoSel.value : 'nova';
    var campNome    = document.getElementById('db-camp-nome').value || '';
    var campId      = '';
    if (campSel === 'existente') {
      var campRadio = document.querySelector('input[name="db-camp-sel"]:checked');
      campId = campRadio ? campRadio.value : '';
      if (!campId) { alert('Selecione uma campanha existente.'); return; }
    }

    var body = {
      cliente_ids:   clienteIds,
      mode:          modoVal,
      campanha:      {tipo: campSel, id: campId, nome: campNome},
      conjuntos: {
        num:           parseInt(document.getElementById('db-num-conj').value) || 0,
        orcamento:     parseFloat(document.getElementById('db-orcamento').value) || 0,
        criativos_por: parseInt(document.getElementById('db-criat-por').value) || 0,
      },
      campanha_tipo: _campTipo,
      copies:        _copies,
    };

    document.getElementById('db-btn-publicar').disabled = true;
    document.getElementById('db-btn-voltar4').disabled = true;
    document.getElementById('db-pub-progresso').style.display = '';
    document.getElementById('db-pub-lista').innerHTML = '';
    document.getElementById('db-expired-msg').style.display = 'none';

    fetch('/api/anuncios/drive/preparar', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.expired) {
          document.getElementById('db-expired-msg').style.display = '';
          document.getElementById('db-btn-publicar').disabled = false;
          document.getElementById('db-btn-voltar4').disabled = false;
          document.getElementById('db-pub-progresso').style.display = 'none';
          return;
        }
        if (data.error) {
          alert('Erro: ' + data.error + (data.detalhes ? '\n' + data.detalhes.join('\n') : ''));
          document.getElementById('db-btn-publicar').disabled = false;
          document.getElementById('db-btn-voltar4').disabled = false;
          document.getElementById('db-pub-progresso').style.display = 'none';
          return;
        }
        _pubToken = data.token;
        _iniciarStream(data.token);
      })
      .catch(function (e) {
        alert('Erro: ' + e.message);
        document.getElementById('db-btn-publicar').disabled = false;
        document.getElementById('db-btn-voltar4').disabled = false;
      });
  };

  function _iniciarStream(token) {
    var lista = document.getElementById('db-pub-lista');
    var es    = new EventSource('/api/anuncios/drive/stream/' + token);

    es.onmessage = function (e) {
      var d = JSON.parse(e.data);
      var color = d.status === 'ok' ? '#4caf50' : d.status === 'erro' ? '#ff6464' : 'rgba(176,190,197,.5)';
      var icon  = d.status === 'ok' ? '✓' : d.status === 'erro' ? '✗' : '⏳';
      var item  = document.createElement('div');
      item.style.color = color;
      item.textContent = icon + ' ' + (d.msg || '');
      lista.appendChild(item);
      lista.scrollTop = lista.scrollHeight;

      if (d.status === 'concluido') {
        es.close();
        _pubToken = null;
        document.getElementById('db-btn-voltar4').disabled = false;
      }
    };

    es.onerror = function () {
      es.close();
      var item = document.createElement('div');
      item.style.color = '#ff6464';
      item.textContent = '✗ Conexão interrompida.';
      lista.appendChild(item);
      document.getElementById('db-btn-publicar').disabled = false;
      document.getElementById('db-btn-voltar4').disabled = false;
    };
  }

  // ── Utils ─────────────────────────────────────────────────────────────────
  function _esc(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

}());
```

- [ ] **Step 2: Register tab in anuncios.js**

In `/root/jake_desktop/static/js/anuncios.js`, find:
```javascript
['publicar', 'publicos', 'lote', 'multi'].forEach(function(t) {
```
Change to:
```javascript
['publicar', 'publicos', 'lote', 'multi', 'drive'].forEach(function(t) {
```

Then find:
```javascript
if (tab === 'multi' && typeof mcInit === 'function') mcInit();
```
Add after it:
```javascript
    if (tab === 'drive' && typeof driveBatchInit === 'function') driveBatchInit();
```

- [ ] **Step 3: Verify JS works**

Open http://localhost:5050/#anuncios. Click "Drive 📂" tab. Step 1 should appear. Open browser console — no errors expected.

If Jake OS is not running:
```bash
pkill -f "python app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && source .venv/bin/activate && nohup python app.py > /tmp/jakeos.log 2>&1 &
sleep 3
```

- [ ] **Step 4: Commit**

```bash
cd /root/jake_desktop
git add static/js/drive-batch.js static/js/anuncios.js
git commit -m "feat(drive-batch): JS wizard completo — 4 passos com SSE"
```

---

## Task 6: CSS styles

**Files:**
- Modify: `/root/jake_desktop/static/css/anuncios.css`

- [ ] **Step 1: Add styles at end of file**

Append to `/root/jake_desktop/static/css/anuncios.css`:

```css
/* ── Drive Batch ──────────────────────────────────────────────── */
.db-step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(176, 190, 197, 0.3);
  padding: 4px 10px;
  border-radius: 20px;
}
.db-step.active {
  color: #00b4d8;
  background: rgba(0, 180, 216, 0.1);
}
.db-step.active .mc-step-num {
  background: #00b4d8;
  color: #0a0e1a;
}
```

- [ ] **Step 2: Verify tab renders correctly**

Open http://localhost:5050/#anuncios, click "Drive 📂". Stepper dots should highlight blue for the active step.

- [ ] **Step 3: Commit**

```bash
cd /root/jake_desktop
git add static/css/anuncios.css
git commit -m "feat(drive-batch): estilos do stepper e grid de copies"
```

---

## Task 7: Add GOOGLE_API_KEY to .env and final smoke test

**Files:**
- Modify: `/root/.env`

- [ ] **Step 1: Add GOOGLE_API_KEY to .env**

```bash
echo "" >> /root/.env
echo "GOOGLE_API_KEY=your_key_here" >> /root/.env
```
Replace `your_key_here` with the actual API key (get from Google Cloud Console → APIs & Services → Credentials → API key with Drive API enabled).

Note: the Drive API must be enabled in the GCP project for the key. If not yet enabled: https://console.cloud.google.com/apis/library/drive.googleapis.com

- [ ] **Step 2: Restart Jake OS**

```bash
pkill -f "python app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && source .venv/bin/activate && nohup python app.py > /tmp/jakeos.log 2>&1 &
sleep 3 && tail -5 /tmp/jakeos.log
```
Expected: Flask running, no errors.

- [ ] **Step 3: Full flow smoke test**

1. Open http://localhost:5050/#anuncios
2. Click "Drive 📂" tab
3. Paste a real public Google Drive folder URL with at least 2 images
4. Click "Carregar" → should show file count and thumbnails
5. Select a client, click "Próximo"
6. Set num_conjuntos=1, criativos_por=2 (if folder has 2 images), orcamento=10
7. Validation message should show "✓ 1 × 2 = 2 imagens ✓"
8. Click "Próximo", then "Gerar Copies"
9. Progress bar should advance; copies should appear in the grid
10. Edit a copy title or text manually
11. Click "Próximo", review summary, click "Publicar Tudo"
12. Progress list should show SSE events

- [ ] **Step 4: Commit**

```bash
cd /root/jake_desktop
git add -p  # stage only the .env changes if desired, or skip committing .env (it's in .gitignore)
git commit -m "feat(drive-batch): feature completa — Drive import, AI copies, publicação Meta Ads" --allow-empty
```
Note: `.env` should already be in `.gitignore` — do NOT commit it.

---

## Final commit summary

After all tasks:
```bash
git log --oneline -8
```
Expected commits (newest first):
- `feat(drive-batch): feature completa`
- `feat(drive-batch): estilos do stepper e grid de copies`
- `feat(drive-batch): JS wizard completo — 4 passos com SSE`
- `feat(drive-batch): HTML do wizard 4 passos e botão de aba`
- `feat(drive-batch): preparar e drive/stream com publicação Meta Ads`
- `feat(drive-batch): iniciar-copies e gerar-copies/stream com Claude Vision`
- `feat(drive-batch): endpoints listar e campanhas`
