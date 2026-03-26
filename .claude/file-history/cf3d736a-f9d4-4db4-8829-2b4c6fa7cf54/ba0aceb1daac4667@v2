# Fábrica de Criativos v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir a Fábrica de Criativos atual por versão completa com geração de imagem/vídeo (11 modelos Replicate), 5 especialistas de prompt via Claude, upload de referência, histórico paginado com pastas, e skill global do Claude Code.

**Architecture:** Backend Flask com 13 novas rotas em `app.py`; geração de vídeo assíncrona com polling via `GET /status/<prediction_id>`; frontend Split View (config esquerda / resultado direita) em IIFE Vanilla JS; banco Neon com 2 novas tabelas; skill Markdown com 5 engenheiros de prompt especializados.

**Tech Stack:** Python/Flask, psycopg2 (Neon PostgreSQL), Replicate REST API (sem SDK), Anthropic claude-sonnet-4-6, Vanilla JS (IIFE), CSS Glassmorphism (padrão Jake OS)

**Spec:** `docs/superpowers/specs/2026-03-21-fabrica-de-criativos-design.md`

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `scripts/migrar_criativos.py` | Criar | Migration one-shot: tabelas + índices |
| `jake_desktop/app.py` | Modificar | 13 novas rotas `/api/criativos/*` (upload-imagem, expandir-prompt, analisar-referencia, gerar-imagem, gerar-video, status/\<id\>, historico GET, historico POST, historico/\<id\> DELETE, historico/\<id\>/pasta PATCH, pastas GET, pastas POST, pastas/\<id\> DELETE) |
| `jake_desktop/templates/dashboard.html` | Modificar | Substituir seção `page-criativos` (linhas 690–840) + link CSS/JS |
| `jake_desktop/static/js/criativos.js` | Criar | IIFE completo: layout, modos, upload, geração, histórico |
| `jake_desktop/static/css/criativos.css` | Criar | Estilos da seção |
| `~/.claude/skills/fabrica-de-criativos/SKILL.md` | Criar | Skill global com 5 especialistas de prompt |

---

## Mapeamento de Modelos (referência para toda a implementação)

| Key (frontend/backend) | Slug Replicate | Tipo |
|---|---|---|
| `flux-1.1-pro` | `black-forest-labs/flux-1.1-pro` | imagem |
| `flux-dev` | `black-forest-labs/flux-dev` | imagem |
| `recraft-v3` | `recraft-ai/recraft-v3` | imagem |
| `ideogram-v3-turbo` | `ideogram-ai/ideogram-v3-turbo` | imagem |
| `imagen-4` | `google/imagen-4` | imagem |
| `wan-t2v-fast` | `wavespeedai/wan-2.2-t2v-480p` | video T2V |
| `wan-5b-fast` | `wavespeedai/wan-2.2-t2v-720p` | video T2V |
| `hailuo-02` | `minimax/hailuo-02` | video T2V |
| `seedance-lite` | `bytedance/seedance-1-lite` | video T2V |
| `runway-gen4` | `runwayml/gen4-turbo` | video T2V |
| `wan-i2v-fast` | `wavespeedai/wan-2.2-i2v-480p` | video I2V |

---

## Task 1: Claude Code Skill — 5 Especialistas de Prompt

**Files:**
- Create: `~/.claude/skills/fabrica-de-criativos/SKILL.md`

- [ ] **Step 1: Criar diretório e arquivo da skill**

```bash
mkdir -p ~/.claude/skills/fabrica-de-criativos
```

Criar `~/.claude/skills/fabrica-de-criativos/SKILL.md`:

```markdown
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

**Evitar:** AI-looking skin, plastic textures, symmetry perfeita demais, olhos artificiais

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
```

- [ ] **Step 2: Verificar criação (a skill está fora do repo git, não é commitada)**

```bash
head -5 ~/.claude/skills/fabrica-de-criativos/SKILL.md
```

Expected: frontmatter YAML visível (`name:`, `description:`).

> **Nota:** `~/.claude/skills/` está fora do diretório do repositório (`/root`). Não usar `git add` neste path — causará erro "pathspec outside repository". A skill fica apenas em disco, disponível localmente para o Claude Code.

---

## Task 2: Migration — Tabelas no Neon

**Files:**
- Create: `scripts/migrar_criativos.py`

- [ ] **Step 1: Criar script de migração**

```python
#!/usr/bin/env python3
"""
Script one-shot: cria tabelas creative_folders e creative_history no Neon.
Executar: PYTHONPATH=/root python3 scripts/migrar_criativos.py
"""
import sys
sys.path.insert(0, '/root')
from core.db import get_conn

SQL = """
CREATE TABLE IF NOT EXISTS creative_folders (
    id        SERIAL PRIMARY KEY,
    nome      VARCHAR(100) NOT NULL,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS creative_history (
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

CREATE INDEX IF NOT EXISTS idx_creative_history_tipo    ON creative_history(tipo);
CREATE INDEX IF NOT EXISTS idx_creative_history_folder  ON creative_history(folder_id);
CREATE INDEX IF NOT EXISTS idx_creative_history_criado  ON creative_history(criado_em DESC);
"""

if __name__ == "__main__":
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(SQL)
        conn.commit()
        print("✓ Tabelas creative_folders e creative_history criadas com sucesso.")
    except Exception as e:
        print(f"✕ Erro: {e}")
        sys.exit(1)
    finally:
        conn.close()
```

- [ ] **Step 2: Executar migração**

```bash
PYTHONPATH=/root /root/venv/bin/python3 /root/scripts/migrar_criativos.py
```

Expected: `✓ Tabelas creative_folders e creative_history criadas com sucesso.`

- [ ] **Step 3: Verificar tabelas**

```bash
PYTHONPATH=/root /root/venv/bin/python3 -c "
from core.db import get_conn
conn = get_conn()
cur = conn.cursor()
cur.execute(\"SELECT table_name FROM information_schema.tables WHERE table_name IN ('creative_folders','creative_history')\")
print(cur.fetchall())
conn.close()
"
```

Expected: `[('creative_folders',), ('creative_history',)]`

- [ ] **Step 4: Commit**

```bash
git add scripts/migrar_criativos.py
git commit -m "feat: migration — tabelas creative_folders e creative_history"
```

---

## Task 3: Backend — Upload de Imagem e Prompt Engineering

**Files:**
- Modify: `jake_desktop/app.py`

Adicionar as constantes e funções auxiliares antes do bloco `if __name__ == "__main__":`.

> **Helpers já existentes em `app.py` (não redefinir):**
> - `_get_db()` — linha 42. Abre conexão Neon com `RealDictCursor`, portanto `cur.fetchone()["id"]` funciona.
> - `_anthropic_client()` — linha 316. Retorna cliente Anthropic ou `None` se sem chave.

- [ ] **Step 1: Adicionar constantes de modelos e helpers no app.py**

Localizar a linha `def _open_browser_delayed` e inserir **antes** dela:

```python
# ══════════════════════════════════════════════════════════════════════════
#  FÁBRICA DE CRIATIVOS v2
# ══════════════════════════════════════════════════════════════════════════
import math as _math
import time as _t

_CRIATIVOS_MODOS = {"anuncios", "criativo", "psicodelico", "pessoas", "cena"}

_CRIATIVOS_MODELOS_IMAGEM = {
    "flux-1.1-pro":     "black-forest-labs/flux-1.1-pro",
    "flux-dev":         "black-forest-labs/flux-dev",
    "recraft-v3":       "recraft-ai/recraft-v3",
    "ideogram-v3-turbo":"ideogram-ai/ideogram-v3-turbo",
    "imagen-4":         "google/imagen-4",
}

_CRIATIVOS_MODELOS_VIDEO = {
    "wan-t2v-fast":  ("wavespeedai/wan-2.2-t2v-480p", "t2v"),
    "wan-5b-fast":   ("wavespeedai/wan-2.2-t2v-720p", "t2v"),
    "hailuo-02":     ("minimax/hailuo-02",             "t2v"),
    "seedance-lite": ("bytedance/seedance-1-lite",     "t2v"),
    "runway-gen4":   ("runwayml/gen4-turbo",           "t2v"),
    "wan-i2v-fast":  ("wavespeedai/wan-2.2-i2v-480p", "i2v"),
}

_CRIATIVOS_SYSTEM_PROMPTS = {
    "anuncios": (
        "You are an expert commercial photographer and ad creative director specializing in Meta Ads and Google Ads. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: studio lighting, commercial photography style, trust-inspiring composition, clean backgrounds, "
        "specific camera/lens (Canon EOS R5, 85mm f/1.4), warm color grading. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "criativo": (
        "You are an expert creative director and editorial photographer. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: conceptual art, bold composition, editorial/National Geographic style, dynamic lighting, "
        "color contrast, visual narrative, storytelling. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "psicodelico": (
        "You are an expert AI artist specializing in psychedelic and surrealist visual art. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: fractal geometry, neon/vibrant colors, DMT-inspired visuals, kaleidoscope patterns, "
        "liquid geometry, cosmic themes, ultra-detailed, 8K resolution, surrealist dreamscape. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "pessoas": (
        "You are an expert portrait and fashion photographer. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: hyperrealistic skin texture, subsurface scattering, Rembrandt or natural window lighting, "
        "Canon EOS R5 85mm f/1.2, shallow depth of field, authentic candid expressions, photojournalism style. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "cena": (
        "You are an expert landscape and architectural photographer. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: cinematic wide angle (16mm), leading lines, volumetric light, golden hour, atmospheric haze, "
        "rule of thirds, long exposure, National Geographic / award-winning landscape style. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
}

_REPLICATE_BASE = "https://api.replicate.com/v1"


def _replicate_headers():
    token = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN não configurado no .env")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
```

