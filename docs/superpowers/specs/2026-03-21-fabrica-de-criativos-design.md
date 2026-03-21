# Fábrica de Criativos v2 — Design Spec

**Data:** 2026-03-21
**Projeto:** Jake OS (Flask SPA, porta 5050)
**Contexto:** Gestor de tráfego pago que cria conteúdo para clientes (Meta Ads, Google Ads)

---

## Objetivo

Substituir a Fábrica de Criativos atual (`/api/generate-creative`) por uma versão completa com:
- Geração de imagem via Replicate (5 modelos)
- Geração de vídeo via Replicate (6 modelos, T2V e I2V)
- Engenharia de prompt automática com 5 especialistas via Claude
- Análise de imagem de referência para recriar estilos
- Histórico com pastas e deleção

Além disso, criar uma **Claude Code Skill global** (`fabrica-de-criativos`) com os 5 engenheiros de prompt especializados.

---

## Arquitetura

**Stack:** Python/Flask, psycopg2 (Neon PostgreSQL), Replicate API, Anthropic claude-sonnet-4-6, Vanilla JS (IIFE), CSS Glassmorphism (padrão Jake OS)

**Arquivos afetados:**

| Arquivo | Ação |
|---|---|
| `jake_desktop/app.py` | Adicionar 10 novas rotas `/api/criativos/*` |
| `jake_desktop/templates/dashboard.html` | Substituir seção page-criativos |
| `jake_desktop/static/js/criativos.js` | Criar — IIFE completo |
| `jake_desktop/static/css/criativos.css` | Criar — estilos da seção |
| `scripts/migrar_criativos.py` | Criar — migration one-shot |
| `~/.claude/skills/fabrica-de-criativos/SKILL.md` | Criar — skill global |

---

## Frontend — Jake OS

### Layout: Split View

Dois painéis lado a lado dentro de `#page-criativos`:

**Painel Esquerdo — Configuração:**

1. **Toggle Imagem / Vídeo** — adapta os modelos disponíveis e campos abaixo
2. **Selector de Modo do Prompt** — 5 cards clicáveis de especialistas:
   - 🎯 Anúncios
   - 🎨 Conteúdo Criativo
   - 🌀 Psicodélico
   - 👤 Pessoas Realistas
   - 🌆 Cena/Ambiente
3. **Campo de prompt simples** — textarea
4. **Painel Original vs Expandido** — aparece após expansão via Claude, editável, botão "↺ Regerar"
5. **Upload de imagem** (opcional) — com escolha explícita após upload:
   - "Usar como input de vídeo (I2V)"
   - "Analisar estilo e gerar prompt"
6. **Cards de modelos** — grid 2 colunas com badges:
   - Imagem: Flux 1.1 Pro, Flux Dev, Recraft V3, Ideogram V3 Turbo, Imagen 4
   - Vídeo T2V: Wan 2.2 T2V Fast, Wan 2.2 5B Fast, Hailuo 02 Fast, Seedance 1 Lite, Runway Gen-4 Turbo
   - Vídeo I2V: Wan 2.2 I2V Fast (só habilitado quando há imagem uploadada)
   - Badges: tipo (T2V/I2V), velocidade (⚡Rápido/◑Médio), custo ($/$$/$$$ )
7. **Botão Gerar** — dispara expansão de prompt (se não feita) + geração

**Painel Direito — Resultado:**

- Estado vazio: instrução "Configure e gere seu criativo"
- Após geração: preview de imagem (`<img>`) ou vídeo (`<video controls>`)
- Botões de ação:
  - Download
  - Enviar para Subir Anúncios — chama `window.JakeAnuncios.receberCriativo({ url, tipo })` que navega para a aba e pré-preenche o campo de upload criativo
  - Salvar no Histórico (abre selector de pasta)

**Aba Histórico** (toggle dentro da mesma seção):

- Grid de cards: thumbnail + modelo + modo + data
- Filtros: por pasta (dropdown) e por tipo (imagem/vídeo)
- Ações por card: Download | Mover de pasta | Deletar (com confirmação)
- Deletar pasta com criativos: modal de confirmação informando quantos criativos serão desvinculados. Confirmar → DELETE, cancelar → fechar modal

---

## Backend Flask — Rotas

> **Todas as rotas `/api/criativos/*` requerem `@login_required`.**

### Mapeamento de Modelos (slug Replicate)

| Nome amigável | Slug Replicate | Tipo |
|---|---|---|
| Flux 1.1 Pro | `black-forest-labs/flux-1.1-pro` | imagem |
| Flux Dev | `black-forest-labs/flux-dev` | imagem |
| Recraft V3 | `recraft-ai/recraft-v3` | imagem |
| Ideogram V3 Turbo | `ideogram-ai/ideogram-v3-turbo` | imagem |
| Imagen 4 | `google/imagen-4` | imagem |
| Wan 2.2 T2V Fast | `wavespeedai/wan-2.2-t2v-480p` | video T2V |
| Wan 2.2 5B Fast | `wavespeedai/wan-2.2-t2v-720p` | video T2V |
| Hailuo 02 Fast | `minimax/hailuo-02` | video T2V |
| Seedance 1 Lite | `bytedance/seedance-1-lite` | video T2V |
| Runway Gen-4 Turbo | `runwayml/gen4-turbo` | video T2V |
| Wan 2.2 I2V Fast | `wavespeedai/wan-2.2-i2v-480p` | video I2V |

