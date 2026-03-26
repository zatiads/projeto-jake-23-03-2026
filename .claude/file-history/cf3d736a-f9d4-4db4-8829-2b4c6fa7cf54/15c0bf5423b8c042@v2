# Obsidian Graph Enrichment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enriquecer o grafo do Obsidian com tags e wikilinks automáticos nas notas de output e mais conexões nas notas retroativas.

**Architecture:** Três mudanças independentes: (1) `brain.py` ganha `_find_cliente_nota()` e `salvar()` recebe `cliente=` opcional para gerar tags e links automáticos no TEMPLATE; (2) 4 chamadas `brain.salvar()` em `app.py` recebem `cliente=`; (3) as 18 notas retroativas do vault recebem wikilinks adicionais via edição de conteúdo.

**Tech Stack:** Python stdlib, pytest, markdown (Obsidian vault).

---

## Arquivos

| Arquivo | Mudança |
|---|---|
| `jake_desktop/brain.py` | Novo TEMPLATE, `_find_cliente_nota()`, assinatura `salvar()` com `cliente=` |
| `jake_desktop/tests/test_brain.py` | 9 novos testes (TDD) |
| `jake_desktop/app.py` | Adicionar `cliente=` em 4 chamadas `brain.salvar()` |
| 18 arquivos `.md` em `/root/jake-brain/` | Adicionar wikilinks na seção `## Links Relacionados` |

---

## Task 1: Atualizar `brain.py` — TEMPLATE + `_find_cliente_nota()` + `salvar()` com TDD

**Files:**
- Modify: `jake_desktop/brain.py`
- Modify: `jake_desktop/tests/test_brain.py`

**Contexto:**
- `brain.py` tem `_slug()`, `VAULT_ROOT`, `VAULT`, `TEMPLATE`, `salvar()`, `contexto()`, `_find_cliente_nota()` ainda NÃO existe
- Testes rodam com `/root/venv/bin/python -m pytest` (NÃO o venv do jake_desktop — pytest está em /root/venv)
- `salvar()` atual tem assinatura: `salvar(modulo, titulo, inputs, output, model)`
- A spec descreve uma função `_modulo_tag()` separada, mas como ela apenas chama `_slug(modulo)`, o plan inlineia `modulo_tag = _slug(modulo)` diretamente em `salvar()` para evitar indireção desnecessária (YAGNI)

---

- [ ] **Step 1: Escrever os 9 testes que devem falhar**

Adicionar ao final de `jake_desktop/tests/test_brain.py`:

```python
# --- graph enrichment: tags, cliente, links ---

def test_salvar_tags_no_frontmatter(tmp_path):
    """Nota gerada contém tags: [output, copys]"""
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Copys", "Copy teste", {}, "output", "model")
    arquivo = list((vault_outputs / "Copys").glob("*.md"))[0]
    conteudo = arquivo.read_text(encoding="utf-8")
    assert "tags: [output, copys]" in conteudo


def test_salvar_modulo_tag_com_espaco(tmp_path):
    """'Site Architect' → tags: [output, site-architect]"""
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Site Architect", "Landing teste", {}, "html", "model")
    arquivo = list((vault_outputs / "Site Architect").glob("*.md"))[0]
    conteudo = arquivo.read_text(encoding="utf-8")
    assert "tags: [output, site-architect]" in conteudo


def test_salvar_cliente_no_frontmatter(tmp_path):
    """Com cliente='academia' → frontmatter tem cliente: academia"""
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    # Patchar VAULT (onde escreve) E VAULT_ROOT (onde _find_cliente_nota procura Clientes/)
    with patch("brain.VAULT", str(vault_outputs)), patch("brain.VAULT_ROOT", str(tmp_path)):
        brain.salvar("Copys", "Copy academia", {}, "output", "model", cliente="academia")
    arquivo = list((vault_outputs / "Copys").glob("*.md"))[0]
    conteudo = arquivo.read_text(encoding="utf-8")
    assert "cliente: academia" in conteudo


def test_salvar_sem_cliente_sem_campo(tmp_path):
    """Sem cliente= → frontmatter NÃO tem linha 'cliente:'"""
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Copys", "Copy sem cliente", {}, "output", "model")
    arquivo = list((vault_outputs / "Copys").glob("*.md"))[0]
    conteudo = arquivo.read_text(encoding="utf-8")
    assert "cliente:" not in conteudo


def test_salvar_links_section_com_cliente(tmp_path):
    """Com cliente matching → nota tem ## Links com [[stem]]"""
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    clientes_dir = tmp_path / "Clientes"
    clientes_dir.mkdir(parents=True)
    (clientes_dir / "clinica-cliente.md").write_text("Briefing clínica", encoding="utf-8")
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.VAULT_ROOT", str(tmp_path)):
            brain.salvar("Copys", "Copy clínica", {}, "output", "model", cliente="clinica")
    arquivo = list((vault_outputs / "Copys").glob("*.md"))[0]
    conteudo = arquivo.read_text(encoding="utf-8")
    assert "## Links" in conteudo
    assert "[[clinica-cliente]]" in conteudo


def test_salvar_sem_links_section_sem_cliente(tmp_path):
    """Sem cliente → nota NÃO tem seção ## Links"""
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Copys", "Copy sem link", {}, "output", "model")
    arquivo = list((vault_outputs / "Copys").glob("*.md"))[0]
    conteudo = arquivo.read_text(encoding="utf-8")
    assert "## Links" not in conteudo


def test_find_cliente_nota_match(tmp_path):
    """_find_cliente_nota('clinica') retorna 'clinica-cliente'"""
    clientes_dir = tmp_path / "Clientes"
    clientes_dir.mkdir(parents=True)
    (clientes_dir / "clinica-cliente.md").write_text("briefing", encoding="utf-8")
    with patch("brain.VAULT_ROOT", str(tmp_path)):
        resultado = brain._find_cliente_nota("clinica")
    assert resultado == "clinica-cliente"


def test_find_cliente_nota_sem_match(tmp_path):
    """_find_cliente_nota('xyz') retorna ''"""
    clientes_dir = tmp_path / "Clientes"
    clientes_dir.mkdir(parents=True)
    (clientes_dir / "piloti.md").write_text("briefing", encoding="utf-8")
    with patch("brain.VAULT_ROOT", str(tmp_path)):
        resultado = brain._find_cliente_nota("xyz-inexistente")
    assert resultado == ""


def test_find_cliente_nota_vazio():
    """_find_cliente_nota('') retorna '' sem tocar filesystem"""
    assert brain._find_cliente_nota("") == ""
```

