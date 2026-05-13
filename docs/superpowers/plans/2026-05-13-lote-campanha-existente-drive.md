# Lote — Campanha Existente + Link do Drive + Fix Visual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar ao tab Lote: seletor de campanha existente, suporte a link do Google Drive como criativo, e fix visual dos `<select>`.

**Architecture:** Três melhorias independentes no tab Lote existente. O endpoint `/api/anuncios/campanhas/<account_id>` já existe e é reutilizado para listar campanhas — criar um endpoint separado seria duplicação (YAGNI). Um novo endpoint `POST /api/anuncios/lote/drive-download` faz request direto ao Drive, verifica Content-Type para detectar arquivos não públicos, e faz upload para a Meta retornando `creative_ref` pronto. O backend de publicação (`publicar-lote/stream`) recebe `campaign_id_existente` opcional que, quando presente, pula `criar_campanha()` após validar ownership.

**Tech Stack:** Python/Flask, JavaScript ES5 IIFE, Meta Ads API v21.0, psycopg2.

---

## Decisões arquiteturais (desvios intencionais da spec)

1. **Endpoint de campanhas**: A spec propunha criar `GET /api/anuncios/lote/campanhas`. Em vez disso, **reutilizamos o endpoint existente** `/api/anuncios/campanhas/<account_id>?token_key=...` (app.py:3284) — ele tem a mesma funcionalidade e retorna `{id, name, objective}` (exibimos `objective` no dropdown, equivalente a `status` para fins de display).

2. **ID do select de campanha**: A spec usava `lote-camp-existente`. O plano usa `lote-camp-select` — mais curto e consistente com o padrão de IDs do lote. Todos os usos (HTML e JS) estão alinhados com `lote-camp-select`.

3. **Preview de imagem pós-Drive**: A spec mencionava `URL.createObjectURL` de blob. Como o backend baixa o arquivo e faz upload para a Meta (o frontend nunca recebe o blob), usamos a URL do Drive diretamente como `img.src` — funcional para arquivos públicos.

---

## Arquivos

| Arquivo | Mudança |
|---|---|
| `jake_desktop/static/css/anuncios.css` | Fix visual `<select>` |
| `jake_desktop/templates/dashboard.html` | HTML dos dois toggles no tab Lote (linhas 693-710) |
| `jake_desktop/app.py` | (1) Novo endpoint `POST /api/anuncios/lote/drive-download` após linha 3297; (2) Modificar `anuncios_publicar_lote_stream` para aceitar `campaign_id_existente` (linhas 4880-4887) |
| `jake_desktop/static/js/lote.js` | Toggle campanha, fetch campanhas, toggle drive, localStorage |

---

## Contexto para implementadores

- **`/api/anuncios/campanhas/<account_id>?token_key=...`** — endpoint já existe (app.py:3284). Retorna `{"campanhas": [{id, name, objective}]}`.
- **`_VALID_TOKEN_KEYS`** — set já definido em app.py (ex: `{"META_TOKEN_PILOTI", "META_TOKEN_DENTTO", ...}`).
- **`_TMP_DIR`** — diretório `/tmp` já definido em app.py.
- **`uuid`** — já importado em app.py.
- **`requests`** — já importado em app.py.
- **Lote tab HTML** está em `dashboard.html` linhas 693-770
- **`_salvarLocal()` / `_restaurarLocal()`** em lote.js (linhas 27-73) — persiste `jakeos_lote_v1` no localStorage
- **Padrão de toggle campanha** já implementado em `anuncios.js` — replicar mesmo padrão

---

## Task 1: Fix visual dos `<select>`

**Files:**
- Modify: `jake_desktop/static/css/anuncios.css`

- [ ] **Step 1: Localizar onde adicionar**

```bash
grep -n "anu-select\|\.lote-topo" jake_desktop/static/css/anuncios.css | tail -10
```

- [ ] **Step 2: Adicionar ao final do arquivo**

