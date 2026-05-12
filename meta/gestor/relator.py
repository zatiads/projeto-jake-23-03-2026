"""
Gestor IA — Relator.
Gera PDFs semanais por agência. Chamado nas sextas pelo orquestrador.
Recebe dados já coletados — não refaz queries à Meta API.
"""
import os
import json
import psycopg2
import psycopg2.extras
from datetime import date, timedelta
from typing import List, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv("/root/.env")
except ImportError:
    pass

OUTPUT_DIR = "/root/jake_desktop/static/relatorios/gestor"


def _get_db():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido")
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _anthropic_client():
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY não configurado")
    return anthropic.Anthropic(api_key=api_key)


def _gerar_narrativa(contas_agencia: list, agencia: str, periodo: str) -> str:
    """Usa Claude para gerar texto narrativo do relatório."""
    client = _anthropic_client()
    prompt = (
        f"Você é gestor de tráfego. Gere um relatório executivo SUCINTO em português "
        f"para uso interno sobre a semana de {periodo} da agência {agencia.upper()}.\n\n"
        f"Dados das contas:\n{json.dumps(contas_agencia, ensure_ascii=False, indent=2)}\n\n"
        "Para cada conta: 1-2 frases sobre o desempenho, as ações do agente e o resultado.\n"
        "Termine com um parágrafo de resumo executivo. Seja direto e objetivo."
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _html_relatorio(agencia: str, periodo: str, narrativa: str,
                     contas: list, acoes_semana: list) -> str:
    """Gera HTML do relatório para conversão em PDF."""
    acoes_por_conta: Dict[int, list] = {}
    for a in acoes_semana:
        acoes_por_conta.setdefault(a["cliente_id"], []).append(a)

    linhas_contas = ""
    for c in contas:
        m       = c.get("metricas") or {}
        saldo   = c.get("saldo") or {}
        acoes_c = acoes_por_conta.get(c["cliente_id"], [])
        status  = "Saudável"
        if saldo.get("remaining", 999) < 100:
            status = "⚠ Saldo Baixo"
        elif m.get("cpl_medio") and m.get("cpl_medio") > 0:
            status = "Atenção" if len(acoes_c) > 0 else "Saudável"

        linhas_acoes = "".join(
            f"<li>{a['tipo'].replace('_',' ').title()}: {a.get('entidade_nome','')} — {a.get('motivo','')}</li>"
            for a in acoes_c if a["tipo"] != "alerta_saldo"
        )
        alertas = [a for a in acoes_c if a["tipo"] == "alerta_saldo"]

        linhas_contas += f"""
        <div class="conta">
          <h3>{c['nome']} <span class="status">{status}</span></h3>
          <div class="metricas">
            <span>CPL médio: <b>R$ {m.get('cpl_medio') or '—'}</b></span>
            <span>Conversões 30d: <b>{m.get('total_conversoes', 0)}</b></span>
            <span>Investido 30d: <b>R$ {m.get('total_spend', 0):.2f}</b></span>
            <span>Saldo: <b>R$ {saldo.get('remaining', 0):.2f}</b></span>
          </div>
          {'<ul class="acoes">' + linhas_acoes + '</ul>' if linhas_acoes else '<p class="sem-acao">Sem ações esta semana.</p>'}
          {'<p class="alerta">⚠ ' + alertas[0]['motivo'] + '</p>' if alertas else ''}
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12px; color: #222; margin: 40px; }}
  h1 {{ font-size: 18px; border-bottom: 2px solid #333; padding-bottom: 8px; }}
  h2 {{ font-size: 14px; color: #555; }}
  h3 {{ font-size: 13px; margin-bottom: 4px; }}
  .periodo {{ color: #888; font-size: 11px; margin-bottom: 20px; }}
  .narrativa {{ background: #f5f5f5; padding: 12px; border-radius: 4px; margin-bottom: 24px; line-height: 1.6; }}
  .conta {{ border: 1px solid #ddd; border-radius: 4px; padding: 12px; margin-bottom: 12px; }}
  .status {{ font-size: 10px; padding: 2px 6px; border-radius: 10px; background: #e8f5e9; color: #388e3c; }}
  .metricas {{ display: flex; gap: 20px; font-size: 11px; color: #555; margin: 6px 0; }}
  .acoes {{ font-size: 11px; color: #555; margin: 6px 0; padding-left: 16px; }}
  .sem-acao {{ font-size: 11px; color: #999; }}
  .alerta {{ color: #e65100; font-size: 11px; }}
</style>
</head>
<body>
<h1>Relatório Semanal — {agencia.upper()}</h1>
<p class="periodo">Período: {periodo}</p>
<h2>Análise Executiva</h2>
<div class="narrativa">{narrativa.replace(chr(10), '<br>')}</div>
<h2>Por Conta</h2>
{linhas_contas}
</body>
</html>"""


def gerar(perfis: List[Dict[str, Any]], varredura_id: int, db_conn=None) -> List[str]:
    """
    Gera PDFs para todas as agências com contas no perfis.
    Retorna lista de caminhos gerados.
    """
    import weasyprint

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fechar = False
    if db_conn is None:
        db_conn = _get_db()
        fechar = True

    hoje     = date.today()
    ini      = hoje - timedelta(days=7)
    periodo  = f"{ini.strftime('%d/%m')} a {hoje.strftime('%d/%m/%Y')}"
    arquivos = []

    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT ga.*, acp.nome as conta_nome
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE ga.varredura_id = %s
        """, (varredura_id,))
        acoes_semana = list(cur.fetchall())

        agencias = list({p["agencia"] for p in perfis if not p.get("erro")})

        for agencia in agencias:
            contas_ag = [p for p in perfis if p.get("agencia") == agencia and not p.get("erro")]
            if not contas_ag:
                continue

            narrativa = _gerar_narrativa(contas_ag, agencia, periodo)
            html      = _html_relatorio(agencia, periodo, narrativa, contas_ag, acoes_semana)

            nome_arquivo = f"{agencia}_{hoje.strftime('%Y%m%d')}.pdf"
            caminho      = os.path.join(OUTPUT_DIR, nome_arquivo)
            caminho_rel  = f"relatorios/gestor/{nome_arquivo}"

            weasyprint.HTML(string=html).write_pdf(caminho)

            tamanho_kb = os.path.getsize(caminho) // 1024

            cur.execute("""
                INSERT INTO gestor_relatorios
                    (agencia, periodo_ini, periodo_fim, arquivo_path, tamanho_kb)
                VALUES (%s, %s, %s, %s, %s)
            """, (agencia, ini, hoje, caminho_rel, tamanho_kb))

            arquivos.append(caminho)

        db_conn.commit()
    finally:
        if fechar:
            db_conn.close()

    return arquivos
