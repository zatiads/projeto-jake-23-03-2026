# Financeiro Mobile Sync — Design Spec

**Data:** 2026-03-23
**Projeto:** Jake OS — Módulo Financeiro Pessoal
**Objetivo:** Migrar dados do financeiro de `localStorage` para Neon DB, expor Jake OS via cloudflared tunnel permanente, e tornar o layout do financeiro responsivo para mobile.

---

## Contexto

O módulo financeiro atual (`jake_desktop/static/js/financeiro.js`) armazena todos os dados em `localStorage` do browser. Os dados hardcoded usam a chave `v` para o array de valores mensais do raio-x (ex: `{ nome: 'Dentto', v: [4300,...] }`). Isso impede acesso sincronizado de outros dispositivos. O Jake OS roda na porta 5050 sem URL pública. O `cloudflared` está instalado mas não configurado.

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
    valores     JSONB NOT NULL  -- array de 12 valores numéricos [jan..dez] (2026)
);
```

**Nota de design:** `fin_raiox` não tem coluna `ano` — tabela single-year por design. Adicionar `ano` quando houver necessidade de múltiplos anos.

### Seed inicial

Script `scripts/seed_financeiro.py` — insere os dados hardcoded do `financeiro.js` nas tabelas. Idempotente via `SELECT COUNT(*) FROM fin_transacoes` e `fin_raiox` — não insere se as tabelas já têm dados.

**Atenção ao rename:** no JS os dados do raio-x usam a chave `v`; na tabela a coluna chama `valores`. O seed deve mapear `item['v']` → coluna `valores`.

---

## Parte 2: API Flask

6 rotas novas em `jake_desktop/app.py`, todas com `@login_required`. Usar `_get_db()` existente (retorna `RealDictCursor` — rows como dicts). Seguir padrão existente: `conn, cur = _get_db()` → operação → `conn.commit()` → `conn.close()`.

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/financeiro/transacoes` | Retorna **todas** as transações (sem filtro de mês — filtragem permanece no frontend) |
| `POST` | `/api/financeiro/transacoes` | Cria nova transação; retorna `{"id": N, "ok": true}` |
| `PUT` | `/api/financeiro/transacoes/<id>` | Atualiza transação; retorna `{"ok": true}` |
| `DELETE` | `/api/financeiro/transacoes/<id>` | Remove transação; retorna `{"ok": true}` |
| `GET` | `/api/financeiro/raiox` | Retorna raio-x agrupado por `grupo` |
| `PUT` | `/api/financeiro/raiox` | Substitui raio-x completo (DELETE all + INSERT) |

### Formato de resposta — GET transações

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

### Formato de resposta — GET raio-x

```json
{
  "entradas": [
    {"id": 1, "nome": "Dentto", "valores": [4300, 4950, 4950, ...]},
  ],
  "fixas": [...],
  "variaveis": [...]
}
```

### Formato de request — PUT raio-x

Recebe o objeto agrupado completo (mesmo formato do GET). O handler faz `DELETE FROM fin_raiox` seguido de INSERT de todas as linhas recebidas:

```json
{
  "entradas": [{"nome": "Dentto", "valores": [4300, ...]}, ...],
  "fixas": [...],
  "variaveis": [...]
}
```

### Erros

Em caso de erro retornar `{"error": "mensagem"}` com status 400 ou 500 (padrão existente no `app.py`).

---

## Parte 3: Frontend

### financeiro.js — mudanças

**Remover:**
- Arrays hardcoded `TRANSACOES` e `RAIOX_PADRAO`
- Variável `_nextId` (IDs passam a vir do banco via resposta do POST)
- Toda referência a `localStorage` (duas ocorrências: `setItem` linha ~96, `getItem` linha ~127)
- Função `carregarRaioX()` que lia do localStorage

**Adicionar:**
- `carregarDados()` assíncrona — faz `GET /api/financeiro/transacoes` e `GET /api/financeiro/raiox` em paralelo (`Promise.all`), popula as variáveis globais `TRANSACOES` e `RAIOX`, depois chama `atualizarTudo()` e `renderRaioX()`
- `initFinanceiro()` passa a chamar `carregarDados()` (assíncrono) ao invés de `atualizarTudo()` + `renderRaioX()` direto
- Estado de loading: enquanto `carregarDados()` executa, exibir spinner ou texto "Carregando..." no container principal do financeiro

**Rename obrigatório:** todas as referências `item.v[mes]` e `item.v` no JS devem ser trocadas para `item.valores[mes]` e `item.valores` (múltiplas ocorrências em `raixoSomaLinha`, `renderRaioXLinha`, etc.).

**Operações CRUD:**
- Adicionar transação: POST → usa `id` retornado no response para o objeto local
- Editar transação: PUT `/<id>`
- Deletar transação: DELETE `/<id>`
- Salvar raio-x (blur handlers): PUT `/api/financeiro/raiox` com objeto agrupado completo

### CSS responsivo

Adicionado em `jake_desktop/static/css/dashboard.css` via `@media (max-width: 768px)`:

- **Cards de resumo** (receita/despesa/saldo): `flex-direction: column`
- **Tabela de transações**: linhas `<tr>` viram cards via `display: block`
- **Raio-x**: `overflow-x: auto` no container; coluna `nome` fixada com `position: sticky; left: 0` — scroll horizontal **intencional e confinado** ao container do raio-x
- **Botões de ação**: `min-height: 44px; min-width: 44px`
- **Formulário**: campos em coluna única

Nenhuma alteração no layout desktop.

---

## Parte 4: Cloudflared Tunnel

### Setup

```bash
/root/cloudflared tunnel login           # abre browser para auth Cloudflare
/root/cloudflared tunnel create jake-os  # cria tunnel; imprime UUID do tunnel
```

O UUID é exibido no output do `create` e também disponível via `ls /root/.cloudflared/*.json`.

Config em `/root/.cloudflared/config.yml` (substituir `<tunnel-uuid>` e domínio):

```yaml
tunnel: <tunnel-uuid>
credentials-file: /root/.cloudflared/<tunnel-uuid>.json

ingress:
  - hostname: jake-os.seudominio.com
    service: http://localhost:5050
  - service: http_status:404
```

DNS: no painel Cloudflare, adicionar CNAME `jake-os` → `<tunnel-uuid>.cfargotunnel.com` (ou via `cloudflared tunnel route dns jake-os jake-os.seudominio.com`).

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

### Notas

- O cloudflared faz terminação TLS — Jake OS continua em HTTP interno, o browser recebe HTTPS
- `SESSION_COOKIE_SECURE` do Flask deve permanecer `False` (default) — o cookie vai em HTTP internamente, HTTPS no tunnel. Não setar `SESSION_COOKIE_SECURE=True`
- A autenticação existente do Jake OS protege todos os endpoints — não é necessária autenticação adicional no tunnel

---

## Critérios de Sucesso

- [ ] Tabelas `fin_transacoes` e `fin_raiox` criadas no Neon com dados migrados
- [ ] 6 rotas API funcionando (testáveis via curl)
- [ ] Adicionar/editar/deletar transação persiste no banco e aparece após refresh
- [ ] Editar raio-x persiste no banco após refresh
- [ ] Layout financeiro funcional em tela de 390px sem scroll horizontal na página; raio-x scrollável horizontalmente dentro do seu container
- [ ] Jake OS acessível via URL pública do tunnel com login funcionando
- [ ] Tunnel sobe automaticamente com o servidor (`systemctl status cloudflared-jake` → active)
