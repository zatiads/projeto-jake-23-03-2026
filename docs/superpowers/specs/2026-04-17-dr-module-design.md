# Design Spec: Módulo DR no Jake OS

**Data:** 2026-04-17
**Status:** Aprovado pelo usuário
**Autor:** Bruno (Piloti Digital Agency)

---

## Contexto

Bruno é gestor de tráfego pago com 14 contas ativas no Meta Ads. Está entrando no mercado de Direct Response como produtor — clonando estrutura e posicionamento de ofertas vencedoras para criar seus próprios produtos digitais.

**Stack de ferramentas:**
- **American Swipe** → pesquisa de mercado, transcrição de VSLs, histórico de performance (ferramenta externa, não integrada ao Jake OS)
- **Jake OS** → execução e geração de ativos
- **Meta Ads** → validação com tráfego pago
- **UTMfy** → rastreamento de performance (externo, não integrado ao Jake OS)
- **Hotmart** → checkout (Bruno como produtor)

---

## Escopo do Módulo

### O que o Jake OS faz no fluxo DR:
1. Salvar e gerenciar ofertas em banco de dados
2. Gerar ativos: copy adaptada, script de VSL, criativos, LP HTML, quiz HTML
3. Deploy de LP e quiz clonados no Vercel

### O que está fora do escopo:
- Transcrição de VSL (American Swipe já faz)
- Monitor de performance / CPA / ROAS (UTMfy)
- Webhooks Hotmart
- Integração UTMfy API

---

## Arquitetura

### Localização
Nova seção `#dr` no nav do Jake OS (dashboard.html), entre as seções existentes.

### Persistência de dados
Ofertas são salvas no banco Neon (PostgreSQL). Passo 1 cria/atualiza um registro na tabela `dr_ofertas`. Passos 2, 3 e 4 leem da oferta selecionada. O contexto também é espelhado em `sessionStorage` (chave: `'dr_contexto'`) para acesso rápido no frontend sem round-trip ao servidor.

**Nota:** Se `sessionStorage` for perdido em refresh, o frontend detecta e recarrega da oferta ativa no banco. Sem perda de dados.

### Banco de dados — tabela `dr_ofertas`

```sql
CREATE TABLE dr_ofertas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    nicho VARCHAR(200),
    angulo TEXT,
    hook TEXT,
    promessa TEXT,
    publico TEXT,
    contexto_raw TEXT,
    tipo_funil VARCHAR(50),
    copy_json JSONB,
    script_vsl TEXT,
    angulos_json JSONB,
    lp_html TEXT,
    lp_url VARCHAR(500),
    quiz_html TEXT,
    quiz_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

Lista de ofertas salvas exibida no topo da seção `#dr` — cards clicáveis para carregar uma oferta anterior.

### Novos arquivos
- `jake_desktop/static/js/dr.js` — lógica frontend da seção DR
- `jake_desktop/static/css/dr.css` — estilos (padrão visual Jake OS)

### Arquivos modificados
- `jake_desktop/app.py` — novas rotas `/api/dr/*` + `_init_dr_tables()`
- `jake_desktop/templates/dashboard.html` — nav item + HTML seção `#dr`
- `jake_desktop/static/js/app.js` — adicionar `"dr"` ao array `valid` de páginas (linha ~28); chamar `window.initDR()` no `showPage("dr")` com guard: `if (typeof window.initDR === 'function') window.initDR()`

### Infraestrutura reutilizada
- **Deploy → Vercel**: reutiliza `_deploy_to_vercel(project_name, index_html)` existente no Site Architect. Não requer novas env vars além de `VERCEL_TOKEN` já configurado.
- Geração de criativos → `/api/generate-creative` existente
- Claude API → `_anthropic_client_46()` existente
- HTTP fetch → `requests` já no projeto
- DB → `_get_db()` existente

---

## Design dos 4 Passos

### Passo 1 — Oferta

**Objetivo:** Criar/editar oferta, gerar copy e script VSL, salvar no banco.

**Lista de ofertas:** Acima do formulário, cards das ofertas salvas com nome, nicho e data. Clicar em um card carrega a oferta no formulário. Botão "Nova oferta" limpa o formulário.

**Interface — dois modos (toggle):**

**Modo Rápido:**
- Textarea grande: "Cole aqui o contexto do American Swipe (transcrição, análise, estrutura da oferta)"
- Campo: Nome da oferta (obrigatório, para identificar no histórico)
- Campo: Produto
- Campo: Público-alvo

