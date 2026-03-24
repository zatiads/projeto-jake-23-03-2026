# Spec: Análise de Performance — Jake OS

**Data:** 2026-03-24
**Status:** Aprovado pelo usuário

---

## Contexto

A página `#performance` no Jake OS existe mas está vazia (placeholder). O objetivo é construir um dashboard de acompanhamento de performance Meta Ads por agência (Piloti e Dentto), com visão geral de todos os clientes, alertas de saldo baixo, drill-down por cliente com comparação semanal e análise IA enriquecida com contexto do vault Obsidian.

---

## Escopo (Fase 1)

### O que está incluído
- Dashboard com tabs Piloti / Dentto
- Cards globais: Gasto Total, Saldo, CPL médio, Total de Leads
- Tabela de clientes com métricas individuais e badge de alerta de saldo
- Alerta de saldo < R$150: badge visual + mensagem Telegram (deduplicado por 1h)
- Painel lateral (drawer) por cliente com:
  - Comparação semana atual vs semana anterior (delta %)
  - Análise IA via Claude lendo vault Obsidian se disponível
  - Após análise: salva snapshot `.md` em `jake-brain/Clientes/<nome>/Performance/YYYY-WXX.md`

### O que não está incluído (Fase 2)
- Tabela `performance_semanal` no Neon PostgreSQL
- Histórico crescente no banco
- Gráficos de tendência multi-semana

---

## Arquitetura

### Backend — 3 novas rotas em `app.py`

#### `GET /api/performance/saldo/<agency>/<account_id>`
- Usa `get_saldo_conta()` de `meta/meta_api.py` com token da agência (`META_TOKEN_PILOTI` / `META_TOKEN_DENTTO`)
- Cache em memória: 30 min (igual ao insights)
- Retorna:
```json
{
  "balance": 80.50,
  "amount_spent": 1420.00,
  "spend_cap": 1500.00,
  "remaining": 80.00,
  "currency": "BRL",
  "alerta": true
}
```
- `alerta: true` quando `remaining < 150`

#### `POST /api/performance/alerta-saldo`
- Body: `{ agency, account_id, nome, saldo }`
- Envia mensagem Telegram para `TELEGRAM_ALERT_CHAT_ID`:
  `"⚠️ Patrão, saldo baixo em [nome] ([agency]): R$ XX,XX"`
- Deduplicação server-side: dict em memória `{account_id: timestamp}` — não reenvia se passou < 1h

#### `GET /api/performance/semana-anterior/<agency>/<account_id>`
- Duas chamadas Meta API com datas explícitas (`since`/`until`):
  - Semana atual: últimos 7 dias
  - Semana anterior: 8 a 14 dias atrás
- Retorna mesma estrutura do `/api/relatorios/insights` para cada período:
```json
{
  "atual":    { "spend": ..., "leads": ..., "messaging": ..., "clicks": ..., "reach": ..., "cpm": ..., "ctr": ... },
  "anterior": { "spend": ..., "leads": ..., "messaging": ..., "clicks": ..., "reach": ..., "cpm": ..., "ctr": ... }
}
```

### Enriquecimento da rota existente `/api/relatorios/analise`
- Antes de chamar Claude: procura arquivo `.md` mais recente em `/root/jake-brain/Clientes/<nome>/Performance/`
- Se encontrar: injeta no prompt como "Contexto histórico"
- Após análise bem-sucedida: salva snapshot da semana atual em `jake-brain/Clientes/<nome>/Performance/YYYY-WXX.md`
- Cria diretório se não existir
- Snapshot inclui: data, métricas atuais, delta vs semana anterior, texto da análise IA

---

## Frontend

### Arquivos

| Arquivo | Ação |
|---|---|
| `jake_desktop/static/js/performance.js` | Criar — toda a lógica da página |
| `jake_desktop/templates/dashboard.html` | Modificar — substituir placeholder pelo HTML real |
| `jake_desktop/app.py` | Modificar — 3 novas rotas + enriquecer `/api/relatorios/analise` |

### HTML da página (`#page-performance`)

```
┌─────────────────────────────────────────────────────┐
│  [Piloti] [Dentto]  ← tabs                          │
│                                                      │
│  Cards globais (soma da agência):                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │Gasto     │ │Saldo     │ │CPL médio │ │Leads   │ │
│  │R$ 4.320  │ │⚠ R$ 80  │ │R$ 12,50  │ │  347   │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│                                                      │
│  Tabela:                                            │
│  Nome | Gasto | Saldo | Leads | CPL | [detalhe >]  │
│  ⚠ HiperClin | R$320 | R$80 | 27 | R$11,85 | >    │
│  Isac        | R$480 | R$520| 41 | R$11,70 | >    │
│  ...                                                │
│                                                      │
│  [Drawer lateral ao clicar em >]                    │
│  ┌───────────────────────────────────────────┐      │
│  │ HiperClin                           [X]  │      │
│  │                                          │      │
│  │ Semana atual  vs  Semana anterior        │      │
│  │ Gasto:  R$320    R$290    (+10,3%)       │      │
│  │ Leads:  27       22       (+22,7%)       │      │
│  │ CPL:    R$11,85  R$13,18  (-10,1%)  ✅  │      │
│  │ ...                                      │      │
│  │                                          │      │
│  │ [Analisar com IA]                        │      │
│  │ > "Boa performance: leads aumentaram..." │      │
│  └───────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────┘
```

### Comportamento JavaScript

