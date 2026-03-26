# Brain Retroativo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Documentar todos os 17 componentes do projeto Jake no vault Obsidian, gerando notas completas com script + preenchimento por Claude.

**Architecture:** Script Python gera 17 `.md` stubs com `[TODO]` no vault `/root/jake-brain/`. Claude então lê cada componente e preenche o conteúdo real. Commits frequentes, push automático via cron a cada 5 min.

**Tech Stack:** Python 3, arquivos `.md`, vault `/root/jake-brain/`, git

**Spec:** `docs/superpowers/specs/2026-03-22-brain-retroativo-design.md`

---

## File Map

| Arquivo | Ação |
|---|---|
| `scripts/gerar_brain.py` | Criar — gera os 17 stubs |
| `jake-brain/Jake OS/Bots/jake-principal.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Bots/jake-pessoal.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Bots/jake-viagem.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Bots/gerar-agente.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Core/banco-de-dados.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Core/sync-planilha.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Core/tarefas.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Core/utilitarios.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Meta Ads/overview.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/App-Rotas.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Frontend.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Infraestrutura/vps-scripts.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Infraestrutura/migrations.md` | Criar (stub) → preencher |
| `jake-brain/Jake OS/Infraestrutura/docs-existentes.md` | Criar (stub) → preencher |
| `jake-brain/Projetos/carousel-engine.md` | Criar (stub) → preencher |
| `jake-brain/Clientes/clinica-cliente.md` | Criar (stub) → preencher |
| `jake-brain/Clientes/camila-piercer.md` | Criar (stub) → preencher |

---

## Task 1: Script gerar_brain.py

**Files:**
- Create: `scripts/gerar_brain.py`

- [ ] **Step 1: Criar o script**