**Modo Estruturado:**
- Nome da oferta (obrigatório)
- Nicho
- Ângulo principal
- Hook principal
- Promessa central
- Público-alvo (avatar)
- Provas usadas (depoimentos, resultados, certificados)
- Objeções tratadas
- Tipo de funil: VSL Direto / Quiz → VSL

**Output — 3 abas:**
1. **Copy Adaptada**: headline, subheadline, 5-7 bullets de benefício, copy de anúncio (3 variações: curta/média/longa), CTA
2. **Script VSL**: estrutura completa por blocos — Hook → Problema → Agitação → Solução → Prova → Oferta → Garantia → CTA. Cada bloco com texto sugerido.
3. **Ângulos Alternativos**: 3 ângulos diferentes para split test

Cada aba tem botão "Copiar". Output é salvo automaticamente no banco ao ser gerado. Botão "Ir para LP →" abre Passo 2 com contexto da oferta ativa.

**Backend:**
- `POST /api/dr/ofertas` — cria oferta nova, retorna `{ id, ... }`
- `GET /api/dr/ofertas` — lista todas as ofertas (id, nome, nicho, created_at)
- `GET /api/dr/ofertas/<id>` — carrega oferta completa
- `DELETE /api/dr/ofertas/<id>` — remove oferta
- `POST /api/dr/gerar-copy` — Input: oferta_id + contexto. Output: `{ copy, script_vsl, angulos }`. Salva resultado na oferta. `max_tokens`: 4096. Engine: Claude Sonnet 4.6.

---

### Passo 2 — Landing Page

**Objetivo:** Clonar LP de oferta vencedora e gerar versão adaptada, pronta para deploy.

**Interface — dois modos:**

**Clonar LP existente (modo principal):**
- Campo URL da LP original
- Jake OS faz `requests.get(url, headers={"User-Agent": "Mozilla/5.0 ..."}, timeout=10)` → extrai HTML
- Claude analisa estrutura (headline, video, bullets, prova, CTA) → gera versão adaptada ao produto do Bruno
- **Fallback obrigatório:** se fetch retornar status != 200, timeout, ou HTML com menos de 500 caracteres de conteúdo visível, cai para modo "gerar do zero" e exibe aviso: _"Não foi possível carregar a URL original — LP gerada do zero com base no contexto."_

**Gerar do zero:**
- Usa contexto da oferta ativa (pré-preenchido)
- Claude gera estrutura padrão VSL

**Campos adicionais (ambos os modos):**
- Link do Hotmart (checkout URL)
- URL do vídeo VSL (YouTube ou Vimeo embed)
- Pixel ID Meta DR (editável, persiste em `localStorage`)
- Preço + parcelas (ex: "R$97 ou 3x R$37")

**LP gerada inclui:**
- Meta Pixel no `<head>` com Pixel ID configurado
- Hero: headline + subheadline (da oferta ativa)
- Player de vídeo embed (YouTube/Vimeo iframe)
- Bullets de benefício (da oferta ativa)
- Seção de prova social (3 depoimentos placeholder gerados por Claude)
- **Timer de escassez:** data de encerramento fixa via `localStorage` (primeira visita define; visitas seguintes leem a mesma). Não usar countdown com reset por cookie — dark pattern sinalizado em auditorias Meta.
- Bloco de preço + botão CTA → Hotmart com UTMs automáticos (`utm_source=meta&utm_medium=cpc&utm_campaign={slug_produto}`)
- Mobile-first, CSS inline, zero dependências externas

**Ações disponíveis:**
- Preview (abre em nova aba via `blob:` URL)
- Download HTML
- Deploy Vercel (chama `_deploy_to_vercel("jake-dr-lp", html)` → retorna URL pública, salva em `lp_url` na oferta)

**Backend:**
- `POST /api/dr/clonar-lp` — oferta_id + URL → fetch + Claude → LP HTML adaptada. Salva em `lp_html`. `max_tokens`: 8192
- `POST /api/dr/gerar-lp` — oferta_id + contexto → Claude → LP do zero. Salva em `lp_html`. `max_tokens`: 8192
- `POST /api/dr/deploy-lp` — oferta_id + HTML → `_deploy_to_vercel("jake-dr-lp", html)` → salva URL em `lp_url`, retorna URL

---

### Passo 3 — Criativos

**Objetivo:** Gerar criativos visuais com contexto DR pré-preenchido.

**Implementação:** Sem novo backend. O botão "Ir para Criativos" no Passo 3:
1. Chama `showPage("criativos")`
2. Lê contexto da oferta ativa em `sessionStorage.getItem("dr_contexto")`
3. Concatena `nicho + ângulo + hook` em string de prompt
4. Escreve em `document.getElementById("cri-prompt").value`