**Ao entrar na página:**
1. Mostra skeleton loading em cards e tabela
2. Dispara fetch paralelo de insights (rota existente) + saldo (nova rota) para todos os clientes
3. Atualiza cards globais (somas/médias) e linhas da tabela
4. Se saldo < 150 em alguma conta:
   - Badge `⚠` vermelho na linha e no card de saldo global
   - Verifica localStorage: se alerta já enviado há menos de 1h, não reenvia
   - Caso contrário: POST `/api/performance/alerta-saldo` + salva timestamp no localStorage

**Ao clicar em `>`:**
1. Abre drawer lateral com nome do cliente
2. Busca `/api/performance/semana-anterior/<agency>/<id>` (loading)
3. Exibe tabela comparativa com delta (verde se melhora, vermelho se piora)
4. Botão "Analisar com IA":
   - POST `/api/relatorios/analise` com métricas enriquecidas (inclui semana anterior e delta)
   - Exibe análise em parágrafo de texto
   - Vault snapshot salvo silenciosamente no backend

**Visual:** padrão dark/Jarvis idêntico ao módulo relatórios — sem novos estilos, reutilizar CSS existente onde possível.

---

## Deduplicação de Alertas

| Camada | Mecanismo | TTL |
|---|---|---|
| Frontend | `localStorage["perf_alerta_<id>"]` = timestamp | 1h |
| Backend | Dict em memória `_alerta_sent = {account_id: timestamp}` | 1h |

---

## Obsidian (jake-brain)

**Leitura:** antes da análise IA, busca o `.md` mais recente em:
`/root/jake-brain/Clientes/<nome-normalizado>/Performance/`

**Escrita:** após análise, cria/sobrescreve:
`/root/jake-brain/Clientes/<nome-normalizado>/Performance/YYYY-WXX.md`

Conteúdo do snapshot:
```markdown
# Performance — [Nome do Cliente] — Semana XX/YYYY

**Data de análise:** YYYY-MM-DD

## Métricas
| Métrica | Atual | Anterior | Delta |
|---|---|---|---|
| Gasto | R$ XX | R$ XX | +X% |
| Leads | XX | XX | +X% |
| CPL | R$ XX | R$ XX | -X% |

## Análise IA
[texto gerado pelo Claude]
```

---

## Dependências

- `meta/meta_api.py` → `get_saldo_conta()` **não pode ser usada diretamente** — ela usa `META_ACCESS_TOKEN` fixo. A rota `/api/performance/saldo` deve inlinear a chamada à Meta API usando `_META_TOKENS[agency]()`, igual ao que a rota de insights já faz.
- `/api/relatorios/insights` → já existe, reutilizado
- `/api/relatorios/analise` → já existe, será enriquecida (ver payload abaixo)
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ALERT_CHAT_ID` → já no `.env`. Fallback: `AUTHORIZED_ID` (comportamento existente em `_send_telegram()`)
- `jake-brain/Clientes/` → contém arquivos `.md` flat (ex: `dentto.md`, `piloti.md`), **não subdiretórios**. A implementação deve criar `os.makedirs(..., exist_ok=True)` ao salvar snapshots.

## Config de clientes

O mapeamento agência → lista de clientes (mesmo dict do `relatorios.js`) fica definido no `performance.js`:

```js
var AGENCIES = {
  piloti: [
    { id: "act_712297048202295",  name: "61 eventos"       },
    { id: "act_2162454744176337", name: "Amanda"           },
    { id: "act_1006820257491698", name: "Calixta"          },
    { id: "act_1095710212746155", name: "Daniele Taveira"  },
    { id: "act_5684689948235819", name: "HiperClin"        },
    { id: "act_1006436427517079", name: "IOB"              },
    { id: "act_126503999415274",  name: "Isac Academia"    },
    { id: "act_812220691454430",  name: "Maíra Castaldi"   },
    { id: "act_1693935704869895", name: "Marcus"           },
    { id: "act_507545471090485",  name: "Odonto Uberaba"   },
    { id: "act_323137203122197",  name: "Queen Poltronas"  },
    { id: "act_840594572249284",  name: "RD Contabilidade" },
    { id: "act_7838846752907408", name: "Realize Sorrisos" },
    { id: "act_510054631964792",  name: "RunWay"           }
  ],
  dentto: []
};
```

## Payload enriquecido para `/api/relatorios/analise`

```json
{
  "nome": "HiperClin",
  "metricas": { "Gasto": "R$ 320,00", "Leads": 27, "CPL": "R$ 11,85", "Alcance": 8420 },
  "metricas_anterior": { "Gasto": "R$ 290,00", "Leads": 22, "CPL": "R$ 13,18", "Alcance": 7100 },
  "delta": { "Gasto": "+10,3%", "Leads": "+22,7%", "CPL": "-10,1%", "Alcance": "+18,6%" }
}
```

O backend formata no prompt:
```
Semana atual: Gasto R$320, Leads 27, CPL R$11,85...
Semana anterior: Gasto R$290, Leads 22, CPL R$13,18...
Variação: Leads +22,7%, CPL -10,1% (melhora)...
```

## Normalização de nomes para vault

Regra: lowercase, sem acentos, espaços → hífens, caracteres especiais removidos.
Exemplos: `"HiperClin"` → `hiperclin`, `"Maíra Castaldi"` → `maira-castaldi`, `"61 eventos"` → `61-eventos`

Função Python:
```python
import re, unicodedata
def _slug(name):
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")
```

---

## Critérios de sucesso

- [ ] Tabs Piloti/Dentto funcionando com dados reais da Meta API
- [ ] Badge de alerta aparece quando saldo < R$150
- [ ] Mensagem Telegram disparada (1x por hora por conta)
- [ ] Drawer abre com comparação semana atual vs anterior
- [ ] Análise IA gerada com contexto do vault quando disponível
- [ ] Snapshot salvo no vault após análise