- [ ] **Step 2: Rodar para confirmar que falham**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_brain.py -k "graph" -v 2>&1 | tail -15
```

Esperado: `FAILED` — `AttributeError: module 'brain' has no attribute '_find_cliente_nota'` e/ou `KeyError: 'modulo_tag'`

- [ ] **Step 3: Atualizar `TEMPLATE` em `brain.py`**

Substituir o `TEMPLATE` atual (linhas 14-34) por:

```python
TEMPLATE = """\
---
modulo: {modulo}
modelo: {model}
gerado_em: {gerado_em}
tags: [output, {modulo_tag}]
{cliente_linha}---

# {titulo}

## Inputs
{inputs_md}

## Output
{output}

## Modelo
{model}

## Observações
<!-- espaço para anotar no Obsidian depois -->
{links_section}"""
```

- [ ] **Step 4: Adicionar `_find_cliente_nota()` em `brain.py`**

Inserir imediatamente antes de `def salvar(`:

```python
def _find_cliente_nota(cliente: str) -> str:
    """Retorna stem do arquivo de briefing do cliente ou '' se não encontrar."""
    try:
        if not cliente:
            return ""
        if not os.path.isdir(VAULT_ROOT):
            return ""
        clientes_dir = os.path.join(VAULT_ROOT, "Clientes")
        if not os.path.isdir(clientes_dir):
            return ""
        slug_cliente = _slug(cliente)
        candidatos = []
        for raiz, dirs, arquivos in os.walk(clientes_dir):
            dirs[:] = [d for d in dirs if d != "_Template"]
            for nome in arquivos:
                if nome.endswith(".md"):
                    candidatos.append(os.path.join(raiz, nome))
        candidatos.sort(key=lambda p: os.path.basename(p))
        for caminho in candidatos:
            stem = os.path.splitext(os.path.basename(caminho))[0]
            slug_arquivo = _slug(stem)
            if slug_cliente in slug_arquivo or slug_arquivo in slug_cliente:
                return stem
        return ""
    except Exception as e:
        logging.warning(f"brain._find_cliente_nota falhou: {e}")
        return ""
```

- [ ] **Step 5: Atualizar `salvar()` em `brain.py`**

Substituir a assinatura e o bloco `conteudo = TEMPLATE.format(...)`:

**Assinatura** — mudar de:
```python
def salvar(modulo: str, titulo: str, inputs: dict, output: str, model: str) -> None:
```
para:
```python
def salvar(modulo: str, titulo: str, inputs: dict, output: str, model: str, cliente: str = "") -> None:
```

**Bloco `TEMPLATE.format()`** — substituir:
```python
        conteudo = TEMPLATE.format(
            modulo=modulo,
            model=model,
            gerado_em=gerado_em,
            titulo=titulo,
            inputs_md=_inputs_md(inputs or {}),
            output=output or "(sem output)",
        )
```
por:
```python
        modulo_tag = _slug(modulo)
        cliente_linha = f"cliente: {_slug(cliente)}\n" if cliente else ""
        stem = _find_cliente_nota(cliente) if cliente else ""
        links_section = f"\n## Links\n- [[{stem}]]\n" if stem else ""

        conteudo = TEMPLATE.format(
            modulo=modulo,
            model=model,
            gerado_em=gerado_em,
            titulo=titulo,
            inputs_md=_inputs_md(inputs or {}),
            output=output or "(sem output)",
            modulo_tag=modulo_tag,
            cliente_linha=cliente_linha,
            links_section=links_section,
        )
```

- [ ] **Step 6: Rodar todos os testes**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_brain.py -v 2>&1 | tail -15
```

Esperado: **33 passed** (24 existentes + 9 novos)

- [ ] **Step 7: Commit**

```bash
cd /root/jake_desktop
git add brain.py tests/test_brain.py
git commit -m "feat: brain.salvar() com tags, cliente e links automáticos no vault"
```

---

## Task 2: Wiring `cliente=` nas 4 chamadas `brain.salvar()` em `app.py`

**Files:**
- Modify: `jake_desktop/app.py`

**Contexto:**
- 4 chamadas existentes precisam de `cliente=` adicionado como último argumento
- As outras 7 chamadas NÃO devem ser tocadas

---

- [ ] **Step 1: Localizar as 4 chamadas alvo**

```bash
grep -n "brain.salvar" /root/jake_desktop/app.py
```

As 4 a modificar:
- Linha ~374: Carrossel (`modulo="Carrossel"`)
- Linha ~527: Copys (`modulo="Copys"`)
- Linha ~1475: Site Architect (`modulo="Site Architect"`)
- Linha ~1912: Anuncios (`modulo="Anuncios"`)

- [ ] **Step 2: Adicionar `cliente=theme` na chamada do Carrossel (linha ~374)**

Localizar o bloco:
```python
        brain.salvar(
            modulo="Carrossel",
            titulo=f"Carrossel {theme}",
            inputs={...},
            output=slides_texto,
            model="claude-sonnet-4-5",
        )
```

Adicionar `cliente=theme,` após `model="claude-sonnet-4-5",`:
```python
        brain.salvar(
            modulo="Carrossel",
            titulo=f"Carrossel {theme}",
            inputs={...},
            output=slides_texto,
            model="claude-sonnet-4-5",
            cliente=theme,
        )
```

- [ ] **Step 3: Adicionar `cliente=nicho` na chamada do Copys (linha ~527)**

Localizar o bloco com `modulo="Copys"` e adicionar `cliente=nicho,` após a linha `model=`:

```python
            model="claude-sonnet-4-6",
            cliente=nicho,
        )
```

- [ ] **Step 4: Adicionar `cliente=contexto[:80]` na chamada do Site Architect (linha ~1475)**

Localizar o bloco com `modulo="Site Architect"` (o `generate`, NÃO o `refine`). A variável local `contexto` existe nesta rota:
```python
contexto = (data.get("business_context") or "").strip()
```
Adicionar `cliente=contexto[:80],` após `model=`:

```python
            model="claude-sonnet-4-6",
            cliente=contexto[:80],
        )
```

⚠️ `contexto` é a variável local com o `business_context` — NÃO é a função `brain.contexto()`. Usar exatamente `contexto[:80]` (não `brain.contexto(...)`).

- [ ] **Step 5: Adicionar `cliente=cliente_nome` na chamada do Anuncios (linha ~1912)**

Localizar o bloco com `modulo="Anuncios"` e adicionar `cliente=cliente_nome,`:

```python
            model="claude-sonnet-4-6",
            cliente=cliente_nome,
        )
```

- [ ] **Step 6: Verificar sintaxe**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "import app; print('OK')" 2>&1 | head -3
```

Esperado: `OK`

- [ ] **Step 7: Confirmar contagem**

```bash
grep -c "cliente=" /root/jake_desktop/app.py
```

Esperado: `4` (apenas as 4 chamadas `brain.salvar()` — `brain.contexto()` usa argumentos posicionais)

Confirmar também que o total de `brain.salvar` ainda é 11 (7 intocadas + 4 modificadas):

```bash
grep -c "brain.salvar" /root/jake_desktop/app.py
```

Esperado: `11`

- [ ] **Step 8: Rodar testes**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_brain.py -q 2>&1 | tail -3
```

Esperado: `33 passed`

- [ ] **Step 9: Commit**

```bash
cd /root/jake_desktop
git add app.py
git commit -m "feat: passar cliente= para brain.salvar() nas 4 rotas elegíveis"
```

---

## Task 3: Adicionar wikilinks às 18 notas retroativas do vault

**Files:**
- Modify: 18 arquivos `.md` em `/root/jake-brain/`

**Contexto:**
- Vault em `/root/jake-brain/`
- Cada nota tem uma seção `## Links Relacionados` existente
- Regras: não duplicar links já presentes; não remover links existentes; substituir `[[Jake OS App (Rotas)]]` por `[[App-Rotas]]` onde encontrado
- Após editar, commitar no vault (git em `/root/jake-brain/`)

**Mapa de links a adicionar (por nota):**

| Arquivo | Links a adicionar |
|---|---|
| `Jake OS/Bots/jake-principal.md` | `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[Meta Ads/overview]]`, `[[sync-planilha]]`, `[[tarefas]]` |
| `Jake OS/Bots/jake-pessoal.md` | `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[jake-principal]]`, `[[tarefas]]` |
| `Jake OS/Bots/jake-viagem.md` | `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[jake-principal]]`, `[[tarefas]]` |
| `Jake OS/Bots/gerar-agente.md` | `[[jake-principal]]`, `[[App-Rotas]]`, `[[banco-de-dados]]` |
| `Jake OS/Core/banco-de-dados.md` | `[[App-Rotas]]`, `[[jake-principal]]`, `[[sync-planilha]]`, `[[tarefas]]`, `[[migrations]]` |
| `Jake OS/Core/sync-planilha.md` | `[[banco-de-dados]]`, `[[tarefas]]`, `[[utilitarios]]`, `[[App-Rotas]]` |
| `Jake OS/Core/tarefas.md` | `[[banco-de-dados]]`, `[[jake-principal]]`, `[[sync-planilha]]`, `[[App-Rotas]]` |
| `Jake OS/Core/utilitarios.md` | `[[banco-de-dados]]`, `[[sync-planilha]]`, `[[App-Rotas]]` |
| `Jake OS/Meta Ads/overview.md` | `[[App-Rotas]]`, `[[jake-principal]]`, `[[vps-scripts]]`, `[[banco-de-dados]]` |
| `Jake OS/App-Rotas.md` | `[[banco-de-dados]]`, `[[Frontend]]`, `[[Meta Ads/overview]]`, `[[jake-principal]]`, `[[vps-scripts]]` |
| `Jake OS/Frontend.md` | substituir `[[Jake OS App (Rotas)]]` → `[[App-Rotas]]`, adicionar `[[vps-scripts]]` |
| `Jake OS/Infraestrutura/vps-scripts.md` | `[[App-Rotas]]`, `[[docs-existentes]]` |
| `Jake OS/Infraestrutura/migrations.md` | `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[vps-scripts]]` |
| `Jake OS/Infraestrutura/docs-existentes.md` | `[[jake-principal]]`, `[[Arquitetura]]`, `[[vps-scripts]]`, substituir `[[Jake OS App (Rotas)]]` → `[[App-Rotas]]` se presente |
| `Jake OS/Arquitetura.md` | `[[App-Rotas]]`, `[[Frontend]]`, `[[banco-de-dados]]`, `[[jake-principal]]`, `[[vps-scripts]]` |
| `Projetos/carousel-engine.md` | `[[banco-de-dados]]`, `[[vps-scripts]]`, substituir `[[Jake OS App (Rotas)]]` → `[[App-Rotas]]` se presente, `[[Frontend]]` |
| `Clientes/clinica-cliente.md` | `[[App-Rotas]]`, `[[Frontend]]` |
| `Clientes/camila-piercer.md` | `[[App-Rotas]]`, `[[Frontend]]` |

---

Para cada nota: ler → localizar `## Links Relacionados` → checar quais links do mapa já existem → substituir `[[Jake OS App (Rotas)]]` por `[[App-Rotas]]` se presente → adicionar faltantes como `- [[nome]]`.

- [ ] **Step 1a: Bots (4 arquivos)**

Editar em sequência:
- `Jake OS/Bots/jake-principal.md` — adicionar: `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[Meta Ads/overview]]`, `[[sync-planilha]]`, `[[tarefas]]`
- `Jake OS/Bots/jake-pessoal.md` — adicionar: `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[jake-principal]]`, `[[tarefas]]`
- `Jake OS/Bots/jake-viagem.md` — adicionar: `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[jake-principal]]`, `[[tarefas]]`
- `Jake OS/Bots/gerar-agente.md` — adicionar: `[[jake-principal]]`, `[[App-Rotas]]`, `[[banco-de-dados]]`

- [ ] **Step 1b: Core (4 arquivos)**

- `Jake OS/Core/banco-de-dados.md` — adicionar: `[[App-Rotas]]`, `[[jake-principal]]`, `[[sync-planilha]]`, `[[tarefas]]`, `[[migrations]]`
- `Jake OS/Core/sync-planilha.md` — adicionar: `[[banco-de-dados]]`, `[[tarefas]]`, `[[utilitarios]]`, `[[App-Rotas]]`
- `Jake OS/Core/tarefas.md` — adicionar: `[[banco-de-dados]]`, `[[jake-principal]]`, `[[sync-planilha]]`, `[[App-Rotas]]`
- `Jake OS/Core/utilitarios.md` — adicionar: `[[banco-de-dados]]`, `[[sync-planilha]]`, `[[App-Rotas]]`

- [ ] **Step 1c: Meta Ads + App-Rotas + Frontend (3 arquivos)**

- `Jake OS/Meta Ads/overview.md` — adicionar: `[[App-Rotas]]`, `[[jake-principal]]`, `[[vps-scripts]]`, `[[banco-de-dados]]`
- `Jake OS/App-Rotas.md` — adicionar: `[[banco-de-dados]]`, `[[Frontend]]`, `[[Meta Ads/overview]]`, `[[jake-principal]]`, `[[vps-scripts]]`
- `Jake OS/Frontend.md` — substituir `[[Jake OS App (Rotas)]]` → `[[App-Rotas]]`, adicionar: `[[vps-scripts]]`

- [ ] **Step 1d: Infraestrutura + Arquitetura (4 arquivos)**

- `Jake OS/Infraestrutura/vps-scripts.md` — adicionar: `[[App-Rotas]]`, `[[docs-existentes]]`
- `Jake OS/Infraestrutura/migrations.md` — adicionar: `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[vps-scripts]]`
- `Jake OS/Infraestrutura/docs-existentes.md` — adicionar: `[[jake-principal]]`, `[[Arquitetura]]`, `[[vps-scripts]]`; substituir `[[Jake OS App (Rotas)]]` → `[[App-Rotas]]` se presente
- `Jake OS/Arquitetura.md` — adicionar: `[[App-Rotas]]`, `[[Frontend]]`, `[[banco-de-dados]]`, `[[jake-principal]]`, `[[vps-scripts]]`

- [ ] **Step 1e: Projetos + Clientes (3 arquivos)**

- `Projetos/carousel-engine.md` — adicionar: `[[banco-de-dados]]`, `[[vps-scripts]]`, `[[Frontend]]`; substituir `[[Jake OS App (Rotas)]]` → `[[App-Rotas]]` se presente
- `Clientes/clinica-cliente.md` — adicionar: `[[App-Rotas]]`, `[[Frontend]]`
- `Clientes/camila-piercer.md` — adicionar: `[[App-Rotas]]`, `[[Frontend]]`

- [ ] **Step 2: Verificar contagem de wikilinks após edição**

```bash
grep -r "\[\[" /root/jake-brain/Jake\ OS/ --include="*.md" | wc -l
```

Esperado: significativamente maior que 40 (o total anterior)

- [ ] **Step 3: Commitar no vault**

```bash
cd /root/jake-brain
git add "Jake OS/" Projetos/ Clientes/
git commit -m "feat: enriquece wikilinks nas 18 notas retroativas do vault"
```

(Não usar `git add -A` — evitar commitar acidentalmente notas de output geradas por `brain.salvar()` durante testes)

---

## Verificação Final

```bash
# 1. Testes do brain.py
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_brain.py -v 2>&1 | tail -5
# Esperado: 33 passed

# 2. Sintaxe do app.py
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "import app; print('OK')"
# Esperado: OK

# 3. Confirmar que todas as 11 chamadas brain.salvar() estão intactas
grep -c "brain.salvar" /root/jake_desktop/app.py
# Esperado: 11

# 3. Total de wikilinks no vault
grep -r "\[\[" /root/jake-brain/ --include="*.md" | grep -v "_Template" | grep -v "Decisoes" | wc -l
# Esperado: >120 (era ~40 antes)

# 4. Contagem de links por nota (nenhuma com menos de 5)
for f in $(find /root/jake-brain -name "*.md" | grep -v "_Template" | grep -v README | grep -v Roadmap | grep -v Decisoes); do
  count=$(grep -c "\[\[" "$f" 2>/dev/null || echo 0)
  echo "$count $f"
done | sort -n | head -10
```
