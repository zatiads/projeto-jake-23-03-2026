# Gestor IA Completo via WhatsApp — Design Spec
**Data:** 2026-05-15
**Status:** Aprovado pelo usuário (v2 — issues da revisão corrigidos)

---

## Visão Geral

Expandir o Gestor IA de um agente autônomo silencioso para um gestor semi-autônomo controlado via WhatsApp. O gestor analisa todas as contas diariamente, propõe otimizações, aguarda aprovação do Bruno e só então executa. Tudo via WA, sem precisar abrir Jake OS.

---

## Modo de Operação

**Semi-autônomo:** O gestor nunca executa ações no Meta Ads sem aprovação explícita do Bruno. Ações ficam com `status='pendente'` até aprovadas ou expiradas (timeout 4h). O `varredura_id` pendente é persistido no banco, não em memória, para sobreviver a restarts do bot.

---

## Fluxo Principal — Varredura Diária

```
06:00 cron (systemd/crontab externo)
  1. coletar()     — métricas das 23 contas via Meta API
  2. analisar()    — Claude decide ações e alertas
  3. salvar()      — grava ações com status='pendente' no banco
  4. notificar()   — envia resumo consolidado no WA do Bruno
  5. cron 17h APScheduler DESATIVADO (substituído por esta notificação)

Bruno responde no WA:
  "ok"         → aprova todas as ações pendentes → executa no Meta
  "cancela 2"  → remove ação 2 da lista → executa restantes
  (silêncio)   → após 4h, job de expiração no banco marca como 'expirado'

Após execução:
  → confirmação no WA: "Executei X ações: [lista do que foi feito]"
```

---

## Roteamento de Mensagens no WA (cadeia de prioridade)

O `processar_mensagem()` do `jake_whatsapp.py` seguirá esta ordem:

```
1. Slash-command? (mensagem começa com "/")
   → parser dedicado: /gestor, /saldo, /status, /relatorio, /pausa, /ativa, /historico
   → NUNCA cai no roteador existente

2. Aprovação do gestor? (sem sessão ativa E há varredura pendente no banco)
   → texto é "ok" ou regex r"^cancela\s+\d+$"
   → chama processar_aprovacao()

3. Sessão ativa? (anúncio em andamento, confirmação de público, etc.)
   → _processar_confirmacao() existente — comportamento atual

4. Keywords de gestor? (_eh_gestor_cmd)
   → subir anúncio, pausar campanha, etc.

5. Keywords financeiro?
6. Chat geral com Claude
```

Regra: `/saldo` como slash-command nunca chega ao `_eh_financeiro()`. "ok" como aprovação só é interceptado se não há sessão ativa — se houver sessão de anúncio aberta, o "ok" vai para a sessão. As duas situações simultâneas (sessão ativa + varredura pendente) são improváveis mas o sistema prioriza a sessão ativa; o Bruno pode responder "ok" à varredura após fechar a sessão de anúncio.

---

## Mensagem Matinal (formato)

```
Gestor IA — 15/05 06:00
Analisei 23 contas. 3 acoes para aprovar:

1. PAUSAR AD — Vielife
   "Criativo Botox Maio" | CPL R$87 (media R$52) | freq 3.8

2. ESCALAR ORCAMENTO +15% — Castaldi
   Adset "Leads Advogados" | CPL R$18 (media R$31)

3. REDUZIR ORCAMENTO -20% — Isac Rocha
   Adset "Academia BH" | CPL R$94 (limite R$60)

Alertas (sem acao):
- ODC Massaranduba: freq 2.7, monitorando
- Vielife: saldo projetado acaba em 2 dias

Responda "ok" para aprovar tudo ou "cancela N" para cancelar uma acao.
Expira em 4h.
```

**Regra de numeração:** Somente ações (que executam algo no Meta) recebem número. Alertas são listados separadamente, sem número, e não podem ser "cancelados" via "cancela N". O "cancela N" só se aplica a ações numeradas.

---

## Ações do Gestor (completas)

### Existentes (mantidas)
| Ação | Trigger | Reversível |
|------|---------|-----------|
| `pausar_ad` | CPL > média + 1σ OU freq > 3.5 | Sim |
| `escalar_orcamento` | CPL top ad < média - 40% e freq < 2.0 | Sim |
| `pausar_conta` | saldo < R$30 | Sim |

