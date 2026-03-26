# Jake IA

Bot no Telegram para gestão de tráfego (Meta Ads, relatórios, saldo, copy e múltiplos agentes com Claude).

## Estrutura do projeto

```
/root
├── .env                 # Credenciais (nunca commitar). Ver docs/SEGURANCA.md
├── venv/                 # Ambiente Python (telegram, anthropic, openai, etc.)
├── bot/                  # Bot Telegram (Jake — múltiplos agentes)
│   └── jake_telegram.py   # Entrada do bot: /start, /relatorio, /copy, /subir, áudio
├── meta/                 # Meta (Facebook) Ads API
│   ├── config_meta.py     # Config e tokens da Meta
│   ├── meta_api.py       # Relatórios, saldo, insights
│   └── checar_saldo_meta.py  # Script de alerta de saldo (rodar via cron)
├── core/                 # Recursos compartilhados
│   ├── db.py             # Conexão Neon (PostgreSQL)
│   └── sync_planilha.py  # Sync planilha controle_relatorios_semanais → Neon
├── leitor_planilha.py    # Leitor Google Sheets (gspread); clientes ativos
├── docs/                 # Documentação
│   ├── AGENTES_JAKE.md    # Matriz de agentes (Analista, Copy, Operador)
│   ├── CONFIGURAR_META.md # Como configurar a Meta
│   ├── JAKE_ROADMAP.md    # Roadmap e cron
│   └── SEGURANCA.md       # Credenciais, .env, SSH, firewall
├── scripts/              # Scripts de manutenção
│   ├── subir_jake.sh     # Sobe o bot em background (usar este para iniciar)
│   └── ativar_firewall.sh
└── logs/                 # Logs do bot e do cron de saldo
    ├── jake.log
    └── log_saldo_meta.log
```

## Como rodar

- **Subir o bot:**  
  `./scripts/subir_jake.sh`  
  (ou `bash /root/scripts/subir_jake.sh`)

- **Cron de saldo (1x por dia às 9h):**  
  `crontab -e` e adicionar:  
  `0 9 * * * cd /root && PYTHONPATH=/root /root/venv/bin/python3 -m meta.checar_saldo_meta >> /root/logs/log_saldo_meta.log 2>&1`

- **Testar saldo manualmente:**  
  `cd /root && PYTHONPATH=/root /root/venv/bin/python3 -m meta.checar_saldo_meta`

- **Planilha → Neon (controle_relatorios_semanais):**  
  O comando `/clientes` no Telegram já sincroniza a planilha com o banco antes de listar. Para rodar o sync manualmente:  
  `cd /root && PYTHONPATH=/root /root/venv/bin/python3 -m core.sync_planilha`  
  A tabela no Neon é criada automaticamente; colunas: cliente, id_conta, modelo_relatorio, tag_captacao, tag_engajamento, frequencia, chat_id, status.

Detalhes em **docs/JAKE_ROADMAP.md** e **docs/SEGURANCA.md**.
