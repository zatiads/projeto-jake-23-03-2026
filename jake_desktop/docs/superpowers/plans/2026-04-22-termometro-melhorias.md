# Termômetro Melhorias Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar tooltip enriquecido (patrimônio + aporte do mês + renda projetada) ao gráfico de evolução do Termômetro, e permitir ao usuário criar/deletar ativos customizáveis além dos 5 fixos.

**Architecture:** Feature 1 é puramente JS (`_renderTermoEvolucao` em `financeiro.js`). Feature 2 adiciona tabela `ativos_personalizados` no PostgreSQL, 3 rotas Flask novas, seção HTML de gerenciamento, CSS e JS dinâmico (ATIVOS_CARTEIRA deixa de ser hardcoded). A validação do POST aportes é expandida para aceitar ativos customizados.

**Tech Stack:** Flask + psycopg2 (Neon/PostgreSQL), Vanilla JS ES5, Chart.js, CSS glassmorphism dark.

---

## File Map

| Arquivo | Ação | O que muda |
|---|---|---|
| `jake_desktop/app.py` | Modify | `_init_ativos_personalizados_table()` + 3 rotas `/api/financeiro/ativos` + `financeiro_criar_aporte` aceita ativos customizados |
| `jake_desktop/tests/test_financeiro_api.py` | Modify | Testes para as 3 novas rotas + teste do ativo customizado aceito no POST aporte |
| `jake_desktop/templates/dashboard.html` | Modify | Seção "Gerenciar Ativos" abaixo da tabela de aportes |
| `jake_desktop/static/css/dashboard.css` | Modify | Estilos `.mil-gerenciar-*` e `.mil-novo-ativo-*` |
| `jake_desktop/static/js/financeiro.js` | Modify | `carregarAtivos()`, `_popularSelectAtivos()`, `renderAtivos()`, `adicionarAtivo()`, `deletarAtivo()`, refatoração de `ATIVOS_CARTEIRA` + tooltip de `_renderTermoEvolucao()` |

---

## Task 1: DB init — tabela ativos_personalizados

**Files:**
- Modify: `jake_desktop/app.py` (após `_init_aportes_table()` ~linha 318, e startup ~linha 5981)
- Modify: `jake_desktop/tests/test_financeiro_api.py`

- [ ] **Step 1: Escrever o teste**

Adicionar ao final de `test_financeiro_api.py`:

```python
# ── _init_ativos_personalizados_table ────────────────────────────────────────

def test_init_ativos_personalizados_table(client):
    conn_mock = _mock_conn()
    with patch("app._get_db", return_value=conn_mock):
        import app as flask_app
        flask_app._init_ativos_personalizados_table()
    conn_mock.cursor().execute.assert_called()
    conn_mock.commit.assert_called_once()
    conn_mock.close.assert_called_once()
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
cd /root/jake_desktop && /root/jake_desktop/.venv/bin/python -m pytest tests/test_financeiro_api.py::test_init_ativos_personalizados_table -v 2>&1 | tail -10
```
Esperado: `FAILED — AttributeError: module 'app' has no attribute '_init_ativos_personalizados_table'`

- [ ] **Step 3: Implementar `_init_ativos_personalizados_table()` em `app.py`**

Inserir logo após `_init_aportes_table()` (buscar com grep por `def _init_aportes_table`):

```python
def _init_ativos_personalizados_table():
    """Cria tabela de ativos personalizados se não existir."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ativos_personalizados (
                id SERIAL PRIMARY KEY,
                key VARCHAR(50) UNIQUE NOT NULL,
                label VARCHAR(100) NOT NULL,
                cor VARCHAR(20) NOT NULL,
                meta NUMERIC(5,2) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Registrar no startup**

Na sequência de startup (buscar `_init_aportes_table()` no final do arquivo, ~linha 5981), adicionar logo depois:

```python
    _init_ativos_personalizados_table()
