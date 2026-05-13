# Carteira de Investimentos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar histórico de aportes por ativo e termômetro de patrimônio ao módulo Financeiro do Jake OS, dentro da aba Projeto Milhão como 3 sub-tabs (Simulador / Termômetro / Aportes).

**Architecture:** Nova tabela `aportes_investimento` no PostgreSQL (Neon), 3 rotas Flask novas em `app.py`, sub-tabs em `dashboard.html`, estilos em `dashboard.css`, funções JS em `financeiro.js`. O patrimônio é calculado dinamicamente pela soma dos aportes registrados.

**Tech Stack:** Flask + psycopg2 (Neon/PostgreSQL), Vanilla JS, Chart.js (já disponível), CSS glassmorphism dark theme.

---

## File Map

| Arquivo | Ação | O que muda |
|---|---|---|
| `jake_desktop/app.py` | Modify | `_init_aportes_table()` + 3 rotas novas + chamada no startup |
| `jake_desktop/templates/dashboard.html` | Modify | Wrap conteúdo existente de `#fin-pane-milhao` em sub-tab pane, adicionar sub-tab bar + 2 novos panes |
| `jake_desktop/static/css/dashboard.css` | Modify | Estilos `.mil-subtab-*`, `.mil-termo-*`, `.mil-aporte-*` |
| `jake_desktop/static/js/financeiro.js` | Modify | `APORTES`, `ATIVOS_CARTEIRA`, `initSubTabsMilhao()`, `carregarAportes()`, `renderTermometro()`, `renderAportes()`, `adicionarAporte()`, `deletarAporte()` |
| `jake_desktop/tests/test_financeiro_api.py` | Modify | Testes para as 3 novas rotas |

---

## Task 1: DB init function + startup

**Files:**
- Modify: `jake_desktop/app.py` (após `_init_dr_tables()` ~linha 266, e startup ~linha 5878)
- Modify: `jake_desktop/tests/test_financeiro_api.py`

- [ ] **Step 1: Escrever o teste de que a tabela é criada**

Adicionar ao final de `test_financeiro_api.py`:

```python
# ── _init_aportes_table ───────────────────────────────────────────────────────

def test_init_aportes_table_cria_tabela(client):
    conn_mock = _mock_conn()
    with patch("app._get_db", return_value=conn_mock):
        import app as flask_app
        flask_app._init_aportes_table()
    conn_mock.cursor().execute.assert_called()
    conn_mock.commit.assert_called_once()
    conn_mock.close.assert_called_once()
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_financeiro_api.py::test_init_aportes_table_cria_tabela -v
```
Esperado: `FAILED — AttributeError: module 'app' has no attribute '_init_aportes_table'`

- [ ] **Step 3: Implementar `_init_aportes_table()` em `app.py`**

Inserir logo após a função `_init_dr_tables()` (buscar com grep por `def _init_dr_tables`):

```python
def _init_aportes_table():
    """Cria tabela de aportes de investimento se não existir."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS aportes_investimento (
                id SERIAL PRIMARY KEY,
                mes_ano DATE NOT NULL,
                ativo VARCHAR(50) NOT NULL,
                valor NUMERIC(12,2) NOT NULL CHECK (valor > 0),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_aportes_mes_ano
            ON aportes_investimento(mes_ano)
        """)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Registrar no startup**

Na linha de startup (~linha 5878), após `_init_dr_tables()`:

```python
    _init_aportes_table()
```

- [ ] **Step 5: Rodar o teste e confirmar que passa**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_financeiro_api.py::test_init_aportes_table_cria_tabela -v
```
Esperado: `PASSED`

- [ ] **Step 6: Commit**

```bash
cd /root/jake_desktop && git add app.py tests/test_financeiro_api.py
git commit -m "feat(financeiro): _init_aportes_table — tabela aportes_investimento"
```

---

## Task 2: API routes — GET, POST, DELETE

**Files:**
- Modify: `jake_desktop/app.py` (após a seção `# ── Financeiro: CRUD Raio-X`, ~linha 2206)
- Modify: `jake_desktop/tests/test_financeiro_api.py`