```css
/* ── Fix visual: select dark theme ─────────────────── */
#page-anuncios select {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(176,190,197,0.12);
  color: rgba(176,190,197,0.9);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  width: 100%;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
}
#page-anuncios select:focus {
  outline: none;
  border-color: rgba(100,181,246,0.4);
}
#page-anuncios option {
  background: #1a1a2e;
  color: rgba(176,190,197,0.9);
}
#page-anuncios select:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

- [ ] **Step 3: Reiniciar Jake OS e verificar**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup .venv/bin/python app.py >> /tmp/jake_os.log 2>&1 &
sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/login
```
Expected: `200`

Abrir Anúncios → tab Lote → confirmar que o `<select>` "Tipo de campanha" está com fundo escuro e texto legível.

- [ ] **Step 4: Commit**

```bash
git add jake_desktop/static/css/anuncios.css
git commit -m "fix(lote): select dark theme — fundo escuro e texto legivel"
```

---

## Task 2: HTML — toggles no tab Lote

**Files:**
- Modify: `jake_desktop/templates/dashboard.html` (dentro de `#anu-tab-lote`, linhas 694-710)

- [ ] **Step 1: Localizar linha exata**

```bash
grep -n "lote-camp-nome\|Nome da campanha" jake_desktop/templates/dashboard.html
```

- [ ] **Step 2: Localizar também o campo de tipo de campanha**

```bash
grep -n "campanha_tipo\|Tipo de campanha\|lote-camp-tipo" jake_desktop/templates/dashboard.html
```

Confirmar que o campo `campanha_tipo` (select de tipo) está **fora** do bloco que será substituído. O campo `campanha_tipo` deve ficar **fora das divs de toggle** — visível em ambos os modos, pois é obrigatório para o adset. Se ele estiver junto ao campo `lote-camp-nome`, movê-lo para fora antes de continuar.

- [ ] **Step 3: Substituir somente o campo `lote-camp-nome`**

Substituir:
```html
                <label class="anu-label">Nome da campanha
                  <input type="text" id="lote-camp-nome" class="anu-input" placeholder="Campanha Maio 2026">
                </label>
```

Por:
```html
                <!-- Toggle: Nova / Campanha Existente -->
                <div style="display:flex;gap:6px;margin-bottom:10px;">
                  <button id="lote-btn-camp-nova" class="anu-btn-secondary active" style="font-size:12px" onclick="loteCampToggle('nova')">Nova campanha</button>
                  <button id="lote-btn-camp-exist" class="anu-btn-secondary" style="font-size:12px" onclick="loteCampToggle('existente')">Campanha existente</button>
                </div>
                <div id="lote-camp-nova-form">
                  <label class="anu-label">Nome da campanha
                    <input type="text" id="lote-camp-nome" class="anu-input" placeholder="Campanha Maio 2026">
                  </label>
                </div>
                <div id="lote-camp-exist-form" style="display:none">
                  <label class="anu-label">Selecionar campanha existente
                    <select id="lote-camp-select" disabled>
                      <option value="">Selecione o cliente primeiro</option>
                    </select>
                  </label>
                </div>
```

- [ ] **Step 4: Adicionar toggle de criativo Drive**

Localizar `lote-btn-add-criativo`:
```bash
grep -n "lote-btn-add-criativo" jake_desktop/templates/dashboard.html
```

Adicionar ANTES da div `lote-col-header` dos criativos (dentro da col 2):
```html
                  <!-- Toggle: Upload / Drive -->
                  <div id="lote-drive-toggle" style="display:none;gap:4px;padding:4px 6px;">
                    <button id="lote-btn-criativo-upload" class="anu-btn-secondary active" style="font-size:11px" onclick="loteCriativoToggle('upload')">Upload</button>
                    <button id="lote-btn-criativo-drive" class="anu-btn-secondary" style="font-size:11px" onclick="loteCriativoToggle('drive')">Link Drive</button>
                  </div>
                  <div id="lote-drive-form" style="display:none;padding:6px 0;gap:6px;flex-direction:column;">
                    <input type="text" id="lote-drive-url" class="anu-input" placeholder="https://drive.google.com/file/d/..." style="font-size:12px">
                    <button class="anu-btn-secondary" style="font-size:12px" onclick="loteDriveDownload()">⬇ Baixar e usar</button>
                    <div id="lote-drive-status" style="font-size:11px;color:rgba(176,190,197,.4)"></div>
                    <div id="lote-drive-preview" style="margin-top:4px;"></div>
                  </div>
```

