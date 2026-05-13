# Multi-Cliente Ads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar aba "Multi-Cliente" no módulo de Anúncios com stepper de 3 passos para publicar um mesmo criativo em múltiplos clientes simultaneamente, cada um com seu próprio público.

**Architecture:** Hashes de imagem no Meta são por conta de anúncio — então o upload não pode ser feito uma vez só. O fluxo é: (1) salvar o arquivo em `/tmp` via endpoint `upload-temp`, (2) na stream SSE fazer upload para cada conta individualmente e criar o anúncio com o hash resultante. O preparar/stream reutiliza o dict `_lote_payloads` já existente. Frontend: novo arquivo `multi-cliente.js` + HTML no `dashboard.html` + registro da tab em `anuncios.js`.

**Tech Stack:** Flask (SSE generator bare pattern), JavaScript ES5 (IIFE, padrão do projeto), Meta Ads API via `_meta_api`, PostgreSQL via psycopg2.

---

## Arquivos

- **Criar:** `jake_desktop/static/js/multi-cliente.js` — lógica completa do stepper
- **Modificar:** `jake_desktop/app.py` — 3 novos endpoints (upload-temp, preparar, stream)
- **Modificar:** `jake_desktop/templates/dashboard.html` — nova tab button + HTML do stepper + script tag
- **Modificar:** `jake_desktop/static/js/anuncios.js` — registrar tab 'multi' no `anuSwitchTab`
- **Modificar:** `jake_desktop/static/css/anuncios.css` — estilos do stepper

---

### Task 1: Backend — endpoint upload-temp

Salva a imagem em `/tmp` sem chamar a Meta API. O upload real para cada conta acontece na stream.

**Files:**
- Modify: `jake_desktop/app.py` (inserir antes da seção `# ABA SUBIR ANÚNCIOS — Builder de Lote`, ~linha 3564)

- [ ] **Inserir o bloco completo**

```python
# ══════════════════════════════════════════════════════════════════════════
#  ABA SUBIR ANÚNCIOS — Multi-Cliente
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/anuncios/multi-cliente/upload-temp", methods=["POST"])
@login_required
def anuncios_multi_cliente_upload_temp():
    """Salva o criativo em /tmp e retorna tmp_uuid. Upload real para cada conta ocorre na stream."""
    if "criativo" not in request.files:
        return jsonify({"error": "Campo 'criativo' ausente"}), 400
    arq  = request.files["criativo"]
    ext  = os.path.splitext(arq.filename or "img")[1].lower() or ".jpg"
    mime = arq.content_type or "image/jpeg"
    tmp_uuid_val = str(uuid.uuid4())
    tmp_path = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{ext}")
    arq.save(tmp_path)
    return jsonify({"tmp_uuid": tmp_uuid_val, "ext": ext, "mime": mime, "ok": True})
```

