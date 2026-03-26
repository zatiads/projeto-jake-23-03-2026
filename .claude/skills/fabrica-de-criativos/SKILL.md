---
name: fabrica-de-criativos
description: Use when generating AI images or videos for ad creatives, needing prompt engineering for Replicate models, or working on the Jake OS Fábrica de Criativos feature. Provides 5 specialized prompt engineers (Anúncios, Criativo, Psicodélico, Pessoas, Cena) and Replicate model reference.
---

# Fábrica de Criativos — Prompt Engineering Skill

## Overview

5 engenheiros de prompt especializados para geração de criativos com IA. Cada especialista expande um prompt simples em português para um prompt técnico profissional em inglês, otimizado para o tipo de criativo.

**Regra universal:** Sempre gerar o prompt expandido em **inglês**. Manter o prompt expandido entre 50–120 palavras. Incluir sempre: sujeito principal, iluminação, estilo fotográfico/artístico, câmera/lente (quando aplicável), mood/atmosfera.

---

## Os 5 Especialistas

### 🎯 Anúncios
**Quando usar:** Criativos para Meta Ads, Google Ads, produtos, serviços, clínicas, negócios locais.

**Estrutura canônica:**
`[produto/serviço] advertisement, [sujeito + ação], [iluminação: studio/rim/softbox], [câmera: Canon/Sony 85mm f/1.4], commercial photography style, [background: clean/white/gradient], [color grading: warm/cool/neutral], [emoção: trust/confident/welcoming], Meta Ads format`

**Vocabulário:** studio lighting, rim light, commercial photography, shallow depth of field, trust-inspiring, clean background, product hero shot, brand colors

**Evitar:** artsy, experimental, surreal, cluttered backgrounds, dark moody tones

**Exemplo:**
- Simples: "clínica odontológica sorriso"
- Expandido: "Professional dental clinic advertisement, confident woman smiling with perfect white teeth, soft studio lighting with rim light, shallow depth of field, Canon EOS R5 85mm f/1.4, commercial photography style, clean white background, warm color grading, trust-inspiring composition, Meta Ads format"

---

### 🎨 Conteúdo Criativo
**Quando usar:** Arte conceitual, posts de redes sociais com apelo estético, storytelling visual, marcas de moda/lifestyle.

**Estrutura canônica:**
`[conceito] conceptual art, [sujeito + contexto], [composição: bold/dynamic/layered], [estilo: editorial/National Geographic/fine art], [iluminação: golden hour/dramatic/cinematic], [mood: narrative/emotional/striking], [técnica: high contrast/color grading]`

**Vocabulário:** conceptual art, editorial style, bold composition, visual narrative, dynamic lighting, color contrast, fine art photography, storytelling

**Evitar:** genérico, stock photo look, plain backgrounds sem intenção

**Exemplo:**
- Simples: "mulher e natureza"
- Expandido: "Editorial conceptual art, woman merging with lush tropical nature, bold color contrast, dynamic composition, National Geographic style, golden hour lighting, environmental storytelling, high contrast shadows, award-winning photography"

---

### 🌀 Psicodélico
**Quando usar:** Arte generativa, covers musicais, conteúdo alternativo, eventos, marcas disruptivas.

**Estrutura canônica:**
`psychedelic [tema], [geometria: fractal/kaleidoscope/spiral], [paleta: neon/vibrant/cosmic], [referência: DMT-inspired/surrealist/dreamscape], ultra-detailed, 8K resolution, [técnica: liquid geometry/morphing/infinite recursion]`

**Vocabulário:** psychedelic, fractal geometry, neon colors, surrealist, kaleidoscope, liquid geometry, cosmic, DMT-inspired, interdimensional, crystalline

**Evitar:** fotorrealismo, tons apagados, composição convencional

**Exemplo:**
- Simples: "portal dimensional"
- Expandido: "Psychedelic dimensional portal, fractal geometry spiraling into infinite cosmos, neon cyan and magenta hues, liquid geometry morphing, DMT-inspired visuals, ultra-detailed, 8K resolution, surrealist dreamscape, kaleidoscope symmetry, cosmic interdimensional gateway"

---

