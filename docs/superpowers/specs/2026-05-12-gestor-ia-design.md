# Gestor IA — Design Spec

**Data:** 2026-05-12
**Status:** Aprovado pelo usuário

---

## Visão Geral

Agente autônomo de tráfego que gerencia 28 contas Meta Ads (agências Piloti e Dentto). Roda 1x/dia via cron, analisa o histórico de cada conta com Claude, toma ações de otimização (pausar ads, escalar orçamento), loga tudo no banco, e permite rollback via Jake OS. Toda sexta, gera 2 PDFs executivos (um por agência) com resumo da semana.

**Princípio central:** o agente aprende o perfil de cada conta pelo histórico antes de agir. Não usa thresholds fixos globais — o critério é sempre relativo ao comportamento histórico de cada conta.

---

## Arquitetura

### Pipeline modular — `meta/gestor_agente.py` (orquestrador)

```
cron 06:00 (diário)
    └─► gestor_agente.py
            ├─► meta/gestor/coletor.py      → métricas 30d das 28 contas via Meta API
            ├─► meta/gestor/analista.py     → 1 chamada Claude → decisões por conta
            ├─► meta/gestor/executor.py     → aplica ações no Meta, loga no banco
            └─► meta/gestor/relator.py      → sexta 08:00: gera PDF Piloti + PDF Dentto

cron 08:00 sexta-feira
    └─► relator.py (standalone, invocado pelo orquestrador ou cron separado)
```

### Novos arquivos

```
meta/
  gestor_agente.py          # orquestrador principal
  gestor/
    __init__.py
    coletor.py              # coleta métricas Meta API (sem IA)
    analista.py             # prompt Claude, retorna decisões JSON
    executor.py             # aplica ações + reverter(acao_id)
    relator.py              # gera PDFs com weasyprint
jake_desktop/
  static/js/gestor.js       # IIFE — aba Gestor IA
  static/css/gestor.css     # estilos da aba
```

---

## Banco de Dados

### Tabela `gestor_varreduras`

```sql
CREATE TABLE gestor_varreduras (
    id              SERIAL PRIMARY KEY,
    executado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contas_total    INTEGER NOT NULL,
    contas_ok       INTEGER NOT NULL,
    contas_acao     INTEGER NOT NULL,
    contas_erro     INTEGER NOT NULL,
    resumo_json     JSONB,          -- resumo completo retornado pelo Claude
    duracao_seg     FLOAT,
    status          TEXT NOT NULL   -- 'sucesso' | 'parcial' | 'erro'
);
```

### Tabela `gestor_acoes`

```sql
CREATE TABLE gestor_acoes (
    id              SERIAL PRIMARY KEY,
    varredura_id    INTEGER REFERENCES gestor_varreduras(id),
    cliente_id      INTEGER REFERENCES ad_client_profiles(id),
    account_id      TEXT NOT NULL,
    executado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tipo            TEXT NOT NULL,      -- 'pausar_ad' | 'escalar_orcamento' | 'pausar_conta' | 'alerta_saldo'
    entidade_id     TEXT NOT NULL,      -- ad_id, adset_id ou campaign_id afetado
    entidade_nome   TEXT,
    valor_antes     JSONB,              -- estado anterior (status, budget, etc.)
    valor_depois    JSONB,              -- estado aplicado
    motivo          TEXT,               -- justificativa do Claude
    revertido       BOOLEAN DEFAULT FALSE,
    revertido_em    TIMESTAMPTZ,
    status          TEXT NOT NULL       -- 'sucesso' | 'erro' | 'revertido'
);
```

### Tabela `gestor_relatorios`

```sql
CREATE TABLE gestor_relatorios (
    id           SERIAL PRIMARY KEY,
    gerado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agencia      TEXT NOT NULL,   -- 'piloti' | 'dentto'
    periodo_ini  DATE NOT NULL,
    periodo_fim  DATE NOT NULL,
    arquivo_path TEXT NOT NULL,   -- caminho relativo em static/relatorios/gestor/
    tamanho_kb   INTEGER
);
```

### Alteração em `ad_client_profiles`

Adicionar coluna:
```sql
ALTER TABLE ad_client_profiles
ADD COLUMN gestor_config_json JSONB DEFAULT NULL,
ADD COLUMN gestor_ativo BOOLEAN DEFAULT TRUE;
```