### Novas ações
| Ação | Trigger | Reversível |
|------|---------|-----------|
| `reativar_ad` | Ad pausado pelo gestor + CPL voltou ao normal nos últimos 7 dias | Sim |
| `reduzir_orcamento` | CPL > limite + 30%, reduz 20% do orçamento diário | Sim |
| `duplicar_ad` | Top ad com CPL 40% abaixo da média e freq < 2.0 | Sim (pausa a duplicata) |

### Novos alertas (sem ação no Meta, sem número na mensagem)
| Alerta | Trigger |
|--------|---------|
| `alerta_frequencia` | freq > 2.5 e < 3.5 |
| `alerta_zero_conversoes` | Campanha ativa com spend > 0 e 0 conversões em 3+ dias |
| `alerta_learning_travado` | Ad com effective_status=LEARNING por >7 dias (requer campo extra na API) |
| `alerta_saldo_projetado` | saldo_remaining / gasto_diario_medio < 3 dias |
| `alerta_sem_veiculacao` | Campanhas ativas mas spend=R$0 nos últimos 2 dias |
| `alerta_comparativo_semanal` | Resumo CPL semana vs semana anterior (toda sexta) |

---

## Comandos via WhatsApp (slash-commands)

Todos começam com `/` — detectados antes de qualquer outro roteamento.

| Comando | Comportamento |
|---------|--------------|
| `/gestor` | Roda varredura manual. Se já houver varredura pendente de aprovação, retorna "há X ações aguardando aprovação (varredura #N). Responda 'ok' ou 'cancela N' primeiro." |
| `/saldo` | Lista saldo atual de todas as contas ativas |
| `/relatorio` | Resumo da semana em texto no WA + PDF disponível no Jake OS |
| `/pausa [cliente]` | Pausa conta do cliente (com confirmação antes de agir) |
| `/ativa [cliente]` | Ativa campanhas do cliente (com confirmação antes de agir) |
| `/status [cliente]` | CPL, frequência, saldo, nome do top ad |
| `/historico` | Últimas 10 ações do gestor com status (aprovado/cancelado/expirado) |

---

## Arquitetura — Mudanças por Arquivo

### `meta/gestor/executor.py`
- Adicionar função `salvar_pendentes(decisoes, perfis, varredura_id, db_conn)`: salva ações com `status='pendente'` SEM chamar Meta API
- Adicionar função `executar_aprovadas(varredura_id, canceladas=[], db_conn)`: busca pendentes, filtra canceladas, executa aprovadas no Meta, atualiza `status` e `aprovado_em`
- `reverter()`: adicionar guard — se `status != 'sucesso'` lança exceção clara ("ação não foi executada, nada a reverter")
- Manter `executar()` existente como função interna usada por `executar_aprovadas()`

### `meta/gestor/analista.py`
- Adicionar regras para `reativar_ad`, `reduzir_orcamento`, `duplicar_ad` no system prompt
- Adicionar detecção dos 6 novos alertas (baseados nos campos extras do coletor)
- `alerta_comparativo_semanal`: calculado com dados da varredura da semana anterior buscados do banco

### `meta/gestor/coletor.py`
- Manter chamada existente `_buscar_insights_ads()` (level=ad, campos atuais)
- Adicionar `_buscar_insights_diarios(token, account_id, days=7)`: level=account, retorna gasto por dia para calcular `gasto_ontem` e `dias_sem_conversao`
- Adicionar campo `effective_status` nos campos da chamada de ads para `alerta_learning_travado`
- Adicionar `_buscar_cpl_semana_anterior(cliente_id, db_conn)`: lê do banco (tabela `gestor_varreduras` + `gestor_acoes`) o CPL médio da semana anterior, sem nova chamada Meta API
- **Impacto de rate limit**: +1 chamada por conta por varredura (dados diários). Com 23 contas, ~23 chamadas extras — dentro dos limites normais da Meta API

### `meta/gestor_agente.py`
- Substituir chamada `executar(decisoes, ...)` por `salvar_pendentes(decisoes, ...)`
- Após salvar, chamar `notificar_whatsapp(varredura_id)` que envia mensagem WA
- Salvar `varredura_id` pendente na tabela `gestor_estado` (ver banco abaixo)
- Manter fluxo de relatório PDF na sexta (inalterado)
- **Remover** o cron APScheduler das 17h de `resumo_gestor()` no `jake_whatsapp.py`