- [ ] **Step 1: Escrever os 3 testes**

Adicionar ao final de `test_financeiro_api.py`:

```python
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
    conn_mock.cursor().rowcount = 1
    with patch("app._get_db", return_value=conn_mock):
        resp = client.delete("/api/financeiro/aportes/1")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_deletar_aporte_nao_existente(client):
    conn_mock = _mock_conn()
    conn_mock.cursor().rowcount = 0
    with patch("app._get_db", return_value=conn_mock):
        resp = client.delete("/api/financeiro/aportes/999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_financeiro_api.py -k "aporte" -v
```
Esperado: todos `FAILED — 404 Not Found` (rotas inexistentes)

- [ ] **Step 3: Implementar as 3 rotas em `app.py`**

Inserir após a seção `# ── Financeiro: CRUD Raio-X` (após a rota PUT /api/financeiro/raiox, buscar por `# ── Financeiro: CRUD Raio-X` e adicionar bloco novo ao final dessa seção):

```python
# ── Financeiro: Aportes de Investimento ──────────────────────────────────────

_ATIVOS_VALIDOS = {"tesouro_selic", "cdb", "lci_lca", "ivvb11", "gold11"}


@app.route("/api/financeiro/aportes", methods=["GET"])
@login_required
def financeiro_listar_aportes():
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, mes_ano::text, ativo, valor
            FROM aportes_investimento
            ORDER BY mes_ano DESC, id DESC
        """)
        rows = cur.fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/aportes", methods=["POST"])
@login_required
def financeiro_criar_aporte():
    d = request.get_json(force=True) or {}
    mes_ano = d.get("mes_ano")
    ativo   = d.get("ativo")
    valor   = d.get("valor")
    if not mes_ano:
        return jsonify({"error": "mes_ano obrigatório"}), 400
    if ativo not in _ATIVOS_VALIDOS:
        return jsonify({"error": f"ativo inválido: {ativo}"}), 400
    try:
        valor = float(valor)
        if valor <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "valor deve ser > 0"}), 400
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO aportes_investimento (mes_ano, ativo, valor)
            VALUES (DATE_TRUNC('month', %s::date), %s, %s)
            RETURNING id
        """, (mes_ano, ativo, valor))
        novo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "id": novo_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/aportes/<int:aid>", methods=["DELETE"])
@login_required
def financeiro_deletar_aporte(aid):
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("DELETE FROM aportes_investimento WHERE id = %s", (aid,))
        conn.commit()
        rowcount = cur.rowcount
        conn.close()
        if rowcount == 0:
            return jsonify({"error": "not found"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_financeiro_api.py -k "aporte" -v
```
Esperado: todos `PASSED`

- [ ] **Step 5: Rodar suite completa sem regressão**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_financeiro_api.py -v
```
Esperado: todos os testes existentes continuam `PASSED`

- [ ] **Step 6: Commit**

```bash
cd /root/jake_desktop && git add app.py tests/test_financeiro_api.py
git commit -m "feat(financeiro): 3 rotas /api/financeiro/aportes (GET/POST/DELETE)"
```

---

## Task 3: HTML — Sub-tabs + novos panes

**Files:**
- Modify: `jake_desktop/templates/dashboard.html` (linhas 1514–1636)

O objetivo é: envolver o conteúdo existente de `#fin-pane-milhao` num pane `#mil-pane-simulador`, e adicionar a barra de sub-tabs + panes `termometro` e `aportes`.

- [ ] **Step 1: Substituir a abertura de `#fin-pane-milhao`**

Localizar linha 1514:
```html
          <div class="fin-tab-pane" id="fin-pane-milhao">
```

Substituir por:
```html
          <div class="fin-tab-pane" id="fin-pane-milhao">

            <!-- Sub-tab bar -->
            <div class="mil-subtab-bar">
              <button class="mil-subtab-btn active" data-subtab="simulador">Simulador</button>
              <button class="mil-subtab-btn" data-subtab="termometro">Termômetro</button>
              <button class="mil-subtab-btn" data-subtab="aportes">Aportes</button>
            </div>

            <!-- Pane: Simulador (conteúdo existente) -->
            <div id="mil-pane-simulador" class="mil-subtab-pane active">
```

