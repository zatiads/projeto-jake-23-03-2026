# Públicos Salvos — Jake OS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar sistema de públicos salvos na aba "Subir Anúncios" do Jake OS, com importação do Meta e seletor no fluxo de publicação.

**Architecture:** Nova tabela `ad_audiences` no Neon/PostgreSQL. Duas funções novas no `meta/meta_api.py` para buscar públicos do Meta. Cinco novas rotas em `jake_desktop/app.py`. Nova sub-aba "Públicos" no frontend (HTML + JS em `anuncios.js`). Rota `/api/anuncios/publicar` recebe `audience_id` opcional como fallback ao `publico_json` existente.

**Tech Stack:** Flask, psycopg2, Meta Graph API v21.0, JavaScript vanilla (SPA existente)

**Spec:** `docs/superpowers/specs/2026-05-07-audiencias-jake-os-design.md`

---

## File Map

| Arquivo | Ação | O que muda |
|---------|------|------------|
| `meta/meta_api.py` | Modificar | +2 funções: `listar_publicos_salvos`, `listar_custom_audiences` |
| `jake_desktop/app.py` | Modificar | +5 rotas audiences + modificar `/publicar` para aceitar `audience_id` |
| `jake_desktop/templates/dashboard.html` | Modificar | +tab "Públicos" dentro de "Subir Anúncios" |
| `jake_desktop/static/js/anuncios.js` | Modificar | +lógica de gerenciamento de públicos + seletor no publicar |

---

## Task 1: Banco de Dados — criar tabela e migrar ad_publish_log

**Files:**
- Executar SQL direto via psycopg2 (sem arquivo novo)

- [ ] **Step 1: Criar tabela `ad_audiences` e índice**

Executar no terminal:

```bash
DB_URL=$(grep "DATABASE_URL" /root/.env | cut -d'=' -f2-)
/root/venv/bin/python3 -c "
import psycopg2
conn = psycopg2.connect('$DB_URL')
cur = conn.cursor()
cur.execute('''
    CREATE TABLE IF NOT EXISTS ad_audiences (
        id               SERIAL PRIMARY KEY,
        nome             VARCHAR(255) NOT NULL,
        account_id       VARCHAR(64)  NOT NULL,
        token_key        VARCHAR(64)  NOT NULL,
        tipo             VARCHAR(32)  NOT NULL CHECK (tipo IN (\'manual\', \'salvo_meta\', \'custom_meta\')),
        targeting_json   JSONB        NOT NULL DEFAULT \'{}\',
        meta_audience_id VARCHAR(64),
        criado_em        TIMESTAMP    DEFAULT NOW()
    )
''')
cur.execute('''
    CREATE UNIQUE INDEX IF NOT EXISTS ad_audiences_meta_unique
        ON ad_audiences (account_id, meta_audience_id)
        WHERE meta_audience_id IS NOT NULL
''')
cur.execute('ALTER TABLE ad_publish_log ADD COLUMN IF NOT EXISTS audience_id INTEGER')
conn.commit()
print('OK')
conn.close()
"
```

- [ ] **Step 2: Verificar criação**

```bash
DB_URL=$(grep "DATABASE_URL" /root/.env | cut -d'=' -f2-)
/root/venv/bin/python3 -c "
import psycopg2
conn = psycopg2.connect('$DB_URL')
cur = conn.cursor()
cur.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='ad_audiences' ORDER BY ordinal_position\")
print('ad_audiences:', [r[0] for r in cur.fetchall()])
cur.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='ad_publish_log' AND column_name='audience_id'\")
print('audience_id em ad_publish_log:', cur.fetchone())
conn.close()
"
```

Esperado: lista com id, nome, account_id, token_key, tipo, targeting_json, meta_audience_id, criado_em + audience_id presente.

- [ ] **Step 3: Commit**

```bash
cd /root && git add -A && git commit -m "feat(db): tabela ad_audiences + audience_id em ad_publish_log"
```

---

## Task 2: Meta API — funções para buscar públicos

**Files:**
- Modify: `/root/meta/meta_api.py`

- [ ] **Step 1: Adicionar `listar_publicos_salvos` e `listar_custom_audiences`**

Em `/root/meta/meta_api.py`, adicionar após a função `listar_paginas`:

