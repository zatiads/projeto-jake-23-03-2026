"""
Gestor IA — Analista.
Recebe perfis agregados de todas as contas e retorna decisões via Claude.
1 chamada Claude por execução, independente do número de contas.
"""
import os
import json
import logging
from typing import List, Dict, Any

try:
    from meta.gestor.conhecimento.contexto import montar_contexto as _montar_contexto
except Exception:
    _montar_contexto = None  # type: ignore

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
1. Se a conta tem histórico (cpl_medio não nulo e dias_historico >= 14): analise pelo perfil histórico — custo por resultado acima da média + 1 desvio padrão do histórico é sinal de problema; frequência > 3.5 indica fadiga criativa
2. Se a conta tem < 14 dias de histórico ou cpl_medio nulo: use gestor_config como fallback (cpl_max, freq_max)
3. Se nem histórico nem config: apenas monitore, não aja (acoes=[])

REGRAS DE MATURIDADE — OBRIGATÓRIAS antes de pausar qualquer ad:
- NÃO pause um ad com dias_rodando < 7. Ads novos precisam de pelo menos 7 dias para estabilizar.
- NÃO pause um ad com spend < R$50 nos últimos 30 dias. Dados insuficientes.
- NÃO pause um ad com conversoes < 2 nos últimos 30 dias, a menos que o spend seja > R$150. Uma conversão isolada pode ser distorção pontual.
- Prefira ALERTAR ao invés de PAUSAR quando o ad está dentro da margem (custo no limite, não muito acima).

ANÁLISE DE TENDÊNCIA — use os dois horizontes:
- Baseline 30 dias: cpl_medio e cpl_desvio da conta
- Tendência 7 dias: dados diários (gasto_ontem, dias_sem_conversao) para confirmar a direção
- Só pause se a tendência dos últimos 7 dias CONFIRMAR a piora — não pause só com dados de 30d se o ad é recente

ESCALADA DE ORÇAMENTO:
- Quando o melhor ad (top_ads[0]) tem custo 30%+ abaixo do limite histórico E frequência < 2.5, use escalar_orcamento no CONJUNTO (adset) desse ad.
- Use o adset_id e adset_name de top_ads[0] para identificar o conjunto correto.
- Não sugira aumentar orçamento e pausar outro anúncio na mesma ação — são decisões separadas.
4. SALDO — regra ABSOLUTA e INVIOLÁVEL baseada em tipo_pagamento:
   - tipo_pagamento="pix": se saldo.remaining < 300, emita alerta SALDO_CRITICO. NUNCA pause a conta por saldo — apenas avise para solicitar recarga.
   - tipo_pagamento="cartao": NUNCA emita SALDO_CRITICO nem qualquer alerta relacionado a saldo. Ponto final. Contas de cartão têm cobrança automática, o saldo não importa.
5. ZERO_CONV — regra ABSOLUTA: NUNCA emita ZERO_CONV para contas com objetivo="ENGAGEMENT". Campanhas de engajamento, visitas ao perfil e reconhecimento de marca não geram conversões — isso é esperado e correto. ZERO_CONV só se aplica a contas com objetivo="MESSAGES" ou "PURCHASE".

AÇÕES DISPONÍVEIS (executam no Meta Ads — precisam de aprovação do usuário):
- pausar_ad: {"tipo": "pausar_ad", "entidade_id": "<ad_id>", "entidade_nome": "<nome do ad>", "motivo": "..."}
- reativar_ad: {"tipo": "reativar_ad", "entidade_id": "<ad_id>", "entidade_nome": "<nome>", "motivo": "custo por resultado voltou ao normal"}
  → Use apenas se custo por resultado voltou abaixo do limite histórico e o ad estava pausado por performance
- escalar_orcamento: {"tipo": "escalar_orcamento", "entidade_id": "<adset_id>", "entidade_nome": "<nome do conjunto>", "motivo": "..."}
  → Use quando o melhor ad (top_ads[0]) tem custo claramente abaixo do limite histórico E frequência < 2.5. Use o adset_id e adset_name do top_ads[0] para identificar o conjunto correto.
- reduzir_orcamento: {"tipo": "reduzir_orcamento", "entidade_id": "<adset_id>", "entidade_nome": "<nome do conjunto>", "motivo": "..."}
  → Use quando custo por resultado > limite + 30% mas pausar o ad seria prematuro — reduz 20% do orçamento

NOMENCLATURA POR OBJETIVO — use sempre estes nomes no campo "motivo":
- objetivo="MESSAGES": chame a métrica de "custo por conversa"
- objetivo="PURCHASE": chame a métrica de "custo por venda"
- objetivo="ENGAGEMENT": chame a métrica de "custo por clique"

FORMATO DO CAMPO "motivo" — use linguagem clara e direta, SEM termos técnicos:
- NÃO use: "threshold", "1dp", "desvio padrão", "média + 1dp"
- USE: "limite histórico" para se referir ao teto calculado pelo histórico
- Exemplos corretos:
  - "Custo por conversa R$142 acima do limite histórico R$128 (média dos últimos 30 dias)"
  - "Frequência 4.8 indica público saturado (limite: 3.5)"
  - "Melhor anúncio com custo por conversa R$72, bem abaixo do limite histórico, frequência saudável 1.17"
  - "Custo por conversa R$72 é 45% abaixo da média — duplicar para escalar"

FORMATO DE RESPOSTA — retorne APENAS JSON válido, sem markdown:
[
  {
    "cliente_id": <int>,
    "conta": "<nome>",
    "analise": "<1-2 frases explicando o diagnóstico>",
    "acoes": [...],
    "alertas": []
  }
]

Alertas (saldo, frequência, sem veiculação) são gerados automaticamente — retorne sempre alertas=[].
Foque exclusivamente nas ações de otimização. Seja conservador: só aja quando os dados confirmam o problema.
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
            "cliente_id":    p["cliente_id"],
            "nome":          p["nome"],
            "agencia":       p["agencia"],
            "account_id":    p["account_id"],
            "objetivo":      p["objetivo"],
            "tipo_pagamento": p.get("tipo_pagamento", "pix"),
            "saldo":         p.get("saldo"),
            "metricas":      p.get("metricas"),
            "gestor_config": p.get("gestor_config"),
        })

    # Injetar conhecimento de gestor sênior no system_prompt
    system_prompt = _SYSTEM_PROMPT
    if _montar_contexto is not None:
        bloco = _montar_contexto(perfis_validos)
        if bloco:
            system_prompt = _SYSTEM_PROMPT + "\n\n" + bloco

    user_msg = (
        "Analise estas contas e retorne as decisões de otimização em JSON:\n\n"
        + json.dumps(perfis_prompt, ensure_ascii=False, indent=2)
    )

    client = _anthropic_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=system_prompt,
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