### Upload de Imagem

**`POST /api/criativos/upload-imagem`** — multipart/form-data
```json
Request:  arquivo (file field)
Response: { "url": "string", "base64": "string", "mime_type": "string", "ok": true }
```
Sobe a imagem para o Replicate via `/v1/files` e devolve tanto a URL (para I2V) quanto o base64 (para análise de referência via Claude). Armazenamento temporário no Replicate CDN.

### Prompt Engineering

**`POST /api/criativos/expandir-prompt`**
```json
Request:  { "prompt": "string", "modo": "anuncios|criativo|psicodelico|pessoas|cena", "tipo": "imagem|video" }
Response: { "prompt_expandido": "string" }
```
Claude usa o prompt do especialista correspondente ao modo. O `tipo` influencia o vocabulário (vídeo privilegia movimento, câmera, duração).

**`POST /api/criativos/analisar-referencia`**
```json
Request:  { "imagem_base64": "string", "mime_type": "string" }
Response: { "prompt_sugerido": "string", "modo_sugerido": "anuncios|criativo|psicodelico|pessoas|cena" }
```
Claude analisa a imagem e responde com JSON forçado dentro do enum de modos. Backend valida `modo_sugerido` — fallback para `"criativo"` se valor fora do enum.

### Geração de Imagem

**`POST /api/criativos/gerar-imagem`**
```json
Request:  { "prompt_expandido": "string", "modelo": "flux-1.1-pro|flux-dev|recraft-v3|ideogram-v3-turbo|imagen-4" }
Response: { "url": "string", "ok": true }
```
Polling síncrono no Replicate (imagens são rápidas, < 30s).

### Geração de Vídeo — Assíncrona

Vídeos levam até 3 minutos. Fluxo em dois passos para não segurar o worker Flask:

**`POST /api/criativos/gerar-video`** — inicia a geração
```json
Request:  { "prompt_expandido": "string", "modelo": "string", "imagem_url": "string|null" }
Response: { "prediction_id": "string", "ok": true }
```
`imagem_url` obrigatório para modelos I2V. Backend valida modelo vs presença de `imagem_url`.

**`GET /api/criativos/status/<prediction_id>`** — frontend faz polling a cada 3s
```json
Response: { "status": "starting|processing|succeeded|failed", "url": "string|null", "error": "string|null" }
```

### Histórico

**`GET /api/criativos/historico`** — query params: `?folder_id=&tipo=&page=1&limit=20`
```json
Response: { "items": [...], "total": int, "page": int, "pages": int }
```

**`POST /api/criativos/historico`**
```json
{ "tipo", "modo", "modelo", "prompt_original", "prompt_expandido", "url_resultado", "folder_id" }
```

**`DELETE /api/criativos/historico/<id>`**

**`PATCH /api/criativos/historico/<id>/pasta`**
```json
{ "folder_id": int|null }
```

### Pastas

**`GET /api/criativos/pastas`**

**`POST /api/criativos/pastas`** — `{ "nome": "string" }`

**`DELETE /api/criativos/pastas/<id>`** — criativos ficam com `folder_id = NULL` (ON DELETE SET NULL)

---

## Banco de Dados

```sql
CREATE TABLE creative_folders (
    id        SERIAL PRIMARY KEY,
    nome      VARCHAR(100) NOT NULL,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE creative_history (
    id               SERIAL PRIMARY KEY,
    tipo             VARCHAR(10)  NOT NULL CHECK (tipo IN ('imagem','video')),
    modo             VARCHAR(20)  NOT NULL,
    modelo           VARCHAR(50)  NOT NULL,
    prompt_original  TEXT         NOT NULL,
    prompt_expandido TEXT         NOT NULL,
    url_resultado    TEXT         NOT NULL,
    folder_id        INTEGER      REFERENCES creative_folders(id) ON DELETE SET NULL,
    criado_em        TIMESTAMP    DEFAULT NOW()
);

-- Índices para performance do histórico
CREATE INDEX idx_creative_history_tipo ON creative_history(tipo);
CREATE INDEX idx_creative_history_folder ON creative_history(folder_id);
CREATE INDEX idx_creative_history_criado ON creative_history(criado_em DESC);
```

---

## Claude Code Skill — `fabrica-de-criativos`

**Localização:** `~/.claude/skills/fabrica-de-criativos/SKILL.md`
**Também referenciada em:** `/root/CLAUDE.md`

### Estrutura da Skill

