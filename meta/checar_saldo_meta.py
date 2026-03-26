#!/usr/bin/env python3
"""
Jake IA — Alertas financeiros (item 1 do roadmap).
Verifica o saldo restante da conta Meta; se estiver abaixo do limite (R$),
envia mensagem no Telegram pedindo recarga.
Rodar via cron (1x por dia) ou manualmente. Executar com: python -m meta.checar_saldo_meta (a partir de /root).
"""
import os
import sys

try:
    from dotenv import load_dotenv
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

import requests

# Config (env)
META_AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID", "").strip()
META_ALERTA_LIMITE = float(os.environ.get("META_ALERTA_SALDO_LIMITE", "150"))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_ALERT_CHAT_ID = os.environ.get("TELEGRAM_ALERT_CHAT_ID", "").strip()


def enviar_telegram(texto: str) -> bool:
    """Envia mensagem para o chat configurado (TELEGRAM_ALERT_CHAT_ID)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ALERT_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": TELEGRAM_ALERT_CHAT_ID, "text": texto},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False


def main():
    if not META_AD_ACCOUNT_ID or not META_AD_ACCOUNT_ID.startswith("act_"):
        print("Erro: META_AD_ACCOUNT_ID não configurado no .env")
        sys.exit(1)
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ALERT_CHAT_ID:
        print("Erro: TELEGRAM_BOT_TOKEN e TELEGRAM_ALERT_CHAT_ID devem estar no .env")
        sys.exit(1)

    try:
        from .config_meta import meta_configured
        from .meta_api import get_saldo_conta
    except ImportError as e:
        print("Erro ao importar meta:", e)
        sys.exit(1)

    if not meta_configured():
        print("Erro: Meta não configurada (META_ACCESS_TOKEN)")
        sys.exit(1)

    saldo = get_saldo_conta(META_AD_ACCOUNT_ID)
    if saldo is None:
        print("Erro: não foi possível obter saldo da conta Meta")
        sys.exit(1)

    remaining = saldo.get("remaining", 0)
    amount_spent = saldo.get("amount_spent", 0)
    spend_cap = saldo.get("spend_cap", 0)
    currency = saldo.get("currency", "BRL")

    remaining_str = f"R$ {remaining:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    if remaining < META_ALERTA_LIMITE:
        msg = (
            "⚠️ Jake IA — Alerta de saldo\n\n"
            "Patrão, a conta de anúncios está com saldo restante baixo.\n\n"
            f"Saldo restante: {remaining_str}\n"
            f"Limite configurado para aviso: R$ {META_ALERTA_LIMITE:,.2f}\n\n"
            "A conta precisa ser recarregada para não interromper as campanhas."
        )
        if enviar_telegram(msg):
            print("Alerta enviado no Telegram.")
        else:
            print("Falha ao enviar alerta no Telegram.")
        sys.exit(0)

    print(f"Saldo OK. Restante: {remaining_str} (limite de alerta: R$ {META_ALERTA_LIMITE:,.2f})")
    sys.exit(0)


if __name__ == "__main__":
    main()
