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
  app.py                     # 3 endpoints novos: interpretar + transcrever + subir
  static/js/app.js           # rota #planejador + callback planejadorInit()
```

### Sem dependências novas

Usa `anthropic` SDK (`claude-sonnet-4-6`), OpenAI Whisper-1 — tudo já instalado.

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

**Objetivos suportados** (apenas os aceitos pelo backend Meta Ads):

| Código | Label |
|---|---|
| `MESSAGES` | Mensagens/WhatsApp |
| `ENGAGEMENT` | Engajamento / visitas ao perfil |
| `PURCHASE` | Conversões / Vendas |

**Tratamento de erro do Claude:** Se a resposta não for JSON válido (ex: markdown com ```json), o endpoint aplica regex para extrair o primeiro bloco JSON. Se ainda assim falhar, retorna `{"error": "Não consegui interpretar. Pode reformular?"}` com status 200 — o frontend renderiza como mensagem de erro no chat, sem travar a conversa.

---

### `POST /api/planejador/transcrever`

Recebe arquivo de áudio (multipart `audio`), chama Whisper-1, retorna texto transcrito.

**Request:** multipart/form-data com campo `audio` (webm, mp4, ogg, mp3)

**Response:**
```json
{"text": "sobe campanha para Queen Poltronas, distribuição de conteúdo..."}
```

Simples e isolado — não usa TTS nem GPT. O `/api/falar` faz coisas demais para ser reaproveitado aqui.

**Nota sobre Safari:** `MediaRecorder` em Safari grava em mp4/aac, não webm. O JS deve detectar o formato suportado via `MediaRecorder.isTypeSupported()` e enviar o arquivo no formato correto. O endpoint `/transcrever` aceita qualquer formato suportado pelo Whisper.

---

### `POST /api/planejador/subir`

Endpoint de submissão. Recebe os params confirmados, baixa os criativos do Google Drive, cria a campanha no Meta Ads e retorna progresso via **SSE** (`text/event-stream`).

**Request:**
```json
{
  "cliente_id": 5,
  "campanha_nome": "Queen Poltronas — Engajamento Mai/26",
  "objetivo": "ENGAGEMENT",
  "drive_link": "https://drive.google.com/drive/folders/...",
  "orcamento_diario": 80.0,
  "publico_descricao": "Mulheres 25-45 interessadas em decoração",
  "copy_titulo": "Renove seu lar",
  "copy_texto": "Descubra as melhores poltronas..."
}
```

**SSE events emitidos:**
```
data: {"status": "baixando", "msg": "Conectando ao Drive..."}
data: {"status": "baixando", "msg": "3 criativos encontrados"}
data: {"status": "criando", "msg": "Criando campanha no Meta Ads..."}
data: {"status": "criando", "msg": "Criando conjunto de anúncios..."}
data: {"status": "publicando", "msg": "Publicando anúncio 1/3..."}
data: {"status": "concluido", "msg": "✅ Campanha criada!", "campaign_id": "120210XXXXXXXXX"}
data: {"status": "erro", "msg": "Descrição do erro"}
```

**Lógica interna:**
1. Busca cliente em `ad_client_profiles` pelo `cliente_id`
2. Resolve token via `_resolve_token(cliente.token_key)`
3. Baixa arquivos do Drive link para `_TMP_DIR` (mesmo padrão do Drive Batch)
4. Para cada criativo baixado: faz upload para o Meta como `AdCreative` com o copy fornecido
5. Cria campanha → conjunto → ads via `meta_api.py` (mesmas helpers já existentes)
6. Loga em `controle_relatorios_semanais` ou tabela existente de tracking
7. Emite eventos SSE ao longo do processo

**Não duplica lógica do Drive Batch** — usa as mesmas funções internas de `meta_api.py` (`criar_campanha`, `criar_conjunto`, `criar_ad`). O Drive Batch e o Planejador são fluxos diferentes de entrada para a mesma engine.

