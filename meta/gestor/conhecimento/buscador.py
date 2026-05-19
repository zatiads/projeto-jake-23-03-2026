"""
Gestor IA — Buscador semanal de conhecimento.
Executar via cron: PYTHONPATH=/root python -m meta.gestor.conhecimento.buscador
"""
import os
import json
import logging
import time

try:
    from dotenv import load_dotenv
    load_dotenv("/root/.env")
except ImportError:
    pass

import requests
import psycopg2
from bs4 import BeautifulSoup
import anthropic

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

QUERIES = [
    "CPL Meta Ads benchmark Brasil 2024 dentista clínica",
    "frequência anúncios Meta Ads quando pausar escalar campanha",
    "tráfego pago Meta Ads otimização avançada custo por resultado",
    "Meta Ads campaign budget adset scaling rules best practices",
    "quando escalar orçamento Meta Ads sem perder performance",
    "criativo fadigado frequência alta Meta Ads como resolver",
    "CPL alto Meta Ads diagnóstico e solução gestor tráfego",
    "Meta Ads aprendizado campanha phase como acelerar sair",
]

_PROMPT_EXTRACAO = """Você é um especialista em tráfego pago Meta Ads no Brasil.
Leia o texto abaixo e extraia APENAS regras acionáveis sobre gestão de campanhas Meta Ads.
Ignore conteúdo genérico, de vendas, introdutório ou sem dados concretos.

Retorne SOMENTE JSON válido neste formato (sem markdown):
{{
  "aprovado": true,
  "motivo_rejeicao": null,
  "titulo": "string curto e descritivo em minúsculas (max 80 chars)",
  "nichos": ["dental", "fitness", "varejo", "servicos", "saude", "geral"],
  "tipo_campanha": "MESSAGES",
  "regras": "- regra 1\\n- regra 2\\n- regra 3"
}}

Ou se o conteúdo não for útil:
{{"aprovado": false, "motivo_rejeicao": "motivo"}}

Rejeite (aprovado=false) se:
- Menos de 3 regras acionáveis com dados concretos
- Conteúdo genérico sem números ou limiares específicos
- Conteúdo de vendas ou introdutório sem informação técnica

Para tipo_campanha, use somente: "MESSAGES", "PURCHASE", "ENGAGEMENT" ou "geral"
Para nichos, use somente: "dental", "fitness", "varejo", "servicos", "saude", "geral"

TEXTO:
{texto}"""


def _get_db():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido")
    return psycopg2.connect(db_url)


def _titulo_existe(conn, titulo: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM gestor_conhecimento WHERE LOWER(TRIM(titulo)) = %s AND ativo = TRUE",
        (titulo.lower().strip(),),
    )
    return cur.fetchone() is not None


def _buscar_urls(query: str) -> list[str]:
    """Retorna até 5 URLs via DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            resultados = list(ddgs.text(query, max_results=5))
        return [r["href"] for r in resultados if r.get("href")]
    except Exception as e:
        _log.warning("DuckDuckGo falhou para query '%s': %s", query[:50], e)
        return []


def _scrape_url(url: str) -> str | None:
    """Faz scraping de uma URL. Retorna texto limpo ou None."""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        texto = soup.get_text(separator="\n", strip=True)
        # Mínimo 500 chars para tentar extração
        if len(texto) < 500:
            _log.debug("Texto muito curto (%d chars): %s", len(texto), url)
            return None
        # Limitar a 3000 chars para não inflar o prompt
        return texto[:3000]
    except Exception as e:
        _log.debug("Scraping falhou para %s: %s", url, e)
        return None


def _extrair_com_claude(texto: str) -> dict | None:
    """Envia texto ao Claude e retorna dict extraído, ou None se rejeitado/erro."""
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        prompt = _PROMPT_EXTRACAO.format(texto=texto)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Limpar markdown se vier
        if "```" in raw:
            import re
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            if m:
                raw = m.group(1).strip()
        data = json.loads(raw)
        if not data.get("aprovado"):
            _log.debug("Conteúdo rejeitado: %s", data.get("motivo_rejeicao"))
            return None
        return data
    except Exception as e:
        _log.warning("Extração Claude falhou: %s", e)
        return None


def _salvar(conn, data: dict, fonte: str):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO gestor_conhecimento (titulo, regras, nichos, tipo_campanha, fonte, origem)
        VALUES (%s, %s, %s, %s, %s, 'busca')
        """,
        (
            data["titulo"],
            data["regras"],
            data.get("nichos", ["geral"]),
            data.get("tipo_campanha", "geral"),
            fonte,
        ),
    )
    conn.commit()


def run():
    conn = _get_db()
    total_inseridos = 0
    total_rejeitados = 0
    total_duplicados = 0

    for query in QUERIES:
        _log.info("Buscando: %s", query[:60])
        urls = _buscar_urls(query)
        for url in urls:
            texto = _scrape_url(url)
            if not texto:
                continue
            data = _extrair_com_claude(texto)
            if not data:
                total_rejeitados += 1
                continue
            if _titulo_existe(conn, data["titulo"]):
                _log.debug("Duplicado: %s", data["titulo"])
                total_duplicados += 1
                continue
            _salvar(conn, data, fonte=url)
            total_inseridos += 1
            _log.info("Salvo: %s", data["titulo"])
            time.sleep(1)  # respeitar rate limit do Claude

    conn.close()
    _log.info(
        "Buscador concluido: %d inseridos, %d rejeitados, %d duplicados",
        total_inseridos, total_rejeitados, total_duplicados,
    )


if __name__ == "__main__":
    run()