- [ ] **Step 2: Fechar o pane Simulador e adicionar panes novos**

Localizar linha 1636:
```html
          </div><!-- /#fin-pane-milhao -->
```

Substituir por:
```html
            </div><!-- /#mil-pane-simulador -->

            <!-- Pane: Termômetro -->
            <div id="mil-pane-termometro" class="mil-subtab-pane">
              <div id="mil-termo-patrimonio-wrap">
                <div class="mil-termo-valor" id="mil-termo-valor">R$ 0,00</div>
                <div class="mil-termo-label">patrimônio total investido</div>
                <div class="mil-termo-pct" id="mil-termo-pct">0,0% da meta R$ 1.000.000</div>
                <div class="mil-termo-barra-wrap">
                  <div class="mil-termo-barra-fill" id="mil-termo-barra-fill" style="width:0%"></div>
                </div>
              </div>
              <div id="mil-termo-body">
                <div class="mil-termo-charts-row">
                  <div class="mil-termo-donut-wrap">
                    <canvas id="mil-termo-donut"></canvas>
                  </div>
                  <div class="mil-termo-ativos-wrap" id="mil-termo-ativos-wrap">
                    <!-- barras por ativo renderizadas via JS -->
                  </div>
                </div>
                <div class="mil-termo-evolucao-wrap">
                  <canvas id="mil-termo-evolucao"></canvas>
                </div>
              </div>
              <div class="mil-termo-empty hidden" id="mil-termo-empty">
                Nenhum aporte registrado ainda. Vá à aba <strong>Aportes</strong> para começar.
              </div>
            </div><!-- /#mil-pane-termometro -->

            <!-- Pane: Aportes -->
            <div id="mil-pane-aportes" class="mil-subtab-pane">
              <form id="mil-aporte-form" class="mil-aporte-form">
                <div class="mil-aporte-form-row">
                  <div class="mil-aporte-field">
                    <label class="mil-aporte-label">Mês/Ano</label>
                    <input type="month" id="mil-aporte-mes" class="mil-aporte-input" required>
                  </div>
                  <div class="mil-aporte-field">
                    <label class="mil-aporte-label">Ativo</label>
                    <select id="mil-aporte-ativo" class="mil-aporte-input">
                      <option value="tesouro_selic">Tesouro Selic</option>
                      <option value="cdb">CDB</option>
                      <option value="lci_lca">LCI/LCA</option>
                      <option value="ivvb11">IVVB11</option>
                      <option value="gold11">GOLD11</option>
                    </select>
                  </div>
                  <div class="mil-aporte-field">
                    <label class="mil-aporte-label">Valor (R$)</label>
                    <input type="number" id="mil-aporte-valor" class="mil-aporte-input" min="0.01" step="0.01" placeholder="0,00" required>
                  </div>
                  <button type="submit" class="mil-aporte-submit">+ Adicionar</button>
                </div>
                <div class="mil-aporte-status" id="mil-aporte-status"></div>
              </form>

              <div id="mil-aporte-empty" class="mil-aporte-empty hidden">
                Nenhum aporte registrado ainda.
              </div>

              <table class="mil-aporte-table" id="mil-aporte-table">
                <thead>
                  <tr>
                    <th>Mês</th>
                    <th>Ativo</th>
                    <th>Valor</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody id="mil-aporte-tbody"></tbody>
              </table>
            </div><!-- /#mil-pane-aportes -->

          </div><!-- /#fin-pane-milhao -->
```

- [ ] **Step 3: Verificar estrutura no browser**

```bash
# Reiniciar Jake OS
pkill -f "python.*app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/venv/bin/python app.py > /tmp/jakeos.log 2>&1 &
sleep 2 && tail -5 /tmp/jakeos.log
```

Navegar para Financeiro → aba Projeto Milhão. Confirmar que 3 sub-tabs aparecem e que clicar em cada um não quebra a página.

- [ ] **Step 4: Commit**