- [ ] **Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(multi-cliente): endpoint upload-temp — salva criativo em /tmp"
```

---

### Task 2: Backend — endpoint preparar

**Files:**
- Modify: `jake_desktop/app.py` (logo após o endpoint upload-temp)

- [ ] **Inserir o bloco**

```python
@app.route("/api/anuncios/multi-cliente/preparar", methods=["POST"])
@login_required
def anuncios_multi_cliente_preparar():
    """Valida payload, busca perfis dos clientes, armazena em memória, retorna token + dados para revisão."""
    d = request.get_json() or {}
    cliente_ids = d.get("cliente_ids") or []
    if not cliente_ids:
        return jsonify({"error": "Selecione ao menos um cliente"}), 400
    if not d.get("tmp_uuid"):
        return jsonify({"error": "Criativo obrigatório — faça upload primeiro"}), 400
    if not d.get("campanha_nome"):
        return jsonify({"error": "Nome da campanha obrigatório"}), 400
    if not d.get("orcamento"):
        return jsonify({"error": "Orçamento obrigatório"}), 400

    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, agencia, account_id, token_key, page_id, link_url, "
            "campanha_tipo, optimization_goal, pixel_id, localizacao_json, publico_json "
            "FROM ad_client_profiles WHERE id = ANY(%s)",
            (cliente_ids,)
        )
        clientes = [dict(c) for c in cur.fetchall()]
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar clientes: {e}"}), 500

    if not clientes:
        return jsonify({"error": "Nenhum cliente encontrado"}), 404

    erros = []
    for c in clientes:
        loc = c.get("localizacao_json") or {}
        if not (loc.get("paises") or loc.get("cidades")):
            erros.append(f"{c['nome']}: localização não configurada")
        if not c.get("page_id"):
            erros.append(f"{c['nome']}: page_id não configurado")
        if c.get("token_key") not in _VALID_TOKEN_KEYS:
            erros.append(f"{c['nome']}: token_key inválido")
    if erros:
        return jsonify({"error": "Clientes com configuração incompleta", "detalhes": erros}), 400

    mc_token = str(uuid.uuid4())
    _lote_payloads[mc_token] = {
        "clientes":      clientes,
        "tmp_uuid":      d["tmp_uuid"],
        "tmp_ext":       d.get("tmp_ext", ".jpg"),
        "copy":          d.get("copy") or {},
        "campanha_nome": d["campanha_nome"],
        "orcamento":     float(d["orcamento"]),
    }

    clientes_revisao = []
    for c in clientes:
        pub = c.get("publico_json") or {}
        loc = c.get("localizacao_json") or {}
        cidades_raw = loc.get("cidades") or []
        cidades = [ci.get("name", ci) if isinstance(ci, dict) else ci for ci in cidades_raw]
        clientes_revisao.append({
            "id":       c["id"],
            "nome":     c["nome"],
            "agencia":  c["agencia"],
            "publico": {
                "idade_min": pub.get("idade_min", 18),
                "idade_max": pub.get("idade_max", 65),
                "genero":    pub.get("genders", []),
                "cidades":   cidades,
                "paises":    loc.get("paises") or [],
            },
            "orcamento": d["orcamento"],
        })

    return jsonify({"token": mc_token, "clientes": clientes_revisao})
```

- [ ] **Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(multi-cliente): endpoint preparar — valida clientes e armazena payload"
```

---

### Task 3: Backend — endpoint stream SSE

**Files:**
- Modify: `jake_desktop/app.py` (logo após o endpoint preparar)

- [ ] **Inserir o bloco**

Usar o padrão de generator bare (sem `stream_with_context`) igual ao endpoint de lote existente.

