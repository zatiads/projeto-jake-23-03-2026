# Jake OS — Builder de Anúncios em Lote: Design Spec

**Data:** 2026-05-08
**Status:** Aprovado pelo usuário

---

## Objetivo

Substituir o fluxo de publicação unitária por um builder de lote visual em 3 colunas que permite criar até 1 campanha × 10 conjuntos × 10 criativos (máx 100 anúncios) numa única sessão, com geração de copy via Jake e importação de criativo por URL.

---

## Contexto

O módulo Anúncios do Jake OS já suporta:
- Publicação unitária (1 campanha → 1 conjunto → 1 anúncio) via `POST /api/anuncios/publicar`
- Perfis de clientes com token, account_id, page_id, localizacao_json, publico_json, optimization_goal, pixel_id, link_url
- Públicos salvos (manual, importado do Meta) na tabela `ad_audiences` com campos: id, nome, account_id, token_key, tipo, targeting_json, meta_audience_id
- Tipos de campanha: MESSAGES (CBO, budget na campanha), ENGAGEMENT e PURCHASE (budget no adset)
- Upload de imagem/vídeo para biblioteca Meta via `POST /api/anuncios/upload-criativo`
- Tabela `ad_publish_log` com colunas: id, cliente_id, account_id, campaign_id, adset_id, ad_id, status, audience_id, payload_json, criado_em

O builder de lote é uma nova aba "Lote" no módulo Anúncios, paralela às abas "Publicar" e "Públicos Salvos".

---

## Arquitetura

### Frontend

**Nova aba "Lote"** em `dashboard.html` dentro do módulo Anúncios.

Layout: sidebar de clientes (existente) + área principal com 3 colunas:

```
| Conjuntos (col 1) | Criativos (col 2) | Copy (col 3) |
```

- **Col 1 — Conjuntos:** cards verticais com nome editável, seletor de público (herda do perfil ou escolhe público salvo). Botão "+ Conjunto". Máx 10.
- **Col 2 — Criativos:** aparece ao clicar num conjunto. Slots com tipo selecionável (imagem/vídeo/URL/carrossel) e preview inline após upload. Máx 10 por conjunto.
- **Col 3 — Copy:** aparece ao clicar num criativo. Campos título + texto pré-preenchidos pelo Jake, editáveis individualmente. Publicação bloqueada se qualquer copy estiver vazia.

**Topo fixo:**
- Nome da campanha (texto)
- Tipo de campanha (dropdown, herdado do perfil, editável)
- Orçamento diário total em R$
- Contador: `N conjuntos × M criativos = X anúncios`

**Rodapé fixo:**
- Botão "Gerar todas as copies" → chama `/api/anuncios/copy-lote`, preenche todos os slots
- Botão "Publicar Lote" → dispara fluxo de 2 etapas: POST payload → GET SSE stream

### Backend