```

- [ ] **Step 5: Rodar e confirmar PASS**

```bash
cd /root/jake_desktop && /root/jake_desktop/.venv/bin/python -m pytest tests/test_financeiro_api.py::test_init_ativos_personalizados_table -v 2>&1 | tail -10
```

- [ ] **Step 6: Commit**

```bash
cd /root/jake_desktop && git add app.py tests/test_financeiro_api.py
git commit -m "feat(financeiro): _init_ativos_personalizados_table"
```

---

## Task 2: API routes GET/POST/DELETE /api/financeiro/ativos + aportes aceita custom

**Files:**
- Modify: `jake_desktop/app.py` (após a seção `# ── Financeiro: Aportes de Investimento`, ~linha 2349)
- Modify: `jake_desktop/tests/test_financeiro_api.py`

### Constantes necessárias

```python
_ATIVOS_FIXOS = [
    {"key": "tesouro_selic", "label": "Tesouro Selic", "cor": "#00e5ff", "meta": 30},
    {"key": "cdb",           "label": "CDB",           "cor": "#ffd740", "meta": 25},
    {"key": "lci_lca",       "label": "LCI/LCA",       "cor": "#69f0ae", "meta": 15},
    {"key": "ivvb11",        "label": "IVVB11",         "cor": "#ff5252", "meta": 20},
    {"key": "gold11",        "label": "GOLD11",         "cor": "#7c4dff", "meta": 10},
]
_KEYS_FIXAS = {a["key"] for a in _ATIVOS_FIXOS}
_PALETA_CUSTOM = ['#ff8a65', '#ce93d8', '#80deea', '#a5d6a7', '#ffcc02', '#ef9a9a']
```

### Helper de key

```python
import re as _re

def _gerar_key_ativo(label):
    """Gera key única a partir do label: custom_<slug>, máx 50 chars."""
    slug = _re.sub(r'[^a-z0-9 ]', '', label.lower().strip())
    slug = _re.sub(r'\s+', '_', slug).strip('_')
    return ('custom_' + slug)[:50]
```

- [ ] **Step 1: Escrever os testes**

Adicionar ao final de `test_financeiro_api.py`:

```python
# ── GET /api/financeiro/ativos ───────────────────────────────────────────────

def test_listar_ativos_retorna_fixos_e_custom(client):
    rows = [{"id": 1, "key": "custom_fii", "label": "FII XP", "cor": "#ff8a65", "meta": 5.0}]
    with patch("app._get_db", return_value=_mock_conn(rows=rows)):
        resp = client.get("/api/financeiro/ativos")
    assert resp.status_code == 200
    data = resp.get_json()
    keys = [a["key"] for a in data]
    assert "tesouro_selic" in keys   # fixo sempre presente
    assert "custom_fii" in keys      # custom do mock
    assert data[0]["fixo"] is True   # fixos vêm primeiro


# ── POST /api/financeiro/ativos ──────────────────────────────────────────────

def test_criar_ativo_valido(client):
    conn_mock = _mock_conn(novo_id=1)
    # rowcount para simular que key não existe ainda (fetchone retorna None no SELECT)
    conn_mock.cursor.return_value.fetchone.return_value = None
    with patch("app._get_db", return_value=conn_mock):
        resp = client.post("/api/financeiro/ativos", json={"label": "FII XP", "meta": 5})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["ativo"]["key"] == "custom_fii_xp"
    assert data["ativo"]["fixo"] is False


def test_criar_ativo_sem_label(client):
    resp = client.post("/api/financeiro/ativos", json={"meta": 5})
    assert resp.status_code == 400


def test_criar_ativo_meta_invalida(client):
    resp = client.post("/api/financeiro/ativos", json={"label": "FII", "meta": 150})
    assert resp.status_code == 400


# ── DELETE /api/financeiro/ativos/<key> ──────────────────────────────────────

def test_deletar_ativo_custom(client):
    conn_mock = _mock_conn()
    conn_mock.cursor.return_value.rowcount = 1
    with patch("app._get_db", return_value=conn_mock):
        resp = client.delete("/api/financeiro/ativos/custom_fii")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_deletar_ativo_fixo_rejeitado(client):
    resp = client.delete("/api/financeiro/ativos/tesouro_selic")
    assert resp.status_code == 400


def test_deletar_ativo_inexistente(client):
    conn_mock = _mock_conn()
    conn_mock.cursor.return_value.rowcount = 0
    with patch("app._get_db", return_value=conn_mock):
        resp = client.delete("/api/financeiro/ativos/custom_xyz")
    assert resp.status_code == 404


# ── POST aporte aceita ativo customizado ─────────────────────────────────────

def test_criar_aporte_ativo_customizado(client):
    """POST /api/financeiro/aportes deve aceitar key de ativo customizado."""
    conn_mock = _mock_conn(novo_id=10)
    # mock: query verifica se custom_fii existe na tabela ativos_personalizados
    conn_mock.cursor.return_value.fetchone.return_value = {"key": "custom_fii"}
    with patch("app._get_db", return_value=conn_mock):
        resp = client.post("/api/financeiro/aportes", json={
            "mes_ano": "2026-04-01",
            "ativo": "custom_fii",
            "valor": 200.0
        })
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
cd /root/jake_desktop && /root/jake_desktop/.venv/bin/python -m pytest tests/test_financeiro_api.py -k "ativo" -v 2>&1 | tail -20
```
Esperado: todos FAILED (rotas não existem)

