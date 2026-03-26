# Engenheiro de Prompts — Design Spec

**Data:** 2026-03-25
**Status:** Aprovado pelo usuário
**Escopo:** Substituir o módulo `prompts` atual do Jake OS por um chat conversacional de engenharia de prompts com histórico persistido.

---

## Contexto

O Jake OS já possui uma página `#prompts` que gera prompts de imagem em inglês. Ela será **substituída** por um Engenheiro de Prompts conversacional: um agente Claude que faz 5–7 perguntas estratégicas para entender o projeto do usuário e então gera um prompt estruturado e assertivo.

O usuário forneceu o HTML completo da interface de referência. A lógica visual (bubble chat, prompt-box verde, indicador de digitação, parsing de JSON do Claude) já está definida e será portada para dentro do Jake OS.

---

## Arquitetura

### Abordagem escolhida
**Full backend** — todas as chamadas à API Anthropic e toda a persistência passam pelo Flask. O JS só faz fetch para rotas internas do Jake OS. A `ANTHROPIC_API_KEY` nunca é exposta no browser.

---

## Banco de Dados (Neon/PostgreSQL)

Duas novas tabelas, criadas via `CREATE TABLE IF NOT EXISTS` no startup do `app.py`:

```sql
CREATE TABLE IF NOT EXISTS prompt_sessions (
  id            SERIAL PRIMARY KEY,
  titulo        TEXT,
  criado_em     TIMESTAMPTZ DEFAULT NOW(),
  atualizado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prompt_messages (
  id         SERIAL PRIMARY KEY,
  session_id INT REFERENCES prompt_sessions(id) ON DELETE CASCADE,
  role       TEXT NOT NULL,   -- 'user' | 'assistant'
  content    TEXT NOT NULL,
  criado_em  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Rotas Flask (`app.py`)

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/prompts/sessoes` | Lista sessões ordenadas por `atualizado_em DESC` |
| `POST` | `/api/prompts/sessoes` | Cria nova sessão (título vazio) |
| `GET` | `/api/prompts/sessoes/<id>/mensagens` | Retorna todas as mensagens da sessão |
| `POST` | `/api/prompts/sessoes/<id>/chat` | Envia mensagem, chama Claude, salva par user+assistant, retorna resposta |
| `PATCH` | `/api/prompts/sessoes/<id>/titulo` | Atualiza título da sessão |
| `DELETE` | `/api/prompts/sessoes/<id>` | Deleta sessão e mensagens em cascata |

### POST `/api/prompts/sessoes/<id>/chat`
- Recebe `{ "message": "texto do usuário" }`
- Lê todas as mensagens anteriores da sessão do banco
- Monta array `messages` para Claude (histórico completo)
- Chama `claude-sonnet-4-6` com o `SYSTEM_PROMPT` do Engenheiro de Prompts
- Salva mensagem do usuário + resposta do assistente no banco
- Atualiza `atualizado_em` da sessão
- Retorna `{ "reply": "...", "session_id": N }`

### Geração de título (PATCH)
- Chamado pelo JS quando Claude retorna um JSON `{"type":"prompt",...}` (prompt final gerado)
- O JS extrai o campo `title` do JSON e faz PATCH com `{ "titulo": "..." }`

---

## System Prompt do Agente

O `SYSTEM_PROMPT` instrui Claude a:
1. **Etapa 1** — fazer 5–7 perguntas estratégicas, retornando JSON: `{"type":"questions","questions":[...]}`
2. **Etapa 2** — gerar o prompt final após respostas, retornando JSON: `{"type":"prompt","title":"...","prompt":"..."}`
3. Nunca gerar o prompt direto sem perguntar antes
4. Responder sempre em português brasileiro

---

## Frontend

### Arquivos modificados/criados
- `static/js/prompts.js` — **reescrito completamente**
- `templates/dashboard.html` — seção `#page-prompts` substituída pelo novo layout
- `static/css/style.css` — variáveis e estilos específicos do módulo (prompt-box, sidebar de sessões)

### Layout: 2 colunas
```
┌──────────────┬────────────────────────────────────┐
│  SIDEBAR     │  CHAT AREA                         │
│              │                                    │
│  + Nova      │  [mensagens do agente/usuário]      │
│  ─────────   │                                    │
│  23/03       │  [prompt-box verde ao final]        │
│  Bot para... │  ──────────────────────────────── │
│              │  [textarea]  [enviar →]             │
└──────────────┴────────────────────────────────────┘
```

### Comportamento do JS (`prompts.js`)
1. **Init**: carrega lista de sessões via `GET /api/prompts/sessoes`, renderiza sidebar
2. **Nova conversa**: `POST /api/prompts/sessoes` → cria sessão → exibe mensagem de boas-vindas do agente (sem chamar Claude — mensagem local)
3. **Abrir sessão existente**: `GET /api/prompts/sessoes/<id>/mensagens` → renderiza histórico completo
4. **Enviar mensagem**: `POST /api/prompts/sessoes/<id>/chat` → mostra typing indicator → renderiza resposta
5. **Parsing da resposta**: detecta JSON `{"type":"questions"}` ou `{"type":"prompt"}` para renderizar perguntas numeradas ou prompt-box verde
6. **Geração de título**: quando detecta `{"type":"prompt","title":"..."}`, faz `PATCH /api/prompts/sessoes/<id>/titulo` e atualiza sidebar
7. **Deletar sessão**: botão de lixeira na sidebar, `DELETE /api/prompts/sessoes/<id>`

### Estilos
- Sidebar: `width: 240px`, fundo `var(--surface)`, borda direita `var(--border)`
- Sessão ativa: destaque com `var(--accent)` na borda esquerda
- Prompt-box: fundo `#0d1a14`, borda `var(--accent2)` (verde), fonte monospace
- Perguntas: lista numerada com fundo `var(--surface2)`, fonte monospace
- Responsivo: sidebar colapsa em mobile (toggle button)

---

## Fluxo completo de uso

```
Usuário abre #prompts
  → JS carrega sessões → renderiza sidebar
  → Se nenhuma sessão ativa, mostra tela de boas-vindas

Usuário clica "+ Nova conversa"
  → POST /api/prompts/sessoes → session_id = 42
  → JS exibe mensagem de boas-vindas local
  → Sessão 42 aparece na sidebar (sem título ainda)

Usuário digita "Quero um prompt para um bot de vendas"
  → POST /api/prompts/sessoes/42/chat
  → Claude retorna {"type":"questions","questions":["Qual o produto?","..."]}
  → JS renderiza lista de perguntas

Usuário responde todas as perguntas
  → POST /api/prompts/sessoes/42/chat
  → Claude retorna {"type":"prompt","title":"Bot de Vendas SaaS","prompt":"Você é..."}
  → JS renderiza prompt-box verde com botão Copiar
  → JS faz PATCH /api/prompts/sessoes/42/titulo com "Bot de Vendas SaaS"
  → Sidebar atualiza o título da sessão
```

---

## O que NÃO está no escopo

- Exportar prompt como arquivo
- Compartilhar sessão com link
- Busca no histórico
- Tags/categorias de sessões
- Editar mensagens passadas

---

## Dependências

- `anthropic` SDK Python (já instalado)
- Neon PostgreSQL (já configurado via `DATABASE_URL`)
- Sem novas dependências Python ou npm
