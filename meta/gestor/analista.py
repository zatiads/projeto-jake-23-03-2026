"""
Gestor IA — Analista.
Recebe perfis agregados de todas as contas e retorna decisões via Claude.
1 chamada Claude por execução, independente do número de contas.
"""
import os
import json
import logging
from typing import List, Dict, Any

_log = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv("/root/.env")
except ImportError:
    pass


def _anthropic_client():
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY não configurado")
    return anthropic.Anthropic(api_key=api_key)


_SYSTEM_PROMPT = """Você é um gestor expert de tráfego pago Meta Ads. Você gerencia múltiplas contas e toma decisões de otimização baseadas no histórico de cada conta.

REGRAS DE DECISÃO:
1. Se a conta tem histórico (cpl_medio não nulo e dias_historico >= 14): analise pelo perfil histórico — CPL acima da média + 1 desvio padrão é sinal de problema; frequência > 3.5 indica fadiga criativa
2. Se a conta tem < 14 dias de histórico ou cpl_medio nulo: use gestor_config como fallback (cpl_max, freq_max)
3. Se nem histórico nem config: apenas monitore, não aja (acoes=[])
4. SALDO — depende do tipo_pagamento da conta:
   - tipo_pagamento="pix": se saldo.remaining < 200, emita alerta SALDO_CRITICO. NUNCA pause a conta por saldo — apenas avise para solicitar recarga.
   - tipo_pagamento="cartao": IGNORE saldo completamente. Contas de cartão de crédito têm cobrança automática. Não emita nenhum alerta de saldo para essas contas.

AÇÕES DISPONÍVEIS (executam no Meta Ads — precisam de aprovação do usuário):
- pausar_ad: {"tipo": "pausar_ad", "entidade_id": "<ad_id>", "entidade_nome": "<nome>", "motivo": "..."}
- reativar_ad: {"tipo": "reativar_ad", "entidade_id": "<ad_id>", "entidade_nome": "<nome>", "motivo": "CPL voltou ao normal"}
  → Use apenas se CPL voltou abaixo do threshold e o ad estava pausado por performance
- escalar_orcamento: {"tipo": "escalar_orcamento", "entidade_id": "<adset_id>", "entidade_nome": "<nome>", "motivo": "..."}
  → Escale apenas quando o melhor performer estiver claramente ABAIXO do threshold (CPL bom)
- reduzir_orcamento: {"tipo": "reduzir_orcamento", "entidade_id": "<adset_id>", "entidade_nome": "<nome>", "motivo": "..."}
  → Use quando CPL > limite + 30% mas pausar o ad seria prematuro — reduz 20% do orçamento
- duplicar_ad: {"tipo": "duplicar_ad", "entidade_id": "<ad_id>", "entidade_nome": "<nome>", "motivo": "..."}
  → Use quando top_ads[0] tem CPL 40% abaixo da média E frequência < 2.0 — duplica para teste

ALERTAS DISPONÍVEIS (não executam no Meta — só informam no WhatsApp):
Use o campo "alertas" (lista de strings) para situações que não requerem ação imediata:
- "FREQ_ALTA: <ad_nome> freq=<X>" quando algum ad tem freq > 2.5 e < 3.5
- "ZERO_CONV: <X> dias sem conversao" quando metricas.dias_sem_conversao >= 3
- "LEARNING_TRAVADO: <N> ads em aprendizado" quando metricas.ads_em_learning > 0
- "SALDO_CRITICO: R$<X> restantes" quando tipo_pagamento=pix e saldo.remaining < 200
- "SEM_VEICULACAO: sem gasto ontem" quando metricas.gasto_ontem == 0
- "CPL_SEMANAL: CPL subiu/caiu X%" quando metricas.cpl_semana_anterior não é null

FORMATO DE RESPOSTA — retorne APENAS JSON válido, sem markdown:
[
  {
    "cliente_id": <int>,
    "conta": "<nome>",
    "analise": "<1-2 frases explicando o diagnóstico>",
    "acoes": [...],
    "alertas": ["<texto de alerta se houver>"]
  }
]

Se uma conta não requer ação nem alerta, retorne acoes=[] e alertas=[].
Seja conservador: prefira alertar a agir quando houver dúvida.
"""


def analisar(perfis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Recebe lista de perfis do coletor.
    Retorna lista de decisões por conta (mesmo índice).
    """
    # Filtrar contas com erro de token — retornar decisão vazia para elas
    perfis_validos = [p for p in perfis if not p.get("erro")]
    perfis_erro    = [p for p in perfis if p.get("erro")]

    decisoes_erro = [
        {
            "cliente_id": p["cliente_id"],
            "conta":      p["nome"],
            "analise":    f"Erro de configuração: {p['erro']}",
            "acoes":      [],
            "alertas":    [p["erro"]],
        }
        for p in perfis_erro
    ]

    if not perfis_validos:
        return decisoes_erro

    # Serializar perfis para o prompt (sem token_key — segurança)
    perfis_prompt = []
    for p in perfis_validos:
        perfis_prompt.append({
            "cliente_id":  p["cliente_id"],
            "nome":        p["nome"],
            "agencia":     p["agencia"],
            "account_id":  p["account_id"],
            "objetivo":    p["objetivo"],
            "saldo":       p.get("saldo"),
            "metricas":    p.get("metricas"),
            "gestor_config": p.get("gestor_config"),
        })

    user_msg = (
        "Analise estas contas e retorne as decisões de otimização em JSON:\n\n"
        + json.dumps(perfis_prompt, ensure_ascii=False, indent=2)
    )

    client = _anthropic_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = msg.content[0].text.strip() if msg.content else ""
    # Limpar markdown via regex (robusto para ```json, ``` \njson, ```JSON)
    import re as _re
    match = _re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, _re.IGNORECASE)
    if match:
        raw = match.group(1).strip()

    try:
        decisoes_validas = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        # Fallback: retornar decisões vazias para todos os perfis válidos
        _log.error("analista: falha ao parsear JSON do Claude. Raw: %s", raw[:500])
        decisoes_validas = [
            {"cliente_id": p["cliente_id"], "conta": p["nome"],
             "analise": "Falha ao parsear resposta do Claude. Nenhuma ação aplicada.",
             "acoes": [], "alertas": []}
            for p in perfis_validos
        ]

    # Merge: preservar ordem original dos perfis
    decisoes_por_id = {d["cliente_id"]: d for d in decisoes_validas}
    resultado = []
    for p in perfis:
        cid = p["cliente_id"]
        if p.get("erro"):
            resultado.append(next(d for d in decisoes_erro if d["cliente_id"] == cid))
        else:
            resultado.append(decisoes_por_id.get(cid, {
                "cliente_id": cid,
                "conta": p["nome"],
                "analise": "Sem dados suficientes para análise.",
                "acoes": [],
                "alertas": [],
            }))
    return resultado