```bash
cd /root/jake_desktop && git add templates/dashboard.html
git commit -m "feat(financeiro): sub-tabs Simulador/Termômetro/Aportes em #fin-pane-milhao"
```

---

## Task 4: CSS — Estilos dos novos componentes

**Files:**
- Modify: `jake_desktop/static/css/dashboard.css` (append ao final)

- [ ] **Step 1: Adicionar estilos ao final de `dashboard.css`**

```css
/* ── Projeto Milhão: Sub-tabs ──────────────────────────────────────────────── */
.mil-subtab-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 20px;
  border-bottom: 1px solid rgba(0,229,255,0.15);
  padding-bottom: 10px;
}
.mil-subtab-btn {
  background: transparent;
  border: 1px solid rgba(0,229,255,0.25);
  color: #546e7a;
  padding: 6px 18px;
  border-radius: 20px;
  cursor: pointer;
  font-family: 'Rajdhani', sans-serif;
  font-size: 13px;
  letter-spacing: 0.5px;
  transition: all 0.2s;
}
.mil-subtab-btn:hover { color: #00e5ff; border-color: #00e5ff; }
.mil-subtab-btn.active {
  background: rgba(0,229,255,0.12);
  border-color: #00e5ff;
  color: #00e5ff;
}
.mil-subtab-pane { display: none; }
.mil-subtab-pane.active { display: block; }

/* ── Termômetro ────────────────────────────────────────────────────────────── */
#mil-termo-patrimonio-wrap {
  text-align: center;
  margin-bottom: 24px;
}
.mil-termo-valor {
  font-size: 2.4rem;
  font-weight: 700;
  color: #69f0ae;
  font-family: 'Rajdhani', sans-serif;
  letter-spacing: 1px;
}
.mil-termo-label {
  font-size: 12px;
  color: #546e7a;
  margin: 2px 0 4px;
}
.mil-termo-pct {
  font-size: 13px;
  color: #00e5ff;
  margin-bottom: 10px;
}
.mil-termo-barra-wrap {
  height: 8px;
  background: rgba(255,255,255,0.08);
  border-radius: 4px;
  overflow: hidden;
  max-width: 480px;
  margin: 0 auto;
}
.mil-termo-barra-fill {
  height: 100%;
  background: linear-gradient(90deg, #69f0ae, #00e5ff);
  border-radius: 4px;
  transition: width 0.6s ease;
  min-width: 0;
}
.mil-termo-charts-row {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
  align-items: flex-start;
}
.mil-termo-donut-wrap {
  width: 200px;
  height: 200px;
  flex-shrink: 0;
}
.mil-termo-ativos-wrap { flex: 1; }
.mil-termo-ativo-row { margin-bottom: 10px; }
.mil-termo-ativo-header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 3px;
}
.mil-termo-ativo-name { font-weight: 600; }
.mil-termo-ativo-pcts { color: #546e7a; }
.mil-termo-ativo-bar-bg {
  height: 5px;
  background: rgba(255,255,255,0.07);
  border-radius: 3px;
  overflow: hidden;
}
.mil-termo-ativo-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}
.mil-termo-evolucao-wrap {
  height: 180px;
  margin-top: 8px;
}
.mil-termo-empty {
  text-align: center;
  padding: 48px 0;
  color: #546e7a;
  font-size: 14px;
}

/* ── Aportes Form + Table ──────────────────────────────────────────────────── */
.mil-aporte-form {
  background: rgba(0,229,255,0.04);
  border: 1px solid rgba(0,229,255,0.15);
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 20px;
}
.mil-aporte-form-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-wrap: wrap;
}
.mil-aporte-field { display: flex; flex-direction: column; gap: 4px; }
.mil-aporte-label { font-size: 11px; color: #546e7a; font-family: 'Rajdhani', sans-serif; }
.mil-aporte-input {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.15);
  color: #e0e0e0;
  border-radius: 6px;
  padding: 7px 12px;
  font-size: 13px;
  font-family: 'Rajdhani', sans-serif;
  min-width: 120px;
}
.mil-aporte-input:focus { outline: none; border-color: #00e5ff; }
.mil-aporte-submit {
  background: rgba(0,229,255,0.12);
  border: 1px solid #00e5ff;
  color: #00e5ff;
  border-radius: 6px;
  padding: 7px 20px;
  cursor: pointer;
  font-family: 'Rajdhani', sans-serif;
  font-size: 13px;
  transition: background 0.2s;
  white-space: nowrap;
}
.mil-aporte-submit:hover { background: rgba(0,229,255,0.22); }
.mil-aporte-status { font-size: 12px; margin-top: 6px; min-height: 16px; }
.mil-aporte-empty {
  text-align: center;
  color: #546e7a;
  padding: 32px 0;
  font-size: 14px;
}
.mil-aporte-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  font-family: 'Rajdhani', sans-serif;
}
.mil-aporte-table th {
  text-align: left;
  padding: 8px 12px;
  color: #546e7a;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.mil-aporte-table td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  color: #b0bec5;
}
.mil-aporte-table tr:hover td { background: rgba(255,255,255,0.02); }
.mil-aporte-del-btn {
  background: transparent;
  border: none;
  color: #ff525266;
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
  border-radius: 4px;
  transition: color 0.15s;
}
.mil-aporte-del-btn:hover { color: #ff5252; }
```

