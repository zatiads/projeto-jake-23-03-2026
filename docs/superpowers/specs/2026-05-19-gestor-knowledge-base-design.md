# Gestor IA — Base de Conhecimento Sênior

**Data:** 2026-05-19
**Status:** Aprovado

## Problema

O Gestor IA toma decisões usando apenas o conhecimento geral do Claude (modelo de linguagem). Ele não tem benchmarks específicos por nicho (dental, fitness, varejo, serviços B2B), nem regras práticas de gestão de tráfego pago no contexto brasileiro. Isso resulta em decisões genéricas — pausar criativos com CPL ainda aceitável para o nicho, ou escalar em momentos errados.

## Objetivo

Injetar no prompt do analista um bloco de "conhecimento de gestor sênior" — regras acionáveis, benchmarks por nicho e boas práticas de Meta Ads — que melhore a qualidade das decisões sem exigir configuração manual por conta.

## Escopo

- Enriquecimento do prompt do analista (Seção A do design aprovado)
- Não altera thresholds no banco automaticamente
- Não modifica o fluxo de aprovação/execução existente

---

## Arquitetura

### Novo módulo: `meta/gestor/conhecimento/`

```
meta/gestor/conhecimento/
  __init__.py
  seed.py       -- popula base inicial curada (roda 1 vez)
  buscador.py   -- agente semanal de busca + extração via Claude
  contexto.py   -- injeta conhecimento relevante no analista
```

### Tabela no banco: `gestor_conhecimento`

```sql
CREATE TABLE gestor_conhecimento (
    id          SERIAL PRIMARY KEY,
    titulo      TEXT NOT NULL,
    regras      TEXT NOT NULL,        -- regras acionáveis em texto
    nichos      TEXT[] DEFAULT '{}',  -- ['dental','fitness','geral',...]
    tipo_campanha TEXT,               -- 'MESSAGES','PURCHASE','ENGAGEMENT','geral'
    fonte       TEXT,                 -- URL ou 'seed'
    origem      TEXT DEFAULT 'seed',  -- 'seed' | 'busca'
    ativo       BOOLEAN DEFAULT TRUE,
    criado_em   TIMESTAMP DEFAULT NOW()
);
```

---

## Componentes

### 1. `seed.py` — Base curada inicial

Script de migração única. Popula a tabela com ~20 blocos de conhecimento de alta qualidade cobrindo:

- **Dental / MESSAGES**: CPL saudável R$8–R$25, limite R$40, freq máx 3.0, sazonalidade (jan/jul picos)
- **Fitness / MESSAGES**: CPL R$15–R$50, premium até R$80, sazonalidade (jan/set picos +30%)
- **Varejo / MESSAGES**: CPL R$20–R$60, alta variação por ticket médio
- **Serviços B2B / MESSAGES**: CPL R$30–R$100 aceitável (lead qualificado vale mais)
- **Engajamento geral**: CPM > R$40 = público pequeno, CTR < 0.8% em 7d = problema de criativo
- **Escalada geral**: Nunca +20%/dia, melhor horário 0h–6h, escalar no adset não no ad
- **Fadiga criativa**: Freq > 2.5 em < 14 dias = público restrito, > 3.5 = pausar
- **Análise temporal**: Nunca pausar com < 7 dias de dados, variação semanal é normal

### 2. `buscador.py` — Agente de busca semanal

**Fluxo:**
1. Executa ~8 queries no DuckDuckGo (via `duckduckgo_search`)
2. Scraping dos top-5 resultados por query (`requests` + `BeautifulSoup`)
3. Claude recebe texto bruto e extrai apenas regras acionáveis no formato padronizado
4. Se conteúdo for genérico/fraco/duplicado → Claude descarta
5. Se aprovado → salva no banco com `origem='busca'`

**Queries rotativas:**
```
"CPL Meta Ads benchmark Brasil {ano} {nicho}"
"frequência anúncios Meta Ads quando pausar escalar"
"tráfego pago Meta Ads otimização avançada gestor sênior"
"Meta Ads campaign budget optimization rules 2024"
"quando escalar orçamento Meta Ads sem perder performance"
```

