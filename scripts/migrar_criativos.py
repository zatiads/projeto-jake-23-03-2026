#!/usr/bin/env python3
"""
Script one-shot: cria tabelas creative_folders e creative_history no Neon.
Executar: PYTHONPATH=/root python3 scripts/migrar_criativos.py
"""
import sys
sys.path.insert(0, '/root')
from core.db import get_conn

SQL = """
CREATE TABLE IF NOT EXISTS creative_folders (
    id        SERIAL PRIMARY KEY,
    nome      VARCHAR(100) NOT NULL,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS creative_history (
    id               SERIAL PRIMARY KEY,
    tipo             VARCHAR(10)  NOT NULL CHECK (tipo IN ('imagem','video')),
    modo             VARCHAR(20)  NOT NULL,
    modelo           VARCHAR(50)  NOT NULL,
    prompt_original  TEXT         NOT NULL,
    prompt_expandido TEXT         NOT NULL,
    url_resultado    TEXT         NOT NULL,
    folder_id        INTEGER      REFERENCES creative_folders(id) ON DELETE SET NULL,
    criado_em        TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_creative_history_tipo    ON creative_history(tipo);
CREATE INDEX IF NOT EXISTS idx_creative_history_folder  ON creative_history(folder_id);
CREATE INDEX IF NOT EXISTS idx_creative_history_criado  ON creative_history(criado_em DESC);
"""

if __name__ == "__main__":
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(SQL)
        conn.commit()
        print("✓ Tabelas creative_folders e creative_history criadas com sucesso.")
    except Exception as e:
        print(f"✕ Erro: {e}")
        sys.exit(1)
    finally:
        conn.close()
