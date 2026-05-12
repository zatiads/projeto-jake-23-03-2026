# Planejador de Campanhas — Design Spec

**Data:** 2026-05-12
**Status:** Aprovado pelo usuário

---

## Visão Geral

Nova aba **"Planejador"** no Jake OS. Interface de chat onde o usuário conversa com o Jake para criar campanhas Meta Ads. Claude interpreta as mensagens em linguagem natural, extrai parâmetros de campanha progressivamente (multi-turn), pergunta o que falta, e quando tiver tudo mostra um **card de confirmação** estruturado. Após confirmação, executa o sistema Drive Batch existente para criar a campanha no Meta Ads.

Funciona por texto e por áudio (Whisper-1 para transcrição).

**Princípio central:** o usuário não preenche formulário — ele conversa. O Jake entende o contexto, resolve ambiguidades, e só age após confirmação explícita.

---

## Arquitetura

### Novos arquivos

```
jake_desktop/
  static/
    js/planejador.js          # IIFE — chat UI, áudio, confirmação, progresso
    css/planejador.css        # estilos do chat
```

### Arquivos modificados

```
jake_desktop/
  templates/dashboard.html   # nav item + page section + link CSS + script tag
  app.py                     # 2 endpoints novos: interpretar + transcrever
```

### Sem dependências novas

Usa `anthropic` SDK (`claude-sonnet-4-6`), OpenAI Whisper-1 e os endpoints Drive Batch já existentes — tudo já instalado.

---

## Endpoints Backend

### `POST /api/planejador/interpretar`

Recebe o histórico da conversa e os parâmetros acumulados. Chama Claude para extrair/atualizar parâmetros e decidir o próximo passo.

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "sobe campanha para Queen Poltronas..."},
    {"role": "assistant", "content": "Entendido! Qual o orçamento diário?"},
    {"role": "user", "content": "R$ 80 por dia"}
  ],
  "params": {
    "cliente_nome": "Queen Poltronas",
    "cliente_id": 5,
    "objetivo": "ENGAGEMENT",
    "drive_link": "https://drive.google.com/..."
  }
}
```

**Response:**
```json
{
  "resposta": "Entendido! Falta só o orçamento diário — quanto você quer investir?",
  "params": {
    "cliente_id": 5,
    "cliente_nome": "Queen Poltronas",
    "campanha_nome": "Queen Poltronas — Engajamento Mai/26",
    "objetivo": "ENGAGEMENT",
    "drive_link": "https://drive.google.com/...",
    "orcamento_diario": null,
    "publico_descricao": "Mulheres 25-45 interessadas em decoração",
    "copy_titulo": null,
    "copy_texto": null
  },
  "duvidas": ["orcamento_diario"],
  "pronto": false
}
```

Quando `pronto: true`, todos os campos obrigatórios estão preenchidos e o frontend renderiza o card de confirmação.

**Lógica interna:**

1. Busca lista de clientes em `ad_client_profiles` para passar ao Claude como contexto (resolve `cliente_nome` → `cliente_id`)
2. Monta prompt com: instrução de extração, lista de clientes, histórico da conversa, params acumulados
3. Claude retorna JSON estruturado
4. Se `copies` não fornecidas e `pronto: true` → Claude gera `copy_titulo` e `copy_texto` automaticamente baseado no cliente e objetivo
5. Endpoint não persiste nada no banco — estado fica no frontend

**Campos obrigatórios para `pronto: true`:** `cliente_id`, `objetivo`, `drive_link`, `orcamento_diario`

**Campos opcionais (auto-gerados se ausentes):**
- `campanha_nome` → `"{cliente_nome} — {objetivo_legivel} {mes}/{ano}"`
- `copy_titulo` + `copy_texto` → Claude gera automaticamente
- `publico_descricao` → usa público padrão do cliente (`publico_json`)

**Objetivos suportados:**

| Código | Label |
|---|---|
| `MESSAGES` | Mensagens/WhatsApp |
| `ENGAGEMENT` | Engajamento / visitas ao perfil |
| `REACH` | Alcance |
| `PURCHASE` | Conversões / Vendas |

---

### `POST /api/planejador/transcrever`

Recebe arquivo de áudio (multipart `audio`), chama Whisper-1, retorna texto transcrito.

**Request:** multipart/form-data com campo `audio` (webm, mp4, ogg)

**Response:**
```json
{"text": "sobe campanha para Queen Poltronas, distribuição de conteúdo..."}
```

Simples e isolado — não usa TTS nem GPT. O `/api/falar` faz coisas demais para ser reaproveitado aqui.

---

### Endpoints existentes usados na confirmação

O frontend chama diretamente após confirmação:

```
POST /api/anuncios/drive/preparar   → retorna {token, resumo}
GET  /api/anuncios/drive/stream/<token>  → SSE com progresso
```

O payload enviado ao `/preparar` é montado pelo frontend com os `params` confirmados.

---

## Frontend — `planejador.js`

### Estado

```javascript
var _messages = [];     // [{role: 'user'|'assistant', content: string}]
var _params   = {};     // parâmetros acumulados (atualizado a cada resposta do Claude)
var _estado   = 'chat'; // 'chat' | 'confirmando' | 'subindo' | 'concluido'
var _gravando = false;  // controle do microfone
```

### Funções públicas (window.*)

```
planejadorInit()             — init ao entrar na aba, foca o input
planejadorEnviar()           — envia mensagem de texto
planejadorConfirmar()        — executa Drive Batch após confirmação
planejadorCancelar()         — volta ao estado 'chat', descarta card
planejadorNovaConversa()     — limpa estado e histórico
planejadorToggleMic()        — inicia/para gravação de áudio
```

### Fluxo de mensagem

```
1. Usuário digita texto (ou grava áudio → transcreve → exibe no input)
2. planejadorEnviar():
   - Adiciona mensagem em _messages
   - Renderiza bolha do usuário
   - Mostra "Jake está digitando..."
   - POST /api/planejador/interpretar {messages, params}
   - Atualiza _params com resposta
   - Se pronto: false → renderiza bolha do Jake com a resposta
   - Se pronto: true → renderiza card de confirmação (muda _estado para 'confirmando')
