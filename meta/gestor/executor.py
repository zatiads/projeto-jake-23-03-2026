"""
Gestor IA — Executor.
Aplica decisões do Analista no Meta Ads e loga no banco.
Expõe reverter(acao_id) para rollback via Jake OS.
"""
import os
import json
import psycopg2
import psycopg2.extras
from typing import List, Dict, Any

from meta.meta_api import (
    get_ad, get_adset,
    atualizar_status_ad, atualizar_status_campanha,
    atualizar_orcamento_conjunto,
    _resolve_token,
)


def _get_db():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido")
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def executar(
    decisoes: List[Dict[str, Any]],
    perfis: List[Dict[str, Any]],
    varredura_id: int,
    db_conn=None,
) -> Dict[str, int]:
    """
    Aplica todas as ações das decisões no Meta e loga no banco.
    Retorna contadores: {"ok": N, "erro": N, "alertas": N}.
    """
    fechar = False
    if db_conn is None:
        db_conn = _get_db()
        fechar = True

    # Mapear cliente_id → perfil (para token_key e gestor_config)
    perfil_map = {p["cliente_id"]: p for p in perfis}

    contadores = {"ok": 0, "erro": 0, "alertas": 0}

    try:
        cur = db_conn.cursor()

        for decisao in decisoes:
            cid    = decisao["cliente_id"]
            perfil = perfil_map.get(cid)
            if not perfil or perfil.get("erro"):
                continue

            token_key  = perfil["token_key"]
            account_id = perfil["account_id"]
            config     = perfil.get("gestor_config") or {}
            escala_pct = float(config.get("escala_pct", 15))

            try:
                token = _resolve_token(token_key)
            except ValueError as e:
                contadores["erro"] += 1
                continue

            # Registrar alertas (sem ação no Meta)
            for alerta in decisao.get("alertas", []):
                cur.execute("""
                    INSERT INTO gestor_acoes
                        (varredura_id, cliente_id, account_id, tipo, entidade_id,
                         entidade_nome, motivo, status)
                    VALUES (%s,%s,%s,'alerta_saldo',%s,%s,%s,'sucesso')
                """, (varredura_id, cid, account_id, account_id, decisao["conta"], alerta))
                contadores["alertas"] += 1

            # Executar ações
            for acao in decisao.get("acoes", []):
                tipo         = acao["tipo"]
                entidade_id  = acao["entidade_id"]
                entidade_nome = acao.get("entidade_nome", "")
                motivo       = acao.get("motivo", "")
                valor_antes  = None
                valor_depois = None

                try:
                    if tipo == "pausar_ad":
                        estado = get_ad(token, entidade_id)
                        valor_antes  = {"status": estado.get("status")}
                        valor_depois = {"status": "PAUSED"}
                        atualizar_status_ad(token, entidade_id, "PAUSED")

                    elif tipo == "escalar_orcamento":
                        estado = get_adset(token, entidade_id)
                        atual_cents = int(estado.get("daily_budget") or 0)
                        novo_cents  = int(atual_cents * (1 + escala_pct / 100))
                        valor_antes  = {"daily_budget": atual_cents}
                        valor_depois = {"daily_budget": novo_cents}
                        atualizar_orcamento_conjunto(token, entidade_id, novo_cents)

                    elif tipo == "pausar_conta":
                        valor_antes  = {"status": "ACTIVE"}
                        valor_depois = {"status": "PAUSED"}
                        atualizar_status_campanha(token, entidade_id, "PAUSED")

                    else:
                        continue

                    cur.execute("""
                        INSERT INTO gestor_acoes
                            (varredura_id, cliente_id, account_id, tipo, entidade_id,
                             entidade_nome, valor_antes, valor_depois, motivo, status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'sucesso')
                    """, (
                        varredura_id, cid, account_id, tipo, entidade_id,
                        entidade_nome,
                        json.dumps(valor_antes), json.dumps(valor_depois),
                        motivo,
                    ))
                    contadores["ok"] += 1

                except Exception as e:
                    cur.execute("""
                        INSERT INTO gestor_acoes
                            (varredura_id, cliente_id, account_id, tipo, entidade_id,
                             entidade_nome, motivo, status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,'erro')
                    """, (varredura_id, cid, account_id, tipo, entidade_id, entidade_nome,
                          f"{motivo} | Erro: {e}"))
                    contadores["erro"] += 1

        db_conn.commit()
    finally:
        if fechar:
            db_conn.close()

    return contadores


def reverter(acao_id: int, db_conn=None) -> None:
    """
    Reverte uma ação pelo ID. Restaura valor_antes no Meta e marca revertido=TRUE no banco.
    Lança Exception se ação não encontrada, já revertida, ou tipo não revertível.
    """
    fechar = False
    if db_conn is None:
        db_conn = _get_db()
        fechar = True

    try:
        cur = db_conn.cursor()
        cur.execute(
            "SELECT * FROM gestor_acoes WHERE id = %s",
            (acao_id,)
        )
        acao = cur.fetchone()
        if not acao:
            raise Exception(f"Ação {acao_id} não encontrada")
        if acao["revertido"]:
            raise Exception(f"Ação {acao_id} já foi revertida")
        if acao["status"] != "sucesso":
            raise Exception(f"Só é possível reverter ações com status 'sucesso'")

        tipo        = acao["tipo"]
        entidade_id = acao["entidade_id"]
        valor_antes = acao["valor_antes"] or {}
        token_key   = None

        # Buscar token_key da conta
        cur2 = db_conn.cursor()
        cur2.execute(
            "SELECT token_key FROM ad_client_profiles WHERE id = %s",
            (acao["cliente_id"],)
        )
        row = cur2.fetchone()
        if not row:
            raise Exception("Cliente não encontrado")
        token = _resolve_token(row["token_key"])

        if tipo == "pausar_ad":
            status_original = valor_antes.get("status", "ACTIVE")
            atualizar_status_ad(token, entidade_id, status_original)

        elif tipo == "escalar_orcamento":
            budget_original = int(valor_antes.get("daily_budget", 0))
            atualizar_orcamento_conjunto(token, entidade_id, budget_original)

        elif tipo == "pausar_conta":
            atualizar_status_campanha(token, entidade_id, "ACTIVE")

        else:
            raise Exception(f"Tipo '{tipo}' não suporta rollback")

        cur.execute("""
            UPDATE gestor_acoes
            SET revertido = TRUE, revertido_em = NOW()
            WHERE id = %s
        """, (acao_id,))
        db_conn.commit()

    finally:
        if fechar:
            db_conn.close()
