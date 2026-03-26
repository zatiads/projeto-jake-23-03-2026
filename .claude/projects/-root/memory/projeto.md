# Jake IA — Projeto Completo

## Bots Telegram em /root/bot/

### Bot principal: jake_telegram.py (em bot/ e na raiz /root/)
- Múltiplos agentes: Analista Sênior (texto), Diretor de Copy (/copy), Operador de Tráfego (/subir)
- Suporte a: PDF (leitura e geração), busca web (ddgs), áudio/Whisper, imagens
- Histórico de conversa salvo no Neon por chat_id + namespace
- Token: `TELEGRAM_BOT_TOKEN`

### Bot Pessoal: jake_pessoal.py
- Agente: assistente pessoal (rotina, tarefas, produtividade do Bruno)
- Token env: `TELEGRAM_TOKEN_PESSOAL`
- Namespace: "pessoal"

### Bot Viagem: jake_viagem.py
- Agente: especialista em viagens para brasileiros (orçamentos em R$, roteiros)
- Token env: `TELEGRAM_TOKEN_VIAGEM`
- Namespace: "viagem"

### base_bot.py
- Base comum para todos os bots gerados
- Função `rodar_bot(token_env, prompt_sistema, namespace, nome)`

### gerar_agente.py
- Meta-agente: gera novos bots interativamente (prompt + arquivo .py)
- Padrão de prompt inclui: capacidades especiais (web, PDF), sempre chamar Bruno de "Patrão"

## Jake OS em /root/jake_desktop/
- Flask SPA, porta 5050
- Auth: admin@jakeos.local / Jake@2024!
- Funcionalidades: carrossel Instagram, copy de anúncios, relatórios Meta Ads, fábrica de criativos, arquiteto de sites, finanças pessoais, geração de imagens
- Modelos: GPT-4o (chat/voz), Claude Sonnet (copy, análise, prompts), Flux 1.1 Pro (imagens)

## Infraestrutura
- VPS Linux (servidor este aqui, /root)
- Banco: Neon (PostgreSQL) — `DATABASE_URL` no .env
- Planilha: Google Sheets → sync via `core/sync_planilha.py`
- Tabela principal: `controle_relatorios_semanais` (clientes, status, chat_id, etc.)
- Tunnel: cloudflared (binário em /root/cloudflared)
- Firewall: scripts/ativar_firewall.sh

## Como subir o bot principal
```bash
./scripts/subir_jake.sh
# ou diretamente:
PYTHONPATH=/root nohup /root/venv/bin/python3 /root/jake_telegram.py >> /root/logs/jake.log 2>&1 &
```

## Como rodar outros bots
```bash
nohup /root/venv/bin/python3 /root/bot/jake_pessoal.py > /tmp/jake_pessoal.log 2>&1 &
nohup /root/venv/bin/python3 /root/bot/jake_viagem.py > /tmp/jake_viagem.log 2>&1 &
```

## Cron
- Saldo Meta: `0 9 * * *` → `python3 -m meta.checar_saldo_meta`
- Alerta abaixo de R$150 (META_ALERTA_SALDO_LIMITE)

## Meta Ads
- Conta: act_360347436292903
- Alerta saldo: META_ALERTA_SALDO_LIMITE=150

## APIs usadas
- Anthropic (Claude): claude-sonnet-4-6 principal
- OpenAI: GPT-4o (chat Jake OS), Whisper (voz), DALL-E 3 (fallback imagens)
- Replicate: Flux 1.1 Pro (imagens)
- Meta Ads API v21.0
- Google Sheets (gspread) + credenciais.json
