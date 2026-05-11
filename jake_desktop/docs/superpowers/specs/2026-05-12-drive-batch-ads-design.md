# Drive Batch Ads — Design Spec

## Goal

Allow the user to upload a public Google Drive folder link containing N images, configure multiple ad sets (conjuntos) with budget and creative count, auto-generate AI copies per image via Claude Vision, and publish to one or multiple Meta Ads clients in a single flow.

## Architecture

A new "Drive Batch" tab in the Anúncios module. 4-step wizard (Drive + Client → Campaign + Adsets → Generate Copies → Review + Publish). Backend: 5 new Flask endpoints + 1 new JS file (`drive-batch.js`). Google Drive API v3 via existing service account (`credenciais.json`). SSE stream for publish progress, same pattern as existing lote/multi-cliente.

## Tech Stack

- **Backend**: Flask, Google Drive API v3 (`google-api-python-client`), Claude Vision (`claude-sonnet-4-6`), Meta Ads Graph API v21.0
- **Frontend**: Vanilla JS ES5 IIFE (same pattern as `lote.js`, `multi-cliente.js`)
- **Auth**: Existing service account `credenciais.json` for Drive; existing per-client `token_key` for Meta

---

## Step 1 — Drive + Client Selection

### UI
- Text input: paste Google Drive public folder URL
- Button "Carregar" → calls `POST /api/anuncios/drive/listar`
- Shows file count + filename list (with thumbnails if available)
- Mode toggle: **Um cliente** (select dropdown from `ad_client_profiles`) or **Vários clientes** (checkbox list, same pattern as multi-cliente)
- Button "Proximo" → advances to Step 2

### Backend: `POST /api/anuncios/drive/listar`
- Input: `{ url: "<drive_folder_url>" }`
- Extract folder ID from URL (supports formats: `/folders/<id>`, `id=<id>`)
- Call Drive API v3: `files.list(q="'<folder_id>' in parents", fields="files(id,name,mimeType,thumbnailLink)")`
- Filter only image MIME types (`image/jpeg`, `image/png`, `image/webp`, `image/gif`)
- Returns: `{ files: [{id, name, thumbnailLink}], total: N }`
- Error if folder not accessible or no images found

---

## Step 2 — Campaign + Adset Configuration

### UI
**Single client:**
- Button "Buscar campanhas ativas" → calls `GET /api/anuncios/drive/campanhas?cliente_id=X`
- Shows campaign list (name + id) → user selects one
- Option "Criar nova campanha" with name input field

