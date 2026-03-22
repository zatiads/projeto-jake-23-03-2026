# Brain Retroativo — Design Spec

**Data:** 2026-03-22
**Projeto:** Jake Brain — Cérebro do ecossistema Jake IA
**Sub-projeto:** 2 de 4 — Brain Retroativo (documentar o que já existe)

---

## Objetivo

Documentar todos os componentes existentes em `/root` no vault Obsidian (`/root/jake-brain/`), gerando notas completas com: o que cada componente faz, como funciona, dependências, variáveis de ambiente, decisões tomadas e próximos passos.

**Abordagem híbrida:**
1. Script Python (`scripts/gerar_brain.py`) varre `/root` e cria estrutura de `.md` com frontmatter e marcadores `[TODO]`
2. Claude lê os arquivos principais de cada componente e preenche os `[TODO]` com conteúdo real

---

## Componentes a Documentar

| Componente | Caminho | Tipo |
|---|---|---|
| Bot Principal | `/root/jake_telegram.py` + `/root/bot/` | Bots Telegram |
| Bot Pessoal | `/root/bot/jake_pessoal.py` | Bot Telegram |
| Bot Viagem | `/root/bot/jake_viagem.py` | Bot Telegram |
| Gerador de Agentes | `/root/bot/gerar_agente.py` | Meta-agente |
| Banco de Dados | `/root/core/db.py` | Core |
| Sync Planilha | `/root/core/sync_planilha.py` | Core |
| Tarefas | `/root/core/tarefas.py` | Core |
| Meta Ads | `/root/meta/` | Integração |
| Jake OS App | `/root/jake_desktop/app.py` | Flask SPA |
| Jake OS Frontend | `/root/jake_desktop/static/js/` | Frontend |
| Scripts | `/root/scripts/` | Infraestrutura |
| Carousel Engine | `/root/carousel-engine/` | Projeto Next.js |
| Clínica Cliente | `/root/clinica-cliente/` | Site de cliente |
| Camila Piercer | `/root/camila_piercerr_2.html` | Site de cliente |
| Utilitários | `/root/leitor_planilha.py`, `/root/listar_ids.py` | Scripts avulsos |

---

## Estrutura do Vault Após Brain Retroativo

```
jake-brain/
├── Clientes/
│   ├── _Template/          (já existe)
│   ├── clinica-cliente.md
│   └── camila-piercer.md
├── Jake OS/
│   ├── Arquitetura.md      (já existe)
│   ├── App-Rotas.md        (todas as rotas do app.py)
│   ├── Frontend.md         (módulos JS, CSS, estrutura)
│   ├── Bots/
│   │   ├── jake-principal.md
│   │   ├── jake-pessoal.md
│   │   ├── jake-viagem.md
│   │   └── gerar-agente.md
│   ├── Core/
│   │   ├── banco-de-dados.md
│   │   ├── sync-planilha.md
│   │   └── tarefas.md
│   ├── Meta Ads/
│   │   └── overview.md
│   └── Infraestrutura/
│       ├── vps-scripts.md
│       └── cron.md
└── Projetos/
    └── carousel-engine.md
```

---

## Script de Varredura (`scripts/gerar_brain.py`)

O script realiza as seguintes operações:

1. Define lista de componentes com caminho, tipo e arquivos principais
2. Para cada componente, cria o `.md` correspondente no vault com:
   - **Frontmatter:** caminho, tipo, arquivos principais, data de geração
   - **Seções com `[TODO]`:** O que faz, Como funciona, Variáveis de ambiente, Decisões, Próximos passos
   - **Lista de arquivos** detectada automaticamente (excluindo venv, __pycache__, .git)
3. Não sobrescreve arquivos que já têm conteúdo real (verifica se `[TODO]` foi removido)

**Diretórios ignorados pelo script:**
- `venv/`, `.venv/`, `node_modules/`, `__pycache__/`, `.git/`, `.local/`, `.npm/`, `.cache/`

---

## Template de Nota Gerada pelo Script

```markdown
# [Nome do Componente]

**Tipo:** [bot/core/integração/frontend/site/script]
**Caminho:** `/root/caminho/`
**Gerado em:** YYYY-MM-DD

## Arquivos
- `arquivo1.py` — [TODO: descrever]
- `arquivo2.py` — [TODO: descrever]

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
```

---

## Preenchimento por Claude

Após o script gerar a estrutura, Claude executa uma passagem por cada componente:

1. Lê os arquivos principais (usando Grep/Read com ranges para arquivos grandes)
2. Substitui cada `[TODO]` com conteúdo real
3. Commita as notas preenchidas no vault (auto-push via cron em até 5 min)

**Ordem de preenchimento (prioridade):**
1. Core (db, sync_planilha, tarefas) — base de tudo
2. Bots (jake_principal, jake_pessoal, jake_viagem, gerar_agente)
3. Meta Ads
4. Jake OS App (rotas) e Frontend
5. Infraestrutura (scripts, cron)
6. Projetos (carousel-engine)
7. Clientes (clinica-cliente, camila-piercer)

---

## Critérios de Sucesso

- [ ] Script `gerar_brain.py` roda sem erros e cria todos os `.md`
- [ ] Nenhum arquivo existente no vault é sobrescrito
- [ ] Todos os 15 componentes têm nota no vault
- [ ] Cada nota tem conteúdo real (sem `[TODO]` remanescente)
- [ ] Notas aparecem no Obsidian Windows após pull
- [ ] Links entre componentes relacionados estão presentes nas notas
