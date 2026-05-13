# Spec: Lote — Campanha Existente + Link do Drive + Fix Visual

**Data:** 2026-05-13
**Módulo:** Jake OS — Subir Anúncios, tab Lote
**Scope:** Três melhorias no tab Lote existente — nenhuma nova aba.

---

## Contexto

O tab Lote permite publicar anúncios em lote para múltiplos clientes. Hoje ele:
- Sempre cria uma campanha nova
- Só aceita upload de arquivo como criativo
- Tem listas (`<select>`) com fundo branco e texto ilegível no tema dark

O HTML do tab Lote está estático em `dashboard.html`. A lógica de estado está em `lote.js`, que persiste em `localStorage` com chave `jakeos_lote_v1`. O backend de publicação é o endpoint `POST /api/anuncios/lote/publicar`.

---

## Funcionalidades

### 1. Campanha Existente

**Toggle no formulário do Lote (HTML estático em dashboard.html):**
```
[ Nova campanha ]  [ Campanha existente ]
```

- **Nova campanha** (padrão): comportamento atual — campos `campanha_nome` e `campanha_tipo`
- **Campanha existente**: campos de nome e tipo somem; aparece `<select id="lote-camp-existente">` populado via API

**Endpoint de busca de campanhas:**
```
GET /api/anuncios/lote/campanhas?account_id=act_XXXXX&token_key=META_TOKEN_DENTTO
```
- Decorado com `@login_required`
- Backend faz `token_val = os.getenv(token_key)` e valida `token_key in _VALID_TOKEN_KEYS`
- Chama `GET /{account_id}/campaigns?fields=id,name,status&limit=50` na Meta API v21.0
- Retorna `{"campanhas": [{id, name, status}]}` — lista vazia `[]` se não houver campanhas
- Em erro de token/API: retorna `{"error": "..."}` com status 400

**Frontend (lote.js):**
- Ao trocar para modo "existente": verifica se cliente está selecionado
  - Não selecionado → aviso "Selecione o cliente primeiro", toggle volta para "nova"
  - Selecionado → faz fetch `/api/anuncios/lote/campanhas?account_id=...&token_key=...` usando `_cliente.account_id` e `_cliente.token_key`
- Ao trocar de cliente (evento change no select de cliente): se modo for "existente", limpa e recarrega o seletor de campanhas
- Em erro no fetch: exibe "Erro ao carregar campanhas" dentro do `<select>` desabilitado
- LocalStorage (`jakeos_lote_v1`) estendido com: `modoCamp: 'nova'|'existente'` e `campExistenteId: ''`

**`camp_tipo` no modo existente:**
- `campanha_tipo` permanece obrigatório mesmo no modo existente — é usado para configurar o adset (optimization_goal, billing_event). O campo `campanha_tipo` permanece visível no formulário em ambos os modos.

**Fluxo de publicação com campanha existente:**
- Frontend inclui no payload: `{"modo_campanha": "existente", "campaign_id_existente": "XXXXXXX", "campanha_tipo": "MESSAGES", ...}`
- Backend valida: se `modo_campanha == "existente"`, verifica que `campaign_id_existente` pertence à conta do cliente chamando `GET /{campaign_id}?fields=account_id` na Meta API. Se account_id não bater → retorna erro 400 "Campanha não pertence à conta do cliente"
- Pula `criar_campanha()`, usa `campaign_id_existente` como `campaign_id`
- Cria adset novo na campanha existente + anúncio normalmente

**Payload modificado:**
```json
{
  "modo_campanha": "nova" | "existente",
  "campanha_nome": "...",           // usado se modo=nova
  "campaign_id_existente": "...",   // usado se modo=existente
  "campanha_tipo": "MESSAGES"       // sempre obrigatório (para adset)
}
```

---

### 2. Link do Google Drive como Criativo

**Toggle no campo de criativo (HTML estático em dashboard.html):**
```
[ Upload de arquivo ]  [ Link do Drive ]
```