- [ ] **Step 2: Verificar no browser**

Recarregar página, abrir Financeiro → Projeto Milhão. Confirmar:
- Sub-tabs com visual correto (botão ativo com borda cyan)
- Pane Aportes mostra formulário e tabela vazia
- Pane Termômetro mostra área em branco (JS ainda não implementado)

- [ ] **Step 3: Commit**

```bash
cd /root/jake_desktop && git add static/css/dashboard.css
git commit -m "feat(financeiro): CSS sub-tabs, termômetro e aportes"
```

---

## Task 5: JS — Estado, sub-tabs, CRUD de aportes

**Files:**
- Modify: `jake_desktop/static/js/financeiro.js`

- [ ] **Step 1: Adicionar variáveis de estado e constante de ativos**

Logo após `var chartMilhao = null;` (~linha 114), adicionar:

```js
  var chartTermoDonut    = null;
  var chartTermoEvolucao = null;
  var APORTES = [];
  var _milSubTabsInited = false;

  var ATIVOS_CARTEIRA = [
    { key: 'tesouro_selic', label: 'Tesouro Selic', cor: '#00e5ff', meta: 30 },
    { key: 'cdb',           label: 'CDB',           cor: '#ffd740', meta: 25 },
    { key: 'lci_lca',       label: 'LCI/LCA',       cor: '#69f0ae', meta: 15 },
    { key: 'ivvb11',        label: 'IVVB11',         cor: '#ff5252', meta: 20 },
    { key: 'gold11',        label: 'GOLD11',         cor: '#7c4dff', meta: 10 },
  ];
```

- [ ] **Step 2: Adicionar `initSubTabsMilhao()` e `carregarAportes()`**

Adicionar após a função `initProjetoMilhao()` (antes de `calcularMilhao()`):

```js
  function initSubTabsMilhao() {
    if (_milSubTabsInited) return;
    _milSubTabsInited = true;

    document.querySelectorAll('.mil-subtab-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        document.querySelectorAll('.mil-subtab-btn').forEach(function(b){ b.classList.remove('active'); });
        document.querySelectorAll('.mil-subtab-pane').forEach(function(p){ p.classList.remove('active'); });
        this.classList.add('active');
        var pane = document.getElementById('mil-pane-' + this.dataset.subtab);
        if (pane) pane.classList.add('active');
        if (this.dataset.subtab === 'termometro') renderTermometro();
        if (this.dataset.subtab === 'aportes')    renderAportes();
      });
    });

    // Form de registro de aporte
    var form = document.getElementById('mil-aporte-form');
    if (form) {
      form.addEventListener('submit', function(e) {
        e.preventDefault();
        var mes   = document.getElementById('mil-aporte-mes').value;    // "2026-04"
        var ativo = document.getElementById('mil-aporte-ativo').value;
        var valor = parseFloat(document.getElementById('mil-aporte-valor').value);
        if (!mes || !ativo || isNaN(valor) || valor <= 0) return;
        adicionarAporte({ mes_ano: mes + '-01', ativo: ativo, valor: valor });
        document.getElementById('mil-aporte-valor').value = '';
      });
    }

    carregarAportes();
  }

  function carregarAportes() {
    fetch('/api/financeiro/aportes')
      .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function(data) {
        APORTES = data;
        renderTermometro();
        renderAportes();
      })
      .catch(function(e){ console.error('Erro ao carregar aportes:', e); });
  }
```

