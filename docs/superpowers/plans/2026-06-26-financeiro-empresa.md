# Financeiro Empresa — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar seção PJ (Zati Soluções Digitais) ao módulo financeiro do Jake OS, com cálculo fiscal automático (DAS 6%, INSS 11% s/ pró-labore 28%), 3 donuts separados por categoria e integração com o Raio-X pessoal.

**Architecture:** Nova tabela `fin_empresa_mensal` no Neon com 2 endpoints REST. A seção empresa vive em `#fin-pane-visao-geral`, calcula impostos em tempo real no cliente, e injeta pró-labore + distribuição como linhas somente-leitura nas Entradas do Raio-X. O donut único "Divisão de Despesas" é substituído por 3 donuts lado a lado (Fixas / Variáveis / Empresa).

**Tech Stack:** Flask (Blueprint), psycopg2, Vanilla JS (Chart.js já presente), HTML/CSS glassmorphism dark.

## Global Constraints

- Não usar `venv/` ou `.venv/` em buscas
- Ler `dashboard.html` e `financeiro.js` SEMPRE em blocos de 100 linhas com offset
- Jake OS roda na porta 5050 — reiniciar após mudanças no backend
- Não commitar `.env`
- Ano fixo 2026 no seletor de mês
- Dados da empresa: nunca DELETE, somente upsert via PUT

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|------------------|
| `jake_desktop/blueprints/financeiro.py` | Modificar | 2 novos endpoints GET/PUT + criar tabela no boot |
| `jake_desktop/templates/dashboard.html` | Modificar | Substituir 1 donut por 3 + seção empresa acima do Raio-X |
| `jake_desktop/static/js/financeiro.js` | Modificar | Lógica empresa, 3 renderDonut*, injeção Raio-X, carregarDados |

---

## Task 1: Criar tabela `fin_empresa_mensal` + endpoints backend

**Files:**
- Modify: `jake_desktop/blueprints/financeiro.py` (ao final do arquivo, antes da linha `# ── API: Site Architect`)

**Interfaces:**
- Produz: `GET /api/financeiro/empresa` → `[{mes_ano, faturamento_bruto, pro_labore, distribuicao, mensalidade_contab, outras_despesas_pj}, ...]`
- Produz: `PUT /api/financeiro/empresa/<mes_ano>` → `{"ok": true}`

- [ ] **Step 1: Adicionar função de criação da tabela e endpoints no financeiro.py**

Localizar a linha `# ── API: Site Architect` no `financeiro.py` (linha ~440) e inserir o bloco abaixo ANTES dela:

```python
# ── Financeiro: Empresa (Zati Soluções Digitais) ─────────────────────────

def _init_empresa_table():
    """Cria tabela fin_empresa_mensal se não existir."""
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fin_empresa_mensal (
                id                  SERIAL PRIMARY KEY,
                mes_ano             DATE NOT NULL UNIQUE,
                faturamento_bruto   NUMERIC(12,2) DEFAULT 0,
                pro_labore          NUMERIC(12,2) DEFAULT 0,
                distribuicao        NUMERIC(12,2) DEFAULT 0,
                mensalidade_contab  NUMERIC(12,2) DEFAULT 0,
                outras_despesas_pj  NUMERIC(12,2) DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


_init_empresa_table()


@bp.route("/api/financeiro/empresa", methods=["GET"])
@login_required
def financeiro_empresa_listar():
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT
                TO_CHAR(mes_ano, 'YYYY-MM-DD') AS mes_ano,
                faturamento_bruto, pro_labore, distribuicao,
                mensalidade_contab, outras_despesas_pj
            FROM fin_empresa_mensal
            ORDER BY mes_ano DESC
        """)
        rows = cur.fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/financeiro/empresa/<mes_ano>", methods=["PUT"])
@login_required
def financeiro_empresa_salvar(mes_ano):
    d = request.get_json(force=True) or {}
    campos = {
        "faturamento_bruto":  float(d.get("faturamento_bruto",  0) or 0),
        "pro_labore":         float(d.get("pro_labore",         0) or 0),
        "distribuicao":       float(d.get("distribuicao",       0) or 0),
        "mensalidade_contab": float(d.get("mensalidade_contab", 0) or 0),
        "outras_despesas_pj": float(d.get("outras_despesas_pj", 0) or 0),
    }
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO fin_empresa_mensal
                (mes_ano, faturamento_bruto, pro_labore, distribuicao,
                 mensalidade_contab, outras_despesas_pj)
            VALUES
                (DATE_TRUNC('month', %s::date),
                 %(faturamento_bruto)s, %(pro_labore)s, %(distribuicao)s,
                 %(mensalidade_contab)s, %(outras_despesas_pj)s)
            ON CONFLICT (mes_ano) DO UPDATE SET
                faturamento_bruto  = EXCLUDED.faturamento_bruto,
                pro_labore         = EXCLUDED.pro_labore,
                distribuicao       = EXCLUDED.distribuicao,
                mensalidade_contab = EXCLUDED.mensalidade_contab,
                outras_despesas_pj = EXCLUDED.outras_despesas_pj
        """, dict(campos, **{"mes_ano_param": mes_ano}))
        # Corrigir: passar mes_ano como primeiro parâmetro posicional
        conn.rollback()
        cur.execute("""
            INSERT INTO fin_empresa_mensal
                (mes_ano, faturamento_bruto, pro_labore, distribuicao,
                 mensalidade_contab, outras_despesas_pj)
            VALUES
                (DATE_TRUNC('month', %s::date), %s, %s, %s, %s, %s)
            ON CONFLICT (mes_ano) DO UPDATE SET
                faturamento_bruto  = EXCLUDED.faturamento_bruto,
                pro_labore         = EXCLUDED.pro_labore,
                distribuicao       = EXCLUDED.distribuicao,
                mensalidade_contab = EXCLUDED.mensalidade_contab,
                outras_despesas_pj = EXCLUDED.outras_despesas_pj
        """, (
            mes_ano,
            campos["faturamento_bruto"], campos["pro_labore"],
            campos["distribuicao"], campos["mensalidade_contab"],
            campos["outras_despesas_pj"]
        ))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

**ATENÇÃO:** o bloco acima tem uma versão duplicada para corrigir o upsert. A versão final correta do endpoint PUT deve ser apenas:

```python
@bp.route("/api/financeiro/empresa/<mes_ano>", methods=["PUT"])
@login_required
def financeiro_empresa_salvar(mes_ano):
    d = request.get_json(force=True) or {}
    fat   = float(d.get("faturamento_bruto",  0) or 0)
    pl    = float(d.get("pro_labore",         0) or 0)
    dist  = float(d.get("distribuicao",       0) or 0)
    cont  = float(d.get("mensalidade_contab", 0) or 0)
    outras = float(d.get("outras_despesas_pj",0) or 0)
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO fin_empresa_mensal
                (mes_ano, faturamento_bruto, pro_labore, distribuicao,
                 mensalidade_contab, outras_despesas_pj)
            VALUES (DATE_TRUNC('month', %s::date), %s, %s, %s, %s, %s)
            ON CONFLICT (mes_ano) DO UPDATE SET
                faturamento_bruto  = EXCLUDED.faturamento_bruto,
                pro_labore         = EXCLUDED.pro_labore,
                distribuicao       = EXCLUDED.distribuicao,
                mensalidade_contab = EXCLUDED.mensalidade_contab,
                outras_despesas_pj = EXCLUDED.outras_despesas_pj
        """, (mes_ano, fat, pl, dist, cont, outras))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

Use essa versão limpa, sem o bloco rollback duplicado.

- [ ] **Step 2: Reiniciar Jake OS e verificar tabela criada**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && /root/jake_desktop/.venv/bin/python app.py &>> /tmp/jakeos.log &
sleep 3
curl -s -c /tmp/jake_cookies.txt -b /tmp/jake_cookies.txt \
  -X POST http://localhost:5050/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@jakeos.local","password":"Jake@2024!"}' | head -5
```

- [ ] **Step 3: Testar endpoints**

```bash
# GET — deve retornar []
curl -s -c /tmp/jake_cookies.txt -b /tmp/jake_cookies.txt \
  http://localhost:5050/api/financeiro/empresa

# PUT — salvar junho/2026
curl -s -c /tmp/jake_cookies.txt -b /tmp/jake_cookies.txt \
  -X PUT http://localhost:5050/api/financeiro/empresa/2026-06-01 \
  -H "Content-Type: application/json" \
  -d '{"faturamento_bruto":7475,"pro_labore":2093,"distribuicao":0,"mensalidade_contab":0,"outras_despesas_pj":0}'

# GET novamente — deve retornar o registro salvo
curl -s -c /tmp/jake_cookies.txt -b /tmp/jake_cookies.txt \
  http://localhost:5050/api/financeiro/empresa
```

Esperado: `[{"mes_ano":"2026-06-01","faturamento_bruto":"7475.00",...}]`

- [ ] **Step 4: Commit**

```bash
cd /root && git add jake_desktop/blueprints/financeiro.py
git commit -m "feat(financeiro): endpoint empresa + tabela fin_empresa_mensal"
```

---

## Task 2: HTML — substituir donut único por 3 donuts + seção empresa

**Files:**
- Modify: `jake_desktop/templates/dashboard.html` (região linha ~1717–1730 para donuts; linha ~1747 para seção empresa)

**Interfaces:**
- Consome: nada de tasks anteriores (HTML puro)
- Produz: canvas IDs `fin-chart-donut-fixas`, `fin-chart-donut-variaveis`, `fin-chart-donut-empresa` | seção `#fin-empresa-section` com inputs

- [ ] **Step 1: Substituir bloco dos gráficos (donuts)**

Localizar o trecho atual (linha ~1724–1730):
```html
              <div class="fin-chart-card fin-chart-donut-card">
                <h3 class="fin-chart-title">Divisão de Despesas</h3>
                <div class="fin-chart-wrap">
                  <canvas id="fin-chart-donut"></canvas>
                </div>
              </div>
```

Substituir por:
```html
              <div class="fin-chart-card fin-chart-donut-card fin-donut-triple">
                <div class="fin-donut-triple-item">
                  <h3 class="fin-chart-title fin-donut-title">Fixas</h3>
                  <div class="fin-chart-wrap fin-donut-wrap-sm">
                    <canvas id="fin-chart-donut-fixas"></canvas>
                  </div>
                </div>
                <div class="fin-donut-triple-item">
                  <h3 class="fin-chart-title fin-donut-title">Variáveis</h3>
                  <div class="fin-chart-wrap fin-donut-wrap-sm">
                    <canvas id="fin-chart-donut-variaveis"></canvas>
                  </div>
                </div>
                <div class="fin-donut-triple-item">
                  <h3 class="fin-chart-title fin-donut-title">Empresa</h3>
                  <div class="fin-chart-wrap fin-donut-wrap-sm">
                    <canvas id="fin-chart-donut-empresa"></canvas>
                  </div>
                </div>
              </div>
```

- [ ] **Step 2: Adicionar seção empresa acima do Raio-X**

Localizar a linha da seção Raio-X (linha ~1748):
```html
            <!-- ── Raio-X: Planilha Anual ────────────── -->
            <div class="fin-raiox-section">
```

Inserir o bloco abaixo ANTES dessa div:
```html
            <!-- ── Empresa: Zati Soluções Digitais ─────── -->
            <div class="fin-empresa-section" id="fin-empresa-section">
              <div class="fin-empresa-header">
                <h3 class="fin-section-title">◈ Empresa — Zati Soluções Digitais
                  <span class="fin-empresa-cnpj">CNPJ 66.989.646/0001-51 · Simples Nacional Anexo III</span>
                </h3>
                <button class="fin-empresa-save-btn" id="fin-empresa-save-btn">Salvar</button>
              </div>

              <div class="fin-empresa-grid">
                <!-- Entradas PJ -->
                <div class="fin-empresa-card">
                  <div class="fin-empresa-card-title">Entradas PJ</div>
                  <label class="fin-empresa-label">Faturamento bruto
                    <input type="number" id="fin-emp-faturamento" class="fin-empresa-input" placeholder="0,00" min="0" step="0.01">
                  </label>
                  <label class="fin-empresa-label">Pró-labore (28% sugerido)
                    <input type="number" id="fin-emp-prolabore" class="fin-empresa-input" placeholder="0,00" min="0" step="0.01">
                  </label>
                  <label class="fin-empresa-label">Distribuição de lucros
                    <input type="number" id="fin-emp-distribuicao" class="fin-empresa-input" placeholder="0,00" min="0" step="0.01">
                  </label>
                  <div class="fin-empresa-receita-pj">
                    Receita PJ → pessoal: <strong id="fin-emp-receita-pj">R$ --</strong>
                  </div>
                </div>

                <!-- Impostos (auto) -->
                <div class="fin-empresa-card fin-empresa-card-impostos">
                  <div class="fin-empresa-card-title">Impostos (auto)</div>
                  <div class="fin-empresa-calc-row">
                    <span>DAS 6%</span>
                    <span id="fin-emp-das">R$ --</span>
                  </div>
                  <div class="fin-empresa-calc-row">
                    <span>INSS 11% s/ pró-labore</span>
                    <span id="fin-emp-inss">R$ --</span>
                  </div>
                  <div class="fin-empresa-calc-row fin-empresa-calc-total">
                    <span>Total impostos</span>
                    <span id="fin-emp-total-imp">R$ --</span>
                  </div>
                  <div class="fin-empresa-calc-row fin-empresa-calc-liquido">
                    <span>Líquido PJ</span>
                    <span id="fin-emp-liquido">R$ --</span>
                  </div>
                </div>

                <!-- Despesas PJ -->
                <div class="fin-empresa-card">
                  <div class="fin-empresa-card-title">Despesas PJ</div>
                  <label class="fin-empresa-label">Mensalidade contabilidade
                    <input type="number" id="fin-emp-contab" class="fin-empresa-input" placeholder="0,00" min="0" step="0.01">
                  </label>
                  <label class="fin-empresa-label">Outras despesas PJ
                    <input type="number" id="fin-emp-outras" class="fin-empresa-input" placeholder="0,00" min="0" step="0.01">
                  </label>
                </div>
              </div>
            </div>
```

- [ ] **Step 3: Commit**

```bash
cd /root && git add jake_desktop/templates/dashboard.html
git commit -m "feat(financeiro): HTML seção empresa + 3 donuts"
```

---

## Task 3: CSS — estilos da seção empresa e 3 donuts

**Files:**
- Modify: `jake_desktop/static/css/dashboard.css` (adicionar ao final)

**Interfaces:**
- Consome: classes HTML criadas na Task 2
- Produz: layout visual consistente com o tema glassmorphism/dark cyan

- [ ] **Step 1: Adicionar estilos ao final de dashboard.css**

```css
/* ── Financeiro: 3 Donuts ──────────────────────────────────────────────── */
.fin-donut-triple {
  display: flex;
  gap: 0;
  padding: 0;
  align-items: stretch;
}
.fin-donut-triple-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1rem 0.5rem;
  border-right: 1px solid rgba(0,229,255,0.08);
}
.fin-donut-triple-item:last-child { border-right: none; }
.fin-donut-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 0.5rem;
  color: var(--cyan);
  opacity: 0.8;
}
.fin-donut-wrap-sm {
  width: 100%;
  height: 160px;
  position: relative;
}

/* ── Financeiro: Seção Empresa ─────────────────────────────────────────── */
.fin-empresa-section {
  background: rgba(0,229,255,0.03);
  border: 1px solid rgba(0,229,255,0.15);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}
.fin-empresa-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.fin-empresa-cnpj {
  font-size: 11px;
  color: var(--cyan);
  opacity: 0.6;
  margin-left: 0.75rem;
  font-weight: 400;
}
.fin-empresa-save-btn {
  background: rgba(0,229,255,0.12);
  border: 1px solid rgba(0,229,255,0.35);
  color: var(--cyan);
  border-radius: 6px;
  padding: 0.35rem 1rem;
  font-size: 13px;
  cursor: pointer;
  font-family: 'Rajdhani', sans-serif;
  letter-spacing: 0.05em;
  transition: background 0.2s;
}
.fin-empresa-save-btn:hover { background: rgba(0,229,255,0.22); }
.fin-empresa-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}
@media (max-width: 900px) {
  .fin-empresa-grid { grid-template-columns: 1fr; }
  .fin-donut-triple { flex-direction: column; }
}
.fin-empresa-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
  padding: 1rem;
}
.fin-empresa-card-impostos {
  border-color: rgba(255,210,0,0.15);
  background: rgba(255,210,0,0.03);
}
.fin-empresa-card-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #78909c;
  margin-bottom: 0.75rem;
}
.fin-empresa-label {
  display: flex;
  flex-direction: column;
  font-size: 12px;
  color: #90a4ae;
  margin-bottom: 0.6rem;
  gap: 0.25rem;
}
.fin-empresa-input {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 5px;
  color: #e0e0e0;
  font-size: 14px;
  padding: 0.35rem 0.6rem;
  width: 100%;
  font-family: 'Rajdhani', sans-serif;
}
.fin-empresa-input:focus {
  outline: none;
  border-color: rgba(0,229,255,0.4);
}
.fin-empresa-receita-pj {
  margin-top: 0.75rem;
  font-size: 12px;
  color: #69f0ae;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(255,255,255,0.06);
}
.fin-empresa-calc-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #90a4ae;
  padding: 0.3rem 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.fin-empresa-calc-row span:last-child { color: #ffd740; font-weight: 600; }
.fin-empresa-calc-total {
  color: #e0e0e0 !important;
  font-weight: 600;
  border-top: 1px solid rgba(255,210,0,0.2);
  margin-top: 0.25rem;
}
.fin-empresa-calc-total span:last-child { color: #ff5252 !important; }
.fin-empresa-calc-liquido span:last-child { color: #69f0ae !important; }
```

- [ ] **Step 2: Verificar visual no browser**

Abrir `http://localhost:5050/#financeiro` e confirmar:
- 3 donuts lado a lado no lugar do donut único
- Seção empresa com 3 cards acima do Raio-X

- [ ] **Step 3: Commit**

```bash
cd /root && git add jake_desktop/static/css/dashboard.css
git commit -m "feat(financeiro): CSS seção empresa + 3 donuts"
```

---

## Task 4: JS — 3 funções renderDonut + remover ME/Impostos

**Files:**
- Modify: `jake_desktop/static/js/financeiro.js`

**Interfaces:**
- Consome: canvas IDs `fin-chart-donut-fixas`, `fin-chart-donut-variaveis`, `fin-chart-donut-empresa`
- Consome: variável global `EMPRESA_MES` (definida na Task 5)
- Produz: funções `renderDonutFixas()`, `renderDonutVariaveis()`, `renderDonutEmpresa()`

- [ ] **Step 1: Remover linha ME/Impostos do RAIOX_PADRAO**

No `financeiro.js`, localizar na seção `fixas` do `RAIOX_PADRAO` (linha ~35):
```js
      { nome: 'ME/Impostos',    valores: [1200,1200,1200,1200,1200,1200,1200,1200,1200,0,0,0] },
```
Remover essa linha completamente.

- [ ] **Step 2: Adicionar variável global EMPRESA_MES**

Logo após a linha `var ATIVOS_CARTEIRA = [];` (linha ~120), adicionar:
```js
  var EMPRESA_DADOS = {};   // { "2026-01-01": {faturamento_bruto, pro_labore, ...}, ... }
```

- [ ] **Step 3: Substituir renderDonut() pelas 3 funções**

Localizar a função `renderDonut()` (linha ~684) e substituí-la integralmente pelas 3 funções abaixo:

```js
  function _renderDonutGenerico(canvasId, titulo, dados, paleta) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) return;
    var entries = Object.entries(dados)
      .filter(function(e){ return e[1] > 0; })
      .sort(function(a,b){ return b[1]-a[1]; });
    if (entries.length === 0) {
      canvas.parentElement.innerHTML = '<div style="color:#546e7a;font-size:11px;text-align:center;padding:20px 0;">Sem dados</div>';
      return;
    }
    var top    = entries.slice(0, 7);
    var outros = entries.slice(7).reduce(function(s,e){ return s+e[1]; }, 0);
    if (outros > 0) top.push(['Outros', outros]);
    var existingChart = Chart.getChart(canvas);
    if (existingChart) existingChart.destroy();
    new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: top.map(function(e){ return e[0]; }),
        datasets: [{
          data: top.map(function(e){ return parseFloat(e[1].toFixed(2)); }),
          backgroundColor: paleta.slice(0, top.length).map(function(c){ return c+'cc'; }),
          borderColor: paleta.slice(0, top.length),
          borderWidth: 1.5,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '60%',
        plugins: {
          legend: { position: 'bottom', labels: { color: '#90a4ae', font: { family: 'Rajdhani', size: 10 }, padding: 6, boxWidth: 10 } },
          tooltip: { callbacks: { label: function(ctx){
            var total = ctx.dataset.data.reduce(function(s,v){ return s+v; }, 0);
            var pct   = ((ctx.raw/total)*100).toFixed(1);
            return ' R$ '+ctx.raw.toLocaleString('pt-BR',{minimumFractionDigits:2})+' ('+pct+'%)';
          }}}
        }
      }
    });
  }

  function renderDonutFixas() {
    var mesIdx = mesSelecionado - 1;
    var dados  = {};
    RAIOX.fixas.forEach(function(item){
      var v = item.valores[mesIdx] || 0;
      if (v > 0) dados[item.nome] = (dados[item.nome] || 0) + v;
    });
    var paleta = ['#00e5ff','#40c4ff','#7c4dff','#e040fb','#69f0ae','#ffd740','#ff6e40','#f48fb1'];
    _renderDonutGenerico('fin-chart-donut-fixas', 'Fixas', dados, paleta);
  }

  function renderDonutVariaveis() {
    var mesIdx = mesSelecionado - 1;
    var dados  = {};
    RAIOX.variaveis.forEach(function(item){
      var v = item.valores[mesIdx] || 0;
      if (v > 0) dados[item.nome] = (dados[item.nome] || 0) + v;
    });
    var paleta = ['#ff5252','#ff6e40','#ffd740','#ffab40','#ef9a9a','#ffcc02','#ff8a65','#b0bec5'];
    _renderDonutGenerico('fin-chart-donut-variaveis', 'Variáveis', dados, paleta);
  }

  function renderDonutEmpresa() {
    var mesKey = '2026-' + String(mesSelecionado).padStart(2,'0') + '-01';
    var emp    = EMPRESA_DADOS[mesKey] || {};
    var fat    = parseFloat(emp.faturamento_bruto || 0);
    var pl     = parseFloat(emp.pro_labore        || 0);
    var cont   = parseFloat(emp.mensalidade_contab|| 0);
    var outras = parseFloat(emp.outras_despesas_pj|| 0);
    var das    = parseFloat((fat * 0.06).toFixed(2));
    var inss   = parseFloat((pl  * 0.11).toFixed(2));
    var dados  = {};
    if (das   > 0) dados['DAS 6%']       = das;
    if (inss  > 0) dados['INSS']         = inss;
    if (cont  > 0) dados['Contabilidade']= cont;
    if (outras> 0) dados['Outras']       = outras;
    var paleta = ['#7c4dff','#ce93d8','#69f0ae','#80deea','#a5d6a7','#ffcc02'];
    _renderDonutGenerico('fin-chart-donut-empresa', 'Empresa', dados, paleta);
  }
```

- [ ] **Step 4: Atualizar renderCharts() para chamar as 3 funções**

Localizar a função `renderCharts()` e substituir a chamada `renderDonut()` por:
```js
    renderDonutFixas();
    renderDonutVariaveis();
    renderDonutEmpresa();
```

- [ ] **Step 5: Verificar no browser**

Abrir `http://localhost:5050/#financeiro` → deve aparecer 3 donuts preenchidos (empresa vazio até Task 5).

- [ ] **Step 6: Commit**

```bash
cd /root && git add jake_desktop/static/js/financeiro.js
git commit -m "feat(financeiro): 3 donuts + remove ME/Impostos legacy"
```

---

## Task 5: JS — lógica da seção empresa (carregar, calcular, salvar)

**Files:**
- Modify: `jake_desktop/static/js/financeiro.js`

**Interfaces:**
- Consome: `EMPRESA_DADOS` (Task 4), endpoints `/api/financeiro/empresa` (Task 1)
- Produz: funções `carregarEmpresa()`, `renderEmpresaSection()`, `_calcularEmpresa()`

- [ ] **Step 1: Adicionar função carregarEmpresa()**

Logo após a função `carregarDados()` (linha ~231), adicionar:

```js
  function carregarEmpresa() {
    fetch('/api/financeiro/empresa')
      .then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
      .then(function(lista) {
        EMPRESA_DADOS = {};
        lista.forEach(function(item) {
          EMPRESA_DADOS[item.mes_ano] = item;
        });
        renderEmpresaSection();
        renderDonutEmpresa();
      })
      .catch(function(e){ console.error('Erro carregar empresa:', e); });
  }

  function _calcularEmpresa(fat, pl, cont, outras) {
    var das   = parseFloat((fat * 0.06).toFixed(2));
    var inss  = parseFloat((pl  * 0.11).toFixed(2));
    var total = parseFloat((das + inss).toFixed(2));
    var liq   = parseFloat((fat - total - cont - outras).toFixed(2));
    return { das: das, inss: inss, total: total, liquido: liq };
  }

  function renderEmpresaSection() {
    var mesKey = '2026-' + String(mesSelecionado).padStart(2,'0') + '-01';
    var emp    = EMPRESA_DADOS[mesKey] || {};

    var elFat  = document.getElementById('fin-emp-faturamento');
    var elPL   = document.getElementById('fin-emp-prolabore');
    var elDist = document.getElementById('fin-emp-distribuicao');
    var elCont = document.getElementById('fin-emp-contab');
    var elOut  = document.getElementById('fin-emp-outras');
    if (!elFat) return;

    elFat.value  = emp.faturamento_bruto   || '';
    elPL.value   = emp.pro_labore          || '';
    elDist.value = emp.distribuicao        || '';
    elCont.value = emp.mensalidade_contab  || '';
    elOut.value  = emp.outras_despesas_pj  || '';
    _atualizarCalcEmpresa();
  }

  function _atualizarCalcEmpresa() {
    var fat   = parseFloat(document.getElementById('fin-emp-faturamento')?.value || 0);
    var pl    = parseFloat(document.getElementById('fin-emp-prolabore')?.value   || 0);
    var dist  = parseFloat(document.getElementById('fin-emp-distribuicao')?.value|| 0);
    var cont  = parseFloat(document.getElementById('fin-emp-contab')?.value      || 0);
    var outras= parseFloat(document.getElementById('fin-emp-outras')?.value      || 0);

    var calc  = _calcularEmpresa(fat, pl, cont, outras);

    var set = function(id, v) { var el=document.getElementById(id); if(el) el.textContent=fmt(v); };
    set('fin-emp-das',       calc.das);
    set('fin-emp-inss',      calc.inss);
    set('fin-emp-total-imp', calc.total);
    set('fin-emp-liquido',   calc.liquido);
    set('fin-emp-receita-pj', pl + dist);
  }

  function _bindEmpresaEvents() {
    ['fin-emp-faturamento','fin-emp-distribuicao','fin-emp-contab','fin-emp-outras'].forEach(function(id){
      var el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('input', function() {
        if (id === 'fin-emp-faturamento') {
          var fat = parseFloat(this.value || 0);
          var elPL = document.getElementById('fin-emp-prolabore');
          if (elPL && !elPL._manual) elPL.value = parseFloat((fat * 0.28).toFixed(2)) || '';
        }
        _atualizarCalcEmpresa();
      });
    });
    var elPL = document.getElementById('fin-emp-prolabore');
    if (elPL) {
      elPL.addEventListener('input', function() {
        elPL._manual = true;
        _atualizarCalcEmpresa();
      });
    }
    var btnSave = document.getElementById('fin-empresa-save-btn');
    if (btnSave) {
      btnSave.addEventListener('click', function() {
        var mesKey = '2026-' + String(mesSelecionado).padStart(2,'0') + '-01';
        var payload = {
          faturamento_bruto:  parseFloat(document.getElementById('fin-emp-faturamento')?.value || 0),
          pro_labore:         parseFloat(document.getElementById('fin-emp-prolabore')?.value   || 0),
          distribuicao:       parseFloat(document.getElementById('fin-emp-distribuicao')?.value|| 0),
          mensalidade_contab: parseFloat(document.getElementById('fin-emp-contab')?.value      || 0),
          outras_despesas_pj: parseFloat(document.getElementById('fin-emp-outras')?.value      || 0)
        };
        btnSave.textContent = 'Salvando...';
        btnSave.disabled = true;
        fetch('/api/financeiro/empresa/' + mesKey, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        .then(function(r){ return r.json(); })
        .then(function(res){
          if (res.ok) {
            EMPRESA_DADOS[mesKey] = Object.assign({mes_ano: mesKey}, payload);
            btnSave.textContent = '✓ Salvo';
            renderDonutEmpresa();
            atualizarKPIs();
            renderRaioX();
          } else {
            btnSave.textContent = '⚠ Erro';
          }
          setTimeout(function(){ btnSave.textContent='Salvar'; btnSave.disabled=false; }, 2000);
        })
        .catch(function(e){
          console.error(e);
          btnSave.textContent = '⚠ Erro';
          setTimeout(function(){ btnSave.textContent='Salvar'; btnSave.disabled=false; }, 2000);
        });
      });
    }
  }
```

- [ ] **Step 2: Adicionar carregarEmpresa() ao carregarDados()**

Localizar o bloco `Promise.all([...])` em `carregarDados()`. Adicionar no `then` final, logo após `renderRaioX()`:
```js
      carregarEmpresa();
```

- [ ] **Step 3: Chamar _bindEmpresaEvents() em initFinanceiro()**

Dentro de `initFinanceiro()`, logo após `carregarDados()`:
```js
    _bindEmpresaEvents();
```

- [ ] **Step 4: Atualizar renderEmpresaSection quando mês muda**

Na função que trata o `change` do `selectMes` (linha ~258), adicionar após `renderRaioX()`:
```js
        renderEmpresaSection();
        renderDonutEmpresa();
```

- [ ] **Step 5: Testar no browser**

- Selecionar Jun/2026
- Digitar `7475` no Faturamento → pró-labore deve preencher automaticamente com `2093`
- DAS deve mostrar `R$ 448,50`, INSS `R$ 230,23`, Total `R$ 678,73`
- Clicar Salvar → botão mostra "✓ Salvo"
- Trocar de mês e voltar → dados devem reaparecer

- [ ] **Step 6: Commit**

```bash
cd /root && git add jake_desktop/static/js/financeiro.js
git commit -m "feat(financeiro): seção empresa com cálculo fiscal automático"
```

---

## Task 6: JS — integrar empresa no Raio-X e nos KPIs

**Files:**
- Modify: `jake_desktop/static/js/financeiro.js`

**Interfaces:**
- Consome: `EMPRESA_DADOS` (Task 4/5)
- Produz: linhas somente-leitura "Pró-labore" e "Distribuição de lucros" nas entradas do Raio-X; KPIs e totais mensais incluem empresa

- [ ] **Step 1: Atualizar calcularKPIsFromRaioX() para incluir empresa**

Localizar a função `calcularKPIsFromRaioX()` (linha ~277) e substituir:

```js
  function calcularKPIsFromRaioX(mes, ano) {
    if (ano !== 2026) return calcularKPIs(mes, ano);
    var idx      = mes - 1;
    var receita  = raixoSomaLinha(RAIOX.entradas, idx);
    var fixas    = raixoSomaLinha(RAIOX.fixas,    idx);
    var variaveis= raixoSomaLinha(RAIOX.variaveis,idx);

    var mesKey   = '2026-' + String(mes).padStart(2,'0') + '-01';
    var emp      = EMPRESA_DADOS[mesKey] || {};
    var fat      = parseFloat(emp.faturamento_bruto  || 0);
    var pl       = parseFloat(emp.pro_labore         || 0);
    var dist     = parseFloat(emp.distribuicao       || 0);
    var cont     = parseFloat(emp.mensalidade_contab || 0);
    var outras   = parseFloat(emp.outras_despesas_pj || 0);
    var das      = parseFloat((fat * 0.06).toFixed(2));
    var inss     = parseFloat((pl  * 0.11).toFixed(2));
    var despEmp  = das + inss + cont + outras;
    var recPJ    = pl + dist;

    var totalReceita = receita + recPJ;
    var totalDesp    = fixas + variaveis + despEmp;
    return { receita: totalReceita, despesas: totalDesp, saldo: totalReceita - totalDesp };
  }
```

- [ ] **Step 2: Atualizar raixoTotaisMensais() para incluir empresa**

Localizar a função `raixoTotaisMensais()` (linha ~155) e substituir:

```js
  function raixoTotaisMensais() {
    var totais = { receitas:[], fixas:[], variaveis:[], empresa:[], saldo:[], acumulado:[] };
    var acum = 0;
    for (var m = 0; m < 12; m++) {
      var mesKey  = '2026-' + String(m+1).padStart(2,'0') + '-01';
      var emp     = EMPRESA_DADOS[mesKey] || {};
      var fat     = parseFloat(emp.faturamento_bruto  || 0);
      var pl      = parseFloat(emp.pro_labore         || 0);
      var dist    = parseFloat(emp.distribuicao       || 0);
      var cont    = parseFloat(emp.mensalidade_contab || 0);
      var outras  = parseFloat(emp.outras_despesas_pj || 0);
      var das     = parseFloat((fat * 0.06).toFixed(2));
      var inss    = parseFloat((pl  * 0.11).toFixed(2));
      var despEmp = das + inss + cont + outras;
      var recPJ   = pl + dist;

      var r = raixoSomaLinha(RAIOX.entradas,   m) + recPJ;
      var f = raixoSomaLinha(RAIOX.fixas,       m);
      var v = raixoSomaLinha(RAIOX.variaveis,   m);
      var s = r - f - v - despEmp;
      acum += s;
      totais.receitas.push(r);
      totais.fixas.push(f);
      totais.variaveis.push(v);
      totais.empresa.push(despEmp);
      totais.saldo.push(s);
      totais.acumulado.push(acum);
    }
    return totais;
  }
```

- [ ] **Step 3: Injetar linhas Pró-labore e Distribuição no Raio-X**

Na função `renderRaioX()`, localizar o bloco `// ── ENTRADAS` e após o `forEach` das entradas normais, inserir as linhas PJ somente-leitura:

Localizar (logo antes do `renderRaioXAddLinha('entradas', 'entrada')`):
```js
    RAIOX.entradas.forEach(function(item, idx) {
      html += renderRaioXLinha(item, 'entrada', 'entradas', idx);
    });
    html += renderRaioXAddLinha('entradas', 'entrada');
```

Substituir por:
```js
    RAIOX.entradas.forEach(function(item, idx) {
      html += renderRaioXLinha(item, 'entrada', 'entradas', idx);
    });
    // Linhas PJ (somente-leitura, calculadas de EMPRESA_DADOS)
    html += _renderRaioXLinhaEmpresa('Pró-labore PJ', 'pro_labore');
    html += _renderRaioXLinhaEmpresa('Distribuição de lucros', 'distribuicao');
    html += renderRaioXAddLinha('entradas', 'entrada');
```

E adicionar a função auxiliar antes de `renderRaioX()`:
```js
  function _renderRaioXLinhaEmpresa(nome, campo) {
    var html = '<tr class="fin-rx-row fin-rx-row-pj">';
    html += '<td class="fin-rx-td-label"><span class="fin-rx-pj-badge">PJ</span>' + _escHtml(nome) + '</td>';
    var anual = 0;
    for (var m = 0; m < 12; m++) {
      var mesKey = '2026-' + String(m+1).padStart(2,'0') + '-01';
      var emp    = EMPRESA_DADOS[mesKey] || {};
      var v      = parseFloat(emp[campo] || 0);
      anual += v;
      var isPast = (m+1) <= mesSelecionado;
      html += '<td class="fin-rx-td' + (isPast ? ' fin-rx-past' : ' fin-rx-future') + ' fin-rx-pj-cell">';
      html += v > 0 ? '<span class="fin-val-positive">' + fmt(v) + '</span>' : '<span style="color:#546e7a">–</span>';
      html += '</td>';
    }
    html += '<td class="fin-rx-td-anual fin-val-positive">' + fmt(anual) + '</td>';
    html += '</tr>';
    return html;
  }
```

- [ ] **Step 4: Adicionar CSS para linhas PJ no Raio-X**

Adicionar ao final de `dashboard.css`:
```css
/* Raio-X: linhas PJ */
.fin-rx-row-pj { background: rgba(105,240,174,0.04); }
.fin-rx-pj-cell { font-style: italic; }
.fin-rx-pj-badge {
  display: inline-block;
  font-size: 9px;
  background: rgba(105,240,174,0.2);
  color: #69f0ae;
  border-radius: 3px;
  padding: 1px 4px;
  margin-right: 5px;
  vertical-align: middle;
}
```

- [ ] **Step 5: Testar integração completa**

- Preencher faturamento Jun/2026 e salvar
- Verificar que as linhas "Pró-labore PJ" e "Distribuição de lucros" aparecem no Raio-X
- Verificar que o KPI "Receitas do Mês" inclui o pró-labore
- Verificar que o KPI "Despesas do Mês" inclui DAS + INSS + contabilidade
- Verificar que o donut Empresa exibe DAS e INSS

- [ ] **Step 6: Commit**

```bash
cd /root && git add jake_desktop/static/js/financeiro.js jake_desktop/static/css/dashboard.css
git commit -m "feat(financeiro): empresa integrada no Raio-X e KPIs"
```

---

## Task 7: Salvar memória e atualizar CLAUDE.md

- [ ] **Step 1: Salvar contexto fiscal na memória do Jake**

Criar `/root/.claude/projects/-root/memory/projeto_fiscal_zati.md`:
```markdown
---
name: projeto-fiscal-zati
description: Contexto fiscal da empresa Zati Soluções Digitais — CNPJ, regime, cálculos
metadata:
  type: project
---

Razão Social: Zati Soluções Digitais LTDA
CNPJ: 66.989.646/0001-51
Regime: Simples Nacional Anexo III (mantendo Fator R ≥ 28%)

**Regra fiscal:**
- Pró-labore = 28% do faturamento (mínimo para manter Fator R)
- DAS = 6% do faturamento bruto
- INSS = 11% do pró-labore
- Distribuição de lucros: sem INSS, sem IR (Simples)

**Contador:** Kefferson (Senhor Contábil)
**Emissor NFS-e:** https://www.nfse.gov.br/EmissorNacional
**Conta PJ:** Nubank PJ

**Why:** CNPJ aberto em junho/2026, primeiro recebimento em 19/06/2026
**How to apply:** Usar esses percentuais nos cálculos do módulo financeiro Jake OS
```

- [ ] **Step 2: Atualizar MEMORY.md**

Adicionar linha ao índice `/root/.claude/projects/-root/memory/MEMORY.md`:
```
- [Contexto Fiscal Zati](projeto_fiscal_zati.md) — CNPJ ME, Simples Nacional Anexo III, regras DAS/INSS/pró-labore
```

- [ ] **Step 3: Commit final**

```bash
cd /root && git add jake_desktop/
git commit -m "feat(financeiro): módulo empresa completo — Zati Soluções Digitais"
```