- [ ] **Step 5: Verificar que a página carrega sem erro**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/login
```
Expected: `200`

- [ ] **Step 6: Commit**

```bash
git add jake_desktop/templates/dashboard.html
git commit -m "feat(lote): HTML toggles campanha existente e link drive"
```

---

## Task 3: Backend — `campaign_id_existente` no publicar-lote

**Files:**
- Modify: `jake_desktop/app.py` (linhas 4850-4887 em `anuncios_publicar_lote_stream`)

- [ ] **Step 1: Localizar o bloco de criação de campanha**

```bash
grep -n "criar_campanha\|camp_nome\|campaign_id" jake_desktop/app.py | grep -A2 -B2 "4880\|4882\|4884"
```

- [ ] **Step 2: Substituir o bloco de extração + criação de campanha**

Substituir (linhas ~4850-4887):
```python
        camp_nome       = payload.get("campanha_nome", "Campanha Jake OS")
        camp_tipo       = payload.get("campanha_tipo", "MESSAGES")
        orcamento_total = float(payload.get("orcamento_diario_total", 0))
```
Por:
```python
        camp_nome            = payload.get("campanha_nome", "Campanha Jake OS")
        camp_tipo            = payload.get("campanha_tipo", "MESSAGES")
        orcamento_total      = float(payload.get("orcamento_diario_total", 0))
        modo_camp            = payload.get("modo_campanha", "nova")
        campaign_id_existente = payload.get("campaign_id_existente", "").strip()
```

Substituir o bloco de criação de campanha:
```python
        cbo = camp_tipo not in ("ENGAGEMENT", "PURCHASE")
        try:
            campaign_id = _meta_api.criar_campanha(
                token, account_id, camp_tipo, camp_nome, orcamento_total, cbo=cbo
            )
            yield _sse({"tipo": "campanha_ok", "campaign_id": campaign_id})
        except Exception as e:
            yield _sse({"tipo": "erro_fatal", "erro": str(e)}); return
```
Por:
```python
        cbo = camp_tipo not in ("ENGAGEMENT", "PURCHASE")
        if modo_camp == "existente" and campaign_id_existente:
            # Validar que a campanha pertence à conta do cliente
            try:
                r_check = requests.get(
                    f"https://graph.facebook.com/v21.0/{campaign_id_existente}",
                    params={"fields": "account_id", "access_token": token},
                    timeout=10,
                )
                r_check.raise_for_status()
                resp_data = r_check.json()
                expected_account = account_id.replace("act_", "")
                if str(resp_data.get("account_id", "")) != expected_account:
                    yield _sse({"tipo": "erro_fatal", "erro": "Campanha não pertence à conta do cliente"}); return
            except Exception as e:
                yield _sse({"tipo": "erro_fatal", "erro": f"Erro ao validar campanha: {e}"}); return
            campaign_id = campaign_id_existente
            yield _sse({"tipo": "campanha_ok", "campaign_id": campaign_id, "existente": True})
        else:
            try:
                campaign_id = _meta_api.criar_campanha(
                    token, account_id, camp_tipo, camp_nome, orcamento_total, cbo=cbo
                )
                yield _sse({"tipo": "campanha_ok", "campaign_id": campaign_id})
            except Exception as e:
                yield _sse({"tipo": "erro_fatal", "erro": str(e)}); return
