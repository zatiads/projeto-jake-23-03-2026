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
- **InLead** (ou similar) → quiz funnels (ferramenta externa)

---

## Escopo do Módulo

### O que o Jake OS faz no fluxo DR:
1. Receber contexto da oferta vencedora (trazido pelo usuário do American Swipe)
2. Gerar ativos: copy adaptada, script de VSL, criativos, LP HTML, roteiro de quiz
3. Deploy da LP no Vercel

### O que está fora do escopo:
- Transcrição de VSL (American Swipe já faz)
- Monitor de performance / CPA / ROAS (UTMfy)
- Quiz builder interativo (InLead)
- Webhooks Hotmart
- Integração UTMfy API

---

## Arquitetura

### Localização
Nova seção `#dr` no nav do Jake OS (dashboard.html), entre as seções existentes.

### Fluxo de dados
Passo 1 salva contexto em `sessionStorage` do browser. Passos 2, 3 e 4 leem esse contexto e pré-preenchem campos automaticamente. Sem persistência em banco de dados — workflow ephemeral por sessão.

**Nota:** `sessionStorage` é perdido em refresh de página. Se o usuário atualizar o browser nos Passos 2, 3 ou 4, o frontend deve detectar contexto vazio e exibir banner: _"Contexto DR perdido. Volte ao Passo 1 para recarregar."_

### Novos arquivos
- `jake_desktop/static/js/dr.js` — lógica frontend da seção DR
- `jake_desktop/static/css/dr.css` — estilos (padrão visual Jake OS)

### Arquivos modificados
- `jake_desktop/app.py` — novas rotas `/api/dr/*`
- `jake_desktop/templates/dashboard.html` — nav item + HTML seção `#dr`
- `jake_desktop/static/js/app.js` — adicionar `"dr"` ao array `valid` de páginas (linha ~28); chamar `window.initDR()` no `showPage("dr")` seguindo padrão da seção `nutricao`, com guard: `if (typeof window.initDR === 'function') window.initDR()`

### Infraestrutura reutilizada
- **Deploy LP → Vercel**: reutiliza `_deploy_to_vercel(project_name, index_html)` existente no Site Architect. `project_name` = `"jake-dr-lp"`. Não requer novas env vars além de `VERCEL_TOKEN` já configurado.
- Geração de criativos → `/api/generate-creative` existente
- Claude API → `_anthropic_client_46()` existente
- HTTP fetch → `requests` já no projeto

---

## Design dos 4 Passos

### Passo 1 — Oferta

**Objetivo:** Intake do contexto + geração de copy e script VSL.

**Interface — dois modos (toggle):**

**Modo Rápido:**
- Textarea grande: "Cole aqui o contexto do American Swipe (transcrição, análise, estrutura da oferta)"
- Campo: Produto
- Campo: Público-alvo

**Modo Estruturado:**
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

Cada aba tem botão "Copiar". Botão "Salvar e ir para LP →" persiste contexto no `sessionStorage` (chave: `'dr_contexto'`) e abre Passo 2.

**Backend:** `POST /api/dr/gerar-copy`
- Input: contexto estruturado ou texto livre + produto + público
- Output: `{ copy, script_vsl, angulos }`
- Engine: Claude Sonnet 4.6
- `max_tokens`: 4096

---

### Passo 2 — Landing Page

**Objetivo:** Gerar LP HTML completa, autocontida, pronta para deploy.

**Interface — dois modos:**

**Clonar LP existente:**
- Campo URL da LP original
- Jake OS faz `requests.get(url, headers={"User-Agent": "Mozilla/5.0 ..."}, timeout=10)` → extrai HTML
- Claude analisa estrutura (headline, video, bullets, prova, CTA) → gera versão adaptada ao produto do Bruno
- **Fallback obrigatório:** se o fetch retornar status != 200, timeout, ou HTML com menos de 500 caracteres de conteúdo visível, o sistema cai automaticamente para modo "gerar do zero" **e exibe aviso explícito ao usuário:** _"Não foi possível carregar a URL original — LP gerada do zero com base no contexto."_

**Gerar do zero:**
- Usa contexto do Passo 1 (pré-preenchido)
- Claude gera estrutura padrão VSL

**Campos adicionais (ambos os modos):**
- Link do Hotmart (checkout URL)
- URL do vídeo VSL (YouTube ou Vimeo embed)
- Pixel ID Meta DR (editável, persiste em `localStorage` para próximas LPs)
- Preço + parcelas (ex: "R$97 ou 3x R$37")