**Fallback de público:** se `publico_descricao` fornecido mas não mapeado a targeting JSON, usa `cliente.publico_json` do banco. Se nem isso existir, retorna erro SSE pedindo ao usuário para configurar o público no perfil do cliente.

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
planejadorEnviar()           — envia mensagem de texto (bloqueado durante 'subindo')
planejadorConfirmar()        — dispara POST /api/planejador/subir + abre SSE
planejadorCancelar()         — remove card, volta a _estado='chat'; preserva _messages e _params
planejadorNovaConversa()     — zera _messages=[], _params={}, _estado='chat'; limpa o chat na UI
planejadorToggleMic()        — inicia/para gravação de áudio
```

### Transições de estado

```
'chat'        → 'confirmando'  quando Claude retorna pronto: true
'confirmando' → 'chat'         quando usuário clica "Ajustar" (planejadorCancelar)
'confirmando' → 'subindo'      quando usuário clica "Confirmar e Subir" (planejadorConfirmar)
'subindo'     → 'concluido'    quando SSE emite status: 'concluido'
'subindo'     → 'chat'         quando SSE emite status: 'erro' (mostra erro no chat, permite nova tentativa)
qualquer      → 'chat'         quando usuário clica "Nova conversa" (planejadorNovaConversa)
```

**Comportamento da UI por estado:**
- `chat`: input habilitado, mic habilitado
- `confirmando`: input desabilitado (usuário deve clicar Confirmar ou Ajustar), card visível
- `subindo`: input desabilitado, botões do card ocultos, progresso SSE renderizado no chat
- `concluido`: input desabilitado, botão "Nova conversa" visível

### Fluxo de mensagem

```
1. Usuário digita texto (ou grava áudio → transcreve → exibe no input → usuário pressiona Enter)
2. planejadorEnviar():
   - Se _estado !== 'chat' → ignora
   - Adiciona mensagem em _messages
   - Renderiza bolha do usuário
   - Mostra indicador "Jake está digitando..."
   - POST /api/planejador/interpretar {messages, params: _params}
   - Atualiza _params com params retornados
   - Se error → renderiza bolha de erro do Jake, permanece em 'chat'
   - Se pronto: false → renderiza bolha do Jake com resposta, permanece em 'chat'
   - Se pronto: true → renderiza card de confirmação, muda _estado para 'confirmando'
3. Usuário clica "Confirmar e Subir" → planejadorConfirmar():
   - Muda _estado para 'subindo'
   - POST /api/planejador/subir com _params
   - Abre EventSource para SSE stream
   - Cada evento SSE → renderiza bolha de progresso no chat
   - status 'concluido' → muda _estado='concluido', renderiza mensagem de sucesso
   - status 'erro' → muda _estado='chat', renderiza mensagem de erro
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

### `static/js/app.js`

Em `showPage()`, dentro do bloco de callbacks (após o `if (id === "dr" ...)`), adicionar:
```javascript
if (id === "gestor" && typeof window.gestorInit === "function") {
  window.gestorInit();
}
// ↓ adicionar aqui:
if (id === "planejador" && typeof window.planejadorInit === "function") {
  window.planejadorInit();
}
```

Na lista `valid` (linha com `var valid = [...]`), adicionar `"planejador"` após `"gestor"`:
```javascript
var valid = [..., "gestor", "planejador", ...];
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
    "objetivo": "<MESSAGES|ENGAGEMENT|PURCHASE ou null>",
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
- campanha_nome auto-gerado se null: "{cliente_nome} — {objetivo_label} {mês}/{ano}" onde objetivo_label é o label legível (ex: "Engajamento", não "ENGAGEMENT")
- Seja conciso na resposta — máximo 2 frases
```

---

## Fora de Escopo

- Histórico de conversas persistido no banco (cada sessão começa limpa)
- Edição do card de confirmação inline (usuário ajusta conversando)
- Suporte a múltiplos clientes em uma mesma conversa (um cliente por conversa)
- Criação de públicos novos (usa público existente do cliente ou descrição livre)
- Notificações por Telegram ao concluir