```

- [ ] **Step 3: Verificar sintaxe**

```bash
cd /root/jake_desktop && .venv/bin/python -c "import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(lote): backend aceita campaign_id_existente com validacao de ownership"
```

---

## Task 4: Backend — endpoint drive-download para Lote

**Files:**
- Modify: `jake_desktop/app.py` (inserir após linha 3297, após `anuncios_listar_campanhas`)

- [ ] **Step 1: Localizar onde inserir**

```bash
grep -n "anuncios_listar_campanhas\|upload-criativo" jake_desktop/app.py | head -5
```

- [ ] **Step 2: Inserir o endpoint após `anuncios_listar_campanhas` (linha ~3297)**

```python
@app.route("/api/anuncios/lote/drive-download", methods=["POST"])
@login_required
def anuncios_lote_drive_download():
    """Baixa arquivo de link público do Drive, faz upload para Meta e retorna creative_ref."""
    import re as _re
    from urllib.parse import urlparse, parse_qs
    d = request.get_json() or {}
    url        = (d.get("url") or "").strip()
    account_id = (d.get("account_id") or "").strip()
    token_key  = (d.get("token_key") or "META_ACCESS_TOKEN").strip()

    if not url:
        return jsonify({"error": "URL obrigatória"}), 400
    if not account_id:
        return jsonify({"error": "account_id obrigatório"}), 400
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    # Extrair file_id do link do Drive
    file_id = None
    m = _re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if m:
        file_id = m.group(1)
    elif "id=" in url:
        file_id = parse_qs(urlparse(url).query).get("id", [None])[0]
    if not file_id:
        return jsonify({"error": "URL inválida. Use um link no formato drive.google.com/file/d/ID/view"}), 400

    # Baixar arquivo diretamente do Drive (stream para detectar Content-Type antes de ler body)
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        resp = requests.get(download_url, stream=True, allow_redirects=True, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"error": f"Erro ao baixar arquivo: {e}"}), 400

    # Detectar arquivo não público (Drive retorna HTML com página de confirmação)
    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type:
        return jsonify({"error": "Arquivo não público ou requer confirmação. Compartilhe com 'qualquer pessoa com o link'"}), 400

    # Detectar tipo suportado via Content-Type
    _MIME_EXT = {
        "image/jpeg": ".jpg",
        "image/png":  ".png",
        "image/gif":  ".gif",
        "video/mp4":  ".mp4",
    }
    mime_base = content_type.split(";")[0].strip()
    ext = _MIME_EXT.get(mime_base)
    if not ext:
        return jsonify({"error": f"Tipo de arquivo não suportado: {mime_base}. Use JPG, PNG, GIF ou MP4."}), 400

    content = resp.content

    # Salvar em /tmp e fazer upload para Meta
    tmp_id   = str(uuid.uuid4())
    tmp_path = os.path.join(_TMP_DIR, f"{tmp_id}{ext}")
    try:
        with open(tmp_path, "wb") as f:
            f.write(content)
    except Exception as e:
        return jsonify({"error": f"Erro ao salvar arquivo: {e}"}), 500

    try:
        if mime_base == "video/mp4":
            video_id = _meta_api.upload_video(token, account_id, content, f"lote_drive{ext}")
            creative_ref = {"tipo": "video", "video_id": video_id}
        else:
            resultado = _meta_api.upload_imagem(token, account_id, content, f"lote_drive{ext}")
            creative_ref = {"tipo": "imagem", "hash": resultado["hash"]}
    except Exception as e:
        return jsonify({"error": f"Erro ao enviar para Meta: {e}"}), 500
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return jsonify({"creative_ref": creative_ref, "mime": mime_base, "file_id": file_id, "ok": True})
```

Note: `file_id` is returned so the frontend can construct a preview URL.

- [ ] **Step 3: Verificar sintaxe**

```bash
cd /root/jake_desktop && .venv/bin/python -c "import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Reiniciar e testar**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup .venv/bin/python app.py >> /tmp/jake_os.log 2>&1 &
sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/login
```
Expected: `200`

- [ ] **Step 5: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(lote): endpoint drive-download — baixa arquivo do Drive e faz upload para Meta"
```

---

## Task 5: JS — toggle campanha existente no lote.js

**Files:**
- Modify: `jake_desktop/static/js/lote.js`

- [ ] **Step 1: Verificar variáveis e helpers disponíveis no IIFE**

```bash
grep -n "var _conj\|var _cri\|function _esc\|_esc\|_el\b\|_val\b" jake_desktop/static/js/lote.js | head -20
```

Confirmar:
- `_conjIdx` (ou nome equivalente para índice do conjunto ativo) — anotar o nome exato
- `_conjuntos` (ou nome equivalente para array de conjuntos) — anotar o nome exato
- `_esc` — se não existir em lote.js, verificar se está definido globalmente em outro arquivo carregado antes:

```bash
grep -n "function _esc\|window\._esc" jake_desktop/static/js/*.js
```

