# Drive Batch Ads — Design Spec

## Goal

Allow the user to paste a public Google Drive folder link containing N images, configure multiple ad sets with budget and creative count, auto-generate AI copies per image via Claude Vision, and publish to one or multiple Meta Ads clients in a single flow.

## Architecture

A new "Drive Batch" tab in the Anuncios module. 4-step wizard: Drive + Client → Campaign + Adsets → Generate Copies → Review + Publish. Backend: 6 new Flask endpoints. Google Drive accessed via REST API with `GOOGLE_API_KEY` (no OAuth, no new packages — `requests` only). SSE stream for copy generation and publish progress, same pattern as existing lote/multi-cliente.

## Tech Stack

- **Backend**: Flask, `requests` (Drive REST API v3 + Meta Ads API), `anthropic` SDK (Claude Vision, already imported)
- **Frontend**: Vanilla JS ES5 IIFE (same pattern as `lote.js`, `multi-cliente.js`)
- **Drive auth**: Public API key (`GOOGLE_API_KEY` in `.env`) — no OAuth, no service account, no new packages
- **Meta auth**: Existing per-client `token_key` from `ad_client_profiles`

## Dependency

Add `GOOGLE_API_KEY` to `.env`. This is a standard Google Cloud Console API key with Drive API enabled (free tier). Assumed available before implementation. The key only needs read access to public files.

## Confirmed existing helpers (app.py)

- `_meta_api.criar_campanha(token, account_id, nome, objetivo, status)` — creates Meta campaign
- `_meta_api.criar_conjunto(token, account_id, campaign_id, camp_tipo, publico, localizacao, orcamento_centavos, optimization_goal)` — creates adset
- `_meta_api.criar_anuncio(token, account_id, adset_id, creative)` — creates ad
- `_meta_api.upload_imagem(token, account_id, file_bytes, filename)` — uploads image, returns dict with `hash`
- `_meta_api.deletar_objeto_meta(token, object_id)` — deletes any Meta object by ID
- `_lote_payloads` dict — already exists in app.py for token storage
- `ad_publish_log` table — already exists in DB

---

## Step 1 — Drive + Client Selection

### UI
- Text input: paste Google Drive public folder URL
- Button "Carregar" → calls `POST /api/anuncios/drive/listar`
- Shows file count + filename list with thumbnails
- Mode toggle: **Um cliente** (select dropdown from `ad_client_profiles`) OR **Varios clientes** (checkbox list, same pattern as multi-cliente)
- Button "Proximo" → advances to Step 2

### Backend: `POST /api/anuncios/drive/listar`
- Input: `{ "url": "<drive_folder_url>" }`
- Extract folder ID from URL — supports:
  - `/folders/<id>` (e.g. `drive.google.com/drive/folders/1ABC...`)
  - `id=<id>` query param
- Call Drive API v3 via `requests.get()`:
  ```python
  requests.get(
      "https://www.googleapis.com/drive/v3/files",
      params={
          "q": f"'{folder_id}' in parents",
          "fields": "files(id,name,mimeType,thumbnailLink)",
          "key": GOOGLE_API_KEY
      }
  )
  ```
  Note: pass `q` via `params` dict so `requests` handles URL encoding automatically.
- Filter: only files where `mimeType` in `{image/jpeg, image/png, image/webp, image/gif}`
- Returns: `{ "files": [{"id": "...", "name": "...", "thumbnailLink": "..."}], "total": N }`
- Error if API returns non-200, or zero image files found

---

## Step 2 — Campaign + Adset Configuration

### UI

**Single client:**
- Button "Buscar campanhas ativas" → calls `GET /api/anuncios/drive/campanhas?cliente_id=X`
- Shows campaign list (name + id + status) → user selects one
- OR toggle "Criar nova campanha" → text input for campaign name

