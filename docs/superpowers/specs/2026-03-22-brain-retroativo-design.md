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

| Componente | Arquivos canônicos | Nota no vault |
|---|---|---|
| Bot Principal | `/root/jake_telegram.py` + `/root/bot/base_bot.py` | `Jake OS/Bots/jake-principal.md` |
| Bot Pessoal | `/root/bot/jake_pessoal.py` + `bot/prompt_pessoal.txt` | `Jake OS/Bots/jake-pessoal.md` |
| Bot Viagem | `/root/bot/jake_viagem.py` + `bot/prompt_viagem.txt` | `Jake OS/Bots/jake-viagem.md` |
| Gerador de Agentes | `/root/bot/gerar_agente.py` | `Jake OS/Bots/gerar-agente.md` |
| Banco de Dados | `/root/core/db.py` | `Jake OS/Core/banco-de-dados.md` |
| Sync Planilha | `/root/core/sync_planilha.py` | `Jake OS/Core/sync-planilha.md` |
| Tarefas | `/root/core/tarefas.py` | `Jake OS/Core/tarefas.md` |
| Meta Ads | `/root/meta/` (3 arquivos) | `Jake OS/Meta Ads/overview.md` |
| Jake OS App | `/root/jake_desktop/app.py` | `Jake OS/App-Rotas.md` |
| Jake OS Frontend | `/root/jake_desktop/static/js/` | `Jake OS/Frontend.md` |
| Scripts e Infraestrutura | `/root/scripts/` (todos) | `Jake OS/Infraestrutura/vps-scripts.md` |
| Migrations | `scripts/migrar_anuncios.py` + `scripts/migrar_criativos.py` | `Jake OS/Infraestrutura/migrations.md` |
| Docs existentes | `/root/docs/*.md` | `Jake OS/Infraestrutura/docs-existentes.md` |
| Carousel Engine | `/root/carousel-engine/` | `Projetos/carousel-engine.md` |
| Clínica Cliente | `/root/clinica-cliente/` (index.html + sitealine.html) | `Clientes/clinica-cliente.md` |
| Camila Piercer | `/root/camila_piercerr_2.html` | `Clientes/camila-piercer.md` |
| Utilitários | `/root/leitor_planilha.py` + `/root/listar_ids.py` | `Jake OS/Core/utilitarios.md` |

---

## Estrutura do Vault Após Brain Retroativo

```
jake-brain/
├── Clientes/
│   ├── _Template/              (já existe)
│   ├── clinica-cliente.md
│   └── camila-piercer.md
├── Decisoes/                   (já existe — não tocar)
│   ├── _Template.md
│   └── 2026-03-22-obsidian-vault-foundation.md
├── Jake OS/
│   ├── Arquitetura.md          (já existe)
│   ├── App-Rotas.md
│   ├── Frontend.md
│   ├── Bots/
│   │   ├── jake-principal.md
│   │   ├── jake-pessoal.md
│   │   ├── jake-viagem.md
│   │   └── gerar-agente.md
│   ├── Core/
│   │   ├── banco-de-dados.md
│   │   ├── sync-planilha.md
│   │   ├── tarefas.md
│   │   └── utilitarios.md
│   ├── Meta Ads/
│   │   └── overview.md
│   └── Infraestrutura/
│       ├── vps-scripts.md
│       ├── migrations.md
│       └── docs-existentes.md
├── Projetos/
│   └── carousel-engine.md
├── README.md                   (já existe)
└── Roadmap.md                  (já existe)
```

---

## Script de Varredura (`scripts/gerar_brain.py`)

**Uso:**
```bash
cd /root && python3 scripts/gerar_brain.py
```

O script realiza as seguintes operações:

1. Define lista estática de componentes com caminho canônico e destino no vault
2. Para cada componente, cria o `.md` correspondente com:
   - **Frontmatter YAML:** tipo, caminho, arquivos, tags, data de geração
   - **Lista de arquivos** detectada automaticamente (excluindo diretórios ignorados)
   - **Seções com `[TODO]`:** O que faz, Como funciona, Variáveis de ambiente, Decisões, Próximos passos, Links relacionados

**Regra de não-sobrescrita:**
- Se o arquivo `.md` **não existe** → cria
- Se o arquivo `.md` **já existe** → pula, independente do conteúdo (não sobrescreve nunca)
- Claude preenche os `[TODO]` manualmente na etapa seguinte

**Diretórios ignorados:**
`venv/`, `.venv/`, `node_modules/`, `__pycache__/`, `.git/`, `.local/`, `.npm/`, `.cache/`, `jake-brain/`

---

## Template de Nota Gerada pelo Script

```markdown
---
tipo: [bot|core|integração|frontend|site|script|projeto]
caminho: /root/caminho/
tags: [jake, bot]
gerado_em: YYYY-MM-DD
---

# [Nome do Componente]

## Arquivos
- `arquivo1.py`
- `arquivo2.py`

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

1. Lê os arquivos canônicos (usando Grep/Read com ranges para arquivos grandes)
2. Substitui cada `[TODO]` com conteúdo real
3. Adiciona pelo menos **um `[[wikilink]]`** para componente relacionado em "Links Relacionados"
4. Commita as notas preenchidas no vault

**Ordem de preenchimento (prioridade):**
1. Core (db, sync_planilha, tarefas, utilitários)
2. Bots (jake-principal, jake-pessoal, jake-viagem, gerar-agente)
3. Meta Ads
4. Jake OS App e Frontend
5. Infraestrutura (scripts, migrations, docs existentes)
6. Projetos (carousel-engine)
7. Clientes (clinica-cliente, camila-piercer)

---

## Critérios de Sucesso

- [ ] `python3 scripts/gerar_brain.py` roda sem erros
- [ ] Todos os 17 `.md` são criados no vault
- [ ] Nenhum arquivo existente no vault é sobrescrito
- [ ] Todos os `[TODO]` foram substituídos por conteúdo real
- [ ] Cada nota tem pelo menos um `[[wikilink]]` para componente relacionado
- [ ] Notas aparecem no Obsidian Windows após pull