Se `_esc` não estiver disponível em lote.js, usar esta implementação local (adicionar no topo do IIFE):
```javascript
  function _esc(s) { return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
```

- [ ] **Step 2: Localizar seção de inicialização e localStorage**

```bash
grep -n "_salvarLocal\|_restaurarLocal\|loteInit\|window\.lote" jake_desktop/static/js/lote.js | head -20
```

- [ ] **Step 3: Adicionar variáveis de estado no topo (após linha 14, onde estão as variáveis globais)**

```javascript
  var _modoCamp    = 'nova';       // 'nova' | 'existente'
  var _modoCriativo = 'upload';    // 'upload' | 'drive'
```

- [ ] **Step 4: Atualizar `_salvarLocal()` — adicionar campos novos ao objeto salvo**

Dentro do objeto passado para `localStorage.setItem`, adicionar após `clienteId`:
```javascript
        modoCamp:         _modoCamp,
        campExistenteId:  _val('lote-camp-select'),
        modoCriativo:     _modoCriativo,
        driveUrl:         _val('lote-drive-url'),
```

- [ ] **Step 5: Atualizar `_restaurarLocal()` — restaurar campos novos**

Após a linha `if (s.orcamento) _set('lote-orcamento', s.orcamento);`, adicionar:
```javascript
      if (s.modoCamp) { _modoCamp = s.modoCamp; loteCampToggle(s.modoCamp, true); }
      if (s.campExistenteId) _set('lote-camp-select', s.campExistenteId);
      if (s.modoCriativo) { _modoCriativo = s.modoCriativo; }
      if (s.driveUrl) _set('lote-drive-url', s.driveUrl);
```

- [ ] **Step 6: Adicionar função `loteCampToggle` (exposta no window)**

Adicionar antes do fechamento do IIFE (`})();`):

```javascript
  // ── Toggle: Nova / Campanha Existente ─────────────
  window.loteCampToggle = function(modo, silencioso) {
    _modoCamp = modo;
    var btnNova   = _el('lote-btn-camp-nova');
    var btnExist  = _el('lote-btn-camp-exist');
    var formNova  = _el('lote-camp-nova-form');
    var formExist = _el('lote-camp-exist-form');
    if (!btnNova) return;

    if (modo === 'existente') {
      if (!_cliente && !silencioso) {
        // Sem cliente: reverter para 'nova'
        _modoCamp = 'nova';
        btnNova.classList.add('active');
        btnExist.classList.remove('active');
        if (formNova) formNova.style.display = '';
        if (formExist) formExist.style.display = 'none';
        return;
      }
      btnNova.classList.remove('active');
      btnExist.classList.add('active');
      if (formNova) formNova.style.display = 'none';
      if (formExist) formExist.style.display = '';
      if (!silencioso && _cliente) _loteCarregarCampanhas();
    } else {
      btnNova.classList.add('active');
      btnExist.classList.remove('active');
      if (formNova) formNova.style.display = '';
      if (formExist) formExist.style.display = 'none';
    }
    if (!silencioso) _salvarLocal();
  };

  function _loteCarregarCampanhas() {
    if (!_cliente) return;
    var sel = _el('lote-camp-select');
    if (!sel) return;
    sel.innerHTML = '<option value="">Carregando...</option>';
    sel.disabled = true;
    fetch('/api/anuncios/campanhas/' + _cliente.account_id + '?token_key=' + _cliente.token_key)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.error) {
          sel.innerHTML = '<option value="">Erro: ' + _esc(data.error) + '</option>';
          return;
        }
        var camps = data.campanhas || [];
        if (!camps.length) {
          sel.innerHTML = '<option value="">Nenhuma campanha encontrada</option>';
        } else {
          sel.innerHTML = camps.map(function(c) {
            return '<option value="' + _esc(c.id) + '">' + _esc(c.name) + ' (' + _esc(c.objective || c.status || '') + ')</option>';
          }).join('');
          sel.disabled = false;
        }
        sel.removeEventListener('change', _salvarLocal);
        sel.addEventListener('change', _salvarLocal);
      })
      .catch(function() {
        sel.innerHTML = '<option value="">Erro de rede</option>';
      });
  }
```

- [ ] **Step 7: Recarregar campanhas ao trocar de cliente**