**Prompt de extração (Claude):**
```
Você é um especialista em tráfego pago Meta Ads no Brasil.
Leia o texto abaixo e extraia APENAS regras acionáveis sobre gestão de campanhas.
Ignore conteúdo genérico, de vendas ou sem dados concretos.

Retorne SOMENTE JSON válido neste formato:
{
  "aprovado": true|false,
  "motivo_rejeicao": "string ou null",
  "titulo": "string curto descritivo",
  "nichos": ["dental"|"fitness"|"varejo"|"servicos"|"saude"|"geral"],
  "tipo_campanha": "MESSAGES"|"PURCHASE"|"ENGAGEMENT"|"geral",
  "regras": "- regra 1\n- regra 2\n..."
}

Rejeite (aprovado=false) se: menos de 3 regras acionáveis, conteúdo genérico sem números,
ou conteúdo de vendas sem informação técnica útil.

TEXTO:
{texto}
```

**Controle de qualidade:**
- Output parseado como JSON; se `aprovado=false` → descartado sem salvar
- Duplicatas: match exato em `titulo` normalizado (lowercase, strip) contra últimas 100 entradas

**Execução:** cron toda segunda às 6h00 (antes da varredura das 7h30)

### 3. `contexto.py` — Injeção no analista

**Detecção de nicho por nome de conta:**
```python
NICHO_MAP = {
    "dental":   ["ODC", "Espaço Dente", "Odontocompany", "Realize", "Uberaba", "Ilhota",
                 "Massaranduba", "Schroeder", "Tijucas", "São Francisco", "Cordeirópolis"],
    "fitness":  ["ISAC", "mrrunners", "Meu Ritmo"],
    "varejo":   ["Queen Poltronas", "Saucker"],
    "servicos": ["Castaldi", "RD Contabilidade", "Calixta", "Runway"],
    "saude":    ["Hiperbárica", "Vielife"],
}
```

**Seleção de blocos:**
- Detecta nichos presentes na lista de perfis da varredura
- Busca no banco: filtro por `nichos` + `ativo=TRUE`, ordenado por `origem='seed'` primeiro
- Limite: 10 blocos, máx ~1.000 tokens

**Formato do bloco injetado:**
```
CONHECIMENTO DE GESTOR SENIOR — use como referencia nas decisoes:

[DENTAL - MESSAGES]
- CPL saudavel: R$8-R$25. Acima de R$40 = criativo saturado ou publico errado.
- Frequencia maxima: 3.0 antes de rodar novo criativo.
...
```

**Assinatura de `montar_contexto`:**
```python
def montar_contexto(perfis: list[dict]) -> str:
    """
    perfis: lista de dicts com pelo menos as chaves:
      - 'nome': str  (nome da conta, ex: "Espaço Dente")
      - 'objetivo': str  (ex: "MESSAGES", "ENGAGEMENT", "PURCHASE")
    Retorna string formatada para append no system_prompt do analista.
    Retorna "" se banco vazio ou erro.
    """
```

**Integração com `analista.py`:**
```python
from meta.gestor.conhecimento.contexto import montar_contexto

bloco = montar_contexto(perfis)
system_prompt = _SYSTEM_PROMPT + ("\n\n" + bloco if bloco else "")
```

---

## Budget de tokens por varredura

| Componente | Tokens |
|---|---|
| Prompt atual do analista | ~900 |
| Bloco de conhecimento (10 blocos) | ~1.000 |
| **Total** | **~1.900** |

Custo adicional por varredura: ~$0.003 (modelo claude-sonnet-4-6, contexto de 200k tokens — sem risco de overflow).

---

## Cron

| Job | Schedule | Descrição |
|---|---|---|
| `seed.py` | uma vez | Popula base inicial |
| `buscador.py` | `0 6 * * 1` (segunda 6h) | Atualiza com novos conteúdos |

---

## Arquivos a criar/modificar

| Arquivo | Ação |
|---|---|
| `meta/gestor/conhecimento/__init__.py` | criar |
| `meta/gestor/conhecimento/seed.py` | criar |
| `meta/gestor/conhecimento/buscador.py` | criar |
| `meta/gestor/conhecimento/contexto.py` | criar |
| `meta/gestor/analista.py` | modificar (importar e injetar contexto) |
| `meta/gestor/migrations.py` | modificar — adicionar migration com o CREATE TABLE acima (executar antes do seed.py) |
| `crontab` | modificar (adicionar job semanal buscador) |

---

## Dependencias Python

- `duckduckgo_search` (busca sem API key)
- `beautifulsoup4` (ja instalado)
- `requests` (ja instalado)
- `anthropic` (ja instalado)
