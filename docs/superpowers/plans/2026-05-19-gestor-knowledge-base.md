# Gestor Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enriquecer o prompt do analista do Gestor IA com uma base de conhecimento de gestor sênior (benchmarks por nicho, boas práticas Meta Ads) coletada via seed curado + busca semanal automática.

**Architecture:** Novo módulo `meta/gestor/conhecimento/` com seed curado (roda 1x), buscador semanal (DuckDuckGo + Claude extração), e contexto.py que injeta blocos relevantes no system_prompt do analista antes de cada varredura.

**Tech Stack:** Python 3, psycopg2, anthropic, duckduckgo_search, beautifulsoup4, requests, APScheduler (cron via crontab do sistema)

**Spec:** `docs/superpowers/specs/2026-05-19-gestor-knowledge-base-design.md`

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `meta/gestor/migrations.py` | modificar | Adicionar tabela `gestor_conhecimento` |
| `meta/gestor/conhecimento/__init__.py` | criar | Módulo vazio |
| `meta/gestor/conhecimento/seed.py` | criar | Popula base inicial curada (~20 blocos) |
| `meta/gestor/conhecimento/contexto.py` | criar | `montar_contexto(perfis)` → string para injetar no prompt |
| `meta/gestor/conhecimento/buscador.py` | criar | Agente semanal: DuckDuckGo → scraping → Claude → DB |
| `meta/gestor/analista.py` | modificar | Importar e injetar contexto no system_prompt |
| `crontab` | modificar | Adicionar job semanal do buscador (segunda 6h) |

---

## Task 1: Migração do banco

**Files:**
- Modify: `meta/gestor/migrations.py`

- [ ] **Step 1: Adicionar migration `migrate_conhecimento` em `migrations.py`**

Inserir antes do bloco `if __name__ == "__main__":`:

```python
def migrate_conhecimento(conn):
    """Migração: tabela de conhecimento sênior do Gestor."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gestor_conhecimento (
            id            SERIAL PRIMARY KEY,
            titulo        TEXT NOT NULL,
            regras        TEXT NOT NULL,
            nichos        TEXT[] DEFAULT '{}',
            tipo_campanha TEXT,
            fonte         TEXT,
            origem        TEXT DEFAULT 'seed',
            ativo         BOOLEAN DEFAULT TRUE,
            criado_em     TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_gestor_conhecimento_nichos
        ON gestor_conhecimento USING GIN(nichos)
        WHERE ativo = TRUE
    """)
    conn.commit()
    print("[migrations] gestor_conhecimento aplicada.")
```

Chamar no bloco `run()` — após o último `cur.execute` e antes do `conn.commit()` final:

```python
        migrate_conhecimento(conn)
```

- [ ] **Step 2: Rodar a migração**

```bash
cd /root && PYTHONPATH=/root /root/venv/bin/python -m meta.gestor.migrations
```

Saída esperada: `Migrations aplicadas com sucesso.`

- [ ] **Step 3: Verificar tabela criada**

```bash
PYTHONPATH=/root /root/venv/bin/python3 -c "
import os; from dotenv import load_dotenv; load_dotenv('/root/.env')
import psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='gestor_conhecimento'\")
print([r[0] for r in cur.fetchall()])
conn.close()
"
```

Saída esperada: lista com `id, titulo, regras, nichos, tipo_campanha, fonte, origem, ativo, criado_em`

- [ ] **Step 4: Commit**

```bash
git add meta/gestor/migrations.py
git commit -m "feat(gestor): migration tabela gestor_conhecimento"
```

---

## Task 2: Módulo `conhecimento/__init__.py` e `contexto.py`

**Files:**
- Create: `meta/gestor/conhecimento/__init__.py`
- Create: `meta/gestor/conhecimento/contexto.py`

- [ ] **Step 1: Criar `__init__.py` vazio**

```bash
mkdir -p /root/meta/gestor/conhecimento
touch /root/meta/gestor/conhecimento/__init__.py
```

