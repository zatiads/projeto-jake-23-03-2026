# Spec: Termômetro — Melhorias (tooltip + ativos customizáveis)

**Data:** 2026-04-22
**Módulo:** Jake OS — Financeiro / Carteira de Investimentos
**Feature:** Tooltip enriquecido no gráfico de evolução + ativos customizáveis

---

## Contexto

O módulo Carteira de Investimentos (Projeto Milhão) já possui a aba Termômetro com gráfico de evolução mensal e aba Aportes com 5 ativos fixos. Este spec descreve duas melhorias incrementais:

1. **Tooltip enriquecido:** ao passar o mouse num ponto do gráfico de evolução, exibir patrimônio acumulado, aporte do mês e renda passiva projetada.
2. **Ativos customizáveis:** permitir ao usuário adicionar ativos além dos 5 fixos, com label, cor automática e meta% opcional.

---

## Feature 1 — Tooltip enriquecido no gráfico de evolução

### Comportamento

Ao hover em qualquer ponto do gráfico `#mil-termo-evolucao`, o tooltip exibe:

```
Abr/2026
Patrimônio: R$ 5.308,00
Aporte do mês: R$ 567,00
Renda projetada: R$ 42,46/mês
```

### Cálculo da renda projetada

`renda = patrimônio_acumulado × taxa`

onde `taxa` é lida do campo `#mil-taxa` (Simulador), parseada como `parseFloat(el.value) / 100`. Se o elemento não existir, o valor for NaN ou `<= 0`, usar fallback `0.008` (0,80%/mês).

### Implementação

Mudança exclusiva em `_renderTermoEvolucao()` em `financeiro.js`:

- O array `porMes` (aportes por mês) já é calculado na função. Os arrays `labels`, `dados` (acumulado) e `porMes` são referenciados por closure no callback `tooltip.callbacks.afterBody`.
- O `label` continua mostrando o patrimônio acumulado.
- `afterBody` retorna array de strings: aporte do mês + renda projetada (calculada no momento do hover usando o índice `ctx[0].dataIndex`).

### Sem mudança de backend ou HTML

Esta feature é puramente JS.

---

## Feature 2 — Ativos customizáveis

### Banco de Dados

#### Tabela `ativos_personalizados`

Nova tabela PostgreSQL, criada no startup via `_init_ativos_personalizados_table()`:

```sql
CREATE TABLE IF NOT EXISTS ativos_personalizados (
    id SERIAL PRIMARY KEY,
    key VARCHAR(50) UNIQUE NOT NULL,
    label VARCHAR(100) NOT NULL,
    cor VARCHAR(20) NOT NULL,
    meta NUMERIC(5,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

`key VARCHAR(50)` alinhado com `aportes_investimento.ativo VARCHAR(50)` para garantir integridade referencial implícita.

#### Geração da key

Server-side: lowercase, strip caracteres não-alfanuméricos exceto espaço, espaços→`_`, prefixo `custom_`, truncado a 50 chars no total. Ex: `"FII XP"` → `custom_fii_xp`.

Se a key gerada já existir na tabela: retornar `{error: "Ativo com nome similar já existe (key: custom_fii_xp)"}`, status 400 — mensagem inclui a key conflitante para clareza.

### Paleta de cores automáticas

Sequência fixada no backend (round-robin pelo `count(*) % 6` de ativos já cadastrados):

```python
PALETA_CUSTOM = ['#ff8a65', '#ce93d8', '#80deea', '#a5d6a7', '#ffcc02', '#ef9a9a']
```

### Backend — `app.py`

#### Inicialização

`_init_ativos_personalizados_table()` chamada no startup após `_init_aportes_table()`. Usa o padrão try/finally com `conn.close()`.

#### `GET /api/financeiro/ativos`

Retorna os 5 ativos fixos + os customizados do banco, na ordem: fixos primeiro (ordem hardcoded), depois customizados por `id ASC`.

Response:
```json
[
  {"key": "tesouro_selic", "label": "Tesouro Selic", "cor": "#00e5ff", "meta": 30, "fixo": true},
  {"key": "cdb",           "label": "CDB",           "cor": "#ffd740", "meta": 25, "fixo": true},
  {"key": "lci_lca",       "label": "LCI/LCA",       "cor": "#69f0ae", "meta": 15, "fixo": true},
  {"key": "ivvb11",        "label": "IVVB11",         "cor": "#ff5252", "meta": 20, "fixo": true},
  {"key": "gold11",        "label": "GOLD11",         "cor": "#7c4dff", "meta": 10, "fixo": true},
  {"key": "custom_fii_xp", "label": "FII XP",         "cor": "#ff8a65", "meta": 5,  "fixo": false}
]
```

#### `POST /api/financeiro/ativos`

Body: `{label, meta}` (`meta` opcional, default 0)

Validações:
- `label` obrigatório, não vazio após strip, máx 100 chars
- `meta` deve ser número entre 0 e 100 (inclusive); se ausente, usa 0
- `key` gerada server-side conforme regra acima
- Em erro de unicidade (key já existe): `{error: "Ativo com nome similar já existe (key: <key>)"}`, status 400

Response de sucesso: `{ok: true, ativo: {key, label, cor, meta, fixo: false}}`

#### `DELETE /api/financeiro/ativos/<key>`

- Se key pertencer aos 5 fixos: `{error: "ativo fixo não pode ser removido"}`, status 400
- Se key não existe na tabela: `{error: "not found"}`, status 404
- Sucesso: `{ok: true}`
- **Aportes existentes com esse ativo NÃO são deletados.** No Termômetro, aportes órfãos são incluídos no patrimônio total mas não aparecem no donut/barras de alocação (comportamento intencional — ativo foi removido da carteira mas o dinheiro investido conta no patrimônio total).

### Frontend — `financeiro.js`

#### Carregamento dinâmico de ATIVOS_CARTEIRA

- `ATIVOS_CARTEIRA` é inicializado como `[]` (vazio) e populado por `carregarAtivos()`.
- `carregarAtivos()`: faz GET `/api/financeiro/ativos`, popula `ATIVOS_CARTEIRA`, chama `_popularSelectAtivos()` e `renderAtivos()`, depois chama `carregarAportes()` (que já chama `renderTermometro()` e `renderAportes()` ao concluir). Ou seja: `carregarAportes()` é sempre chamado dentro de `carregarAtivos()` — não há segunda chamada no `initSubTabsMilhao()`.
- `carregarAtivos()` é chamada de dentro de `initSubTabsMilhao()` (substituindo a chamada direta a `carregarAportes()`).
- Ao navegar de volta para a aba (re-enter), `_milSubTabsInited` e `_milhaoInited` guards já existentes impedem re-inicialização.

#### `_popularSelectAtivos()`

Reconstrói o `<select id="mil-aporte-ativo">` com as options atuais de `ATIVOS_CARTEIRA`. Preserva o valor selecionado se possível.

#### Seção "Gerenciar Ativos" na aba Aportes

Adicionada abaixo da tabela de aportes em `dashboard.html`:

```html
<div class="mil-gerenciar-ativos">
  <div class="mil-gerenciar-header">
    <span>Ativos da carteira</span>
    <button id="mil-novo-ativo-btn" class="mil-novo-ativo-btn">+ Novo Ativo</button>
  </div>
  <div id="mil-novo-ativo-form" class="mil-novo-ativo-form hidden">
    <input type="text" id="mil-ativo-label" placeholder="Nome do ativo" maxlength="100">
    <input type="number" id="mil-ativo-meta" placeholder="Meta % (opcional)" min="0" max="100" step="0.1">
    <button id="mil-ativo-submit">Adicionar</button>
    <button id="mil-ativo-cancel" type="button">Cancelar</button>
    <div id="mil-ativo-status"></div>
  </div>
  <div id="mil-ativos-lista">
    <!-- populado via JS -->
  </div>