```python
#!/usr/bin/env python3
"""
gerar_brain.py — Gera estrutura de notas no vault jake-brain para cada componente do Jake.
Uso: cd /root && python3 scripts/gerar_brain.py
Regra: se o arquivo já existe, pula (não sobrescreve nunca).
"""
import os
from datetime import date

VAULT = "/root/jake-brain"
TODAY = date.today().isoformat()

COMPONENTES = [
    {
        "arquivo": "Jake OS/Bots/jake-principal.md",
        "nome": "Bot Principal",
        "tipo": "bot",
        "caminho": "/root/jake_telegram.py + /root/bot/base_bot.py",
        "arquivos": ["/root/jake_telegram.py", "/root/bot/base_bot.py"],
        "tags": ["jake", "bot", "telegram"],
    },
    {
        "arquivo": "Jake OS/Bots/jake-pessoal.md",
        "nome": "Bot Pessoal",
        "tipo": "bot",
        "caminho": "/root/bot/jake_pessoal.py",
        "arquivos": ["/root/bot/jake_pessoal.py", "/root/bot/prompt_pessoal.txt"],
        "tags": ["jake", "bot", "telegram", "pessoal"],
    },
    {
        "arquivo": "Jake OS/Bots/jake-viagem.md",
        "nome": "Bot Viagem",
        "tipo": "bot",
        "caminho": "/root/bot/jake_viagem.py",
        "arquivos": ["/root/bot/jake_viagem.py", "/root/bot/prompt_viagem.txt"],
        "tags": ["jake", "bot", "telegram", "viagem"],
    },
    {
        "arquivo": "Jake OS/Bots/gerar-agente.md",
        "nome": "Gerador de Agentes",
        "tipo": "bot",
        "caminho": "/root/bot/gerar_agente.py",
        "arquivos": ["/root/bot/gerar_agente.py"],
        "tags": ["jake", "bot", "meta-agente"],
    },
    {
        "arquivo": "Jake OS/Core/banco-de-dados.md",
        "nome": "Banco de Dados",
        "tipo": "core",
        "caminho": "/root/core/db.py",
        "arquivos": ["/root/core/db.py"],
        "tags": ["jake", "core", "database", "neon", "postgresql"],
    },
    {
        "arquivo": "Jake OS/Core/sync-planilha.md",
        "nome": "Sync Planilha",
        "tipo": "core",
        "caminho": "/root/core/sync_planilha.py",
        "arquivos": ["/root/core/sync_planilha.py"],
        "tags": ["jake", "core", "google-sheets"],
    },
    {
        "arquivo": "Jake OS/Core/tarefas.md",
        "nome": "Tarefas",
        "tipo": "core",
        "caminho": "/root/core/tarefas.py",
        "arquivos": ["/root/core/tarefas.py"],
        "tags": ["jake", "core"],
    },
    {
        "arquivo": "Jake OS/Core/utilitarios.md",
        "nome": "Utilitários",
        "tipo": "script",
        "caminho": "/root/",
        "arquivos": ["/root/leitor_planilha.py", "/root/listar_ids.py"],
        "tags": ["jake", "utilitarios"],
    },
    {
        "arquivo": "Jake OS/Meta Ads/overview.md",
        "nome": "Meta Ads",
        "tipo": "integração",
        "caminho": "/root/meta/",
        "arquivos": ["/root/meta/meta_api.py", "/root/meta/checar_saldo_meta.py", "/root/meta/config_meta.py"],
        "tags": ["jake", "meta-ads", "facebook"],
    },
    {
        "arquivo": "Jake OS/App-Rotas.md",
        "nome": "Jake OS App (Rotas)",
        "tipo": "flask",
        "caminho": "/root/jake_desktop/app.py",
        "arquivos": ["/root/jake_desktop/app.py"],
        "tags": ["jake", "flask", "backend"],
    },
    {
        "arquivo": "Jake OS/Frontend.md",
        "nome": "Jake OS Frontend",
        "tipo": "frontend",
        "caminho": "/root/jake_desktop/static/js/",
        "arquivos": [],
        "tags": ["jake", "frontend", "javascript"],
    },
    {
        "arquivo": "Jake OS/Infraestrutura/vps-scripts.md",
        "nome": "Scripts e Infraestrutura",
        "tipo": "script",
        "caminho": "/root/scripts/",
        "arquivos": [],
        "tags": ["jake", "infraestrutura", "scripts"],
    },
    {
        "arquivo": "Jake OS/Infraestrutura/migrations.md",
        "nome": "Migrations",
        "tipo": "script",
        "caminho": "/root/scripts/",
        "arquivos": ["/root/scripts/migrar_anuncios.py", "/root/scripts/migrar_criativos.py"],
        "tags": ["jake", "database", "migration"],
    },
    {
        "arquivo": "Jake OS/Infraestrutura/docs-existentes.md",
        "nome": "Documentação Existente",
        "tipo": "docs",
        "caminho": "/root/docs/",
        "arquivos": [],
        "tags": ["jake", "docs"],
    },
    {
        "arquivo": "Projetos/carousel-engine.md",
        "nome": "Carousel Engine",
        "tipo": "projeto",
        "caminho": "/root/carousel-engine/",
        "arquivos": [],
        "tags": ["jake", "projeto", "nextjs"],
    },
    {
        "arquivo": "Clientes/clinica-cliente.md",
        "nome": "Clínica Cliente",
        "tipo": "site",
        "caminho": "/root/clinica-cliente/",
        "arquivos": ["/root/clinica-cliente/index.html", "/root/clinica-cliente/sitealine.html"],
        "tags": ["jake", "cliente", "site"],
    },
    {
        "arquivo": "Clientes/camila-piercer.md",
        "nome": "Camila Piercer",
        "tipo": "site",
        "caminho": "/root/camila_piercerr_2.html",
        "arquivos": ["/root/camila_piercerr_2.html"],
        "tags": ["jake", "cliente", "site"],
    },
]

TEMPLATE = """---
tipo: {tipo}
caminho: {caminho}
tags: {tags}
gerado_em: {hoje}
---

# {nome}

## Arquivos
{arquivos_lista}

## O que faz
[TODO]

## Como funciona
[TODO]

## Variáveis de Ambiente
[TODO]

## Dependências
[TODO]

## Decisões Tomadas
[TODO]

## Próximos Passos
[TODO]

## Links Relacionados
[TODO]
"""

IGNORAR = {"venv", ".venv", "node_modules", "__pycache__", ".git", ".local", ".npm", ".cache", "jake-brain"}


def listar_arquivos_dir(caminho):
    resultado = []
    if os.path.isdir(caminho):
        for f in sorted(os.listdir(caminho)):
            if f in IGNORAR or f.startswith("."):
                continue
            fp = os.path.join(caminho, f)
            if os.path.isfile(fp):
                resultado.append(fp)
    return resultado


def gerar_nota(comp):
    arquivos = comp["arquivos"]
    if not arquivos:
        arquivos = listar_arquivos_dir(comp["caminho"])
    arquivos_lista = "\n".join(f"- `{a}`" for a in arquivos) if arquivos else "- (nenhum arquivo detectado)"
    tags_str = "[" + ", ".join(comp["tags"]) + "]"
    return TEMPLATE.format(
        tipo=comp["tipo"],
        caminho=comp["caminho"],
        tags=tags_str,
        hoje=TODAY,
        nome=comp["nome"],
        arquivos_lista=arquivos_lista,
    )


def main():
    criados = 0
    pulados = 0
    for comp in COMPONENTES:
        destino = os.path.join(VAULT, comp["arquivo"])
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        if os.path.exists(destino):
            print(f"[PULADO]  {comp['arquivo']}")
            pulados += 1
            continue
        conteudo = gerar_nota(comp)
        with open(destino, "w", encoding="utf-8") as f:
            f.write(conteudo)
        print(f"[CRIADO]  {comp['arquivo']}")
        criados += 1
    print(f"\nConcluído: {criados} criados, {pulados} pulados.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificar que jake-brain é um repositório git**

```bash
git -C /root/jake-brain status
```

Expected: `On branch main` (vault já existe como repo git desde sub-projeto 1)

- [ ] **Step 3: Rodar o script e verificar**

```bash
cd /root && python3 scripts/gerar_brain.py
```

Expected:
```
[CRIADO]  Jake OS/Bots/jake-principal.md
[CRIADO]  Jake OS/Bots/jake-pessoal.md
[CRIADO]  Jake OS/Bots/jake-viagem.md
[CRIADO]  Jake OS/Bots/gerar-agente.md
[CRIADO]  Jake OS/Core/banco-de-dados.md
[CRIADO]  Jake OS/Core/sync-planilha.md
[CRIADO]  Jake OS/Core/tarefas.md
[CRIADO]  Jake OS/Core/utilitarios.md
[CRIADO]  Jake OS/Meta Ads/overview.md
[CRIADO]  Jake OS/App-Rotas.md
[CRIADO]  Jake OS/Frontend.md
[CRIADO]  Jake OS/Infraestrutura/vps-scripts.md
[CRIADO]  Jake OS/Infraestrutura/migrations.md
[CRIADO]  Jake OS/Infraestrutura/docs-existentes.md
[CRIADO]  Projetos/carousel-engine.md
[CRIADO]  Clientes/clinica-cliente.md
[CRIADO]  Clientes/camila-piercer.md
Concluído: 17 criados, 0 pulados.
```

- [ ] **Step 4: Confirmar arquivos criados**

```bash
find /root/jake-brain -name "*.md" | grep -v "\.obsidian" | sort
```

Expected: todos os 17 novos `.md` + os arquivos existentes (README, Roadmap, Decisoes/, etc.)

- [ ] **Step 5: Commit**

```bash
cd /root && git add scripts/gerar_brain.py
git commit -m "feat: script gerar_brain.py — gera 17 stubs de documentação"