- [ ] **Step 3: Implementar as 3 rotas em `app.py`**

Inserir após o último route de aportes (~linha 2349):

```python
# ── Financeiro: Ativos Personalizados ────────────────────────────────────────

_ATIVOS_FIXOS = [
    {"key": "tesouro_selic", "label": "Tesouro Selic", "cor": "#00e5ff", "meta": 30},
    {"key": "cdb",           "label": "CDB",           "cor": "#ffd740", "meta": 25},
    {"key": "lci_lca",       "label": "LCI/LCA",       "cor": "#69f0ae", "meta": 15},
    {"key": "ivvb11",        "label": "IVVB11",         "cor": "#ff5252", "meta": 20},
    {"key": "gold11",        "label": "GOLD11",         "cor": "#7c4dff", "meta": 10},
]
_KEYS_FIXAS  = {a["key"] for a in _ATIVOS_FIXOS}
_PALETA_CUSTOM = ['#ff8a65', '#ce93d8', '#80deea', '#a5d6a7', '#ffcc02', '#ef9a9a']


def _gerar_key_ativo(label):
    import re
    slug = re.sub(r'[^a-z0-9 ]', '', label.lower().strip())
    slug = re.sub(r'\s+', '_', slug).strip('_')
    return ('custom_' + slug)[:50]


@app.route("/api/financeiro/ativos", methods=["GET"])
@login_required
def financeiro_listar_ativos():
    try:
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT key, label, cor, meta FROM ativos_personalizados ORDER BY id ASC")
            rows = cur.fetchall()
        finally:
            conn.close()
        result = [{**a, "fixo": True} for a in _ATIVOS_FIXOS]
        result += [{"key": r["key"], "label": r["label"], "cor": r["cor"],
                    "meta": float(r["meta"]), "fixo": False} for r in rows]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/ativos", methods=["POST"])
@login_required
def financeiro_criar_ativo():
    d     = request.get_json(force=True) or {}
    label = (d.get("label") or "").strip()
    if not label:
        return jsonify({"error": "label obrigatório"}), 400
    if len(label) > 100:
        return jsonify({"error": "label muito longo (máx 100)"}), 400
    try:
        meta = float(d.get("meta") or 0)
        if not (0 <= meta <= 100):
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "meta deve ser entre 0 e 100"}), 400
    key = _gerar_key_ativo(label)
    if key in _KEYS_FIXAS:
        return jsonify({"error": f"Ativo com nome similar já existe (key: {key})"}), 400
    try:
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS n FROM ativos_personalizados")
            n = cur.fetchone()["n"]
            cor = _PALETA_CUSTOM[int(n) % len(_PALETA_CUSTOM)]
            cur.execute("""
                INSERT INTO ativos_personalizados (key, label, cor, meta)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (key) DO NOTHING
                RETURNING id
            """, (key, label, cor, meta))
            row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()
        if not row:
            return jsonify({"error": f"Ativo com nome similar já existe (key: {key})"}), 400
        ativo = {"key": key, "label": label, "cor": cor, "meta": meta, "fixo": False}
        return jsonify({"ok": True, "ativo": ativo})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/ativos/<string:key>", methods=["DELETE"])
@login_required
def financeiro_deletar_ativo(key):
    if key in _KEYS_FIXAS:
        return jsonify({"error": "ativo fixo não pode ser removido"}), 400
    try:
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM ativos_personalizados WHERE key = %s", (key,))
            conn.commit()
            rowcount = cur.rowcount
        finally:
            conn.close()
        if rowcount == 0:
            return jsonify({"error": "not found"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 4: Atualizar `financeiro_criar_aporte` para aceitar ativos customizados**

Localizar a linha:
```python
if ativo not in _ATIVOS_VALIDOS:
    return jsonify({"error": f"ativo inválido: {ativo}"}), 400
