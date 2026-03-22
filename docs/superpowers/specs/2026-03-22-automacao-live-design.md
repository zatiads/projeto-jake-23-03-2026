# Automação Live — Design Spec

**Data:** 2026-03-22
**Projeto:** Jake Brain — Cérebro do ecossistema Jake IA
**Sub-projeto:** 3 de 4 — Automação Live (Jake OS salva automaticamente no vault)

---

## Objetivo

Sempre que o Jake OS gerar conteúdo (copy, carrossel, criativo, landing page, análise financeira), salvar automaticamente uma nota `.md` no vault Obsidian (`/root/jake-brain/`), sem intervenção manual.

---

## Arquitetura

### Novo arquivo: `jake_desktop/brain.py`

Módulo utilitário com uma única função pública:

```python
def salvar(modulo: str, titulo: str, inputs: dict, output: str, model: str) -> None
```

**Parâmetros:**
- `modulo` — nome legível da seção do vault (ex: `"Copys"`, `"Carrossel"`, `"Criativos"`, `"Anuncios"`, `"Site Architect"`, `"Financeiro"`)
- `titulo` — título descritivo da nota (ex: `"Copy Instagram AIDA — academia"`)
- `inputs` — dict com campos relevantes da request (sem base64, sem file content — apenas strings/números simples)
- `output` — conteúdo gerado, sempre como `str` (texto, HTML, JSON formatado como string)
- `model` — modelo de IA usado (ex: `"claude-sonnet-4-6"`)

**Algoritmo de nome de arquivo:**

```python
import re, unicodedata

def _slug(texto: str) -> str:
    # Normaliza acentos → ASCII, lowercase, troca espaços/pontuação por hífens, max 60 chars
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    texto = re.sub(r"[\s_-]+", "-", texto)
    return texto[:60].strip("-")

# Nome final: YYYY-MM-DD-HH-MM-<slug>.md
# Colisão (mesmo minuto, mesmo slug): append -2, -3, etc.
```

**Caminho de destino:**
```
/root/jake-brain/Jake OS/Outputs/<Modulo>/<YYYY-MM-DD-HH-MM-slug>.md
```

**Comportamento de erro:**
- Qualquer exceção dentro de `salvar()` → capturada com `try/except Exception`
- Logar com `import logging; logging.warning(f"brain.salvar falhou: {e}")`
- Nunca propagar a exceção — a rota continua funcionando normalmente
- Se `/root/jake-brain/` não existir → logar e retornar silenciosamente

### Modificação: `jake_desktop/app.py`

Adicionar `import brain` no topo. Chamar `brain.salvar(...)` no final de cada rota elegível, imediatamente antes do `return jsonify(...)`.

### Infraestrutura (sem mudanças)

O cron existente (`*/5 * * * *` → `jake_brain_push.sh`) continua fazendo o git push. Nenhuma mudança de infra.

---

## Template da Nota

```markdown
---
modulo: {modulo}
modelo: {model}
gerado_em: 2026-03-22 15:43
---

# {titulo}

## Inputs
- **Campo:** valor
- **Campo:** valor

## Output
{output}

## Modelo
{model}

## Observações
<!-- espaço para anotar no Obsidian depois -->
```

**Regras:**
- `gerado_em` usa formato `YYYY-MM-DD HH:MM` (sem segundos) — o mesmo usado no nome do arquivo com hífens
- `inputs` é renderizado como lista markdown: `- **Chave:** valor` para cada par do dict
- `output` é inserido como texto puro (sem bloco de código adicional — o conteúdo já tem formatação adequada)
- Campos com valor `None` ou string vazia são omitidos do `inputs`

---

## Rotas Elegíveis

