"""
Gestor IA — Coletor de métricas.
Busca e agrega dados das 28 contas via Meta API. Sem IA.
Retorna lista de perfis de conta para o Analista.
"""
import os
import math
import json
import requests
import psycopg2
import psycopg2.extras
from datetime import date, timedelta
from typing import List, Dict, Any

GRAPH_URL = "https://graph.facebook.com/v21.0"

def _get_db():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido")
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _extrair_conversoes(actions: list, objetivo: str) -> int:
    """Extrai métrica de conversão relevante por objetivo da campanha."""
    if not actions:
        return 0
    alvo = {
        "MESSAGES": {"onsite_conversion.messaging_conversation_started_7d",
                     "messaging_conversation_started_7d",
                     "onsite_conversion.messaging_conversation_started_1d"},
        "PURCHASE":  {"purchase", "offsite_conversion.fb_pixel_purchase"},
        "ENGAGEMENT": {"link_click", "post_engagement"},
    }.get(objetivo, set())
    return sum(
        int(a.get("value", 0))
        for a in actions
        if isinstance(a, dict) and a.get("action_type") in alvo
    )


def _buscar_insights_ads(token: str, account_id: str, days: int = 30) -> list:
    """Busca insights a nível de ad dos últimos N dias. Retorna lista de rows."""
    hoje = date.today()
    inicio = hoje - timedelta(days=days)
    url = f"{GRAPH_URL}/{account_id}/insights"
    params = {
        "access_token": token,
        "level": "ad",
        "fields": "ad_id,ad_name,spend,impressions,clicks,actions,frequency,cpm,ctr,effective_status",
        "time_range": json.dumps({"since": str(inicio), "until": str(hoje)}),
        "limit": 200,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception:
        return []


def _buscar_insights_diarios(token: str, account_id: str, days: int = 7) -> list:
    """
    Busca gasto diário da conta nos últimos N dias (level=account).
    Retorna lista de {"date_start": "YYYY-MM-DD", "spend": float, "actions": list}.
    """
    hoje = date.today()
    inicio = hoje - timedelta(days=days)
    url = f"{GRAPH_URL}/{account_id}/insights"
    params = {
        "access_token": token,
        "level": "account",
        "fields": "spend,date_start,actions",
        "time_range": json.dumps({"since": str(inicio), "until": str(hoje)}),
        "time_increment": 1,
        "limit": 10,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception:
        return []


def _buscar_cpl_semana_anterior(cliente_id: int, objetivo: str) -> float | None:
    """
    Lê do banco o CPL médio da semana anterior.
    Abre sua própria conexão (o db_conn de coletar() é fechado antes do loop).
    Retorna None por ora (será expandido quando gestor gravar CPL por conta).
    """
    try:
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT gv.resumo_json
                FROM gestor_varreduras gv
                WHERE gv.executado_em < NOW() - INTERVAL '6 days'
                  AND gv.status = 'sucesso'
                ORDER BY gv.executado_em DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if not row or not row["resumo_json"]:
                return None
            return None  # expandir futuramente quando gestor gravar CPL por conta
        finally:
            conn.close()
    except Exception:
        return None


def _buscar_saldo(token: str, account_id: str) -> dict:
    """Retorna saldo da conta em reais."""
    try:
        resp = requests.get(
            f"{GRAPH_URL}/{account_id}",
            params={"fields": "amount_spent,spend_cap,balance", "access_token": token},
            timeout=15,
        )
        data = resp.json()
        amount_spent = float(data.get("amount_spent", 0) or 0) / 100
        spend_cap    = float(data.get("spend_cap", 0) or 0) / 100
        balance      = float(data.get("balance", 0) or 0) / 100
        remaining    = max(0.0, spend_cap - amount_spent) if spend_cap else balance
        return {"amount_spent": amount_spent, "spend_cap": spend_cap, "remaining": remaining}
    except Exception:
        return {"amount_spent": 0.0, "spend_cap": 0.0, "remaining": 0.0}


def _agregar_conta(rows: list, objetivo: str) -> dict:
    """
    Agrega linhas de ad-level insights num perfil de conta.
    Retorna: cpl_medio, cpl_desvio, total_conversoes, total_spend, dias_com_dados,
             top_ads (3 melhores CPL), bottom_ads (3 piores CPL).
    """
    ads_com_dados = []
    for row in rows:
        spend = float(row.get("spend") or 0)
        conv  = _extrair_conversoes(row.get("actions") or [], objetivo)
        cpl   = spend / conv if conv > 0 else None
        ads_com_dados.append({
            "ad_id":   row.get("ad_id", ""),
            "ad_name": row.get("ad_name", ""),
            "spend":   spend,
            "conversoes": conv,
            "cpl":     cpl,
            "freq":    float(row.get("frequency") or 0),
            "ctr":     float(row.get("ctr") or 0),
        })

    cpls = [a["cpl"] for a in ads_com_dados if a["cpl"] is not None]
    cpl_medio  = sum(cpls) / len(cpls) if cpls else None
    cpl_desvio = math.sqrt(sum((c - cpl_medio) ** 2 for c in cpls) / len(cpls)) if len(cpls) > 1 else 0.0

    ads_sorted = sorted(
        [a for a in ads_com_dados if a["cpl"] is not None],
        key=lambda x: x["cpl"]
    )

    return {
        "cpl_medio":        round(cpl_medio, 2) if cpl_medio is not None else None,
        "cpl_desvio":       round(cpl_desvio, 2),
        "total_conversoes": sum(a["conversoes"] for a in ads_com_dados),
        "total_spend":      round(sum(a["spend"] for a in ads_com_dados), 2),
        "total_ads":        len(ads_com_dados),
        "dias_historico":   30,
        "top_ads":    ads_sorted[:3],
        "bottom_ads": ads_sorted[-3:] if len(ads_sorted) > 5 else [],
    }


def coletar(db_conn=None) -> List[Dict[str, Any]]:
    """
    Coleta e agrega métricas de todas as contas ativas.
    Retorna lista de perfis prontos para o Analista.
    """
    fechar = False
    if db_conn is None:
        db_conn = _get_db()
        fechar = True

    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT id, nome, agencia, account_id, token_key,
                   campanha_tipo, gestor_config_json, gestor_ativo, tipo_pagamento
            FROM ad_client_profiles
            WHERE gestor_ativo = TRUE
        """)
        contas = list(cur.fetchall())
    finally:
        if fechar:
            db_conn.close()

    perfis = []
    for conta in contas:
        token_key   = conta["token_key"]
        try:
            from meta.meta_api import _resolve_token
            token = _resolve_token(token_key)
        except Exception:
            token = os.getenv(token_key, "").strip()
        if not token:
            perfis.append({
                "cliente_id":     conta["id"],
                "nome":           conta["nome"],
                "agencia":        conta["agencia"],
                "account_id":     conta["account_id"],
                "objetivo":       conta["campanha_tipo"] or "MESSAGES",
                "gestor_config":  conta["gestor_config_json"],
                "tipo_pagamento": conta.get("tipo_pagamento") or "pix",
                "erro":           f"Token '{token_key}' não configurado",
            })
            continue

        objetivo = conta["campanha_tipo"] or "MESSAGES"
        rows     = _buscar_insights_ads(token, conta["account_id"])
        saldo    = _buscar_saldo(token, conta["account_id"])
        metricas = _agregar_conta(rows, objetivo)

        # Dados diários para alertas
        dados_diarios = _buscar_insights_diarios(token, conta["account_id"], days=7)
        gasto_ontem = 0.0
        dias_sem_conversao = 0
        if dados_diarios:
            ultimo_dia = dados_diarios[-1]
            gasto_ontem = float(ultimo_dia.get("spend") or 0)
            # Contar dias consecutivos com gasto mas sem conversão
            for dia in reversed(dados_diarios):
                spend_dia = float(dia.get("spend") or 0)
                conv_dia = _extrair_conversoes(dia.get("actions") or [], objetivo)
                if spend_dia > 0 and conv_dia == 0:
                    dias_sem_conversao += 1
                elif spend_dia > 0:
                    break

        # Ads em aprendizado (effective_status = LEARNING)
        ads_em_learning = sum(1 for r in rows if r.get("effective_status") == "LEARNING")

        # CPL semana anterior (do banco)
        cpl_semana_anterior = _buscar_cpl_semana_anterior(conta["id"], objetivo)

        metricas["gasto_ontem"] = gasto_ontem
        metricas["dias_sem_conversao"] = dias_sem_conversao
        metricas["ads_em_learning"] = ads_em_learning
        metricas["cpl_semana_anterior"] = cpl_semana_anterior

        perfis.append({
            "cliente_id":      conta["id"],
            "nome":            conta["nome"],
            "agencia":         conta["agencia"],
            "account_id":      conta["account_id"],
            "token_key":       token_key,
            "objetivo":        objetivo,
            "gestor_config":   conta["gestor_config_json"],
            "tipo_pagamento":  conta.get("tipo_pagamento") or "pix",
            "saldo":           saldo,
            "metricas":        metricas,
            "erro":            None,
        })

    return perfis
