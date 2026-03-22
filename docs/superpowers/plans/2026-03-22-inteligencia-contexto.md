# Inteligência de Contexto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar `brain.contexto(cliente)` ao `brain.py` e injetá-la no system prompt de 4 rotas do Jake OS para que o Claude conheça o briefing do cliente antes de gerar conteúdo.

**Architecture:** Nova função pública em `brain.py` lê a nota de briefing em `jake-brain/Clientes/` via fuzzy match bidirecional, retorna o conteúdo como string. Cada rota elegível chama `brain.contexto()` antes do `client.messages.create()` e concatena o briefing ao system prompt existente. Falhas são silenciosas — a rota funciona normalmente se não houver briefing ou vault.

**Tech Stack:** Python stdlib (`os`, `pathlib`, `unicodedata`, `re`), pytest, Flask (nenhuma nova dependência).

---

## Arquivos

| Arquivo | Mudança |
|---|---|
| `jake_desktop/brain.py` | Adicionar função `contexto(cliente: str) -> str` |
| `jake_desktop/tests/test_brain.py` | Adicionar 9 novos testes para `contexto()` |
| `jake_desktop/app.py` | Wiring em 4 rotas (linhas ~339-345, ~509-515, ~1856-1880, ~1455-1462) |

---

## Task 1: Implementar `brain.contexto()` com TDD

**Files:**
- Modify: `jake_desktop/brain.py` (adicionar função após `salvar()`)
- Modify: `jake_desktop/tests/test_brain.py` (adicionar 8 testes)

**Contexto para o implementador:**
- `brain.py` já tem `_slug()` (normaliza texto para slug) — reusar aqui
- `VAULT_ROOT = "/root/jake-brain"` — usar esse caminho pra checar existência
- Clientes ficam em `/root/jake-brain/Clientes/`
- Excluir arquivos cujo caminho contenha componente de diretório `_Template`
- Match bidirecional: `slug_cliente in slug_arquivo` OU `slug_arquivo in slug_cliente`
- Iterar arquivos em ordem alfabética; retornar primeiro match
- `try/except Exception` completo — nunca propagar

---

- [ ] **Step 1: Escrever os testes que devem falhar**

Adicionar ao final de `jake_desktop/tests/test_brain.py`:

```python
# --- contexto ---

def test_contexto_match_exato(tmp_path):
    """'clinica' encontra clinica-cliente.md (slug cliente in slug arquivo)"""
    clientes_dir = tmp_path / "Clientes"
    clientes_dir.mkdir(parents=True)
    nota = clientes_dir / "clinica-cliente.md"
    nota.write_text("# Clínica\nTom: sofisticado", encoding="utf-8")

    with patch("brain.VAULT_ROOT", str(tmp_path)):
        resultado = brain.contexto("clinica")

    assert "Clínica" in resultado
    assert "sofisticado" in resultado


def test_contexto_match_parcial(tmp_path):
    """'academia' encontra academia-fitness.md (slug cliente in slug arquivo)"""
    clientes_dir = tmp_path / "Clientes"
    clientes_dir.mkdir(parents=True)
    (clientes_dir / "academia-fitness.md").write_text("Briefing academia", encoding="utf-8")

    with patch("brain.VAULT_ROOT", str(tmp_path)):
        resultado = brain.contexto("academia")

    assert "Briefing academia" in resultado


def test_contexto_match_inverso(tmp_path):
    """'clinica-aline-estetica' encontra clinica.md (slug arquivo in slug cliente)"""
    clientes_dir = tmp_path / "Clientes"
    clientes_dir.mkdir(parents=True)
    (clientes_dir / "clinica.md").write_text("Briefing clinica curto", encoding="utf-8")

    with patch("brain.VAULT_ROOT", str(tmp_path)):
        resultado = brain.contexto("clinica-aline-estetica")

    assert "Briefing clinica curto" in resultado


def test_contexto_sem_match(tmp_path):
    """Nenhum arquivo faz match → retorna string vazia"""
    clientes_dir = tmp_path / "Clientes"
    clientes_dir.mkdir(parents=True)
    (clientes_dir / "piloti.md").write_text("Briefing piloti", encoding="utf-8")

    with patch("brain.VAULT_ROOT", str(tmp_path)):
        resultado = brain.contexto("xyz-inexistente")

    assert resultado == ""


def test_contexto_cliente_vazio():
    """cliente='' retorna '' sem tocar filesystem"""
    assert brain.contexto("") == ""


def test_contexto_cliente_none():
    """cliente=None retorna '' sem tocar filesystem"""
    assert brain.contexto(None) == ""


def test_contexto_vault_inexistente():
    """Vault inexistente → retorna '' sem propagar exceção"""
    with patch("brain.VAULT_ROOT", "/caminho/que/nao/existe"):
        resultado = brain.contexto("qualquer")
    assert resultado == ""


def test_contexto_exclui_template(tmp_path):
    """Arquivos em _Template/ são ignorados"""
    clientes_dir = tmp_path / "Clientes"
    template_dir = clientes_dir / "_Template"
    template_dir.mkdir(parents=True)
    (template_dir / "briefing.md").write_text("Template genérico", encoding="utf-8")
    (clientes_dir / "piloti.md").write_text("Briefing real", encoding="utf-8")

    with patch("brain.VAULT_ROOT", str(tmp_path)):
        # "briefing" está apenas no _Template — não deve ser encontrado
        resultado = brain.contexto("briefing")

    assert resultado == ""


def test_contexto_retorna_conteudo(tmp_path):
    """Verifica que o conteúdo completo da nota é retornado corretamente"""
    clientes_dir = tmp_path / "Clientes"
    clientes_dir.mkdir(parents=True)
    conteudo_esperado = "# Piloti\n\nTom: jovem e urbano\nProduto: camisetas premium\nPublico: 18-35 anos"
    (clientes_dir / "piloti.md").write_text(conteudo_esperado, encoding="utf-8")

    with patch("brain.VAULT_ROOT", str(tmp_path)):
        resultado = brain.contexto("piloti")

    assert resultado == conteudo_esperado
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -m pytest tests/test_brain.py::test_contexto_match_exato -v
```

Esperado: `FAILED` com `AttributeError: module 'brain' has no attribute 'contexto'`

- [ ] **Step 3: Adicionar `VAULT_ROOT` e implementar `contexto()` em `brain.py`**

Adicionar logo após a linha `VAULT = "/root/jake-brain/Jake OS/Outputs"`:

```python
VAULT_ROOT = "/root/jake-brain"
```

Adicionar a função após `salvar()`, no final do arquivo:

```python
def contexto(cliente: str) -> str:
    """
    Retorna o conteúdo da nota de briefing do cliente no vault Obsidian.
    Faz fuzzy match bidirecional: slug_cliente in slug_arquivo OU slug_arquivo in slug_cliente.
    Arquivos em _Template/ são ignorados.
    Retorna '' se não encontrar match, vault ausente ou qualquer erro.
    Nunca propaga exceção.
    """
    try:
        if not cliente:
            return ""
        if not os.path.isdir(VAULT_ROOT):
            logging.warning(f"brain.contexto: vault {VAULT_ROOT} não encontrado.")
            return ""

        clientes_dir = os.path.join(VAULT_ROOT, "Clientes")
        if not os.path.isdir(clientes_dir):
            return ""

        slug_cliente = _slug(cliente)

        # Coletar e ordenar arquivos .md alfabeticamente, excluindo _Template/
        candidatos = []
        for raiz, dirs, arquivos in os.walk(clientes_dir):
            # Excluir diretórios _Template da busca
            dirs[:] = [d for d in dirs if d != "_Template"]
            for nome in arquivos:
                if nome.endswith(".md"):
                    candidatos.append(os.path.join(raiz, nome))
        candidatos.sort(key=lambda p: os.path.basename(p))

        for caminho in candidatos:
            nome_sem_ext = os.path.splitext(os.path.basename(caminho))[0]
            slug_arquivo = _slug(nome_sem_ext)
            if slug_cliente in slug_arquivo or slug_arquivo in slug_cliente:
                with open(caminho, encoding="utf-8") as f:
                    return f.read()

        return ""

    except Exception as e:
        logging.warning(f"brain.contexto falhou: {e}")
        return ""
```