3. Usuário clica "Confirmar e Subir":
   - planejadorConfirmar()
   - Monta payload Drive Batch a partir de _params
   - POST /api/anuncios/drive/preparar
   - Abre SSE /api/anuncios/drive/stream/<token>
   - Renderiza mensagens de progresso no chat
   - No evento 'concluido' → mensagem de sucesso + botão "Nova conversa"
```

### Card de confirmação

Renderizado como mensagem especial do Jake (não uma bolha normal):

```
┌─────────────────────────────────────┐
│  📋 RESUMO DA CAMPANHA              │
│                                     │
│  Cliente    Queen Poltronas         │
│  Objetivo   Engajamento             │
│  Drive      drive.google.com/...    │
│  Orçamento  R$ 80/dia               │
│  Público    Mulheres 25-45          │
│  Copy       "Renove seu lar..." /   │
│             "Descubra as melhores…" │
│                                     │
│  [✓ Confirmar e Subir] [✎ Ajustar] │
└─────────────────────────────────────┘
```

Botão "Ajustar" volta ao estado `chat` com o histórico preservado — usuário pode corrigir na conversa.

### Progresso no chat

Mensagens de progresso do SSE são renderizadas como bolhas do Jake em tempo real:

```
⏳ Conectando ao Drive...
⏳ Baixando criativos (3 imagens encontradas)...
⏳ Criando campanha "Queen Poltronas — Engajamento Mai/26"...
⏳ Criando conjunto de anúncios...
⏳ Publicando anúncios (1/3)...
✅ Campanha criada com sucesso!
   Campaign ID: 120210XXXXXXXXX
```

### Input de áudio

Botão microfone na barra de input. Ao clicar:
1. Solicita permissão `getUserMedia({audio: true})`
2. Inicia `MediaRecorder` (formato webm/opus)
3. Botão fica vermelho pulsando enquanto grava
4. Clique novamente → para gravação → POST `/api/planejador/transcrever`
5. Texto transcrito aparece no campo de input
6. Usuário revisa e pressiona Enter (não envia automaticamente — usuário confirma o que foi transcrito)

---

## Dashboard — Alterações

### `dashboard.html`

**Nav item** (após "Subir Anúncios"):
```html
<a class="nav-item" data-page="planejador" href="#">
  <span class="nav-icon">💬</span>
  <span class="nav-label">Planejador</span>
