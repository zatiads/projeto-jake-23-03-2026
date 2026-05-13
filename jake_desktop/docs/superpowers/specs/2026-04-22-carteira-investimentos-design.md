# Spec: Carteira de Investimentos — Projeto Milhão

**Data:** 2026-04-22
**Módulo:** Jake OS — Financeiro Pessoal
**Feature:** Histórico de aportes + Termômetro de patrimônio

---

## Contexto

O módulo Financeiro do Jake OS já tem uma aba "Projeto Milhão" com uma calculadora de simulação. O Bruno quer rastrear aportes reais mês a mês por ativo (Tesouro Selic, CDB, LCI/LCA, IVVB11, GOLD11), visualizar o patrimônio acumulado e acompanhar o desvio vs. alocação alvo do Roadmap R$1M.

### Carteira alvo (Roadmap R$1M)
| Ativo | % Alvo |
|---|---|
| Tesouro Selic (LFT) | 30% |
| CDB pós-fixado | 25% |
| LCI/LCA | 15% |
| ETF IVVB11 | 20% |
| GOLD11 | 10% |

---

## Decisões de Design

- **Layout:** 3 sub-tabs na aba Projeto Milhão — Simulador (existente), Termômetro (novo), Aportes (novo)
- **Termômetro:** layout vertical compacto — número grande → barra de progresso → donut + barras de alocação → gráfico de evolução
- **Aportes:** formulário fixo no topo + tabela de histórico abaixo
- **Registro de aporte:** usuário especifica manualmente mês/ano, ativo e valor (não há divisão automática)
- **Patrimônio:** calculado dinamicamente a partir dos aportes registrados (sem campo manual)
- **Duplicatas:** permitidas — múltiplos aportes no mesmo mês/ativo são somados; cada linha da tabela é um aporte independente
- **sincronizarPatrimonioMilhao():** a função existente sincroniza o campo `#mil-patrimonio` da calculadora (Simulador) com o acumulado do Raio-X. Esse comportamento é mantido sem alteração. O patrimônio do Termômetro é calculado de forma independente, a partir dos aportes registrados.

---

## Arquitetura

### 1. Banco de Dados

Nova tabela PostgreSQL (Neon), criada no startup da aplicação via `_init_aportes_table()`:

```sql
CREATE TABLE IF NOT EXISTS aportes_investimento (
    id SERIAL PRIMARY KEY,
    mes_ano DATE NOT NULL,
    ativo VARCHAR(50) NOT NULL,
    valor NUMERIC(12, 2) NOT NULL CHECK (valor > 0),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aportes_mes_ano ON aportes_investimento(mes_ano);
```

`mes_ano` armazena sempre o primeiro dia do mês (ex: `2026-04-01`). A normalização é feita server-side via `DATE_TRUNC('month', %s::date)`.

### 2. Backend (`jake_desktop/app.py`)

#### Inicialização

Adicionar `_init_aportes_table()` e chamá-la dentro da função `_init_db()` ou `_init_rotina_tables()` existente (padrão DDL-at-startup do projeto):

```python
def _init_aportes_table():
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
            );
            CREATE INDEX IF NOT EXISTS idx_aportes_mes_ano ON aportes_investimento(mes_ano);
        """)
        conn.commit()
    finally:
        conn.close()
```

#### `GET /api/financeiro/aportes`

- Retorna todos os aportes ordenados por `mes_ano DESC, id DESC`
- Response: `[{id, mes_ano: "2026-04-01", ativo, valor}, ...]`

#### `POST /api/financeiro/aportes`

- Body: `{mes_ano: "2026-04-01", ativo: "ivvb11", valor: 113.00}`
- Validações:
  - `mes_ano` obrigatório; normalizado server-side com `DATE_TRUNC('month', %s::date)`
  - `ativo` deve ser um de: `tesouro_selic`, `cdb`, `lci_lca`, `ivvb11`, `gold11`
  - `valor` obrigatório e `> 0`
- Em erro de validação: `{error: "mensagem"}`, status 400
- Response de sucesso: `{ok: true, id: <novo_id>}`

#### `DELETE /api/financeiro/aportes/<id>`

- Remove pelo id
- Se `rowcount == 0` (id não existe): retorna `{error: "not found"}`, status 404
- Response de sucesso: `{ok: true}`

### 3. Frontend

#### `jake_desktop/templates/dashboard.html`

O conteúdo atual de `#fin-pane-milhao` (linhas ~1514–1636) é envolvido por um pane `simulador`. Estrutura nova:

```html
<div id="fin-pane-milhao" class="fin-tab-pane">
  <!-- sub-tab bar -->
  <div class="mil-subtab-bar">
    <button class="mil-subtab-btn active" data-subtab="simulador">Simulador</button>
    <button class="mil-subtab-btn" data-subtab="termometro">Termômetro</button>
    <button class="mil-subtab-btn" data-subtab="aportes">Aportes</button>
  </div>

  <!-- simulador: conteúdo atual movido para cá, sem alteração -->
  <div id="mil-pane-simulador" class="mil-subtab-pane active">
    <!-- ... todo HTML existente do Projeto Milhão ... -->
  </div>

  <!-- termômetro -->
  <div id="mil-pane-termometro" class="mil-subtab-pane">
    <div id="mil-termo-patrimonio">...</div>
    <div id="mil-termo-barra">...</div>
    <div id="mil-termo-donut-wrap">
      <canvas id="mil-termo-donut"></canvas>
    </div>
    <div id="mil-termo-barras-ativos">...</div>
    <canvas id="mil-termo-evolucao"></canvas>
  </div>

  <!-- aportes -->
  <div id="mil-pane-aportes" class="mil-subtab-pane">
    <form id="mil-aporte-form">
      <input type="month" id="mil-aporte-mes">
      <select id="mil-aporte-ativo">...</select>
      <input type="number" id="mil-aporte-valor">
      <button type="submit">+ Adicionar</button>
    </form>
    <table id="mil-aporte-table">
      <thead><tr><th>Mês</th><th>Ativo</th><th>Valor</th><th></th></tr></thead>
      <tbody></tbody>
    </table>
    <!-- estado vazio, exibido quando APORTES.length === 0 -->
    <div id="mil-aporte-empty">Nenhum aporte registrado ainda.</div>
  </div>
</div>
```

#### `jake_desktop/static/js/financeiro.js`

Variável de estado adicional no módulo:

```js
var APORTES = [];  // carregado da API
var chartTermoDonut   = null;  // instância Chart.js — destruir antes de re-criar
var chartTermoEvolucao = null; // idem
```

Constante de configuração dos ativos:

```js
var ATIVOS_CARTEIRA = [
  { key: 'tesouro_selic', label: 'Tesouro Selic', cor: '#00e5ff', meta: 30 },
  { key: 'cdb',           label: 'CDB',           cor: '#ffd740', meta: 25 },
  { key: 'lci_lca',       label: 'LCI/LCA',       cor: '#69f0ae', meta: 15 },
  { key: 'ivvb11',        label: 'IVVB11',         cor: '#ff5252', meta: 20 },
  { key: 'gold11',        label: 'GOLD11',         cor: '#7c4dff', meta: 10 },
];
```

Novas funções:

- **`initSubTabsMilhao()`** — bind nos `.mil-subtab-btn`; ativa pane correspondente. Chamada de dentro de `initProjetoMilhao()` com guard de idempotência (`if (_milSubTabsInited) return; _milSubTabsInited = true`). Ao ativar sub-tab `termometro`, chama `renderTermometro()`. Ao ativar `aportes`, chama `renderAportes()`.
- **`carregarAportes()`** — fetch GET, popula `APORTES`, chama `renderTermometro()` e `renderAportes()`
- **`renderTermometro()`** — calcula patrimônio total e por ativo a partir de `APORTES`; destrói `chartTermoDonut`/`chartTermoEvolucao` antes de re-criar; **estado vazio:** exibe `"Nenhum aporte registrado. Vá à aba Aportes para começar."`, patrimônio R$0, barra 0%, sem gráficos
- **`renderAportes()`** — renderiza tabela com `APORTES` ordenados mais recente primeiro; **estado vazio:** exibe `#mil-aporte-empty` e oculta `<tbody>`
- **`adicionarAporte(dados)`** — POST, em sucesso adiciona ao `APORTES` local e re-renderiza Termômetro + Aportes
- **`deletarAporte(id)`** — DELETE, em sucesso remove de `APORTES` e re-renderiza

#### `jake_desktop/static/css/dashboard.css`

Novos estilos (seguindo padrão `.mil-*` e `.fin-*` existentes):
- `.mil-subtab-bar` / `.mil-subtab-btn` / `.mil-subtab-btn.active` / `.mil-subtab-pane` / `.mil-subtab-pane.active`
- `.mil-termo-patrimonio`, `.mil-termo-barra`, `.mil-termo-ativo-bar`
- `.mil-aporte-form`, `.mil-aporte-table`, `.mil-aporte-empty`

---

## Fluxo de Dados

```
initProjetoMilhao()
  └── initSubTabsMilhao()     ← novo, idempotente
  └── carregarAportes()       ← novo, popula APORTES

Usuário clica sub-tab Termômetro
  └── renderTermometro()      ← recalcula a partir de APORTES

Usuário registra aporte (form submit)
  └── POST /api/financeiro/aportes
  └── APORTES.push(novo)
  └── renderTermometro() + renderAportes()

Usuário deleta aporte (✕)
  └── DELETE /api/financeiro/aportes/<id>
  └── APORTES.splice(idx, 1)
  └── renderTermometro() + renderAportes()
```

---

## Critérios de Aceitação

1. Usuário consegue registrar aporte: mês/ano, ativo (dos 5 da carteira) e valor > 0
2. Tabela exibe histórico do mais recente para o mais antigo
3. Estado vazio da tabela exibe mensagem orientativa
4. Termômetro exibe patrimônio total correto (soma de todos os aportes)
5. Barra de progresso reflete % da meta R$1M
6. Donut + barras mostram % atual de cada ativo vs. meta alvo
7. Gráfico de linha mostra evolução mensal do patrimônio acumulado
8. Termômetro com zero aportes exibe estado vazio sem erros de JS
9. Deletar aporte atualiza Termômetro e tabela imediatamente
10. Sub-tabs navegam corretamente sem afetar a calculadora (Simulador) existente
11. `sincronizarPatrimonioMilhao()` continua funcionando normalmente (campo `#mil-patrimonio` do Simulador)
12. Chart.js não lança erro "Canvas already in use" em re-entradas