```python
@app.route("/api/anuncios/multi-cliente/stream/<mc_token>")
@login_required
def anuncios_multi_cliente_stream(mc_token):
    """Para cada cliente: faz upload da imagem na conta dele, cria campanha+conjunto+anúncio via SSE."""
    payload = _lote_payloads.pop(mc_token, None)

    def _sse(data: dict) -> str:
        return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

    def _gerar():
        if not payload:
            yield _sse({"status": "erro", "cliente": "", "erro": "Token inválido ou expirado", "idx": 0, "total": 0})
            return

        clientes      = payload["clientes"]
        tmp_uuid_val  = payload["tmp_uuid"]
        tmp_ext       = payload.get("tmp_ext", ".jpg")
        copy_data     = payload["copy"]
        campanha_nome = payload["campanha_nome"]
        orcamento     = payload["orcamento"]
        total         = len(clientes)

        tmp_path = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{tmp_ext}")
        try:
            with open(tmp_path, "rb") as f:
                file_bytes = f.read()
            filename = f"mc_criativo{tmp_ext}"
            mime = "video/mp4" if tmp_ext == ".mp4" else "image/jpeg"
        except Exception as e:
            yield _sse({"status": "erro", "cliente": "upload", "erro": f"Arquivo temp não encontrado: {e}", "idx": 0, "total": total})
            return

        for idx, cliente in enumerate(clientes):
            nome       = cliente["nome"]
            account_id = cliente["account_id"]
            token_key  = cliente["token_key"]
            token_val  = os.getenv(token_key, "")
            page_id    = cliente.get("page_id", "")
            camp_tipo  = cliente.get("campanha_tipo", "MESSAGES")
            localizacao = cliente.get("localizacao_json") or {}
            publico    = cliente.get("publico_json") or {}
            link_url   = cliente.get("link_url") or ""
            opt_goal   = cliente.get("optimization_goal") or None
            pixel_id   = cliente.get("pixel_id") or None

            yield _sse({"status": "publicando", "cliente": nome, "idx": idx + 1, "total": total})

            campaign_id = adset_id = ad_id = None
            try:
                # 1. Upload imagem para a conta deste cliente
                if "video" in mime:
                    video_id = _meta_api.upload_video(token_val, account_id, file_bytes, filename)
                    creative_ref = {"tipo": "video", "video_id": video_id}
                else:
                    resultado = _meta_api.upload_imagem(token_val, account_id, file_bytes, filename)
                    creative_ref = {"tipo": "imagem", "hash": resultado["hash"]}

                # 2. Campanha
                cbo = camp_tipo not in ("ENGAGEMENT", "PURCHASE")
                campaign_id = _meta_api.criar_campanha(
                    token_val, account_id, camp_tipo, campanha_nome, orcamento, cbo=cbo
                )

                # 3. Conjunto
                try:
                    adset_id = _meta_api.criar_conjunto(
                        token_val, account_id, campaign_id, camp_tipo, publico, localizacao,
                        orcamento=(orcamento if camp_tipo in ("ENGAGEMENT", "PURCHASE") else None),
                        optimization_goal=opt_goal, pixel_id=pixel_id
                    )
                except Exception as e2:
                    _meta_api.deletar_objeto_meta(token_val, campaign_id)
                    raise Exception(f"Falha no conjunto: {e2}")

                # 4. Anúncio
                try:
                    ad_id = _meta_api.criar_anuncio(
                        token_val, account_id, adset_id, page_id, creative_ref,
                        copy_data.get("titulo", ""), copy_data.get("texto", ""),
                        copy_data.get("cta", "SEND_MESSAGE"), link_url=link_url
                    )
                except Exception as e3:
                    _meta_api.deletar_objeto_meta(token_val, adset_id)
                    _meta_api.deletar_objeto_meta(token_val, campaign_id)
                    raise Exception(f"Falha no anúncio: {e3}")

                # 5. Log
                try:
                    conn = _get_db(); cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO ad_publish_log
                            (cliente_id, account_id, campaign_id, adset_id, ad_id,
                             status, audience_id, payload_json)
                        VALUES (%s,%s,%s,%s,%s,'sucesso',NULL,%s)
                    """, (cliente["id"], account_id, campaign_id, adset_id, ad_id,
                          json.dumps(copy_data)))
                    conn.commit(); conn.close()
                except Exception:
                    pass

                yield _sse({"status": "ok", "cliente": nome, "ad_id": ad_id, "idx": idx + 1, "total": total})

            except Exception as e:
                try:
                    conn = _get_db(); cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO ad_publish_log
                            (cliente_id, account_id, campaign_id, adset_id, ad_id,
                             status, audience_id, erro_msg, payload_json)
                        VALUES (%s,%s,%s,%s,%s,'erro',NULL,%s,%s)
                    """, (cliente["id"], account_id, campaign_id, adset_id, ad_id,
                          str(e), json.dumps(copy_data)))
                    conn.commit(); conn.close()
                except Exception:
                    pass
                yield _sse({"status": "erro", "cliente": nome, "erro": str(e), "idx": idx + 1, "total": total})

        # Limpar arquivo temp
        try:
            os.remove(tmp_path)
        except Exception:
            pass

        yield _sse({"status": "concluido", "total": total})

    return app.response_class(
        _gerar(),
        mimetype="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )
```