Localizar o evento de troca de cliente no lote.js:
```bash
grep -n "_cliente\s*=\|onchange.*cliente\|clienteChange\|_set.*cliente" jake_desktop/static/js/lote.js | head -10
```

Após a linha onde `_cliente` é definido com o novo cliente, adicionar:
```javascript
    if (_modoCamp === 'existente') _loteCarregarCampanhas();
```

- [ ] **Step 8: Atualizar payload de publicação**

Localizar a montagem do `payload` em `lote.js` e adicionar os campos (usando os nomes de variáveis confirmados no Step 1):
```javascript
      modo_campanha:          _modoCamp,
      campaign_id_existente:  _modoCamp === 'existente' ? (_val('lote-camp-select') || '') : '',
```

- [ ] **Step 9: Testar no browser**

1. Ir em Anúncios → Lote
2. Clicar "Campanha existente" **sem** cliente selecionado → toggle deve voltar para "Nova campanha" automaticamente
3. Selecionar cliente → clicar "Campanha existente" → deve carregar campanhas no seletor
4. Verificar que ao trocar cliente, a lista recarrega

- [ ] **Step 10: Commit**

```bash
git add jake_desktop/static/js/lote.js
git commit -m "feat(lote): JS toggle campanha existente + fetch campanhas + localStorage"
```

---

## Task 6: JS — toggle Drive no lote.js

**Files:**
- Modify: `jake_desktop/static/js/lote.js`

- [ ] **Step 1: Confirmar nomes das variáveis de conjunto e criativo**

```bash
grep -n "_conjIdx\|_conjuntos\|_criatIdx\|MAX_CRIAT\|_renderCriativos\|_renderCopy\|_atualizarContador" jake_desktop/static/js/lote.js | head -20
```

Anotar os nomes exatos. Se algum nome for diferente do esperado, adaptar o código do Step 2 antes de inserir.

- [ ] **Step 2: Adicionar função `loteCriativoToggle` e `loteDriveDownload`**

Adicionar antes do fechamento do IIFE (usando os nomes confirmados no Step 1):

```javascript
  // ── Toggle: Upload / Link Drive ───────────────────
  window.loteCriativoToggle = function(modo) {
    _modoCriativo = modo;
    var btnUpload  = _el('lote-btn-criativo-upload');
    var btnDrive   = _el('lote-btn-criativo-drive');
    var formDrive  = _el('lote-drive-form');
    if (!btnUpload) return;

    if (modo === 'drive') {
      btnUpload.classList.remove('active');
      btnDrive.classList.add('active');
      if (formDrive) formDrive.style.display = 'flex';
    } else {
      btnUpload.classList.add('active');
      btnDrive.classList.remove('active');
      if (formDrive) formDrive.style.display = 'none';
    }
    _salvarLocal();
  };

  window.loteDriveDownload = function() {
    if (!_cliente) { alert('Selecione um cliente primeiro.'); return; }
    if (_conjIdx === null || _conjIdx === undefined) { alert('Selecione um conjunto primeiro.'); return; }

    var url     = (_val('lote-drive-url') || '').trim();
    var status  = _el('lote-drive-status');
    var preview = _el('lote-drive-preview');
    if (!url) { if (status) status.textContent = 'Cole um link do Drive.'; return; }

    if (status) status.textContent = 'Baixando...';
    if (preview) preview.innerHTML = '';
    var btn = document.querySelector('[onclick="loteDriveDownload()"]');
    if (btn) btn.disabled = true;

    fetch('/api/anuncios/lote/drive-download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url:        url,
        account_id: _cliente.account_id,
        token_key:  _cliente.token_key
      })
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (btn) btn.disabled = false;
      if (d.error) {
        if (status) status.textContent = 'Erro: ' + d.error;
        return;
      }
      if (status) status.textContent = 'Criativo carregado via Drive!';

      // Preview: imagem via URL Drive ou ícone de vídeo
      if (preview) {
        var isVideo = d.mime && d.mime.indexOf('video') === 0;
        if (isVideo) {
          preview.innerHTML = '<span style="font-size:24px">🎬</span> <span style="font-size:11px;color:rgba(176,190,197,.6)">Vídeo carregado</span>';
        } else if (d.file_id) {
          var img = document.createElement('img');
          img.src = 'https://drive.google.com/uc?export=download&id=' + d.file_id;
          img.style.cssText = 'max-width:100%;max-height:80px;border-radius:4px;margin-top:4px;';
          img.onerror = function() { preview.innerHTML = '<span style="font-size:11px;color:rgba(176,190,197,.6)">Imagem carregada</span>'; };
          preview.innerHTML = '';
          preview.appendChild(img);
        }
      }

      // Adicionar criativo ao conjunto ativo com o creative_ref retornado
      var conj = _conjuntos[_conjIdx];
      if (!conj.criativos) conj.criativos = [];
      if (conj.criativos.length >= MAX_CRIAT) {
        alert('Máximo de ' + MAX_CRIAT + ' criativos por conjunto.');
        return;
      }
      conj.criativos.push({
        tipo:         d.mime && d.mime.indexOf('video') === 0 ? 'video' : 'imagem',
        creative_ref: d.creative_ref,
        copy:         { titulo: '', texto: '', cta: 'SEND_MESSAGE' },
        preview:      null,
        _url:         url,
      });
      _criatIdx = conj.criativos.length - 1;
      _renderCriativos();
      _renderCopy();
      _atualizarContador();
      _salvarLocal();
    })
    .catch(function(e) {
      if (btn) btn.disabled = false;
      if (status) status.textContent = 'Erro de rede: ' + e;
    });
  };
```

