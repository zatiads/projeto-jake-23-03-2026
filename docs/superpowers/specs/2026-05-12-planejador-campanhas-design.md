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
  app.py                     # 4 endpoints novos: interpretar + transcrever + subir (POST) + subir/stream/<token> (GET/SSE)
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

### `POST /api/planejador/subir` + `GET /api/planejador/subir/stream/<token>`

Fluxo em **duas fases** (igual ao Drive Batch) para compatibilidade com `EventSource` do browser que não suporta POST.

**Fase 1 — POST `/api/planejador/subir`**

Valida e salva o payload em memória, retorna token de sessão.

Request:
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

Response:
```json
{"token": "uuid4-aqui"}
```

`publico_descricao` é campo de exibição (card + UX) — **não** é usado como targeting. O backend sempre usa `cliente.publico_json` como `publico` dict para `criar_conjunto`. Se `publico_json` for nulo, retorna 400 com mensagem pedindo ao usuário configurar o público no perfil do cliente.

**Fase 2 — GET `/api/planejador/subir/stream/<token>`** (SSE)

Executa a criação. O token expira em 30 minutos (mesmo padrão do Drive Batch).

SSE events:
```
data: {"status": "baixando", "msg": "Conectando ao Drive..."}
data: {"status": "baixando", "msg": "3 criativos encontrados"}
data: {"status": "criando",  "msg": "Criando campanha no Meta Ads..."}
data: {"status": "criando",  "msg": "Criando conjunto de anúncios..."}
data: {"status": "publicando","msg": "Publicando anúncio 1/3..."}
data: {"status": "concluido","msg": "✅ Campanha criada!", "campaign_id": "120210XXXXXXXXX"}
data: {"status": "erro",     "msg": "Descrição do erro"}
```

**Lógica interna da Fase 2:**

1. Busca cliente em `ad_client_profiles` pelo `cliente_id`
2. Obtém token Meta via `os.getenv(cliente.token_key)` diretamente (não via `meta_api._resolve_token` — `VALID_TOKEN_KEYS` do meta_api não inclui todos os token keys válidos do app)
3. **Download do Drive** — dois passos (igual ao `drive_listar` + download do Drive Batch):
   - Parseia o `drive_link` para extrair `folder_id`
   - Lista arquivos da pasta via `GET https://www.googleapis.com/drive/v3/files?q='{folder_id}'+in+parents&key={GOOGLE_API_KEY}`
   - Baixa cada arquivo por `file_id` via `GET https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={GOOGLE_API_KEY}`
   - Salva em `_TMP_DIR` com `uuid4` como nome; coleta lista de `(tmp_path, ext)`
4. Para cada criativo baixado: faz upload para o Meta como `AdImage`/`AdVideo`, obtém `hash` ou `video_id`
5. Resolve parâmetros do cliente:
   - `page_id = cliente.page_id` (obrigatório — retorna erro SSE se ausente)
   - `publico = cliente.publico_json` (dict com `idade_min`, `idade_max`, `genders`)
   - `localizacao = cliente.localizacao_json` (dict com `paises` e/ou `cidades`)
   - `opt_goal = cliente.optimization_goal` (opcional)
   - `pixel_id = cliente.pixel_id` (opcional — necessário para PURCHASE)
   - `link_url = cliente.link_url` (usado para ENGAGEMENT e PURCHASE)
   - `cta` = mapeado via `{"MESSAGES": "SEND_MESSAGE", "PURCHASE": "SHOP_NOW", "ENGAGEMENT": "LEARN_MORE"}[objetivo]`
6. **CBO logic:** `cbo = objetivo not in ("ENGAGEMENT", "PURCHASE")`
   - Se `cbo=True` (MESSAGES): orçamento no nível de campanha
   - Se `cbo=False` (ENGAGEMENT, PURCHASE): orçamento no nível de conjunto de anúncios
7. Chama `meta_api.criar_campanha(token, account_id, campanha_nome, objetivo, cbo, orcamento_diario)`
8. Chama `meta_api.criar_conjunto(token, account_id, campaign_id, objetivo, publico, localizacao, orcamento_diario_centavos, opt_goal, pixel_id)` — nota: `orcamento_diario` em R$ deve ser convertido para centavos (× 100) conforme padrão da Meta API
9. Para cada criativo: chama `meta_api.criar_anuncio(token, account_id, adset_id, page_id, creative_ref, copy_titulo, copy_texto, cta, link_url)`
10. Em caso de erro após criar campanha/conjunto: chama `meta_api.deletar_objeto_meta` para rollback (mesmo padrão do Drive Batch)
11. Não loga em banco — sem nova tabela. O tracking existente de campanhas (`controle_relatorios_semanais`) não se aplica aqui.

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
   - POST /api/planejador/subir com _params → recebe {token}
   - Abre new EventSource('/api/planejador/subir/stream/' + token)
   - Cada evento SSE → renderiza bolha de progresso no chat
   - status 'concluido' → fecha EventSource, muda _estado='concluido', renderiza mensagem de sucesso
   - status 'erro' → fecha EventSource, muda _estado='chat', renderiza mensagem de erro
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
