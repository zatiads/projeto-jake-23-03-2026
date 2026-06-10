import json
import os
import re as _re
import time

import requests

from flask import Blueprint, jsonify, request

from .shared import get_db, login_required, anthropic_client, get_meta_token

bp = Blueprint('relatorios', __name__)


import re as _re

_meta_insights_cache: dict = {}   # account_id → {"ts": float, "data": dict}
_META_CACHE_TTL = 1800            # 30 minutos

# Tokens por agência (expansível)
_META_TOKENS = {
    "piloti": lambda: os.environ.get("META_TOKEN_PILOTI", "").strip(),
}

@bp.route("/api/relatorios/insights/<agency>/<account_id>")
@login_required
def api_relatorios_insights(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    cache_key = f"{agency}:{account_id}"
    now = time.time()
    if cache_key in _meta_insights_cache:
        cached = _meta_insights_cache[cache_key]
        if now - cached["ts"] < _META_CACHE_TTL:
            return jsonify(cached["data"])

    token = get_meta_token(agency)
    if not token:
        return jsonify({"error": f"Token da agência '{agency}' não configurado"}), 500

    def _find_action(arr, *types):
        """Percorre um array de actions e retorna o value do primeiro type encontrado."""
        for entry in (arr or []):
            if entry.get("action_type") in types:
                try:
                    return float(entry.get("value", 0) or 0)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/insights",
            params={
                "fields": "spend,impressions,clicks,reach,cpm,ctr,frequency,"
                          "actions,cost_per_action_type",
                "date_preset": "last_7d",
                "access_token": token,
            },
            timeout=15,
        )
        if not r.ok:
            err = r.json().get("error", {})
            return jsonify({"error": err.get("message", f"Meta API {r.status_code}")}), 502

        data = r.json().get("data", [])
        if not data:
            result = {
                "spend": 0.0, "impressions": 0, "clicks": 0, "reach": 0,
                "leads": 0,          "lead_cost": 0.0,
                "messaging": 0,      "messaging_cost": 0.0,
                "profile_visits": 0, "profile_visit_cost": 0.0,
                "purchases": 0,
                "ctr": "0.00", "cpm": "0.00", "frequency": "1.00", "empty": True,
            }
            _meta_insights_cache[cache_key] = {"ts": now, "data": result}
            return jsonify(result)

        row      = data[0]
        actions  = row.get("actions") or []
        costs    = row.get("cost_per_action_type") or []

        # ── Extrações com fallback seguro ────────────────────────────
        leads          = int(_find_action(actions, "lead"))
        lead_cost      = _find_action(costs,   "lead")

        profile_visits      = int(_find_action(actions, "instagram_profile_visit"))
        profile_visit_cost  = _find_action(costs,   "instagram_profile_visit")

        # Fallback: campanhas OUTCOME_TRAFFIC (Turbinar/boost) reportam visitas como link_click
        if profile_visits == 0:
            try:
                # Passo 1: pega IDs das campanhas OUTCOME_TRAFFIC
                rc = requests.get(
                    f"https://graph.facebook.com/v21.0/{account_id}/campaigns",
                    params={"fields": "objective", "access_token": token},
                    timeout=10,
                )
                traffic_ids = [
                    c["id"] for c in rc.json().get("data", [])
                    if c.get("objective") == "OUTCOME_TRAFFIC"
                ]
                # Passo 2: query direta de insights por campanha (evita dados incorretos do embed)
                traffic_clicks = 0
                traffic_spend  = 0.0
                for cid in traffic_ids:
                    ri = requests.get(
                        f"https://graph.facebook.com/v21.0/{cid}/insights",
                        params={
                            "fields": "spend,actions",
                            "date_preset": "last_7d",
                            "access_token": token,
                        },
                        timeout=10,
                    )
                    ri_row = (ri.json().get("data") or [{}])[0]
                    traffic_clicks += int(_find_action(ri_row.get("actions") or [], "link_click"))
                    traffic_spend  += float(ri_row.get("spend", 0) or 0)
                print(f"[Jake debug] traffic_ids={traffic_ids} clicks={traffic_clicks} spend={traffic_spend}")
                if traffic_clicks > 0:
                    profile_visits     = traffic_clicks
                    profile_visit_cost = traffic_spend / traffic_clicks
            except Exception as _e:
                print(f"[Jake debug] fallback erro: {_e}")

        messaging      = int(_find_action(
            actions,
            "onsite_conversion.messaging_conversation_started_7d",
            "onsite_conversion.messaging_conversation_started",
        ))
        messaging_cost = _find_action(
            costs,
            "onsite_conversion.messaging_conversation_started_7d",
            "onsite_conversion.messaging_conversation_started",
        )

        purchases = int(_find_action(actions, "purchase", "omni_purchase"))

        # Diagnóstico: todos os action_types retornados
        raw_actions = {a.get("action_type"): a.get("value") for a in actions}

        result = {
            "spend":              float(row.get("spend", 0) or 0),
            "impressions":        int(row.get("impressions", 0) or 0),
            "clicks":             int(row.get("clicks", 0) or 0),
            "reach":              int(row.get("reach", 0) or 0),
            "leads":              leads,
            "lead_cost":          lead_cost,
            "messaging":          messaging,
            "messaging_cost":     messaging_cost,
            "profile_visits":     profile_visits,
            "profile_visit_cost": profile_visit_cost,
            "purchases":          purchases,
            "ctr":                row.get("ctr", "0.00"),
            "cpm":                row.get("cpm", "0.00"),
            "frequency":          row.get("frequency", "1.00"),
            "_actions":           raw_actions,
        }
        _meta_insights_cache[cache_key] = {"ts": now, "data": result}
        return jsonify(result)

    except requests.Timeout:
        return jsonify({"error": "Timeout na Meta API"}), 504
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# ── API: Debug — action_types brutos de uma conta Meta ──────────────────────
@bp.route("/api/relatorios/debug/<agency>/<account_id>")
@login_required
def api_relatorios_debug(agency, account_id):
    import re as _re2
    if not _re2.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID inválido"}), 400
    token = get_meta_token(agency)
    if not token:
        return jsonify({"error": f"Token da agência '{agency}' não configurado"}), 500
    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/insights",
            params={
                "fields": "spend,actions,cost_per_action_type",
                "date_preset": "last_7d",
                "access_token": token,
            },
            timeout=15,
        )
        data = r.json().get("data", [])
        if not data:
            return jsonify({"info": "Sem dados nos últimos 7 dias", "raw": r.json()})
        row = data[0]
        account_result = {
            "nivel": "conta",
            "spend": row.get("spend"),
            "actions": row.get("actions", []),
            "cost_per_action_type": row.get("cost_per_action_type", []),
        }

        # Busca também por campanha para encontrar dados de Turbinar/boost
        r2 = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/campaigns",
            params={
                "fields": "name,objective,insights.date_preset(last_7d){spend,actions,cost_per_action_type}",
                "access_token": token,
            },
            timeout=15,
        )
        campaigns = []
        for c in r2.json().get("data", []):
            ins = (c.get("insights") or {}).get("data", [{}])
            ins_row = ins[0] if ins else {}
            if float(ins_row.get("spend", 0) or 0) > 0:
                campaigns.append({
                    "nome": c.get("name"),
                    "objetivo": c.get("objective"),
                    "spend": ins_row.get("spend"),
                    "actions": ins_row.get("actions", []),
                    "cost_per_action_type": ins_row.get("cost_per_action_type", []),
                })

        return jsonify({"account": account_result, "campaigns": campaigns})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# ── Vault Obsidian — helpers ────────────────────────────────────────────────