```

Substituir por:
```python
if ativo not in _ATIVOS_VALIDOS and not ativo.startswith('custom_'):
    return jsonify({"error": f"ativo inválido: {ativo}"}), 400
if ativo.startswith('custom_'):
    try:
        _conn = _get_db()
        try:
            _cur = _conn.cursor()
            _cur.execute("SELECT key FROM ativos_personalizados WHERE key = %s", (ativo,))
            if not _cur.fetchone():
                return jsonify({"error": f"ativo inválido: {ativo}"}), 400
        finally:
            _conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 5: Rodar testes de ativos e confirmar PASS**

```bash
cd /root/jake_desktop && /root/jake_desktop/.venv/bin/python -m pytest tests/test_financeiro_api.py -k "ativo" -v 2>&1 | tail -20
```

- [ ] **Step 6: Suite completa sem regressão**

```bash
cd /root/jake_desktop && /root/jake_desktop/.venv/bin/python -m pytest tests/test_financeiro_api.py -v 2>&1 | tail -30
```

- [ ] **Step 7: Commit**

```bash
cd /root/jake_desktop && git add app.py tests/test_financeiro_api.py
git commit -m "feat(financeiro): rotas /api/financeiro/ativos (GET/POST/DELETE) + aporte aceita custom"
```

---

## Task 3: HTML — seção Gerenciar Ativos

**Files:**
- Modify: `jake_desktop/templates/dashboard.html` (linha 1717 — após `</table>` e antes de `</div><!-- /#mil-pane-aportes -->`)

- [ ] **Step 1: Localizar o ponto de inserção**

```bash
grep -n "mil-aporte-tbody\|mil-pane-aportes" /root/jake_desktop/templates/dashboard.html
```
Deve mostrar linha ~1716 para `</tbody>` e ~1718 para `<!-- /#mil-pane-aportes -->`.

- [ ] **Step 2: Inserir seção Gerenciar Ativos**

Localizar exatamente:
```html
            </div><!-- /#mil-pane-aportes -->
```

Substituir por:
```html
              <div class="mil-gerenciar-ativos">
                <div class="mil-gerenciar-header">
                  <span class="mil-gerenciar-titulo">Ativos da carteira</span>
                  <button id="mil-novo-ativo-btn" class="mil-novo-ativo-btn">+ Novo Ativo</button>
                </div>
                <div id="mil-novo-ativo-form" class="mil-novo-ativo-form hidden">
                  <input type="text" id="mil-ativo-label" class="mil-ativo-input" placeholder="Nome do ativo" maxlength="100">
                  <input type="number" id="mil-ativo-meta" class="mil-ativo-input" placeholder="Meta % (opcional)" min="0" max="100" step="0.1">
                  <button id="mil-ativo-submit" class="mil-ativo-submit-btn">Adicionar</button>
                  <button id="mil-ativo-cancel" class="mil-ativo-cancel-btn" type="button">Cancelar</button>
                  <div id="mil-ativo-status" class="mil-ativo-status"></div>
                </div>
                <div id="mil-ativos-lista" class="mil-ativos-lista">
                  <!-- populado via JS -->
                </div>
              </div>

            </div><!-- /#mil-pane-aportes -->
```

