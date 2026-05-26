"""
wa_grupos/viagem_chile.py — Lógica específica do grupo Viagem Chile.
[NOVO] Este arquivo não existia antes — adiciona roteamento novo ao webhook.
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)

VIAGEM_GROUP_JID = "120363403675290579@g.us"
VIAGEM_DATA = date(2026, 8, 9)


def handle_mensagem_viagem(texto: str, key: dict, processar_fn=None) -> bool:
    """
    Processa mensagem recebida no grupo Viagem Chile.
    Por ora retorna False (placeholder para lógica futura).
    """
    return False
