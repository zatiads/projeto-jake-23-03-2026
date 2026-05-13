# Design: Públicos Salvos — Jake OS (Subir Anúncios)

**Data:** 2026-05-07
**Status:** Aprovado

---

## Contexto

A aba "Subir Anúncios" do Jake OS usa campos JSON crus para definir público-alvo (idade, gênero, localização). A solução é substituir isso por um sistema de públicos salvos — criados manualmente ou importados do Meta — que podem ser reutilizados em qualquer publicação.

---

## Banco de Dados

### Nova tabela `ad_audiences`

```sql
CREATE TABLE IF NOT EXISTS ad_audiences (
    id               SERIAL PRIMARY KEY,
    nome             VARCHAR(255) NOT NULL,
    account_id       VARCHAR(64)  NOT NULL,
    token_key        VARCHAR(64)  NOT NULL,
    tipo             VARCHAR(32)  NOT NULL CHECK (tipo IN ('manual', 'salvo_meta', 'custom_meta')),
    targeting_json   JSONB        NOT NULL DEFAULT '{}',
    meta_audience_id VARCHAR(64),
    criado_em        TIMESTAMP    DEFAULT NOW()
);

-- Índice parcial: unicidade só para linhas importadas do Meta
CREATE UNIQUE INDEX IF NOT EXISTS ad_audiences_meta_unique
    ON ad_audiences (account_id, meta_audience_id)
    WHERE meta_audience_id IS NOT NULL;
```

**`targeting_json` por tipo:**
- `manual`: `{age_min, age_max, genders: [1|2], countries: ["BR"]}` — cities e interests excluídos do form manual nesta fase
- `salvo_meta`: normalizado para `{age_min, age_max, genders, countries, cities}` extraindo apenas esses campos de `geo_locations` e da raiz do objeto `targeting` retornado pela Meta. Campos não mapeados (exclusions, flexible_spec, etc.) são descartados nesta fase.
- `custom_meta`: `{custom_audience_id: "<id>"}` — referencia o público por ID, sem parâmetros de segmentação

### Migração em `ad_client_profiles` / `ad_publish_log`

`publico_json` em `ad_client_profiles` é **mantido como fallback**. Não é removido.

```sql
ALTER TABLE ad_publish_log ADD COLUMN IF NOT EXISTS audience_id INTEGER;
```

### Sistema single-tenant

Jake OS tem um único usuário admin. Não há risco de IDOR entre sessões de usuários diferentes.

---

## Backend

### Todas as rotas protegidas por `@login_required`

### Novas funções em `meta/meta_api.py`

- `listar_publicos_salvos(token, account_id)` — `GET /{account_id}/saved_audiences?fields=id,name,targeting&limit=50`
- `listar_custom_audiences(token, account_id)` — `GET /{account_id}/customaudiences?fields=id,name,subtype&limit=50`

**Limitação aceita:** paginação não implementada. Máximo 50 resultados por tipo por conta.

### Novas rotas em `jake_desktop/app.py`

Todas retornam `{"error": "..."}` em caso de falha, `{"ok": true, ...dados}` em sucesso.

| Método | Rota | Request body | Response |
|--------|------|-------------|----------|
| GET | `/api/anuncios/audiences?account_id=` | — | `{audiences: [...]}` |
| POST | `/api/anuncios/audiences` | `{nome, account_id, token_key, tipo, targeting_json}` | `{ok: true, id: N}` |
| PUT | `/api/anuncios/audiences/<id>` | `{nome?, targeting_json?}` — `tipo` e `meta_audience_id` imutáveis | `{ok: true}` |
| DELETE | `/api/anuncios/audiences/<id>` | — | `{ok: true}` |
| POST | `/api/anuncios/audiences/importar` | `{account_id, token_key}` | `{ok: true, importados: N, atualizados: M, erros: [...]}` |

**GET sem `account_id`:** retorna todos os públicos de todas as contas.

**PUT:** `tipo` e `meta_audience_id` não podem ser alterados após criação. `custom_meta` aceita PUT apenas no campo `nome`.

### `POST /api/anuncios/audiences/importar` — detalhes

- `token_key` vem do body; na UI é lido automaticamente do perfil do cliente selecionado (`ad_client_profiles.token_key`)
- Busca saved audiences + custom audiences via Meta API
- Upsert por `(account_id, meta_audience_id)`: atualiza se existe, insere se não existe
- Falha parcial: registros já inseridos permanecem; erros por registro acumulados em `erros[]`

### Mudança em `/api/anuncios/publicar`

Aceita `audience_id` (opcional, integer). Lógica:
1. Se `audience_id` fornecido: busca `targeting_json` de `ad_audiences`, monta targeting conforme tipo
2. Se não fornecido: usa `publico_json` do cliente (fallback atual)
3. Registra `audience_id` em `ad_publish_log` (null se fallback)

**Montagem do targeting por tipo:**
- `manual` / `salvo_meta`: `geo_locations.countries`, `age_min`, `age_max`, `genders`
- `custom_meta`: `custom_audiences: [{id: custom_audience_id}]`

---

## Frontend

### Sub-navegação dentro da aba "Subir Anúncios"

Três tabs internas: **Clientes** | **Públicos** | **Publicar**

### Tela "Públicos"

- Lista: nome, tipo (badge: Manual / Meta Salvo / Custom), conta
- **"Importar do Meta"**: modal seleciona cliente → lê `account_id` e `token_key` do perfil → chama `/importar`
- **"Novo Público"**: form com nome, cliente (dropdown), idade min/max, gênero, país
- Editar: disponível para `manual` e `salvo_meta`. Desabilitado para `custom_meta` (apenas nome editável via PUT)
- Deletar: disponível para todos os tipos

### Tela "Publicar" (alteração)

- Campo de público vira dropdown **"Selecionar Público"** filtrado pelo `account_id` do cliente ativo
- Opção padrão: "Usar perfil do cliente" (fallback para `publico_json`)
- Se nenhum público salvo para o cliente: apenas a opção de fallback aparece

---

## O que NÃO está no escopo desta fase

- Interesses e cidades via targeting search API
- Sync Jake → Meta (públicos criados no Jake não viram saved audiences no Meta)
- Paginação além de 50 resultados por importação
- Remoção de `publico_json` de `ad_client_profiles`