- [ ] **Step 3: Verificar estrutura**

```bash
grep -n "mil-gerenciar\|mil-novo-ativo\|mil-ativos-lista" /root/jake_desktop/templates/dashboard.html
```
Deve retornar ~8 linhas com os novos elementos.

- [ ] **Step 4: Commit**

```bash
cd /root/jake_desktop && git add templates/dashboard.html
git commit -m "feat(financeiro): HTML seção Gerenciar Ativos em #mil-pane-aportes"
```

---

## Task 4: CSS — estilos Gerenciar Ativos

**Files:**
- Modify: `jake_desktop/static/css/dashboard.css` (append ao final)

- [ ] **Step 1: Verificar fim do arquivo**

```bash
wc -l /root/jake_desktop/static/css/dashboard.css
```

- [ ] **Step 2: Adicionar CSS ao final**

```css
/* ── Gerenciar Ativos ──────────────────────────────────────────────────────── */
.mil-gerenciar-ativos {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid rgba(255,255,255,0.07);
}
.mil-gerenciar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.mil-gerenciar-titulo {
  font-size: 12px;
  color: #546e7a;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-family: 'Rajdhani', sans-serif;
}
.mil-novo-ativo-btn {
  background: transparent;
  border: 1px solid rgba(0,229,255,0.35);
  color: #00e5ff;
  padding: 4px 14px;
  border-radius: 16px;
  cursor: pointer;
  font-family: 'Rajdhani', sans-serif;
  font-size: 12px;
  transition: all 0.2s;
}
.mil-novo-ativo-btn:hover { background: rgba(0,229,255,0.1); }
.mil-novo-ativo-form {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
  padding: 12px 16px;
  background: rgba(0,229,255,0.04);
  border: 1px solid rgba(0,229,255,0.12);
  border-radius: 8px;
}
.mil-ativo-input {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.15);
  color: #e0e0e0;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
  font-family: 'Rajdhani', sans-serif;
}
.mil-ativo-input:focus { outline: none; border-color: #00e5ff; }
.mil-ativo-submit-btn {
  background: rgba(0,229,255,0.12);
  border: 1px solid #00e5ff;
  color: #00e5ff;
  border-radius: 6px;
  padding: 6px 16px;
  cursor: pointer;
  font-family: 'Rajdhani', sans-serif;
  font-size: 12px;
  transition: background 0.2s;
}
.mil-ativo-submit-btn:hover { background: rgba(0,229,255,0.22); }
.mil-ativo-cancel-btn {
  background: transparent;
  border: 1px solid rgba(255,255,255,0.15);
  color: #546e7a;
  border-radius: 6px;
  padding: 6px 12px;
  cursor: pointer;
  font-family: 'Rajdhani', sans-serif;
  font-size: 12px;
}
.mil-ativo-status { font-size: 11px; width: 100%; min-height: 14px; margin-top: 2px; }
.mil-ativos-lista {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.mil-ativo-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 16px;
  font-size: 12px;
  font-family: 'Rajdhani', sans-serif;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.1);
  color: #b0bec5;
}
.mil-ativo-chip-dot { font-size: 10px; }
.mil-ativo-chip-del {
  background: transparent;
  border: none;
  color: #ff525266;
  cursor: pointer;
  font-size: 12px;
  padding: 0 2px;
  line-height: 1;
  transition: color 0.15s;
}
.mil-ativo-chip-del:hover { color: #ff5252; }
```

- [ ] **Step 3: Confirmar**

