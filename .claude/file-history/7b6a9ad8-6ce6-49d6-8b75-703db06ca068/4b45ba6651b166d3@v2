# Design: Aba "Subir Anúncios" — Jake OS

**Data:** 2026-03-20
**Status:** Aprovado pelo usuário
**Contexto:** Jake OS (`/root/jake_desktop`) — Flask SPA, porta 5050

---

## Problema

Bruno gerencia ~30 clientes em duas agências (Piloti, Dentto) e freelancers. Hoje sobe anúncios manualmente no Gerenciador da Meta, o que consome tempo — principalmente na criação de copy e no processo de configuração repetitivo por cliente. O maior risco é erro humano em localização e público, que pode queimar verba do cliente.

---

## Solução

Aba "Subir Anúncios" com perfis por cliente (template salvo no banco), geração de copy via IA a partir do criativo, e publicação na Meta API mediante aprovação explícita do Patrão.

---

## Organização dos Clientes

Sidebar esquerda com clientes agrupados em 3 categorias:

```
📁 Piloti
   └ Cliente A
📁 Dentto
   └ Cliente B
📁 Freelance
   └ Cliente C
```

Cada cliente tem um **perfil salvo no PostgreSQL (Neon)** com os campos:

| Campo | Tipo | Descrição |
|---|---|---|
| `nome` | string | Nome do cliente |
| `agencia` | enum | `piloti` / `dentto` / `freelance` |
| `account_id` | string | `act_XXXXXXXXX` da conta Meta |
| `token_key` | string | Nome da env var do token (whitelist: `META_TOKEN_PILOTI`, `META_TOKEN_DENTTO`) |
| `whatsapp` | string | Número vinculado para campanhas de mensagem |
| `campanha_tipo` | enum | `MESSAGES` / `ENGAGEMENT` |
| `localizacao_json` | json | Cidades, raio em km, país |
| `publico_json` | json | Faixa etária, gênero, interesses |
| `orcamento_diario` | float | Orçamento padrão em R$ |
| `campanha_id_existente` | string | ID de campanha recorrente (opcional) |

---

## Fluxo de Criação de Anúncio

Ao selecionar um cliente na sidebar, a tela direita exibe 4 blocos verticais — mais um painel de gerenciamento de perfis.

### Gerenciamento de Perfis de Clientes

Na sidebar, cada agência tem um botão **"+ Novo cliente"**. Ao clicar, abre um formulário inline (ou modal) com todos os campos do perfil. Clientes existentes têm ícone de edição. O formulário tem validação: `account_id` e `localizacao_json` são obrigatórios para salvar. Tempo estimado de cadastro: < 3 minutos.

### Bloco 1 — Campanha
- Toggle: **Nova campanha** / **Usar existente**
- Se nova: campos de objetivo (pré-selecionado do perfil), nome e orçamento diário
- Se existente: dropdown com campanhas ativas da conta (buscadas via Meta API)
- **Orçamento:** Para `MESSAGES`, o orçamento é definido ao nível da campanha (CBO — Campaign Budget Optimization). Para `ENGAGEMENT`, é definido ao nível do conjunto de anúncios (ad set budget). O backend determina automaticamente o nível correto com base no `campanha_tipo` do perfil.

### Bloco 2 — Criativo
- Upload por drag & drop (imagem JPG/PNG ou vídeo MP4)
- Preview ao fazer upload
- **Imagem:** upload via `/act_xxx/adimages` — retorna `hash` imediato
- **Vídeo:** upload via `/act_xxx/advideos` — processo assíncrono; backend faz polling até `status = ready` (máx 60s com feedback de progresso no frontend)
- Ao confirmar: dispara análise automática para geração de copy

### Bloco 3 — Copy (IA)
- Jake analisa o criativo + tipo de cliente e gera automaticamente:
  - **Título** (até 40 caracteres)
  - **Texto principal** (até 125 caracteres — padrão Meta)
  - **CTA** (opções: `SEND_MESSAGE`, `LEARN_MORE`, `SIGN_UP`)
- **Como funciona:** a imagem é enviada como base64 (ou URL temporária do upload) junto com metadados do cliente (nome, tipo de campanha, segmento) para o Claude `claude-sonnet-4-6` via multimodal prompt
- Para vídeo: envia o thumbnail/frame extraído do vídeo como imagem
- Tudo editável em campos de texto
- Botão "Regerar" para nova versão da IA