**Novos endpoints:**

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/anuncios/publicar-lote` | Salva payload em memória, retorna `{lote_token: uuid}` |
| `GET`  | `/api/anuncios/publicar-lote/stream/<lote_token>` | SSE stream da publicação real |
| `POST` | `/api/anuncios/preview-url` | Download de URL externa, retorna preview + tipo detectado |
| `GET`  | `/api/anuncios/tmp-preview/<uuid>` | Serve arquivo temporário para preview inline |
| `POST` | `/api/anuncios/copy-lote` | Gera N copies via Claude para o lote |

**Endpoints existentes modificados:**
- `POST /api/anuncios/upload-criativo` — aceita novo campo `tmp_uuid` além de `file`

**Endpoints existentes reutilizados sem modificação:**
- `GET /api/anuncios/audiences` — popula o seletor de público em cada conjunto

### Armazenamento temporário de payloads

Flask session é cookie-based (limite 4KB). Para evitar o limite, usar um dict em memória no módulo `app.py`:

```python
_lote_payloads: dict = {}  # lote_token → payload dict
```

O `POST /api/anuncios/publicar-lote` armazena em `_lote_payloads[lote_token] = payload` e o `GET stream/<lote_token>` lê e apaga do dict após processar. Este dict é em memória — não persiste entre restarts do processo, o que é aceitável (lotes em progresso são descartados se o server reiniciar).

### Banco de dados

Adicionar `lote_id` na tabela `ad_publish_log` existente:

```sql
ALTER TABLE ad_publish_log ADD COLUMN IF NOT EXISTS lote_id VARCHAR(36);
```

---

## Fluxo de Uso

1. Usuário seleciona cliente na sidebar
2. Clica na aba "Lote"
3. Define nome da campanha, tipo e orçamento total no topo
4. Clica "+ Conjunto" N vezes (até 10), define nome e público de cada um
5. Para cada conjunto, clica nos slots de criativo:
   - Escolhe tipo (imagem/vídeo/URL/carrossel)
   - Faz upload ou cola URL → preview aparece
6. Clica "Gerar todas as copies" → Jake preenche título + texto pra cada criativo
7. Edita copies individualmente se necessário
8. Clica "Publicar Lote" (bloqueado se qualquer copy estiver vazia)
9. Modal de progresso em tempo real via SSE: `Conjunto 2/3 — Anúncio 1/4 ✓ ✓ ✗`
10. Resumo final: X criados, Y com erro + detalhes

---

## Detalhamento dos Tipos de Criativo

### Imagem
- Upload via `<input type="file">`, enviado para `/api/anuncios/upload-criativo`
- Retorna `{tipo: "imagem", hash: "abc123"}`
- Preview: `<img>` inline no slot

### Vídeo
- Upload via `<input type="file">`, enviado para `/api/anuncios/upload-criativo`
- Retorna `{tipo: "video", video_id: "123456"}`
- Preview: `<video>` inline no slot

### URL
- Campo de texto + botão "Pré-visualizar"
- Backend (`POST /api/anuncios/preview-url`):
  - Faz GET da URL com timeout=30s e max_size=50MB (rejeita se Content-Length > 50MB ou stream exceder 50MB)
  - Detecta tipo via Content-Type: `image/*` → imagem, `video/*` → vídeo. Outros → retorna 400 "Formato não suportado"
  - Salva em `/tmp/<uuid>.<ext>` e retorna `{tmp_uuid: "<uuid>", tipo: "imagem"|"video"}`
  - Arquivo temporário é apagado 30 minutos após criação via `threading.Timer(1800, os.remove, [path])`
- Frontend recebe `tmp_uuid` e exibe preview em `/api/anuncios/tmp-preview/<uuid>`
- Usuário confirma → frontend envia `{tmp_uuid: "<uuid>"}` para `/api/anuncios/upload-criativo`
- Backend em `upload-criativo` detecta campo `tmp_uuid`: faz glob `/tmp/<uuid>.*` para encontrar o arquivo (mesma estratégia de `tmp-preview`), lê, faz upload para Meta, apaga o arquivo temp

**Rota de preview (`GET /api/anuncios/tmp-preview/<uuid>`):**
- Busca o arquivo em `/tmp/` via `glob.glob(f"/tmp/{uuid}.*")` — pega o primeiro resultado
- Serve com `send_file(path)` (Flask infere Content-Type pela extensão)
- Retorna 404 se `glob` não encontrar nada (expirado ou nunca criado)

### Carrossel
- Abre sub-slots (mín 2, máx 10 imagens)
- Upload individual por card via `/api/anuncios/upload-criativo`
- Retorna `{tipo: "carrossel", cards: [{hash: "abc"}, {hash: "def"}, ...]}`
- Preview: miniaturas horizontais

**Payload Meta API para carrossel** (implementar em `criar_anuncio` como novo branch `elif`, após o branch de vídeo):
```python
elif creative_ref["tipo"] == "carrossel":
    child_attachments = [
        {
            "link": link_url,
            "image_hash": card["hash"],
            "call_to_action": {"type": cta, "value": {"link": link_url}}
        }
        for card in creative_ref["cards"]
    ]
    link_data = {
        "link": link_url,
        "child_attachments": child_attachments,   # lista Python, NÃO json.dumps()
        "multi_share_optimized": True,
        # Sem "call_to_action" no top-level de link_data para carrossel —
        # cada child_attachment já define o seu próprio CTA
    }
    story_spec = {"page_id": page_id, "link_data": link_data}
    # story_spec inteiro é serializado via _json_meta.dumps() na chamada de criação do creative
```

---

## Copy via Jake

**Endpoint:** `POST /api/anuncios/copy-lote`

**Payload:**
```json
{
  "cliente_id": 1,
  "campanha_tipo": "PURCHASE",
  "criativos": [
    {"indice": "1-1", "tipo": "imagem", "descricao": "Foto produto X"},
    {"indice": "1-2", "tipo": "video",  "descricao": "Vídeo depoimento Y"}
  ]
}
```

**Comportamento:** Uma única chamada ao `claude-sonnet-4-6`. O prompt solicita N copies distintas em JSON com chaves `indice`, `titulo` (máx 40 chars), `texto` (máx 125 chars). Retorna array `[{indice, titulo, texto}]`. Frontend preenche os campos correspondentes.

**Regra de bloqueio:** O botão "Publicar Lote" fica desabilitado enquanto qualquer campo de título ou texto estiver vazio. Tooltip: "Preencha todas as copies antes de publicar."

---

## Publicação em Lote via SSE

**Arquitetura de 2 etapas** (necessária porque `EventSource` do browser só aceita GET):

**Etapa 1 — `POST /api/anuncios/publicar-lote`:**
- Recebe o payload JSON completo
- Valida campos obrigatórios (cliente_id, conjuntos não vazios, copies preenchidas)
- Gera `lote_token = str(uuid.uuid4())`
- Armazena em `_lote_payloads[lote_token] = payload`
- **`lote_id` e `lote_token` são o mesmo valor:** retorna `{lote_token: lote_token}`. O frontend usa `lote_token` tanto para abrir o SSE stream quanto como `lote_id` para logging no banco.

**Etapa 2 — `GET /api/anuncios/publicar-lote/stream/<lote_token>`:**
- Lê `payload = _lote_payloads.pop(lote_token, None)` — remove do dict ao ler (evita re-execução em reconexão)
- Se não encontrar: retorna SSE com `{tipo: "erro_fatal", erro: "Lote não encontrado ou já processado"}` e encerra
- Retorna `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`
- Processa sequencialmente e emite eventos SSE. Ao fim, emite `{tipo: "fim"}` e encerra o generator
- **Reconexão:** como o payload é consumido com `pop`, uma reconexão automática do browser receberá `erro_fatal` e não re-criará a campanha. O frontend deve fechar o `EventSource` ao receber `fim` chamando `es.close()`.

**Formato dos eventos SSE** (cada evento é `data: <json>\n\n`):
```
data: {"tipo": "campanha_ok", "campaign_id": "123"}

data: {"tipo": "conjunto_ok", "conjunto_idx": 0, "adset_id": "456"}

data: {"tipo": "conjunto_erro", "conjunto_idx": 1, "erro": "Mensagem do erro"}

data: {"tipo": "anuncio_ok", "conjunto_idx": 0, "criativo_idx": 1, "ad_id": "789"}

data: {"tipo": "anuncio_erro", "conjunto_idx": 0, "criativo_idx": 2, "erro": "Invalid parameter"}

data: {"tipo": "erro_fatal", "erro": "Mensagem do erro fatal"}

data: {"tipo": "fim", "total": 10, "sucesso": 9, "falha": 1}
```

**Lógica do stream:**

1. **Criar campanha:** `criar_campanha(token, account_id, campanha_tipo, campanha_nome, orcamento_total, cbo=cbo)` onde `cbo = campanha_tipo not in ("ENGAGEMENT", "PURCHASE")`. Se falhar → emite `erro_fatal` e encerra.

2. **Para cada conjunto:**
   - **Lookup do público:** se `audience_id` fornecido, busca `targeting_json` na tabela `ad_audiences`. A localização sempre vem de `cliente["localizacao_json"]`. Se `audience_id` for null, usa `cliente["publico_json"]` como publico.
   - **Orçamento:** ENGAGEMENT/PURCHASE → `orcamento_total / N_conjuntos`. MESSAGES → `None`.
   - `criar_conjunto(..., nome=nome_conjunto, orcamento=orcamento_conjunto, optimization_goal=..., pixel_id=...)`
   - Se falhar → emite `conjunto_erro`, pula criativos deste conjunto, continua.

3. **Para cada criativo:**
   - `link_url = cliente["link_url"] or ""`
   - `criar_anuncio(..., link_url=link_url)`
   - Se falhar → emite `anuncio_erro`, continua próximo.
   - Se OK → registra em `ad_publish_log` com `lote_id = lote_token`.

4. Emite `fim` com contadores de sucesso e falha.

---

## Modificações em `criar_conjunto`

Adicionar parâmetro `nome: str = None`. Substituir:
```python
"name": f"Conjunto - {campanha_tipo}",
```
por:
```python
"name": nome or f"Conjunto - {campanha_tipo}",
```

---

## Tratamento de Erros

| Situação | Comportamento |
|----------|---------------|
| Slot de criativo sem upload | Botão Publicar bloqueado + highlight vermelho no slot |
| Copy vazia em qualquer slot | Botão Publicar bloqueado + tooltip explicativo |
| Erro na criação da campanha | Emite `erro_fatal`, encerra stream |
| Erro na criação de conjunto | Emite `conjunto_erro`, pula criativos daquele conjunto, continua |
| Erro em anúncio individual | Emite `anuncio_erro`, continua próximo criativo |
| Reconexão SSE após `fim` | `pop` retorna None → emite `erro_fatal` "Lote já processado", frontend ignora |
| URL inválida/inacessível | 400 `{error: "Não foi possível acessar a URL"}` |
| Content-Type não suportado | 400 `{error: "Formato não suportado. Use imagem ou vídeo."}` |
| Arquivo temp expirado em tmp-preview | 404 |

---

## Arquivos Afetados

| Arquivo | Tipo | O que muda |
|---------|------|-----------|
| `jake_desktop/templates/dashboard.html` | Modifica | Nova aba "Lote" + layout 3 colunas + modal de progresso SSE |
| `jake_desktop/static/js/lote.js` | Cria | Toda lógica do builder de lote (estado, eventos, SSE, publicação) |
| `jake_desktop/app.py` | Modifica | Dict `_lote_payloads`; 5 novos endpoints; `upload-criativo` aceita `tmp_uuid` |
| `meta/meta_api.py` | Modifica | (1) `criar_conjunto` aceita `nome`; (2) `criar_anuncio` suporta carrossel |
| `ad_publish_log` | Schema | `ADD COLUMN IF NOT EXISTS lote_id VARCHAR(36)` |

O JS do lote fica em `lote.js` separado para manter os arquivos focados.

---

## Fora de Escopo

- Agendamento de publicação (horário futuro)
- Duplicação de lotes salvos
- Relatório de performance dos anúncios do lote
- Edição de lotes já publicados
- Reutilização de campanha existente no lote (sempre cria uma nova)
- Suporte a URLs do Google Drive/Dropbox (apenas URLs diretas com Content-Type correto)
