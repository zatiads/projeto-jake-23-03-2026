"""
Gestor IA — Alertas e monitoramento determinísticos.
Gera alertas por regra e lista de ads em maturidade, sem IA.
"""

_OBJETIVOS_SEM_CONVERSAO = {"ENGAGEMENT", "REACH", "BRAND_AWARENESS", "VIDEO_VIEWS"}


def _todos_ads_unicos(metricas: dict) -> list:
    """Retorna lista deduplicada de ads a partir de top_ads + bottom_ads."""
    vistos = {}
    for a in (metricas.get("top_ads") or []) + (metricas.get("bottom_ads") or []):
        vistos.setdefault(a["ad_id"], a)
    return list(vistos.values())


def gerar_alertas(perfis: list[dict]) -> dict[int, list[str]]:
    """
    Retorna {cliente_id: [alertas]} gerados deterministicamente a partir dos perfis.
    Nao usa IA — baseado exclusivamente em regras sobre os dados coletados.
    """
    resultado = {}
    for p in perfis:
        if p.get("erro"):
            continue
        cid = p["cliente_id"]
        alertas = []
        objetivo  = p.get("objetivo", "MESSAGES")
        tipo_pag  = p.get("tipo_pagamento", "pix")
        saldo     = p.get("saldo") or {}
        metricas  = p.get("metricas") or {}
        remaining   = float(saldo.get("remaining", 0) or 0)
        gasto_ontem = float(metricas.get("gasto_ontem", 0) or 0)

        # SALDO_CRITICO — pix com saldo abaixo de R$300
        if tipo_pag == "pix" and remaining < 300:
            alertas.append(f"SALDO_CRITICO: R${remaining:.0f} restantes")

        # SEM_VEICULACAO — sem gasto ontem mas conta com saldo
        if gasto_ontem == 0 and remaining > 0:
            alertas.append("SEM_VEICULACAO: sem gasto ontem")

        # ZERO_CONV — dias consecutivos sem conversao (so objetivos de conversao)
        dias_sem_conv = int(metricas.get("dias_sem_conversao", 0) or 0)
        if dias_sem_conv >= 7 and objetivo not in _OBJETIVOS_SEM_CONVERSAO:
            alertas.append(f"ZERO_CONV: {dias_sem_conv} dias sem conversao")

        # LEARNING_TRAVADO
        ads_learning = int(metricas.get("ads_em_learning", 0) or 0)
        if ads_learning > 0:
            alertas.append(f"LEARNING_TRAVADO: {ads_learning} ads em aprendizado")

        # FREQ_ALTA — varre todos os ads
        for ad in _todos_ads_unicos(metricas):
            freq = float(ad.get("freq", 0) or 0)
            nome = ad.get("ad_name", "")
            if freq > 3.5:
                alertas.append(f"FREQ_ALTA: {nome} freq={freq:.2f} — acima de 3.5, considerar pausar")
            elif freq > 2.5:
                alertas.append(f"FREQ_ALTA: {nome} freq={freq:.2f}")

        if alertas:
            resultado[cid] = alertas

    return resultado


def gerar_monitorando(perfis: list[dict]) -> list[dict]:
    """
    Retorna lista de {"conta": str, "ads": [...]} para ads em maturidade.
    Criterio: dias_rodando < 14 E spend >= R$10.
    """
    resultado = []
    for p in perfis:
        if p.get("erro"):
            continue
        metricas = p.get("metricas") or {}
        ads_jovens = [
            {
                "ad_name": a["ad_name"],
                "dias":    a.get("dias_rodando", 30),
                "spend":   round(float(a.get("spend", 0) or 0), 2),
                "cpl":     round(a["cpl"], 2) if a.get("cpl") else None,
                "freq":    round(float(a.get("freq", 0) or 0), 2),
            }
            for a in _todos_ads_unicos(metricas)
            if a.get("dias_rodando", 30) < 14 and float(a.get("spend", 0) or 0) >= 10
        ]
        if ads_jovens:
            resultado.append({"conta": p["nome"], "ads": ads_jovens})
    return resultado