```bash
grep -n "mil-gerenciar-ativos\|mil-ativo-chip" /root/jake_desktop/static/css/dashboard.css
```

- [ ] **Step 4: Commit**

```bash
cd /root/jake_desktop && git add static/css/dashboard.css
git commit -m "feat(financeiro): CSS Gerenciar Ativos"
```

---

## Task 5: JS — carregarAtivos, renderAtivos, CRUD customizados

**Files:**
- Modify: `jake_desktop/static/js/financeiro.js`

Esta task transforma `ATIVOS_CARTEIRA` de constante hardcoded para array dinâmico carregado da API, e adiciona toda a lógica de gerenciamento de ativos.

- [ ] **Step 1: Localizar pontos-chave**

```bash
grep -n "var ATIVOS_CARTEIRA\|carregarAportes();\|function carregarAportes\|initSubTabsMilhao" /root/jake_desktop/static/js/financeiro.js
```

- [ ] **Step 2: Mudar ATIVOS_CARTEIRA de constante para array vazio**

Localizar (linhas ~120–126):
```js
  var ATIVOS_CARTEIRA = [
    { key: 'tesouro_selic', label: 'Tesouro Selic', cor: '#00e5ff', meta: 30 },
    { key: 'cdb',           label: 'CDB',           cor: '#ffd740', meta: 25 },
    { key: 'lci_lca',       label: 'LCI/LCA',       cor: '#69f0ae', meta: 15 },
    { key: 'ivvb11',        label: 'IVVB11',         cor: '#ff5252', meta: 20 },
    { key: 'gold11',        label: 'GOLD11',         cor: '#7c4dff', meta: 10 },
  ];
```

Substituir por:
```js
  var ATIVOS_CARTEIRA = [];  // populado por carregarAtivos()
```

- [ ] **Step 3: Substituir `carregarAportes()` por `carregarAtivos()` em `initSubTabsMilhao`**

Localizar ao final de `initSubTabsMilhao()`:
```js
    carregarAportes();
  }
```

Substituir por:
```js
    carregarAtivos();
  }
```

- [ ] **Step 4: Adicionar `carregarAtivos()` após `initSubTabsMilhao()`**

Inserir após o fechamento de `initSubTabsMilhao()`, antes de `function carregarAportes()`:

```js
  function carregarAtivos() {
    fetch('/api/financeiro/ativos')
      .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function(data) {
        ATIVOS_CARTEIRA = data;
        _popularSelectAtivos();
        renderAtivos();
        carregarAportes();
      })
      .catch(function(e){ console.error('Erro ao carregar ativos:', e); });
  }

  function _popularSelectAtivos() {
    var sel = document.getElementById('mil-aporte-ativo');
    if (!sel) return;
    var valorAtual = sel.value;
    sel.innerHTML = ATIVOS_CARTEIRA.map(function(a) {
      return '<option value="' + a.key + '">' + a.label + '</option>';
    }).join('');
    // Preservar seleção se ainda existir
    if (ATIVOS_CARTEIRA.some(function(a){ return a.key === valorAtual; })) {
      sel.value = valorAtual;
    }
  }

  function renderAtivos() {
    var lista = document.getElementById('mil-ativos-lista');
    if (!lista) return;
    lista.innerHTML = ATIVOS_CARTEIRA.map(function(a) {
      var metaStr = a.meta > 0 ? ' <span style="color:#546e7a">(' + a.meta + '%)</span>' : '';
      var delBtn  = !a.fixo
        ? '<button class="mil-ativo-chip-del" data-key="' + a.key + '" title="Remover">✕</button>'
        : '';
      return '<span class="mil-ativo-chip">' +
        '<span class="mil-ativo-chip-dot" style="color:' + a.cor + '">●</span>' +
        a.label + metaStr + delBtn +
      '</span>';
    }).join('');

    lista.querySelectorAll('.mil-ativo-chip-del').forEach(function(btn) {
      btn.addEventListener('click', function() {
        deletarAtivo(this.dataset.key);
      });
    });

    // Bind "+ Novo Ativo" e form (idempotente via flag)
    _bindGerenciarAtivos();
  }

  var _gerenciarAtivosBound = false;
  function _bindGerenciarAtivos() {
    if (_gerenciarAtivosBound) return;
    _gerenciarAtivosBound = true;

    var btnNovo   = document.getElementById('mil-novo-ativo-btn');
    var formNovo  = document.getElementById('mil-novo-ativo-form');
    var btnCancel = document.getElementById('mil-ativo-cancel');
    var btnSubmit = document.getElementById('mil-ativo-submit');

    if (btnNovo)   btnNovo.addEventListener('click',   function(){ formNovo.classList.toggle('hidden'); });
    if (btnCancel) btnCancel.addEventListener('click', function(){ formNovo.classList.add('hidden'); });
    if (btnSubmit) btnSubmit.addEventListener('click', function() {
      var label = (document.getElementById('mil-ativo-label').value || '').trim();
      var meta  = parseFloat(document.getElementById('mil-ativo-meta').value) || 0;
      if (!label) return;
      adicionarAtivo(label, meta);
    });
  }

  function adicionarAtivo(label, meta) {
    var status = document.getElementById('mil-ativo-status');
    fetch('/api/financeiro/ativos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label: label, meta: meta })
    })
    .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function(res) {
      if (res.ok) {
        ATIVOS_CARTEIRA.push(res.ativo);
        _popularSelectAtivos();
        renderAtivos();
        renderTermometro();
        document.getElementById('mil-ativo-label').value = '';
        document.getElementById('mil-ativo-meta').value  = '';
        document.getElementById('mil-novo-ativo-form').classList.add('hidden');
        if (status) { status.textContent = '✓ Ativo adicionado'; status.style.color = '#69f0ae'; setTimeout(function(){ status.textContent = ''; }, 2000); }
      } else {
        if (status) { status.textContent = '⚠ ' + (res.error || 'Erro'); status.style.color = '#ff5252'; }
      }
    })
    .catch(function(e){
      if (status) { status.textContent = '⚠ Erro de conexão'; status.style.color = '#ff5252'; }
      console.error('adicionarAtivo erro:', e);
    });
  }

  function deletarAtivo(key) {
    fetch('/api/financeiro/ativos/' + key, { method: 'DELETE' })
      .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function(res) {
        if (res.ok) {
          ATIVOS_CARTEIRA = ATIVOS_CARTEIRA.filter(function(a){ return a.key !== key; });
          _popularSelectAtivos();
          renderAtivos();
          renderTermometro();
        }
      })
      .catch(function(e){ console.error('deletarAtivo erro:', e); });
  }
```

- [ ] **Step 5: Syntax check**

```bash
node --check /root/jake_desktop/static/js/financeiro.js 2>&1
echo "exit: $?"
```
Esperado: exit 0.

- [ ] **Step 6: Restart e confirmar início**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/venv/bin/python app.py > /tmp/jakeos.log 2>&1 &
sleep 3 && tail -5 /tmp/jakeos.log
```

- [ ] **Step 7: Commit**

```bash
cd /root/jake_desktop && git add static/js/financeiro.js
git commit -m "feat(financeiro): ATIVOS_CARTEIRA dinâmico + carregarAtivos + CRUD custom ativos JS"
```

---

## Task 6: JS — tooltip enriquecido em _renderTermoEvolucao

**Files:**
- Modify: `jake_desktop/static/js/financeiro.js`

- [ ] **Step 1: Localizar `_renderTermoEvolucao`**

```bash
grep -n "function _renderTermoEvolucao\|tooltip.*callbacks\|afterBody" /root/jake_desktop/static/js/financeiro.js
```

- [ ] **Step 2: Substituir o bloco `tooltip` dentro do chart de evolução**

Localizar exatamente:
```js
          tooltip: {
            callbacks: {
              label: function(ctx){ return ' Patrimônio: ' + fmt(ctx.raw); }
            }
          }