- [ ] **Step 2: Adicionar rota de upload de imagem**

Logo após as constantes acima:

```python
@app.route("/api/criativos/upload-imagem", methods=["POST"])
@login_required
def criativos_upload_imagem():
    if "arquivo" not in request.files:
        return jsonify({"error": "Campo 'arquivo' ausente"}), 400
    arquivo = request.files["arquivo"]
    file_bytes = arquivo.read()
    mime = arquivo.content_type or "image/jpeg"
    # base64 para análise via Claude
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    # Upload para Replicate Files API para uso como URL em I2V
    try:
        headers = _replicate_headers()
        headers.pop("Content-Type")  # multipart não usa Content-Type JSON
        resp = requests.post(
            f"{_REPLICATE_BASE}/files",
            headers={"Authorization": headers["Authorization"]},
            files={"content": (arquivo.filename or "upload", file_bytes, mime)},
            timeout=30,
        )
        if not resp.ok:
            return jsonify({"error": f"Replicate upload: {resp.text[:200]}"}), 500
        url = resp.json().get("urls", {}).get("get") or resp.json().get("url", "")
        return jsonify({"url": url, "base64": b64, "mime_type": mime, "ok": True})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 3: Adicionar rota de expandir prompt**

```python
@app.route("/api/criativos/expandir-prompt", methods=["POST"])
@login_required
def criativos_expandir_prompt():
    d = request.get_json() or {}
    prompt = (d.get("prompt") or "").strip()
    modo   = d.get("modo", "criativo")
    tipo   = d.get("tipo", "imagem")
    if not prompt:
        return jsonify({"error": "Campo 'prompt' obrigatório"}), 400
    if modo not in _CRIATIVOS_MODOS:
        return jsonify({"error": f"modo inválido. Válidos: {list(_CRIATIVOS_MODOS)}"}), 400

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    system = _CRIATIVOS_SYSTEM_PROMPTS[modo]
    tipo_hint = " Optimize for motion, camera movement, and temporal consistency." if tipo == "video" else ""
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=system + tipo_hint,
            messages=[{"role": "user", "content": f"Expand this prompt: {prompt}"}],
        )
        return jsonify({"prompt_expandido": msg.content[0].text.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 4: Adicionar rota de análise de referência**

```python
@app.route("/api/criativos/analisar-referencia", methods=["POST"])
@login_required
def criativos_analisar_referencia():
    d = request.get_json() or {}
    b64  = d.get("imagem_base64", "")
    mime = d.get("mime_type", "image/jpeg")
    if not b64:
        return jsonify({"error": "imagem_base64 obrigatório"}), 400

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    system = (
        "You are an expert visual analyst and prompt engineer. "
        "Analyze the image and return ONLY valid JSON with two fields: "
        "'prompt_sugerido' (English prompt 50-120 words to recreate this visual style) and "
        "'modo_sugerido' (one of: anuncios, criativo, psicodelico, pessoas, cena). "
        "No markdown, no explanation, just the JSON object."
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text",  "text": "Analyze this image and return the JSON."},
            ]}],
        )
        raw = msg.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json\n"):
                raw = raw[5:]
        result = json.loads(raw)
        # Validar modo_sugerido
        if result.get("modo_sugerido") not in _CRIATIVOS_MODOS:
            result["modo_sugerido"] = "criativo"
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({"error": "IA retornou formato inválido"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 5: Verificar sintaxe**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python3 -c "import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: rotas criativos — upload-imagem, expandir-prompt, analisar-referencia"
```

---

## Task 4: Backend — Geração de Imagem

**Files:**
- Modify: `jake_desktop/app.py`

- [ ] **Step 1: Adicionar rota de geração de imagem**

```python
@app.route("/api/criativos/gerar-imagem", methods=["POST"])
@login_required
def criativos_gerar_imagem():
    d = request.get_json() or {}
    prompt  = (d.get("prompt_expandido") or "").strip()
    modelo  = d.get("modelo", "flux-1.1-pro")
    if not prompt:
        return jsonify({"error": "prompt_expandido obrigatório"}), 400
    if modelo not in _CRIATIVOS_MODELOS_IMAGEM:
        return jsonify({"error": f"modelo inválido. Válidos: {list(_CRIATIVOS_MODELOS_IMAGEM)}"}), 400

    slug = _CRIATIVOS_MODELOS_IMAGEM[modelo]
    try:
        headers = _replicate_headers()
        headers["Prefer"] = "wait=60"
        resp = requests.post(
            f"{_REPLICATE_BASE}/models/{slug}/predictions",
            headers=headers,
            json={"input": {"prompt": prompt, "aspect_ratio": "4:5",
                            "output_format": "webp", "output_quality": 90}},
            timeout=90,
        )
        if not resp.ok:
            return jsonify({"error": f"Replicate {resp.status_code}: {resp.text[:300]}"}), 500
        pred = resp.json()
        # Caminho síncrono (Prefer: wait)
        if pred.get("status") == "succeeded":
            out = pred.get("output")
            url = out[0] if isinstance(out, list) else out
            return jsonify({"url": url, "ok": True})
        # Fallback polling (raro) — _t já importado no nível do módulo em Task 3
        get_url = (pred.get("urls") or {}).get("get", "")
        hdrs = {"Authorization": headers["Authorization"]}
        for _ in range(20):
            _t.sleep(3)
            p = requests.get(get_url, headers=hdrs, timeout=15).json()
            if p.get("status") == "succeeded":
                out = p.get("output")
                return jsonify({"url": (out[0] if isinstance(out, list) else out), "ok": True})
            if p.get("status") == "failed":
                return jsonify({"error": p.get("error", "Geração falhou")}), 500
        return jsonify({"error": "Timeout na geração de imagem"}), 500
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 2: Verificar sintaxe**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python3 -c "import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: rota criativos/gerar-imagem — 5 modelos Replicate com polling síncrono"
```

---

## Task 5: Backend — Geração de Vídeo (assíncrona)

**Files:**
- Modify: `jake_desktop/app.py`

- [ ] **Step 1: Adicionar rota de geração de vídeo (inicia)**

```python
@app.route("/api/criativos/gerar-video", methods=["POST"])
@login_required
def criativos_gerar_video():
    d = request.get_json() or {}
    prompt     = (d.get("prompt_expandido") or "").strip()
    modelo     = d.get("modelo", "wan-t2v-fast")
    imagem_url = d.get("imagem_url")
    if not prompt:
        return jsonify({"error": "prompt_expandido obrigatório"}), 400
    if modelo not in _CRIATIVOS_MODELOS_VIDEO:
        return jsonify({"error": f"modelo inválido. Válidos: {list(_CRIATIVOS_MODELOS_VIDEO)}"}), 400

    slug, tipo = _CRIATIVOS_MODELOS_VIDEO[modelo]
    if tipo == "i2v" and not imagem_url:
        return jsonify({"error": "imagem_url obrigatório para modelos I2V"}), 400

    input_payload = {"prompt": prompt}
    if tipo == "i2v":
        input_payload["image"] = imagem_url

    try:
        headers = _replicate_headers()
        resp = requests.post(
            f"{_REPLICATE_BASE}/models/{slug}/predictions",
            headers=headers,
            json={"input": input_payload},
            timeout=30,
        )
        if not resp.ok:
            return jsonify({"error": f"Replicate {resp.status_code}: {resp.text[:300]}"}), 500
        pred = resp.json()
        return jsonify({"prediction_id": pred.get("id"), "ok": True})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 2: Adicionar rota de status (polling do frontend)**

```python
@app.route("/api/criativos/status/<prediction_id>")
@login_required
def criativos_status(prediction_id):
    try:
        headers = _replicate_headers()
        resp = requests.get(
            f"{_REPLICATE_BASE}/predictions/{prediction_id}",
            headers={"Authorization": headers["Authorization"]},
            timeout=15,
        )
        if not resp.ok:
            return jsonify({"status": "failed", "error": resp.text[:200]}), 500
        pred = resp.json()
        status = pred.get("status", "starting")
        url = None
        if status == "succeeded":
            out = pred.get("output")
            url = out[0] if isinstance(out, list) else out
        return jsonify({"status": status, "url": url, "error": pred.get("error")})
    except RuntimeError as e:
        return jsonify({"status": "failed", "error": str(e)}), 500
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 500
```

- [ ] **Step 3: Verificar sintaxe**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python3 -c "import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Verificar que todas as rotas existem**

```bash
fuser -k 5050/tcp 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/jake_desktop/venv/bin/python app.py > /tmp/jake_flask.log 2>&1 &
sleep 4 && for rota in "/api/criativos/upload-imagem" "/api/criativos/expandir-prompt" "/api/criativos/gerar-imagem" "/api/criativos/gerar-video" "/api/criativos/status/test"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5050$rota")
  echo "$rota → $code"
done
```

Expected: upload=`405`, expandir=`405`, gerar-imagem=`405`, gerar-video=`405`, status=`302` (todos protegidos ou método correto).

- [ ] **Step 5: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: rotas criativos — gerar-video (assíncrono) e status/<prediction_id>"
```

---

## Task 6: Backend — Histórico e Pastas

**Files:**
- Modify: `jake_desktop/app.py`

- [ ] **Step 1: Adicionar rotas de pastas**

```python
@app.route("/api/criativos/pastas", methods=["GET"])
@login_required
def criativos_listar_pastas():
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute("SELECT id, nome, criado_em FROM creative_folders ORDER BY nome")
        rows = cur.fetchall(); conn.close()
        return jsonify({"pastas": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/criativos/pastas", methods=["POST"])
@login_required
def criativos_criar_pasta():
    d = request.get_json() or {}
    nome = (d.get("nome") or "").strip()
    if not nome:
        return jsonify({"error": "nome obrigatório"}), 400
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO creative_folders (nome) VALUES (%s) RETURNING id", (nome,))
        novo_id = cur.fetchone()["id"]; conn.commit(); conn.close()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/criativos/pastas/<int:pid>", methods=["DELETE"])
@login_required
def criativos_deletar_pasta(pid):
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as n FROM creative_history WHERE folder_id = %s", (pid,))
        count = cur.fetchone()["n"]
        cur.execute("DELETE FROM creative_folders WHERE id = %s", (pid,))
        conn.commit(); conn.close()
        return jsonify({"ok": True, "criativos_desvinculados": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 2: Adicionar rotas de histórico**

```python
@app.route("/api/criativos/historico", methods=["GET"])
@login_required
def criativos_listar_historico():
    folder_id = request.args.get("folder_id")
    tipo      = request.args.get("tipo")
    page      = max(1, int(request.args.get("page", 1)))
    limit     = min(50, max(1, int(request.args.get("limit", 20))))
    offset    = (page - 1) * limit
    where, params = [], []
    if folder_id:
        where.append("folder_id = %s"); params.append(int(folder_id))
    if tipo in ("imagem", "video"):
        where.append("tipo = %s"); params.append(tipo)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as total FROM creative_history {where_sql}", params)
        total = cur.fetchone()["total"]
        cur.execute(
            f"SELECT id, tipo, modo, modelo, prompt_original, prompt_expandido, url_resultado, folder_id, criado_em "
            f"FROM creative_history {where_sql} ORDER BY criado_em DESC LIMIT %s OFFSET %s",
            params + [limit, offset]
        )
        items = [dict(r) for r in cur.fetchall()]; conn.close()
        return jsonify({"items": items, "total": total, "page": page, "pages": _math.ceil(total/limit) if total else 1})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/criativos/historico", methods=["POST"])
@login_required
def criativos_salvar_historico():
    d = request.get_json() or {}
    required = ["tipo", "modo", "modelo", "prompt_original", "prompt_expandido", "url_resultado"]
    missing = [f for f in required if not d.get(f)]
    if missing:
        return jsonify({"error": f"Campos obrigatórios: {missing}"}), 400
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO creative_history (tipo,modo,modelo,prompt_original,prompt_expandido,url_resultado,folder_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (d["tipo"], d["modo"], d["modelo"], d["prompt_original"],
             d["prompt_expandido"], d["url_resultado"], d.get("folder_id"))
        )
        novo_id = cur.fetchone()["id"]; conn.commit(); conn.close()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/criativos/historico/<int:hid>", methods=["DELETE"])
@login_required
def criativos_deletar_historico(hid):
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM creative_history WHERE id = %s", (hid,))
        conn.commit(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/criativos/historico/<int:hid>/pasta", methods=["PATCH"])
@login_required
def criativos_mover_pasta(hid):
    d = request.get_json() or {}
    folder_id = d.get("folder_id")  # pode ser None para "sem pasta"
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute("UPDATE creative_history SET folder_id = %s WHERE id = %s", (folder_id, hid))
        conn.commit(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 3: Verificar sintaxe e reiniciar**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python3 -c "import app; print('OK')"
fuser -k 5050/tcp 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/jake_desktop/venv/bin/python app.py > /tmp/jake_flask.log 2>&1 &
sleep 4 && tail -5 /tmp/jake_flask.log
```

Expected: Flask rodando sem erros.

- [ ] **Step 4: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: rotas criativos — histórico paginado e pastas (CRUD completo)"
```

---

## Task 7: CSS da Fábrica de Criativos

**Files:**
- Create: `jake_desktop/static/css/criativos.css`

- [ ] **Step 1: Criar arquivo CSS**

```css
/* ──────────────────────────────────────────────────────
   Jake OS — Fábrica de Criativos v2
────────────────────────────────────────────────────── */

/* Layout principal Split View */
.cri-layout { display:grid; grid-template-columns:380px 1fr; height:100%; overflow:hidden; gap:0; }

/* ── Painel Esquerdo — Configuração ── */
.cri-config { overflow-y:auto; padding:1.25rem; display:flex; flex-direction:column; gap:1rem; border-right:1px solid rgba(0,229,255,.08); }

/* Toggle Imagem / Vídeo */
.cri-tipo-toggle { display:flex; gap:.5rem; }
.cri-tipo-btn { flex:1; padding:.55rem; background:rgba(0,0,0,.2); border:1px solid rgba(0,229,255,.15); border-radius:8px; color:rgba(176,190,197,.6); font-family:var(--ff-h); font-size:.82rem; letter-spacing:.06em; cursor:pointer; transition:all .2s; text-align:center; }
.cri-tipo-btn.active { background:rgba(0,229,255,.12); border-color:rgba(0,229,255,.4); color:#00e5ff; }

/* Selector de modo */
.cri-modos { display:grid; grid-template-columns:1fr 1fr; gap:.4rem; }
.cri-modo-card { background:rgba(0,0,0,.2); border:1px solid rgba(0,229,255,.1); border-radius:8px; padding:.5rem .6rem; cursor:pointer; transition:all .15s; }
.cri-modo-card:hover { background:rgba(0,229,255,.05); border-color:rgba(0,229,255,.25); }
.cri-modo-card.active { background:rgba(0,229,255,.1); border-color:rgba(0,229,255,.5); }
.cri-modo-icon { font-size:1rem; display:block; margin-bottom:.2rem; }
.cri-modo-nome { font-size:.72rem; color:#b0bec5; display:block; }
.cri-modo-card.active .cri-modo-nome { color:#00e5ff; }

/* Section label */
.cri-label { font-size:.72rem; letter-spacing:.07em; text-transform:uppercase; color:rgba(176,190,197,.4); margin-bottom:.35rem; display:block; }

/* Prompt */
.cri-prompt-area { background:rgba(0,0,0,.25); border:1px solid rgba(0,229,255,.15); border-radius:8px; color:#e0e0e0; padding:.65rem .8rem; font-size:.86rem; font-family:var(--ff-b); width:100%; resize:vertical; min-height:70px; box-sizing:border-box; transition:border-color .2s; }
.cri-prompt-area:focus { outline:none; border-color:rgba(0,229,255,.45); }

/* Painel expandido */
.cri-expandido-painel { background:rgba(0,229,255,.03); border:1px solid rgba(0,229,255,.12); border-radius:8px; padding:.75rem; }
.cri-expandido-original { font-size:.75rem; color:rgba(176,190,197,.45); font-style:italic; margin-bottom:.5rem; }
.cri-expandido-texto { background:rgba(0,0,0,.2); border:1px solid rgba(0,229,255,.12); border-radius:6px; color:#e0e0e0; padding:.5rem .65rem; font-size:.82rem; width:100%; min-height:60px; resize:vertical; box-sizing:border-box; font-family:var(--ff-b); }
.cri-expandido-actions { display:flex; justify-content:flex-end; margin-top:.4rem; }

/* Upload */
.cri-upload-zone { border:2px dashed rgba(0,229,255,.18); border-radius:8px; padding:1rem; text-align:center; cursor:pointer; position:relative; transition:all .2s; }
.cri-upload-zone:hover, .cri-upload-zone.dragover { border-color:rgba(0,229,255,.45); background:rgba(0,229,255,.03); }
.cri-upload-input { position:absolute; inset:0; opacity:0; cursor:pointer; width:100%; height:100%; }
.cri-upload-text { font-size:.78rem; color:rgba(176,190,197,.5); }
.cri-upload-preview { max-width:100%; max-height:100px; border-radius:6px; border:1px solid rgba(0,229,255,.2); margin-top:.5rem; }
.cri-upload-actions { display:flex; gap:.4rem; margin-top:.5rem; justify-content:center; }

/* Cards de modelos */
.cri-modelos-grid { display:grid; grid-template-columns:1fr 1fr; gap:.4rem; }
.cri-modelo-card { background:rgba(0,0,0,.2); border:1px solid rgba(0,229,255,.1); border-radius:8px; padding:.55rem .65rem; cursor:pointer; transition:all .15s; }
.cri-modelo-card:hover:not(.disabled) { border-color:rgba(0,229,255,.3); background:rgba(0,229,255,.05); }
.cri-modelo-card.active { background:rgba(0,229,255,.1); border-color:rgba(0,229,255,.5); }
.cri-modelo-card.disabled { opacity:.35; cursor:not-allowed; }
.cri-modelo-nome { font-size:.75rem; color:#e0e0e0; display:block; margin-bottom:.3rem; }
.cri-modelo-card.active .cri-modelo-nome { color:#00e5ff; }
.cri-modelo-badges { display:flex; gap:3px; flex-wrap:wrap; }
.cri-badge { font-size:.62rem; padding:1px 5px; border-radius:3px; }
.cri-badge-tipo-imagem { background:rgba(0,229,255,.1); color:#00e5ff; }
.cri-badge-tipo-t2v { background:rgba(105,240,174,.1); color:#69f0ae; }
.cri-badge-tipo-i2v { background:rgba(255,214,0,.1); color:#ffd740; }
.cri-badge-vel-fast { background:rgba(105,240,174,.08); color:#69f0ae; }
.cri-badge-vel-med { background:rgba(255,214,0,.08); color:#ffd740; }
.cri-badge-custo-1 { background:rgba(105,240,174,.06); color:#69f0ae; }
.cri-badge-custo-2 { background:rgba(255,214,0,.06); color:#ffd740; }
.cri-badge-custo-3 { background:rgba(255,82,82,.08); color:#ff5252; }

/* Botão gerar */
.cri-btn-gerar { width:100%; background:linear-gradient(135deg,rgba(0,229,255,.15),rgba(105,240,174,.1)); border:1px solid rgba(0,229,255,.35); color:#00e5ff; border-radius:10px; padding:.85rem; font-family:var(--ff-h); font-size:.95rem; letter-spacing:.06em; cursor:pointer; transition:all .2s; }
.cri-btn-gerar:hover:not(:disabled) { background:linear-gradient(135deg,rgba(0,229,255,.25),rgba(105,240,174,.18)); box-shadow:0 0 20px rgba(0,229,255,.15); }
.cri-btn-gerar:disabled { opacity:.35; cursor:not-allowed; }
.cri-btn-gerar.loading { opacity:.7; pointer-events:none; }

/* Botões secundários */
.cri-btn-sm { background:rgba(176,190,197,.06); border:1px solid rgba(176,190,197,.15); color:rgba(176,190,197,.7); border-radius:6px; padding:.3rem .75rem; font-size:.75rem; cursor:pointer; transition:all .18s; }
.cri-btn-sm:hover { background:rgba(176,190,197,.12); color:#b0bec5; }
.cri-btn-sm-cyan { background:rgba(0,229,255,.06); border:1px solid rgba(0,229,255,.2); color:#00e5ff; border-radius:6px; padding:.3rem .75rem; font-size:.75rem; cursor:pointer; transition:all .18s; }
.cri-btn-sm-cyan:hover { background:rgba(0,229,255,.12); }

/* ── Painel Direito — Resultado ── */
.cri-resultado { display:flex; flex-direction:column; overflow-y:auto; }

/* Abas Resultado / Histórico */
.cri-abas { display:flex; border-bottom:1px solid rgba(0,229,255,.1); }
.cri-aba { padding:.65rem 1.25rem; font-size:.8rem; letter-spacing:.06em; text-transform:uppercase; color:rgba(176,190,197,.4); cursor:pointer; border-bottom:2px solid transparent; transition:all .2s; font-family:var(--ff-h); }
.cri-aba.active { color:#00e5ff; border-bottom-color:#00e5ff; }

/* Painel de resultado gerado */
.cri-resultado-content { flex:1; padding:1.25rem; display:flex; flex-direction:column; gap:1rem; }
.cri-empty { display:flex; flex-direction:column; align-items:center; justify-content:center; flex:1; gap:.75rem; opacity:.3; }
.cri-empty-icon { font-size:2.5rem; }
.cri-empty-text { color:#b0bec5; text-align:center; font-size:.85rem; }

/* Preview */
.cri-preview-wrap { position:relative; }
.cri-preview-img { max-width:100%; max-height:420px; border-radius:10px; border:1px solid rgba(0,229,255,.15); display:block; }
.cri-preview-video { max-width:100%; max-height:420px; border-radius:10px; border:1px solid rgba(0,229,255,.15); }
.cri-loading-overlay { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:.75rem; padding:2rem; background:rgba(0,0,0,.15); border:1px solid rgba(0,229,255,.1); border-radius:10px; }
.cri-spinner-lg { width:32px; height:32px; border:3px solid rgba(0,229,255,.15); border-top-color:#00e5ff; border-radius:50%; animation:spin .8s linear infinite; }
.cri-loading-text { color:#00e5ff; font-size:.85rem; }
.cri-progress-bar { width:200px; height:3px; background:rgba(0,229,255,.1); border-radius:2px; overflow:hidden; }
.cri-progress-fill { height:100%; background:#00e5ff; width:0%; transition:width .5s; }

/* Ações do resultado */
.cri-acoes { display:flex; gap:.5rem; flex-wrap:wrap; }

/* Histórico */
.cri-historico-content { flex:1; padding:1.25rem; display:flex; flex-direction:column; gap:.75rem; }
.cri-historico-filtros { display:flex; gap:.5rem; flex-wrap:wrap; align-items:center; }
.cri-select-sm { background:rgba(0,0,0,.25); border:1px solid rgba(0,229,255,.15); border-radius:6px; color:#e0e0e0; padding:.35rem .6rem; font-size:.78rem; }
.cri-historico-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr)); gap:.65rem; overflow-y:auto; }
.cri-hist-card { background:rgba(0,0,0,.2); border:1px solid rgba(0,229,255,.08); border-radius:8px; overflow:hidden; transition:border-color .15s; }
.cri-hist-card:hover { border-color:rgba(0,229,255,.25); }
.cri-hist-thumb { width:100%; aspect-ratio:4/5; object-fit:cover; display:block; background:rgba(0,0,0,.3); }
.cri-hist-thumb-video { width:100%; aspect-ratio:4/5; object-fit:cover; display:block; background:rgba(0,0,0,.3); }
.cri-hist-info { padding:.4rem .5rem; }
.cri-hist-modelo { font-size:.65rem; color:#00e5ff; display:block; margin-bottom:.15rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.cri-hist-data { font-size:.62rem; color:rgba(176,190,197,.4); display:block; margin-bottom:.3rem; }
.cri-hist-acoes { display:flex; gap:3px; }
.cri-hist-btn { background:none; border:none; color:rgba(176,190,197,.4); cursor:pointer; font-size:.72rem; padding:2px 4px; border-radius:3px; transition:color .15s; }
.cri-hist-btn:hover { color:#00e5ff; background:rgba(0,229,255,.08); }
.cri-hist-btn-del:hover { color:#ff5252; background:rgba(255,82,82,.08); }
.cri-historico-empty { display:flex; align-items:center; justify-content:center; flex:1; color:rgba(176,190,197,.3); font-size:.85rem; }
.cri-paginacao { display:flex; align-items:center; gap:.5rem; justify-content:center; padding-top:.5rem; }
.cri-pag-btn { background:rgba(0,0,0,.2); border:1px solid rgba(0,229,255,.12); border-radius:6px; color:#b0bec5; padding:.3rem .7rem; font-size:.78rem; cursor:pointer; }
.cri-pag-btn:disabled { opacity:.3; cursor:not-allowed; }
.cri-pag-info { font-size:.75rem; color:rgba(176,190,197,.4); }

/* Utilitários */
@keyframes spin { to { transform:rotate(360deg); } }
.hidden { display:none !important; }
```

- [ ] **Step 2: Commit**

```bash
git add jake_desktop/static/css/criativos.css
git commit -m "feat: CSS da Fábrica de Criativos v2 — split view, modos, modelos, histórico"
```

---

## Task 8: HTML — Substituir seção page-criativos

**Files:**
- Modify: `jake_desktop/templates/dashboard.html`

- [ ] **Step 1: Localizar início e fim da seção atual**

```bash
grep -n "page-criativos\|<!-- 5\." /root/jake_desktop/templates/dashboard.html
```

A seção vai da linha com `id="page-criativos"` até a linha antes de `<!-- 5. ENVIO DE RELATÓRIOS`.

- [ ] **Step 2: Substituir o bloco `<section id="page-criativos">...</section>`**

Substituir todo o bloco por:

```html
      <!-- 4.1 FÁBRICA DE CRIATIVOS ────────────────────── -->
      <section class="page" id="page-criativos">
        <div class="cri-layout">

          <!-- ── Painel Esquerdo — Configuração ── -->
          <div class="cri-config">

            <!-- Toggle Imagem/Vídeo -->
            <div>
              <span class="cri-label">Tipo de saída</span>
              <div class="cri-tipo-toggle">
                <button class="cri-tipo-btn active" id="cri-tipo-imagem">🖼️ Imagem</button>
                <button class="cri-tipo-btn" id="cri-tipo-video">🎬 Vídeo</button>
              </div>
            </div>

            <!-- Seletor de Modo -->
            <div>
              <span class="cri-label">Especialista de Prompt</span>
              <div class="cri-modos">
                <div class="cri-modo-card active" data-modo="anuncios"><span class="cri-modo-icon">🎯</span><span class="cri-modo-nome">Anúncios</span></div>
                <div class="cri-modo-card" data-modo="criativo"><span class="cri-modo-icon">🎨</span><span class="cri-modo-nome">Criativo</span></div>
                <div class="cri-modo-card" data-modo="psicodelico"><span class="cri-modo-icon">🌀</span><span class="cri-modo-nome">Psicodélico</span></div>
                <div class="cri-modo-card" data-modo="pessoas"><span class="cri-modo-icon">👤</span><span class="cri-modo-nome">Pessoas</span></div>
                <div class="cri-modo-card" data-modo="cena"><span class="cri-modo-icon">🌆</span><span class="cri-modo-nome">Cena</span></div>
              </div>
            </div>

            <!-- Prompt -->
            <div>
              <span class="cri-label">Seu prompt (simples, em português)</span>
              <textarea id="cri-prompt" class="cri-prompt-area" placeholder="Ex: clínica odontológica com sorriso feliz..."></textarea>
            </div>

            <!-- Painel Expandido -->
            <div class="hidden" id="cri-expandido-painel">
              <span class="cri-label">Prompt expandido pelo Claude</span>
              <div class="cri-expandido-painel">
                <div class="cri-expandido-original" id="cri-expandido-original"></div>
                <textarea class="cri-expandido-texto" id="cri-expandido-texto" rows="4"></textarea>
                <div class="cri-expandido-actions">
                  <button class="cri-btn-sm-cyan" id="cri-btn-regerar">↺ Regerar</button>
                </div>
              </div>
            </div>

            <!-- Upload de Imagem -->
            <div>
              <span class="cri-label">Imagem de referência (opcional)</span>
              <div class="cri-upload-zone" id="cri-upload-zone">
                <input type="file" id="cri-upload-input" class="cri-upload-input" accept="image/jpeg,image/png,image/webp">
                <div id="cri-upload-placeholder">
                  <span class="cri-upload-text">⬆ Arraste ou clique para selecionar (JPG, PNG)</span>
                </div>
                <div class="hidden" id="cri-upload-preview-wrap">
                  <img id="cri-upload-img" class="cri-upload-preview" src="" alt="preview">
                  <div class="cri-upload-actions">
                    <button class="cri-btn-sm-cyan" id="cri-btn-i2v" data-modo="i2v">🎬 Usar como I2V</button>
                    <button class="cri-btn-sm-cyan" id="cri-btn-analisar">🔍 Analisar estilo</button>
                    <button class="cri-btn-sm" id="cri-btn-remover-img">✕</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Modelos -->
            <div>
              <span class="cri-label" id="cri-modelos-label">Modelo de imagem</span>
              <div class="cri-modelos-grid" id="cri-modelos-grid">
                <!-- preenchido pelo JS -->
              </div>
            </div>

            <!-- Botão Gerar -->
            <button class="cri-btn-gerar" id="cri-btn-gerar">✦ Gerar Criativo</button>

          </div>

          <!-- ── Painel Direito — Resultado + Histórico ── -->
          <div class="cri-resultado">

            <!-- Abas -->
            <div class="cri-abas">
              <div class="cri-aba active" data-aba="resultado" id="cri-aba-resultado">Resultado</div>
              <div class="cri-aba" data-aba="historico" id="cri-aba-historico">Histórico</div>
            </div>

            <!-- Aba Resultado -->
            <div class="cri-resultado-content" id="cri-painel-resultado">
              <div class="cri-empty" id="cri-empty">
                <div class="cri-empty-icon">✦</div>
                <div class="cri-empty-text">Configure e gere seu criativo</div>
              </div>
              <div class="hidden" id="cri-loading-wrap">
                <div class="cri-loading-overlay">
                  <div class="cri-spinner-lg"></div>
                  <div class="cri-loading-text" id="cri-loading-text">Expandindo prompt...</div>
                  <div class="cri-progress-bar"><div class="cri-progress-fill" id="cri-progress-fill"></div></div>
                </div>
              </div>
              <div class="hidden" id="cri-preview-wrap">
                <img id="cri-preview-img" class="cri-preview-img" src="" alt="criativo">
                <video id="cri-preview-video" class="cri-preview-video hidden" controls></video>
              </div>
              <div class="cri-acoes hidden" id="cri-acoes">
                <button class="cri-btn-sm-cyan" id="cri-btn-download">⬇ Download</button>
                <button class="cri-btn-sm-cyan" id="cri-btn-enviar-anuncios">→ Subir Anúncios</button>
                <button class="cri-btn-sm" id="cri-btn-salvar-historico">💾 Salvar</button>
              </div>
            </div>

            <!-- Aba Histórico -->
            <div class="cri-historico-content hidden" id="cri-painel-historico">
              <div class="cri-historico-filtros">
                <select class="cri-select-sm" id="cri-filtro-pasta"><option value="">Todas as pastas</option></select>
                <select class="cri-select-sm" id="cri-filtro-tipo"><option value="">Todos os tipos</option><option value="imagem">Imagem</option><option value="video">Vídeo</option></select>
                <button class="cri-btn-sm-cyan" id="cri-btn-nova-pasta">+ Pasta</button>
                <button class="cri-btn-sm" id="cri-btn-del-pasta" title="Deletar pasta selecionada">🗑</button>
              </div>
              <div class="cri-historico-grid" id="cri-historico-grid">
                <div class="cri-historico-empty">Nenhum criativo salvo ainda</div>
              </div>
              <div class="cri-paginacao" id="cri-paginacao">
                <button class="cri-pag-btn" id="cri-pag-anterior">←</button>
                <span class="cri-pag-info" id="cri-pag-info">1 / 1</span>
                <button class="cri-pag-btn" id="cri-pag-proximo">→</button>
              </div>
            </div>

          </div>
        </div>

        <!-- Modal Salvar no Histórico -->
        <div class="anu-modal-overlay hidden" id="cri-modal-salvar">
          <div class="anu-modal">
            <h3 class="anu-modal-title">💾 Salvar no Histórico</h3>
            <div style="margin-bottom:1rem">
              <label class="cri-label">Pasta (opcional)</label>
              <select class="cri-select-sm" id="cri-modal-pasta" style="width:100%;padding:.5rem"></select>
            </div>
            <div class="anu-modal-actions">
              <button class="anu-btn-secondary" id="cri-modal-salvar-cancelar">Cancelar</button>
              <button class="anu-btn-primary" id="cri-modal-salvar-confirmar">Salvar</button>
            </div>
          </div>
        </div>

      </section>
```

- [ ] **Step 3: Adicionar CSS e JS no dashboard.html**

No `<head>`, após o `anuncios.css`:
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/criativos.css') }}">
```

Antes do `</body>`, após o `anuncios.js`:
```html
<script src="{{ url_for('static', filename='js/criativos.js') }}"></script>
```

Verificar que as tags foram inseridas corretamente:
```bash
grep -n "criativos\." /root/jake_desktop/templates/dashboard.html
```
Expected: 2 linhas — uma com `criativos.css` no `<head>` e outra com `criativos.js` antes de `</body>`.

- [ ] **Step 4: Verificar que Flask carrega sem erro de template**

```bash
fuser -k 5050/tcp 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/jake_desktop/venv/bin/python app.py > /tmp/jake_flask.log 2>&1 &
sleep 4 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/login
```

Expected: `200`

- [ ] **Step 5: Commit**

```bash
git add jake_desktop/templates/dashboard.html
git commit -m "feat: HTML da Fábrica de Criativos v2 — split view completo com histórico"
```

---

## Task 9: JavaScript — criativos.js (layout, modos, modelos)

**Files:**
- Create: `jake_desktop/static/js/criativos.js`

- [ ] **Step 1: Criar arquivo com IIFE, estado e inicialização**

```javascript
/* ──────────────────────────────────────────────────────
   Jake OS — Fábrica de Criativos v2
────────────────────────────────────────────────────── */
(function () {
  'use strict';

  // ── Estado ─────────────────────────────────────────
  var _tipo        = 'imagem';   // 'imagem' | 'video'
  var _modo        = 'anuncios'; // modo do especialista
  var _modelo      = 'flux-1.1-pro';
  var _promptExp   = '';
  var _resultadoUrl= '';
  var _uploadUrl   = '';         // URL Replicate da imagem uploadada (para I2V)
  var _uploadB64   = '';         // base64 da imagem (para análise)
  var _uploadMime  = 'image/jpeg';
  var _usarI2V     = false;
  var _predId      = '';         // prediction_id do vídeo em andamento
  var _pollTimer   = null;
  var _histPage    = 1;
  var _histFiltros = { folder_id: '', tipo: '' };

  // ── Definição de modelos ────────────────────────────
  var _MODELOS_IMAGEM = [
    { key:'flux-1.1-pro',    nome:'Flux 1.1 Pro',       vel:'fast', custo:2 },
    { key:'flux-dev',        nome:'Flux Dev',            vel:'med',  custo:2 },
    { key:'recraft-v3',      nome:'Recraft V3',          vel:'fast', custo:2 },
    { key:'ideogram-v3-turbo',nome:'Ideogram V3 Turbo', vel:'fast', custo:1 },
    { key:'imagen-4',        nome:'Imagen 4',            vel:'med',  custo:3 },
  ];
  var _MODELOS_VIDEO = [
    { key:'wan-t2v-fast',  nome:'Wan T2V Fast',     tipo:'T2V', vel:'fast', custo:1 },
    { key:'wan-5b-fast',   nome:'Wan 5B Fast',      tipo:'T2V', vel:'med',  custo:2 },
    { key:'hailuo-02',     nome:'Hailuo 02 Fast',   tipo:'T2V', vel:'fast', custo:2 },
    { key:'seedance-lite', nome:'Seedance Lite',    tipo:'T2V', vel:'med',  custo:2 },
    { key:'runway-gen4',   nome:'Runway Gen-4',     tipo:'T2V', vel:'fast', custo:3 },
    { key:'wan-i2v-fast',  nome:'Wan I2V Fast',     tipo:'I2V', vel:'fast', custo:1 },
  ];

  // ── Init ───────────────────────────────────────────
  function init() {
    bindTipoToggle();
    bindModos();
    renderModelos();
    bindUpload();
    bindPromptActions();
    bindGerarBtn();
    bindResultadoAcoes();
    bindAbas();
    bindHistoricoEvents();
    carregarPastas();
    carregarHistorico();
  }

  // ── Toggle Imagem / Vídeo ───────────────────────────
  function bindTipoToggle() {
    var btnImg = document.getElementById('cri-tipo-imagem');
    var btnVid = document.getElementById('cri-tipo-video');
    if (btnImg) btnImg.addEventListener('click', function () {
      _tipo = 'imagem'; _modelo = 'flux-1.1-pro'; _usarI2V = false;
      btnImg.classList.add('active'); btnVid.classList.remove('active');
      renderModelos();
      _setText('cri-modelos-label', 'Modelo de imagem');
    });
    if (btnVid) btnVid.addEventListener('click', function () {
      _tipo = 'video'; _modelo = 'wan-t2v-fast';
      btnVid.classList.add('active'); btnImg.classList.remove('active');
      renderModelos();
      _setText('cri-modelos-label', 'Modelo de vídeo');
    });
  }

  // ── Seletor de Modo ─────────────────────────────────
  function bindModos() {
    document.querySelectorAll('.cri-modo-card').forEach(function (card) {
      card.addEventListener('click', function () {
        _modo = this.dataset.modo;
        document.querySelectorAll('.cri-modo-card').forEach(function (c) { c.classList.remove('active'); });
        this.classList.add('active');
        esconder('cri-expandido-painel'); _promptExp = '';
      });
    });
  }

  // ── Render modelos ──────────────────────────────────
  function renderModelos() {
    var grid = document.getElementById('cri-modelos-grid');
    if (!grid) return;
    var lista = _tipo === 'imagem' ? _MODELOS_IMAGEM : _MODELOS_VIDEO;
    grid.innerHTML = lista.map(function (m) {
      var ativo = m.key === _modelo ? ' active' : '';
      var disabled = (m.tipo === 'I2V' && !_usarI2V) ? ' disabled' : '';
      var badges = '';
      if (_tipo === 'imagem') {
        badges = '<span class="cri-badge cri-badge-tipo-imagem">IMG</span>';
      } else {
        badges = '<span class="cri-badge cri-badge-tipo-' + (m.tipo === 'I2V' ? 'i2v' : 't2v') + '">' + m.tipo + '</span>';
      }
      badges += '<span class="cri-badge cri-badge-vel-' + m.vel + '">' + (m.vel === 'fast' ? '⚡' : '◑') + '</span>';
      badges += '<span class="cri-badge cri-badge-custo-' + m.custo + '">' + '$'.repeat(m.custo) + '</span>';
      return '<div class="cri-modelo-card' + ativo + disabled + '" data-key="' + m.key + '">' +
        '<span class="cri-modelo-nome">' + _esc(m.nome) + '</span>' +
        '<div class="cri-modelo-badges">' + badges + '</div></div>';
    }).join('');
    grid.querySelectorAll('.cri-modelo-card:not(.disabled)').forEach(function (card) {
      card.addEventListener('click', function () {
        _modelo = this.dataset.key;
        grid.querySelectorAll('.cri-modelo-card').forEach(function (c) { c.classList.remove('active'); });
        this.classList.add('active');
      });
    });
  }

  // ── Utilitários ─────────────────────────────────────
  function _val(id) { var el = document.getElementById(id); return el ? el.value : ''; }
  function _set(id, v) { var el = document.getElementById(id); if (el) el.value = v || ''; }
  function _setText(id, t) { var el = document.getElementById(id); if (el) el.textContent = t || ''; }
  function _esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function mostrar(id) { var el = document.getElementById(id); if (el) el.classList.remove('hidden'); }
  function esconder(id) { var el = document.getElementById(id); if (el) el.classList.add('hidden'); }

  // ── Observer para init lazy ─────────────────────────
  var _iniciado = false;
  var _obs = new MutationObserver(function (muts) {
    muts.forEach(function (m) {
      if (m.target.id === 'page-criativos' && m.target.classList.contains('active')) {
        if (!_iniciado) { _iniciado = true; init(); }
      }
    });
  });
  var page = document.getElementById('page-criativos');
  if (page) {
    _obs.observe(page, { attributes: true, attributeFilter: ['class'] });
    if (page.classList.contains('active')) { _iniciado = true; init(); }
  }

  // ── Stubs para tasks seguintes ──────────────────────
  function bindUpload() {}
  function bindPromptActions() {}
  function bindGerarBtn() {}
  function bindResultadoAcoes() {}
  function bindAbas() {}
  function bindHistoricoEvents() {}
  function carregarPastas() {}
  function carregarHistorico() {}

})();
```

- [ ] **Step 2: Verificar no browser que a seção carrega**

Reiniciar Flask e acessar `http://localhost:5050/#criativos`. Verificar:
- Toggle Imagem/Vídeo funciona visualmente
- Cards de modo mudam de seleção
- Grid de modelos renderiza com badges

- [ ] **Step 3: Commit**

```bash
git add jake_desktop/static/js/criativos.js
git commit -m "feat: criativos.js — layout, toggle tipo, modos, grid de modelos"
```

---

## Task 10: JavaScript — Upload, Prompt e Geração

**Files:**
- Modify: `jake_desktop/static/js/criativos.js`

Usar a ferramenta Edit para substituir os stubs pelo código real. O old_string exato a ser substituído em `criativos.js` é:

```javascript
  function bindUpload() {}
  function bindPromptActions() {}
  function bindGerarBtn() {}
```

(Deixar os demais stubs `bindResultadoAcoes`, `bindAbas`, etc. intactos — serão substituídos na Task 11.)

- [ ] **Step 1: Implementar bindUpload**

```javascript
  function bindUpload() {
    var zone  = document.getElementById('cri-upload-zone');
    var input = document.getElementById('cri-upload-input');
    if (!zone || !input) return;
    zone.addEventListener('dragover', function (e) { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', function () { zone.classList.remove('dragover'); });
    zone.addEventListener('drop', function (e) {
      e.preventDefault(); zone.classList.remove('dragover');
      var f = e.dataTransfer.files[0]; if (f) _processarUpload(f);
    });
    input.addEventListener('change', function () { if (this.files[0]) _processarUpload(this.files[0]); });
    var btnI2V = document.getElementById('cri-btn-i2v');
    var btnAna = document.getElementById('cri-btn-analisar');
    var btnRem = document.getElementById('cri-btn-remover-img');
    if (btnI2V) btnI2V.addEventListener('click', function () {
      _usarI2V = true;
      if (_tipo !== 'video') {
        _tipo = 'video';
        document.getElementById('cri-tipo-video').classList.add('active');
        document.getElementById('cri-tipo-imagem').classList.remove('active');
        _modelo = 'wan-i2v-fast';
        _setText('cri-modelos-label', 'Modelo de vídeo');
      } else {
        _modelo = 'wan-i2v-fast';
      }
      renderModelos();
      alert('Imagem definida como input I2V. Modelo Wan I2V Fast selecionado.');
    });
    if (btnAna) btnAna.addEventListener('click', _analisarReferencia);
    if (btnRem) btnRem.addEventListener('click', function () {
      _uploadUrl = ''; _uploadB64 = ''; _usarI2V = false;
      esconder('cri-upload-preview-wrap'); mostrar('cri-upload-placeholder');
      document.getElementById('cri-upload-input').value = '';
      renderModelos();
    });
  }

  function _processarUpload(file) {
    var reader = new FileReader();
    reader.onload = function (e) {
      var img = document.getElementById('cri-upload-img');
      if (img) { img.src = e.target.result; }
      esconder('cri-upload-placeholder'); mostrar('cri-upload-preview-wrap');
    };
    reader.readAsDataURL(file);
    // Upload para Replicate
    var fd = new FormData();
    fd.append('arquivo', file);
    fetch('/api/criativos/upload-imagem', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { alert('Erro no upload: ' + data.error); return; }
        _uploadUrl  = data.url   || '';
        _uploadB64  = data.base64 || '';
        _uploadMime = data.mime_type || 'image/jpeg';
      })
      .catch(function (e) { alert('Erro de rede no upload: ' + e); });
  }

  function _analisarReferencia() {
    if (!_uploadB64) { alert('Faça upload de uma imagem primeiro.'); return; }
    _setLoading('🔍 Analisando estilo da imagem...');
    fetch('/api/criativos/analisar-referencia', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imagem_base64: _uploadB64, mime_type: _uploadMime }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _clearLoading();
        if (data.error) { alert('Erro na análise: ' + data.error); return; }
        _set('cri-prompt', '(Analisado da referência)');
        _promptExp = data.prompt_sugerido || '';
        // Selecionar modo sugerido
        if (data.modo_sugerido) {
          _modo = data.modo_sugerido;
          document.querySelectorAll('.cri-modo-card').forEach(function (c) {
            c.classList.toggle('active', c.dataset.modo === _modo);
          });
        }
        _setText('cri-expandido-original', 'Gerado a partir da análise da referência');
        _set('cri-expandido-texto', _promptExp);
        mostrar('cri-expandido-painel');
      })
      .catch(function (e) { _clearLoading(); alert('Erro: ' + e); });
  }
```

- [ ] **Step 2: Implementar bindPromptActions**

```javascript
  function bindPromptActions() {
    var btnReg = document.getElementById('cri-btn-regerar');
    if (btnReg) btnReg.addEventListener('click', _expandirPrompt);
  }

  function _expandirPrompt(callback) {
    var prompt = _val('cri-prompt').trim();
    if (!prompt || prompt === '(Analisado da referência)') {
      if (_promptExp && typeof callback === 'function') { callback(); return; }
      alert('Digite um prompt antes de gerar.'); return;
    }
    _setLoading('✨ Claude expandindo o prompt...');
    fetch('/api/criativos/expandir-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt, modo: _modo, tipo: _tipo }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _clearLoading();
        if (data.error) { alert('Erro ao expandir: ' + data.error); return; }
        _promptExp = data.prompt_expandido || '';
        _setText('cri-expandido-original', 'Original: ' + prompt);
        _set('cri-expandido-texto', _promptExp);
        mostrar('cri-expandido-painel');
        if (typeof callback === 'function') callback();
      })
      .catch(function (e) { _clearLoading(); alert('Erro: ' + e); });
  }
```

- [ ] **Step 3: Implementar bindGerarBtn**

```javascript
  function bindGerarBtn() {
    var btn = document.getElementById('cri-btn-gerar');
    if (btn) btn.addEventListener('click', function () {
      // Prompt expandido já existe? Ir direto para geração
      var promptFinal = _val('cri-expandido-texto').trim() || _promptExp;
      if (promptFinal) {
        _promptExp = promptFinal;
        _gerar();
      } else {
        // Expandir primeiro, depois gerar
        _expandirPrompt(function () { _gerar(); });
      }
    });
  }

  function _gerar() {
    if (_tipo === 'imagem') {
      _gerarImagem();
    } else {
      _gerarVideo();
    }
  }

  function _gerarImagem() {
    _setLoading('🖼️ Gerando imagem...', 40);
    fetch('/api/criativos/gerar-imagem', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt_expandido: _promptExp, modelo: _modelo }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _clearLoading();
        if (data.error) { alert('Erro na geração: ' + data.error); return; }
        _resultadoUrl = data.url;
        _mostrarResultado('imagem');
      })
      .catch(function (e) { _clearLoading(); alert('Erro: ' + e); });
  }

  function _gerarVideo() {
    _setLoading('🎬 Iniciando geração de vídeo...', 10);
    var payload = { prompt_expandido: _promptExp, modelo: _modelo };
    if (_usarI2V && _uploadUrl) payload.imagem_url = _uploadUrl;
    fetch('/api/criativos/gerar-video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { _clearLoading(); alert('Erro: ' + data.error); return; }
        _predId = data.prediction_id;
        _pollVideo(0);
      })
      .catch(function (e) { _clearLoading(); alert('Erro: ' + e); });
  }

  function _pollVideo(tentativa) {
    var progresso = Math.min(10 + tentativa * 4, 85);
    _setLoading('🎬 Gerando vídeo (' + (tentativa * 3) + 's)...', progresso);
    fetch('/api/criativos/status/' + _predId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.status === 'succeeded') {
          _clearLoading(); _resultadoUrl = data.url; _mostrarResultado('video');
        } else if (data.status === 'failed') {
          _clearLoading(); alert('Geração falhou: ' + (data.error || 'erro desconhecido'));
        } else {
          // Continuar polling
          _pollTimer = setTimeout(function () { _pollVideo(tentativa + 1); }, 3000);
        }
      })
      .catch(function () { _pollTimer = setTimeout(function () { _pollVideo(tentativa + 1); }, 3000); });
  }

  function _setLoading(texto, progresso) {
    esconder('cri-empty'); esconder('cri-preview-wrap'); esconder('cri-acoes');
    mostrar('cri-loading-wrap');
    _setText('cri-loading-text', texto);
    var fill = document.getElementById('cri-progress-fill');
    if (fill && progresso) fill.style.width = progresso + '%';
    var btn = document.getElementById('cri-btn-gerar');
    if (btn) { btn.textContent = 'Gerando...'; btn.classList.add('loading'); }
  }

  function _clearLoading() {
    esconder('cri-loading-wrap');
    var btn = document.getElementById('cri-btn-gerar');
    if (btn) { btn.textContent = '✦ Gerar Criativo'; btn.classList.remove('loading'); }
  }

  function _mostrarResultado(tipo) {
    esconder('cri-empty'); esconder('cri-loading-wrap');
    mostrar('cri-preview-wrap'); mostrar('cri-acoes');
    var img = document.getElementById('cri-preview-img');
    var vid = document.getElementById('cri-preview-video');
    if (tipo === 'imagem') {
      if (img) { img.src = _resultadoUrl; img.classList.remove('hidden'); }
      if (vid) vid.classList.add('hidden');
    } else {
      if (vid) { vid.src = _resultadoUrl; vid.classList.remove('hidden'); }
      if (img) img.classList.add('hidden');
    }
  }
```

- [ ] **Step 4: Commit**

```bash
git add jake_desktop/static/js/criativos.js
git commit -m "feat: criativos.js — upload, análise de referência, expansão de prompt e geração"
```

---

## Task 11: JavaScript — Resultado, Histórico e Pastas

**Files:**
- Modify: `jake_desktop/static/js/criativos.js`

Usar a ferramenta Edit para substituir os stubs restantes pelo código real. O old_string exato a ser substituído em `criativos.js` é:

```javascript
  function bindResultadoAcoes() {}
  function bindAbas() {}
  function bindHistoricoEvents() {}
  function carregarPastas() {}
  function carregarHistorico() {}
```

- [ ] **Step 1: Implementar bindResultadoAcoes**

```javascript
  function bindResultadoAcoes() {
    var btnDl = document.getElementById('cri-btn-download');
    if (btnDl) btnDl.addEventListener('click', function () {
      if (!_resultadoUrl) return;
      var a = document.createElement('a');
      a.href = _resultadoUrl; a.download = 'criativo-jakeos.' + (_tipo === 'video' ? 'mp4' : 'webp');
      a.target = '_blank'; a.click();
    });

    var btnAnu = document.getElementById('cri-btn-enviar-anuncios');
    if (btnAnu) btnAnu.addEventListener('click', function () {
      if (!_resultadoUrl) return;
      if (window.JakeAnuncios && window.JakeAnuncios.receberCriativo) {
        window.JakeAnuncios.receberCriativo({ url: _resultadoUrl, tipo: _tipo });
      } else {
        alert('Abra a aba Subir Anúncios e use a URL: ' + _resultadoUrl);
      }
    });

    var btnSalvar = document.getElementById('cri-btn-salvar-historico');
    if (btnSalvar) btnSalvar.addEventListener('click', _abrirModalSalvar);

    var btnCancelar = document.getElementById('cri-modal-salvar-cancelar');
    if (btnCancelar) btnCancelar.addEventListener('click', function () { esconder('cri-modal-salvar'); });

    var btnConfirmar = document.getElementById('cri-modal-salvar-confirmar');
    if (btnConfirmar) btnConfirmar.addEventListener('click', _confirmarSalvar);
  }

  function _abrirModalSalvar() {
    if (!_resultadoUrl) return;
    carregarPastasModal();
    mostrar('cri-modal-salvar');
  }

  function carregarPastasModal() {
    var sel = document.getElementById('cri-modal-pasta');
    if (!sel) return;
    fetch('/api/criativos/pastas')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        sel.innerHTML = '<option value="">Sem pasta</option>' +
          (data.pastas || []).map(function (p) {
            return '<option value="' + p.id + '">' + _esc(p.nome) + '</option>';
          }).join('');
      });
  }

  function _confirmarSalvar() {
    var folderId = _val('cri-modal-pasta') || null;
    var payload = {
      tipo: _tipo, modo: _modo, modelo: _modelo,
      prompt_original: _val('cri-prompt') || '(referência)',
      prompt_expandido: _promptExp || _val('cri-expandido-texto'),
      url_resultado: _resultadoUrl,
      folder_id: folderId ? parseInt(folderId) : null,
    };
    fetch('/api/criativos/historico', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        esconder('cri-modal-salvar');
        if (data.error) { alert('Erro ao salvar: ' + data.error); return; }
        carregarHistorico();
      })
      .catch(function (e) { alert('Erro: ' + e); });
  }
```

- [ ] **Step 2: Implementar bindAbas**

```javascript
  function bindAbas() {
    document.querySelectorAll('.cri-aba').forEach(function (aba) {
      aba.addEventListener('click', function () {
        var alvo = this.dataset.aba;
        document.querySelectorAll('.cri-aba').forEach(function (a) { a.classList.remove('active'); });
        this.classList.add('active');
        if (alvo === 'resultado') {
          mostrar('cri-painel-resultado'); esconder('cri-painel-historico');
        } else {
          esconder('cri-painel-resultado'); mostrar('cri-painel-historico');
          carregarHistorico();
        }
      });
    });
  }
```

- [ ] **Step 3: Implementar carregarPastas e bindHistoricoEvents**

```javascript
  function carregarPastas() {
    fetch('/api/criativos/pastas')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var sel = document.getElementById('cri-filtro-pasta');
        if (!sel) return;
        sel.innerHTML = '<option value="">Todas as pastas</option>' +
          (data.pastas || []).map(function (p) {
            return '<option value="' + p.id + '">' + _esc(p.nome) + '</option>';
          }).join('');
      });
  }

  function bindHistoricoEvents() {
    var filtPasta = document.getElementById('cri-filtro-pasta');
    var filtTipo  = document.getElementById('cri-filtro-tipo');
    if (filtPasta) filtPasta.addEventListener('change', function () {
      _histFiltros.folder_id = this.value; _histPage = 1; carregarHistorico();
    });
    if (filtTipo) filtTipo.addEventListener('change', function () {
      _histFiltros.tipo = this.value; _histPage = 1; carregarHistorico();
    });

    var btnNovaPasta = document.getElementById('cri-btn-nova-pasta');
    if (btnNovaPasta) btnNovaPasta.addEventListener('click', function () {
      var nome = prompt('Nome da nova pasta:');
      if (!nome || !nome.trim()) return;
      fetch('/api/criativos/pastas', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome: nome.trim() }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.error) { alert('Erro: ' + data.error); return; }
          carregarPastas(); carregarHistorico();
        });
    });

    // Deletar pasta selecionada no filtro (com aviso de quantos criativos serão desvinculados)
    var btnDelPasta = document.getElementById('cri-btn-del-pasta');
    if (btnDelPasta) btnDelPasta.addEventListener('click', function () {
      var sel = document.getElementById('cri-filtro-pasta');
      var pid = sel && sel.value;
      if (!pid) { alert('Selecione uma pasta no filtro para deletar.'); return; }
      var nomePasta = sel.options[sel.selectedIndex].text;
      // Primeiro busca contagem de criativos na pasta
      fetch('/api/criativos/historico?folder_id=' + pid + '&limit=1')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var n = data.total || 0;
          var msg = n > 0
            ? 'Deletar pasta "' + nomePasta + '"?\n' + n + ' criativo(s) serão desvinculados (não deletados).'
            : 'Deletar pasta "' + nomePasta + '"? Está vazia.';
          if (!confirm(msg)) return;
          fetch('/api/criativos/pastas/' + pid, { method: 'DELETE' })
            .then(function () { carregarPastas(); _histFiltros.folder_id = ''; carregarHistorico(); });
        });
    });

    var btnAnterior = document.getElementById('cri-pag-anterior');
    var btnProximo  = document.getElementById('cri-pag-proximo');
    if (btnAnterior) btnAnterior.addEventListener('click', function () {
      if (_histPage > 1) { _histPage--; carregarHistorico(); }
    });
    if (btnProximo) btnProximo.addEventListener('click', function () {
      _histPage++; carregarHistorico();
    });
  }

  function carregarHistorico() {
    var params = '?page=' + _histPage + '&limit=20';
    if (_histFiltros.folder_id) params += '&folder_id=' + _histFiltros.folder_id;
    if (_histFiltros.tipo)      params += '&tipo=' + _histFiltros.tipo;
    fetch('/api/criativos/historico' + params)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var grid = document.getElementById('cri-historico-grid');
        if (!grid) return;
        var items = data.items || [];
        if (!items.length) {
          grid.innerHTML = '<div class="cri-historico-empty">Nenhum criativo salvo</div>';
        } else {
          grid.innerHTML = items.map(function (item) {
            var thumb = item.tipo === 'video'
              ? '<video class="cri-hist-thumb-video" src="' + _esc(item.url_resultado) + '" muted></video>'
              : '<img class="cri-hist-thumb" src="' + _esc(item.url_resultado) + '" alt="">';
            var data_fmt = item.criado_em ? item.criado_em.substring(0, 10) : '';
            return '<div class="cri-hist-card" data-id="' + item.id + '">' +
              thumb +
              '<div class="cri-hist-info">' +
              '<span class="cri-hist-modelo">' + _esc(item.modelo) + '</span>' +
              '<span class="cri-hist-data">' + data_fmt + '</span>' +
              '<div class="cri-hist-acoes">' +
              '<button class="cri-hist-btn cri-hist-btn-dl" title="Download" data-url="' + _esc(item.url_resultado) + '" data-tipo="' + item.tipo + '">⬇</button>' +
              '<button class="cri-hist-btn cri-hist-btn-pasta" title="Mover de pasta" data-id="' + item.id + '">📁</button>' +
              '<button class="cri-hist-btn cri-hist-btn-del" title="Deletar" data-id="' + item.id + '">✕</button>' +
              '</div></div></div>';
          }).join('');
          // Bind actions
          grid.querySelectorAll('.cri-hist-btn-dl').forEach(function (btn) {
            btn.addEventListener('click', function () {
              var a = document.createElement('a');
              a.href = this.dataset.url; a.download = 'criativo.' + (this.dataset.tipo === 'video' ? 'mp4' : 'webp');
              a.target = '_blank'; a.click();
            });
          });
          grid.querySelectorAll('.cri-hist-btn-del').forEach(function (btn) {
            btn.addEventListener('click', function () {
              if (!confirm('Deletar este criativo do histórico?')) return;
              var id = this.dataset.id;
              fetch('/api/criativos/historico/' + id, { method: 'DELETE' })
                .then(function () { carregarHistorico(); });
            });
          });
          grid.querySelectorAll('.cri-hist-btn-pasta').forEach(function (btn) {
            btn.addEventListener('click', function () {
              var id = this.dataset.id;
              carregarPastas(); // garante lista atualizada
              fetch('/api/criativos/pastas')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                  var opcoes = ['Sem pasta (null)'].concat((data.pastas || []).map(function (p, i) { return (i + 1) + ') ' + p.nome; }));
                  var escolha = prompt('Mover para pasta:\n' + opcoes.join('\n') + '\n\nDigite 0 para sem pasta, ou o número da pasta:');
                  if (escolha === null) return;
                  var idx = parseInt(escolha);
                  var folderId = idx === 0 ? null : ((data.pastas || [])[idx - 1] || {}).id || null;
                  fetch('/api/criativos/historico/' + id + '/pasta', {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder_id: folderId }),
                  }).then(function () { carregarHistorico(); });
                });
            });
          });
        }
        // Paginação
        var total = data.total || 0;
        var pages = data.pages || 1;
        _setText('cri-pag-info', _histPage + ' / ' + pages);
        var btnAnt = document.getElementById('cri-pag-anterior');
        var btnPro = document.getElementById('cri-pag-proximo');
        if (btnAnt) btnAnt.disabled = _histPage <= 1;
        if (btnPro) btnPro.disabled = _histPage >= pages;
      });
  }
```

- [ ] **Step 4: Smoke test completo**

```bash
fuser -k 5050/tcp 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/jake_desktop/venv/bin/python app.py > /tmp/jake_flask.log 2>&1 &
sleep 4 && tail -5 /tmp/jake_flask.log
```

Acessar `http://localhost:5050/#criativos` e verificar:
- Seção carrega sem erros no console
- Toggle Imagem/Vídeo muda os modelos
- Cards de modo selecionam
- Aba Histórico abre (vazio)
- Botão "+ Pasta" funciona (cria pasta)
- Botão 🗑 ao lado da pasta deletar mostra contagem e confirma

- [ ] **Step 5: Commit final**

```bash
git add jake_desktop/static/js/criativos.js jake_desktop/app.py jake_desktop/templates/dashboard.html jake_desktop/static/css/criativos.css scripts/migrar_criativos.py
git commit -m "feat: Fábrica de Criativos v2 — implementação completa (imagem, vídeo, histórico, pastas)"
```

---

## Critérios de Sucesso

- [ ] Gerar imagem com Flux 1.1 Pro retorna URL em < 30s
- [ ] Gerar vídeo T2V inicia geração e polling funciona até `succeeded`
- [ ] Prompt expandido pelo especialista tem 50-120 palavras em inglês
- [ ] Análise de referência devolve prompt + modo_sugerido válido
- [ ] Histórico salva, lista com paginação e deleta
- [ ] Pastas criam, listam e deletam (criativos ficam sem pasta)
- [ ] I2V só habilita modelo Wan I2V quando imagem está uploadada
- [ ] Download funciona para imagem e vídeo
- [ ] Flask não trava durante geração de vídeo (prediction_id retorna imediato)
