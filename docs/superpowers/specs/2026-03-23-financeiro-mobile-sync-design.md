# Financeiro Mobile Sync — Design Spec

**Data:** 2026-03-23
**Projeto:** Jake OS — Módulo Financeiro Pessoal
**Objetivo:** Migrar dados do financeiro de `localStorage` para Neon DB, expor Jake OS via cloudflared tunnel permanente, e tornar o layout do financeiro responsivo para mobile.

---

## Contexto

O módulo financeiro atual (`jake_desktop/static/js/financeiro.js`) armazena todos os dados em `localStorage` do browser. Isso impede acesso sincronizado de outros dispositivos. O Jake OS roda na porta 5050 sem URL pública. O `cloudflared` está instalado mas não configurado.

---

## Arquitetura

Quatro partes independentes implementadas em sequência:

1. **Banco de dados** — duas tabelas novas no Neon (PostgreSQL existente)
2. **API Flask** — 6 rotas CRUD protegidas por `@login_required`
3. **Frontend** — `financeiro.js` migra de `localStorage` para API; CSS responsivo adicionado
4. **Cloudflared** — tunnel nomeado permanente via systemd

---

## Parte 1: Banco de Dados

### Tabelas

```sql
CREATE TABLE fin_transacoes (
    id          SERIAL PRIMARY KEY,
    descricao   TEXT NOT NULL,
    valor       NUMERIC(10,2) NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('Entrada', 'Saída')),
    categoria   TEXT NOT NULL CHECK (categoria IN ('Fixa', 'Variável')),
    recorrente  BOOLEAN DEFAULT false,
    data        DATE NOT NULL
);

CREATE TABLE fin_raiox (
    id          SERIAL PRIMARY KEY,
    nome        TEXT NOT NULL,
    grupo       TEXT NOT NULL CHECK (grupo IN ('entradas', 'fixas', 'variaveis')),
    valores     JSONB NOT NULL  -- array de 12 valores numéricos [jan..dez]
);
```

### Seed inicial

Script de migração (`scripts/seed_financeiro.py`) lê os dados hardcoded do `financeiro.js` e os insere nas tabelas via `DATABASE_URL`. Roda uma única vez — verifica se as tabelas já têm dados antes de inserir (idempotente).

---

## Parte 2: API Flask

6 rotas novas em `jake_desktop/app.py`, todas com `@login_required`:

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/financeiro/transacoes` | Retorna todas as transações ordenadas por data desc |
| `POST` | `/api/financeiro/transacoes` | Cria nova transação |
| `PUT` | `/api/financeiro/transacoes/<id>` | Atualiza transação existente |
| `DELETE` | `/api/financeiro/transacoes/<id>` | Remove transação |
| `GET` | `/api/financeiro/raiox` | Retorna raio-x completo agrupado por grupo |
| `PUT` | `/api/financeiro/raiox` | Substitui raio-x completo (recebe array de linhas) |

### Formato de resposta — transações

```json
[
  {
    "id": 1,
    "descricao": "Dentto",
    "valor": 4300.00,
    "tipo": "Entrada",
    "categoria": "Fixa",
    "recorrente": true,
    "data": "2026-01-05"
  }
]
```

### Formato de resposta — raio-x

```json
{
  "entradas": [
    {"id": 1, "nome": "Dentto", "valores": [4300, 4950, 4950, ...]},
    ...
  ],
  "fixas": [...],
  "variaveis": [...]
}
```

### Conexão DB

Usa `DATABASE_URL` do `.env` via `psycopg2` (já usado em `core/db.py`). As rotas do financeiro importam `psycopg2` diretamente — sem ORM.

---

## Parte 3: Frontend

### financeiro.js

- Remover array `TRANSACOES` hardcoded e `RAIOX_PADRAO` hardcoded
- Remover todas as referências a `localStorage`
- Adicionar `carregarDados()` chamado no init — faz `GET /api/financeiro/transacoes` e `GET /api/financeiro/raiox` e popula as variáveis em memória
- Adicionar/editar transação: `POST`/`PUT` para a API antes de atualizar a UI
- Deletar: `DELETE` para a API antes de remover da UI
- Salvar raio-x: `PUT /api/financeiro/raiox` ao invés de `localStorage.setItem`

### CSS responsivo

Adicionado em `jake_desktop/static/css/dashboard.css` via media query `@media (max-width: 768px)`:

- **Cards de resumo** (receita/despesa/saldo): `flex-direction: column`
- **Tabela de transações**: linhas `<tr>` viram cards via `display: block` com pseudo-elemento de label
- **Raio-x**: `overflow-x: auto` com coluna `nome` fixada (`position: sticky; left: 0`)
- **Botões de ação**: `min-height: 44px; min-width: 44px`
- **Formulário**: campos em coluna única (`flex-direction: column`)

Nenhuma alteração no layout desktop.

---

## Parte 4: Cloudflared Tunnel

### Configuração

Tunnel nomeado `jake-os` via Cloudflare Dashboard ou CLI:

```bash
/root/cloudflared tunnel login          # autentica com conta Cloudflare
/root/cloudflared tunnel create jake-os # cria tunnel
```

Config em `/root/.cloudflared/config.yml`:

```yaml
tunnel: jake-os
credentials-file: /root/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: jake-os.seudominio.com
    service: http://localhost:5050
  - service: http_status:404
```

DNS: adicionar CNAME no Cloudflare apontando `jake-os.seudominio.com` → `<tunnel-id>.cfargotunnel.com`.

### Systemd service

`/etc/systemd/system/cloudflared-jake.service`:

```ini
[Unit]
Description=Cloudflared tunnel — Jake OS
After=network.target

[Service]
ExecStart=/root/cloudflared tunnel run jake-os
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable cloudflared-jake
systemctl start cloudflared-jake
```

### Autenticação

A autenticação existente do Jake OS (session-based, `admin@jakeos.local` / `Jake@2024!`) protege todos os endpoints. Não é necessária autenticação adicional no tunnel.

---

## Critérios de Sucesso

- [ ] Tabelas `fin_transacoes` e `fin_raiox` criadas no Neon com dados migrados
- [ ] 6 rotas API funcionando (testáveis via curl)
- [ ] Adicionar/editar/deletar transação persiste no banco e aparece após refresh
- [ ] Editar raio-x persiste no banco
- [ ] Layout financeiro funcional em tela de 390px (iPhone) sem scroll horizontal indesejado
- [ ] Jake OS acessível via URL pública do tunnel
- [ ] Tunnel sobe automaticamente com o servidor (systemd)
