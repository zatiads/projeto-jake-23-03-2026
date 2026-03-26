#!/bin/bash
# ──────────────────────────────────────────────────────────
#  Jake IA — Quick Tunnel (HTTPS público automático)
#  Usa ngrok (primário) ou cloudflared (fallback).
#  Salva a URL e envia pelo Telegram.
# ──────────────────────────────────────────────────────────

URL_FILE=/root/jake_desktop/tunnel_url.txt
LOG_FILE=/root/jake_desktop/tunnel.log

# Lê variáveis do .env para o Telegram
set -a
[ -f /root/.env ] && source /root/.env
set +a

send_telegram() {
  local text="$1"
  if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_ALERT_CHAT_ID" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="$TELEGRAM_ALERT_CHAT_ID" \
      -d text="$text" \
      -d disable_web_page_preview=true > /dev/null 2>&1
  fi
  if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$AUTHORIZED_ID" ] && [ "$AUTHORIZED_ID" != "$TELEGRAM_ALERT_CHAT_ID" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="$AUTHORIZED_ID" \
      -d text="$text" \
      -d disable_web_page_preview=true > /dev/null 2>&1
  fi
}

echo "" > "$LOG_FILE"
_FLAG=$(mktemp)

# ── ngrok ────────────────────────────────────────────────
ngrok http 5050 --log=stdout 2>&1 | tee -a "$LOG_FILE" | while IFS= read -r line; do
  echo "$line"
  # Detecta URL ngrok (https://xxx.ngrok-free.app ou xxx.ngrok.io) — envia só uma vez
  if [ ! -s "$_FLAG" ] && echo "$line" | grep -qE 'https://[a-z0-9-]+\.ngrok'; then
    URL=$(echo "$line" | grep -oE 'https://[a-z0-9-]+\.ngrok[^"[:space:]]*' | head -1)
    if [ -n "$URL" ]; then
      echo "$URL" > "$_FLAG"
      echo "$URL" > "$URL_FILE"
      echo ""
      echo "  ✓ Jake IA online! (ngrok)"
      echo "  Link público: $URL"
      echo ""
      send_telegram "🟢 Jake IA online!
Link: $URL"
    fi
  fi
done
rm -f "$_FLAG"
