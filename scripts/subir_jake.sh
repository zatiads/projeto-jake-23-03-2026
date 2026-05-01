#!/bin/bash
# Sobe o Jake no Telegram em background.
# OBRIGATÓRIO: usar o venv e PYTHONPATH=/root (projeto organizado em bot/, meta/, core/).
cd /root
mkdir -p /root/logs

# Sobe o Meta MCP Server (HTTP :5051)
pkill -f "mcp_server.py" 2>/dev/null; sleep 1
PYTHONPATH=/root nohup /root/venv/bin/python3 /root/meta/mcp_server.py >> /root/logs/meta_mcp.log 2>&1 &
echo $! > /tmp/meta_mcp.pid
echo "Meta MCP Server iniciado. PID: $(cat /tmp/meta_mcp.pid)"

# Sobe o bot Telegram principal
pkill -f "jake_telegram.py" 2>/dev/null; sleep 2
PYTHONPATH=/root nohup /root/venv/bin/python3 /root/jake_telegram.py >> /root/logs/jake.log 2>&1 &
echo "Jake iniciado. PID: $!"
echo "Log: tail -f /root/logs/jake.log"
