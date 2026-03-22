# Obsidian Vault Foundation — Design Spec

**Data:** 2026-03-22
**Projeto:** Jake Brain — Cérebro do ecossistema Jake IA
**Sub-projeto:** 1 de 4 — Vault Foundation (base para tudo)

---

## Objetivo

Criar a fundação do vault Obsidian do projeto Jake: estrutura de pastas, repositório Git privado no GitHub, sincronização automática VPS↔Windows via Git, e cron job de auto-push na VPS.

Este sub-projeto não inclui conteúdo retroativo, auto-save do Jake OS, nem leitura de contexto por Claude — esses são os sub-projetos 2, 3 e 4.

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
│       ├── Criativos/
│       ├── Copies/
│       ├── Relatorios/
│       └── Carrossel/
└── Jake OS/                    # documentação do ecossistema Jake
    ├── Arquitetura.md
    ├── Bots/
    ├── Meta Ads/
    └── Infraestrutura/
```

---

## Arquivos Criados

| Arquivo | Descrição |
|---|---|
| `/root/jake-brain/` | Diretório raiz do vault |
| `/root/jake-brain/README.md` | Visão geral e instruções de uso |
| `/root/jake-brain/Roadmap.md` | Roadmap Jake com sub-projetos do brain |
| `/root/jake-brain/Decisoes/_Template.md` | Template para log de decisões |
| `/root/jake-brain/Clientes/_Template/Briefing.md` | Template de briefing de cliente |
| `/root/scripts/jake_brain_push.sh` | Script de auto-push do vault |

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

---

## Configuração Git

```bash
# Na VPS
git clone git@github.com:USUARIO/jake-brain.git /root/jake-brain
# ou se o repo ainda não existe:
cd /root/jake-brain && git init && git remote add origin git@github.com:USUARIO/jake-brain.git
```

Usa SSH key existente da VPS (assumindo que já está configurada para o GitHub).

---

## Configuração Windows (Obsidian Git)

1. Instalar plugin **Obsidian Git** no Obsidian
2. Clonar `jake-brain` via HTTPS ou SSH no Windows
3. Abrir a pasta clonada como vault no Obsidian
4. Configurar pull automático: `Pull interval: 5 minutos`
5. Auto-push do Windows: desabilitado (VPS é o primário; Windows só lê/puxa)

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
```

---

## Critérios de Sucesso

- [ ] `/root/jake-brain/` existe e tem a estrutura de pastas correta
- [ ] Repositório privado `jake-brain` no GitHub com push inicial feito
- [ ] Cron job ativo — push automático a cada 5 min
- [ ] Log `/root/logs/jake_brain.log` sendo gerado
- [ ] Windows consegue fazer pull e ver o vault no Obsidian
- [ ] Mudanças feitas na VPS aparecem no Obsidian em até 10 min