`gestor_config_json` (fallback quando histórico < 14 dias):
```json
{
  "cpl_max": 70,
  "ctr_min": 1.0,
  "freq_max": 3.5,
  "escala_pct": 15,
  "saldo_alerta": 100,
  "saldo_critico": 30
}
```

---

## Módulos Backend

### `coletor.py`

- Para cada conta em `ad_client_profiles WHERE gestor_ativo = TRUE`:
  - Lê `token_key` da linha (ex: `META_TOKEN_PILOTI`) e resolve o token via `os.getenv(token_key)`; nunca usa token global único
  - Busca insights a nível de ad (últimos 30 dias): `spend`, `impressions`, `clicks`, `actions`, `frequency`, `cpm`, `ctr`
  - **Agrega por conta** antes de passar ao analista — retorna métricas sumarizadas por conta (CPL médio, desvio padrão, top/bottom ads), não linhas brutas por ad. Isso garante que o payload caiba no contexto do Claude mesmo com 28 contas e muitos ads.
  - Busca saldo atual da conta (`spend_cap`, `amount_spent`)
  - Calcula CPL médio histórico (30d) e desvio padrão
  - Retorna lista de dicts por conta — sem IA, só dados agregados

### `analista.py`

- Recebe o bloco completo do coletor (todas as contas)
- Monta um único prompt para `claude-sonnet-4-6` com:
  - Perfil histórico de cada conta (CPL médio, desvio, objetivo, ads ativos)
  - Instrução: analisar cada conta pelo seu histórico, decidir ações, retornar JSON estruturado
- Retorna lista de decisões por conta:
```json
[
  {
    "cliente_id": 5,
    "conta": "Implan RS",
    "analise": "CPL 35% acima da média histórica. Ad com frequência 4.2.",
    "acoes": [
      {"tipo": "pausar_ad", "entidade_id": "123456", "motivo": "CPL R$95, freq 4.2"},
      {"tipo": "escalar_orcamento", "entidade_id": "789012", "motivo": "CPL R$38, melhor performer"}
    ],
    "alertas": []
  }
]
```

**Lógica de decisão (instrução ao Claude):**
1. Se conta tem ≥ 14 dias de histórico → analisa pelo perfil histórico (CPL médio ± desvio)
2. Se conta tem < 14 dias → usa `gestor_config_json` como fallback
3. Se nem histórico nem config → apenas monitora, não age
4. Saldo < R$30 → sempre pausa toda a conta, independente de histórico

### `executor.py`

- Recebe decisões do analista
- Para cada ação:
  - Busca estado atual da entidade no Meta (salva em `valor_antes`)
  - Aplica a ação via Meta API
  - Loga em `gestor_acoes` com `valor_antes`, `valor_depois`, `motivo`
- Método `reverter(acao_id)`:
  - Lê `valor_antes` do banco
  - Restaura o estado original via Meta API
  - Atualiza `revertido = TRUE`, `revertido_em = NOW()` na linha original — não cria nova linha

**Helpers Meta API necessários** — adicionar em `meta/meta_api.py` (módulo compartilhado):
```python
atualizar_status_ad(token, ad_id, status)        # status: "ACTIVE" | "PAUSED"
atualizar_status_campanha(token, campaign_id, status)
atualizar_orcamento_conjunto(token, adset_id, daily_budget_cents)  # executor lê escala_pct de gestor_config_json da conta para calcular o novo valor
get_ad(token, ad_id)                              # busca estado atual de um ad
get_adset(token, adset_id)                        # busca estado atual de um adset
```
Estes helpers são usados tanto pelo executor quanto pelo rollback.

### `relator.py`

- Executa toda sexta-feira, chamado pelo orquestrador ao final da varredura das 06:00
- Recebe os dados já agregados do coletor da mesma execução — não refaz queries à Meta API
- Para cada agência (Piloti, Dentto):
  - Busca ações da semana em `gestor_acoes`
  - Usa métricas do coletor já coletadas na mesma execução
  - Chama Claude para gerar texto narrativo por conta
  - Renderiza HTML com os dados
  - Converte para PDF com `weasyprint`
  - Salva em `jake_desktop/static/relatorios/gestor/` com nome `piloti_YYYYMMDD.pdf`
  - Registra na tabela `gestor_relatorios` (tabela dedicada, não em `gestor_varreduras`)

