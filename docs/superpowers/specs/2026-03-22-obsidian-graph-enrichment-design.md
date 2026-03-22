# Obsidian Graph Enrichment — Design Spec

**Data:** 2026-03-22
**Projeto:** Jake Brain — Cérebro do ecossistema Jake IA
**Objetivo:** Enriquecer o grafo do Obsidian com tags, wikilinks automáticos nas notas de output e mais conexões nas notas retroativas.

---

## Contexto

O vault tem:
- 18 notas no vault (15 em `Jake OS/`, 1 em `Projetos/`, 2 em `Clientes/`) com tags e ~2-3 wikilinks cada
- Notas de output geradas por `brain.salvar()` sem tags e sem links
- Notas de cliente em `Clientes/` sem ligação com os outputs que as referenciam

O grafo do Obsidian é esparso porque os nós têm poucas arestas. Três intervenções atacam isso:

---

## Melhoria 1: Tags e campo `cliente` no TEMPLATE de output (`brain.py`)

### TEMPLATE atualizado

```markdown
---
modulo: {modulo}
modelo: {model}
gerado_em: {gerado_em}
tags: [output, {modulo_tag}]
cliente: {cliente_slug}
---
```

**Regras:**
- `modulo_tag`: slug do módulo em minúsculas, hífens no lugar de espaços e underscores
  - `"Copys"` → `copys`
  - `"Site Architect"` → `site-architect`
  - `"Carrossel"` → `carrossel`
  - Calculado com `_slug(modulo)` já existente
- `cliente_slug`: slug do nome do cliente fornecido, calculado com `_slug(cliente)`. Se `cliente` for vazio → campo omitido do frontmatter (linha não incluída)

### Implementação

Nova função privada `_modulo_tag(modulo: str) -> str`:
```python
def _modulo_tag(modulo: str) -> str:
    return _slug(modulo)
```

O `TEMPLATE` recebe `{modulo_tag}` e `{cliente_linha}` onde:
- `{cliente_linha}` = `f"cliente: {_slug(cliente)}\n"` se cliente não vazio, senão `""`

---

## Melhoria 2: Wikilink automático para nota do cliente (`brain.py`)

### Assinatura de `salvar()` — nova versão

```python
def salvar(modulo: str, titulo: str, inputs: dict, output: str, model: str, cliente: str = "") -> None
```

Parâmetro `cliente` é opcional — retrocompatível com todas as 11 chamadas existentes.

### Nova função privada: `_find_cliente_nota(cliente: str) -> str`

Retorna o stem do arquivo matching em `Clientes/` (ex: `"clinica-cliente"`) ou `""` se não encontrar. Usa a mesma lógica de slug bidirecional de `contexto()`:

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

### Seção `## Links` no TEMPLATE

Quando `_find_cliente_nota(cliente)` retorna um stem não vazio, a nota de output recebe:

```markdown
## Links
- [[{stem}]]
```

Se não houver cliente → seção `## Links` é omitida completamente.

### TEMPLATE completo atualizado

```
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
{links_section}
```

Onde:
- `{cliente_linha}` = `f"cliente: {_slug(cliente)}\n"` ou `""`
- `{links_section}` = `f"\n## Links\n- [[{stem}]]\n"` ou `""` (inclui `\n` inicial para separar da seção Observações)

**Nota sobre o TEMPLATE Python:** O TEMPLATE atual termina com `\n` após o comentário de Observações. O `{links_section}` é o último campo do TEMPLATE — quando vazio, o arquivo termina normalmente com `\n`; quando preenchido, a seção `## Links` aparece após uma linha em branco.

### Wiring em `app.py`

Adicionar `cliente=` nas 4 rotas que identificam o cliente:

| Rota | Campo | Valor passado |
|---|---|---|
| `/api/carousel/copy` | tema | `cliente=theme` |
| `/api/copys/gerar` | nicho | `cliente=nicho` |
| `/api/anuncios/copy` | cliente_nome | `cliente=cliente_nome` |
| `/api/site-architect/generate` | business_context | `cliente=contexto[:80]` |

As demais 7 chamadas existentes ficam sem `cliente=` — retrocompatível.

---

## Melhoria 3: Mais wikilinks nas notas retroativas

Edição de conteúdo nas **18 notas** do vault (15 em `Jake OS/` incluindo `Arquitetura.md`, 1 em `Projetos/`, 2 em `Clientes/`). Meta: **mínimo 5 wikilinks por nota**, adicionados na seção `## Links Relacionados` existente em cada nota.

### Mapa de links esperados (mínimo)

