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
| `token_key` | string | Nome da env var do token (`META_TOKEN_PILOTI`, etc.) |
| `whatsapp` | string | Número vinculado para campanhas de mensagem |
| `campanha_tipo` | enum | `MESSAGES` / `ENGAGEMENT` |
| `localizacao_json` | json | Cidades, raio em km, país |
| `publico_json` | json | Faixa etária, gênero, interesses |
| `orcamento_diario` | float | Orçamento padrão em R$ |
| `campanha_id_existente` | string | ID de campanha recorrente (opcional) |

---

## Fluxo de Criação de Anúncio

Ao selecionar um cliente na sidebar, a tela direita exibe 4 blocos verticais:

### Bloco 1 — Campanha
- Toggle: **Nova campanha** / **Usar existente**
- Se nova: campos de objetivo (pré-selecionado do perfil), nome e orçamento diário
- Se existente: dropdown com campanhas ativas da conta (buscadas via Meta API)

### Bloco 2 — Criativo
- Upload por drag & drop (imagem JPG/PNG ou vídeo MP4)
- Preview ao fazer upload
- Ao confirmar: dispara análise automática para geração de copy

### Bloco 3 — Copy (IA)
- Jake analisa o criativo + tipo de cliente e gera automaticamente:
  - **Título** (até 40 caracteres)
  - **Texto principal** (até 125 caracteres — padrão Meta)
  - **CTA** (opções: `SEND_MESSAGE`, `LEARN_MORE`, `SIGN_UP`)
- Tudo editável em campos de texto
- Botão "Regerar" para nova versão da IA
- Modelo: `claude-sonnet-4-6`

### Bloco 4 — Revisão Final
- Resumo completo: conta Meta, localização, público, orçamento, criativo (thumbnail), copy
- Validação visual: cada campo com indicador ✓ / ⚠ / ✕
- Campos obrigatórios vazios bloqueiam o botão de publicar
- Localização vazia = bloqueio hard (sem exceção)
- Botão **"Publicar"** → abre modal de confirmação com preview final
- Publicação só ocorre após confirmação no modal

---

## Arquitetura Backend

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

### Novas funções em `meta/meta_api.py`

```python
def upload_criativo(token, account_id, arquivo) -> str:
    """Upload de imagem/vídeo para a Meta. Retorna creative_id."""

def listar_campanhas(token, account_id) -> list:
    """Lista campanhas ativas da conta."""

def criar_campanha(token, account_id, objetivo, nome, orcamento) -> str:
    """Cria campanha. Retorna campaign_id."""

def criar_conjunto(token, campaign_id, publico, localizacao, orcamento) -> str:
    """Cria ad set. Retorna adset_id."""

def criar_anuncio(token, adset_id, creative_id, copy, titulo, cta) -> str:
    """Cria anúncio. Retorna ad_id."""
```

### Nova tabela PostgreSQL

```sql
CREATE TABLE ad_client_profiles (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(100) NOT NULL,
    agencia         VARCHAR(20) NOT NULL CHECK (agencia IN ('piloti','dentto','freelance')),
    account_id      VARCHAR(50) NOT NULL,
    token_key       VARCHAR(50) NOT NULL,
    whatsapp        VARCHAR(20),
    campanha_tipo   VARCHAR(20) DEFAULT 'MESSAGES',
    localizacao_json JSONB,
    publico_json    JSONB,
    orcamento_diario NUMERIC(10,2),
    campanha_id_existente VARCHAR(50),
    criado_em       TIMESTAMP DEFAULT NOW(),
    atualizado_em   TIMESTAMP DEFAULT NOW()
);
```

---

## Arquitetura Frontend

**Novo arquivo:** `static/js/anuncios.js` — IIFE pattern (igual aos outros módulos)

**Responsabilidades:**
- Carregar e renderizar lista de clientes agrupados por agência
- Gerenciar seleção de cliente e carregamento do perfil
- Upload de criativo com preview
- Disparo e exibição da copy gerada pela IA
- Validação dos campos antes de habilitar publicação
- Modal de confirmação antes de publicar
- Feedback visual de progresso durante publicação

**Seção HTML:** `page-anuncios` já existe em `dashboard.html` como placeholder — substituir pelo layout real.

---

## Segurança e Controle

- Publicação sempre requer confirmação explícita no modal — nunca dispara automático
- Localização vazia bloqueia o botão de publicar (hard block)
- Token da agência nunca exposto no frontend — sempre referenciado pelo `token_key` e resolvido no backend
- Logs de cada publicação (cliente, account_id, ad_id, timestamp) salvos na tabela `ad_publish_log`

---

## Fora do Escopo (v1)

- Edição de anúncios existentes
- Pausar / arquivar campanhas
- Relatórios de performance dentro desta aba (já existe na aba Relatórios)
- A/B testing automático
- Agendamento de publicação futura

---

## Critérios de Sucesso

1. Cadastrar perfil de um cliente leva menos de 3 minutos
2. Da segunda vez em diante, subir um anúncio completo leva menos de 2 minutos
3. Zero possibilidade de publicar sem localização definida
4. Copy gerada pela IA é aproveitável direto (sem edição) em pelo menos 60% dos casos
