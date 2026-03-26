#!/bin/bash
# ──────────────────────────────────────────────────────────
#  Jake IA — Configuração completa do Tunnel Cloudflare
#  Executado automaticamente após autenticação.
# ──────────────────────────────────────────────────────────
set -e

CF=/root/cloudflared
TUNNEL_NAME="jake-ia"
CF_DIR="/root/.cloudflared"

echo ""
echo "  Configurando tunnel permanente Jake IA..."
echo ""

# 1. Criar o tunnel nomeado
echo "▶ Criando tunnel '$TUNNEL_NAME'..."
$CF tunnel create $TUNNEL_NAME 2>&1

# Pega o UUID do tunnel recém criado
TUNNEL_ID=$($CF tunnel list --output json 2>/dev/null | python3 -c "
import json,sys
data=json.load(sys.stdin)
for t in data:
    if t.get('name')=='$TUNNEL_NAME':
        print(t['id'])
        break
" 2>/dev/null)

if [ -z "$TUNNEL_ID" ]; then
  echo "Erro: não foi possível obter o UUID do tunnel."
  exit 1
fi

echo "   UUID: $TUNNEL_ID"

# 2. Criar o config.yml
cat > "$CF_DIR/config.yml" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $CF_DIR/$TUNNEL_ID.json

ingress:
  - service: http://localhost:5050
EOF

echo "▶ Config gravada em $CF_DIR/config.yml"

# 3. Criar serviço systemd para o Jake IA (Flask)
cat > /etc/systemd/system/jake-ia.service <<EOF
[Unit]
Description=Jake IA — Flask App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/jake_desktop
ExecStart=/root/jake_desktop/venv/bin/python app.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 4. Criar serviço systemd para o Cloudflare Tunnel
cat > /etc/systemd/system/jake-tunnel.service <<EOF
[Unit]
Description=Jake IA — Cloudflare Tunnel
After=network.target jake-ia.service
Requires=jake-ia.service

[Service]
Type=simple
User=root
ExecStart=/root/cloudflared tunnel --config /root/.cloudflared/config.yml run
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "▶ Serviços systemd criados"

# 5. Habilitar e iniciar os serviços
systemctl daemon-reload
systemctl enable jake-ia.service jake-tunnel.service
systemctl start jake-ia.service
sleep 3
systemctl start jake-tunnel.service

echo ""
echo "  ✓ Configuração completa!"
echo ""
echo "  Seu link permanente Jake IA:"
echo "  https://$TUNNEL_ID.cfargotunnel.com"
echo ""
echo "  Os serviços agora iniciam automaticamente no boot do VPS."
echo ""
echo "  Comandos úteis:"
echo "    systemctl status jake-ia      → ver status do Flask"
echo "    systemctl status jake-tunnel  → ver status do túnel"
echo "    journalctl -u jake-ia -f      → logs do Flask"
echo "    journalctl -u jake-tunnel -f  → logs do túnel"
echo ""
