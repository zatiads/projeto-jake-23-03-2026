"""
Conexão com o banco Neon (PostgreSQL).
Use DATABASE_URL no .env.
"""
import os

try:
    from dotenv import load_dotenv
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def get_conn():
    """Abre e retorna uma conexão com o Neon. Fecha com conn.close()."""
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def testar_conexao():
    """Testa a conexão e retorna (True, mensagem) ou (False, erro)."""
    if not DATABASE_URL:
        return False, "DATABASE_URL não definido no .env"
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        return True, "Conexão com Neon OK."
    except Exception as e:
        return False, str(e)


def executar(sql, params=None):
    """Executa uma query (SELECT ou outro) e retorna os resultados. Para INSERT/UPDATE, use commit=True no get_conn()."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        if cur.description:
            rows = cur.fetchall()
        else:
            conn.commit()
            rows = None
        cur.close()
        return rows
    finally:
        conn.close()
