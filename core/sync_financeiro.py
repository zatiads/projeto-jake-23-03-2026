"""
Sync e gestão do financeiro pessoal do Bruno.

- auto_importar_recorrentes(): copia entradas/saídas fixas do fin_raiox para
  fin_transacoes no mês corrente. Idempotente — não duplica.
- registrar_transacao(): adiciona transação manual via WhatsApp.
- resumo_mes(): retorna dict com receitas, despesas, saldo do mês.
"""
import os
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

_log = logging.getLogger(__name__)


def _get_db():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL nao configurado")
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def auto_importar_recorrentes(mes: int = None, ano: int = None) -> int:
    """
    Importa transações recorrentes do fin_raiox para fin_transacoes.
    Roda no início de cada mês — não duplica se já existir dados do mês.
    Retorna número de transações inseridas.
    """
    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year
    idx = mes - 1  # jan=0 … dez=11

    conn = _get_db()
    try:
        cur = conn.cursor()

        # Idempotência: já existe alguma recorrente deste mês?
        cur.execute("""
            SELECT COUNT(*) as n FROM fin_transacoes
            WHERE EXTRACT(YEAR FROM data)=%s
              AND EXTRACT(MONTH FROM data)=%s
              AND recorrente = TRUE
        """, (ano, mes))
        if cur.fetchone()["n"] > 0:
            _log.info("auto_importar_recorrentes: %d/%d ja importado", mes, ano)
            return 0

        cur.execute("SELECT nome, grupo, valores FROM fin_raiox")
        rows = cur.fetchall()

        data_ref = date(ano, mes, 5)  # dia 5 como referência
        inseridas = 0

        for row in rows:
            valores = row["valores"]
            if isinstance(valores, str):
                valores = json.loads(valores)

            if idx >= len(valores):
                continue
            valor = float(valores[idx])
            if valor <= 0:
                continue

            grupo = row["grupo"]
            tipo      = "Entrada" if grupo == "entradas" else "Saída"
            categoria = "Fixa"    if grupo in ("entradas", "fixas") else "Variável"

            cur.execute(
                "INSERT INTO fin_transacoes (descricao, valor, tipo, categoria, recorrente, data) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (row["nome"], valor, tipo, categoria, True, data_ref),
            )
            inseridas += 1

        conn.commit()
        _log.info("auto_importar_recorrentes: %d transacoes inseridas em %d/%d", inseridas, mes, ano)
        return inseridas
    finally:
        conn.close()


def registrar_transacao(descricao: str, valor: float, tipo: str,
                        categoria: str = "Variável", data_str: str = None) -> bool:
    """
    Registra transação manual.
    tipo: 'Entrada' ou 'Saída'
    data_str: 'YYYY-MM-DD' (padrão: hoje)
    """
    try:
        from datetime import datetime
        data = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else date.today()
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO fin_transacoes (descricao, valor, tipo, categoria, recorrente, data) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (descricao, abs(valor), tipo, categoria, False, data),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        _log.error("registrar_transacao error: %s", e)
        return False


def resumo_mes(mes: int = None, ano: int = None) -> dict:
    """Retorna {'receitas', 'despesas', 'saldo', 'mes', 'ano'} do mês."""
    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year

    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT tipo, SUM(valor) as total
            FROM fin_transacoes
            WHERE EXTRACT(YEAR FROM data)=%s AND EXTRACT(MONTH FROM data)=%s
            GROUP BY tipo
        """, (ano, mes))
        totais = {r["tipo"]: float(r["total"]) for r in cur.fetchall()}

        receitas = totais.get("Entrada", 0.0)
        despesas = totais.get("Saída",   0.0)
        return {
            "mes": mes, "ano": ano,
            "receitas": receitas,
            "despesas": despesas,
            "saldo":    receitas - despesas,
        }
    finally:
        conn.close()
