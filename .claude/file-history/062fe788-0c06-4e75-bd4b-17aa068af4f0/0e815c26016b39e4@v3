#!/bin/bash
# ──────────────────────────────────────────────────────────
#  Jake IA — Quick Tunnel (HTTPS público automático)
#  Usa ngrok (primário) ou cloudflared (fallback).
#  Salva a URL e envia pelo Telegram.
# ──────────────────────────────────────────────────────────

URL_FILE=/root/jake_desktop/tunnel_url.txt
LOG_FILE=/root/jake_desktop/tunnel.log
NOTIF_FILE=/root/jake_desktop/tunnel_last_notif.txt  # persiste entre reinícios
COOLDOWN=1800  # 30 minutos entre notificações

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

# Retorna 0 (pode notificar) se URL mudou OU cooldown expirou
pode_notificar() {
  local url="$1"
  local now
  now=$(date +%s)
  if [ -f "$NOTIF_FILE" ]; then
    local last_ts last_url
    last_ts=$(cut -d'|' -f1 "$NOTIF_FILE" 2>/dev/null)
    last_url=$(cut -d'|' -f2 "$NOTIF_FILE" 2>/dev/null)
    local elapsed=$(( now - last_ts ))
    # Mesma URL e cooldown não expirou → silencia
    if [ "$last_url" = "$url" ] && [ "$elapsed" -lt "$COOLDOWN" ]; then
      return 1
    fi
  fi
  # Salva timestamp|url para a próxima checagem
  echo "${now}|${url}" > "$NOTIF_FILE"
  return 0
}

echo "" > "$LOG_FILE"

# ── ngrok ────────────────────────────────────────────────
ngrok http 5050 --log=stdout 2>&1 | tee -a "$LOG_FILE" | while IFS= read -r line; do
  echo "$line"
  if echo "$line" | grep -qE 'https://[a-z0-9-]+\.ngrok'; then
    URL=$(echo "$line" | grep -oE 'https://[a-z0-9-]+\.ngrok[^"[:space:]]*' | head -1)
    if [ -n "$URL" ]; then
      echo "$URL" > "$URL_FILE"
      echo ""
      echo "  ✓ Jake IA online! (ngrok)"
      echo "  Link público: $URL"
      echo ""
      if pode_notificar "$URL"; then
        send_telegram "🟢 Jake IA online!
Link: $URL"
      fi
    fi
  fi
done
