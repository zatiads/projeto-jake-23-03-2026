#!/bin/bash
# Sobe o Jake no Telegram em background.
# OBRIGATÓRIO: usar o venv e PYTHONPATH=/root (projeto organizado em bot/, meta/, core/).
cd /root
pkill -f "jake_telegram.py" 2>/dev/null; sleep 2
PYTHONPATH=/root nohup /root/venv/bin/python3 /root/jake_telegram.py >> /root/logs/jake.log 2>&1 &
echo "Jake iniciado. PID: $!"
echo "Log: tail -f /root/logs/jake.log"