```

Substituir por:
```js
          tooltip: {
            callbacks: {
              label: function(ctx) {
                return ' Patrimônio: ' + fmt(ctx.raw);
              },
              afterBody: function(items) {
                var idx     = items[0].dataIndex;
                var mes     = meses[idx];
                var aporte  = porMes[mes] || 0;
                var elTaxa  = document.getElementById('mil-taxa');
                var taxa    = elTaxa ? parseFloat(elTaxa.value) / 100 : NaN;
                if (!taxa || taxa <= 0) taxa = 0.008;
                var patrimonio = dados[idx];
                var renda      = patrimonio * taxa;
                return [
                  ' Aporte do mês: ' + fmt(aporte),
                  ' Renda projetada: ' + fmt(renda) + '/mês'
                ];
              }
            }
          }
```

> **Nota:** `porMes`, `meses` e `dados` são variáveis locais de `_renderTermoEvolucao()` definidas antes da criação do Chart — o closure funciona corretamente.

- [ ] **Step 3: Syntax check**

```bash
node --check /root/jake_desktop/static/js/financeiro.js 2>&1
echo "exit: $?"
```

- [ ] **Step 4: Commit**

```bash
cd /root/jake_desktop && git add static/js/financeiro.js
git commit -m "feat(financeiro): tooltip enriquecido no gráfico de evolução (aporte + renda projetada)"
```

---

## Task 7: Restart + smoke test final

- [ ] **Step 1: Suite de testes completa**

```bash
cd /root/jake_desktop && /root/jake_desktop/.venv/bin/python -m pytest tests/test_financeiro_api.py -v 2>&1 | tail -35
```
Esperado: todos PASSED (inclui os novos).

- [ ] **Step 2: Reiniciar Jake OS limpo**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/venv/bin/python app.py > /tmp/jakeos.log 2>&1 &
sleep 3 && tail -8 /tmp/jakeos.log
```

- [ ] **Step 3: Smoke test via curl**

```bash
# Login
curl -s -c /tmp/cookies.txt -X POST http://localhost:5050/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@jakeos.local","password":"Jake@2024!"}' > /dev/null

# GET ativos — deve retornar 5 fixos
curl -s -b /tmp/cookies.txt http://localhost:5050/api/financeiro/ativos | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d), 'ativos, fixos:', sum(1 for a in d if a['fixo']))"

# POST ativo customizado
curl -s -b /tmp/cookies.txt -X POST http://localhost:5050/api/financeiro/ativos \
  -H "Content-Type: application/json" \
  -d '{"label":"FII XP","meta":5}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d)"

# GET ativos — deve retornar 6 (5 fixos + 1 custom)
curl -s -b /tmp/cookies.txt http://localhost:5050/api/financeiro/ativos | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d), 'ativos')"

# POST aporte com ativo customizado
curl -s -b /tmp/cookies.txt -X POST http://localhost:5050/api/financeiro/aportes \
  -H "Content-Type: application/json" \
  -d '{"mes_ano":"2026-04-01","ativo":"custom_fii_xp","valor":200}' | python3 -c "import sys,json; print(json.load(sys.stdin))"

# DELETE ativo fixo — deve retornar 400
curl -s -b /tmp/cookies.txt -X DELETE http://localhost:5050/api/financeiro/ativos/tesouro_selic | python3 -c "import sys,json; print(json.load(sys.stdin))"
```

- [ ] **Step 4: Verificar git log**

```bash
cd /root/jake_desktop && git log --oneline -8
```

---

## Dependências

```
Task 1 → Task 2 (tabela deve existir antes das rotas)
Task 2 → Task 5 (API deve existir antes do JS chamar)
Task 3 + Task 4 → Task 5 (HTML/CSS antes de ligar os eventos)
Task 6 — independente (só toca _renderTermoEvolucao, sem deps externas)
Task 7 — depende de tudo
```

Tasks 3, 4, 6 podem ser executadas em paralelo entre si (não tocam os mesmos trechos de código).
