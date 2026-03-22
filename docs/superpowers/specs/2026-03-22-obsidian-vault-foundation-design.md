# Obsidian Vault Foundation — Design Spec

**Data:** 2026-03-22
**Projeto:** Jake Brain — Cérebro do ecossistema Jake IA
**Sub-projeto:** 1 de 4 — Vault Foundation (base para tudo)

---

## Objetivo

Criar a fundação do vault Obsidian do projeto Jake: estrutura de pastas, repositório Git privado no GitHub, sincronização automática VPS↔Windows via Git, e cron job de auto-push na VPS.

Este sub-projeto não inclui conteúdo retroativo, auto-save do Jake OS, nem leitura de contexto por Claude — esses são os sub-projetos 2, 3 e 4.

---

## Pré-requisitos (feitos pelo Bruno antes da implementação)

> **ATENÇÃO:** estes passos precisam ser feitos manualmente antes de rodar qualquer script.

1. **Criar repositório privado `jake-brain` no GitHub** (github.com → New repository → Private)

2. **Verificar SSH key da VPS configurada no GitHub:**
```bash
ssh -T git@github.com
# Esperado: "Hi USUARIO! You've successfully authenticated..."
# Se falhar: ssh-keygen -t ed25519 -C "jake-vps" → copiar ~/.ssh/id_ed25519.pub → GitHub → Settings → SSH Keys
```

3. **Garantir identidade Git configurada na VPS:**
```bash
git config --global user.name "Jake Brain"
git config --global user.email "seu@email.com"
```

4. **Criar diretório de logs:**
```bash
mkdir -p /root/logs
```

---

## Arquitetura

**Vault primário:** `/root/jake-brain/` na VPS Linux
**Repositório GitHub:** `jake-brain` (privado), criado pelo Bruno
**Sync Windows→VPS:** plugin Obsidian Git no Windows (pull automático a cada 5 min)
**Sync VPS→GitHub:** cron job na VPS (`*/5 * * * *`) rodando script de auto-push

O vault vive na VPS porque Jake OS e Claude Code já estão lá — escrever arquivos `.md` direto no disco é o caminho mais simples e sem dependência do Windows estar ligado.

---

## Estrutura de Pastas

```
/root/jake-brain/
├── .gitignore                  # ignorar .obsidian/workspace.json
├── README.md                   # visão geral do vault
├── Roadmap.md                  # roadmap do projeto Jake
├── Decisoes/                   # log de decisões arquiteturais
│   └── _Template.md
├── Clientes/                   # um diretório por cliente
│   └── _Template/              # template base para novos clientes
│       ├── Briefing.md         # contexto, tom de voz, objetivos
│       ├── Criativos/.gitkeep
│       ├── Copies/.gitkeep
│       ├── Relatorios/.gitkeep
│       └── Carrossel/.gitkeep
└── Jake OS/                    # documentação do ecossistema Jake
    ├── Arquitetura.md
    ├── Bots/.gitkeep
    ├── Meta Ads/.gitkeep
    └── Infraestrutura/.gitkeep
```

---

## Arquivos Criados

| Arquivo | Descrição |
|---|---|
| `/root/jake-brain/.gitignore` | Ignora workspace e trash do Obsidian |
| `/root/jake-brain/README.md` | Visão geral e instruções de uso |
| `/root/jake-brain/Roadmap.md` | Roadmap Jake com sub-projetos do brain |
| `/root/jake-brain/Decisoes/_Template.md` | Template para log de decisões |
| `/root/jake-brain/Clientes/_Template/Briefing.md` | Template de briefing de cliente |
| `/root/jake-brain/Clientes/_Template/Criativos/.gitkeep` | Mantém pasta vazia no Git |
| `/root/jake-brain/Clientes/_Template/Copies/.gitkeep` | Mantém pasta vazia no Git |
| `/root/jake-brain/Clientes/_Template/Relatorios/.gitkeep` | Mantém pasta vazia no Git |
| `/root/jake-brain/Clientes/_Template/Carrossel/.gitkeep` | Mantém pasta vazia no Git |
| `/root/jake-brain/Jake OS/Arquitetura.md` | Doc inicial da arquitetura Jake |
| `/root/jake-brain/Jake OS/Bots/.gitkeep` | Mantém pasta vazia no Git |
| `/root/jake-brain/Jake OS/Meta Ads/.gitkeep` | Mantém pasta vazia no Git |
| `/root/jake-brain/Jake OS/Infraestrutura/.gitkeep` | Mantém pasta vazia no Git |
| `/root/scripts/jake_brain_push.sh` | Script de auto-push do vault |

---

## Conteúdo dos Arquivos Base

