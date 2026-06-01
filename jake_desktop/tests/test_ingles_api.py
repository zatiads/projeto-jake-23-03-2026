import sys, pytest
sys.path.insert(0, '/root/jake_desktop')
from unittest.mock import MagicMock, patch, call


def _mock_conn(rows=None, one=None):
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    if rows is not None:
        cur.fetchall.return_value = rows
    if one is not None:
        cur.fetchone.return_value = one
    return conn


def test_init_ingles_tables_cria_tabelas():
    """_init_ingles_tables() deve executar CREATE TABLE IF NOT EXISTS para as 3 tabelas."""
    conn = _mock_conn()
    with patch("app._get_db", return_value=conn):
        import app
        app._init_ingles_tables()
    sql_calls = " ".join(str(c) for c in conn.cursor().execute.call_args_list)
    assert "ingles_palavras" in sql_calls
    assert "ingles_sessoes" in sql_calls
    assert "ingles_atividades" in sql_calls
    conn.commit.assert_called()