- [ ] **Step 3: Mostrar toggle de drive quando conjunto está selecionado**

Localizar onde `lote-btn-add-criativo` é mostrado/escondido no lote.js:
```bash
grep -n "lote-btn-add-criativo\|lote-drive-toggle" jake_desktop/static/js/lote.js | head -10
```

Na mesma função que mostra `lote-btn-add-criativo`, adicionar:
```javascript
    var driveToggle = _el('lote-drive-toggle');
    if (driveToggle) driveToggle.style.display = 'flex';
```

E quando esconder o botão de criativo, também esconder:
```javascript
    var driveToggle = _el('lote-drive-toggle');
    if (driveToggle) driveToggle.style.display = 'none';
```

- [ ] **Step 4: Testar no browser**

1. Lote → selecionar cliente + conjunto
2. Clicar "Link Drive" → deve aparecer input de URL e div de preview
3. Colar link público do Drive → clicar "Baixar e usar"
4. Deve aparecer preview (imagem ou ícone de vídeo) e criativo na lista do conjunto

- [ ] **Step 5: Commit**

```bash
git add jake_desktop/static/js/lote.js
git commit -m "feat(lote): JS toggle drive download — baixa criativo do Drive e adiciona ao conjunto"
```

---

## Task 7: Teste manual completo + restart final

- [ ] **Step 1: Reiniciar Jake OS**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 2
cd /root/jake_desktop && nohup .venv/bin/python app.py >> /tmp/jake_os.log 2>&1 &
sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/login
```
Expected: `200`

- [ ] **Step 2: Checar logs por erros**

```bash
tail -20 /tmp/jake_os.log
```
Expected: sem erros Python.

- [ ] **Step 3: Verificar fluxo campanha existente**

1. Anúncios → Lote → sem cliente → clicar "Campanha existente" → deve reverter automaticamente para "Nova campanha"
2. Selecionar cliente → clicar "Campanha existente" → seletor carrega campanhas da Meta
3. Selecionar campanha → montar conjuntos + criativos → publicar
4. Verificar no log SSE que aparece `{"tipo": "campanha_ok", "existente": true}`

- [ ] **Step 4: Verificar fluxo Drive**

1. Com conjunto selecionado → clicar "Link Drive"
2. Colar URL pública de imagem do Drive → "Baixar e usar"
3. Verificar que preview aparece e criativo entra na lista
4. Publicar → confirmar que anúncio é criado no Gerenciador Meta

- [ ] **Step 5: Verificar fix visual**

Confirmar que todos os `<select>` no módulo anúncios têm fundo escuro e texto legível.

- [ ] **Step 6: Commit final de verificação**

```bash
git log --oneline -6
```
Verificar que os commits das tasks anteriores estão presentes.
