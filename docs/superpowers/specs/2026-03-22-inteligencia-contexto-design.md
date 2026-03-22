# Inteligência de Contexto — Design Spec

**Data:** 2026-03-22
**Projeto:** Jake Brain — Cérebro do ecossistema Jake IA
**Sub-projeto:** 4 de 4 — Inteligência de Contexto (Claude lê vault antes de gerar)

---

## Objetivo

Antes de gerar conteúdo, o Jake OS lê o briefing do cliente armazenado no vault Obsidian (`/root/jake-brain/Clientes/`) e injeta esse contexto no system prompt da chamada à API de IA. Isso permite que o modelo conheça o tom, produto, persona e decisões do cliente sem que o usuário precise repetir essas informações a cada geração.

---

## Arquitetura

### Modificação: `jake_desktop/brain.py`

Nova função pública:

```python
def contexto(cliente: str) -> str
```

**Algoritmo:**

1. Se `cliente` for vazio ou `None` → retorna `""`
2. Se `/root/jake-brain/` não existir → loga warning, retorna `""`
3. Lista todos os arquivos `.md` em `jake-brain/Clientes/` recursivamente, ordenados alfabeticamente por nome de arquivo. Excluir qualquer arquivo cujo caminho contenha um componente de diretório chamado `_Template` (ex: `Clientes/_Template/Briefing.md` → excluído)
4. Slugifica `cliente` com `_slug()` já existente em `brain.py` → `slug_cliente`
5. Para cada arquivo (em ordem alfabética), slugifica o nome do arquivo sem extensão → `slug_arquivo`
6. **Match bidirecional:** considera match se `slug_cliente in slug_arquivo` **OU** `slug_arquivo in slug_cliente`
7. Retorna o conteúdo completo da nota (str) do **primeiro match** na ordem alfabética
8. Se nenhum match → retorna `""`
9. `try/except Exception` completo — nunca propaga exceção, loga warning em caso de erro

**Exemplos de match bidirecional:**

| Input cliente | Slug cliente | Arquivo | Slug arquivo | Match? | Direção |
|---|---|---|---|---|---|
| `"clinica"` | `"clinica"` | `clinica-cliente.md` | `"clinica-cliente"` | ✅ | cliente in arquivo |
| `"academia top"` | `"academia-top"` | `academia.md` | `"academia"` | ✅ | arquivo in cliente |
| `"academia top"` | `"academia-top"` | `academia-fitness.md` | `"academia-fitness"` | ❌ | nenhuma direção |
| `"piloti"` | `"piloti"` | `piloti-agencia.md` | `"piloti-agencia"` | ✅ | cliente in arquivo |

**Comportamento de erro:**
- Qualquer exceção → `logging.warning(f"brain.contexto falhou: {e}")`, retorna `""`
- Vault ausente → loga, retorna `""`
- Nenhum match → retorna `""` silenciosamente (sem log)

---

### Modificação: `jake_desktop/app.py`

Para cada rota elegível, chamar `brain.contexto()` antes da chamada à API de IA e injetar o resultado no system prompt.

**Padrão de injeção:**

```python
ctx = brain.contexto(campo_cliente)
if ctx:
    system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
```

Onde `system_prompt` é a string do prompt de sistema já definida na rota.

---

## Mapeamento de Rotas

| Rota | Campo identificador | Variável |
|---|---|---|
| `POST /api/copys/gerar` | nicho | `nicho` |
| `POST /api/carousel/copy` | tema | `theme` |
| `POST /api/anuncios/copy` | cliente_nome | `cliente_nome` |
| `POST /api/site-architect/generate` | business_context (primeiros 80 chars) | `contexto[:80]` ⚠️ ver nota abaixo |
| `POST /api/financeiro/analise` | — | skip silencioso |
| `POST /api/criativos/expandir-prompt` | — | skip silencioso |
| `POST /api/criativos/gerar-imagem` | — | skip silencioso |
| `POST /api/criativos/gerar-video` | — | skip silencioso |
| `POST /api/site-architect/refine` | — | skip silencioso |

**Rotas com skip silencioso:** `brain.contexto("")` retorna `""` → `if ctx` é falso → system prompt inalterado → rota funciona normalmente.

**⚠️ Nota — colisão de nomes em `site-architect/generate`:** Nessa rota, a variável local `contexto` já existe (guarda o `business_context`). O resultado de `brain.contexto()` deve ser atribuído a `ctx` (não a `contexto`) para evitar sobrescrever a variável local. Implementação correta:

```python
ctx = brain.contexto(contexto[:80])  # `contexto` = variável local com business_context
if ctx:
    system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
```

---

## Estrutura das Notas de Briefing

Os arquivos em `jake-brain/Clientes/` já existem (criados no Brain Retroativo). O sistema lê o conteúdo completo da nota como texto e injeta no prompt. Nenhuma estrutura especial é exigida — o modelo interpreta o markdown naturalmente.

Exemplo de nota existente: `jake-brain/Clientes/clinica-cliente.md`

---

## Edge Cases

| Situação | Comportamento |
|---|---|
| Vault `/root/jake-brain/` não existe | Loga warning, retorna `""`, rota não afetada |
| Nenhum arquivo em `Clientes/` | Retorna `""` silenciosamente |
| Nenhum match encontrado | Retorna `""` silenciosamente |
| Nota do cliente está vazia | Retorna `""` (conteúdo vazio = sem injeção) |
| Exceção ao ler arquivo | Loga warning, retorna `""` |
| `cliente` é `None` ou `""` | Retorna `""` imediatamente (guard clause) |
| Múltiplos matches | Retorna o primeiro match em ordem alfabética por nome de arquivo |

---

## Testes

Arquivo: `jake_desktop/tests/test_brain.py` (já existe — adicionar novos casos)

Casos a cobrir:

| Teste | Descrição |
|---|---|
| `test_contexto_match_exato` | `contexto("clinica")` encontra `clinica-cliente.md` |
| `test_contexto_match_parcial` | `contexto("academia")` encontra `academia-fitness.md` (cliente in arquivo) |
| `test_contexto_match_inverso` | `contexto("clinica-aline-estetica")` encontra `clinica.md` (arquivo in cliente) |
| `test_contexto_sem_match` | `contexto("xyz-inexistente")` retorna `""` |
| `test_contexto_cliente_vazio` | `contexto("")` retorna `""` sem tocar filesystem |
| `test_contexto_cliente_none` | `contexto(None)` retorna `""` sem tocar filesystem |
| `test_contexto_vault_inexistente` | vault path inválido → retorna `""`, não propaga |
| `test_contexto_retorna_conteudo` | verifica que o conteúdo da nota é retornado corretamente |

---

## Critérios de Sucesso

- [ ] `brain.contexto("clinica")` retorna o conteúdo de `Clientes/clinica-cliente.md`
- [ ] `brain.contexto("")` retorna `""` sem erros
- [ ] Ao gerar copy com nicho "clinica", o system prompt inclui o briefing da clínica
- [ ] Rotas sem cliente identificável (Criativos, Financeiro) continuam funcionando normalmente
- [ ] Erros em `brain.contexto()` nunca quebram nenhuma rota
- [ ] Todos os testes passam