- [ ] **Step 3: Chamar `initSubTabsMilhao()` dentro de `initProjetoMilhao()`**

Dentro da função `initProjetoMilhao()`, logo após o guard `if (_milhaoInited) return;`:

```js
    initSubTabsMilhao();
```

- [ ] **Step 4: Adicionar `renderAportes()`, `adicionarAporte()`, `deletarAporte()`**

Adicionar após `initSubTabsMilhao()`:

```js
  function renderAportes() {
    var tbody = document.getElementById('mil-aporte-tbody');
    var empty = document.getElementById('mil-aporte-empty');
    var table = document.getElementById('mil-aporte-table');
    if (!tbody) return;

    if (APORTES.length === 0) {
      if (empty) empty.classList.remove('hidden');
      if (table) table.style.display = 'none';
      return;
    }
    if (empty) empty.classList.add('hidden');
    if (table) table.style.display = '';

    var ativoLabel = {};
    ATIVOS_CARTEIRA.forEach(function(a){ ativoLabel[a.key] = a; });

    tbody.innerHTML = APORTES.map(function(ap) {
      var a = ativoLabel[ap.ativo] || { label: ap.ativo, cor: '#b0bec5' };
      var mesStr = ap.mes_ano ? ap.mes_ano.substring(0, 7) : ap.mes_ano;
      return '<tr>' +
        '<td>' + mesStr + '</td>' +
        '<td style="color:' + a.cor + ';font-weight:600">' + a.label + '</td>' +
        '<td style="color:#69f0ae">' + fmt(ap.valor) + '</td>' +
        '<td><button class="mil-aporte-del-btn" data-id="' + ap.id + '" title="Remover">✕</button></td>' +
      '</tr>';
    }).join('');

    tbody.querySelectorAll('.mil-aporte-del-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        deletarAporte(parseInt(this.dataset.id));
      });
    });
  }

  function adicionarAporte(dados) {
    var status = document.getElementById('mil-aporte-status');
    fetch('/api/financeiro/aportes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados)
    })
    .then(function(r){ return r.json(); })
    .then(function(res) {
      if (res.ok) {
        // prepend local para feedback imediato
        APORTES.unshift({ id: res.id, mes_ano: dados.mes_ano + '-01', ativo: dados.ativo, valor: dados.valor });
        renderAportes();
        renderTermometro();
        if (status) { status.textContent = '✓ Aporte registrado'; status.style.color = '#69f0ae'; setTimeout(function(){ status.textContent = ''; }, 2000); }
      } else {
        if (status) { status.textContent = '⚠ ' + (res.error || 'Erro'); status.style.color = '#ff5252'; }
      }
    })
    .catch(function(e) {
      if (status) { status.textContent = '⚠ Erro de conexão'; status.style.color = '#ff5252'; }
      console.error('adicionarAporte erro:', e);
    });
  }

  function deletarAporte(id) {
    fetch('/api/financeiro/aportes/' + id, { method: 'DELETE' })
      .then(function(r){ return r.json(); })
      .then(function(res) {
        if (res.ok) {
          APORTES = APORTES.filter(function(a){ return a.id !== id; });
          renderAportes();
          renderTermometro();
        }
      })
      .catch(function(e){ console.error('deletarAporte erro:', e); });
  }
```

- [ ] **Step 5: Verificar no browser**

Recarregar. Ir em Financeiro → Projeto Milhão → Aportes:
- Formulário funciona (submit registra na API, aparece na tabela)
- Botão ✕ deleta da tabela
- Mensagem de confirmação aparece e some

- [ ] **Step 6: Commit**

