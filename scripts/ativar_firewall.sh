#!/bin/bash
# Ativa UFW: libera só SSH (22). Rode quando quiser fechar o resto das portas.
# O Jake não precisa de porta aberta (polling).
set -e
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw --force enable
echo "---"
ufw status
