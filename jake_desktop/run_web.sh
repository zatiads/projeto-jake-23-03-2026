#!/bin/bash
# Sobe o Jake OS em modo dev (fora do systemd).
# Em produção, use: systemctl restart jake-ia
cd "$(dirname "$0")"
exec /root/venv/bin/python app.py
