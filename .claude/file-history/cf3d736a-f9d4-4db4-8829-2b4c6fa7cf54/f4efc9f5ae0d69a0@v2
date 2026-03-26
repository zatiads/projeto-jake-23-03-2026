# Automação Live — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar `brain.py` e conectá-lo a 9 rotas do Jake OS para salvar automaticamente outputs no vault Obsidian.

**Architecture:** Novo módulo `jake_desktop/brain.py` com função `salvar()` que escreve `.md` em `/root/jake-brain/Jake OS/Outputs/<Modulo>/`. Cada rota elegível chama `brain.salvar()` antes de retornar. Erros são silenciosos. Cron existente (`*/5 * * * *`) faz git push para o Obsidian Windows.

**Tech Stack:** Python 3, Flask (existente), pytest, unicodedata, re, datetime

**Spec:** `docs/superpowers/specs/2026-03-22-automacao-live-design.md`

---

## File Map

| Arquivo | Ação |
|---|---|
| `jake_desktop/brain.py` | Criar — módulo `salvar()` |
| `jake_desktop/tests/__init__.py` | Criar — vazio |
| `jake_desktop/tests/test_brain.py` | Criar — testes unitários |
| `jake_desktop/app.py` | Modificar — `import brain` + 9 chamadas |

---

## Mapa exato das rotas (variáveis verificadas no código)

| Rota | Linha | Variáveis de input | Variável de output | Retorno |
|---|---|---|---|---|
| `POST /api/carousel/copy` | 320 | `theme`, `tone`, `awareness`, `trigger` | `slides` (list) | linha 366 |
| `POST /api/copys/gerar` | 437 | `plataforma`, `framework`, `tom`, `nicho`, `oferta`, `profissao`, `nivel_consciencia`, `gatilho`, `tamanho` | `copy_text` | linha 503 |
| `POST /api/financeiro/analise` | 1103 | `mes`, `receita`, `despesas`, `saldo`, `receita_ant`, `desp_ant` | `analise` | linhas 1145 e 1158 (2 paths) |
| `POST /api/site-architect/generate` | 1246 | `ref_url`, `contexto`, `hero_copy`, `extra_copy`, `template_kind` | `html` | linha 1402 |
| `POST /api/site-architect/refine` | 1407 | `instruction` | `new_html` | linha 1442 |
| `POST /api/anuncios/copy` | 1768 | `cliente_nome`, `camp_tipo`, `segmento` | `resultado` (dict) | linha 1822 |
| `POST /api/criativos/expandir-prompt` | 2054 | `prompt`, `modo`, `tipo` | `msg.content[0].text.strip()` | linha 2079 |
| `POST /api/criativos/gerar-imagem` | 2130 | `prompt`, `modelo` | `url` | linhas 2159 e 2168 (2 paths) |
| `POST /api/criativos/gerar-video` | 2178 | `prompt`, `modelo`, `imagem_url` | `pred.get("id")` | linha 2209 |

---

## Task 1: Criar brain.py (TDD)

**Files:**
- Create: `jake_desktop/brain.py`
- Create: `jake_desktop/tests/__init__.py`
- Create: `jake_desktop/tests/test_brain.py`

- [ ] **Step 1: Garantir que pytest está instalado**

```bash
cd /root/jake_desktop && /root/venv/bin/pip install pytest -q
```

Expected: `Successfully installed pytest-...` ou `Requirement already satisfied`

- [ ] **Step 2: Criar diretório de testes**

Criar `jake_desktop/tests/__init__.py` (arquivo vazio).

- [ ] **Step 3: Criar `jake_desktop/tests/test_brain.py`**