```bash
cd /root/jake_desktop && git add static/js/financeiro.js
git commit -m "feat(financeiro): CRUD aportes no frontend — initSubTabsMilhao + renderAportes"
```

---

## Task 6: JS — Termômetro (charts + barras de alocação)

**Files:**
- Modify: `jake_desktop/static/js/financeiro.js`

- [ ] **Step 1: Adicionar função `renderTermometro()`**

Adicionar após `renderAportes()`:

```js
  function renderTermometro() {
    var elValor = document.getElementById('mil-termo-valor');
    var elPct   = document.getElementById('mil-termo-pct');
    var elFill  = document.getElementById('mil-termo-barra-fill');
    var elBody  = document.getElementById('mil-termo-body');
    var elEmpty = document.getElementById('mil-termo-empty');

    if (APORTES.length === 0) {
      if (elBody)  elBody.classList.add('hidden');
      if (elEmpty) elEmpty.classList.remove('hidden');
      if (elValor) elValor.textContent = 'R$ 0,00';
      if (elPct)   elPct.textContent   = '0,0% da meta R$ 1.000.000';
      if (elFill)  elFill.style.width  = '0%';
      return;
    }
    if (elBody)  elBody.classList.remove('hidden');
    if (elEmpty) elEmpty.classList.add('hidden');

    // Totais por ativo
    var totais = {};
    ATIVOS_CARTEIRA.forEach(function(a){ totais[a.key] = 0; });
    var total = 0;
    APORTES.forEach(function(ap) {
      if (totais[ap.ativo] !== undefined) totais[ap.ativo] += parseFloat(ap.valor);
      total += parseFloat(ap.valor);
    });

    // Big number + barra
    if (elValor) elValor.textContent = fmt(total);
    var pct = total > 0 ? Math.min((total / 1000000) * 100, 100) : 0;
    if (elPct)  elPct.textContent  = pct.toFixed(2).replace('.', ',') + '% da meta R$ 1.000.000';
    if (elFill) elFill.style.width = Math.max(pct, 0.1) + '%';

    // Barras de alocação por ativo
    var wrapAtivos = document.getElementById('mil-termo-ativos-wrap');
    if (wrapAtivos) {
      wrapAtivos.innerHTML = ATIVOS_CARTEIRA.map(function(a) {
        var v   = totais[a.key] || 0;
        var pctAtual = total > 0 ? (v / total * 100) : 0;
        return '<div class="mil-termo-ativo-row">' +
          '<div class="mil-termo-ativo-header">' +
            '<span class="mil-termo-ativo-name" style="color:' + a.cor + '">' + a.label + '</span>' +
            '<span class="mil-termo-ativo-pcts">' +
              pctAtual.toFixed(1) + '% atual · meta ' + a.meta + '%' +
            '</span>' +
          '</div>' +
          '<div class="mil-termo-ativo-bar-bg">' +
            '<div class="mil-termo-ativo-bar-fill" style="width:' + Math.min(pctAtual, 100) + '%;background:' + a.cor + '"></div>' +
          '</div>' +
        '</div>';
      }).join('');
    }

    // Donut chart
    if (chartTermoDonut) { chartTermoDonut.destroy(); chartTermoDonut = null; }
    var canvasDonut = document.getElementById('mil-termo-donut');
    if (canvasDonut && typeof Chart !== 'undefined') {
      chartTermoDonut = new Chart(canvasDonut, {
        type: 'doughnut',
        data: {
          labels: ATIVOS_CARTEIRA.map(function(a){ return a.label; }),
          datasets: [{
            data: ATIVOS_CARTEIRA.map(function(a){ return parseFloat((totais[a.key] || 0).toFixed(2)); }),
            backgroundColor: ATIVOS_CARTEIRA.map(function(a){ return a.cor + 'cc'; }),
            borderColor: ATIVOS_CARTEIRA.map(function(a){ return a.cor; }),
            borderWidth: 1.5,
            hoverOffset: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          cutout: '60%',
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function(ctx) {
                  var total2 = ctx.dataset.data.reduce(function(s,v){ return s+v; }, 0);
                  var p = total2 > 0 ? ((ctx.raw / total2) * 100).toFixed(1) : '0.0';
                  return ' ' + ctx.label + ': ' + fmt(ctx.raw) + ' (' + p + '%)';
                }
              }
            }
          }
        }
      });
    }

    // Gráfico de evolução mensal
    _renderTermoEvolucao(total);
  }

  function _renderTermoEvolucao(totalAtual) {
    // Agrupar por mês e calcular acumulado
    var porMes = {};
    APORTES.forEach(function(ap) {
      var chave = ap.mes_ano ? ap.mes_ano.substring(0, 7) : '';
      if (!chave) return;
      porMes[chave] = (porMes[chave] || 0) + parseFloat(ap.valor);
    });
    var meses = Object.keys(porMes).sort();
    var acum = 0;
    var labels = [], dados = [];
    meses.forEach(function(m) {
      acum += porMes[m];
      labels.push(m);
      dados.push(parseFloat(acum.toFixed(2)));
    });

    if (chartTermoEvolucao) { chartTermoEvolucao.destroy(); chartTermoEvolucao = null; }
    var canvas = document.getElementById('mil-termo-evolucao');
    if (!canvas || typeof Chart === 'undefined' || labels.length === 0) return;

    chartTermoEvolucao = new Chart(canvas, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Patrimônio',
          data: dados,
          borderColor: '#00e5ff',
          backgroundColor: 'rgba(0,229,255,0.07)',
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
          pointBackgroundColor: '#00e5ff',
          tension: 0.35,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(ctx){ return ' Patrimônio: ' + fmt(ctx.raw); }
            }
          }
        },
        scales: {
          x: {
            ticks: { color: '#546e7a', font: { family: 'Rajdhani', size: 11 } },
            grid: { color: 'rgba(0,229,255,0.05)' }
          },
          y: {
            ticks: {
              color: '#546e7a',
              font: { family: 'Rajdhani', size: 11 },
              callback: function(v){ return 'R$ ' + (v/1000).toFixed(1) + 'K'; }
            },
            grid: { color: 'rgba(0,229,255,0.06)' }
          }
        }
      }
    });
  }
```