</a>
```

**Page section:**
```html
<section class="page" id="page-planejador">
  <div class="plan-layout">
    <div class="plan-header">
      <div class="plan-title">Planejador de Campanhas</div>
      <button onclick="planejadorNovaConversa()" class="anu-btn-secondary" style="font-size:11px">+ Nova conversa</button>
    </div>
    <div id="plan-chat" class="plan-chat"></div>
    <div class="plan-input-bar">
      <button id="plan-mic-btn" class="plan-mic-btn" onclick="planejadorToggleMic()">🎤</button>
      <input id="plan-input" class="plan-input" type="text"
             placeholder="Ex: sobe campanha para Queen Poltronas, engajamento, link do drive..."
             onkeydown="if(event.key==='Enter')planejadorEnviar()">
      <button class="plan-send-btn" onclick="planejadorEnviar()">→</button>
    </div>
  </div>
</section>
```

**Links CSS e script** adicionados junto aos outros.

### `app.js`

Adicionar `"planejador"` na lista de rotas válidas e callback:
```javascript
if (id === "planejador" && typeof planejadorInit === "function") planejadorInit();
```

---

## CSS — `planejador.css`

Estilos de chat estilo "mensagens":
- `.plan-layout` — flex column, altura total
- `.plan-chat` — área scrollável de mensagens, flex-grow
- `.plan-msg-user` — bolha direita, fundo accent (#00b4d8 fraco)
- `.plan-msg-jake` — bolha esquerda, fundo escuro
- `.plan-msg-card` — card de confirmação com borda, fundo distinto
- `.plan-input-bar` — barra fixa no rodapé com input + botões
- `.plan-mic-btn.gravando` — estado vermelho pulsando durante gravação
- `.plan-typing` — indicador "Jake está digitando..." com animação de 3 pontos

---

## Prompt ao Claude (em `/api/planejador/interpretar`)

```
Você é o Jake, assistente de tráfego pago. Sua tarefa é extrair parâmetros de campanha
Meta Ads a partir da conversa com o usuário.

CLIENTES DISPONÍVEIS (use para resolver cliente_nome → cliente_id):
{lista de clientes do banco: id, nome, agencia, campanha_tipo padrão}

PARÂMETROS JÁ EXTRAÍDOS:
{params acumulados em JSON}

CONVERSA:
{histórico de mensagens}

Retorne APENAS JSON válido:
{
  "resposta": "<mensagem para o usuário — amigável, direta, em português>",
  "params": {
    "cliente_id": <int ou null>,
    "cliente_nome": "<string ou null>",
    "campanha_nome": "<string ou null>",
    "objetivo": "<MESSAGES|ENGAGEMENT|REACH|PURCHASE ou null>",
    "drive_link": "<string ou null>",
    "orcamento_diario": <float ou null>,
    "publico_descricao": "<string ou null>",
    "copy_titulo": "<string ou null>",
    "copy_texto": "<string ou null>"
  },
  "duvidas": ["<campo faltando>", ...],
  "pronto": <true se cliente_id, objetivo, drive_link e orcamento_diario estão preenchidos>
}

Regras:
- Preserve params já extraídos — só atualize se o usuário corrigir
- Se cliente não identificado na lista, coloque cliente_id: null e pergunte
- Se copies não fornecidas e pronto: true, gere copy_titulo e copy_texto baseados no cliente e objetivo
- campanha_nome auto-gerado se null: "{cliente_nome} — {objetivo} {mês}/{ano}"
- Seja conciso na resposta — máximo 2 frases
```

---

## Fora de Escopo

- Histórico de conversas persistido no banco (cada sessão começa limpa)
- Edição do card de confirmação inline (usuário ajusta conversando)
- Suporte a múltiplos clientes em uma mesma conversa (um cliente por conversa)
- Criação de públicos novos (usa público existente do cliente ou descrição livre)
- Notificações por Telegram ao concluir