</div>
```

#### `renderAtivos()`

Renderiza `#mil-ativos-lista` com chips para cada ativo em `ATIVOS_CARTEIRA`:
- Chip: `●` na cor do ativo + label + `(meta X%)` se meta > 0 + botão ✕ apenas se `fixo === false`
- ✕ chama `deletarAtivo(key)`

#### `adicionarAtivo(label, meta)`

POST `/api/financeiro/ativos`. Em sucesso: `ATIVOS_CARTEIRA.push(res.ativo)`, chama `_popularSelectAtivos()`, `renderAtivos()`, e `renderTermometro()` (para atualizar donut com novo ativo).

#### `deletarAtivo(key)`

DELETE `/api/financeiro/ativos/<key>`. Em sucesso: remove de `ATIVOS_CARTEIRA`, chama `_popularSelectAtivos()`, `renderAtivos()`, e `renderTermometro()`.

### CSS — `dashboard.css`

Novos estilos `.mil-gerenciar-*` e `.mil-novo-ativo-*` (padrão dark glassmorphism existente).

---

## Fluxo de Dados

```
initSubTabsMilhao()
  └── carregarAtivos()               ← substitui carregarAportes() direto
        └── ATIVOS_CARTEIRA = data
        └── _popularSelectAtivos()
        └── renderAtivos()
        └── carregarAportes()        ← chama renderTermometro() + renderAportes()

Usuário adiciona ativo
  └── POST /api/financeiro/ativos
  └── ATIVOS_CARTEIRA.push(res.ativo)
  └── _popularSelectAtivos() + renderAtivos() + renderTermometro()

Usuário deleta ativo
  └── DELETE /api/financeiro/ativos/<key>
  └── ATIVOS_CARTEIRA.splice(idx)
  └── _popularSelectAtivos() + renderAtivos() + renderTermometro()
```

---

## Critérios de Aceitação

1. Tooltip do gráfico de evolução exibe: mês, patrimônio acumulado, aporte do mês e renda projetada
2. Renda projetada usa taxa do Simulador; se ausente, NaN ou ≤ 0: fallback 0,80%/mês
3. Usuário pode adicionar ativo com label (obrigatório) e meta% (opcional)
4. Ativo customizado aparece no `<select>` de aportes e nos gráficos do Termômetro
5. Usuário pode deletar ativo customizado; ativos fixos não podem ser deletados (backend + frontend)
6. Aportes de ativo deletado somem ao patrimônio total mas não aparecem no donut/barras (comportamento intencional e documentado)
7. Cor é auto-atribuída da paleta sem necessidade de input do usuário
8. `ATIVOS_CARTEIRA` sempre reflete o estado atual (fixos + customizados)
9. Ao recarregar a página, ativos customizados persistem (vêm do banco)
10. Navegar para fora e de volta para Financeiro não reinicializa `ATIVOS_CARTEIRA` (guards existentes)
11. Todos os testes existentes continuam passando
