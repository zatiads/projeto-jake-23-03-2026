"""
Gestor IA — Orquestrador principal.
Executar via cron: cd /root && /root/venv/bin/python -m meta.gestor_agente
"""
import os
import sys
import time
import json
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
    load_dotenv("/root/.env")
except ImportError:
    pass

import psycopg2
import psycopg2.extras

from meta.gestor.coletor  import coletar
from meta.gestor.analista import analisar
from meta.gestor.executor import executar
from meta.gestor.relator  import gerar


def _get_db():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido")
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _log(msg: str):
    print(f"[gestor] {msg}", flush=True)


def main():
    inicio = time.time()
    _log("Iniciando varredura...")

    db_conn = None
    db_conn = _get_db()
    cur = db_conn.cursor()

    # Inserir registro de varredura
    cur.execute("""
        INSERT INTO gestor_varreduras (contas_total, contas_ok, contas_acao, contas_erro, status)
        VALUES (0, 0, 0, 0, 'em_andamento')
        RETURNING id
    """)
    varredura_id = cur.fetchone()["id"]
    db_conn.commit()

    try:
        # 1. Coletar
        _log("Coletando métricas...")
        perfis = coletar(db_conn=None)  # abre própria conexão por segurança de cursor
        _log(f"  {len(perfis)} contas coletadas")

        # 2. Analisar
        _log("Analisando com Claude...")
        decisoes = analisar(perfis)
        _log(f"  {sum(len(d.get('acoes',[])) for d in decisoes)} ações decididas")

        # 3. Executar
        _log("Executando ações...")
        contadores = executar(decisoes, perfis, varredura_id, db_conn=None)
        _log(f"  OK:{contadores['ok']} Erro:{contadores['erro']} Alertas:{contadores['alertas']}")

        # 4. Relatório (somente sextas)
        if date.today().weekday() == 4:  # 4 = sexta-feira
            _log("Gerando relatórios semanais (sexta)...")
            arquivos = gerar(perfis, varredura_id, db_conn=None)
            _log(f"  PDFs gerados: {arquivos}")

        # Atualizar varredura como sucesso
        contas_ok   = sum(1 for p in perfis if not p.get("erro"))
        contas_erro = sum(1 for p in perfis if p.get("erro"))
        contas_acao = sum(1 for d in decisoes if d.get("acoes"))
        duracao = time.time() - inicio

        cur.execute("""
            UPDATE gestor_varreduras
            SET contas_total=%s, contas_ok=%s, contas_acao=%s, contas_erro=%s,
                resumo_json=%s, duracao_seg=%s, status='sucesso'
            WHERE id=%s
        """, (
            len(perfis), contas_ok, contas_acao, contas_erro,
            json.dumps({"acoes": contadores}),
            round(duracao, 2),
            varredura_id,
        ))
        db_conn.commit()
        _log(f"Varredura concluída em {duracao:.1f}s. ID={varredura_id}")

    except Exception as e:
        _log(f"ERRO na varredura: {e}")
        cur.execute("""
            UPDATE gestor_varreduras
            SET status='erro', resumo_json=%s
            WHERE id=%s
        """, (json.dumps({"erro": str(e)}), varredura_id))
        db_conn.commit()
        sys.exit(1)
    finally:
        if db_conn:
            db_conn.close()


if __name__ == "__main__":
    main()