- [ ] **Step 2: Criar `contexto.py`**

Conteúdo completo:

```python
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
```

- [ ] **Step 3: Smoke test do contexto.py**

```bash
PYTHONPATH=/root /root/venv/bin/python3 -c "
import os; from dotenv import load_dotenv; load_dotenv('/root/.env')
from meta.gestor.conhecimento.contexto import montar_contexto
# Banco ainda vazio — deve retornar string vazia sem erro
resultado = montar_contexto([{'nome': 'Espaço Dente', 'objetivo': 'MESSAGES'}])
print(repr(resultado))  # espera: ''
print('OK — sem erro com banco vazio')
"
```

Saída esperada: `'' \n OK — sem erro com banco vazio`

- [ ] **Step 4: Commit**

```bash
git add meta/gestor/conhecimento/
git commit -m "feat(gestor): contexto.py — injeção de conhecimento no analista"
```

---

## Task 3: `seed.py` — base curada inicial

**Files:**
- Create: `meta/gestor/conhecimento/seed.py`

- [ ] **Step 1: Criar `seed.py` com 20 blocos curados**

```python
"""
Gestor IA — Seed de conhecimento sênior.
Executar uma vez: PYTHONPATH=/root python -m meta.gestor.conhecimento.seed
Idempotente — não duplica se já existir.
"""
import os
import logging

try:
    from dotenv import load_dotenv
    load_dotenv("/root/.env")
except ImportError:
    pass

import psycopg2

_log = logging.getLogger(__name__)

BLOCOS = [
    {
        "titulo": "dental messages cpl benchmarks brasil",
        "nichos": ["dental"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- CPL saudavel: R$8-R$25. Acima de R$40 indica criativo saturado ou publico errado.
- CPL acima de R$50 por mais de 3 dias consecutivos: pausar o ad e testar novo criativo.
- Frequencia maxima antes de trocar criativo: 3.0. Acima disso, CTR cai e CPL sobe.
- Sazonalidade: janeiro e julho sao picos de busca por tratamento dental — thresholds podem subir 20%.
- Publico ideal: lookalike 1-3% de lista de pacientes ou engajamento 60 dias.
- Campanha de mensagem dental: objetivo MESSAGES no Meta, CTA "Agendar consulta pelo WhatsApp".
- Ads com imagem antes/depois performam 2-3x melhor que ads institucionais para dentistas.""",
    },
    {
        "titulo": "dental messages escalada orcamento",
        "nichos": ["dental"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- Escalar quando CPL < R$15 por 3+ dias consecutivos E frequencia < 2.0.
- Limite de escalada segura: +20% do orcamento do conjunto por vez (Meta reinicia aprendizado acima disso).
- Nunca escalar ad individualmente — sempre escalar no nivel do conjunto de anuncios (adset).
- Melhor janela para editar orcamento: entre 0h e 6h horario de Brasilia (menor competicao no leilao).
- Se CPL caiu mas frequencia esta acima de 2.5: escalar publico, nao orcamento.""",
    },
    {
        "titulo": "fitness messages cpl benchmarks brasil",
        "nichos": ["fitness"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- CPL saudavel academia padrao: R$15-R$50. Academias premium aceitam ate R$80.
- Personal trainer e funcional: CPL ate R$60 e aceitavel se ticket medio for alto.
- Sazonalidade forte: janeiro (resolucoes de ano novo) e setembro — thresholds sobem 30%.
- Junho/julho: queda natural de demanda — nao confundir com problema de criativo.
- Criativos de transformacao (antes/depois) performam 2-3x melhor que institucionais.
- Publico com interesse em "academia", "emagrecimento" e "saude" tende a ter CPL 20% menor.""",
    },
    {
        "titulo": "fitness messages fadiga criativa",
        "nichos": ["fitness"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- Frequencia > 2.5 em menos de 14 dias indica publico muito restrito — ampliar audiencia.
- Frequencia > 3.5: pausar o ad. CTR cai abruptamente apos esse ponto.
- Rotacao de criativos: novo ad a cada 3-4 semanas mesmo sem queda de performance (prevencao).
- Testar angulo diferente de copy: dor (nao consigo emagrecer), solucao (academia perto de voce), prova social (aluno transformado).""",
    },
    {
        "titulo": "varejo mensagem whatsapp benchmarks",
        "nichos": ["varejo"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- CPL para varejo via WhatsApp: R$20-R$60. Alta variacao por ticket medio do produto.
- Produto de alto ticket (sofa, movel): CPL ate R$100 e aceitavel se taxa de fechamento for >10%.
- Ads com preco visivel no criativo tendem a ter CTR mais alto mas CPL mais seletivo (lead mais qualificado).
- Urgencia funciona bem em varejo: "Apenas X unidades", "Preco valido ate domingo".
- Frequencia maxima: 2.5. Varejo tem publico geograficamente limitado — satura rapido.""",
    },
    {
        "titulo": "servicos b2b mensagem benchmarks",
        "nichos": ["servicos"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- CPL para servicos B2B via WhatsApp: R$30-R$100. Lead qualificado justifica custo maior.
- Contabilidade e advocacia: CPL ate R$80 e normal. Ciclo de decisao e longo.
- Copy focado em dor especifica do segmento performa melhor que copy generico.
- Campanha de remarketing para visitantes do site costuma ter CPL 40-60% menor.
- Frequencia maxima: 3.0. Publico B2B e menor — monitorar saturacao semanalmente.""",
    },
    {
        "titulo": "engajamento instagram benchmarks brasil",
        "nichos": ["geral"],
        "tipo_campanha": "ENGAGEMENT",
        "fonte": "seed",
        "regras": """- CPM saudavel: R$15-R$35. Acima de R$40 indica publico muito pequeno ou alta competicao.
- CTR abaixo de 0.8% em 7 dias = problema de criativo, nao de publico — trocar o ad.
- CTR acima de 2.5% = criativo excelente — aumentar orcamento desse conjunto.
- Frequencia > 3.0 em campanha de engajamento: ampliar publico ou pausar.
- Visitas ao perfil nao geram conversao direta — usar como topo de funil, nao como metrica primaria de ROI.""",
    },
    {
        "titulo": "engajamento instagram sazonalidade",
        "nichos": ["geral"],
        "tipo_campanha": "ENGAGEMENT",
        "fonte": "seed",
        "regras": """- Semana santa, carnaval e natal: CPM sobe 30-50% — pausar ou reduzir orcamento preventivamente.
- Black Friday: CPM pode dobrar. So manter ativo se o objetivo e venda direta.
- Verao (dez/jan): engajamento de saude e beleza cresce naturalmente — bom momento para escalar.
- Segunda e terca: melhores dias para lancamento de novos criativos (mais atencao do usuario).""",
    },
    {
        "titulo": "regras gerais de escalada meta ads",
        "nichos": ["geral"],
        "tipo_campanha": "geral",
        "fonte": "seed",
        "regras": """- Nunca aumentar mais de 20% do orcamento por dia — acima disso o Meta reinicia a fase de aprendizado.
- Melhor horario para editar orcamento: entre 0h e 6h (menor competicao no leilao).
- Escalar no adset, nao no ad. O adset controla orcamento; o ad e apenas o criativo.
- Antes de escalar: verificar se o ad tem pelo menos 7 dias de dados e 50+ conversoes no adset.
- CBO (Campaign Budget Optimization) distribui orcamento automaticamente entre adsets — usar quando ha 2+ adsets com bom historico.""",
    },
    {
        "titulo": "regras gerais de pausa e reativacao",
        "nichos": ["geral"],
        "tipo_campanha": "geral",
        "fonte": "seed",
        "regras": """- Nunca pausar um ad com menos de 7 dias de dados. Variacao diaria e normal.
- Nunca pausar com menos de R$50 investidos nos ultimos 30 dias — dados insuficientes.
- Antes de pausar por CPL alto: verificar se o ad tem pelo menos 2-3 conversoes no periodo.
- Ad com 1 conversao e CPL aparentemente alto pode ser distorcao — aguardar mais dados.
- Reativar ad pausado: apenas se CPL da conta voltou abaixo do limite historico E o ad nao estava pausado por frequencia alta.""",
    },
    {
        "titulo": "fadiga criativa regras gerais",
        "nichos": ["geral"],
        "tipo_campanha": "geral",
        "fonte": "seed",
        "regras": """- Frequencia > 3.5: sinal forte de fadiga — pausar o ad independente do CPL.
- Frequencia entre 2.5 e 3.5: alerta — preparar novo criativo, mas nao pausar ainda.
- Frequencia < 2.0 com bom CPL: ad saudavel, pode escalar.
- Rotacao preventiva: trocar criativo a cada 30 dias mesmo sem queda, para evitar saturacao gradual.
- Publico restrito (cidade pequena, nicho especializado): frequencia sobe mais rapido — monitorar semanalmente.""",
    },
    {
        "titulo": "analise temporal e sazonalidade meta ads",
        "nichos": ["geral"],
        "tipo_campanha": "geral",
        "fonte": "seed",
        "regras": """- Analise minima: 7 dias de dados para qualquer decisao de pausa.
- Analise ideal: comparar ultimos 7 dias com baseline de 30 dias.
- Variacao de ate 30% no CPL entre dias da semana e normal (segunda tende a ser mais caro).
- Fim de semana: CTR geralmente maior, mas lead tende a ser menos qualificado.
- Evitar mudancas em campanhas na sexta a tarde — Meta leva ate 24h para reestabilizar apos mudancas.""",
    },
    {
        "titulo": "saude e clinicas mensagem benchmarks",
        "nichos": ["saude"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- Clinicas de saude (hiperbarica, estetica, nutricao): CPL via WhatsApp R$20-R$70.
- Tratamentos de alto ticket: CPL ate R$120 e aceitavel se conversao for boa.
- Copy com prova social (depoimento de paciente) performa 2x melhor que copy tecnico.
- Ads com video curto (15-30s) de depoimento real tendem a ter CPL 20-30% menor.
- Frequencia maxima: 3.0. Publico de saude e geograficamente restrito.""",
    },
    {
        "titulo": "purchase campaigns meta ads benchmarks",
        "nichos": ["geral"],
        "tipo_campanha": "PURCHASE",
        "fonte": "seed",
        "regras": """- ROAS saudavel depende da margem: para 50% de margem, ROAS minimo aceitavel e 2.0.
- CPA (custo por venda) ideal: < 30% do ticket medio do produto.
- Pixel do Meta precisa de pelo menos 50 eventos de compra por semana para sair do aprendizado.
- Retargeting de abandono de carrinho: CPA tipicamente 50-70% menor que prospeccao fria.
- Campanha de prospeccao + retargeting separados: melhor controle de orcamento e otimizacao.""",
    },
    {
        "titulo": "estrutura de campanha meta ads boas praticas",
        "nichos": ["geral"],
        "tipo_campanha": "geral",
        "fonte": "seed",
        "regras": """- Estrutura recomendada: 1 campanha por objetivo, 2-4 adsets por campanha, 2-3 ads por adset.
- Nao criar muitos adsets em 1 campanha — fragmenta orcamento e atrasa aprendizado.
- Testar 1 variavel por vez: ou publico diferente (adset) ou criativo diferente (ad).
- Nomenclatura padrao: [CLIENTE] [OBJETIVO] [PUBLICO/SEGMENTO] [DATA].
- Nunca editar ad ativo — sempre duplicar e pausar o original para manter historico.""",
    },
]


def _get_db():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido")
    return psycopg2.connect(db_url)


def run():
    conn = _get_db()
    cur = conn.cursor()
    inseridos = 0
    pulados = 0

    for bloco in BLOCOS:
        titulo_norm = bloco["titulo"].lower().strip()
        cur.execute(
            "SELECT id FROM gestor_conhecimento WHERE LOWER(TRIM(titulo)) = %s",
            (titulo_norm,),
        )
        if cur.fetchone():
            pulados += 1
            continue

        cur.execute(
            """
            INSERT INTO gestor_conhecimento (titulo, regras, nichos, tipo_campanha, fonte, origem)
            VALUES (%s, %s, %s, %s, %s, 'seed')
            """,
            (
                bloco["titulo"],
                bloco["regras"],
                bloco["nichos"],
                bloco.get("tipo_campanha", "geral"),
                bloco.get("fonte", "seed"),
            ),
        )
        inseridos += 1

    conn.commit()
    conn.close()
    print(f"Seed concluido: {inseridos} inseridos, {pulados} ja existiam.")


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Rodar seed**

```bash
cd /root && PYTHONPATH=/root /root/venv/bin/python -m meta.gestor.conhecimento.seed
```

Saída esperada: `Seed concluido: 15 inseridos, 0 ja existiam.`

- [ ] **Step 3: Verificar dados no banco**

```bash
PYTHONPATH=/root /root/venv/bin/python3 -c "
import os; from dotenv import load_dotenv; load_dotenv('/root/.env')
import psycopg2, psycopg2.extras
conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute('SELECT titulo, nichos, tipo_campanha FROM gestor_conhecimento ORDER BY id')
for r in cur.fetchall():
    print(r['titulo'][:50], '|', r['nichos'], '|', r['tipo_campanha'])