- **Upload** (padrão): comportamento atual — frontend faz upload via `/api/anuncios/upload-criativo` que retorna `creative_ref` completo
- **Link do Drive**: input de texto para colar URL → botão "Baixar" → backend baixa o arquivo → frontend recebe `creative_ref` completo e prossegue normalmente

**Endpoint de download do Drive:**
```
POST /api/anuncios/lote/drive-download
Body: {"url": "https://drive.google.com/file/d/FILE_ID/view", "account_id": "act_XXX", "token_key": "META_TOKEN_DENTTO"}
```
- Decorado com `@login_required`
- Extrai `FILE_ID` da URL — suporta formatos:
  - `/file/d/FILE_ID/view` ou `/file/d/FILE_ID/`
  - `/open?id=FILE_ID`
  - Se não conseguir extrair: retorna `{"error": "URL inválida"}` 400
- URL de download: `https://drive.google.com/uc?export=download&id=FILE_ID`
- Faz `requests.get(url, stream=True, allow_redirects=True, timeout=30)`
- Detecção de "arquivo não público": se `Content-Type` da resposta for `text/html` → retorna `{"error": "Arquivo não público ou requer confirmação. Compartilhe com 'qualquer pessoa com o link'"}` 400
- MIME types aceitos e extensões: `image/jpeg`→`.jpg`, `image/png`→`.png`, `image/gif`→`.gif`, `video/mp4`→`.mp4`. Outros → retorna `{"error": "Tipo de arquivo não suportado"}` 400
- Salva em `/tmp/{uuid}{ext}`
- **Faz upload da imagem para a conta Meta** usando `_meta_api.upload_imagem()` ou `_meta_api.upload_video()` (mesmo que o fluxo normal de upload)
- Retorna `creative_ref` completo: `{"creative_ref": {"tipo": "imagem", "hash": "..."}, "ok": true}`
- O frontend usa esse `creative_ref` exatamente como usaria o retorno do upload normal

**Frontend (lote.js):**
- Ao clicar "Baixar": desabilita botão, exibe spinner
- Sucesso: armazena `_creative_ref` internamente, exibe preview da imagem (se imagem via `URL.createObjectURL` de blob, ou ícone de vídeo se mp4)
- Erro: exibe mensagem de erro abaixo do input
- LocalStorage estendido com: `modoCriativo: 'upload'|'drive'` e `driveUrl: ''`
- Preview de vídeo: exibe apenas nome/ícone (sem player), consistente com comportamento do upload de vídeo existente

---

### 3. Fix Visual das Listas

**Problema:** `<select>` do módulo anúncios tem fundo branco e texto ilegível no tema dark.

**Fix em `anuncios.css`:**

```css
#page-anuncios select {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(176,190,197,0.12);
  color: rgba(176,190,197,0.9);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  width: 100%;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
}
#page-anuncios select:focus {
  outline: none;
  border-color: rgba(100,181,246,0.4);
}
#page-anuncios option {
  background: #1a1a2e;
  color: rgba(176,190,197,0.9);
}
#page-anuncios select:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

Afeta: seletor de cliente, seletor de campanha existente (novo), e qualquer outro `<select>` no módulo anúncios.

---

## Arquivos Modificados

| Arquivo | Mudança |
|---|---|
| `jake_desktop/app.py` | 2 novos endpoints: `GET /api/anuncios/lote/campanhas` e `POST /api/anuncios/lote/drive-download`; modificar endpoint de publicação lote para aceitar `campaign_id_existente` com validação de ownership |
| `jake_desktop/static/css/anuncios.css` | Fix visual dos `<select>` |
| `jake_desktop/static/js/lote.js` | Toggle nova/existente, toggle upload/drive, fetch campanhas ao trocar cliente, download drive, extensão do localStorage |
| `jake_desktop/templates/dashboard.html` | HTML dos dois toggles no tab Lote |

---

## Fora do Escopo

- Reutilizar adset existente (só campanha)
- Drive autenticado (só links públicos)
- Suporte a múltiplos arquivos via Drive
- Mudanças em outros tabs (publicar, publicos, multi-cliente)