**Estrutura do PDF:**
```
RELATÓRIO SEMANAL — [AGÊNCIA]
Período: DD/MM a DD/MM/YYYY

RESUMO EXECUTIVO
  X contas · Y ações · Z revertidas

POR CONTA:
  [Nome] — Objetivo: MESSAGES
  CPL histórico: R$XX | Esta semana: R$XX
  Ações: [lista] | Resultado: +/- leads
  Status: Saudável / Atenção / Crítico
```

---

## Cron Jobs

```
# Varredura diária
0 6 * * * cd /root && /root/venv/bin/python -m meta.gestor_agente >> /root/logs/gestor.log 2>&1

# Relatório semanal (sexta 08:00) — o orquestrador detecta sexta e chama o relator
# (não precisa de cron separado)
```

---

## Jake OS — Aba "Gestor IA"

### Layout

Dois painéis sempre visíveis (layout C aprovado):

**Painel esquerdo — Timeline**
- Filtros: Tudo / Piloti / Dentto / Alertas
- Eventos cronológicos por data: varreduras, otimizações, alertas de saldo
- Cada evento mostra: tipo (cor), nome da conta, resumo, horário
- Evento selecionado destacado com borda azul

**Painel direito — Detalhe**
- Header: tipo + horário + nome da conta + botão "↩ Reverter tudo"
- Bloco "Análise do Agente": texto do Claude explicando o raciocínio
- Lista de ações: ícone (⏸ pausou / ↑ escalou), descrição, valores antes/depois, botão individual "Reverter"
- Métricas da conta: CPL médio, leads 7d, gasto 7d, saldo

### Sub-abas

**Contas**
- Grid das 28 contas com indicador de saúde (verde / amarelo / vermelho)
- Clique abre modal: histórico de ações + edição de `gestor_config_json` + toggle gestor ativo/inativo por conta

**Relatórios**
- Lista de PDFs gerados (data, agência, tamanho)
- Botão download
- Botão "Gerar agora" (força geração manual)

**Configuração**
- Toggle global "Gestor ativo"
- Horário da varredura (padrão 06:00)
- Log das últimas 10 execuções com status

### Endpoints Flask

```
GET  /api/gestor/varreduras              → lista execuções + status
GET  /api/gestor/acoes?filtros           → lista ações (filtro por data, conta, tipo)
POST /api/gestor/reverter/<acao_id>      → rollback de uma ação
POST /api/gestor/reverter-evento/<varredura_id>  → rollback de todas as ações de um evento
POST /api/gestor/rodar                   → dispara varredura manual em background, requer @login_required (retorna 202 imediatamente; progresso consultável via GET /api/gestor/varreduras)
GET  /api/gestor/relatorios              → lista PDFs
GET  /api/gestor/relatorios/<id>/download → download PDF
GET  /api/gestor/contas                  → lista contas com saúde atual
PATCH /api/gestor/contas/<id>            → atualiza gestor_config_json ou gestor_ativo
```

---

## Dependências Novas

- `weasyprint` — geração de PDF a partir de HTML
- Sem outras dependências — usa `requests`, `anthropic`, `psycopg2` já presentes

---

## Rollback

- Cada ação é atômica e logada com estado anterior
- Rollback individual: botão por linha de ação no painel direito
- Rollback total do evento: botão "↩ Reverter tudo" no header do painel direito
- Reversão atualiza a linha original em `gestor_acoes`: `revertido = TRUE`, `revertido_em = NOW()` — não cria nova linha
- Ações já revertidas não podem ser revertidas novamente (botão desabilitado)

---

## Fluxo de Dados Completo

```
cron 06:00
  → coletor.py busca 30d de dados das 28 contas (Meta API)
  → analista.py envia tudo ao Claude (1 chamada)
  → Claude retorna JSON com decisões por conta
  → executor.py aplica cada ação, salva estado anterior no banco
  → gestor_varreduras + gestor_acoes atualizados

Jake OS (qualquer hora)
  → /api/gestor/acoes → painel esquerdo mostra timeline
  → usuário clica evento → painel direito mostra detalhe
  → usuário clica "Reverter" → /api/gestor/reverter/<id>
  → executor.reverter() restaura estado no Meta

Sexta 08:00 (dentro do cron das 06:00 ou cron separado)
  → relator.py gera PDF Piloti + PDF Dentto
  → salva em jake_desktop/static/relatorios/gestor/
  → disponível para download no Jake OS
```

---

## Fora de Escopo

- Notificações via Telegram (Bruno usa Jake OS)
- Criação de novos anúncios (só otimiza o que existe)
- Gestão de criativos
- Relatório por conta individual (PDF é por agência)