**Multi-client:**
- Radio: "Criar nova campanha para todos" (text input for campaign name) OR "Usar campanha salva de cada cliente" (uses `campanha_id_existente` from each client's profile)

**Adset configuration (all modes):**
- `num_conjuntos` — number of ad sets (integer, min 1)
- `orcamento_por_conjunto` — budget per adset in R$ (float)
- `criativos_por_conjunto` — creatives per adset (integer, min 1)
- Live validation: `num_conjuntos x criativos_por_conjunto` must equal total images from Step 1
- Error message if mismatch: "X conjuntos x Y criativos = Z, mas a pasta tem N imagens"

### Backend: `GET /api/anuncios/drive/campanhas?cliente_id=X`
- Fetches client profile from `ad_client_profiles`
- Calls Meta Graph API v21.0: `GET /<account_id>/campaigns?fields=id,name,status&filtering=[{field:effective_status,operator:IN,value:['ACTIVE','PAUSED']}]`
- Returns: `{ campanhas: [{id, name, status}] }`

---

## Step 3 — AI Copy Generation

### UI
- Button "Gerar Copies" → calls `POST /api/anuncios/drive/gerar-copies`
- Progress counter: "Gerando 1/30..." updated per image
- Results shown in an editable grid: each row has thumbnail + titulo field + texto field
- User can edit any copy before proceeding
- Button "Proximo" → advances to Step 4

### Backend: `POST /api/anuncios/drive/gerar-copies`
- Input: `{ files: [{id, name}], cliente_id, campanha_tipo }`
- For each file:
  1. Download image from Drive API (`files.get(fileId, alt=media)`)
  2. Save to `/tmp/<uuid><ext>` with 30-min cleanup timer
  3. Encode as base64
  4. Call Claude Vision (`claude-sonnet-4-6`) with image + prompt tailored to `campanha_tipo`
  5. Parse response → `{ titulo: "...", texto: "..." }`
- Returns: `{ copies: [{file_id, file_name, tmp_uuid, ext, titulo, texto}] }`
- Synchronous endpoint; frontend polls progress via response streaming (chunked JSON lines)

**Copy generation prompt per campanha_tipo:**
- `MESSAGES`: focus on WhatsApp CTA, conversational tone
- `PURCHASE`: focus on product/offer, price urgency
- `ENGAGEMENT`: focus on engagement, question/hook

---

## Step 4 — Review + Publish

### UI
- Summary card: `X cliente(s) x N conjuntos x M anuncios = total publicacoes`
- Adset breakdown: "Conjunto 1: imagens 1-10 | Conjunto 2: imagens 11-20..."
- Button "Publicar" → calls `POST /api/anuncios/drive/preparar` → then SSE `GET /api/anuncios/drive/stream/<token>`
- Progress list: one line per client/adset/ad with status icons (publicando / ok / erro)
- Button "Voltar" (goes back to Step 3)

### Backend: `POST /api/anuncios/drive/preparar`
- Input:
  ```json
  {
    "cliente_ids": [1, 2],
    "mode": "single or multi",
    "campanha": {
      "tipo": "nova or existente or salva",
      "id": "<campaign_id>",
      "nome": "Nome da campanha"
    },
    "conjuntos": {
      "num": 3,
      "orcamento": 10.00,
      "criativos_por": 10
    },
    "copies": [
      { "file_id": "...", "tmp_uuid": "...", "ext": ".jpg", "titulo": "...", "texto": "..." }
    ]
  }
  ```
- Validates: all clients exist in DB, all tmp files exist on disk, `conjuntos.num x conjuntos.criativos_por == len(copies)`
- Stores payload in `_lote_payloads[db_token]` with 30-min TTL timer
- Returns: `{ token: "<db_token>", resumo: { clientes, conjuntos, total_ads } }`

### Backend: `GET /api/anuncios/drive/stream/<db_token>`
- Pops payload from `_lote_payloads`
- For each client:
  1. Resolve campaign_id: use existing id, create new campaign, or use client's `campanha_id_existente`
  2. Distribute copies into adsets sequentially: adset 0 gets copies[0..M-1], adset 1 gets copies[M..2M-1], etc.
  3. For each adset:
     a. Create adset via Meta API with configured budget
     b. For each copy in adset:
        - Upload image to client's Meta account → get hash
        - Create ad creative with titulo + texto
        - Create ad
        - Log to `ad_publish_log` (audience_id=NULL)
  4. Rollback: if adset creation fails → delete newly created campaign (if any)
  5. SSE events: `publicando`, `ok`, `erro`, `concluido`
- Cleans up all tmp files at end

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `app.py` | Modify | 5 new endpoints under `/api/anuncios/drive/` |
| `templates/dashboard.html` | Modify | Add "Drive Batch" tab button + 4-step wizard HTML |
| `static/js/drive-batch.js` | Create | Wizard state machine, Drive listing, copy review grid, SSE publish |
| `static/js/anuncios.js` | Modify | Register 'drive' tab, call `dbInit()` on tab switch |
| `static/css/anuncios.css` | Modify | Styles for copy review grid, adset config section |

---

## Error Handling

- **Drive folder not public / not found**: show error in Step 1, user fixes URL
- **Image count mismatch**: show error in Step 2, user adjusts adset config
- **Copy generation failure (single image)**: show error inline in grid, user can manually fill the copy
- **Meta API failure during publish**: rollback newly created campaign/adsets, log error, continue with remaining clients
- **Tmp file missing at publish time**: abort that client with error message

---

## Key Constraints

- Max images: 100 (Drive API page size limit; pagination not in scope)
- Image formats: JPG, PNG, WebP, GIF only
- Copy generation is synchronous per image (~1-3s each); expect ~30-90s for 30 images; show per-image progress
- `ad_publish_log` entries: one row per ad created, `audience_id=NULL`
- Tmp files cleaned up after 30 min via `threading.Timer`
- All clients in multi-client mode share the same adset structure (num, budget, creatives per adset)

---

## Not In Scope

- Per-client adset configuration in multi-client mode
- Scheduling / delayed publish
- Video support
- Pagination beyond 100 images