conn.close()
"
```

Saída esperada: 15 linhas com títulos, nichos e tipos.

- [ ] **Step 4: Testar `montar_contexto` com dados populados**

```bash
PYTHONPATH=/root /root/venv/bin/python3 -c "
import os; from dotenv import load_dotenv; load_dotenv('/root/.env')
from meta.gestor.conhecimento.contexto import montar_contexto
perfis = [
    {'nome': 'Espaço Dente', 'objetivo': 'MESSAGES'},
    {'nome': 'ISAC ROCHA FUNCIONAL & FITNESS', 'objetivo': 'MESSAGES'},
]
resultado = montar_contexto(perfis)
print(resultado[:500])
print('---')
print(f'Total chars: {len(resultado)}')
"
```

Saída esperada: bloco com `[DENTAL - MESSAGES]` e `[FITNESS - MESSAGES]` visíveis.

- [ ] **Step 5: Commit**

```bash
git add meta/gestor/conhecimento/seed.py
git commit -m "feat(gestor): seed de conhecimento senior (15 blocos curados)"
```

---

## Task 4: Integrar `contexto.py` no `analista.py`

**Files:**
- Modify: `meta/gestor/analista.py`

- [ ] **Step 1: Adicionar import e injeção no `analista.py`**

Logo após os imports existentes no topo do arquivo, adicionar:

```python
try:
    from meta.gestor.conhecimento.contexto import montar_contexto as _montar_contexto