| Nota | Links a adicionar |
|---|---|
| `Bots/jake-principal.md` | `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[Meta Ads/overview]]`, `[[sync-planilha]]`, `[[tarefas]]` |
| `Bots/jake-pessoal.md` | `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[jake-principal]]`, `[[tarefas]]` |
| `Bots/jake-viagem.md` | `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[jake-principal]]`, `[[tarefas]]` |
| `Bots/gerar-agente.md` | `[[jake-principal]]`, `[[App-Rotas]]`, `[[banco-de-dados]]` |
| `Core/banco-de-dados.md` | `[[App-Rotas]]`, `[[jake-principal]]`, `[[sync-planilha]]`, `[[tarefas]]`, `[[migrations]]` |
| `Core/sync-planilha.md` | `[[banco-de-dados]]`, `[[tarefas]]`, `[[utilitarios]]`, `[[App-Rotas]]` |
| `Core/tarefas.md` | `[[banco-de-dados]]`, `[[jake-principal]]`, `[[sync-planilha]]`, `[[App-Rotas]]` |
| `Core/utilitarios.md` | `[[banco-de-dados]]`, `[[sync-planilha]]`, `[[App-Rotas]]` |
| `Meta Ads/overview.md` | `[[App-Rotas]]`, `[[jake-principal]]`, `[[vps-scripts]]`, `[[banco-de-dados]]` |
| `App-Rotas.md` | `[[banco-de-dados]]`, `[[Frontend]]`, `[[Meta Ads/overview]]`, `[[jake-principal]]`, `[[vps-scripts]]` |
| `Frontend.md` | Substituir `[[Jake OS App (Rotas)]]` por `[[App-Rotas]]` (padronização), adicionar `[[vps-scripts]]` |
| `Infraestrutura/vps-scripts.md` | `[[App-Rotas]]`, `[[docs-existentes]]` (os demais já existem: `[[jake-principal]]`, `[[banco-de-dados]]`, `[[migrations]]`) |
| `Infraestrutura/migrations.md` | `[[banco-de-dados]]`, `[[App-Rotas]]`, `[[vps-scripts]]` |
| `Infraestrutura/docs-existentes.md` | `[[jake-principal]]`, `[[Arquitetura]]`, `[[vps-scripts]]`, substituir `[[Jake OS App (Rotas)]]` por `[[App-Rotas]]` se presente |
| `Projetos/carousel-engine.md` | `[[banco-de-dados]]`, `[[vps-scripts]]`, substituir `[[Jake OS App (Rotas)]]` por `[[App-Rotas]]` se presente, `[[Frontend]]` |
| `Arquitetura.md` | `[[App-Rotas]]`, `[[Frontend]]`, `[[banco-de-dados]]`, `[[jake-principal]]`, `[[vps-scripts]]` |
| `Clientes/clinica-cliente.md` | `[[App-Rotas]]`, `[[Frontend]]` |
| `Clientes/camila-piercer.md` | `[[App-Rotas]]`, `[[Frontend]]` |

**Regras:**
- Links são adicionados à seção `## Links Relacionados` existente
- Não duplicar links já presentes
- Não remover links existentes
- **Padronização de alias:** qualquer `[[Jake OS App (Rotas)]]` encontrado deve ser substituído por `[[App-Rotas]]` (mesmo destino, wikilink padronizado)

---

## Testes

Arquivo: `jake_desktop/tests/test_brain.py`

| Teste | Descrição |
|---|---|
| `test_salvar_tags_no_frontmatter` | Nota gerada contém `tags: [output, copys]` |
| `test_salvar_modulo_tag_com_espaco` | `"Site Architect"` → `tags: [output, site-architect]` |
| `test_salvar_cliente_no_frontmatter` | Com `cliente="academia"` → frontmatter tem `cliente: academia` |
| `test_salvar_sem_cliente_sem_campo` | Sem `cliente=` → frontmatter não tem linha `cliente:` |
| `test_salvar_links_section_com_cliente` | Com cliente matching → nota tem `## Links\n- [[stem]]`. Setup: criar `tmp_path/Clientes/clinica-cliente.md` e patchar `brain.VAULT_ROOT` para `tmp_path`; passar `cliente="clinica"` para `salvar()`. Verificar que o arquivo gerado contém `[[clinica-cliente]]`. |
| `test_salvar_sem_links_section_sem_cliente` | Sem cliente → nota não tem `## Links` |
| `test_find_cliente_nota_match` | `_find_cliente_nota("clinica")` retorna `"clinica-cliente"` |
| `test_find_cliente_nota_sem_match` | `_find_cliente_nota("xyz")` retorna `""` |
| `test_find_cliente_nota_vazio` | `_find_cliente_nota("")` retorna `""` |

---

## Critérios de Sucesso

- [ ] Notas de output geradas a partir de agora têm `tags: [output, {modulo}]` no frontmatter
- [ ] Quando cliente é identificado, a nota tem `cliente: {slug}` no frontmatter e `## Links\n- [[stem]]`
- [ ] 4 rotas elegíveis passam `cliente=` para `brain.salvar()`
- [ ] 11 chamadas existentes sem `cliente=` continuam funcionando (retrocompatível)
- [ ] Todos os testes passam (24 existentes + 9 novos = 33)
- [ ] As 18 notas do vault têm ≥5 wikilinks cada em `## Links Relacionados`
- [ ] O grafo do Obsidian mostra clusters visíveis por tag e conexões cliente→output
