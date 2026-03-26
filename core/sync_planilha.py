"""
Sincroniza a planilha 'controle_relatorios_semanais' (Google Sheets) com a tabela
controle_relatorios_semanais no Neon. Rodar após alterações na planilha ou em cron.
"""
import os
from datetime import datetime

# Carrega .env (raiz do projeto = pai de core/)
try:
    from dotenv import load_dotenv
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

from core import db

TABELA = "controle_relatorios_semanais"


def _valor(r, *chaves):
    """Pega o primeiro valor não vazio do dict r para as chaves (planilha pode variar maiúsculas)."""
    for k in chaves:
        v = r.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return None


def criar_tabela_se_nao_existir():
    """Cria a tabela no Neon se ainda não existir."""
    sql = f"""
    CREATE TABLE IF NOT EXISTS {TABELA} (
        cliente TEXT PRIMARY KEY,
        id_conta TEXT,
        modelo_relatorio TEXT,
        tag_captacao TEXT,
        tag_engajamento TEXT,
        frequencia TEXT,
        chat_id TEXT,
        status TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    conn = db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        cur.close()
    finally:
        conn.close()


def sincronizar_planilha_para_db():
    """
    Lê todos os registros da planilha e faz upsert na tabela Neon.
    Retorna (quantidade_inserida_atualizada, erro ou None).
    """
    try:
        from leitor_planilha import buscar_todos_registros
    except ImportError:
        return 0, "leitor_planilha não disponível"

    criar_tabela_se_nao_existir()
    registros = buscar_todos_registros()
    if not registros:
        return 0, None

    conn = db.get_conn()
    try:
        cur = conn.cursor()
        # Upsert: atualiza se já existir (chave = cliente)
        sql = f"""
        INSERT INTO {TABELA}
            (cliente, id_conta, modelo_relatorio, tag_captacao, tag_engajamento, frequencia, chat_id, status, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (cliente) DO UPDATE SET
            id_conta = EXCLUDED.id_conta,
            modelo_relatorio = EXCLUDED.modelo_relatorio,
            tag_captacao = EXCLUDED.tag_captacao,
            tag_engajamento = EXCLUDED.tag_engajamento,
            frequencia = EXCLUDED.frequencia,
            chat_id = EXCLUDED.chat_id,
            status = EXCLUDED.status,
            updated_at = NOW();
        """
        for r in registros:
            cliente = _valor(r, "Cliente", "cliente")
            if not cliente:
                continue
            cur.execute(sql, (
                cliente,
                _valor(r, "ID da Conta", "ID da conta", "id_conta"),
                _valor(r, "Modelo de relatório", "modelo de relatório", "modelo_relatorio"),
                _valor(r, "Tag captação", "tag captação", "tag_captacao"),
                _valor(r, "Tag Engajamento", "Tag engajamento", "tag_engajamento"),
                _valor(r, "frequencia", "Frequencia", "Frequência"),
                _valor(r, "chat id", "chat_id", "chat id"),
                (r.get("status") or r.get("Status") or "").strip().lower() or None,
            ))
        conn.commit()
        cur.close()
        return len(registros), None
    except Exception as e:
        conn.rollback()
        return 0, str(e)
    finally:
        conn.close()


def listar_clientes_ativos_do_db():
    """
    Retorna lista de dicts com clientes ativos já sincronizados no Neon.
    Útil para usar após sync (evita chamar a planilha de novo).
    """
    if not db.DATABASE_URL:
        return []
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT cliente, id_conta, modelo_relatorio, tag_captacao, tag_engajamento, frequencia, chat_id, status FROM {TABELA} WHERE LOWER(TRIM(status)) = 'ativo' ORDER BY cliente"
        )
        colunas = [d[0] for d in cur.description]
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(zip(colunas, row)) for row in rows]
    except Exception:
        return []


if __name__ == "__main__":
    # Rodar: cd /root && PYTHONPATH=/root /root/venv/bin/python3 -m core.sync_planilha
    n, err = sincronizar_planilha_para_db()
    if err:
        print("Erro:", err)
    else:
        print(f"Sync OK: {n} registro(s) na planilha sincronizado(s) para o Neon.")
