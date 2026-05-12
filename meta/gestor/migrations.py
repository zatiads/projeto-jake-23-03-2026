"""
Gestor IA — migrações de banco de dados.
Executar uma vez: python -m meta.gestor.migrations
Idempotente — seguro rodar múltiplas vezes.
"""
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
    load_dotenv("/root/.env")
except ImportError:
    pass

import psycopg2


def _get_db():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido no .env")
    return psycopg2.connect(db_url)


def run():
    conn = _get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gestor_varreduras (
            id           SERIAL PRIMARY KEY,
            executado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            contas_total INTEGER NOT NULL,
            contas_ok    INTEGER NOT NULL,
            contas_acao  INTEGER NOT NULL,
            contas_erro  INTEGER NOT NULL,
            resumo_json  JSONB,
            duracao_seg  FLOAT,
            status       TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gestor_acoes (
            id            SERIAL PRIMARY KEY,
            varredura_id  INTEGER REFERENCES gestor_varreduras(id),
            cliente_id    INTEGER REFERENCES ad_client_profiles(id),
            account_id    TEXT NOT NULL,
            executado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            tipo          TEXT NOT NULL,
            entidade_id   TEXT NOT NULL,
            entidade_nome TEXT,
            valor_antes   JSONB,
            valor_depois  JSONB,
            motivo        TEXT,
            revertido     BOOLEAN DEFAULT FALSE,
            revertido_em  TIMESTAMPTZ,
            status        TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gestor_relatorios (
            id           SERIAL PRIMARY KEY,
            gerado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            agencia      TEXT NOT NULL,
            periodo_ini  DATE NOT NULL,
            periodo_fim  DATE NOT NULL,
            arquivo_path TEXT NOT NULL,
            tamanho_kb   INTEGER
        )
    """)

    # Alterar ad_client_profiles — idempotente via DO $$
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='ad_client_profiles' AND column_name='gestor_config_json'
            ) THEN
                ALTER TABLE ad_client_profiles ADD COLUMN gestor_config_json JSONB DEFAULT NULL;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='ad_client_profiles' AND column_name='gestor_ativo'
            ) THEN
                ALTER TABLE ad_client_profiles ADD COLUMN gestor_ativo BOOLEAN DEFAULT TRUE;
            END IF;
        END $$;
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Migrations aplicadas com sucesso.")


if __name__ == "__main__":
    run()
