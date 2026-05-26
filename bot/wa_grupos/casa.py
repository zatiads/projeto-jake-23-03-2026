"""
wa_grupos/casa.py — Lógica específica do grupo Casa.
"""
import os
import logging
import re
import threading

logger = logging.getLogger(__name__)

CASA_GROUP_JID = "120363310359411409@g.us"


def handle_mensagem_casa(texto: str, key: dict, processar_fn=None) -> bool:
    """
    Processa mensagem recebida no grupo Casa.

    - Se menciona 'jake': chama processar_fn(CASA_GROUP_JID, texto_limpo) em thread.
    - Caso contrário: salva item na tabela lista_compras.

    Retorna True se processou, False se ignorou (texto vazio).
    """
    texto = texto.strip()
    if not texto:
        return False

    if "jake" in texto.lower():
        texto_cmd = re.sub(r"(?i)^@?jake\s*(ia)?\s*[,:]?\s*", "", texto).strip()
        if not texto_cmd:
            texto_cmd = texto
        logger.info(f"Mencao ao Jake no grupo Casa: {texto_cmd!r}")
        if processar_fn:
            def _run():
                try:
                    processar_fn(CASA_GROUP_JID, texto_cmd)
                except Exception as e:
                    logger.error(f"Erro ao processar mencao grupo Casa: {e}", exc_info=True)
            threading.Thread(target=_run, daemon=True).start()
        return True

    # Salvar na lista de compras
    remetente = key.get("participant", "")
    try:
        import psycopg2
        conn = psycopg2.connect(os.environ.get("DATABASE_URL", ""))
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO lista_compras (item, adicionado_por) VALUES (%s, %s)",
            (texto, remetente)
        )
        conn.commit()
        conn.close()
        logger.info(f"Item adicionado na lista: {texto!r} por {remetente}")
    except Exception as e:
        logger.error(f"Erro ao salvar item lista_compras: {e}")

    return True