import unicodedata as _unicodedata

def _slug(name: str) -> str:
    """Normaliza nome para uso como path: lowercase, sem acentos, espaços→hífens."""
    n = _unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if _unicodedata.category(c) != "Mn")
    return _re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")

_VAULT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jake-brain", "Clientes")

def _vault_ler_contexto(nome: str) -> str:
    """Lê o .md mais recente de jake-brain/Clientes/<slug>/Performance/"""
    slug = _slug(nome)
    pasta = os.path.join(_VAULT_ROOT, slug, "Performance")
    if not os.path.isdir(pasta):
        return ""
    arquivos = sorted([f for f in os.listdir(pasta) if f.endswith(".md")], reverse=True)
    if not arquivos:
        return ""
    try:
        with open(os.path.join(pasta, arquivos[0]), encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def _vault_salvar_snapshot(nome: str, metricas: dict, metricas_anterior: dict, delta: dict, analise: str):
    """Salva snapshot semanal em jake-brain/Clientes/<slug>/Performance/YYYY-WXX.md"""
    from datetime import date
    slug  = _slug(nome)
    pasta = os.path.join(_VAULT_ROOT, slug, "Performance")
    os.makedirs(pasta, exist_ok=True)
    hoje   = date.today()
    semana = hoje.strftime("%Y-W%W")
    path   = os.path.join(pasta, f"{semana}.md")
    linhas_met = "\n".join(
        f"| {k} | {v} | {metricas_anterior.get(k,'--')} | {delta.get(k,'--')} |"
        for k, v in metricas.items()
    )
    conteudo = f"""# Performance — {nome} — {semana}

**Data de análise:** {hoje.isoformat()}

## Métricas
| Métrica | Atual | Anterior | Delta |
|---|---|---|---|
{linhas_met}

## Análise IA
{analise}
"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(conteudo)
    except Exception as e:
        print(f"[Jake vault] erro ao salvar snapshot: {e}")

# ── API: Análise IA para Relatórios ──────────────────────────────────────────
@bp.route("/api/relatorios/analise", methods=["POST"])
@login_required
def api_relatorios_analise():
    data              = request.get_json() or {}
    nome              = (data.get("nome") or "").strip()
    metricas          = data.get("metricas") or {}
    metricas_anterior = data.get("metricas_anterior") or {}
    delta             = data.get("delta") or {}

    client = anthropic_client()
    if not client:
        return jsonify({"analise": ""})

    metricas_str = "\n".join(f"- {k}: {v}" for k, v in metricas.items())

    # Contexto histórico do vault Obsidian
    contexto_vault = _vault_ler_contexto(nome)
    bloco_vault = (
        f"\n\nContexto histórico do cliente (semanas anteriores):\n{contexto_vault[:800]}"
        if contexto_vault else ""
    )

    # Comparação com semana anterior
    bloco_anterior = ""
    if metricas_anterior:
        ant_str   = "\n".join(f"- {k}: {v}" for k, v in metricas_anterior.items())
        delta_str = "\n".join(f"- {k}: {v}" for k, v in delta.items()) if delta else ""
        bloco_anterior = (
            f"\n\nSemana anterior:\n{ant_str}"
            + (f"\n\nVariação (atual vs anterior):\n{delta_str}" if delta_str else "")
        )

    prompt = (
        f"Você é analista de tráfego pago. Gere uma análise BREVE (2-3 frases, máximo 140 palavras) "
        f"sobre os resultados das campanhas Meta Ads de '{nome}' nos últimos 7 dias.\n\n"
        f"Dados atuais:\n{metricas_str}"
        f"{bloco_anterior}"
        f"{bloco_vault}\n\n"
        f"Seja direto, profissional, em português brasileiro. "
        f"Destaque o principal resultado, compare com semana anterior se disponível, e dê UMA recomendação prática. "
        f"NÃO use markdown, asteriscos, negrito ou formatação. Apenas texto corrido simples."
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        analise = (msg.content[0].text or "").strip()
        if metricas:
            _vault_salvar_snapshot(nome, metricas, metricas_anterior, delta, analise)
        return jsonify({"analise": analise})
    except Exception as exc:
        return jsonify({"analise": "", "error": str(exc)})