except Exception:
    _montar_contexto = None  # type: ignore
```

Na função `analisar(perfis)`, antes de `user_msg = (...)`, adicionar:

```python
    # Injetar conhecimento de gestor sênior no system_prompt
    system_prompt = _SYSTEM_PROMPT
    if _montar_contexto is not None:
        bloco = _montar_contexto(perfis_validos)
        if bloco:
            system_prompt = _SYSTEM_PROMPT + "\n\n" + bloco
```

Substituir a chamada ao `client.messages.create`:
```python
    # ANTES:
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=_SYSTEM_PROMPT,
        ...
    )

    # DEPOIS:
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=system_prompt,
        ...
    )
```

- [ ] **Step 2: Verificar que analista.py ainda importa sem erro**

```bash
PYTHONPATH=/root /root/venv/bin/python3 -c "from meta.gestor.analista import analisar; print('OK')"
```

Saída esperada: `OK`

- [ ] **Step 3: Rodar varredura completa e verificar log**

```bash
PYTHONPATH=/root /root/venv/bin/python -m meta.gestor_agente 2>&1 | head -20
```

Saída esperada: varredura concluída sem erros.

- [ ] **Step 4: Commit**

```bash
git add meta/gestor/analista.py
git commit -m "feat(gestor): injeta conhecimento senior no prompt do analista"
```

---

## Task 5: `buscador.py` — agente semanal de busca

**Files:**
- Create: `meta/gestor/conhecimento/buscador.py`

- [ ] **Step 1: Instalar `duckduckgo_search`**

```bash
/root/venv/bin/pip install duckduckgo-search beautifulsoup4 2>&1 | tail -3
```

Saída esperada: `Successfully installed duckduckgo-search-...` ou `Requirement already satisfied`

- [ ] **Step 2: Criar `buscador.py`**

```python
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
```

- [ ] **Step 3: Smoke test do buscador (dry run — só testa imports e DB)**

```bash
PYTHONPATH=/root /root/venv/bin/python3 -c "
import os; from dotenv import load_dotenv; load_dotenv('/root/.env')
# Testa apenas as funções de DB sem fazer buscas reais
from meta.gestor.conhecimento.buscador import _get_db, _titulo_existe
conn = _get_db()
existe = _titulo_existe(conn, 'dental messages cpl benchmarks brasil')
print(f'titulo seed existe: {existe}')  # deve ser True
conn.close()
print('OK')
"
```

Saída esperada: `titulo seed existe: True \n OK`

- [ ] **Step 4: Commit**

```bash
git add meta/gestor/conhecimento/buscador.py
git commit -m "feat(gestor): buscador semanal DuckDuckGo + Claude extração"
```

---

## Task 6: Cron semanal + teste de integração final

**Files:**
- Modify: crontab do sistema

- [ ] **Step 1: Adicionar job semanal no crontab**

```bash
(crontab -l; echo "0 6 * * 1 cd /root && PYTHONPATH=/root /root/venv/bin/python -m meta.gestor.conhecimento.buscador >> /root/logs/gestor_buscador.log 2>&1") | crontab -
```

- [ ] **Step 2: Verificar crontab**

```bash
crontab -l | grep buscador
```

Saída esperada: `0 6 * * 1 cd /root && ... meta.gestor.conhecimento.buscador ...`

- [ ] **Step 3: Teste de integração — varredura com conhecimento injetado**

```bash
PYTHONPATH=/root /root/venv/bin/python -m meta.gestor_agente 2>&1 | tail -5
```

Saída esperada: varredura concluída, número de pendentes menor ou igual à rodada anterior.

- [ ] **Step 4: Verificar que o bloco de conhecimento está sendo injetado**

```bash
PYTHONPATH=/root /root/venv/bin/python3 -c "
import os; from dotenv import load_dotenv; load_dotenv('/root/.env')
from meta.gestor.conhecimento.contexto import montar_contexto
# Simula os perfis reais da carteira
perfis = [
    {'nome': 'Espaço Dente', 'objetivo': 'MESSAGES'},
    {'nome': 'CA 01 - Queen Poltronas DF', 'objetivo': 'MESSAGES'},
    {'nome': 'ISAC ROCHA FUNCIONAL & FITNESS', 'objetivo': 'MESSAGES'},
    {'nome': 'BM(24) REALIZE SORRISOS', 'objetivo': 'MESSAGES'},
]
bloco = montar_contexto(perfis)
linhas = bloco.splitlines()
print(f'Blocos injetados: {sum(1 for l in linhas if l.startswith(\"[\"))}')
print(f'Total chars: {len(bloco)}')
print('Primeiras 3 linhas:', linhas[:3])
"
```

Saída esperada: `Blocos injetados: 4+`, chars entre 800-1500.

- [ ] **Step 5: Commit final**

```bash
git add -A
git commit -m "feat(gestor): knowledge base completo — seed + buscador + contexto + cron"
```
