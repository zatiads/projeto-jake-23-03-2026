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

---

## Funcionalidades

### 1. Campanha Existente

**Toggle no topo do formulário do Lote:**
```
[ Nova campanha ]  [ Campanha existente ]
```

- **Nova campanha** (padrão): comportamento atual — campo de texto com nome da campanha
- **Campanha existente**: campo de texto some, aparece seletor que busca campanhas via Meta API

**Busca de campanhas:**
- Endpoint backend: `GET /api/anuncios/lote/campanhas?account_id=act_XXXXX`
- Chama `GET /{account_id}/campaigns?fields=id,name,status&limit=50` na Meta API v21.0
- Usa o token do cliente selecionado no formulário
- Retorna lista `[{id, name, status}]`
- O seletor só ativa depois que o cliente está selecionado — caso contrário exibe aviso "Selecione o cliente primeiro"

**Fluxo de publicação com campanha existente:**
- Backend recebe `campaign_id` existente no payload do lote
- Pula a etapa `criar_campanha()` e usa o ID recebido diretamente
- Cria adset novo na campanha existente + anúncio normalmente

**Campos do payload modificados:**
```json
{
  "modo_campanha": "nova" | "existente",
  "campanha_nome": "...",      // usado se modo=nova
  "campaign_id_existente": "..." // usado se modo=existente
}
```

---

### 2. Link do Google Drive como Criativo

**Toggle no campo de criativo:**
```
[ Upload de arquivo ]  [ Link do Drive ]
```

- **Upload** (padrão): comportamento atual
- **Link do Drive**: input de texto para colar URL

**Conversão da URL (backend):**
- Endpoint: `POST /api/anuncios/lote/drive-download`
- Extrai `FILE_ID` da URL (suporta formatos `/file/d/FILE_ID/view` e `/open?id=FILE_ID`)
- URL de download: `https://drive.google.com/uc?export=download&id=FILE_ID`
- Faz `requests.get()` com `stream=True`, segue redirecionamentos, timeout 30s
- Detecta tipo via `Content-Type` da resposta (`image/*` ou `video/mp4`)
- Salva em `/tmp/{uuid}{ext}` — retorna mesmo formato do upload-temp: `{tmp_uuid, ext, mime, ok}`
- Exibe preview da imagem após download bem-sucedido (se imagem)
- A partir daí o fluxo é idêntico ao upload normal

**Erros tratados:**
- Link inválido (não consegue extrair FILE_ID)
- Arquivo não público (resposta HTML de login/confirmação)
- Timeout
- Tipo não suportado

---

### 3. Fix Visual das Listas

**Problema:** `<select>` do módulo anúncios tem fundo branco e texto ilegível no tema dark.

**Fix em `anuncios.css`:** regra global para todos os `<select>` dentro de `#page-anuncios`:

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
}
#page-anuncios select:focus {
  outline: none;
  border-color: rgba(100,181,246,0.4);
}
#page-anuncios option {
  background: #1a1a2e;
  color: rgba(176,190,197,0.9);
}
```

Afeta: seletor de cliente, seletor de campanha existente, qualquer outro `<select>` no módulo.

---

## Arquivos Modificados

| Arquivo | Mudança |
|---|---|
| `jake_desktop/app.py` | 2 novos endpoints: `/api/anuncios/lote/campanhas` e `/api/anuncios/lote/drive-download`; modificar endpoint de publicação lote para aceitar `campaign_id_existente` |
| `jake_desktop/static/css/anuncios.css` | Fix visual dos `<select>` |
| `jake_desktop/static/js/lote.js` ou equivalente | Toggle nova/existente, toggle upload/drive, fetch campanhas, download drive |
| `jake_desktop/templates/dashboard.html` | Toggle UI no HTML do tab Lote |

---

## Fora do Escopo

- Reutilizar adset existente (só campanha)
- Drive autenticado (só links públicos)
- Suporte a múltiplos arquivos via Drive
- Mudanças em outros tabs (publicar, publicos, multi-cliente)