### Bloco 4 — Revisão Final
- Resumo completo: conta Meta, localização, público, orçamento, criativo (thumbnail), copy
- Validação visual: cada campo com indicador ✓ / ⚠ / ✕
- **Localização vazia = bloqueio hard** — botão de publicar desabilitado e mensagem de erro visível
- Botão **"Publicar"** → abre modal de confirmação com preview final
- Publicação só ocorre após confirmação no modal

---

## Arquitetura Backend

### Versão da Meta API
Todas as novas funções usam **v21.0**. O `GRAPH_URL` existente em `meta_api.py` (`v20.0`) deve ser atualizado para `v21.0` como parte desta implementação.

### Stub existente em `meta_api.py`
A função `criar_campanha(nome, conta_id, objetivo, orcamento_diario, **kwargs)` existe como stub que retorna `(False, "em construção")`. Esta implementação deve ser **substituída** pela nova assinatura especificada abaixo. Não manter compatibilidade com o stub.

### Token resolution
O `token_key` salvo no perfil do cliente é o nome de uma variável de ambiente. O backend resolve via `os.getenv(token_key)`. Para segurança, apenas valores presentes na seguinte whitelist são aceitos:

```python
VALID_TOKEN_KEYS = {"META_TOKEN_PILOTI", "META_TOKEN_DENTTO", "META_ACCESS_TOKEN"}
```

Qualquer `token_key` fora da whitelist retorna erro 400 antes de qualquer chamada à Meta.

### Novas rotas Flask (`app.py`)

| Rota | Método | Função |
|---|---|---|
| `/api/anuncios/clientes` | GET | Lista perfis de clientes |
| `/api/anuncios/clientes` | POST | Cria novo perfil |
| `/api/anuncios/clientes/<id>` | PUT | Atualiza perfil existente |
| `/api/anuncios/clientes/<id>` | DELETE | Remove perfil |
| `/api/anuncios/campanhas/<account_id>` | GET | Lista campanhas ativas na conta Meta |
| `/api/anuncios/copy` | POST | Gera copy via Claude a partir do criativo |
| `/api/anuncios/upload-criativo` | POST | Faz upload do arquivo para a Meta |
| `/api/anuncios/publicar` | POST | Cria campanha + conjunto + anúncio na Meta |

#### Schema: `POST /api/anuncios/copy`
```json
{
  "imagem_base64": "...",
  "mime_type": "image/jpeg",
  "cliente_nome": "Clínica X",
  "campanha_tipo": "MESSAGES",
  "segmento": "odontologia"
}
```
Retorna: `{ "titulo": "...", "texto": "...", "cta": "SEND_MESSAGE" }`

#### Schema: `POST /api/anuncios/publicar`
```json
{
  "cliente_id": 1,
  "campanha_existente_id": null,
  "campanha_nome": "Campanha Março",
  "orcamento_diario": 30.00,
  "creative_ref": { "tipo": "imagem", "hash": "abc123" },
  "copy": { "titulo": "...", "texto": "...", "cta": "SEND_MESSAGE" }
}
```

### Novas funções em `meta/meta_api.py`

```python
def upload_imagem(token, account_id, imagem_bytes, filename) -> dict:
    """Upload via /adimages. Retorna {'hash': '...'}."""

def upload_video(token, account_id, video_bytes, filename) -> str:
    """Upload via /advideos. Faz polling até status=ready. Retorna video_id."""

def listar_campanhas(token, account_id) -> list:
    """Lista campanhas ativas da conta."""

def criar_campanha(token, account_id, objetivo, nome, orcamento, cbo=True) -> str:
    """Cria campanha. Para MESSAGES usa CBO (cbo=True). Retorna campaign_id."""

def criar_conjunto(token, campaign_id, campanha_tipo, publico, localizacao, orcamento=None) -> str:
    """Cria ad set. orcamento só aplicado se cbo=False (ENGAGEMENT). Retorna adset_id."""

def criar_anuncio(token, adset_id, creative_id, copy, titulo, cta) -> str:
    """Cria anúncio. Retorna ad_id."""
```