### `bot/whatsapp_handlers.py`
- `enviar_resumo_gestor(varredura_id)`: formata e envia mensagem matinal com ações numeradas + alertas separados
- `processar_aprovacao(texto, jid)`:
  - "ok" → executa todas as pendentes
  - "cancela N" → remove ação N e executa restantes
  - "cancela N" com N inválido → "só tem X ações, manda 'ok' para aprovar ou ignore para cancelar tudo"
- `cmd_saldo()`, `cmd_status(cliente)`, `cmd_relatorio()`, `cmd_historico()`, `cmd_gestor_manual()`
- `_verificar_varredura_pendente()`: consulta `gestor_estado` no banco para saber se há aprovação aguardando

### `bot/jake_whatsapp.py`
- Adicionar parser de slash-commands no topo do `processar_mensagem()`, ANTES de qualquer outra verificação
- Roteamento de "ok"/"cancela N" somente quando não há sessão ativa E há varredura pendente no banco
- Remover o APScheduler job das 17h (`resumo_gestor`)

### Banco de dados

**Tabela `gestor_acoes` — alterações:**
```sql
-- status é VARCHAR (não ENUM PostgreSQL) — apenas adicionar novos valores nos INSERTs
-- Novos valores: 'pendente', 'expirado' (existentes: 'sucesso', 'erro')
ALTER TABLE gestor_acoes
  ADD COLUMN numero_na_varredura INT,       -- posição na mensagem WA (só ações, não alertas)
  ADD COLUMN aprovado_em TIMESTAMP,
  ADD COLUMN cancelado_em TIMESTAMP,
  ADD COLUMN expirado_em TIMESTAMP;

CREATE INDEX idx_gestor_acoes_status_varredura
  ON gestor_acoes(status, varredura_id);
```

**Nova tabela `gestor_estado`:**
```sql
CREATE TABLE IF NOT EXISTS gestor_estado (
  id SERIAL PRIMARY KEY,
  varredura_id INT NOT NULL REFERENCES gestor_varreduras(id),
  status VARCHAR(20) NOT NULL DEFAULT 'aguardando',  -- aguardando, aprovado, expirado
  criado_em TIMESTAMP DEFAULT NOW(),
  resolvido_em TIMESTAMP
);
```

Usada para persistir qual varredura está pendente de aprovação — sobrevive a restarts do bot.

---

## Tratamento de Edge Cases

| Situação | Comportamento |
|----------|--------------|
| Bruno não responde em 4h | Job de expiração (APScheduler a cada 30min) consulta `gestor_estado` + `gestor_acoes` no banco, marca `status='expirado'` e `expirado_em=NOW()`. Próxima varredura começa do zero. |
| "cancela 2" com N inválido | "só tem X ações numeradas. Manda 'ok' para aprovar ou ignore para cancelar tudo em 4h." |
| Erro ao executar ação aprovada | Loga como `status='erro'`, informa no WA qual falhou, continua as demais |
| Varredura sem ações nem alertas | Sem mensagem (silêncio) |
| Varredura só com alertas | Envia mensagem informativa sem pedir aprovação |
| `/gestor` com varredura pendente | "há X ações aguardando aprovação (varredura #N). Responda 'ok' primeiro, ou ignore que expira em Xh." |
| "ok" com sessão de anúncio ativa | Vai para sessão de anúncio (prioridade). Aprovação do gestor pode ser feita após fechar a sessão. |
| Bot reinicia dentro das 4h | `processar_aprovacao()` consulta `gestor_estado` no banco na inicialização e restaura contexto |
| `reverter()` em ação pendente/expirada | Lança exceção: "ação não foi executada no Meta, nada a reverter" |
| Conta sem dados (<14 dias) | Usa `gestor_config` como fallback (comportamento atual, inalterado) |
| `duplicar_ad` aprovado | Cria novo adset com o mesmo criativo; reversão pausa a duplicata |

---

## Critérios de Sucesso

1. Bruno recebe mensagem no WA às 06h com ações numeradas + alertas separados
2. Slash-commands (`/gestor`, `/saldo`, etc.) funcionam sem conflito com roteador existente
3. Resposta "ok" executa todas as ações aprovadas no Meta em < 60s
4. "cancela N" remove ação específica e executa restantes
5. Ações sem aprovação em 4h expiram automaticamente (job persiste no banco, sobrevive a restart)
6. `/historico` mostra ações aprovadas, canceladas e expiradas
7. Novos alertas aparecem na seção de alertas da mensagem matinal quando triggered
8. Sem regressão: subida de anúncios, pausar/ativar campanhas e chat continuam funcionando
