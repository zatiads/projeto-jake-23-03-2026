import json
import os
import re as _re
import time

import requests

from flask import Blueprint, jsonify, request

from .shared import get_db, login_required, get_meta_token

bp = Blueprint('performance', __name__)



# ── API: Performance — Saldo ────────────────────────────────────────────────

_perf_saldo_cache: dict = {}
_PERF_SALDO_TTL = 1800  # 30 min

@bp.route("/api/performance/saldo/<agency>/<account_id>")
@login_required
def api_performance_saldo(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    token_fn = get_meta_token_dict().get(agency)
    if not token_fn:
        return jsonify({"error": "Agência não encontrada"}), 404

    cache_key = f"saldo:{agency}:{account_id}"
    now = time.time()
    if cache_key in _perf_saldo_cache:
        cached = _perf_saldo_cache[cache_key]
        if now - cached["ts"] < _PERF_SALDO_TTL:
            return jsonify(cached["data"])

    token = token_fn()
    if not token:
        return jsonify({"error": "Token da agência não configurado"}), 500

    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}",
            params={"fields": "amount_spent,balance,spend_cap,currency", "access_token": token},
            timeout=15,
        )
        if not r.ok:
            err = r.json().get("error", {})
            return jsonify({"error": err.get("message", f"Meta API {r.status_code}")}), 502
        data = r.json()
        amount_spent = float(data.get("amount_spent", 0) or 0) / 100
        balance      = float(data.get("balance", 0) or 0) / 100
        spend_cap    = float(data.get("spend_cap", 0) or 0) / 100
        remaining    = max(0.0, spend_cap - amount_spent) if spend_cap else balance
        result = {
            "amount_spent": round(amount_spent, 2),
            "balance":      round(balance, 2),
            "spend_cap":    round(spend_cap, 2),
            "remaining":    round(remaining, 2),
            "currency":     data.get("currency", "BRL"),
            "alerta":       remaining < 200.0,
        }
        _perf_saldo_cache[cache_key] = {"ts": now, "data": result}
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── API: Performance — Alerta de Saldo ─────────────────────────────────────

_alerta_sent_cache: dict = {}  # account_id -> timestamp último envio
_ALERTA_TTL = 3600  # 1 hora

@bp.route("/api/performance/alerta-saldo", methods=["POST"])
@login_required
def api_performance_alerta_saldo():
    data       = request.get_json() or {}
    account_id = (data.get("account_id") or "").strip()
    nome       = (data.get("nome") or "conta").strip()
    agency     = (data.get("agency") or "").strip()
    saldo      = data.get("saldo", 0)

    now = time.time()
    last = _alerta_sent_cache.get(account_id, 0)
    if now - last < _ALERTA_TTL:
        return jsonify({"ok": True, "dedup": True})

    msg = f"⚠️ Patrão, saldo baixo em {nome} ({agency}): R$ {float(saldo):,.2f}"
    ok, detail = _send_telegram(msg)
    _alerta_sent_cache[account_id] = now
    return jsonify({"ok": ok, "detail": detail})


# ── API: Performance — Semana Anterior ─────────────────────────────────────

def _extract_insights_row(row: dict) -> dict:
    """Extrai métricas de uma linha de insights da Meta API."""
    actions = row.get("actions") or []
    costs   = row.get("cost_per_action_type") or []

    def _fa(arr, *types):
        for entry in (arr or []):
            if entry.get("action_type") in types:
                try:
                    return float(entry.get("value", 0) or 0)
                except Exception:
                    return 0.0
        return 0.0

    leads     = int(_fa(actions, "lead"))
    messaging = int(_fa(actions,
        "onsite_conversion.messaging_conversation_started_7d",
        "onsite_conversion.messaging_conversation_started"))
    purchases = int(_fa(actions, "purchase", "omni_purchase"))
    profile_visits = int(_fa(actions, "instagram_profile_visit"))
    spend     = float(row.get("spend", 0) or 0)

    return {
        "spend":          round(spend, 2),
        "impressions":    int(row.get("impressions", 0) or 0),
        "clicks":         int(row.get("clicks", 0) or 0),
        "reach":          int(row.get("reach", 0) or 0),
        "cpm":            row.get("cpm", "0.00"),
        "ctr":            row.get("ctr", "0.00"),
        "frequency":      row.get("frequency", "1.00"),
        "leads":          leads,
        "messaging":      messaging,
        "purchases":      purchases,
        "profile_visits": profile_visits,
    }


def _fetch_meta_period(account_id: str, token: str, since: str, until: str) -> dict:
    """Busca insights de um período específico (since/until em YYYY-MM-DD)."""
    r = requests.get(
        f"https://graph.facebook.com/v21.0/{account_id}/insights",
        params={
            "fields": "spend,impressions,clicks,reach,cpm,ctr,frequency,actions,cost_per_action_type",
            "time_range": '{"since":"' + since + '","until":"' + until + '"}',
            "access_token": token,
        },
        timeout=15,
    )
    if not r.ok:
        return {}
    data = r.json().get("data", [])
    if not data:
        return {"spend": 0, "impressions": 0, "clicks": 0, "reach": 0,
                "leads": 0, "messaging": 0, "purchases": 0, "profile_visits": 0,
                "cpm": "0.00", "ctr": "0.00", "frequency": "1.00"}
    return _extract_insights_row(data[0])


@bp.route("/api/performance/semana-anterior/<agency>/<account_id>")
@login_required
def api_performance_semana_anterior(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    token_fn = get_meta_token_dict().get(agency)
    if not token_fn:
        return jsonify({"error": "Agência não encontrada"}), 404
    token = token_fn()
    if not token:
        return jsonify({"error": "Token da agência não configurado"}), 500

    from datetime import date, timedelta
    today          = date.today()
    since_atual    = (today - timedelta(days=6)).isoformat()
    until_atual    = today.isoformat()
    since_anterior = (today - timedelta(days=13)).isoformat()
    until_anterior = (today - timedelta(days=7)).isoformat()