### 👤 Pessoas Realistas
**Quando usar:** Retratos, personas de cliente, modelos para anúncios, conteúdo com pessoas.

**Estrutura canônica:**
`Hyperrealistic portrait, [sujeito: idade/gênero/etnia/expressão], [iluminação: Rembrandt/natural window/golden hour], skin texture with subsurface scattering, [câmera: Canon EOS R5 85mm f/1.2], shallow depth of field, [contexto/roupa], [mood: candid/professional/authentic]`

**Vocabulário:** hyperrealistic, skin texture, subsurface scattering, natural light, bokeh, candid, Rembrandt lighting, photojournalism, authentic expression, pore detail

**Evitar:** AI-looking skin, plastic textures, symmetria perfeita demais, olhos artificiais

**Exemplo:**
- Simples: "homem de negócios confiante"
- Expandido: "Hyperrealistic portrait, confident businessman mid-40s, natural window light with Rembrandt lighting, skin texture with subsurface scattering, Canon EOS R5 85mm f/1.2, shallow depth of field, professional business attire, authentic expression, photojournalism style, 8K resolution"

---

### 🌆 Cena/Ambiente
**Quando usar:** Paisagens urbanas, natureza, arquitetura, cenários para fundo de anúncios.

**Estrutura canônica:**
`Cinematic [tipo de cena], [horário/luz: golden hour/blue hour/overcast], [técnica de composição: leading lines/rule of thirds/symmetry], [efeito: volumetric light/atmospheric haze/long exposure], wide angle [mm], [referência: award-winning landscape/National Geographic], [mood: epic/serene/dramatic]`

**Vocabulário:** wide angle, leading lines, atmospheric perspective, golden hour, volumetric light, establishing shot, rule of thirds, long exposure, atmospheric haze

**Evitar:** composições planas, luz plana sem drama, perspectiva de smartphone

**Exemplo:**
- Simples: "cidade no pôr do sol"
- Expandido: "Cinematic cityscape at golden hour, dramatic volumetric light rays, leading lines from architecture into infinite horizon, atmospheric haze, wide angle 16mm, rule of thirds composition, long exposure light trails, urban landscape photography, award-winning composition, National Geographic style"

---

## Replicate — Model IDs e Parâmetros

### Imagem

| Key | Slug | Melhor para | aspect_ratio padrão |
|---|---|---|---|
| `flux-1.1-pro` | `black-forest-labs/flux-1.1-pro` | Anúncios, Pessoas | 4:5 |
| `flux-dev` | `black-forest-labs/flux-dev` | Criativo, qualidade alta | 4:5 |
| `recraft-v3` | `recraft-ai/recraft-v3` | Design, UI, vetorial | 1:1 |
| `ideogram-v3-turbo` | `ideogram-ai/ideogram-v3-turbo` | Texto em imagem, logos | 1:1 |
| `imagen-4` | `google/imagen-4` | Fotorrealismo máximo | 4:5 |

**Endpoint padrão imagem:** `POST https://api.replicate.com/v1/models/{slug}/predictions`
**Headers:** `Authorization: Bearer {token}`, `Prefer: wait=60`

### Vídeo

| Key | Slug | Tipo | Duração típica | Custo |
|---|---|---|---|---|
| `wan-t2v-fast` | `wavespeedai/wan-2.2-t2v-480p` | T2V | ~30s geração | $ |
| `wan-5b-fast` | `wavespeedai/wan-2.2-t2v-720p` | T2V | ~60s geração | $$ |
| `hailuo-02` | `minimax/hailuo-02` | T2V | ~45s geração | $$ |
| `seedance-lite` | `bytedance/seedance-1-lite` | T2V | ~60s geração | $$ |
| `runway-gen4` | `runwayml/gen4-turbo` | T2V | ~30s geração | $$$ |
| `wan-i2v-fast` | `wavespeedai/wan-2.2-i2v-480p` | I2V | ~45s geração | $ |

**Endpoint vídeo:** `POST https://api.replicate.com/v1/models/{slug}/predictions` (sem `Prefer: wait`)
**Polling:** `GET https://api.replicate.com/v1/predictions/{id}` a cada 3s
