#!/bin/bash
# Reinicia o Jake OS via systemd (forma correta).
# O systemd gerencia o processo, evita conflito de porta.
echo "Reiniciando Jake OS..."
systemctl restart jake-ia
sleep 2
systemctl status jake-ia --no-pager | grep -E "Active|Main PID"