```python
"""
Testes unitários para brain.py.
Uso: cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_brain.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import brain


# --- _slug ---

def test_slug_basico():
    assert brain._slug("Copy Instagram AIDA") == "copy-instagram-aida"


def test_slug_acentos():
    resultado = brain._slug("Análise Março 2026")
    assert "analise" in resultado
    assert "marco" in resultado
    assert "2026" in resultado


def test_slug_max_60_chars():
    assert len(brain._slug("a" * 100)) <= 60


def test_slug_chars_especiais():
    resultado = brain._slug("Copy — Dashboard v2")
    assert "copy" in resultado
    assert "dashboard" in resultado
    assert len(resultado) <= 60


# --- _inputs_md ---

def test_inputs_md_basico():
    md = brain._inputs_md({"plataforma": "Instagram", "framework": "AIDA"})
    assert "**plataforma:** Instagram" in md
    assert "**framework:** AIDA" in md


def test_inputs_md_ignora_vazios():
    md = brain._inputs_md({"a": "valor", "b": "", "c": None, "d": "ok"})
    assert "**b:**" not in md
    assert "**c:**" not in md
    assert "valor" in md
    assert "ok" in md


def test_inputs_md_trunca_longos():
    md = brain._inputs_md({"prompt": "x" * 400})
    assert "..." in md
    for linha in md.splitlines():
        if "prompt" in linha:
            assert len(linha) < 400


def test_inputs_md_dict_vazio():
    md = brain._inputs_md({})
    assert "sem inputs" in md


# --- salvar ---

def test_salvar_cria_arquivo(tmp_path):
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar(
                "Copys",
                "Copy Instagram AIDA academia",
                {"plataforma": "Instagram", "framework": "AIDA"},
                "Conteúdo gerado aqui",
                "claude-sonnet-4-6",
            )

    arquivos = list((vault_outputs / "Copys").glob("*.md"))
    assert len(arquivos) == 1

    conteudo = arquivos[0].read_text(encoding="utf-8")
    assert "Copy Instagram AIDA academia" in conteudo
    assert "Conteúdo gerado aqui" in conteudo
    assert "claude-sonnet-4-6" in conteudo
    assert "Instagram" in conteudo
    assert "modulo: Copys" in conteudo
    assert "gerado_em:" in conteudo
    assert "## Observações" in conteudo


def test_salvar_titulo_vazio_nao_cria_arquivo(tmp_path):
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Copys", "", {"p": "v"}, "output", "model")
    assert not (vault_outputs / "Copys").exists()


def test_salvar_titulo_none_nao_cria_arquivo(tmp_path):
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Copys", None, {}, "output", "model")
    assert not (vault_outputs / "Copys").exists()


def test_salvar_vault_inexistente_nao_propaga():
    with patch("brain.os.path.isdir", return_value=False):
        brain.salvar("Copys", "titulo", {}, "output", "model")  # não deve lançar


def test_salvar_erro_interno_nao_propaga():
    with patch("brain.VAULT", "/dev/null/impossivel"):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Copys", "titulo", {}, "output", "model")  # não deve lançar


def test_salvar_colisao_gera_sufixo(tmp_path):
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    dt_fixo = datetime(2026, 3, 22, 15, 43, 0)

    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            with patch("brain.datetime") as mock_dt:
                mock_dt.now.return_value = dt_fixo
                brain.salvar("Copys", "Copy teste", {}, "output 1", "model")
                brain.salvar("Copys", "Copy teste", {}, "output 2", "model")

    arquivos = sorted((vault_outputs / "Copys").glob("*.md"))
    assert len(arquivos) == 2
    assert any("-2.md" in f.name for f in arquivos)


def test_salvar_frontmatter_completo(tmp_path):
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Financeiro", "Análise março", {}, "texto da análise", "claude-sonnet-4-5")

    arquivo = list((vault_outputs / "Financeiro").glob("*.md"))[0]
    conteudo = arquivo.read_text(encoding="utf-8")
    assert conteudo.startswith("---\n")
    assert "modulo: Financeiro" in conteudo
    assert "modelo: claude-sonnet-4-5" in conteudo
    assert "## Inputs\n" in conteudo
    assert "## Output\n" in conteudo
    assert "## Observações" in conteudo
```

- [ ] **Step 4: Rodar testes — confirmar que falham**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_brain.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'brain'`

- [ ] **Step 5: Criar `jake_desktop/brain.py`**

```python
"""
brain.py — Salva automaticamente outputs do Jake OS no vault Obsidian.
Uso: import brain; brain.salvar(modulo, titulo, inputs, output, model)
"""
import os
import re
import logging
import unicodedata
from datetime import datetime

VAULT = "/root/jake-brain/Jake OS/Outputs"

