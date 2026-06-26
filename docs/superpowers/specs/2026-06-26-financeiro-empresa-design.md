# Design: Módulo Financeiro — Seção Empresa (Zati Soluções Digitais)

**Data:** 2026-06-26
**Status:** Aprovado para implementação

---

## Contexto

Bruno abriu CNPJ ME (Zati Soluções Digitais LTDA, 66.989.646/0001-51) em junho/2026. O módulo financeiro atual só cobre finanças pessoais. Precisa de uma seção PJ integrada com cálculo fiscal automático (Simples Nacional Anexo III, Fator R ≥ 28%).

---

## O que muda

### 1. Banco de Dados — Nova tabela `fin_empresa_mensal`

```sql
CREATE TABLE fin_empresa_mensal (
  id                  SERIAL PRIMARY KEY,
  mes_ano             DATE NOT NULL UNIQUE,
  faturamento_bruto   NUMERIC(12,2) DEFAULT 0,
  pro_labore          NUMERIC(12,2) DEFAULT 0,
  distribuicao        NUMERIC(12,2) DEFAULT 0,
  mensalidade_contab  NUMERIC(12,2) DEFAULT 0,
  outras_despesas_pj  NUMERIC(12,2) DEFAULT 0
);
```

Campos calculados (DAS, INSS, total impostos, líquido) ficam **só no frontend** — são sempre derivados dos persistidos.

### 2. Backend — Novos endpoints em `blueprints/financeiro.py`

| Método | Rota | Ação |
|--------|------|------|
| GET | `/api/financeiro/empresa` | Lista todos os meses (ordenado DESC) |
| PUT | `/api/financeiro/empresa/<mes_ano>` | Upsert de um mês (formato: `2026-06-01`) |

Nenhum DELETE — dados fiscais nunca são apagados, apenas corrigidos via PUT.

### 3. Frontend — Seção "Empresa" no HTML (`dashboard.html`)

Nova seção dentro de `#fin-pane-visao-geral`, logo acima do Raio-X pessoal.

Layout em cards:
- **Card Entradas PJ:** Faturamento bruto (input), Pró-labore (input, pré-preenchido com 28%), Distribuição de lucros (input)
- **Card Impostos (auto):** DAS 6%, INSS 11%, Total impostos, Líquido PJ — todos calculados em tempo real
- **Card Despesas PJ:** Mensalidade contabilidade (input), Outras despesas PJ (input)
- Botão "Salvar" → PUT no endpoint
- Linha de destaque: "Receita PJ que entra no pessoal = Pró-labore + Distribuição = R$ ---"

**Lógica de cálculo (JS, tempo real):**
- Pró-labore sugerido = faturamento × 28% (editável manualmente)
- DAS = faturamento × 6%
- INSS = pró-labore × 11%
- Total impostos = DAS + INSS
- Líquido PJ = faturamento − total impostos − mensalidade_contab − outras_despesas_pj
- Receita PJ pessoal = pró-labore + distribuição

### 4. Frontend — Raio-X: linhas automáticas nas Entradas

As linhas `Pró-labore` e `Distribuição de lucros` são injetadas automaticamente nas entradas do Raio-X com base nos dados da tabela `fin_empresa_mensal`. São somente-leitura (sem edição inline).

A linha legada `ME/Impostos` nas fixas é removida do `RAIOX_PADRAO`.

### 5. Frontend — 3 donuts substituem o donut único

O card atual "Divisão de Despesas" é substituído por 3 cards menores lado a lado:

| Canvas | Título | Dados |
|--------|--------|-------|
| `fin-chart-donut-fixas` | Despesas Fixas | `RAIOX.fixas` do mês |
| `fin-chart-donut-variaveis` | Despesas Variáveis | `RAIOX.variaveis` do mês |
| `fin-chart-donut-empresa` | Despesas Empresa | contabilidade + outras + DAS + INSS do mês |

### 6. Integração com totais do Raio-X

`raixoTotaisMensais()` passa a somar as despesas PJ no saldo mensal. O KPI "Saldo do Mês" refletirá: receitas pessoais + receita PJ − fixas − variáveis − despesas empresa.

---

## Fora do escopo

- Histórico retroativo jan–jun/2026 (preenchimento manual mês a mês)
- Cálculo automático do Fator R dos últimos 12 meses
- Emissão ou controle de NFS-e
- Checklist de regularização fiscal

---

## Arquivos alterados

1. `jake_desktop/blueprints/financeiro.py` — 2 novos endpoints + CREATE TABLE no boot
2. `jake_desktop/templates/dashboard.html` — seção empresa + 3 donuts
3. `jake_desktop/static/js/financeiro.js` — lógica empresa, 3 funções renderDonut, injeção no Raio-X