- [ ] **Step 4: Rodar todos os testes**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -m pytest tests/test_brain.py -v
```

Esperado: **23 passed** (15 existentes + 8 novos)

- [ ] **Step 5: Commit**

```bash
cd /root/jake_desktop
git add brain.py tests/test_brain.py
git commit -m "feat: brain.contexto() — lê briefing do cliente no vault (TDD)"
```

---

## Task 2: Wiring — injetar `brain.contexto()` nas 4 rotas elegíveis

**Files:**
- Modify: `jake_desktop/app.py` (4 pontos cirúrgicos)

**Contexto para o implementador:**

Padrão de injeção para rotas que usam constante de módulo (`_CAROUSEL_SYSTEM`, `_COPYS_SYSTEM`, `_SITE_ARCH_SYSTEM`):

```python
ctx = brain.contexto(campo_cliente)
_sys = _CONSTANTE_SYSTEM + f"\n\n## Briefing do Cliente\n{ctx}" if ctx else _CONSTANTE_SYSTEM
# Substituir system=_CONSTANTE_SYSTEM por system=_sys na chamada API
```

Padrão para rota com variável local `system` (anuncios):

```python
ctx = brain.contexto(cliente_nome)
if ctx:
    system = system + f"\n\n## Briefing do Cliente\n{ctx}"