Requer alteração mínima em `dr.js` — nenhuma mudança em `criativos.js`.

---

### Passo 4 — Quiz

**Objetivo:** Clonar quiz de oferta vencedora e gerar versão HTML adaptada, pronta para deploy.

**Mesma lógica do Passo 2 (LP Cloner), aplicada a quizzes.**

**Interface:**
- Campo URL do quiz original
- Jake OS faz `requests.get(url, headers={"User-Agent": "Mozilla/5.0 ..."}, timeout=10)` → extrai HTML
- Claude analisa estrutura: perguntas, opções, barra de progresso, resultado, lógica de segmentação → gera versão HTML adaptada
- **Fallback:** se JS-heavy (HTML < 500 chars de conteúdo visível), exibe aviso: _"Quiz com renderização pesada em JS — clone parcial gerado com estrutura base."_ Claude gera quiz HTML funcional com estrutura genérica.

**Quiz gerado inclui:**
- 3-5 perguntas com opções (baseadas no nicho/ângulo da oferta)
- Barra de progresso
- Resultado personalizado por perfil de resposta
- Coleta de email antes de revelar resultado (campo simples, sem integração de email nesta versão)
- Redirect para LP/VSL ao final
- Mobile-first, CSS inline, zero dependências externas

**Ações disponíveis:**
- Preview (nova aba via `blob:` URL)
- Download HTML
- Deploy Vercel (chama `_deploy_to_vercel("jake-dr-quiz", html)` → salva em `quiz_url` na oferta)

**Backend:**
- `POST /api/dr/clonar-quiz` — oferta_id + URL → fetch + Claude → quiz HTML adaptado. Salva em `quiz_html`. `max_tokens`: 8192
- `POST /api/dr/deploy-quiz` — oferta_id + HTML → `_deploy_to_vercel("jake-dr-quiz", html)` → salva URL em `quiz_url`, retorna URL

---

## Rotas Backend Resumidas

| Rota | Método | Função | max_tokens |
|------|--------|--------|-----------|
| `/api/dr/ofertas` | GET | Lista ofertas salvas | — |
| `/api/dr/ofertas` | POST | Cria nova oferta | — |
| `/api/dr/ofertas/<id>` | GET | Carrega oferta completa | — |
| `/api/dr/ofertas/<id>` | DELETE | Remove oferta | — |
| `/api/dr/gerar-copy` | POST | Gera copy + script VSL + ângulos | 4096 |
| `/api/dr/clonar-lp` | POST | Clona LP: fetch URL → Claude → HTML adaptado | 8192 |
| `/api/dr/gerar-lp` | POST | Gera LP do zero via Claude | 8192 |
| `/api/dr/deploy-lp` | POST | Deploy LP no Vercel | — |
| `/api/dr/clonar-quiz` | POST | Clona quiz: fetch URL → Claude → HTML adaptado | 8192 |
| `/api/dr/deploy-quiz` | POST | Deploy quiz no Vercel | — |

`/api/generate-creative` — reutilizado sem alteração

---

## Ordem de Implementação

1. **DB + CRUD de ofertas** — tabela `dr_ofertas`, rotas GET/POST/DELETE, lista de ofertas no frontend
2. **Passo 1** — Copy + Script VSL com salvamento na oferta
3. **Passo 2** — LP Cloner + Gerar do zero + Deploy
4. **Passo 4** — Quiz Cloner + Deploy
5. **Passo 3** — Criativos (só integração frontend)

---

## Decisões de Design

- **Banco de dados para ofertas**: `dr_ofertas` no Neon. Ofertas persistem entre sessões, acessíveis por histórico. `sessionStorage` é espelho local para acesso rápido no frontend.
- **Pixel ID persiste em localStorage**: mesmo pixel em todas as campanhas DR.
- **LP e quiz autocontidos**: CSS inline, sem frameworks, zero dependências externas.
- **Fallback com aviso explícito**: se fetch falhar no cloner (LP ou quiz), usuário vê mensagem clara antes de receber versão gerada do zero.
- **Timer estático por localStorage**: countdown com reset é dark pattern sinalizado em auditorias Meta.
- **Deploy via Vercel** (`_deploy_to_vercel()`): função existente no Site Architect, parametrizada. LP → `project_name = "jake-dr-lp"`. Quiz → `project_name = "jake-dr-quiz"`.
- **Passo 3 via injeção direta no DOM**: escreve em `#cri-prompt` após `showPage("criativos")`. Zero mudança em `criativos.js`.
- **Coleta de email no quiz sem integração nesta versão**: campo de email presente na UI do quiz gerado, mas sem backend de lista (MailerLite fica para versão futura).
