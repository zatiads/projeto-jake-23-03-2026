#!/bin/bash
# Reinicia o Jake: mata o que estiver na porta 5050 e sobe de novo com o venv.
cd "$(dirname "$0")"
fuser -k 5050/tcp 2>/dev/null || true
sleep 1
.venv/bin/python app.py