```

**REGRA:** O `brain.contexto()` vai sempre ANTES do `client.messages.create()`. Nunca dentro do `try` que já envolve o create — colocar imediatamente antes.

---

### Rota 1: `/api/carousel/copy` (linha ~340)

Campo cliente: `theme` (linha 325: `theme = (data.get("theme") or "").strip()`)
System prompt: `_CAROUSEL_SYSTEM` (usado em `system=_CAROUSEL_SYSTEM` na linha ~343)

- [ ] **Step 1: Localizar o ponto de injeção**

```bash
grep -n "_CAROUSEL_SYSTEM" /root/jake_desktop/app.py
```

Esperado: linha ~343 com `system=_CAROUSEL_SYSTEM,`

- [ ] **Step 2: Adicionar injeção antes do `client.messages.create()`**

Imediatamente antes da linha `msg = client.messages.create(`, adicionar:

```python
        ctx = brain.contexto(theme)
        system_prompt = _CAROUSEL_SYSTEM
        if ctx:
            system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
```

Substituir `system=_CAROUSEL_SYSTEM,` por `system=system_prompt,`

- [ ] **Step 3: Verificar sintaxe**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "import app" 2>&1 | head -5
```

Esperado: sem output (importação limpa)

---

### Rota 2: `/api/copys/gerar` (linha ~510)

Campo cliente: `nicho` (linha 460: `nicho = (data.get("nicho") or "").strip()`)
System prompt: `_COPYS_SYSTEM` (usado em `system=_COPYS_SYSTEM` na linha ~513)

- [ ] **Step 4: Localizar o ponto de injeção**

```bash
grep -n "_COPYS_SYSTEM" /root/jake_desktop/app.py
```

Esperado: linha ~513 com `system=_COPYS_SYSTEM,`

- [ ] **Step 5: Adicionar injeção**

Imediatamente antes de `msg = client.messages.create(` (linha ~510), adicionar:

```python
        ctx = brain.contexto(nicho)
        system_prompt = _COPYS_SYSTEM
        if ctx:
            system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
```

Substituir `system=_COPYS_SYSTEM,` por `system=system_prompt,`

- [ ] **Step 6: Verificar sintaxe**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "import app" 2>&1 | head -5
```

---

### Rota 3: `/api/anuncios/copy` (linha ~1856)

Campo cliente: `cliente_nome` (linha 1849: `cliente_nome = d.get("cliente_nome", "cliente")`)
System prompt: variável local `system` (definida em linha ~1856 como string)

- [ ] **Step 7: Localizar o ponto de injeção**

```bash
grep -n "def anuncios_gerar_copy" /root/jake_desktop/app.py
```

Ler ~30 linhas a partir daí para encontrar onde `system = (...)` termina e a chamada API começa.

- [ ] **Step 8: Adicionar injeção após definição da variável `system`, antes do API call**

Após a linha onde `system = (...)` está completo e antes de `client.messages.create(`:

```python
    ctx = brain.contexto(cliente_nome)
    if ctx:
        system = system + f"\n\n## Briefing do Cliente\n{ctx}"
```

A variável `system` já existe no escopo — apenas concatenar se `ctx` não for vazio.

- [ ] **Step 9: Verificar sintaxe**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "import app" 2>&1 | head -5
```

---

### Rota 4: `/api/site-architect/generate` (linha ~1455)

Campo cliente: `contexto` (linha 1318: `contexto = (data.get("business_context") or "").strip()`)
System prompt: `_SITE_ARCH_SYSTEM` (usado em `system=_SITE_ARCH_SYSTEM` na linha ~1459)

**⚠️ ATENÇÃO:** A variável local `contexto` já existe nessa rota (guarda o `business_context`). Usar `ctx` para o resultado de `brain.contexto()` — NÃO usar `contexto` como nome da variável de retorno.

- [ ] **Step 10: Localizar o ponto de injeção**

```bash
grep -n "_SITE_ARCH_SYSTEM" /root/jake_desktop/app.py
```

Esperado: linha ~1459 com `system=_SITE_ARCH_SYSTEM,`

- [ ] **Step 11: Adicionar injeção**

Imediatamente antes de `msg = client.messages.create(` (linha ~1456), adicionar:

```python
        ctx = brain.contexto(contexto[:80])
        system_prompt = _SITE_ARCH_SYSTEM
        if ctx:
            system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
```

Substituir `system=_SITE_ARCH_SYSTEM,` por `system=system_prompt,`

**Nota:** A segunda chamada ao `_SITE_ARCH_SYSTEM` é `/api/site-architect/refine` — essa rota NÃO tem campo de cliente identificável, então NÃO injetar contexto nela.

- [ ] **Step 12: Verificar sintaxe final**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "import app" 2>&1 | head -5
```

---

- [ ] **Step 13: Rodar todos os testes**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -m pytest tests/test_brain.py -v
```

Esperado: **23 passed**

- [ ] **Step 14: Contar injeções para confirmar**

```bash
grep -c "brain.contexto" /root/jake_desktop/app.py
```

Esperado: `4`

- [ ] **Step 15: Commit**

```bash
cd /root/jake_desktop
git add app.py
git commit -m "feat: injetar brain.contexto() nas rotas Carousel, Copys, Anuncios e Site Architect"
```

---

## Verificação Final

Após as duas tasks:

```bash
# 1. Todos os testes passam
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -m pytest tests/test_brain.py -v
# Esperado: 23 passed

# 2. Sintaxe ok
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "import app; print('OK')" 2>&1

# 3. Contagem de injeções
grep -n "brain.contexto" /root/jake_desktop/app.py
# Esperado: 4 linhas
```

**Teste manual (opcional):**
1. Criar `/root/jake-brain/Clientes/academia.md` com qualquer texto
2. Subir o Jake OS: `cd /root/jake_desktop && source venv/bin/activate && python app.py`
3. Gerar copy com nicho "academia"
4. Verificar nos logs que o system prompt contém "Briefing do Cliente"
