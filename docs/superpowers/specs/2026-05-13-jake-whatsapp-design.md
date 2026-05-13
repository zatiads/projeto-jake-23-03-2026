# Jake WhatsApp — Design Spec

## Goal

Integrar o Jake ao WhatsApp via Evolution API (self-hosted na VPS), substituindo o Telegram como canal principal de comunicação. O bot responde mensagens do Bruno, envia resumo diário do Gestor IA às 17h, responde perguntas sobre finanças pessoais e envia mensagens programadas ou sob demanda para grupos.

---

## Arquitetura

```
WhatsApp ↔ Evolution API (Docker :8081)
                ↕ webhook POST /webhook
         bot/jake_whatsapp.py (Flask :5051)
                ↕
         Anthropic Claude / DB Neon
                ↕ APScheduler
         Crons: resumo 17h + mensagens agendadas para grupos
```

### Componentes

| Componente | Descrição |
|---|---|
| **Evolution API** | Self-hosted via Docker Compose, porta 8081. Gerencia sessão WhatsApp, recebe/envia mensagens, repassa eventos via webhook. |
| **`bot/jake_whatsapp.py`** | Servidor Flask na porta 5051. Recebe webhook, autentica sender, roteia para handlers. APScheduler interno para crons. |
| **`bot/whatsapp_handlers.py`** | Handlers isolados: chat IA, resumo gestor, financeiro, grupos. |
| **`docker-compose.evolution.yml`** | Docker Compose da Evolution API na raiz `/root`. |
| **`scripts/subir_jake_whatsapp.sh`** | Script de startup do bot. |
| **`/etc/systemd/system/jake-whatsapp.service`** | Systemd com `Restart=always`. |

### Variáveis de ambiente (`.env`)

| Variável | Descrição |
|---|---|
| `EVOLUTION_BASE_URL` | URL base da API, ex: `http://localhost:8081` |
| `EVOLUTION_API_KEY` | API key definida no Docker Compose |
| `WA_INSTANCE` | Nome da instância Evolution, ex: `jake` |
| `WA_AUTHORIZED_JID` | JID do Bruno, ex: `5511999999999@s.whatsapp.net` |
| `WA_GRUPOS_JSON` | JSON array com grupos e configurações de envio agendado |

Formato de `WA_GRUPOS_JSON`:
```json
[
  {
    "nome": "Vielife",
    "jid": "120363XXXXXXXXXX@g.us",
    "msg": "Bom dia, time! 🚀 Semana de resultados!",
    "cron": "08:00",
    "dias": ["mon"]
  }
]
```

---

## Fluxo de dados

### Chat IA

1. Bruno envia mensagem no WhatsApp
2. Evolution API dispara `POST /webhook` para `bot/jake_whatsapp.py`
3. Bot verifica se `sender == WA_AUTHORIZED_JID` — ignora silenciosamente se não for
4. Carrega histórico do DB Neon (tabela `conversa`, namespace `whatsapp`, últimas 40 msgs)
5. Chama Claude `claude-sonnet-4-6` com `PROMPT_ANALISTA` (mesmo prompt do Telegram)
6. Salva mensagens (user + assistant) no DB
7. Envia resposta via `POST {EVOLUTION_BASE_URL}/message/sendText/{WA_INSTANCE}`

### Resumo Gestor IA — 17h diário

1. APScheduler dispara às 17h (America/Sao_Paulo)
2. Consulta DB Neon: tabela `gestor_timeline` — registros do dia atual
3. Formata resumo curto com emojis (máx. ~5 linhas)
4. Envia via `sendText` para `WA_AUTHORIZED_JID`

Exemplo de mensagem:
```
📊 *Resumo do dia — Jake OS*
✅ 3 campanhas analisadas (Queen, Vielife, Piloti)
⚠️ 1 alerta de saldo: Dentto abaixo de R$150
📈 CPA médio hoje: R$12,40
```

Se não houver atividade: `📊 Sem atividades registradas hoje.`

### Financeiro pessoal

1. Bruno pergunta algo financeiro (ex: "quanto gastei esse mês?")
2. Claude identifica intenção financeira no contexto da conversa
3. Handler consulta DB Neon — mesmas tabelas usadas pelo módulo Financeiro do Jake OS
4. Claude formata resposta com os dados reais

### Envio para grupos

**Sob demanda:**
1. Bruno manda "Jake, manda bom dia pro grupo Vielife"
2. Claude identifica intenção de envio para grupo + nome do grupo
3. Handler busca grupo pelo nome no `WA_GRUPOS_JSON`
4. Se não encontrado: responde "Patrão, esse grupo não tá configurado ainda."
5. Se encontrado: envia a mensagem configurada via `sendText` para o JID do grupo

**Agendado:**
1. Na inicialização, bot lê `WA_GRUPOS_JSON`
2. Para cada grupo com `cron` + `dias`, APScheduler agenda o envio
3. No horário: envia a mensagem configurada para o JID do grupo

---

## Tratamento de erros

| Cenário | Comportamento |
|---|---|
| Sender não autorizado | Ignora silenciosamente |
| Claude 529 overloaded | Retry 3x com backoff exponencial (`2^attempt` segundos) |
| Evolution API offline ao responder | Loga erro, não trava o servidor |
| Resumo gestor sem dados | Envia `📊 Sem atividades registradas hoje.` |
| Grupo não encontrado | Responde ao Bruno que o grupo não está configurado |
| Sessão WhatsApp desconectada | Bot verifica status na inicialização e loga alerta com instrução de reconexão via QR |

---

## Segurança

- Apenas `WA_AUTHORIZED_JID` pode interagir com o bot (whitelist de 1 usuário)
- `EVOLUTION_API_KEY` nunca commitada — sempre via `.env`
- Webhook não exposto publicamente — Evolution API e bot rodam na mesma VPS, comunicação local

---

## Arquivos criados/modificados

```
Criar:
  docker-compose.evolution.yml          # Evolution API Docker
  bot/jake_whatsapp.py                  # Flask :5051 + APScheduler
  bot/whatsapp_handlers.py              # Handlers isolados
  scripts/subir_jake_whatsapp.sh        # Script startup
  /etc/systemd/system/jake-whatsapp.service  # Systemd

Modificar:
  .env                                  # Novas variáveis WA_* e EVOLUTION_*
```

---

## Fora do escopo

- Suporte a múltiplos usuários autorizados
- Envio de imagens/áudio via WhatsApp (apenas texto)
- Interface de administração de grupos via UI
- Integração com outros canais além do WhatsApp
