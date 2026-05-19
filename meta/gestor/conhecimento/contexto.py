"""
Gestor IA — Conhecimento Sênior.
Injeta blocos de conhecimento relevantes no prompt do analista.
"""
import os
import logging
import psycopg2
import psycopg2.extras

_log = logging.getLogger(__name__)

# Mapa de nicho por palavras-chave no nome da conta
_NICHO_MAP = {
    "dental": [
        "ODC", "Espaço Dente", "Odontocompany", "Realize", "Uberaba",
        "Ilhota", "Massaranduba", "Schroeder", "Tijucas", "São Francisco",
        "Cordeirópolis", "Sorrisos", "Dente", "Odonto",
    ],
    "fitness": ["ISAC", "mrrunners", "Meu Ritmo", "Academia", "Fitness", "Funcional"],
    "varejo":  ["Queen Poltronas", "Saucker", "Poltronas"],
    "servicos": ["Castaldi", "RD Contabilidade", "Calixta", "Runway", "Contabil",
                 "Advocacia", "Marketing"],
    "saude":   ["Hiperbárica", "Vielife", "Clínica", "Clinica", "Saúde"],
}


def _detectar_nichos(perfis: list[dict]) -> list[str]:
    """Retorna lista de nichos detectados nos nomes das contas."""
    nichos_presentes = set()
    for p in perfis:
        nome = p.get("nome", "")
        for nicho, keywords in _NICHO_MAP.items():
            if any(kw.lower() in nome.lower() for kw in keywords):
                nichos_presentes.add(nicho)
    nichos_presentes.add("geral")
    return list(nichos_presentes)


def _get_db():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido")
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def montar_contexto(perfis: list[dict]) -> str:
    """
    Recebe lista de perfis da varredura e retorna bloco de conhecimento
    formatado para injetar no system_prompt do analista.

    Args:
        perfis: list[dict] com chaves:
            - 'nome': str  (nome da conta, ex: "Espaço Dente")
            - 'objetivo': str  (ex: "MESSAGES", "ENGAGEMENT", "PURCHASE")

    Returns:
        String formatada para append no system_prompt, ou "" em caso de erro
        ou banco vazio.
    """
    try:
        nichos = _detectar_nichos(perfis)
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT titulo, regras, nichos, tipo_campanha
                FROM gestor_conhecimento
                WHERE ativo = TRUE
                  AND (nichos && %s OR 'geral' = ANY(nichos))
                ORDER BY
                    CASE origem WHEN 'seed' THEN 0 ELSE 1 END,
                    criado_em DESC
                LIMIT 10
            """, (nichos,))
            blocos = cur.fetchall()
        finally:
            conn.close()

        if not blocos:
            return ""

        linhas = ["CONHECIMENTO DE GESTOR SENIOR — use como referencia nas decisoes:"]
        linhas.append("")
        for b in blocos:
            tipo = f" - {b['tipo_campanha']}" if b.get("tipo_campanha") and b["tipo_campanha"] != "geral" else ""
            nichos_str = "/".join(n.upper() for n in (b["nichos"] or []) if n != "geral")
            header = f"[{nichos_str}{tipo}]" if nichos_str else "[GERAL]"
            linhas.append(header)
            for linha in b["regras"].strip().splitlines():
                linhas.append(linha)
            linhas.append("")

        return "\n".join(linhas).strip()

    except Exception as e:
        _log.warning("montar_contexto erro: %s", e)
        return ""
