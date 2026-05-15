# Gestor IA Completo via WhatsApp — Design Spec
**Data:** 2026-05-15
**Status:** Aprovado pelo usuário

---

## Visão Geral

Expandir o Gestor IA de um agente autônomo silencioso para um gestor semi-autônomo controlado via WhatsApp. O gestor analisa todas as contas diariamente, propõe otimizações, aguarda aprovação do Bruno e só então executa. Tudo via WA, sem precisar abrir Jake OS.

---

## Modo de Operação

**Semi-autônomo:** O gestor nunca executa ações no Meta Ads sem aprovação explícita do Bruno. Ações ficam com `status='pendente'` até aprovadas ou expiradas (timeout 4h).

Exceção futura (não nesta versão): ações urgentes como saldo crítico poderão ter aprovação automática após ganho de confiança.

---

## Fluxo Principal — Varredura Diária

```
06:00 cron
  1. coletar()     — métricas das 23 contas via Meta API
  2. analisar()    — Claude decide ações e alertas
  3. salvar()      — grava ações com status='pendente' no banco
  4. notificar()   — envia resumo consolidado no WA do Bruno

Bruno responde no WA:
  "ok"         → aprova todas as ações pendentes → executa no Meta
  "cancela 2"  → remove ação 2 da lista → executa restantes
  (silêncio)   → após 4h, ações expiram automaticamente sem executar

Após execução:
  → confirmação no WA: "Executei X ações: [lista do que foi feito]"
```

---

## Mensagem Matinal (formato)

```
Gestor IA — 15/05 06:00
Analisei 23 contas. 4 otimizacoes encontradas:

1. PAUSAR AD — Vielife
   "Criativo Botox Maio" | CPL R$87 (media R$52) | freq 3.8

2. ESCALAR ORCAMENTO +15% — Castaldi
   Adset "Leads Advogados" | CPL R$18 (media R$31)

3. REDUZIR ORCAMENTO -20% — Isac Rocha
   Adset "Academia BH" | CPL R$94 (limite R$60)

4. ALERTA FREQUENCIA — ODC Massaranduba (sem acao)
   Freq 2.7, monitorando

Responda "ok" para aprovar tudo ou "cancela N" para cancelar uma acao.
Expira em 4h.
```

Alertas informativos aparecem na lista mas não precisam de aprovação — executam zero no Meta.

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
| `duplicar_ad` | Top ad com CPL 40% abaixo da média e freq < 2.0 | Sim |

### Novos alertas (sem ação no Meta)
| Alerta | Trigger |
|--------|---------|
| `alerta_frequencia` | freq > 2.5 e < 3.5 |
| `alerta_zero_conversoes` | Campanha ativa com gasto mas 0 conversões em 3+ dias |
| `alerta_learning_travado` | Ad em aprendizado > 7 dias sem sair do status learning |
| `alerta_saldo_projetado` | Saldo atual / gasto diário médio < 3 dias |
| `alerta_sem_veiculacao` | Campanhas ativas mas gasto = R$0 nos últimos 2 dias |
| `alerta_comparativo_semanal` | Resumo CPL semana vs semana anterior (toda sexta) |

---

## Comandos via WhatsApp

| Comando | Comportamento |
|---------|--------------|
| `/gestor` | Roda varredura manual agora, envia resumo |
| `/saldo` | Lista saldo atual de todas as contas ativas |
| `/relatorio` | Resumo da semana em texto no WA + PDF disponível no Jake OS |
| `/pausa [cliente]` | Pausa conta do cliente (com confirmação antes de agir) |
| `/ativa [cliente]` | Ativa campanhas do cliente (com confirmação antes de agir) |
| `/status [cliente]` | CPL, frequência, saldo, nome do top ad |
| `/historico` | Últimas 10 ações do gestor com status |

---

## Arquitetura — Mudanças por Arquivo

### `meta/gestor/executor.py`
- Adicionar modo `pendente`: salva ações no banco com `status='pendente'` sem chamar Meta API
- Adicionar função `executar_aprovadas(varredura_id, canceladas=[])` que executa apenas as aprovadas
- Manter `reverter()` intacto

### `meta/gestor/analista.py`
- Adicionar regras para `reativar_ad`, `reduzir_orcamento`, `duplicar_ad`
- Adicionar detecção dos 6 novos alertas no system prompt do Claude
- Incluir `alerta_comparativo_semanal` (calculado com dados da varredura anterior)

### `meta/gestor/coletor.py`
- Coletar dados adicionais por conta:
  - `dias_sem_conversao`: dias consecutivos com spend > 0 e conversoes = 0
  - `dias_em_learning`: ads com effective_status = LEARNING há quantos dias
  - `projecao_dias_saldo`: saldo_remaining / gasto_diario_medio
  - `gasto_ontem`: para detectar sem veiculação
  - `cpl_semana_anterior`: para comparativo semanal (busca varredura da semana passada no banco)

### `meta/gestor_agente.py`
- Após `analisar()`, chamar `salvar_pendentes()` em vez de `executar()` diretamente
- Chamar `notificar_whatsapp()` com o resumo formatado
- Manter fluxo de relatório PDF na sexta

### `bot/whatsapp_handlers.py`
- `enviar_resumo_gestor(varredura_id)`: formata e envia mensagem matinal
- `processar_aprovacao(texto, jid)`: interpreta "ok" / "cancela N", executa aprovadas
- `cmd_saldo()`, `cmd_status(cliente)`, `cmd_relatorio()`, `cmd_historico()`
- Timeout: APScheduler verifica a cada 30min ações pendentes com idade > 4h e expira

### `bot/jake_whatsapp.py`
- Roteamento dos novos comandos `/gestor`, `/saldo`, `/status`, `/relatorio`, `/pausa`, `/ativa`, `/historico`
- Handler para respostas de aprovação ("ok", "cancela N")

### Banco de dados
- `gestor_acoes.status`: adicionar valor `'pendente'` e `'expirado'` ao enum (hoje: `'sucesso'`, `'erro'`)
- `gestor_acoes.aprovado_em`: nova coluna TIMESTAMP nullable
- `gestor_acoes.numero_na_varredura`: INT para identificar ação pelo número na mensagem WA
- `gestor_varreduras.notificado_em`: TIMESTAMP de quando o WA foi enviado

---

## Tratamento de Edge Cases

| Situação | Comportamento |
|----------|--------------|
| Bruno não responde em 4h | Ações expiram, nenhuma executada. Próxima varredura começa do zero. |
| "cancela 2" com lista de 1 ação | Jake responde "só tem 1 ação, manda 'ok' para aprovar ou ignore para cancelar" |
| Erro ao executar ação aprovada | Loga como `status='erro'`, informa no WA qual falhou, continua as demais |
| Varredura sem ações | Jake não envia mensagem (silêncio) |
| Varredura com só alertas | Envia mensagem informativa sem pedir aprovação |
| `/gestor` enquanto varredura em andamento | Retorna "já tem uma varredura em andamento, aguarde" |
| Conta sem dados suficientes (<14 dias) | Usa gestor_config como fallback, igual ao comportamento atual |

---

## Critérios de Sucesso

1. Bruno recebe mensagem no WA às 06h com ações propostas
2. Resposta "ok" executa todas as ações no Meta em < 60s
3. "cancela N" remove ação específica e executa o restante
4. Ações sem aprovação em 4h expiram sem executar
5. Todos os 7 comandos funcionam via WA
6. Novos alertas aparecem na mensagem matinal quando triggered
7. `/historico` mostra ações aprovadas, canceladas e expiradas