**LP gerada inclui:**
- Meta Pixel no `<head>` com Pixel ID configurado
- Hero: headline + subheadline (do Passo 1)
- Player de vídeo embed (YouTube/Vimeo iframe)
- Bullets de benefício (do Passo 1)
- Seção de prova social (3 depoimentos placeholder gerados por Claude)
- **Timer de escassez:** bloco estático "Oferta por tempo limitado" com data de encerramento fixa gerada via `localStorage` (primeira visita define a data; visitas seguintes leem a mesma data). Não usar countdown que reseta por cookie — prática sinalizada em auditorias de conta Meta.
- Bloco de preço + botão CTA → Hotmart com UTMs automáticos (`utm_source=meta&utm_medium=cpc&utm_campaign={slug_produto}`)
- Mobile-first, CSS inline, zero dependências externas

**Ações disponíveis:**
- Preview (abre em nova aba via `blob:` URL)
- Download HTML
- Deploy Vercel (chama `_deploy_to_vercel("jake-dr-lp", html)` — retorna URL pública)

**Backend:**
- `POST /api/dr/clonar-lp` — URL + contexto → fetch HTML → Claude gera LP adaptada. `max_tokens`: 8192
- `POST /api/dr/gerar-lp` — contexto → Claude gera LP do zero. `max_tokens`: 8192
- `POST /api/dr/deploy-lp` — HTML → chama `_deploy_to_vercel("jake-dr-lp", html)` → retorna URL

---

### Passo 3 — Criativos

**Objetivo:** Gerar criativos visuais com contexto DR pré-preenchido.

**Implementação:** Sem novo backend. O botão "Ir para Criativos" no Passo 3:
1. Chama `showPage("criativos")`
2. Lê `sessionStorage.getItem("dr_contexto")`
3. Concatena `nicho + ângulo + hook` em uma string de prompt
4. Escreve diretamente em `document.getElementById("cri-prompt").value`

Requer alteração mínima em `dr.js` — nenhuma mudança em `criativos.js`.

---

### Passo 4 — Quiz Roteiro

**Objetivo:** Gerar roteiro estruturado de quiz para uso em InLead ou ferramenta similar.

**Output gerado por Claude — formato Markdown estruturado:**
```
## Título do Quiz
"[Título chamativo]"

## Perguntas
### Pergunta 1: [texto]
- A) [opção]
- B) [opção]
- C) [opção]

[...]

## Perfis de Resultado
### Perfil A (respostas: 1A, 2B, 3A...)
**Resultado:** [texto personalizado]
**Transição para VSL:** "[frase de bridge para o vídeo]"

[...]
```

Botão "Copiar tudo". Output é Markdown — copy-paste manual no InLead. Sem HTML, sem backend complexo.

**Backend:** `POST /api/dr/quiz-roteiro`
- Input: contexto do Passo 1
- Output: string Markdown estruturada
- `max_tokens`: 2048

---

## Rotas Backend Resumidas

| Rota | Método | Função | max_tokens |
|------|--------|--------|-----------|
| `/api/dr/gerar-copy` | POST | Gera copy + script VSL + ângulos | 4096 |
| `/api/dr/clonar-lp` | POST | Busca URL, analisa HTML, gera LP adaptada | 8192 |
| `/api/dr/gerar-lp` | POST | Gera LP do zero via Claude | 8192 |
| `/api/dr/deploy-lp` | POST | Deploy HTML no Vercel | — |
| `/api/dr/quiz-roteiro` | POST | Gera roteiro de quiz em Markdown | 2048 |

`/api/generate-creative` — reutilizado sem alteração

---

## Ordem de Implementação

1. **Passo 1** — Copy + Script VSL (maior uso, menor dependência)
2. **Passo 2** — LP Generator + Cloner + Deploy
3. **Passo 4** — Quiz Roteiro (simples)
4. **Passo 3** — Criativos (só integração frontend)

---

## Decisões de Design

- **Sem banco de dados para sessões DR**: `sessionStorage` é suficiente, contexto não precisa persistir entre dias. Banner de aviso se contexto perdido em refresh.
- **Pixel ID persiste em localStorage**: mesmo pixel em todas as campanhas DR, não vale redigitar.
- **LP autocontida**: CSS inline, sem frameworks, zero dependências — carrega rápido, sem ponto de falha externo.
- **Fallback no cloner de LP com aviso explícito**: se fetch falhar, usuário vê mensagem clara antes de receber LP gerada do zero.
- **Timer estático por localStorage, não cookie reset**: countdown que reseta é dark pattern sinalizado em auditorias Meta.
- **Deploy via Vercel** (`_deploy_to_vercel()`): função já existente e parametrizada no Site Architect. `project_name = "jake-dr-lp"`.
- **Passo 3 via injeção direta no DOM**: concatena contexto DR e escreve em `#cri-prompt` após `showPage("criativos")`. Zero mudança em `criativos.js`.
- **Quiz como Markdown**: InLead é melhor ferramenta para quiz interativo; Jake OS gera o conteúdo estruturado, não a mecânica.