TEMPLATE = """\
---
modulo: {modulo}
modelo: {model}
gerado_em: {gerado_em}
---

# {titulo}

## Inputs
{inputs_md}

## Output
{output}

## Modelo
{model}

## Observações
<!-- espaço para anotar no Obsidian depois -->
"""


def _slug(texto: str) -> str:
    """'Copy — Instagram AIDA' → 'copy-instagram-aida' (max 60 chars)"""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    texto = re.sub(r"[\s_-]+", "-", texto)
    return texto[:60].strip("-")


def _inputs_md(inputs: dict) -> str:
    """Converte dict de inputs em lista markdown. Ignora vazios, trunca longos."""
    if not inputs:
        return "- (sem inputs registrados)"
    linhas = []
    for k, v in inputs.items():
        if v is None or v == "":
            continue
        v_str = str(v)
        if len(v_str) > 300:
            v_str = v_str[:300] + "..."
        linhas.append(f"- **{k}:** {v_str}")
    return "\n".join(linhas) if linhas else "- (sem inputs registrados)"


def salvar(modulo: str, titulo: str, inputs: dict, output: str, model: str) -> None:
    """
    Salva um output gerado pelo Jake OS como nota .md no vault Obsidian.
    Silencioso em caso de erro — nunca propaga exceção.
    """
    try:
        if not titulo:
            logging.warning("brain.salvar: titulo vazio, ignorando.")
            return
        if not os.path.isdir("/root/jake-brain"):
            logging.warning("brain.salvar: vault /root/jake-brain não encontrado.")
            return

        agora = datetime.now()
        ts = agora.strftime("%Y-%m-%d-%H-%M")
        gerado_em = agora.strftime("%Y-%m-%d %H:%M")

        destino_dir = os.path.join(VAULT, modulo)
        os.makedirs(destino_dir, exist_ok=True)

        slug = _slug(titulo)
        nome_base = f"{ts}-{slug}"
        destino = os.path.join(destino_dir, f"{nome_base}.md")

        # Colisão: append -2, -3, etc.
        contador = 2
        while os.path.exists(destino):
            destino = os.path.join(destino_dir, f"{nome_base}-{contador}.md")
            contador += 1

        conteudo = TEMPLATE.format(
            modulo=modulo,
            model=model,
            gerado_em=gerado_em,
            titulo=titulo,
            inputs_md=_inputs_md(inputs or {}),
            output=output or "(sem output)",
        )

        with open(destino, "w", encoding="utf-8") as f:
            f.write(conteudo)

    except Exception as e:
        logging.warning(f"brain.salvar falhou: {e}")
```

- [ ] **Step 6: Rodar testes — confirmar que passam**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_brain.py -v
```

Expected: `12 passed` (todos os testes verdes)

- [ ] **Step 7: Commit**

```bash
cd /root && git add jake_desktop/brain.py jake_desktop/tests/
git commit -m "feat: brain.py — salva outputs Jake OS no vault Obsidian"
```

---

## Task 2: Conectar Copys, Carrossel e Financeiro

**Files:**
- Modify: `jake_desktop/app.py` (linhas 1, 320–366, 437–503, 1103–1158)

- [ ] **Step 1: Adicionar `import brain` no app.py**

Ler: `Read /root/jake_desktop/app.py offset=1 limit=30`

Localizar o bloco de imports. Adicionar `import brain` no final dos imports (após `import json` ou similar — não no meio das importações de terceiros, apenas depois delas).

- [ ] **Step 2: Conectar `/api/copys/gerar` (linha 503)**

Ler: `Read /root/jake_desktop/app.py offset=493 limit=15`

Adicionar antes do `return jsonify({"copy": copy_text, "variacao": variacao})` na linha 503:

```python
        brain.salvar(
            modulo="Copys",
            titulo=f"Copy {plataforma} {framework}",
            inputs={
                "plataforma": plataforma,
                "framework": framework,
                "tom": tom,
                "nicho": nicho,
                "oferta": oferta,
                "profissao": profissao,
                "nivel_consciencia": nivel_consciencia,
                "gatilho": gatilho,
                "tamanho": tamanho,
            },
            output=copy_text,
            model="claude-sonnet-4-6",
        )
```