- [ ] **Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(multi-cliente): stream SSE — upload por conta + criação de anúncios"
```

---

### Task 4: Frontend HTML — tab button + stepper

**Files:**
- Modify: `jake_desktop/templates/dashboard.html`

- [ ] **Adicionar botão da tab** (após o botão "Lote ⚡", ~linha 493)

```html
<button class="anu-btn-secondary anu-tab-btn" data-tab="multi" onclick="anuSwitchTab('multi')" style="font-size:13px">Multi-Cliente</button>
```

- [ ] **Adicionar HTML do stepper** (após `</div><!-- /anu-tab-lote -->`, ~linha 758)

```html
<!-- Tab: Multi-Cliente -->
<div id="anu-tab-multi" style="display:none">

  <!-- Stepper header -->
  <div class="mc-stepper">
    <div class="mc-step active" data-step="1"><span class="mc-step-num">1</span> Clientes</div>
    <div class="mc-step" data-step="2"><span class="mc-step-num">2</span> Criativo</div>
    <div class="mc-step" data-step="3"><span class="mc-step-num">3</span> Revisar</div>
  </div>

  <!-- Passo 1: Selecionar Clientes -->
  <div id="mc-passo-1">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <span style="font-weight:600;font-size:14px">Selecione os clientes</span>
      <div style="display:flex;gap:8px;">
        <button class="anu-btn-secondary" style="font-size:12px" onclick="mcSelecionarAgencia('dentto')">Todos Dentto</button>
        <button class="anu-btn-secondary" style="font-size:12px" onclick="mcSelecionarAgencia('piloti')">Todos Piloti</button>
        <button class="anu-btn-secondary" style="font-size:12px" onclick="mcLimparSelecao()">Limpar</button>
      </div>
    </div>
    <div id="mc-lista-clientes" style="display:flex;flex-direction:column;gap:6px;max-height:400px;overflow-y:auto;margin-bottom:16px;"></div>
    <button class="anu-btn-primary" onclick="mcIrPasso(2)" id="mc-btn-passo2" disabled>Próximo →</button>
  </div>

  <!-- Passo 2: Criativo -->
  <div id="mc-passo-2" style="display:none">
    <div style="display:flex;flex-direction:column;gap:12px;max-width:520px;">
      <label class="anu-label">Imagem do anúncio
        <div id="mc-dropzone" style="margin-top:4px;min-height:120px;display:flex;align-items:center;justify-content:center;cursor:pointer;border:2px dashed rgba(176,190,197,.2);border-radius:8px;position:relative;">
          <input type="file" id="mc-file-input" accept="image/*,video/mp4" style="position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%;">
          <div id="mc-dropzone-placeholder" style="text-align:center;pointer-events:none;"><span style="font-size:24px">⬆</span><p style="margin:4px 0 0;font-size:12px;color:rgba(176,190,197,.4)">Clique ou arraste a imagem</p></div>
          <img id="mc-preview-img" style="display:none;max-width:100%;max-height:200px;border-radius:6px;pointer-events:none;">
        </div>
        <div id="mc-upload-status" style="font-size:11px;color:rgba(176,190,197,.4);margin-top:4px;"></div>
      </label>
      <label class="anu-label">Nome da campanha
        <input type="text" id="mc-camp-nome" class="anu-input" placeholder="Campanha Maio 2026">
      </label>
      <label class="anu-label">Título do anúncio
        <input type="text" id="mc-copy-titulo" class="anu-input" placeholder="Título">
      </label>
      <label class="anu-label">Texto do anúncio
        <textarea id="mc-copy-texto" class="anu-input" rows="4" placeholder="Texto do anúncio..."></textarea>
      </label>
      <label class="anu-label">Orçamento diário (R$)
        <input type="number" id="mc-orcamento" class="anu-input" placeholder="30" min="1">
      </label>
    </div>
    <div style="display:flex;gap:8px;margin-top:16px;">
      <button class="anu-btn-secondary" onclick="mcIrPasso(1)">← Voltar</button>
      <button class="anu-btn-primary" onclick="mcIrPasso(3)" id="mc-btn-passo3">Revisar →</button>
    </div>
  </div>

  <!-- Passo 3: Revisão + Publicar -->
  <div id="mc-passo-3" style="display:none">
    <p style="font-size:13px;color:rgba(176,190,197,.5);margin-bottom:12px;">Confirme o público de cada cliente antes de publicar.</p>
    <div id="mc-revisao-cards" style="display:flex;flex-direction:column;gap:10px;margin-bottom:16px;max-height:400px;overflow-y:auto;"></div>
    <div id="mc-progresso" style="display:none;margin-bottom:16px;">
      <div style="font-size:13px;font-weight:600;margin-bottom:8px">Publicando...</div>
      <div id="mc-prog-lista" style="display:flex;flex-direction:column;gap:4px;font-size:12px;"></div>
    </div>
    <div style="display:flex;gap:8px;">
      <button class="anu-btn-secondary" onclick="mcIrPasso(2)" id="mc-btn-voltar3">← Voltar</button>
      <button class="anu-btn-primary" onclick="mcPublicar()" id="mc-btn-publicar">Publicar Tudo</button>
    </div>
  </div>

