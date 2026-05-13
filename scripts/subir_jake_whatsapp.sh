#!/bin/bash
# Sobe o Jake WhatsApp bot na porta 5052.
cd /root
mkdir -p /root/logs

pkill -f "jake_whatsapp.py" 2>/dev/null; sleep 2

PYTHONPATH=/root nohup /root/venv/bin/python3 /root/bot/jake_whatsapp.py \
  >> /root/logs/jake_whatsapp.log 2>&1 &

echo "Jake WhatsApp iniciado. PID: $!"
echo "Log: tail -f /root/logs/jake_whatsapp.log"