cd /root/jake-brain && git add -A
git commit -m "feat: brain retroativo — 17 stubs gerados para documentação"
git push origin main
```

---

## Task 2: Preencher notas — Core

**Files:**
- Modify: `jake-brain/Jake OS/Core/banco-de-dados.md`
- Modify: `jake-brain/Jake OS/Core/sync-planilha.md`
- Modify: `jake-brain/Jake OS/Core/tarefas.md`
- Modify: `jake-brain/Jake OS/Core/utilitarios.md`

> Ler cada arquivo canônico e substituir todos os `[TODO]` com conteúdo real.

> **Regra para todas as notas:** substituir **todos** os `[TODO]` com conteúdo real. Seção "Links Relacionados" deve ter pelo menos **um `[[wikilink]]`** apontando para componente relacionado.

- [ ] **Step 1: Ler e documentar `core/db.py`**

Ler: `Read /root/core/db.py`

Preencher `/root/jake-brain/Jake OS/Core/banco-de-dados.md` com:
- **O que faz:** conecta ao Neon (PostgreSQL) via psycopg2, retorna cursor com RealDictCursor
- **Como funciona:** função `get_conn()`, usa `DATABASE_URL` do ambiente
- **Variáveis de Ambiente:** `DATABASE_URL`
- **Dependências:** `psycopg2`, Neon PostgreSQL
- **Links Relacionados:** `[[sync-planilha]]`, `[[Jake OS App (Rotas)]]`

- [ ] **Step 2: Ler e documentar `core/sync_planilha.py`**

Ler: `Read /root/core/sync_planilha.py`

Preencher `/root/jake-brain/Jake OS/Core/sync-planilha.md` com conteúdo real.
Links obrigatórios: `[[banco-de-dados]]`, `[[utilitarios]]`

- [ ] **Step 3: Ler e documentar `core/tarefas.py` e utilitários**

Ler: `Read /root/core/tarefas.py`, `Read /root/leitor_planilha.py`, `Read /root/listar_ids.py`

Preencher as notas correspondentes.
- `tarefas.md` → Links: `[[banco-de-dados]]`, `[[Jake OS App (Rotas)]]`
- `utilitarios.md` → Links: `[[sync-planilha]]`, `[[banco-de-dados]]`

- [ ] **Step 4: Commit**

```bash
cd /root/jake-brain && git add -A
git commit -m "docs: brain retroativo — notas Core preenchidas"
git push origin main
```

---

## Task 3: Preencher notas — Bots

**Files:**
- Modify: `jake-brain/Jake OS/Bots/jake-principal.md`
- Modify: `jake-brain/Jake OS/Bots/jake-pessoal.md`
- Modify: `jake-brain/Jake OS/Bots/jake-viagem.md`
- Modify: `jake-brain/Jake OS/Bots/gerar-agente.md`

> **Regra:** substituir todos os `[TODO]`. Cada nota deve ter pelo menos um `[[wikilink]]` em "Links Relacionados".

- [ ] **Step 1: Ler e documentar Bot Principal**

Ler: `Read /root/jake_telegram.py limit=80` (header e handlers principais)
Grep: `grep -n "def \|@bot\|handler\|command" /root/jake_telegram.py | head -40`

Preencher `jake-principal.md` com:
- Comandos disponíveis, ferramentas (copy, análise Meta Ads, Telegram), modelo GPT-4o
- Token env: `TELEGRAM_BOT_TOKEN`
- Links: `[[Meta Ads]]`, `[[banco-de-dados]]`

- [ ] **Step 2: Ler e documentar Bot Pessoal e Viagem**

Ler: `Read /root/bot/jake_pessoal.py`, `Read /root/bot/prompt_pessoal.txt`
Ler: `Read /root/bot/jake_viagem.py`, `Read /root/bot/prompt_viagem.txt`

Preencher as notas com personalidade, comandos e diferenciais de cada bot.
- Tokens env: `TELEGRAM_TOKEN_PESSOAL`, `TELEGRAM_TOKEN_VIAGEM`
- Links: `[[jake-principal]]`, `[[banco-de-dados]]`

- [ ] **Step 3: Ler e documentar Gerador de Agentes**

Ler: `Read /root/bot/gerar_agente.py`

Preencher `gerar-agente.md` explicando como o meta-agente cria novos bots.
Links: `[[jake-principal]]`, `[[Jake OS App (Rotas)]]`

- [ ] **Step 4: Commit**

```bash
cd /root/jake-brain && git add -A
git commit -m "docs: brain retroativo — notas Bots preenchidas"
git push origin main
```

---

## Task 4: Preencher nota — Meta Ads

**Files:**
- Modify: `jake-brain/Jake OS/Meta Ads/overview.md`

> **Regra:** substituir todos os `[TODO]`. Incluir pelo menos um `[[wikilink]]` em "Links Relacionados".

- [ ] **Step 1: Ler e documentar Meta Ads**

Ler: `Read /root/meta/meta_api.py`, `Read /root/meta/checar_saldo_meta.py`, `Read /root/meta/config_meta.py`

Preencher `overview.md` com:
- Conta Meta: `act_360347436292903`
- API: Graph API v21.0
- Tokens env: `META_TOKEN_PILOTI`, `META_TOKEN_DENTTO`
- Cron: `0 9 * * *` para checar saldo
- Alerta: `META_ALERTA_SALDO_LIMITE` (R$150)
- Links: `[[banco-de-dados]]`, `[[Jake OS App (Rotas)]]`

- [ ] **Step 2: Commit**

```bash
cd /root/jake-brain && git add -A
git commit -m "docs: brain retroativo — nota Meta Ads preenchida"
git push origin main
```

---

## Task 5: Preencher notas — Jake OS App e Frontend

**Files:**
- Modify: `jake-brain/Jake OS/App-Rotas.md`
- Modify: `jake-brain/Jake OS/Frontend.md`

> **Regra:** substituir todos os `[TODO]`. Incluir pelo menos um `[[wikilink]]` em "Links Relacionados".

- [ ] **Step 1: Documentar rotas do app.py**

Grep: `grep -n "^@app.route" /root/jake_desktop/app.py`

Preencher `App-Rotas.md` com:
- **O que faz:** SPA Flask gerenciando todos os módulos do Jake OS
- **Como funciona:** lista completa de rotas agrupadas por módulo (Auth, Chat, Carrossel, Copys, Criativos `/api/criativos/*`, Relatorios, Prompts, Financeiro, Architect)
- **Variáveis de Ambiente:** todas do `.env` (DATABASE_URL, ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
- **Dependências:** Flask, psycopg2, anthropic, openai, replicate
- **Links:** `[[banco-de-dados]]`, `[[Meta Ads]]`, `[[Frontend]]`

- [ ] **Step 2: Documentar Frontend**

```bash
ls /root/jake_desktop/static/js/
ls /root/jake_desktop/static/css/
```

Preencher `Frontend.md` com:
- **O que faz:** camada de UI do Jake OS (SPA com módulos IIFE por feature)
- **Como funciona:** lista de todos os arquivos JS em `static/js/`, padrão IIFE, comunicação via fetch com rotas Flask
- **Dependências:** Vanilla JS, CSS Glassmorphism
- **Links:** `[[Jake OS App (Rotas)]]`

- [ ] **Step 3: Commit**

```bash
cd /root/jake-brain && git add -A
git commit -m "docs: brain retroativo — notas Jake OS App e Frontend preenchidas"
git push origin main
```

---

## Task 6: Preencher notas — Infraestrutura

**Files:**
- Modify: `jake-brain/Jake OS/Infraestrutura/vps-scripts.md`
- Modify: `jake-brain/Jake OS/Infraestrutura/migrations.md`
- Modify: `jake-brain/Jake OS/Infraestrutura/docs-existentes.md`

> **Regra:** substituir todos os `[TODO]`. Incluir pelo menos um `[[wikilink]]` em "Links Relacionados" de cada nota.

- [ ] **Step 1: Documentar scripts**

```bash
ls -la /root/scripts/
```

Ler: `Read /root/scripts/subir_jake.sh`, `Read /root/scripts/ativar_firewall.sh`

Preencher `vps-scripts.md` com:
- **O que faz / Como funciona:** lista de scripts, o que cada um faz e quando usar
- **Links:** `[[jake-principal]]`, `[[banco-de-dados]]`

- [ ] **Step 2: Documentar migrations**

Ler: `Read /root/scripts/migrar_criativos.py`, `Read /root/scripts/migrar_anuncios.py`

Preencher `migrations.md` com:
- **O que faz:** tabelas criadas por cada migration e como rodar
- **Links:** `[[banco-de-dados]]`

- [ ] **Step 3: Documentar docs existentes**

```bash
ls /root/docs/*.md
```

Ler cada doc existente (`AGENTES_JAKE.md`, `CONFIGURAR_META.md`, `JAKE_ROADMAP.md`, `SEGURANCA.md`).

Preencher `docs-existentes.md` com:
- **O que faz:** índice dos docs existentes em `/root/docs/`
- **Como funciona:** resumo de cada doc com link externo e propósito
- **Links:** `[[Jake OS App (Rotas)]]`, `[[Meta Ads]]`

- [ ] **Step 4: Commit**

```bash
cd /root/jake-brain && git add -A
git commit -m "docs: brain retroativo — notas Infraestrutura preenchidas"
git push origin main
```

---

## Task 7: Preencher notas — Projetos e Clientes

**Files:**
- Modify: `jake-brain/Projetos/carousel-engine.md`
- Modify: `jake-brain/Clientes/clinica-cliente.md`
- Modify: `jake-brain/Clientes/camila-piercer.md`

> **Regra:** substituir todos os `[TODO]`. Incluir pelo menos um `[[wikilink]]` em "Links Relacionados" de cada nota.

- [ ] **Step 1: Documentar Carousel Engine**

Ler: `Read /root/carousel-engine/README.md`, `Read /root/carousel-engine/package.json`

Preencher `carousel-engine.md` com stack (Next.js), propósito, como rodar, status atual.
Links: `[[Jake OS App (Rotas)]]`

- [ ] **Step 2: Documentar sites de clientes**

Ler primeiras 50 linhas de cada:
`Read /root/clinica-cliente/index.html limit=50`
`Read /root/camila_piercerr_2.html limit=50`

Preencher as notas dos clientes com: nome do negócio, tipo de site, tecnologias, status, localização dos arquivos.
Links: `[[carousel-engine]]` ou `[[Jake OS App (Rotas)]]`

- [ ] **Step 3: Commit final**

```bash
cd /root/jake-brain && git add -A
git commit -m "docs: brain retroativo — notas Projetos e Clientes preenchidas"
git push origin main
```

- [ ] **Step 4: Verificar critérios de sucesso**

```bash
# Nenhum [TODO] remanescente
grep -r "\[TODO\]" /root/jake-brain/ --include="*.md"
# Expected: sem output

# Pelo menos um wikilink por nota (busca arquivos SEM [[)
grep -rL "\[\[" /root/jake-brain/Jake\ OS /root/jake-brain/Projetos /root/jake-brain/Clientes
# Expected: sem output (todas as notas têm pelo menos um wikilink)

# Contar notas geradas (excluindo vault files existentes antes do brain retroativo)
find /root/jake-brain/Jake\ OS /root/jake-brain/Projetos /root/jake-brain/Clientes -name "*.md" | wc -l
# Expected: 17
```