```python
def listar_publicos_salvos(token: str, account_id: str) -> list:
    """Lista saved audiences da conta. Retorna lista de dicts com id, name, targeting."""
    url = f"{GRAPH_URL}/{account_id}/saved_audiences"
    resp = requests.get(url, params={
        "fields": "id,name,targeting",
        "access_token": token,
        "limit": 50,
    })
    data = resp.json()
    if "data" in data:
        return data["data"]
    raise Exception(data.get("error", {}).get("message", "Erro ao listar saved audiences"))


def listar_custom_audiences(token: str, account_id: str) -> list:
    """Lista custom audiences da conta. Retorna lista de dicts com id, name, subtype."""
    url = f"{GRAPH_URL}/{account_id}/customaudiences"
    resp = requests.get(url, params={
        "fields": "id,name,subtype",
        "access_token": token,
        "limit": 50,
    })
    data = resp.json()
    if "data" in data:
        return data["data"]
    raise Exception(data.get("error", {}).get("message", "Erro ao listar custom audiences"))
```

- [ ] **Step 2: Verificar sintaxe**

```bash
/root/venv/bin/python3 -c "from meta import meta_api; print('listar_publicos_salvos:', callable(meta_api.listar_publicos_salvos)); print('listar_custom_audiences:', callable(meta_api.listar_custom_audiences))"
```

Esperado: ambos `True`.

- [ ] **Step 3: Commit**

```bash
cd /root && git add meta/meta_api.py && git commit -m "feat(meta): listar_publicos_salvos + listar_custom_audiences"
```

---

## Task 3: Backend — rotas CRUD de audiences

**Files:**
- Modify: `/root/jake_desktop/app.py` (inserir antes do bloco `# ABA SUBIR ANÚNCIOS — Meta API`)

- [ ] **Step 1: Adicionar rotas GET, POST, PUT, DELETE**

Em `jake_desktop/app.py`, localizar o comentário `#  ABA SUBIR ANÚNCIOS — Meta API` (linha ~3111) e inserir ANTES dele:

```python
#  ABA SUBIR ANÚNCIOS — CRUD de públicos salvos
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/anuncios/audiences")
@login_required
def audiences_listar():
    account_id = request.args.get("account_id", "").strip() or None
    try:
        conn = _get_db()
        cur  = conn.cursor()
        if account_id:
            cur.execute("SELECT * FROM ad_audiences WHERE account_id=%s ORDER BY tipo, nome", (account_id,))
        else:
            cur.execute("SELECT * FROM ad_audiences ORDER BY account_id, tipo, nome")
        rows = cur.fetchall()
        conn.close()
        return jsonify({"audiences": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/audiences", methods=["POST"])
@login_required
def audiences_criar():
    d = request.get_json() or {}
    for f in ("nome", "account_id", "token_key", "targeting_json"):
        if not d.get(f):
            return jsonify({"error": f"Campo obrigatório: {f}"}), 400
    if d.get("token_key") not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    tipo = d.get("tipo", "manual")
    if tipo not in ("manual", "salvo_meta", "custom_meta"):
        return jsonify({"error": "tipo inválido"}), 400
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO ad_audiences (nome, account_id, token_key, tipo, targeting_json, meta_audience_id)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (
            d["nome"], d["account_id"], d["token_key"], tipo,
            json.dumps(d["targeting_json"]), d.get("meta_audience_id")
        ))
        novo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "id": novo_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/audiences/<int:aid>", methods=["PUT"])
@login_required
def audiences_atualizar(aid):
    d = request.get_json() or {}
    campos, valores = [], []
    if "nome" in d:
        campos.append("nome = %s"); valores.append(d["nome"])
    if "targeting_json" in d:
        # Não permite editar targeting de custom_meta
        conn = _get_db(); cur = conn.cursor()
        cur.execute("SELECT tipo FROM ad_audiences WHERE id=%s", (aid,))
        row = cur.fetchone(); conn.close()
        if row and row["tipo"] == "custom_meta":
            return jsonify({"error": "custom_meta: apenas nome pode ser editado"}), 400
        campos.append("targeting_json = %s"); valores.append(json.dumps(d["targeting_json"]))
    if not campos:
        return jsonify({"error": "Nenhum campo para atualizar"}), 400
    valores.append(aid)
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute(f"UPDATE ad_audiences SET {', '.join(campos)} WHERE id=%s", valores)
        conn.commit(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/audiences/<int:aid>", methods=["DELETE"])
@login_required
def audiences_deletar(aid):
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM ad_audiences WHERE id=%s", (aid,))
        conn.commit(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 2: Verificar sintaxe do app.py**

```bash
/root/jake_desktop/venv/bin/python3 -c "import py_compile; py_compile.compile('/root/jake_desktop/app.py'); print('OK')"
```

Esperado: `OK` sem erros.

- [ ] **Step 3: Commit**

```bash
cd /root && git add jake_desktop/app.py && git commit -m "feat(anuncios): rotas CRUD /api/anuncios/audiences"
```

---

## Task 4: Backend — rota de importação do Meta

**Files:**
- Modify: `/root/jake_desktop/app.py`

- [ ] **Step 1: Adicionar rota `/api/anuncios/audiences/importar`**

Inserir após a rota `audiences_deletar` (antes do bloco Meta API existente):

```python
@app.route("/api/anuncios/audiences/importar", methods=["POST"])
@login_required
def audiences_importar():
    d = request.get_json() or {}
    account_id = d.get("account_id", "").strip()
    token_key  = d.get("token_key", "").strip()
    if not account_id or not token_key:
        return jsonify({"error": "account_id e token_key obrigatórios"}), 400
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    importados = atualizados = 0
    erros = []

    def _upsert(nome, tipo, targeting_j, meta_id):
        nonlocal importados, atualizados
        try:
            conn = _get_db(); cur = conn.cursor()
            cur.execute("SELECT id FROM ad_audiences WHERE account_id=%s AND meta_audience_id=%s",
                        (account_id, meta_id))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE ad_audiences SET nome=%s, targeting_json=%s WHERE id=%s",
                            (nome, json.dumps(targeting_j), row["id"]))
                atualizados += 1
            else:
                cur.execute("""
                    INSERT INTO ad_audiences (nome, account_id, token_key, tipo, targeting_json, meta_audience_id)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (nome, account_id, token_key, tipo, json.dumps(targeting_j), meta_id))
                importados += 1
            conn.commit(); conn.close()
        except Exception as e:
            erros.append(f"{nome}: {e}")

    # Saved audiences
    try:
        salvos = _meta_api.listar_publicos_salvos(token, account_id)
        for s in salvos:
            t = s.get("targeting") or {}
            geo = t.get("geo_locations") or {}
            targeting_j = {
                "age_min":   t.get("age_min", 18),
                "age_max":   t.get("age_max", 65),
                "genders":   t.get("genders", []),
                "countries": geo.get("countries", []),
                "cities":    [c.get("name", "") for c in geo.get("cities", [])],
            }
            _upsert(s["name"], "salvo_meta", targeting_j, s["id"])
    except Exception as e:
        erros.append(f"saved_audiences: {e}")

    # Custom audiences
    try:
        customs = _meta_api.listar_custom_audiences(token, account_id)
        for c in customs:
            targeting_j = {"custom_audience_id": c["id"]}
            _upsert(f"{c['name']} ({c.get('subtype','?')})", "custom_meta", targeting_j, c["id"])
    except Exception as e:
        erros.append(f"custom_audiences: {e}")

    return jsonify({"ok": True, "importados": importados, "atualizados": atualizados, "erros": erros})
```

- [ ] **Step 2: Verificar sintaxe**

```bash
/root/jake_desktop/venv/bin/python3 -c "import py_compile; py_compile.compile('/root/jake_desktop/app.py'); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd /root && git add jake_desktop/app.py && git commit -m "feat(anuncios): rota /api/anuncios/audiences/importar"
```

---

## Task 5: Backend — modificar `/api/anuncios/publicar` para aceitar `audience_id`

**Files:**
- Modify: `/root/jake_desktop/app.py` (função `anuncios_publicar`)

- [ ] **Step 1: Localizar e modificar a montagem do targeting em `anuncios_publicar`**

Na função `anuncios_publicar`, localizar onde `publico` é usado (atualmente vem de `cliente.get("publico_json") or {}`). Adicionar lógica de `audience_id` logo após a leitura do cliente:

Localizar este trecho:
```python
    publico    = cliente.get("publico_json") or {}
```

Substituir por:
```python
    audience_id = d.get("audience_id")
    publico    = cliente.get("publico_json") or {}
    _audience_tipo = None
    if audience_id:
        try:
            conn2 = _get_db(); cur2 = conn2.cursor()
            cur2.execute("SELECT targeting_json, tipo FROM ad_audiences WHERE id=%s", (audience_id,))
            aud_row = cur2.fetchone(); conn2.close()
            if aud_row:
                publico = aud_row["targeting_json"] or {}
                _audience_tipo = aud_row["tipo"]
        except Exception:
            pass
```

- [ ] **Step 2: Ajustar montagem do targeting em `criar_conjunto` para custom_meta e novas chaves**

O `publico` agora pode vir de duas fontes com chaves diferentes:
- `publico_json` legado (cliente): usa `idade_min`, `idade_max`, `genero`
- `targeting_json` de `ad_audiences`: usa `age_min`, `age_max`, `genders`, `custom_audience_id`

Em `meta/meta_api.py`, na função `criar_conjunto`, localizar:
```python
    targeting = {
        "age_min": publico.get("idade_min", 18),
        "age_max": publico.get("idade_max", 65),
        "geo_locations": {
            "countries": localizacao.get("paises", ["BR"]),
            "cities": localizacao.get("cidades", []),
        }
    }
    if publico.get("genero"):
        targeting["genders"] = publico["genero"]
```

Substituir por:
```python
    targeting = {
        "age_min": publico.get("idade_min") or publico.get("age_min", 18),
        "age_max": publico.get("idade_max") or publico.get("age_max", 65),
        "geo_locations": {
            "countries": localizacao.get("paises", ["BR"]),
            "cities": localizacao.get("cidades", []),
        }
    }
    if publico.get("genders"):
        targeting["genders"] = publico["genders"]
    elif publico.get("genero"):
        targeting["genders"] = publico["genero"]
    if publico.get("custom_audience_id"):
        targeting["custom_audiences"] = [{"id": publico["custom_audience_id"]}]
```

- [ ] **Step 3: Registrar `audience_id` em `ad_publish_log`**

Na função `anuncios_publicar`, localizar o INSERT em `ad_publish_log`:

```python
            cur.execute("""
                INSERT INTO ad_publish_log
                    (cliente_id, account_id, campaign_id, adset_id, ad_id, status, payload_json)
                VALUES (%s,%s,%s,%s,%s,'sucesso',%s)
            """, (cliente_id, account_id, campaign_id, adset_id, ad_id, json.dumps(d)))
```

Substituir por:
```python
            cur.execute("""
                INSERT INTO ad_publish_log
                    (cliente_id, account_id, campaign_id, adset_id, ad_id, status, audience_id, payload_json)
                VALUES (%s,%s,%s,%s,%s,'sucesso',%s,%s)
            """, (cliente_id, account_id, campaign_id, adset_id, ad_id,
                  audience_id if audience_id else None, json.dumps(d)))
```

- [ ] **Step 4: Verificar sintaxe**

```bash
/root/jake_desktop/venv/bin/python3 -c "import py_compile; py_compile.compile('/root/jake_desktop/app.py'); print('OK')"
/root/venv/bin/python3 -c "import py_compile; py_compile.compile('/root/meta/meta_api.py'); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
cd /root && git add jake_desktop/app.py meta/meta_api.py && git commit -m "feat(anuncios): publicar aceita audience_id + suporte custom_meta targeting"
```

---

## Task 6: Frontend HTML — tab "Públicos" em Subir Anúncios

**Files:**
- Modify: `/root/jake_desktop/templates/dashboard.html`

A estrutura real de `anu-main` (linha ~511 de dashboard.html) contém em sequência: sub-nav (a adicionar), `anu-empty`, `anu-perfil-form`, `anu-criacao`. O `anu-criacao` fecha na linha ~630 com `</div>`, seguido de `</main>`.

- [ ] **Step 1: Adicionar sub-nav e envolver conteúdo existente em `anu-tab-publicar`**

Localizar exatamente em dashboard.html:
```
          <main class="anu-main">

            <div class="anu-empty-state" id="anu-empty">
```

Substituir por:
```html
          <main class="anu-main">

            <!-- Sub-navegação Anúncios -->
            <div style="display:flex;gap:8px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,0.08)">
              <button class="anu-btn-secondary anu-tab-btn active" data-tab="publicar" onclick="anuSwitchTab('publicar')" style="font-size:13px">Publicar</button>
              <button class="anu-btn-secondary anu-tab-btn" data-tab="publicos" onclick="anuSwitchTab('publicos')" style="font-size:13px">Públicos Salvos</button>
            </div>

            <!-- Tab: Publicar (conteúdo existente) -->
            <div id="anu-tab-publicar">

            <div class="anu-empty-state" id="anu-empty">
```

- [ ] **Step 2: Fechar `anu-tab-publicar` e adicionar tab Públicos antes de `</main>`**

Localizar exatamente (o fechamento de `anu-criacao` seguido de `</main>`):
```
            </div>

          </main>
```

Substituir por:
```html
            </div>

            </div><!-- /anu-tab-publicar -->

            <!-- Tab: Públicos Salvos -->
            <div id="anu-tab-publicos" style="display:none">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <span style="font-weight:600">Públicos Salvos</span>
                <div style="display:flex;gap:8px;">
                  <button class="anu-btn-secondary" id="anu-btn-importar-meta" style="font-size:13px">Importar do Meta</button>
                  <button class="anu-btn-secondary" id="anu-btn-novo-publico" style="font-size:13px">+ Novo Público</button>
                </div>
              </div>
              <div id="anu-publicos-lista"></div>

              <!-- Form novo/editar público -->
              <div id="anu-publico-form" class="anu-bloco hidden" style="margin-top:12px">
                <div id="anu-publico-form-titulo" style="font-weight:600;margin-bottom:12px">Novo Público</div>
                <label class="anu-label">Nome<input type="text" id="anu-pub-nome" class="anu-input" placeholder="Ex: Mulheres BR 25-45"></label>
                <label class="anu-label">Cliente<select id="anu-pub-cliente" class="anu-select"></select></label>
                <label class="anu-label">Idade mínima<input type="number" id="anu-pub-age-min" class="anu-input" value="18" min="13" max="65"></label>
                <label class="anu-label">Idade máxima<input type="number" id="anu-pub-age-max" class="anu-input" value="65" min="13" max="65"></label>
                <label class="anu-label">Gênero<select id="anu-pub-genero" class="anu-select">
                  <option value="">Todos</option>
                  <option value="1">Masculino</option>
                  <option value="2">Feminino</option>
                </select></label>
                <label class="anu-label">País<input type="text" id="anu-pub-pais" class="anu-input" value="BR" placeholder="BR"></label>
                <div style="display:flex;gap:8px;margin-top:12px;">
                  <button class="anu-btn-primary" id="anu-pub-salvar">Salvar</button>
                  <button class="anu-btn-secondary" id="anu-pub-cancelar">Cancelar</button>
                </div>
              </div>

              <!-- Modal importar do Meta -->
              <div id="anu-modal-importar" class="anu-bloco hidden" style="margin-top:12px">
                <div style="font-weight:600;margin-bottom:12px">Importar do Meta</div>
                <label class="anu-label">Cliente<select id="anu-imp-cliente" class="anu-select"></select></label>
                <div style="display:flex;gap:8px;margin-top:12px;">
                  <button class="anu-btn-primary" id="anu-imp-confirmar">Importar</button>
                  <button class="anu-btn-secondary" id="anu-imp-cancelar">Cancelar</button>
                </div>
                <div id="anu-imp-resultado" style="margin-top:8px;font-size:13px"></div>
              </div>
            </div><!-- /anu-tab-publicos -->

          </main>
```

- [ ] **Step 3: Adicionar seletor de público no Bloco 4 (Revisão Final)**

Localizar exatamente em dashboard.html:
```
                <div class="anu-revisao-grid" id="anu-revisao-grid"></div>
```

Substituir por:
```html
                <div class="anu-revisao-grid" id="anu-revisao-grid"></div>
                <label class="anu-label" style="margin-bottom:12px">Público
                  <select id="anu-pub-selector" class="anu-select">
                    <option value="">Usar perfil do cliente</option>
                  </select>
                  <span class="anu-hint">Opcional — sobrescreve o público do perfil do cliente</span>
                </label>
```

- [ ] **Step 4: Verificar HTML**

```bash
grep -c "anu-tab-publicar\|anu-tab-publicos\|anu-pub-selector\|anu-btn-importar-meta" /root/jake_desktop/templates/dashboard.html
```

Esperado: 4.

- [ ] **Step 5 (REMOVIDO — era redundante)**

Avançar direto para o commit no Step 5 abaixo.

- [ ] **Step SKIP: Adicionar sub-navegação tabs (era step 2 anterior — substituído acima)**

O HTML a adicionar era:

```html
<!-- Sub-navegação Anúncios -->
<div class="anu-subnav" style="display:flex;gap:8px;margin-bottom:16px;">
  <button class="anu-tab-btn active" data-tab="clientes" onclick="anuSwitchTab('clientes')">Clientes</button>
  <button class="anu-tab-btn" data-tab="publicos" onclick="anuSwitchTab('publicos')">Públicos</button>
</div>

<!-- Tab Públicos -->
<div id="anu-tab-publicos" style="display:none">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
    <span style="font-weight:600">Públicos Salvos</span>
    <div style="display:flex;gap:8px;">
      <button class="anu-btn-sec" id="anu-btn-importar-meta">Importar do Meta</button>
      <button class="anu-btn-sec" id="anu-btn-novo-publico">+ Novo Público</button>
    </div>
  </div>
  <div id="anu-publicos-lista"></div>

  <!-- Form novo/editar público -->
  <div id="anu-publico-form" style="display:none" class="anu-card">
    <div id="anu-publico-form-titulo" style="font-weight:600;margin-bottom:12px">Novo Público</div>
    <label class="anu-label">Nome<input type="text" id="anu-pub-nome" class="anu-input" placeholder="Ex: Mulheres BR 25-45"></label>
    <label class="anu-label">Cliente<select id="anu-pub-cliente" class="anu-select"></select></label>
    <label class="anu-label">Idade mínima<input type="number" id="anu-pub-age-min" class="anu-input" value="18" min="13" max="65"></label>
    <label class="anu-label">Idade máxima<input type="number" id="anu-pub-age-max" class="anu-input" value="65" min="13" max="65"></label>
    <label class="anu-label">Gênero<select id="anu-pub-genero" class="anu-select">
      <option value="">Todos</option>
      <option value="1">Masculino</option>
      <option value="2">Feminino</option>
    </select></label>
    <label class="anu-label">País<input type="text" id="anu-pub-pais" class="anu-input" value="BR" placeholder="BR"></label>
    <div style="display:flex;gap:8px;margin-top:12px;">
      <button class="anu-btn" id="anu-pub-salvar">Salvar</button>
      <button class="anu-btn-sec" id="anu-pub-cancelar">Cancelar</button>
    </div>
  </div>

  <!-- Modal importar do Meta -->
  <div id="anu-modal-importar" style="display:none" class="anu-card">
    <div style="font-weight:600;margin-bottom:12px">Importar do Meta</div>
    <label class="anu-label">Cliente<select id="anu-imp-cliente" class="anu-select"></select></label>
    <div style="display:flex;gap:8px;margin-top:12px;">
      <button class="anu-btn" id="anu-imp-confirmar">Importar</button>
      <button class="anu-btn-sec" id="anu-imp-cancelar">Cancelar</button>
    </div>
    <div id="anu-imp-resultado" style="margin-top:8px;font-size:13px"></div>
  </div>
</div>
```

- [ ] **Step 3: Adicionar dropdown de público na tela de Publicar**

Localizar o formulário de publicação (onde ficam campanha, criativo, copy). Adicionar antes do botão de publicar:

```html
<label class="anu-label">Público
  <select id="anu-pub-selector" class="anu-select">
    <option value="">Usar perfil do cliente</option>
  </select>
  <span class="anu-hint">Selecione um público salvo ou use o configurado no perfil do cliente</span>
</label>
```

- [ ] **Step 4: Verificar HTML válido**

```bash
grep -c "anu-tab-publicos\|anu-pub-selector\|anu-btn-importar-meta" /root/jake_desktop/templates/dashboard.html
```

Esperado: 3 ou mais ocorrências.

- [ ] **Step 5: Commit**

```bash
cd /root && git add jake_desktop/templates/dashboard.html && git commit -m "feat(frontend): tab Públicos + seletor de público no form de publicar"
```

---

## Task 7: Frontend JS — lógica de públicos

**Files:**
- Modify: `/root/jake_desktop/static/js/anuncios.js`

- [ ] **Step 1: Adicionar função `anuSwitchTab`**

No início do módulo JS (dentro do IIFE ou escopo principal), adicionar:

```javascript
  // ── Sub-navegação tabs ──────────────────────────────────────────────
  window.anuSwitchTab = function(tab) {
    ['clientes','publicos'].forEach(function(t) {
      var el = document.getElementById('anu-tab-' + t);
      var btn = document.querySelector('[data-tab="' + t + '"]');
      if (el) el.style.display = t === tab ? '' : 'none';
      if (btn) btn.classList.toggle('active', t === tab);
    });
    if (tab === 'publicos') carregarPublicos();
  };
```

- [ ] **Step 2: Adicionar funções de gerenciamento de públicos**

```javascript
  // ── Públicos Salvos ─────────────────────────────────────────────────
  var _publicos = [];
  var _pubEditId = null;

  function carregarPublicos() {
    var accountId = _clienteAtivo ? _clienteAtivo.account_id : '';
    var url = '/api/anuncios/audiences' + (accountId ? '?account_id=' + accountId : '');
    fetch(url).then(function(r){return r.json();}).then(function(d){
      _publicos = d.audiences || [];
      renderPublicos();
      popularSeletorPublico();
    });
  }

  function renderPublicos() {
    var el = document.getElementById('anu-publicos-lista');
    if (!el) return;
    if (!_publicos.length) { el.innerHTML = '<div style="color:#888;font-size:13px">Nenhum público salvo. Importe do Meta ou crie manualmente.</div>'; return; }
    var tipoBadge = {'manual':'Manual','salvo_meta':'Meta Salvo','custom_meta':'Custom'};
    el.innerHTML = _publicos.map(function(p){
      var editBtn = p.tipo !== 'custom_meta'
        ? '<button class="anu-btn-sec" style="padding:2px 8px;font-size:12px" onclick="abrirEditPublico('+p.id+')">Editar</button>'
        : '<button class="anu-btn-sec" style="padding:2px 8px;font-size:12px" onclick="abrirEditPublicoNome('+p.id+')">Renomear</button>';
      return '<div class="anu-card" style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;margin-bottom:6px">'
        + '<div><strong>'+_esc(p.nome)+'</strong> <span style="font-size:11px;color:#888;margin-left:6px">['+tipoBadge[p.tipo]+'] '+_esc(p.account_id)+'</span></div>'
        + '<div style="display:flex;gap:6px;">'+editBtn
        + '<button class="anu-btn-sec" style="padding:2px 8px;font-size:12px;color:#e55" onclick="deletarPublico('+p.id+')">X</button>'
        + '</div></div>';
    }).join('');
  }

  window.abrirEditPublico = function(id) {
    var p = _publicos.find(function(x){return x.id===id;});
    if (!p) return;
    _pubEditId = id;
    _set('anu-pub-nome', p.nome);
    _set('anu-pub-age-min', (p.targeting_json||{}).age_min||18);
    _set('anu-pub-age-max', (p.targeting_json||{}).age_max||65);
    _set('anu-pub-genero', ((p.targeting_json||{}).genders||[])[0]||'');
    _set('anu-pub-pais', ((p.targeting_json||{}).countries||[])[0]||'BR');
    _setText('anu-publico-form-titulo','Editar Público');
    mostrar('anu-publico-form');
  };

  window.abrirEditPublicoNome = function(id) {
    var p = _publicos.find(function(x){return x.id===id;});
    if (!p) return;
    _pubEditId = id;
    _set('anu-pub-nome', p.nome);
    _setText('anu-publico-form-titulo','Renomear Público');
    mostrar('anu-publico-form');
  };

  window.deletarPublico = function(id) {
    if (!confirm('Deletar este público?')) return;
    fetch('/api/anuncios/audiences/'+id, {method:'DELETE'})
      .then(function(r){return r.json();})
      .then(function(d){ if (d.ok) carregarPublicos(); else alert('Erro: '+d.error); });
  };

  function popularClientesDropdowns() {
    ['anu-pub-cliente','anu-imp-cliente'].forEach(function(selId){
      var sel = document.getElementById(selId);
      if (!sel) return;
      sel.innerHTML = '<option value="">— selecione —</option>';
      _clientes.forEach(function(c){
        var opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = c.nome + ' (' + c.account_id + ')';
        opt.dataset.accountId = c.account_id;
        opt.dataset.tokenKey = c.token_key;
        sel.appendChild(opt);
      });
    });
  }

  function popularSeletorPublico() {
    var sel = document.getElementById('anu-pub-selector');
    if (!sel) return;
    sel.innerHTML = '<option value="">Usar perfil do cliente</option>';
    _publicos.forEach(function(p){
      var opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.nome;
      sel.appendChild(opt);
    });
  }

  function bindPublicosEvents() {
    var btnNovo = document.getElementById('anu-btn-novo-publico');
    if (btnNovo) btnNovo.addEventListener('click', function(){
      _pubEditId = null;
      ['anu-pub-nome','anu-pub-age-min','anu-pub-age-max','anu-pub-pais'].forEach(function(id){
        var el=document.getElementById(id); if(el){if(id==='anu-pub-age-min')el.value='18';else if(id==='anu-pub-age-max')el.value='65';else if(id==='anu-pub-pais')el.value='BR';else el.value='';}
      });
      _setText('anu-publico-form-titulo','Novo Público');
      popularClientesDropdowns();
      mostrar('anu-publico-form');
    });

    var btnSalvar = document.getElementById('anu-pub-salvar');
    if (btnSalvar) btnSalvar.addEventListener('click', function(){
      var nome = _val('anu-pub-nome').trim();
      if (!nome) { alert('Nome obrigatório'); return; }
      var generoVal = _val('anu-pub-genero');
      var targeting = {
        age_min: parseInt(_val('anu-pub-age-min'))||18,
        age_max: parseInt(_val('anu-pub-age-max'))||65,
        genders: generoVal ? [parseInt(generoVal)] : [],
        countries: [_val('anu-pub-pais').trim()||'BR'],
      };
      if (_pubEditId) {
        var payload = {nome: nome};
        if (document.getElementById('anu-pub-age-min')) payload.targeting_json = targeting;
        fetch('/api/anuncios/audiences/'+_pubEditId, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
          .then(function(r){return r.json();})
          .then(function(d){ if(d.ok){esconder('anu-publico-form');carregarPublicos();}else alert('Erro: '+d.error); });
      } else {
        var sel = document.getElementById('anu-pub-cliente');
        var opt = sel ? sel.options[sel.selectedIndex] : null;
        if (!opt || !opt.dataset.accountId) { alert('Selecione um cliente'); return; }
        fetch('/api/anuncios/audiences',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
          nome: nome, account_id: opt.dataset.accountId, token_key: opt.dataset.tokenKey,
          tipo: 'manual', targeting_json: targeting
        })}).then(function(r){return r.json();})
          .then(function(d){ if(d.ok){esconder('anu-publico-form');carregarPublicos();}else alert('Erro: '+d.error); });
      }
    });

    var btnCancelar = document.getElementById('anu-pub-cancelar');
    if (btnCancelar) btnCancelar.addEventListener('click', function(){ esconder('anu-publico-form'); });

    var btnImportar = document.getElementById('anu-btn-importar-meta');
    if (btnImportar) btnImportar.addEventListener('click', function(){
      popularClientesDropdowns();
      _set('anu-imp-resultado','');
      mostrar('anu-modal-importar');
    });

    var btnImpConfirmar = document.getElementById('anu-imp-confirmar');
    if (btnImpConfirmar) btnImpConfirmar.addEventListener('click', function(){
      var sel = document.getElementById('anu-imp-cliente');
      var opt = sel ? sel.options[sel.selectedIndex] : null;
      if (!opt || !opt.dataset.accountId) { alert('Selecione um cliente'); return; }
      btnImpConfirmar.textContent = 'Importando...';
      fetch('/api/anuncios/audiences/importar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        account_id: opt.dataset.accountId, token_key: opt.dataset.tokenKey
      })}).then(function(r){return r.json();})
        .then(function(d){
          btnImpConfirmar.textContent = 'Importar';
          var res = document.getElementById('anu-imp-resultado');
          if (d.ok) {
            if (res) res.textContent = 'Importados: '+d.importados+' | Atualizados: '+d.atualizados+(d.erros.length?' | Erros: '+d.erros.join('; '):'');
            carregarPublicos();
          } else { alert('Erro: '+d.error); }
        });
    });

    var btnImpCancelar = document.getElementById('anu-imp-cancelar');
    if (btnImpCancelar) btnImpCancelar.addEventListener('click', function(){ esconder('anu-modal-importar'); });
  }
```

- [ ] **Step 3: Chamar `bindPublicosEvents()` e `popularClientesDropdowns()` na inicialização**

Localizar onde `bindPerfilFormEvents()` é chamado (na função de init da aba) e adicionar chamada a `bindPublicosEvents()` logo após.

- [ ] **Step 4: Passar `audience_id` no payload de publicar**

Localizar a função que monta o payload do publicar (onde `campanha_nome`, `creative_ref`, `copy` são enviados). Adicionar:

```javascript
audience_id: parseInt(_val('anu-pub-selector')) || null,
```

- [ ] **Step 5: Reiniciar Jake OS e testar manualmente**

```bash
kill $(ps aux | grep "jake_desktop/venv/bin/python app.py" | grep -v grep | awk '{print $2}') 2>/dev/null
lsof -ti:5050 | xargs kill -9 2>/dev/null
sleep 1
nohup /root/jake_desktop/venv/bin/python app.py > /tmp/jakeos.log 2>&1 &
sleep 4 && cat /tmp/jakeos.log
```

**Teste manual:**
1. Abrir Jake OS → aba Subir Anúncios
2. Clicar na tab "Públicos"
3. Clicar "Importar do Meta" → selecionar Vielife → clicar Importar
4. Verificar que públicos aparecem na lista
5. Clicar "+ Novo Público" → preencher → salvar
6. Ir em Publicar → verificar dropdown "Selecionar Público"

- [ ] **Step 6: Commit final**

```bash
cd /root && git add jake_desktop/static/js/anuncios.js && git commit -m "feat(frontend): gerenciamento de públicos salvos + seletor no publicar"
```
