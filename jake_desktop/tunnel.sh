#!/bin/bash
# ──────────────────────────────────────────────────────────
#  Jake IA — Cloudflare Tunnel
#  Gera um link HTTPS público gratuito para o Jake IA.
#  Execute em um terminal SEPARADO (mantenha aberto).
# ──────────────────────────────────────────────────────────

CF=/root/cloudflared

# Baixa cloudflared se não existir
if [ ! -f "$CF" ]; then
  echo "Baixando cloudflared..."
  curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o "$CF"
  chmod +x "$CF"
fi

# Verifica se o Jake está rodando
if ! curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/login 2>/dev/null | grep -q "200\|302"; then
  echo ""
  echo "⚠  O servidor Jake IA não está rodando em localhost:5050"
  echo "   Suba primeiro com: ./reiniciar_jake.sh"
  echo ""
  exit 1
fi

echo ""
echo "  Jake IA — Tunnel Cloudflare"
echo "  O link público aparece abaixo em alguns segundos..."
echo "  Mantenha esta janela aberta enquanto quiser acesso externo."
echo ""

# Inicia o túnel (o link aparece no output abaixo)
"$CF" tunnel --url http://localhost:5050 2>&1
