"""
Meta (Facebook) Marketing API — insights e relatório no formato Jake IA.
Conta: act_360347436292903 (OdontoCompany Carazinho).
Extrai reach, cliques, leads (mensagens iniciadas) e spend; calcula CPL.
"""
import requests
from datetime import date, timedelta
from typing import Optional, Tuple

from .config_meta import META_ACCESS_TOKEN, get_conta_for_cliente, meta_configured

GRAPH_URL = "https://graph.facebook.com/v21.0"

# action_types que contam como leads = mensagens iniciadas (WhatsApp/Direct)
LEADS_ACTION_TYPES = (
    "onsite_conversion.messaging_conversation_started_7d",
    "onsite_conversion.messaging_conversation_started_1d",
    "messaging_conversation_started_7d",
    "messaging_conversation_started_1d",
)


def _formatar_numero(n):
    """Formato brasileiro: 1.234 (inteiro)."""
    try:
        return f"{int(float(n)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _formatar_brl(valor):
    """Formato brasileiro: R$ 13,37"""
    if valor is None:
        return "0,00"
    try:
        v = float(valor)
        if v != v:
            return "0,00"
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"


def _get_insights(account_id: str, days: int = 7) -> Optional[dict]:
    """Insights da conta nos últimos N dias (agregado). level=account."""
    if not account_id or not account_id.startswith("act_"):
        return None
    if not META_ACCESS_TOKEN or not str(META_ACCESS_TOKEN).strip():
        return None
    hoje = date.today()
    inicio = hoje - timedelta(days=days)
    url = f"{GRAPH_URL}/{account_id}/insights"
    params = {
        "access_token": META_ACCESS_TOKEN.strip(),
        "level": "account",
        "fields": "reach,spend,clicks,inline_link_clicks,actions",
        "time_range": f'{{"since":"{inicio}","until":"{hoje}"}}',
        "limit": 1,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _extrair_leads(actions):
    """Soma o value de actions de mensagens iniciadas (leads)."""
    if not actions:
        return 0
    return sum(
        int(a.get("value", 0))
        for a in actions
        if isinstance(a, dict) and a.get("action_type") in LEADS_ACTION_TYPES
    )


def _extrair_cliques(row):
    """Cliques: preferir inline_link_clicks, senão clicks."""
    raw = row.get("inline_link_clicks") or row.get("clicks") or 0
    if isinstance(raw, list):
        return sum(int(x.get("value", 0)) for x in raw if isinstance(x, dict))
    try:
        return int(float(raw))
    except (ValueError, TypeError):
        return 0


def _gerar_insight(leads: int, spend: float, cpl: float, alcance: int, cliques: int) -> str:
    """Uma ou duas frases positivas sobre a conta, analisando os dados."""
    frases = []
    if leads > 0:
        if cpl <= 10:
            frases.append("CPL bem controlado — ótimo custo por lead para o segmento.")
        elif cpl <= 20:
            frases.append("CPL dentro do esperado; espaço para testar criativos e afinar público.")
        if leads >= 30:
            frases.append("Bom volume de leads na semana; conta pronta para escalar.")
        elif leads >= 15:
            frases.append("Volume de leads sólido; seguir otimizando para baixar CPL.")
    if alcance > 10000 and cliques > 0:
        taxa = (cliques / alcance * 100) if alcance else 0
        if taxa >= 0.8:
            frases.append("Alcance e cliques em boa sintonia — anúncios gerando engajamento.")
    if not frases:
        if spend > 0:
            frases.append("Dados da semana registrados; próxima etapa é comparar com períodos anteriores.")
        else:
            frases.append("Período sem investimento registrado na conta.")
    return " ".join(frases[:2])  # no máximo 2 frases


def formatar_relatorio(metricas: dict, cliente: str, dias: int, insight: str = "") -> str:
    """Template: OdontoCompany Carazinho, Meta, Alcance, Cliques, Leads, CPL + análise breve."""
    alcance = metricas.get("alcance", "0")
    cliques = metricas.get("cliques", "0")
    leads_str = metricas.get("leads_str", "0")
    cpl_str = metricas.get("cpl_str", "0,00")
    nome_exibicao = "OdontoCompany Carazinho" if cliente.lower() == "carazinho" else cliente.title()
    linhas = [
        "Bom dia pessoal! 😁",
        "Segue relatório das nossas campanhas nos últimos " + str(dias) + " dias:",
        "",
        nome_exibicao,
        "",
        "Meta",
        "👥 Alcance: " + alcance,
        "▶️ Cliques: " + cliques,
        "🎯 Leads: " + leads_str,
        "💰 Custo por lead: R$ " + cpl_str,
        "",
    ]
    if insight:
        linhas.append("💡 " + insight)
        linhas.append("")
    linhas.append("Boa semana a todos 🙏")
    return "\n".join(linhas)


def puxar_relatorio(cliente: str, dias: int = 7) -> Tuple[bool, str]:
    """
    Puxa relatório da Meta para o cliente e retorna (sucesso, texto ou mensagem de erro).
    """
    if not meta_configured():
        return False, "Meta API não configurada. Configure .env com META_ACCESS_TOKEN e META_AD_ACCOUNT_ID."
    conta = get_conta_for_cliente(cliente)
    if not conta:
        return False, f"Nenhuma conta de anúncios configurada para o cliente '{cliente}'."
    data = _get_insights(conta, days=dias)
    if data is None:
        return False, "Falha ao buscar dados na Meta (token ou rede). Verifique META_ACCESS_TOKEN e permissões."
    rows = data.get("data") or []
    if not rows:
        alcance_num = 0
        cliques_num = 0
        alcance = "0"
        cliques = "0"
        leads = 0
        spend = 0.0
    else:
        row = rows[0]
        alcance_num = int(row.get("reach") or 0)
        cliques_num = _extrair_cliques(row)
        alcance = _formatar_numero(alcance_num)
        cliques = _formatar_numero(cliques_num)
        actions = row.get("actions") or []
        leads = _extrair_leads(actions)
        spend = float(row.get("spend") or 0)
    cpl = (spend / leads) if leads > 0 else 0
    cpl_str = _formatar_brl(cpl)
    leads_str = _formatar_numero(leads)
    metricas = {
        "alcance": alcance,
        "cliques": cliques,
        "leads_str": leads_str,
        "cpl_str": cpl_str,
    }
    insight = _gerar_insight(leads, spend, cpl, alcance_num, cliques_num)
    texto = formatar_relatorio(metricas, cliente, dias, insight=insight)
    return True, texto


def get_saldo_conta(account_id: str) -> Optional[dict]:
    """
    Retorna saldo/info financeira da conta de anúncios.
    Campos: amount_spent, balance, spend_cap (API devolve em centavos);
    remaining = spend_cap - amount_spent (quanto ainda pode gastar).
    Valores no retorno já em reais (divididos por 100).
    """
    if not account_id or not account_id.startswith("act_"):
        return None
    if not META_ACCESS_TOKEN or not str(META_ACCESS_TOKEN).strip():
        return None
    url = f"{GRAPH_URL}/{account_id}"
    params = {
        "access_token": META_ACCESS_TOKEN.strip(),
        "fields": "amount_spent,balance,spend_cap,currency",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    try:
        amount_spent = float(data.get("amount_spent", 0) or 0) / 100
        balance = float(data.get("balance", 0) or 0) / 100
        spend_cap = float(data.get("spend_cap", 0) or 0) / 100
        remaining = max(0, spend_cap - amount_spent) if spend_cap else 0
        return {
            "amount_spent": amount_spent,
            "balance": balance,
            "spend_cap": spend_cap,
            "remaining": remaining,
            "currency": data.get("currency", "BRL"),
        }
    except (TypeError, ValueError):
        return None


# ── FUNÇÕES DE ESCRITA (Meta Ads API v21.0) ───────────────────────────────
import time as _time
import json as _json_meta

# Mapeamento interno → Meta API objective strings
_OBJETIVO_MAP = {
    "MESSAGES":   "OUTCOME_MESSAGES",
    "ENGAGEMENT": "OUTCOME_ENGAGEMENT",
    "PURCHASE":   "OUTCOME_SALES",
}

VALID_TOKEN_KEYS = {"META_TOKEN_PILOTI", "META_TOKEN_DENTTO", "META_ACCESS_TOKEN"}


def _resolve_token(token_key: str) -> str:
    """Resolve token_key para valor da env var. Lança ValueError se inválido."""
    import os
    if token_key not in VALID_TOKEN_KEYS:
        raise ValueError(f"token_key inválido: {token_key}")
    token = os.getenv(token_key, "").strip()
    if not token:
        raise ValueError(f"Variável {token_key} não definida ou vazia")
    return token


def upload_imagem(token: str, account_id: str, imagem_bytes: bytes, filename: str) -> dict:
    """Upload via /adimages. Retorna {'hash': '...'}."""
    url = f"{GRAPH_URL}/{account_id}/adimages"
    resp = requests.post(url, params={"access_token": token},
                         files={"filename": (filename, imagem_bytes)})
    data = resp.json()
    if "images" in data:
        img_data = list(data["images"].values())[0]
        return {"hash": img_data["hash"]}
    raise Exception(data.get("error", {}).get("message", "Erro no upload de imagem"))


def upload_video(token: str, account_id: str, video_bytes: bytes, filename: str) -> str:
    """Upload via /advideos. Polling até status=ready (máx 60s). Retorna video_id."""
    url = f"{GRAPH_URL}/{account_id}/advideos"
    resp = requests.post(url, params={"access_token": token},
                         files={"source": (filename, video_bytes)})
    data = resp.json()
    if "id" not in data:
        raise Exception(data.get("error", {}).get("message", "Erro no upload de vídeo"))

    video_id = data["id"]
    for _ in range(20):  # 20 x 3s = 60s máx
        _time.sleep(3)
        check = requests.get(f"{GRAPH_URL}/{video_id}",
                             params={"fields": "status", "access_token": token})
        video_status = check.json().get("status", {}).get("video_status", "")
        if video_status == "ready":
            return video_id
        if video_status == "error":
            raise Exception("Vídeo retornou status=error durante processamento")

    raise Exception("Timeout: vídeo não ficou pronto em 60 segundos")


def listar_publicos_salvos(token: str, account_id: str) -> list:
    """Lista saved audiences da conta. Retorna lista de dicts com id, name, targeting."""
    url = f"{GRAPH_URL}/{account_id}/saved_audiences"
    resp = requests.get(url, params={"fields": "id,name,targeting", "access_token": token, "limit": 50})
    data = resp.json()
    if "data" in data:
        return data["data"]
    raise Exception(data.get("error", {}).get("message", "Erro ao listar saved audiences"))


def listar_custom_audiences(token: str, account_id: str) -> list:
    """Lista custom audiences da conta. Retorna lista de dicts com id, name, subtype."""
    url = f"{GRAPH_URL}/{account_id}/customaudiences"
    resp = requests.get(url, params={"fields": "id,name,subtype", "access_token": token, "limit": 50})
    data = resp.json()
    if "data" in data:
        return data["data"]
    raise Exception(data.get("error", {}).get("message", "Erro ao listar custom audiences"))


def listar_paginas(token: str, business_id: str = None) -> list:
    """Lista páginas gerenciadas. Tenta /me/accounts; se vazio e business_id fornecido, usa /{biz}/owned_pages."""
    url = f"{GRAPH_URL}/me/accounts"
    resp = requests.get(url, params={"fields": "id,name,category", "access_token": token, "limit": 50})
    data = resp.json()
    if "data" in data and data["data"]:
        return data["data"]

    if business_id:
        url2 = f"{GRAPH_URL}/{business_id}/owned_pages"
        resp2 = requests.get(url2, params={"fields": "id,name,category", "access_token": token, "limit": 50})
        data2 = resp2.json()
        if "data" in data2:
            return data2["data"]
        raise Exception(data2.get("error", {}).get("message", "Erro ao listar páginas da BM"))

    return []


def listar_campanhas(token: str, account_id: str) -> list:
    """Lista campanhas ativas/pausadas da conta. Retorna lista de dicts."""
    url = f"{GRAPH_URL}/{account_id}/campaigns"
    resp = requests.get(url, params={
        "fields": "id,name,objective,status",
        "effective_status": '["ACTIVE","PAUSED"]',
        "access_token": token,
        "limit": 50,
    })
    data = resp.json()
    if "data" in data:
        return data["data"]
    raise Exception(data.get("error", {}).get("message", "Erro ao listar campanhas"))


def criar_campanha(token: str, account_id: str, campanha_tipo: str,
                   nome: str, orcamento: float, cbo: bool = True) -> str:
    """
    Cria campanha com status PAUSED.
    campanha_tipo: 'MESSAGES', 'ENGAGEMENT' ou 'PURCHASE' (mapeado para objective correto).
    cbo=True: orçamento ao nível da campanha (MESSAGES). PURCHASE usa orçamento no adset.
    Retorna campaign_id.
    """
    objetivo = _OBJETIVO_MAP.get(campanha_tipo, "OUTCOME_MESSAGES")
    url = f"{GRAPH_URL}/{account_id}/campaigns"
    payload = {
        "name": nome,
        "objective": objetivo,
        "status": "PAUSED",
        "special_ad_categories": "[]",
        "access_token": token,
    }
    if cbo:
        payload["daily_budget"] = int(orcamento * 100)  # Meta usa centavos
        payload["bid_strategy"] = "LOWEST_COST_WITHOUT_CAP"
    else:
        payload["is_adset_budget_sharing_enabled"] = "false"

    resp = requests.post(url, data=payload)
    data = resp.json()
    if "id" in data:
        return data["id"]
    raise Exception(data.get("error", {}).get("message", "Erro ao criar campanha"))


def criar_conjunto(token: str, account_id: str, campaign_id: str,
                   campanha_tipo: str, publico: dict, localizacao: dict,
                   orcamento: float = None, optimization_goal: str = None,
                   pixel_id: str = None, nome: str = None) -> str:
    """
    Cria ad set com status PAUSED.
    campanha_tipo: 'MESSAGES' → optimization_goal=CONVERSATIONS
                   'ENGAGEMENT' → optimization_goal=POST_ENGAGEMENT + orcamento no adset
    publico: {'idade_min': int, 'idade_max': int, 'genero': [1,2]}
    localizacao: {'paises': ['BR'], 'cidades': [{'key': '...', 'radius': 15, 'distance_unit': 'kilometer'}]}
    Retorna adset_id.
    """
    url = f"{GRAPH_URL}/{account_id}/adsets"
    targeting = {
        "age_min": publico.get("idade_min") or publico.get("age_min", 18),
        "age_max": publico.get("idade_max") or publico.get("age_max", 65),
        "geo_locations": {
            "countries": localizacao.get("paises", ["BR"]),
            "cities": localizacao.get("cidades", []),
        },
        "targeting_automation": {"advantage_audience": 0},
    }
    if publico.get("genders"):
        targeting["genders"] = publico["genders"]
    elif publico.get("genero"):
        targeting["genders"] = publico["genero"]
    if publico.get("custom_audience_id"):
        targeting["custom_audiences"] = [{"id": publico["custom_audience_id"]}]

    payload = {
        "campaign_id": campaign_id,
        "name": nome or f"Conjunto - {campanha_tipo}",
        "targeting": _json_meta.dumps(targeting),
        "status": "PAUSED",
        "access_token": token,
    }

    if campanha_tipo == "MESSAGES":
        payload["optimization_goal"] = "CONVERSATIONS"
        payload["billing_event"] = "IMPRESSIONS"
    elif campanha_tipo == "PURCHASE":
        goal = optimization_goal or "LINK_CLICKS"
        payload["optimization_goal"] = goal
        payload["billing_event"] = "IMPRESSIONS"
        payload["bid_strategy"] = "LOWEST_COST_WITHOUT_CAP"
        if goal == "OFFSITE_CONVERSIONS" and pixel_id:
            payload["promoted_object"] = _json_meta.dumps({"pixel_id": pixel_id, "custom_event_type": "PURCHASE"})
        if orcamento:
            payload["daily_budget"] = int(orcamento * 100)
    else:  # ENGAGEMENT
        payload["optimization_goal"] = "POST_ENGAGEMENT"
        payload["billing_event"] = "IMPRESSIONS"
        if orcamento:
            payload["daily_budget"] = int(orcamento * 100)

    resp = requests.post(url, data=payload)
    data = resp.json()
    if "id" in data:
        return data["id"]
    raise Exception(data.get("error", {}).get("message", "Erro ao criar conjunto"))


def criar_anuncio(token: str, account_id: str, adset_id: str, page_id: str,
                  creative_ref: dict, titulo: str, texto: str, cta: str,
                  link_url: str = "") -> str:
    """
    Cria AdCreative + Ad com status PAUSED.
    creative_ref: {'tipo': 'imagem', 'hash': '...'} ou {'tipo': 'video', 'video_id': '...'}
    page_id: obrigatório para object_story_spec (Facebook Page ID do cliente).
    cta: 'SEND_MESSAGE' | 'LEARN_MORE' | 'SIGN_UP'
    Retorna ad_id.
    """
    creative_url = f"{GRAPH_URL}/{account_id}/adcreatives"

    cta_value = {"value": {"link": link_url}} if link_url and cta != "SEND_MESSAGE" else {}

    if creative_ref["tipo"] == "imagem":
        link_data = {
            "image_hash": creative_ref["hash"],
            "message": texto,
            "name": titulo,
            "call_to_action": {"type": cta, **cta_value},
        }
        if link_url and cta != "SEND_MESSAGE":
            link_data["link"] = link_url
        story_spec = {"page_id": page_id, "link_data": link_data}
    elif creative_ref["tipo"] == "video":
        video_data = {
            "video_id": creative_ref["video_id"],
            "message": texto,
            "title": titulo,
            "call_to_action": {"type": cta, **cta_value},
        }
        if link_url and cta != "SEND_MESSAGE":
            video_data["link"] = link_url
        story_spec = {"page_id": page_id, "video_data": video_data}
    elif creative_ref["tipo"] == "carrossel":
        child_attachments = [
            {
                "link": link_url,
                "image_hash": card["hash"],
                "call_to_action": {"type": cta, "value": {"link": link_url}},
            }
            for card in creative_ref["cards"]
        ]
        link_data = {
            "link": link_url,
            "child_attachments": child_attachments,
            "multi_share_optimized": True,
        }
        story_spec = {"page_id": page_id, "link_data": link_data}
    else:
        raise ValueError(f"creative_ref.tipo desconhecido: {creative_ref['tipo']}")

    cr = requests.post(creative_url, data={
        "name": f"Criativo - {titulo[:30]}",
        "object_story_spec": _json_meta.dumps(story_spec),
        "access_token": token,
    })
    cr_data = cr.json()
    if "id" not in cr_data:
        raise Exception(cr_data.get("error", {}).get("message", "Erro ao criar criativo"))
    creative_id = cr_data["id"]

    ad_url = f"{GRAPH_URL}/{account_id}/ads"
    ad = requests.post(ad_url, data={
        "name": titulo[:40],
        "adset_id": adset_id,
        "creative": _json_meta.dumps({"creative_id": creative_id}),
        "status": "PAUSED",
        "access_token": token,
    })
    ad_data = ad.json()
    if "id" in ad_data:
        return ad_data["id"]
    raise Exception(ad_data.get("error", {}).get("message", "Erro ao criar anúncio"))


def deletar_objeto_meta(token: str, objeto_id: str) -> None:
    """Deleta campanha/conjunto/anúncio pelo ID (usado em rollback)."""
    requests.delete(f"{GRAPH_URL}/{objeto_id}", params={"access_token": token})


# ── GESTOR IA — helpers de leitura e atualização ──────────────────────────

def get_ad(token: str, ad_id: str) -> dict:
    """Retorna estado atual de um ad (id, name, status, effective_status)."""
    resp = requests.get(
        f"{GRAPH_URL}/{ad_id}",
        params={"fields": "id,name,status,effective_status", "access_token": token},
        timeout=15,
    )
    data = resp.json()
    if "error" in data:
        raise Exception(data["error"].get("message", "Erro ao buscar ad"))
    return data


def get_adset(token: str, adset_id: str) -> dict:
    """Retorna estado atual de um adset (id, name, status, daily_budget)."""
    resp = requests.get(
        f"{GRAPH_URL}/{adset_id}",
        params={"fields": "id,name,status,daily_budget,lifetime_budget", "access_token": token},
        timeout=15,
    )
    data = resp.json()
    if "error" in data:
        raise Exception(data["error"].get("message", "Erro ao buscar adset"))
    return data


def atualizar_status_ad(token: str, ad_id: str, status: str) -> None:
    """Atualiza status de um ad. status: 'ACTIVE' | 'PAUSED'."""
    resp = requests.post(
        f"{GRAPH_URL}/{ad_id}",
        params={"access_token": token},
        data={"status": status},
        timeout=15,
    )
    data = resp.json()
    if "error" in data:
        raise Exception(data["error"].get("message", f"Erro ao atualizar status do ad {ad_id}"))


def atualizar_status_campanha(token: str, campaign_id: str, status: str) -> None:
    """Atualiza status de uma campanha. status: 'ACTIVE' | 'PAUSED'."""
    resp = requests.post(
        f"{GRAPH_URL}/{campaign_id}",
        params={"access_token": token},
        data={"status": status},
        timeout=15,
    )
    data = resp.json()
    if "error" in data:
        raise Exception(data["error"].get("message", f"Erro ao atualizar status da campanha {campaign_id}"))


def atualizar_orcamento_conjunto(token: str, adset_id: str, daily_budget_cents: int) -> None:
    """
    Atualiza daily_budget de um adset.
    daily_budget_cents: valor em centavos (ex: R$50 → 5000).
    Executor calcula: novo = int(atual_cents * (1 + escala_pct/100)).
    """
    resp = requests.post(
        f"{GRAPH_URL}/{adset_id}",
        params={"access_token": token},
        data={"daily_budget": str(daily_budget_cents)},
        timeout=15,
    )
    data = resp.json()
    if "error" in data:
        raise Exception(data["error"].get("message", f"Erro ao atualizar orçamento do adset {adset_id}"))