**Multi-client:**
- Radio: "Criar nova campanha para todos" (text input for name) OR "Usar campanha salva de cada cliente" (uses `campanha_id_existente` from each client's profile — confirmed present in `ad_client_profiles`)

**Adset configuration (all modes):**
- `campanha_tipo` — dropdown: MESSAGES / PURCHASE / ENGAGEMENT (drives copy prompt, campaign objective, CTA)
- `num_conjuntos` — number of ad sets (integer, min 1)
- `orcamento_por_conjunto` — budget per adset in R$ (float)
- `criativos_por_conjunto` — creatives per adset (integer, min 1)
- Live validation: `num_conjuntos x criativos_por_conjunto` must equal total images from Step 1
  - If mismatch: show "X conjuntos x Y criativos = Z, mas a pasta tem N imagens"
- Button "Proximo" → advances to Step 3 (only enabled when validation passes)

### Backend: `GET /api/anuncios/drive/campanhas?cliente_id=X`
- Fetch client from `ad_client_profiles` WHERE id = X
- Call Meta Graph API v21.0:
  ```
  GET https://graph.facebook.com/v21.0/<account_id>/campaigns
      ?fields=id,name,effective_status
      &filtering=[{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED"]}]
      &access_token=<token>
  ```
- Returns: `{ "campanhas": [{"id": "...", "name": "...", "status": "..."}] }`

---

## Step 3 — AI Copy Generation (two-phase)

### UI
- Button "Gerar Copies" → calls `POST /api/anuncios/drive/iniciar-copies` → gets `copies_token` → opens SSE to `GET /api/anuncios/drive/gerar-copies/stream/<copies_token>`
- Progress counter per image: "Gerando 2/30..."
- Results shown in editable grid: each row has thumbnail + `titulo` input + `texto` textarea
- User can edit any copy before proceeding
- Button "Proximo" → advances to Step 4 (enabled once all copies done)

### Backend: `POST /api/anuncios/drive/iniciar-copies`
- Input: `{ "files": [{"id": "...", "name": "..."}], "campanha_tipo": "...", "cliente_id": X }`
- Stores payload in `_lote_payloads[copies_token]` with `threading.Timer(1800, cleanup)` TTL
- Returns: `{ "copies_token": "<uuid>" }`

This two-phase design avoids passing up to 100 file IDs in a GET query string (which would exceed safe URL length limits of ~2000 chars for 100 × 33-char IDs).

### Backend: `GET /api/anuncios/drive/gerar-copies/stream/<copies_token>`
- Pops payload from `_lote_payloads`
- Bare generator function, no `stream_with_context` (same as lote/multi-cliente stream pattern)
- For each file in payload:
  1. Download image bytes from Drive:
     ```python
     requests.get(
         f"https://www.googleapis.com/drive/v3/files/{file_id}",
         params={"alt": "media", "key": GOOGLE_API_KEY},
         stream=True
     )
     ```
  2. Save to `/tmp/<uuid><ext>` (ext from MIME type mapping) with `threading.Timer(1800, cleanup)` TTL
  3. Encode as base64
  4. Call Claude Vision (`claude-sonnet-4-6`) with image + system prompt (see below)
  5. Parse JSON from response → `{ "titulo": "...", "texto": "..." }`
  6. Emit SSE:
     ```
     event: copy
     data: {"index": N, "file_id": "...", "tmp_uuid": "...", "ext": ".jpg", "titulo": "...", "texto": "..."}
     ```
- On error for a single image:
  ```
  event: erro
  data: {"index": N, "file_id": "...", "msg": "..."}
  ```
- Final event:
  ```
  event: concluido
  data: {"total": 30}
  ```

**Copy generation system prompts (per campanha_tipo):**
- `MESSAGES`: "Voce e um copywriter especialista em anuncios de WhatsApp. Analise a imagem e crie uma copy persuasiva focada em gerar mensagens no WhatsApp. Retorne APENAS JSON: {\"titulo\": \"string max 40 chars\", \"texto\": \"string max 125 chars\"}."
- `PURCHASE`: "Voce e um copywriter especialista em conversao. Analise a imagem e crie uma copy focada em venda direta com urgencia. Retorne APENAS JSON: {\"titulo\": \"string max 40 chars\", \"texto\": \"string max 125 chars\"}."
- `ENGAGEMENT`: "Voce e um copywriter especialista em engajamento. Analise a imagem e crie uma copy instigante que gere curtidas e comentarios. Retorne APENAS JSON: {\"titulo\": \"string max 40 chars\", \"texto\": \"string max 125 chars\"}."

---

## Step 4 — Review + Publish (two-phase)

### UI
- Summary card: "X cliente(s) x N conjuntos x M anuncios = total publicacoes"
- Adset breakdown table: "Conjunto 1: imagens 1-10 | Conjunto 2: imagens 11-20..."
- Warning if any copy row has an error (user must fill manually before publishing)
- Button "Publicar" → calls `POST /api/anuncios/drive/preparar` → on success opens SSE to `GET /api/anuncios/drive/stream/<token>`
- Progress list: one row per client/adset/ad with status icons (publicando / ok / erro)
- Button "Voltar" → goes back to Step 3 (copies preserved in JS state)
- If tmp files expired: JS receives `{ "expired": true }` from preparar → shows "Arquivos expiraram — clique em Regerar" button that resets to Step 3

### Backend: `POST /api/anuncios/drive/preparar`
Input:
```json
{
  "cliente_ids": [1, 2],
  "mode": "single | multi",
  "campanha": {
    "tipo": "nova | existente | salva",
    "id": "<campaign_id_if_existente>",
    "nome": "Nome da campanha (if nova)"
  },
  "conjuntos": {
    "num": 3,
    "orcamento": 10.00,
    "criativos_por": 10
  },
  "campanha_tipo": "MESSAGES | PURCHASE | ENGAGEMENT",
  "copies": [
    { "file_id": "...", "tmp_uuid": "...", "ext": ".jpg", "titulo": "...", "texto": "..." }
  ]
}
```
Validations (in order):
1. All `cliente_ids` exist in `ad_client_profiles`
2. For `mode=multi` + `campanha.tipo=salva`: each client must have non-null `campanha_id_existente`
3. `conjuntos.num x conjuntos.criativos_por == len(copies)`
4. All tmp files (`/tmp/<tmp_uuid><ext>`) exist on disk → if any missing: return `{ "ok": false, "expired": true }`

On success: store payload in `_lote_payloads[db_token]` with `threading.Timer(1800, cleanup)`. Returns: `{ "token": "<db_token>", "resumo": { "clientes": N, "conjuntos": N, "total_ads": N } }`

### Backend: `GET /api/anuncios/drive/stream/<db_token>`
- Bare generator function, no `stream_with_context`
- Pops payload from `_lote_payloads`
- For each client:
  1. Fetch client profile from DB: `account_id`, `token_key`, `localizacao_json`, `publico_json`, `optimization_goal`, `campanha_id_existente`, `link_url`
  2. Resolve `token` from `token_key` env var
  3. Track `newly_created_campaign = False` and `created_adset_ids = []`
  4. Resolve `campaign_id`:
     - `tipo=existente`: use `campanha.id` from payload
     - `tipo=salva`: use client's `campanha_id_existente`
     - `tipo=nova`: call `_meta_api.criar_campanha(token, account_id, nome, objetivo, "PAUSED")` where objetivo maps from `campanha_tipo`:
       - `MESSAGES → MESSAGES`
       - `PURCHASE → OUTCOME_SALES`
       - `ENGAGEMENT → POST_ENGAGEMENT`
       - `special_ad_categories = []` (handled inside `criar_campanha`)
       Set `newly_created_campaign = True`
  5. Distribute copies into adsets sequentially:
     - adset 0 → `copies[0 .. criativos_por-1]`
     - adset 1 → `copies[criativos_por .. 2*criativos_por-1]`
     - etc.
  6. For each adset (index 0..num-1):
     a. Emit: `event: publicando\ndata: {"msg": "Cliente X — Conjunto N/total"}`
     b. Call `_meta_api.criar_conjunto(token, account_id, campaign_id, campanha_tipo, publico_json, localizacao_json, int(orcamento*100), optimization_goal)` → `adset_id`
     c. On adset failure:
        - Delete all adsets created so far for this client: `for aid in created_adset_ids: _meta_api.deletar_objeto_meta(token, aid)`
        - If `newly_created_campaign`: also call `_meta_api.deletar_objeto_meta(token, campaign_id)`
        - Emit error, skip remaining adsets for this client, continue next client
     d. `created_adset_ids.append(adset_id)`
     e. For each copy in this adset:
        - Read `/tmp/<tmp_uuid><ext>` bytes
        - Call `_meta_api.upload_imagem(token, account_id, file_bytes, filename)` → `result["hash"]`
        - Build creative: `{"title": titulo, "body": texto, "image_hash": hash, "link_url": client.link_url}`
        - Call `_meta_api.criar_anuncio(token, account_id, adset_id, creative)` → `ad_id`
        - On ad failure: emit error for this ad, continue (no rollback of adset)
        - Log to `ad_publish_log`: `(cliente_id, account_id, campaign_id, adset_id, ad_id, status, NULL, payload_json)`
        - Emit: `event: ok\ndata: {"msg": "Ad criado: titulo"}`
- After all clients: emit `event: concluido\ndata: {}`
- Cleanup: delete all `/tmp/<tmp_uuid><ext>` files referenced in the payload

---

## Rollback Policy

| Scenario | Action |
|---|---|
| Adset creation fails, campaign newly created | Delete all `created_adset_ids` for this client, then delete the campaign |
| Adset creation fails, campaign was pre-existing | Delete only `created_adset_ids` for this client (not the campaign) |
| Ad creation fails within an adset | Log error, continue with remaining ads — no rollback of adset |
| Client N fails in multi-client mode | Log error, continue with client N+1 — no rollback of already-published clients |

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `app.py` | Modify | 6 new endpoints: `/drive/listar`, `/drive/campanhas`, `/drive/iniciar-copies`, `/drive/gerar-copies/stream/<token>`, `/drive/preparar`, `/drive/stream/<token>` |
| `templates/dashboard.html` | Modify | Add "Drive Batch" tab button + 4-step wizard HTML |
| `static/js/drive-batch.js` | Create | IIFE exporting `window.driveBatchInit`. Wizard state, Drive listing, copy grid, SSE for copies and publish |
| `static/js/anuncios.js` | Modify | Add 'drive' to tab array; call `window.driveBatchInit()` when tab === 'drive' |
| `static/css/anuncios.css` | Modify | Styles for copy grid rows, adset config inputs |

---

## Error Handling Summary

| Error | UX Response |
|---|---|
| Drive folder not public / not found | Inline error in Step 1, user fixes URL |
| No image files in folder | Inline error in Step 1 |
| Count mismatch | Inline error in Step 2, user adjusts config |
| Single copy generation failure | Inline error in grid row; user fills manually |
| Tmp files expired at publish time | preparar returns `expired:true` → JS shows "Regerar" button resetting to Step 3 |
| Meta API failure during publish | SSE erro event per item; stream continues |

---

## Key Constraints

- Max images: 100 (Drive API default page size; no pagination in scope)
- Image formats: JPG, PNG, WebP, GIF only
- Copy generation: ~1-3s per image via SSE stream; user sees per-image progress
- Tmp file TTL: 30 min from download (`threading.Timer`)
- `ad_publish_log`: one row per ad, `audience_id=NULL`
- All clients in multi-client mode share the same adset structure
- `GOOGLE_API_KEY` must be present in `.env` — feature will return 500 if missing
- All DB fields used (`campanha_id_existente`, `optimization_goal`, `localizacao_json`, `publico_json`, `link_url`) confirmed present in `ad_client_profiles`
- `ad_publish_log` and `_meta_api.deletar_objeto_meta` confirmed to exist

---

## Not In Scope

- Per-client adset configuration in multi-client mode
- Scheduling / delayed publish
- Video support
- Drive folder pagination beyond 100 images
