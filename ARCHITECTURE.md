# Jake IA — Arquitetura do Sistema

**Última atualização:** 2026-06-10  
**Servidor:** VPS Contabo Linux, IP `95.111.252.131`

---

## Visão Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERFACES                               │
│  Jake OS (porta 5050)  │  Telegram Bots  │  WhatsApp Bot (5052) │
└────────────┬───────────┴────────┬────────┴──────────┬──────────┘
             │                   │                    │
┌────────────▼───────────────────▼────────────────────▼──────────┐
│                    CAMADA DE LÓGICA                             │
│  Flask SPA (app.py)  │  bot/jake_telegram.py  │  jake_whatsapp │
│  Meta Ads routes     │  bot/base_bot.py        │  Evolution API │
│  Social Brief        │  bot/jake_pessoal.py    │  wa_crons.py   │
│  Criativos / Copy    │  bot/jake_viagem.py     │                │
└────────────┬─────────────────────────────────────────┬─────────┘
             │                                         │
┌────────────▼─────────────────┐  ┌────────────────────▼────────┐
│     INFRAESTRUTURA            │  │        APIs EXTERNAS        │
│  core/db.py (Neon/PG)        │  │  Anthropic (Claude)         │
│  core/sync_planilha.py       │  │  OpenAI (GPT-4o, Whisper)   │
│  meta/meta_api.py            │  │  Replicate (Flux 1.1 Pro)   │
│  meta/gestor_agente.py       │  │  Meta Ads Graph API v21.0   │
│  meta/mcp_server.py          │  │  Google Sheets (gspread)    │
└──────────────────────────────┘  └─────────────────────────────┘
```

---

## Módulos

### `jake_desktop/` — Jake OS (Flask SPA)
- **Porta:** 5050
- **Processo:** `jake-ia.service` (systemd)
- **Venv:** `/root/jake_desktop/.venv/`
- **Entrypoint:** `app.py` (~9.500 linhas, monolito)
- **Auth:** sessão Flask, credenciais em `ADMIN_EMAIL`/`ADMIN_PASSWORD`
- **Restart:** `systemctl restart jake-ia`

Módulos funcionais ativos no app.py:
| Módulo | Rota base | JS |
|--------|-----------|-----|
| Painel / Dashboard | `/api/now`, `/api/weather` | `main.js` |
| Gestor IA | `/api/gestor/*` | `gestor.js`, `planejador.js` |
| Criativos | `/api/criativos/*`, `/api/carousel/*` | `criativos.js`, `carousel.js`, `creative_factory.js` |
| Social Brief | `/api/social-brief/*` | `social_brief.js` |
| Relatórios Meta | `/api/relatorios/*` | `relatorios.js` |
| Financeiro | `/api/financeiro/*` | `financeiro.js` |
| Nutrição | `/api/nutricao/*` | `nutricao.js` |
| Inglês | `/api/ingles/*` | `ingles.js` |
| Site Architect | `/api/architect/*` | `architect.js` |
| Anúncios | `/api/anuncios/*` | `anuncios.js`, `lote.js` |
| Performance | integrado ao Gestor | `performance.js` |

### `bot/` — Bots Telegram
| Arquivo | Token env | Status |
|---------|-----------|--------|
| `jake_telegram.py` | `TELEGRAM_BOT_TOKEN` | ativo (processo manual) |
| `jake_pessoal.py` | `TELEGRAM_TOKEN_PESSOAL` | ativo (processo manual) |
| `jake_viagem.py` | `TELEGRAM_TOKEN_VIAGEM` | ativo (processo manual) |
| `base_bot.py` | — | base compartilhada |

Launcher: `/root/jake_telegram.py` → importa `bot.jake_telegram`

### `bot/jake_whatsapp.py` — Jake WhatsApp
- **Porta:** 5052
- **Processo:** `jake-whatsapp.service` (systemd)
- **Integração:** Evolution API v1.8.7 (Docker, porta 8081)
- **Número Jake:** 553598317697
- **Autorizado:** `WA_AUTHORIZED_NUMBER` (Bruno)
- **Handlers:** `bot/whatsapp_handlers.py` (send_text, send_document)

### `core/` — Infraestrutura compartilhada
- `db.py` — conexão Neon/PostgreSQL via `DATABASE_URL`
- `sync_planilha.py` — Google Sheets (gspread + `credenciais.json`)
- `sync_financeiro.py` — sync de dados financeiros
- `perfil_bruno.py` — perfil/contexto do usuário
- `tarefas.py` — gestão de tarefas

### `meta/` — Meta Ads
- `meta_api.py` — wrapper Meta Graph API v21.0
- `checar_saldo_meta.py` — alerta de saldo (cron 9h)
- `gestor_agente.py` — orquestrador de campanhas (cron 12:30)
- `mcp_server.py` — servidor MCP (porta local, pid 654810)
- `gestor/conhecimento/buscador.py` — buscador de conhecimento (cron seg. 6h)

---

## Banco de Dados (Neon/PostgreSQL)

Tabelas principais:
- `controle_relatorios_semanais` — relatórios Meta Ads
- `social_brief_clientes` — clientes do Social Brief
- `social_brief_geracoes` — gerações semanais
- `social_brief_cliente_dados` — dados por cliente/geração
- `ad_client_profiles` — perfis de clientes Meta Ads
- `nutricao_perfis` — perfis nutricionais
- `ingles_*` — módulo de inglês

---

## Crons

| Schedule | Comando | Função |
|----------|---------|--------|
| `*/5 * * * *` | `scripts/jake_brain_push.sh` | Auto-commit/push do vault `/root/jake-brain/` |
| `30 12 * * *` | `python -m meta.gestor_agente` | Orquestrador de campanhas |
| `0 6 * * 1` | `python -m meta.gestor.conhecimento.buscador` | Busca de conhecimento (seg.) |
| Quarta 8h (APScheduler) | interno `app.py` | Gera Social Brief + envia WhatsApp |

---

## Variáveis de Ambiente

Ver `.env.example` para lista completa.  
O `.env` fica em `/root/.env` e é carregado por todos os módulos.  
O `credenciais.json` (Google Service Account) fica em `/root/credenciais.json` — **não commitar**.

---

## Como reiniciar serviços

```bash
# Jake OS
systemctl restart jake-ia
systemctl status jake-ia

# WhatsApp Bot
systemctl restart jake-whatsapp

# Bots Telegram (processo manual)
pkill -f jake_telegram.py && nohup venv/bin/python bot/jake_telegram.py &
pkill -f jake_pessoal.py  && nohup venv/bin/python bot/jake_pessoal.py &
pkill -f jake_viagem.py   && nohup venv/bin/python bot/jake_viagem.py &
```

---

## Notas de Segurança

- `.env` e `credenciais.json` nunca devem ser commitados (ver `.gitignore`)
- Remote git usa HTTPS sem token — configure PAT via `git credential` ou SSH
- Revisar periodicamente tokens de longa duração (Meta Ads, Google SA)