### Estratégia de rollback em falhas parciais
`/api/anuncios/publicar` executa 3 operações sequenciais na Meta API. Em caso de falha:

- **Falha no passo 1 (campanha):** Nenhum rollback necessário — nada foi criado
- **Falha no passo 2 (conjunto):** Backend chama `DELETE /{campaign_id}` para limpar a campanha criada
- **Falha no passo 3 (anúncio):** Backend chama `DELETE /{adset_id}` e `DELETE /{campaign_id}` para limpar

Em todos os casos de falha, o erro é retornado ao frontend com mensagem clara e nada é registrado no `ad_publish_log` como sucesso.

---

## Schema do Banco (PostgreSQL / Neon)

### Tabela: `ad_client_profiles`

```sql
CREATE TABLE ad_client_profiles (
    id                    SERIAL PRIMARY KEY,
    nome                  VARCHAR(100) NOT NULL,
    agencia               VARCHAR(20)  NOT NULL CHECK (agencia IN ('piloti','dentto','freelance')),
    account_id            VARCHAR(50)  NOT NULL,
    token_key             VARCHAR(50)  NOT NULL,
    whatsapp              VARCHAR(20),
    campanha_tipo         VARCHAR(20)  NOT NULL DEFAULT 'MESSAGES'
                              CHECK (campanha_tipo IN ('MESSAGES','ENGAGEMENT')),
    localizacao_json      JSONB        NOT NULL,
    publico_json          JSONB,
    orcamento_diario      NUMERIC(10,2),
    campanha_id_existente VARCHAR(50),
    criado_em             TIMESTAMP    DEFAULT NOW(),
    atualizado_em         TIMESTAMP    DEFAULT NOW()
);
```

### Tabela: `ad_publish_log`

```sql
CREATE TABLE ad_publish_log (
    id           SERIAL PRIMARY KEY,
    cliente_id   INTEGER REFERENCES ad_client_profiles(id),
    account_id   VARCHAR(50)  NOT NULL,
    campaign_id  VARCHAR(50),
    adset_id     VARCHAR(50),
    ad_id        VARCHAR(50),
    status       VARCHAR(20)  NOT NULL CHECK (status IN ('sucesso','erro')),
    erro_msg     TEXT,
    payload_json JSONB,
    criado_em    TIMESTAMP    DEFAULT NOW()
);
```

---

## Arquitetura Frontend

**Novo arquivo:** `static/js/anuncios.js` — IIFE pattern (igual aos outros módulos)

**Responsabilidades:**
- Carregar e renderizar lista de clientes agrupados por agência
- Formulário inline de criação/edição de perfil de cliente
- Gerenciar seleção de cliente e carregamento do perfil nos blocos
- Upload de criativo com preview (com barra de progresso para vídeo)
- Disparo e exibição da copy gerada pela IA
- Validação dos campos antes de habilitar publicação (localização = hard block)
- Modal de confirmação antes de publicar
- Feedback visual de progresso durante publicação
- Exibição do resultado: link do anúncio criado ou mensagem de erro com detalhes

**Seção HTML:** `page-anuncios` já existe em `dashboard.html` como placeholder — substituir pelo layout real.

---

## Segurança e Controle

- Publicação sempre requer confirmação explícita no modal — nunca dispara automático
- Localização vazia bloqueia o botão de publicar (hard block, validado também no backend)
- Token da agência nunca exposto no frontend — `token_key` é resolvido no backend via whitelist
- Logs de cada tentativa de publicação (sucesso ou erro) salvos em `ad_publish_log`

---

## Fora do Escopo (v1)

- Edição de anúncios existentes
- Pausar / arquivar campanhas
- Relatórios de performance dentro desta aba (já existe na aba Relatórios)
- A/B testing automático
- Agendamento de publicação futura
- Suporte a anúncios de catálogo (DPA)

---

## Critérios de Sucesso

1. Cadastrar perfil de um cliente leva menos de 3 minutos
2. Da segunda vez em diante, subir um anúncio completo leva menos de 2 minutos
3. Zero possibilidade de publicar sem localização definida (validação frontend + backend)
4. Copy gerada pela IA é aproveitável direto (sem edição) em pelo menos 60% dos casos
5. Falhas parciais na Meta API nunca deixam campanhas/conjuntos órfãos na conta do cliente
