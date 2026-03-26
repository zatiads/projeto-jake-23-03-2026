#!/usr/bin/env python3
"""
Script one-shot: cria as tabelas ad_client_profiles e ad_publish_log no Neon.
Executar: PYTHONPATH=/root python3 scripts/migrar_anuncios.py
"""
import sys
sys.path.insert(0, '/root')
from core.db import get_conn

SQL = """
CREATE TABLE IF NOT EXISTS ad_client_profiles (
    id                    SERIAL PRIMARY KEY,
    nome                  VARCHAR(100) NOT NULL,
    agencia               VARCHAR(20)  NOT NULL CHECK (agencia IN ('piloti','dentto','freelance')),
    account_id            VARCHAR(50)  NOT NULL,
    token_key             VARCHAR(50)  NOT NULL,
    page_id               VARCHAR(50),
    whatsapp              VARCHAR(20),
    segmento              VARCHAR(100),
    campanha_tipo         VARCHAR(20)  NOT NULL DEFAULT 'MESSAGES'
                              CHECK (campanha_tipo IN ('MESSAGES','ENGAGEMENT')),
    localizacao_json      JSONB        NOT NULL DEFAULT '{}',
    publico_json          JSONB,
    orcamento_diario      NUMERIC(10,2),
    campanha_id_existente VARCHAR(50),
    criado_em             TIMESTAMP    DEFAULT NOW(),
    atualizado_em         TIMESTAMP    DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ad_publish_log (
    id           SERIAL PRIMARY KEY,
    cliente_id   INTEGER REFERENCES ad_client_profiles(id),
    account_id   VARCHAR(50)  NOT NULL,
    campaign_id  VARCHAR(50),
    adset_id     VARCHAR(50),
    ad_id        VARCHAR(50),
    status       VARCHAR(20)  NOT NULL CHECK (status IN ('sucesso','erro')),
    erro_msg     TEXT,
    payload_json JSONB,
    criado_em    TIMESTAMP    DEFAULT NOW()
);
"""

if __name__ == "__main__":
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(SQL)
        conn.commit()
        print("✓ Tabelas criadas com sucesso.")
    except Exception as e:
        print(f"✕ Erro: {e}")
        sys.exit(1)
    finally:
        conn.close()
