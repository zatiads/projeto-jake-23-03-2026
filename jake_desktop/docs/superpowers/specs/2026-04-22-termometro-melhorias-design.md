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

onde `taxa` é lida do campo `#mil-taxa` (Simulador), parseada como float, dividida por 100. Se o elemento não existir ou o valor for inválido, usar fallback `0.008` (0,80%/mês).

### Implementação

Mudança exclusiva em `_renderTermoEvolucao()` em `financeiro.js`:

- O array `porMes` (aportes por mês) já é calculado na função. Antes de criar o Chart, armazená-lo em variável local e referenciá-lo por closure no callback `tooltip.callbacks.afterBody`.
- O `label` continua mostrando o patrimônio acumulado.
- `afterBody` retorna array de strings com aporte do mês e renda projetada.

### Sem mudança de backend ou HTML

Esta feature é puramente JS.

---

## Feature 2 — Ativos customizáveis

### Banco de Dados

Nova tabela PostgreSQL, criada no startup via `_init_ativos_personalizados_table()`:

```sql
CREATE TABLE IF NOT EXISTS ativos_personalizados (
    id SERIAL PRIMARY KEY,
    key VARCHAR(80) UNIQUE NOT NULL,
    label VARCHAR(100) NOT NULL,
    cor VARCHAR(20) NOT NULL,
    meta NUMERIC(5,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

`key` é gerada server-side a partir do label: lowercase, espaços→`_`, caracteres especiais removidos, prefixo `custom_`. Ex: `"FII XP"` → `custom_fii_xp`. Unicidade garantida pelo índice UNIQUE.

### Paleta de cores automáticas

Sequência fixada no backend (round-robin pelo count de ativos já cadastrados):

```python
PALETA_CUSTOM = ['#ff8a65', '#ce93d8', '#80deea', '#a5d6a7', '#ffcc02', '#ef9a9a']
```

### Backend — `app.py`

#### Inicialização

```python
def _init_ativos_personalizados_table():
    # CREATE TABLE IF NOT EXISTS ativos_personalizados ...
    # chamada em _init_aportes_table() ou sequência de startup
```

#### `GET /api/financeiro/ativos`

Retorna os 5 ativos fixos + os customizados do banco, na ordem: fixos primeiro, depois customizados por `id ASC`.

Response:
```json
[
  {"key": "tesouro_selic", "label": "Tesouro Selic", "cor": "#00e5ff", "meta": 30, "fixo": true},
  ...
  {"key": "custom_fii_xp", "label": "FII XP", "cor": "#ff8a65", "meta": 5, "fixo": false}
]
```

Campo `fixo: true` nos 5 fixos, `fixo: false` nos customizados.

#### `POST /api/financeiro/ativos`

Body: `{label, meta}` (`meta` opcional, default 0)

Validações:
- `label` obrigatório, não vazio, máx 100 chars
- `meta` entre 0 e 100 (inclusive)
- `key` gerada server-side; se já existir: retorna `{error: "ativo já existe"}`, status 400

Response de sucesso: `{ok: true, ativo: {key, label, cor, meta, fixo: false}}`

#### `DELETE /api/financeiro/ativos/<key>`

- Rejeita keys dos 5 fixos: retorna `{error: "ativo fixo não pode ser removido"}`, status 400
- Se key não existe: `{error: "not found"}`, status 404
- Sucesso: `{ok: true}`
- **Aportes existentes com esse ativo NÃO são deletados** — ficam orfãos com label genérico no frontend.

### Frontend — `financeiro.js`

#### Carregamento dinâmico de ATIVOS_CARTEIRA

- `ATIVOS_CARTEIRA` deixa de ser constante inicializada inline. Passa a ser populada por `carregarAtivos()`.
- `carregarAtivos()` faz GET `/api/financeiro/ativos`, popula `ATIVOS_CARTEIRA`, então chama `_popularSelectAtivos()` e re-renderiza Termômetro e Aportes se já carregados.
- `carregarAtivos()` é chamada de dentro de `initSubTabsMilhao()`, antes de `carregarAportes()`.

#### `_popularSelectAtivos()`

Reconstrói o `<select id="mil-aporte-ativo">` com as options atuais de `ATIVOS_CARTEIRA`.

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
    <!-- populado via JS: chips com nome + cor + botão ✕ nos customizados -->
  </div>
</div>
```

#### `renderAtivos()`

Renderiza `#mil-ativos-lista` com chips para cada ativo em `ATIVOS_CARTEIRA`:
- Cada chip: `●` na cor do ativo + label + meta% se > 0 + botão ✕ apenas se `fixo === false`
- ✕ chama `deletarAtivo(key)`

#### `adicionarAtivo(label, meta)`

POST `/api/financeiro/ativos`, em sucesso: push no `ATIVOS_CARTEIRA`, re-renderiza select + lista de ativos.

#### `deletarAtivo(key)`

DELETE `/api/financeiro/ativos/<key>`, em sucesso: remove de `ATIVOS_CARTEIRA`, re-renderiza select + lista + Termômetro.

### CSS — `dashboard.css`

Novos estilos `.mil-gerenciar-*` e `.mil-novo-ativo-*` (padrão dark glassmorphism existente).

---

## Fluxo de Dados

```
initSubTabsMilhao()
  └── carregarAtivos()          ← novo, popula ATIVOS_CARTEIRA
        └── _popularSelectAtivos()
        └── carregarAportes()   ← já existente

Usuário adiciona ativo
  └── POST /api/financeiro/ativos
  └── ATIVOS_CARTEIRA.push(novo)
  └── _popularSelectAtivos() + renderAtivos()

Usuário deleta ativo
  └── DELETE /api/financeiro/ativos/<key>
  └── ATIVOS_CARTEIRA.splice(idx)
  └── _popularSelectAtivos() + renderAtivos() + renderTermometro()
```

---

## Critérios de Aceitação

1. Tooltip do gráfico de evolução exibe: mês, patrimônio acumulado, aporte do mês e renda projetada
2. Renda projetada usa taxa do Simulador (fallback 0,80%)
3. Usuário pode adicionar ativo com label e meta% opcional
4. Ativo customizado aparece no `<select>` de aportes e nos gráficos do Termômetro
5. Usuário pode deletar ativo customizado; ativos fixos não podem ser deletados
6. Aportes existentes de ativo deletado não somem (ficam com label genérico)
7. Cor é auto-atribuída da paleta sem necessidade de input do usuário
8. `ATIVOS_CARTEIRA` sempre reflete o estado atual (fixos + customizados)
9. Ao recarregar a página, ativos customizados persistem (vêm do banco)
10. Todos os testes existentes continuam passando