- [ ] **Step 2: Verificar no browser**

Registrar 2-3 aportes pela aba Aportes. Clicar em Termômetro. Confirmar:
- Valor total correto
- Barra de progresso proporcional
- Donut com fatias nos 5 ativos
- Barras de alocação com % atual vs. meta
- Gráfico de evolução mostrando pontos mês a mês

- [ ] **Step 3: Verificar estado vazio**

Deletar todos os aportes. Termômetro exibe mensagem de estado vazio sem erros de JS no console.

- [ ] **Step 4: Commit**

```bash
cd /root/jake_desktop && git add static/js/financeiro.js
git commit -m "feat(financeiro): renderTermometro — patrimônio, donut, barras alocação, evolução"
```

---

## Task 7: Restart + smoke test final

- [ ] **Step 1: Rodar suite de testes completa**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_financeiro_api.py -v
```
Esperado: todos `PASSED`

- [ ] **Step 2: Reiniciar Jake OS**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/venv/bin/python app.py > /tmp/jakeos.log 2>&1 &
sleep 2 && tail -5 /tmp/jakeos.log
```

- [ ] **Step 3: Smoke test manual**

1. Abrir Financeiro → Projeto Milhão
2. Clicar em Simulador → calculadora funciona normalmente
3. Clicar em Aportes → registrar: Abr/2026, IVVB11, R$113
4. Registrar mais: Abr/2026, Tesouro Selic, R$170 / Abr/2026, GOLD11, R$57
5. Clicar em Termômetro → patrimônio R$340, barra, donut, gráfico
6. Deletar um aporte → Termômetro atualiza
7. Nenhum erro no console do browser

- [ ] **Step 4: Commit final**

```bash
cd /root/jake_desktop && git add app.py templates/dashboard.html static/css/dashboard.css static/js/financeiro.js tests/test_financeiro_api.py docs/superpowers/
git commit -m "feat(financeiro): carteira de investimentos completa — aportes + termômetro"
```