- [ ] **Step 3: Conectar `/api/carousel/copy` (linha 366)**

Ler: `Read /root/jake_desktop/app.py offset=356 limit=15`

Adicionar antes do `return jsonify({"slides": slides, "theme": theme, "tone": tone})` na linha 366:

```python
        slides_texto = "\n\n".join(
            f"**Slide {i+1}:** {str(s)}" for i, s in enumerate(slides)
        )
        brain.salvar(
            modulo="Carrossel",
            titulo=f"Carrossel {theme}",
            inputs={
                "tema": theme,
                "tom": tone,
                "awareness": awareness,
                "gatilho": trigger,
            },
            output=slides_texto,
            model="claude-sonnet-4-5",
        )
```

- [ ] **Step 4: Conectar `/api/financeiro/analise` (linhas 1145 e 1158)**

Ler: `Read /root/jake_desktop/app.py offset=1133 limit=30`

Esta rota tem **dois caminhos de retorno** (Claude e GPT-4o), ambos com `analise` definida logo antes. Adicionar `brain.salvar()` antes de **cada** `return jsonify({"analise": analise})`:

```python
            # Adicionar antes de return jsonify({"analise": analise}) — linha ~1145
            brain.salvar(
                modulo="Financeiro",
                titulo=f"Análise financeira {mes}",
                inputs={
                    "mes": mes,
                    "receita": receita,
                    "despesas": despesas,
                    "saldo": saldo,
                    "receita_anterior": receita_ant,
                    "despesas_anteriores": desp_ant,
                },
                output=analise,
                model="claude-sonnet-4-5",
            )
```

Repetir o mesmo bloco antes do segundo `return jsonify({"analise": analise})` na linha ~1158 (path GPT-4o), com `model="gpt-4o"`.

- [ ] **Step 5: Verificar que app importa sem erros**

```bash
cd /root/jake_desktop && /root/venv/bin/python -c "import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
cd /root && git add jake_desktop/app.py
git commit -m "feat: brain.salvar em Copys, Carrossel e Financeiro"
```

---

## Task 3: Conectar Criativos (3 rotas)

**Files:**
- Modify: `jake_desktop/app.py` (linhas 2054–2079, 2130–2175, 2178–2213)

- [ ] **Step 1: Conectar `/api/criativos/expandir-prompt` (linha 2079)**

Ler: `Read /root/jake_desktop/app.py offset=2070 limit=15`

Adicionar antes do `return jsonify({"prompt_expandido": msg.content[0].text.strip()})` na linha 2079:

```python
        prompt_expandido = msg.content[0].text.strip()
        brain.salvar(
            modulo="Criativos",
            titulo=f"Prompt expandido {modo} {tipo}",
            inputs={"prompt": prompt, "modo": modo, "tipo": tipo},
            output=prompt_expandido,
            model="claude-sonnet-4-6",
        )
        return jsonify({"prompt_expandido": prompt_expandido})
```

> **Nota:** Extrair o texto para variável `prompt_expandido` antes de passar para `brain.salvar()` e para o `return`. Remover o `return` original que estava inline.

- [ ] **Step 2: Conectar `/api/criativos/gerar-imagem` (linhas 2159 e 2168)**

Ler: `Read /root/jake_desktop/app.py offset=2150 limit=25`

Esta rota tem **dois caminhos de sucesso** (síncrono e polling). Adicionar `brain.salvar()` antes de cada `return jsonify({"url": url, "ok": True})`:

```python
            # Path síncrono (linha ~2159) e polling (linha ~2168) — mesmo bloco:
            brain.salvar(
                modulo="Criativos",
                titulo=f"Imagem gerada {modelo}",
                inputs={"modelo": modelo, "prompt": prompt},
                output=url,
                model=modelo,
            )
```

- [ ] **Step 3: Conectar `/api/criativos/gerar-video` (linha 2209)**

Ler: `Read /root/jake_desktop/app.py offset=2200 limit=15`

Adicionar antes do `return jsonify({"prediction_id": pred.get("id"), "ok": True})` na linha 2209:

```python
        prediction_id = pred.get("id")
        brain.salvar(
            modulo="Criativos",
            titulo=f"Vídeo iniciado {modelo}",
            inputs={"modelo": modelo, "prompt": prompt},
            output=f"prediction_id: {prediction_id}",
            model=modelo,
        )
        return jsonify({"prediction_id": prediction_id, "ok": True})
```

> **Nota:** Extrair `prediction_id` para variável antes. Remover o `return` original inline.

- [ ] **Step 4: Verificar import**

```bash
cd /root/jake_desktop && /root/venv/bin/python -c "import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd /root && git add jake_desktop/app.py
git commit -m "feat: brain.salvar em Criativos (expandir-prompt, gerar-imagem, gerar-video)"
```

---

## Task 4: Conectar Anúncios e Site Architect

**Files:**
- Modify: `jake_desktop/app.py` (linhas 1768–1822, 1246–1402, 1407–1442)

- [ ] **Step 1: Conectar `/api/anuncios/copy` (linha 1822)**

Ler: `Read /root/jake_desktop/app.py offset=1815 limit=15`

Adicionar antes do `return jsonify(resultado)` na linha 1822:

```python
        brain.salvar(
            modulo="Anuncios",
            titulo=f"Copy anúncio {cliente_nome}",
            inputs={
                "cliente": cliente_nome,
                "campanha_tipo": camp_tipo,
                "segmento": segmento,
            },
            output=(
                f"Título: {resultado.get('titulo', '')}\n\n"
                f"Texto: {resultado.get('texto', '')}\n\n"
                f"CTA: {resultado.get('cta', '')}"
            ),
            model="claude-sonnet-4-6",
        )
```

- [ ] **Step 2: Conectar `/api/site-architect/generate` (linha 1402)**

Ler: `Read /root/jake_desktop/app.py offset=1395 limit=12`

Adicionar antes do `return jsonify({"html": html})` na linha 1402:

```python
        brain.salvar(
            modulo="Site Architect",
            titulo=f"Landing page {contexto[:40] if contexto else ref_url[:40] if ref_url else 'sem contexto'}",
            inputs={
                "reference_url": ref_url,
                "business_context": contexto,
                "hero_copy": hero_copy,
                "extra_copy": extra_copy,
                "template_kind": template_kind,
            },
            output=html,
            model="claude-sonnet-4-6",
        )
```

- [ ] **Step 3: Conectar `/api/site-architect/refine` (linha 1442)**

Ler: `Read /root/jake_desktop/app.py offset=1434 limit=15`

Adicionar antes do `return jsonify({"html": new_html, "summary": ...})` na linha 1442:

```python
        brain.salvar(
            modulo="Site Architect",
            titulo="Refinamento landing page",
            inputs={"instrucao": instruction},
            output=new_html,
            model="claude-sonnet-4-6",
        )
```

- [ ] **Step 4: Verificar import**

```bash
cd /root/jake_desktop && /root/venv/bin/python -c "import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Contar as 9 chamadas brain.salvar**

```bash
grep -n "brain.salvar" /root/jake_desktop/app.py
```

Expected: 10 linhas (9 chamadas `brain.salvar(` + linhas com os parâmetros — ou contar só as que têm `brain.salvar(`):

```bash
grep -c "brain\.salvar(" /root/jake_desktop/app.py
```

Expected: `9`

- [ ] **Step 6: Rodar testes de brain.py — ainda passam**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_brain.py -v
```

Expected: `12 passed`

- [ ] **Step 7: Commit final**

```bash
cd /root && git add jake_desktop/app.py
git commit -m "feat: brain.salvar em Anúncios e Site Architect — automação live completa"
```

---

## Verificação Final

- [ ] **Contar chamadas em app.py**

```bash
grep -c "brain\.salvar(" /root/jake_desktop/app.py
```

Expected: `9`

- [ ] **Verificar que brain.py existe**

```bash
ls -la /root/jake_desktop/brain.py
```

- [ ] **Verificar que vault está acessível**

```bash
ls /root/jake-brain/Jake\ OS/
```

Expected: ver pasta `Outputs/` criada (ou será criada na primeira chamada)

- [ ] **Verificar que não há [TODO] no vault (não deve ter afetado)**

```bash
grep -r "\[TODO\]" /root/jake-brain/ --include="*.md" | wc -l
```

Expected: `0`