</div><!-- /anu-tab-multi -->
```

- [ ] **Adicionar script tag** (após a linha do `lote.js`, ~linha 2558)

```html
<script src="{{ url_for('static', filename='js/multi-cliente.js') }}"></script>
```

- [ ] **Commit**

```bash
git add jake_desktop/templates/dashboard.html
git commit -m "feat(multi-cliente): HTML stepper 3 passos + tab button"
```

---

### Task 5: Frontend JS — anuncios.js (registrar tab)

**Files:**
- Modify: `jake_desktop/static/js/anuncios.js`

- [ ] **Registrar tab 'multi'** (~linha 19): mudar de

```javascript
['publicar', 'publicos', 'lote'].forEach(function(t) {
```
para:
```javascript
['publicar', 'publicos', 'lote', 'multi'].forEach(function(t) {
```

- [ ] **Chamar mcInit ao trocar para a tab** (~linha 26, após o if de lote):

```javascript
if (tab === 'multi' && typeof mcInit === 'function') mcInit();
```

- [ ] **Commit**

```bash
git add jake_desktop/static/js/anuncios.js
git commit -m "feat(multi-cliente): registrar tab multi no anuSwitchTab"
```

---

### Task 6: Frontend JS — multi-cliente.js

**Files:**
- Create: `jake_desktop/static/js/multi-cliente.js`

- [ ] **Criar o arquivo**

```javascript
/* ──────────────────────────────────────────────────────
   Jake OS — Multi-Cliente: mesmo criativo, N clientes
────────────────────────────────────────────────────── */
(function () {
  'use strict';

  var _clientes     = [];   // todos os clientes carregados
  var _selecionados = {};   // id -> true
  var _tmpUuid      = null; // retornado pelo upload-temp
  var _tmpExt       = '.jpg';
  var _revisaoToken = null; // token do /preparar
  var _revisaoData  = null; // array de clientes com público

  function _val(id) { var el=document.getElementById(id); return el?el.value.trim():''; }
  function _el(id)  { return document.getElementById(id); }
  function _esc(s)  { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'); }
  function _status(msg) { var el=_el('mc-upload-status'); if(el) el.textContent=msg; }

  // ── Init (chamado ao trocar para tab) ──────────────
  window.mcInit = function() {
    if (_clientes.length) { renderListaClientes(); return; }
    fetch('/api/anuncios/clientes')
      .then(function(r){ return r.json(); })
      .then(function(d){ _clientes = d.clientes || []; renderListaClientes(); })
      .catch(function(){ _clientes = []; });
  };

  // ── Passo 1: lista de clientes ─────────────────────
  function renderListaClientes() {
    var cont = _el('mc-lista-clientes'); if (!cont) return;
    if (!_clientes.length) {
      cont.innerHTML = '<p style="font-size:12px;color:rgba(176,190,197,.4)">Nenhum cliente cadastrado.</p>';
      return;
    }
    cont.innerHTML = _clientes.map(function(c) {
      var checked = _selecionados[c.id] ? 'checked' : '';
      return '<label style="display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:6px;background:rgba(255,255,255,.03);cursor:pointer;">' +
        '<input type="checkbox" value="' + c.id + '" ' + checked + ' onchange="mcToggleCliente(' + c.id + ')">' +
        '<span style="font-size:13px">' + _esc(c.nome) + '</span>' +
        '<span style="font-size:11px;color:rgba(176,190,197,.35);margin-left:auto">' + _esc(c.agencia) + '</span>' +
        '</label>';
    }).join('');
    atualizarBtnPasso2();
  }

  window.mcToggleCliente = function(id) {
    if (_selecionados[id]) { delete _selecionados[id]; } else { _selecionados[id] = true; }
    atualizarBtnPasso2();
  };

  window.mcSelecionarAgencia = function(ag) {
    _clientes.forEach(function(c){ if (c.agencia === ag) _selecionados[c.id] = true; });
    renderListaClientes();
  };

  window.mcLimparSelecao = function() {
    _selecionados = {};
    renderListaClientes();
  };

  function atualizarBtnPasso2() {
    var btn = _el('mc-btn-passo2');
    if (btn) btn.disabled = Object.keys(_selecionados).length === 0;
  }

  // ── Passo 2: upload de imagem ──────────────────────
  function bindUpload() {
    var input = _el('mc-file-input');
    if (!input || input._mcBound) return;
    input._mcBound = true;
    input.addEventListener('change', function() {
      var file = input.files[0]; if (!file) return;
      // Preview local
      var preview     = _el('mc-preview-img');
      var placeholder = _el('mc-dropzone-placeholder');
      if (preview && file.type.indexOf('image') === 0) {
        preview.src = URL.createObjectURL(file);
        preview.style.display = '';
        if (placeholder) placeholder.style.display = 'none';
      }
      uploadTemp(file);
    });
  }

  function uploadTemp(file) {
    _tmpUuid = null;
    _status('Enviando...');
    var fd = new FormData();
    fd.append('criativo', file);
    fetch('/api/anuncios/multi-cliente/upload-temp', { method: 'POST', body: fd })
      .then(function(r){ return r.json(); })
      .then(function(d){
        if (d.tmp_uuid) {
          _tmpUuid = d.tmp_uuid;
          _tmpExt  = d.ext || '.jpg';
          _status('Arquivo pronto ✓');
        } else {
          _status('Erro: ' + (d.error || 'desconhecido'));
        }
      })
      .catch(function(){ _status('Erro ao enviar arquivo.'); });
  }

  // ── Navegação entre passos ─────────────────────────
  window.mcIrPasso = function(n) {
    if (n === 2) {
      if (Object.keys(_selecionados).length === 0) return;
      bindUpload();
      mostrarPasso(2);
      return;
    }
    if (n === 3) {
      if (!_tmpUuid)           { alert('Aguarde o upload da imagem.'); return; }
      if (!_val('mc-camp-nome'))  { alert('Informe o nome da campanha.'); return; }
      if (!_val('mc-orcamento'))  { alert('Informe o orçamento diário.'); return; }
      mcPreparar();
      return;
    }
    mostrarPasso(n);
  };

  function mostrarPasso(n) {
    [1,2,3].forEach(function(i){
      var el = _el('mc-passo-' + i);
      if (el) el.style.display = (i === n) ? '' : 'none';
      var step = document.querySelector('.mc-step[data-step="' + i + '"]');
      if (step) step.classList.toggle('active', i === n);
    });
  }

  // ── Preparar (/preparar → dados de revisão) ────────
  function mcPreparar() {
    var btn = _el('mc-btn-passo3');
    if (btn) { btn.disabled = true; btn.textContent = 'Carregando...'; }

    var payload = {
      cliente_ids:   Object.keys(_selecionados).map(Number),
      tmp_uuid:      _tmpUuid,
      tmp_ext:       _tmpExt,
      copy: {
        titulo: _val('mc-copy-titulo'),
        texto:  _val('mc-copy-texto'),
        cta:    'SEND_MESSAGE'
      },
      campanha_nome: _val('mc-camp-nome'),
      orcamento:     parseFloat(_val('mc-orcamento')) || 0,
    };

    fetch('/api/anuncios/multi-cliente/preparar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (btn) { btn.disabled = false; btn.textContent = 'Revisar →'; }
      if (d.error) {
        alert(d.error + (d.detalhes ? '\n' + d.detalhes.join('\n') : ''));
        return;
      }
      _revisaoToken = d.token;
      _revisaoData  = d.clientes;
      renderRevisao();
      mostrarPasso(3);
    })
    .catch(function(){
      if (btn) { btn.disabled = false; btn.textContent = 'Revisar →'; }
      alert('Erro ao preparar publicação.');
    });
  }

  // ── Passo 3: cards de revisão ──────────────────────
  function renderRevisao() {
    var cont = _el('mc-revisao-cards');
    if (!cont || !_revisaoData) return;
    cont.innerHTML = _revisaoData.map(function(c) {
      var pub = c.publico;
      var generoLabel = (!pub.genero || !pub.genero.length) ? 'Todos' : (pub.genero[0] === 1 ? 'Masculino' : 'Feminino');
      var locLabel = (pub.cidades && pub.cidades.length) ? pub.cidades.join(', ') : (pub.paises || []).join(', ');
      return '<div style="padding:12px 14px;border-radius:8px;background:rgba(255,255,255,.04);border:1px solid rgba(176,190,197,.08);">' +
        '<div style="font-weight:600;font-size:13px;margin-bottom:6px">' + _esc(c.nome) +
          ' <span style="font-size:11px;color:rgba(176,190,197,.4)">' + _esc(c.agencia) + '</span></div>' +
        '<div style="font-size:12px;color:rgba(176,190,197,.6);display:flex;flex-wrap:wrap;gap:10px;">' +
          '<span>Idade: ' + pub.idade_min + '–' + pub.idade_max + '</span>' +
          '<span>Gênero: ' + generoLabel + '</span>' +
          '<span>Local: ' + _esc(locLabel || 'não configurado') + '</span>' +
          '<span>Orçamento: R$ ' + c.orcamento + '</span>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  // ── Publicar tudo (SSE) ────────────────────────────
  window.mcPublicar = function() {
    if (!_revisaoToken) return;
    var btnPublicar = _el('mc-btn-publicar');
    var btnVoltar   = _el('mc-btn-voltar3');
    var progDiv     = _el('mc-progresso');
    var progLista   = _el('mc-prog-lista');
    if (btnPublicar) { btnPublicar.disabled = true; btnPublicar.textContent = 'Publicando...'; }
    if (btnVoltar)   btnVoltar.disabled = true;
    if (progDiv)     progDiv.style.display = '';
    if (progLista)   progLista.innerHTML = '';

    var es = new EventSource('/api/anuncios/multi-cliente/stream/' + _revisaoToken);
    es.onmessage = function(evt) {
      var d; try { d = JSON.parse(evt.data); } catch(e) { return; }
      if (!progLista) return;

      if (d.status === 'publicando') {
        var li = document.createElement('div');
        li.id = 'mc-prog-' + d.idx;
        li.style.cssText = 'color:rgba(176,190,197,.5)';
        li.textContent = '⏳ (' + d.idx + '/' + d.total + ') ' + d.cliente + '...';
        progLista.appendChild(li);
      } else if (d.status === 'ok') {
        var el = document.getElementById('mc-prog-' + d.idx);
        if (el) { el.textContent = '✓ ' + d.cliente; el.style.color = '#4caf50'; }
      } else if (d.status === 'erro') {
        var el = document.getElementById('mc-prog-' + d.idx);
        if (el) { el.textContent = '✗ ' + d.cliente + ' — ' + d.erro; el.style.color = '#ef5350'; }
      } else if (d.status === 'concluido') {
        es.close();
        if (btnPublicar) { btnPublicar.disabled = false; btnPublicar.textContent = 'Concluído ✓'; }
        if (btnVoltar)   btnVoltar.disabled = false;
      }
    };
    es.onerror = function() {
      es.close();
      if (btnPublicar) { btnPublicar.disabled = false; btnPublicar.textContent = 'Publicar Tudo'; }
      if (btnVoltar)   btnVoltar.disabled = false;
    };
  };

})();
```

- [ ] **Commit**

```bash
git add jake_desktop/static/js/multi-cliente.js
git commit -m "feat(multi-cliente): JS stepper completo — seleção, upload-temp, revisão, SSE"
```

---

### Task 7: CSS — estilos do stepper

**Files:**
- Modify: `jake_desktop/static/css/anuncios.css` (buscar `.lote-topo` para localizar a seção de anúncios e adicionar ao final)

- [ ] **Adicionar ao final do arquivo**

```css
/* ── Multi-Cliente Stepper ───────────────────── */
.mc-stepper {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(176,190,197,.08);
}
.mc-step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(176,190,197,.35);
  font-weight: 500;
  letter-spacing: .04em;
}
.mc-step.active {
  color: rgba(176,190,197,.9);
}
.mc-step-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(176,190,197,.1);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
}
.mc-step.active .mc-step-num {
  background: rgba(100,181,246,.25);
  color: #64b5f6;
}
```

- [ ] **Commit**

```bash
git add jake_desktop/static/css/anuncios.css
git commit -m "feat(multi-cliente): estilos do stepper"
```

---

### Task 8: Teste manual + restart

- [ ] **Reiniciar Jake OS**

```bash
pkill -f "python.*app.py"; sleep 1
cd /root/jake_desktop && nohup .venv/bin/python app.py >> /tmp/jake_os.log 2>&1 &
sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/login
# Esperado: 200
```

- [ ] **Testar fluxo completo**
  1. Anúncios → aba "Multi-Cliente"
  2. Passo 1: selecionar 2+ clientes Dentto → Próximo
  3. Passo 2: subir imagem → aguardar "Arquivo pronto ✓" → preencher campos → Revisar
  4. Passo 3: conferir cards de público de cada cliente
  5. Publicar Tudo → acompanhar progresso SSE (✓ verde por cliente ou ✗ vermelho com erro)
  6. Confirmar no Gerenciador Meta que anúncios foram criados (status PAUSADO)

- [ ] **Commit final**

```bash
git add -A
git commit -m "feat(multi-cliente): publicação de criativo único para múltiplos clientes"
```
