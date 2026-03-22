#!/usr/bin/env python3
"""
Cria tabelas fin_transacoes e fin_raiox no Neon e popula com dados de 2026.
Idempotente: verifica COUNT(*) antes de inserir.
Executar: PYTHONPATH=/root python3 scripts/seed_financeiro.py
"""
import sys, json
sys.path.insert(0, '/root')
from core.db import get_conn

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS fin_transacoes (
    id         SERIAL PRIMARY KEY,
    descricao  TEXT NOT NULL,
    valor      NUMERIC(10,2) NOT NULL,
    tipo       TEXT NOT NULL CHECK (tipo IN ('Entrada', 'Saída')),
    categoria  TEXT NOT NULL CHECK (categoria IN ('Fixa', 'Variável')),
    recorrente BOOLEAN DEFAULT false,
    data       DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS fin_raiox (
    id      SERIAL PRIMARY KEY,
    nome    TEXT NOT NULL,
    grupo   TEXT NOT NULL CHECK (grupo IN ('entradas', 'fixas', 'variaveis')),
    valores JSONB NOT NULL
);
"""

TRANSACOES = [
    # Janeiro 2026
    ('Dentto',               4300.00, 'Entrada', 'Fixa',     True,  '2026-01-05'),
    ('Pedras Carula',         800.00, 'Entrada', 'Fixa',     True,  '2026-01-05'),
    ('Suprema Metal',         800.00, 'Entrada', 'Fixa',     True,  '2026-01-05'),
    ('Piloti',               3250.00, 'Entrada', 'Fixa',     True,  '2026-01-05'),
    ('Diversos',             1100.00, 'Entrada', 'Variável', False, '2026-01-10'),
    ('Aluguel',              1100.00, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Academia',              100.00, 'Saída',   'Fixa',     True,  '2026-01-10'),
    ('Mercado',               700.00, 'Saída',   'Fixa',     True,  '2026-01-15'),
    ('Internet',              100.00, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Água',                   60.00, 'Saída',   'Fixa',     True,  '2026-01-10'),
    ('Luz',                   220.00, 'Saída',   'Fixa',     True,  '2026-01-10'),
    ('Assinaturas',           160.00, 'Saída',   'Fixa',     True,  '2026-01-01'),
    ('Gasolina',              200.00, 'Saída',   'Fixa',     True,  '2026-01-20'),
    ('Sofá (parcela)',        223.10, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Pets',                  130.00, 'Saída',   'Fixa',     True,  '2026-01-15'),
    ('Computador (parc.)',    441.58, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Cadeira (parcela)',     173.24, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Celular (parcela)',     399.79, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Mercado Livre/Shopee',  923.62, 'Saída',   'Variável', False, '2026-01-20'),
    ('ME/Impostos',          1200.00, 'Saída',   'Fixa',     True,  '2026-01-20'),
    ('Geladeira (parcela)',   217.50, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Sicoob',               1793.93, 'Saída',   'Variável', False, '2026-01-15'),
    ('Bradesco',             6905.21, 'Saída',   'Variável', False, '2026-01-15'),
    # Fevereiro 2026
    ('Dentto',               4950.00, 'Entrada', 'Fixa',     True,  '2026-02-05'),
    ('Pedras Carula',         800.00, 'Entrada', 'Fixa',     True,  '2026-02-05'),
    ('Suprema Metal',         800.00, 'Entrada', 'Fixa',     True,  '2026-02-05'),
    ('Piloti',               3500.00, 'Entrada', 'Fixa',     True,  '2026-02-05'),
    ('Diversos',              600.00, 'Entrada', 'Variável', False, '2026-02-10'),
    ('Aluguel',              1100.00, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Academia',              104.43, 'Saída',   'Fixa',     True,  '2026-02-10'),
    ('Mercado',               700.00, 'Saída',   'Fixa',     True,  '2026-02-15'),
    ('Internet',              100.00, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Água',                   60.00, 'Saída',   'Fixa',     True,  '2026-02-10'),
    ('Luz',                   220.00, 'Saída',   'Fixa',     True,  '2026-02-10'),
    ('Assinaturas',           160.00, 'Saída',   'Fixa',     True,  '2026-02-01'),
    ('Gasolina',              200.00, 'Saída',   'Fixa',     True,  '2026-02-20'),
    ('Sofá (parcela)',        223.10, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Pets',                  130.00, 'Saída',   'Fixa',     True,  '2026-02-15'),
    ('Computador (parc.)',    441.58, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Cadeira (parcela)',     173.24, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Celular (parcela)',     399.79, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('ME/Impostos',          1200.00, 'Saída',   'Fixa',     True,  '2026-02-20'),
    ('Geladeira (parcela)',   217.50, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Sicoob',               4204.39, 'Saída',   'Variável', False, '2026-02-15'),
]

RAIOX = [
    ('Dentto',        'entradas', [4300,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950]),
    ('Pedras Carula', 'entradas', [800,800,800,800,800,800,800,800,800,800,800,800]),
    ('Suprema Metal', 'entradas', [800,800,800,800,800,800,800,800,800,800,800,800]),
    ('Piloti',        'entradas', [3250,3500,3500,3500,3500,3500,3500,3500,3500,3500,3500,3500]),
    ('Diversos',      'entradas', [1100,600,546.87,0,0,0,0,0,0,0,0,0]),
    ('Aluguel',       'fixas',    [1100,1100,1100,1100,1100,1100,1100,1100,1100,1100,1100,1100]),
    ('Academia',      'fixas',    [100,104.43,104.43,100,100,100,100,100,100,100,100,100]),
    ('Mercado',       'fixas',    [700,700,800,800,800,800,800,800,800,800,800,800]),
    ('Internet',      'fixas',    [100,100,100,100,100,100,100,100,100,100,100,100]),
    ('Água',          'fixas',    [60,60,60,60,60,60,60,60,60,60,60,60]),
    ('Luz',           'fixas',    [220,220,220,220,220,220,220,220,220,220,220,220]),
    ('Assinaturas',   'fixas',    [160,160,350,350,350,350,350,350,350,350,350,350]),
    ('Gasolina',      'fixas',    [200,200,200,200,200,200,200,200,200,200,200,200]),
    ('Sofá (parc.)',  'fixas',    [223.10,223.10,223.10,223.10,223.10,223.10,223.10,223.10,223.10,223.10,223.10,223.10]),
    ('Pets',          'fixas',    [130,130,130,130,130,130,130,130,130,130,130,130]),
    ('Computador',    'fixas',    [441.58,441.58,441.58,441.58,441.58,441.58,441.58,441.58,441.58,441.58,441.58,441.58]),
    ('Cadeira',       'fixas',    [173.24,173.24,173.24,173.24,173.24,173.24,173.24,173.24,0,0,0,0]),
    ('Celular',       'fixas',    [399.79,399.79,399.79,399.79,399.79,399.79,399.79,399.79,399.79,399.79,399.79,399.79]),
    ('Mercado Livre', 'fixas',    [923.62,923.62,456.16,177.41,0,0,0,0,0,0,0,0]),
    ('ME/Impostos',   'fixas',    [1200,1200,1200,1200,1200,1200,1200,1200,1200,0,0,0]),
    ('Geladeira',     'fixas',    [217.50,217.50,217.50,217.50,0,0,0,0,0,0,0,0]),
    ('Sicoob',        'variaveis',[1793.93,0,4204.39,0,0,0,0,0,0,0,0,0]),
    ('Bradesco',      'variaveis',[6905.21,0,0,0,0,0,0,0,0,0,0,0]),
]

def main():
    conn = get_conn()
    cur = conn.cursor()

    # Criar tabelas
    cur.execute(CREATE_SQL)
    conn.commit()
    print("Tabelas criadas (ou já existiam).")

    # Seed idempotente
    cur.execute("SELECT COUNT(*) FROM fin_transacoes")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO fin_transacoes (descricao,valor,tipo,categoria,recorrente,data) VALUES (%s,%s,%s,%s,%s,%s)",
            TRANSACOES
        )
        conn.commit()
        print(f"Inseridas {len(TRANSACOES)} transações.")
    else:
        print("fin_transacoes já tem dados — pulando.")

    cur.execute("SELECT COUNT(*) FROM fin_raiox")
    if cur.fetchone()[0] == 0:
        for nome, grupo, valores in RAIOX:
            cur.execute(
                "INSERT INTO fin_raiox (nome, grupo, valores) VALUES (%s, %s, %s)",
                (nome, grupo, json.dumps(valores))
            )
        conn.commit()
        print(f"Inseridas {len(RAIOX)} linhas no raio-x.")
    else:
        print("fin_raiox já tem dados — pulando.")

    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