| Módulo (vault) | Rota | inputs a passar | output a salvar |
|---|---|---|---|
| `Copys` | `POST /api/copys/gerar` | plataforma, framework, nicho, oferta, tom, gatilho | `resultado["copy"]` |
| `Carrossel` | `POST /api/carousel/copy` | tema, tom, nivel_consciencia, gatilho | slides formatados como texto (um por linha) |
| `Criativos` | `POST /api/criativos/expandir-prompt` | prompt (truncado em 200 chars), modo, tipo | `resultado["prompt_expandido"]` |
| `Criativos` | `POST /api/criativos/gerar-imagem` | modelo, prompt (truncado em 200 chars) | `resultado["url"]` |
| `Criativos` | `POST /api/criativos/gerar-video` | modelo, prompt (truncado em 200 chars) | URL ou prediction_id |
| `Anuncios` | `POST /api/anuncios/copy` | cliente_nome, campaign_type, segmento | `f"Título: {titulo}\n\nTexto: {texto}\n\nCTA: {cta}"` |
| `Site Architect` | `POST /api/site-architect/generate` | business_context, hero_copy, template_kind | HTML completo |
| `Site Architect` | `POST /api/site-architect/refine` | instrucao (primeiros 300 chars) | HTML refinado |
| `Financeiro` | `POST /api/financeiro/analise` | mes, receita, despesas, saldo | `resultado["analise"]` |

**Regras de input filtering:**
- **Nunca** incluir campos com base64 (imagens, áudios) — omitir silenciosamente
- **Nunca** incluir file objects ou binary data
- Strings muito longas (>300 chars): truncar com `[:300] + "..."`
- Campos numéricos: manter como-é

**Fora do escopo** (não geram conteúdo final ou retornam apenas imagem binária):
- `POST /api/criativos/analisar-referencia` (análise intermediária)
- `POST /api/carousel/generate-image` (retorna base64, não texto)
- `POST /api/generate-creative` (factory legado — substituído pelos criativos v2)
- Todas as rotas GET, DELETE, PATCH

---

## Estrutura do Vault Após Automação Live

```
jake-brain/
└── Jake OS/
    └── Outputs/
        ├── Copys/
        │   └── 2026-03-22-15-43-copy-instagram-aida-academia.md
        ├── Carrossel/
        │   └── 2026-03-22-16-00-carrossel-academia-awareness.md
        ├── Criativos/
        │   ├── 2026-03-22-16-10-expandir-flux-anuncio.md
        │   └── 2026-03-22-16-11-gerar-imagem-flux-1-1-pro.md
        ├── Anuncios/
        │   └── 2026-03-22-16-20-copy-piloti-stories.md
        ├── Site Architect/
        │   └── 2026-03-22-17-00-landing-clinica-aline.md
        └── Financeiro/
            └── 2026-03-22-18-00-analise-marco-2026.md
```

---

## Edge Cases

| Situação | Comportamento |
|---|---|
| Mesmo slug gerado no mesmo minuto | Append `-2`, `-3`, etc. ao nome |
| `titulo` vazio ou None | `salvar()` retorna sem criar arquivo, loga warning |
| `/root/jake-brain/` não existe | Loga warning, retorna silenciosamente |
| Output muito longo (HTML > 100KB) | Salvar completo — Obsidian suporta arquivos grandes |
| Vault read-only | `try/except` captura `PermissionError`, loga, não propaga |

---

## Critérios de Sucesso

- [ ] `jake_desktop/brain.py` existe e `salvar()` funciona standalone
- [ ] Ao chamar `/api/copys/gerar`, um `.md` aparece em `Jake OS/Outputs/Copys/`
- [ ] Ao chamar `/api/carousel/copy`, um `.md` aparece em `Jake OS/Outputs/Carrossel/`
- [ ] Todas as 9 rotas elegíveis geram nota no vault
- [ ] Erros em `brain.salvar()` não quebram nenhuma rota (testar com vault path inválido)
- [ ] Colisão de nomes gera sufixo `-2` corretamente
- [ ] Após ≤5 min, nota aparece no Obsidian Windows via cron