A skill define 5 engenheiros de prompt especializados. Cada especialista tem:
- Vocabulário técnico do estilo
- Estrutura canônica do prompt expandido (ordem dos elementos)
- O que evitar
- Exemplo: prompt simples → expandido

### Os 5 Especialistas

**🎯 Anúncios**
- Foco: conversão, produto destacado, apelo comercial, CTA visual
- Vocabulário: studio lighting, rim light, commercial photography, clean background, trust-inspiring, shallow depth of field
- Exemplo: "clínica odontológica sorriso" → "Professional dental clinic advertisement, confident woman smiling with perfect white teeth, soft studio lighting with rim light, shallow depth of field, Canon EOS R5 85mm f/1.4, commercial photography style, clean white background, warm color grading, trust-inspiring composition, Meta Ads format"

**🎨 Conteúdo Criativo**
- Foco: arte conceitual, storytelling visual, impacto estético
- Vocabulário: conceptual art, bold composition, editorial style, dynamic lighting, color contrast, visual narrative
- Exemplo: "mulher e natureza" → "Editorial conceptual art, woman merging with lush tropical nature, bold color contrast, dynamic composition, National Geographic style, golden hour lighting, environmental storytelling, high contrast shadows"

**🌀 Psicodélico**
- Foco: surrealismo, cores vibrantes, geometria, dimensões alternativas
- Vocabulário: psychedelic, fractal geometry, neon colors, surrealist, kaleidoscope, liquid geometry, cosmic, DMT-inspired
- Exemplo: "portal dimensional" → "Psychedelic dimensional portal, fractal geometry spiraling into infinite cosmos, neon cyan and magenta hues, liquid geometry, DMT-inspired visuals, ultra-detailed, 8K resolution, surrealist dreamscape, kaleidoscope symmetry"

**👤 Pessoas Realistas**
- Foco: fotorrealismo humano, expressão, textura de pele, luz natural
- Vocabulário: hyperrealistic, skin texture, subsurface scattering, natural light, bokeh, candid, 85mm portrait, Rembrandt lighting
- Exemplo: "homem de negócios confiante" → "Hyperrealistic portrait, confident businessman mid-40s, natural window light with Rembrandt lighting, skin texture with subsurface scattering, Canon EOS R5 85mm f/1.2, shallow depth of field, professional attire, authentic expression, photojournalism style"

**🌆 Cena/Ambiente**
- Foco: composição de cenário, profundidade, atmosfera, arquitetura ou natureza
- Vocabulário: wide angle, leading lines, atmospheric perspective, golden hour, volumetric light, establishing shot, rule of thirds
- Exemplo: "cidade no pôr do sol" → "Cinematic cityscape at golden hour, dramatic volumetric light rays, leading lines from architecture, atmospheric haze, wide angle 16mm, rule of thirds composition, long exposure effect, urban landscape photography, award-winning composition"

### Model IDs Replicate

**Imagem:**
| Nome | Model ID | Melhor para |
|---|---|---|
| Flux 1.1 Pro | `black-forest-labs/flux-1.1-pro` | Anúncios, Pessoas (custo-benefício) |
| Flux Dev | `black-forest-labs/flux-dev` | Criativo, qualidade alta |
| Recraft V3 | `recraft-ai/recraft-v3` | Design vetorial, UI |
| Ideogram V3 Turbo | `ideogram-ai/ideogram-v3-turbo` | Texto em imagem, logos |
| Imagen 4 | `google/imagen-4` | Fotorrealismo máximo |

**Vídeo:**
| Nome | Model ID | Tipo | Velocidade | Custo |
|---|---|---|---|---|
| Wan 2.2 T2V Fast | `wavespeedai/wan-2.2-t2v-480p` | T2V | ⚡ Rápido | $ |
| Wan 2.2 5B Fast | `wavespeedai/wan-2.2-t2v-720p` | T2V | ◑ Médio | $$ |
| Wan 2.2 I2V Fast | `wavespeedai/wan-2.2-i2v-480p` | I2V | ⚡ Rápido | $ |
| Hailuo 02 Fast | `minimax/hailuo-02` | T2V | ⚡ Rápido | $$ |
| Seedance 1 Lite | `bytedance/seedance-1-lite` | T2V | ◑ Médio | $$ |
| Runway Gen-4 Turbo | `runwayml/gen4-turbo` | T2V | ⚡ Rápido | $$$ |

---

## Critérios de Sucesso

- [ ] Gerar imagem com qualquer modelo em menos de 30 segundos (exceto Imagen 4)
- [ ] Gerar vídeo T2V em menos de 3 minutos
- [ ] Prompt expandido aproveitável em pelo menos 70% dos casos
- [ ] Análise de referência devolve prompt que reproduz o estilo identificável
- [ ] Histórico carrega em menos de 1 segundo (paginação se > 50 itens)
- [ ] I2V só habilitado quando imagem está uploadada (validação frontend + backend)
- [ ] Integração com Subir Anúncios funcional (imagem enviada diretamente)