**`README.md`:**
```markdown
# Jake Brain 🧠

Vault Obsidian do ecossistema Jake IA. Cérebro central do projeto.

## Estrutura
- **Clientes/** — briefings, criativos, copies, relatórios por cliente
- **Jake OS/** — arquitetura, bots, infraestrutura
- **Decisoes/** — log de decisões arquiteturais
- **Roadmap.md** — próximos passos do projeto

## Como usar
- VPS escreve automaticamente ao gerar conteúdo
- Windows puxa via Obsidian Git (pull a cada 5 min)
- Claude lê os briefings de cliente antes de gerar
```

**`Roadmap.md`:**
```markdown
# Jake Brain — Roadmap

## Sub-projetos
- [x] 1. Vault Foundation — estrutura + Git sync
- [ ] 2. Brain Retroativo — indexar /root existente
- [ ] 3. Automação Live — Jake OS escreve no vault
- [ ] 4. Inteligência de Contexto — Claude lê vault antes de gerar

## Jake OS — Próximas features
(atualizar conforme planejamento)
```

**`Jake OS/Arquitetura.md`:**
```markdown
# Jake OS — Arquitetura

**Stack:** Python/Flask, Neon PostgreSQL, Vanilla JS (IIFE), CSS Glassmorphism
**Porta:** 5050
**Auth:** admin@jakeos.local / Jake@2024!

## Módulos
- Carrossel Instagram (Claude sonnet-4-5)
- Copy de Anúncios (Claude sonnet-4-6)
- Relatórios Meta Ads (Graph API v21.0)
- Fábrica de Criativos v2 (Replicate + Claude)
- Arquiteto de Sites (Claude sonnet-4-5)
- Finanças Pessoais (Claude sonnet-4-5)
- Geração de Prompts (Claude sonnet-4-5)

## Arquivos principais
- `app.py` — ~1900 linhas, todas as rotas
- `templates/dashboard.html` — SPA shell
- `static/js/` — módulos IIFE por feature
```

---

## Script de Auto-Push

**`/root/scripts/jake_brain_push.sh`:**

```bash
#!/bin/bash
cd /root/jake-brain || exit 1
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  git add -A
  git commit -m "auto: sync $(date '+%Y-%m-%d %H:%M')"
  git push origin main
fi
```

Só commita e faz push se houver mudanças — sem commits vazios.

---

## Cron Job

```
*/5 * * * * /bin/bash /root/scripts/jake_brain_push.sh >> /root/logs/jake_brain.log 2>&1
```

Roda a cada 5 minutos. Log em `/root/logs/jake_brain.log`.

**Adicionar via:** `crontab -e`

---

## Configuração Git (VPS)

```bash
# Clonar o repo criado no GitHub
git clone git@github.com:USUARIO/jake-brain.git /root/jake-brain
# substituir USUARIO pelo username do Bruno no GitHub
```

---

## Configuração Windows (Obsidian Git)

1. Instalar plugin **Obsidian Git** no Obsidian (Community Plugins)
2. Clonar `jake-brain` via HTTPS no Windows:
   ```
   git clone https://github.com/USUARIO/jake-brain.git C:\Users\SEU_USUARIO\jake-brain
   ```
3. Abrir a pasta clonada como vault no Obsidian
4. Configurar Obsidian Git: `Pull interval: 5` (minutos), auto-push **desabilitado**
5. Windows só lê/puxa — VPS é quem escreve

---

## .gitignore

```
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.trash/
```

Mantém as configurações do Obsidian (plugins, temas) mas ignora estado de workspace.

---

## Templates de Conteúdo

**`Clientes/_Template/Briefing.md`:**
```markdown
# [Nome do Cliente]

## Sobre
- Segmento:
- Produto/Serviço:
- Diferencial:

## Tom de Voz
- Formal / Informal:
- Palavras a usar:
- Palavras a evitar:

## Objetivos
- Meta principal:
- Público-alvo:

## Histórico
- Início:
- Plataformas:
```

**`Decisoes/_Template.md`:**
```markdown
# [Título da Decisão]

**Data:** YYYY-MM-DD
**Contexto:**
**Decisão tomada:**
**Motivo:**
**Alternativas descartadas:**
**Resultado/Follow-up:**
```

---

## Critérios de Sucesso

- [ ] `/root/jake-brain/` existe com a estrutura de pastas correta
- [ ] Repositório privado `jake-brain` no GitHub com push inicial feito
- [ ] `chmod +x /root/scripts/jake_brain_push.sh` executado
- [ ] Cron job ativo (`crontab -l` mostra a linha)
- [ ] `/root/logs/` existe e `jake_brain.log` sendo gerado após 5 min
- [ ] `jake_brain_push.sh` rodando sem erros (verificar log)
- [ ] Windows consegue clonar e abrir o vault no Obsidian
- [ ] Mudanças feitas na VPS aparecem no Obsidian Windows em até 10 min
