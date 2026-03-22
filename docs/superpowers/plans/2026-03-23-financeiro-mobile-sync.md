# Financeiro Mobile Sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar dados do financeiro de localStorage para Neon DB, criar API CRUD, tornar o layout responsivo e expor Jake OS via cloudflared tunnel permanente.

**Architecture:** Script de seed cria tabelas e popula com dados 2026 hardcoded. 6 rotas Flask novas fazem CRUD no Neon usando `_get_db()` existente. O `financeiro.js` carrega dados via `fetch()` no init e envia mudanças via API. CSS responsivo adicionado via media query. Cloudflared tunnel nomeado roda via systemd.

**Tech Stack:** Python/Flask, psycopg2, PostgreSQL (Neon), JavaScript (fetch), CSS media queries, cloudflared.

---

## Arquivos

| Arquivo | Mudança |
|---|---|
| `scripts/seed_financeiro.py` | Novo — cria tabelas e popula dados 2026 |
| `jake_desktop/app.py` | Adicionar 6 rotas `/api/financeiro/*` |
| `jake_desktop/tests/test_financeiro_api.py` | Novo — 8 testes TDD para as rotas |
| `jake_desktop/static/js/financeiro.js` | Migrar localStorage → fetch API; `.v` → `.valores` |
| `jake_desktop/static/css/dashboard.css` | Adicionar media query `@media (max-width: 768px)` |
| `/root/.cloudflared/config.yml` | Novo — config do tunnel |
| `/etc/systemd/system/cloudflared-jake.service` | Novo — serviço systemd |

---

## Task 1: Seed Script — criar tabelas e popular dados

**Files:**
- Create: `scripts/seed_financeiro.py`

Não tem TDD — é script one-shot de migração. Testar rodando e verificando contagem no banco.

- [ ] **Step 1: Criar `scripts/seed_financeiro.py`**

```python
#!/usr/bin/env python3
"""
Cria tabelas fin_transacoes e fin_raiox no Neon e popula com dados de 2026.
Idempotente: verifica COUNT(*) antes de inserir.
Executar: PYTHONPATH=/root python3 scripts/seed_financeiro.py
"""
import sys, json
sys.path.insert(0, '/root')
from core.db import get_conn

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS fin_transacoes (
    id         SERIAL PRIMARY KEY,
    descricao  TEXT NOT NULL,
    valor      NUMERIC(10,2) NOT NULL,
    tipo       TEXT NOT NULL CHECK (tipo IN ('Entrada', 'Saída')),
    categoria  TEXT NOT NULL CHECK (categoria IN ('Fixa', 'Variável')),
    recorrente BOOLEAN DEFAULT false,
    data       DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS fin_raiox (
    id      SERIAL PRIMARY KEY,
    nome    TEXT NOT NULL,
    grupo   TEXT NOT NULL CHECK (grupo IN ('entradas', 'fixas', 'variaveis')),
    valores JSONB NOT NULL
);
"""

TRANSACOES = [
    # Janeiro 2026
    ('Dentto',               4300.00, 'Entrada', 'Fixa',     True,  '2026-01-05'),
    ('Pedras Carula',         800.00, 'Entrada', 'Fixa',     True,  '2026-01-05'),
    ('Suprema Metal',         800.00, 'Entrada', 'Fixa',     True,  '2026-01-05'),
    ('Piloti',               3250.00, 'Entrada', 'Fixa',     True,  '2026-01-05'),
    ('Diversos',             1100.00, 'Entrada', 'Variável', False, '2026-01-10'),
    ('Aluguel',              1100.00, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Academia',              100.00, 'Saída',   'Fixa',     True,  '2026-01-10'),
    ('Mercado',               700.00, 'Saída',   'Fixa',     True,  '2026-01-15'),
    ('Internet',              100.00, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Água',                   60.00, 'Saída',   'Fixa',     True,  '2026-01-10'),
    ('Luz',                   220.00, 'Saída',   'Fixa',     True,  '2026-01-10'),
    ('Assinaturas',           160.00, 'Saída',   'Fixa',     True,  '2026-01-01'),
    ('Gasolina',              200.00, 'Saída',   'Fixa',     True,  '2026-01-20'),
    ('Sofá (parcela)',        223.10, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Pets',                  130.00, 'Saída',   'Fixa',     True,  '2026-01-15'),
    ('Computador (parc.)',    441.58, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Cadeira (parcela)',     173.24, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Celular (parcela)',     399.79, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Mercado Livre/Shopee',  923.62, 'Saída',   'Variável', False, '2026-01-20'),
    ('ME/Impostos',          1200.00, 'Saída',   'Fixa',     True,  '2026-01-20'),
    ('Geladeira (parcela)',   217.50, 'Saída',   'Fixa',     True,  '2026-01-05'),
    ('Sicoob',               1793.93, 'Saída',   'Variável', False, '2026-01-15'),
    ('Bradesco',             6905.21, 'Saída',   'Variável', False, '2026-01-15'),
    # Fevereiro 2026
    ('Dentto',               4950.00, 'Entrada', 'Fixa',     True,  '2026-02-05'),
    ('Pedras Carula',         800.00, 'Entrada', 'Fixa',     True,  '2026-02-05'),
    ('Suprema Metal',         800.00, 'Entrada', 'Fixa',     True,  '2026-02-05'),
    ('Piloti',               3500.00, 'Entrada', 'Fixa',     True,  '2026-02-05'),
    ('Diversos',              600.00, 'Entrada', 'Variável', False, '2026-02-10'),
    ('Aluguel',              1100.00, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Academia',              104.43, 'Saída',   'Fixa',     True,  '2026-02-10'),
    ('Mercado',               700.00, 'Saída',   'Fixa',     True,  '2026-02-15'),
    ('Internet',              100.00, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Água',                   60.00, 'Saída',   'Fixa',     True,  '2026-02-10'),
    ('Luz',                   220.00, 'Saída',   'Fixa',     True,  '2026-02-10'),
    ('Assinaturas',           160.00, 'Saída',   'Fixa',     True,  '2026-02-01'),
    ('Gasolina',              200.00, 'Saída',   'Fixa',     True,  '2026-02-20'),
    ('Sofá (parcela)',        223.10, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Pets',                  130.00, 'Saída',   'Fixa',     True,  '2026-02-15'),
    ('Computador (parc.)',    441.58, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Cadeira (parcela)',     173.24, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Celular (parcela)',     399.79, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('ME/Impostos',          1200.00, 'Saída',   'Fixa',     True,  '2026-02-20'),
    ('Geladeira (parcela)',   217.50, 'Saída',   'Fixa',     True,  '2026-02-05'),
    ('Sicoob',               4204.39, 'Saída',   'Variável', False, '2026-02-15'),
]

RAIOX = [
    ('Dentto',        'entradas', [4300,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950]),
    ('Pedras Carula', 'entradas', [800,800,800,800,800,800,800,800,800,800,800,800]),
    ('Suprema Metal', 'entradas', [800,800,800,800,800,800,800,800,800,800,800,800]),
    ('Piloti',        'entradas', [3250,3500,3500,3500,3500,3500,3500,3500,3500,3500,3500,3500]),
    ('Diversos',      'entradas', [1100,600,546.87,0,0,0,0,0,0,0,0,0]),
    ('Aluguel',       'fixas',    [1100,1100,1100,1100,1100,1100,1100,1100,1100,1100,1100,1100]),
    ('Academia',      'fixas',    [100,104.43,104.43,100,100,100,100,100,100,100,100,100]),
    ('Mercado',       'fixas',    [700,700,800,800,800,800,800,800,800,800,800,800]),
    ('Internet',      'fixas',    [100,100,100,100,100,100,100,100,100,100,100,100]),
    ('Água',          'fixas',    [60,60,60,60,60,60,60,60,60,60,60,60]),
    ('Luz',           'fixas',    [220,220,220,220,220,220,220,220,220,220,220,220]),
    ('Assinaturas',   'fixas',    [160,160,350,350,350,350,350,350,350,350,350,350]),
    ('Gasolina',      'fixas',    [200,200,200,200,200,200,200,200,200,200,200,200]),
    ('Sofá (parc.)',  'fixas',    [223.10,223.10,223.10,223.10,223.10,223.10,223.10,223.10,223.10,223.10,223.10,223.10]),
    ('Pets',          'fixas',    [130,130,130,130,130,130,130,130,130,130,130,130]),
    ('Computador',    'fixas',    [441.58,441.58,441.58,441.58,441.58,441.58,441.58,441.58,441.58,441.58,441.58,441.58]),
    ('Cadeira',       'fixas',    [173.24,173.24,173.24,173.24,173.24,173.24,173.24,173.24,0,0,0,0]),
    ('Celular',       'fixas',    [399.79,399.79,399.79,399.79,399.79,399.79,399.79,399.79,399.79,399.79,399.79,399.79]),
    ('Mercado Livre', 'fixas',    [923.62,923.62,456.16,177.41,0,0,0,0,0,0,0,0]),
    ('ME/Impostos',   'fixas',    [1200,1200,1200,1200,1200,1200,1200,1200,1200,0,0,0]),
    ('Geladeira',     'fixas',    [217.50,217.50,217.50,217.50,0,0,0,0,0,0,0,0]),
    ('Sicoob',        'variaveis',[1793.93,0,4204.39,0,0,0,0,0,0,0,0,0]),
    ('Bradesco',      'variaveis',[6905.21,0,0,0,0,0,0,0,0,0,0,0]),
]

def main():
    conn = get_conn()
    cur = conn.cursor()

    # Criar tabelas
    cur.execute(CREATE_SQL)
    conn.commit()
    print("Tabelas criadas (ou já existiam).")

    # Seed idempotente: só insere se vazio
    cur.execute("SELECT COUNT(*) FROM fin_transacoes")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO fin_transacoes (descricao,valor,tipo,categoria,recorrente,data) VALUES (%s,%s,%s,%s,%s,%s)",
            TRANSACOES
        )
        conn.commit()
        print(f"Inseridas {len(TRANSACOES)} transações.")
    else:
        print("fin_transacoes já tem dados — pulando.")

    cur.execute("SELECT COUNT(*) FROM fin_raiox")
    if cur.fetchone()[0] == 0:
        for nome, grupo, valores in RAIOX:
            cur.execute(
                "INSERT INTO fin_raiox (nome, grupo, valores) VALUES (%s, %s, %s)",
                (nome, grupo, json.dumps(valores))
            )
        conn.commit()
        print(f"Inseridas {len(RAIOX)} linhas no raio-x.")
    else:
        print("fin_raiox já tem dados — pulando.")

    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rodar o seed**

```bash
PYTHONPATH=/root python3 /root/scripts/seed_financeiro.py
```

Esperado:
```
Tabelas criadas (ou já existiam).
Inseridas 44 transações.
Inseridas 23 linhas no raio-x.
Done.
```

- [ ] **Step 3: Verificar no banco**

```bash
PYTHONPATH=/root python3 -c "
from core.db import get_conn
conn = get_conn()
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM fin_transacoes')
print('transacoes:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM fin_raiox')
print('raiox:', cur.fetchone()[0])
conn.close()
"
```

Esperado: `transacoes: 44` e `raiox: 23`

- [ ] **Step 4: Commit**

```bash
cd /root && git add scripts/seed_financeiro.py
git commit -m "feat: seed script fin_transacoes e fin_raiox com dados 2026"
```

---

## Task 2: API Flask — 6 rotas CRUD (TDD)

**Files:**
- Create: `jake_desktop/tests/test_financeiro_api.py`
- Modify: `jake_desktop/app.py`

**Contexto:**
- Padrão de rota existente: `@app.route(...)` depois `@login_required` depois `def fn():`
- Usar `_get_db()` → retorna conexão com `RealDictCursor` (rows como dicts)
- Padrão: `conn = _get_db(); cur = conn.cursor(); ... ; conn.commit(); conn.close()`
- Erros: `return jsonify({"error": str(e)}), 500`
- `json` já importado em `app.py` (linha ~28)

- [ ] **Step 1: Escrever os testes (arquivo novo)**

Criar `jake_desktop/tests/test_financeiro_api.py`:

```python
"""Testes TDD para as 6 rotas /api/financeiro/*"""
import sys, json, pytest
sys.path.insert(0, '/root/jake_desktop')
from unittest.mock import MagicMock, patch


def _mock_conn(rows=None, novo_id=None):
    """Retorna mock de conexão psycopg2 com RealDictCursor."""
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    if rows is not None:
        cur.fetchall.return_value = rows
    if novo_id is not None:
        cur.fetchone.return_value = {"id": novo_id}
    return conn


@pytest.fixture
def client():
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.secret_key = 'test-secret'
    with flask_app.app.test_client() as c:
        with c.session_transaction() as sess:
            sess['logged_in'] = True
        yield c


@pytest.fixture
def client_anonimo():
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.secret_key = 'test-secret'
    with flask_app.app.test_client() as c:
        yield c


# ── GET /api/financeiro/transacoes ──────────────────────────────────────────

def test_listar_transacoes(client):
    row = {"id": 1, "descricao": "Dentto", "valor": 4300.0,
           "tipo": "Entrada", "categoria": "Fixa", "recorrente": True, "data": "2026-01-05"}
    with patch("app._get_db", return_value=_mock_conn(rows=[row])):
        resp = client.get("/api/financeiro/transacoes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data[0]["descricao"] == "Dentto"


# ── POST /api/financeiro/transacoes ─────────────────────────────────────────

def test_criar_transacao(client):
    with patch("app._get_db", return_value=_mock_conn(novo_id=45)):
        resp = client.post("/api/financeiro/transacoes", json={
            "descricao": "Nova entrada", "valor": 500.0,
            "tipo": "Entrada", "categoria": "Fixa", "data": "2026-03-01"
        })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == 45
    assert body["ok"] is True


def test_criar_transacao_campo_faltando(client):
    with patch("app._get_db", return_value=_mock_conn()):
        resp = client.post("/api/financeiro/transacoes", json={"descricao": "incompleto"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── PUT /api/financeiro/transacoes/<id> ─────────────────────────────────────

def test_atualizar_transacao(client):
    with patch("app._get_db", return_value=_mock_conn()):
        resp = client.put("/api/financeiro/transacoes/1", json={"valor": 5000.0})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# ── DELETE /api/financeiro/transacoes/<id> ───────────────────────────────────

def test_deletar_transacao(client):
    with patch("app._get_db", return_value=_mock_conn()):
        resp = client.delete("/api/financeiro/transacoes/1")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# ── GET /api/financeiro/raiox ────────────────────────────────────────────────

def test_get_raiox(client):
    rows = [{"id": 1, "nome": "Dentto", "grupo": "entradas",
             "valores": [4300,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950]}]
    with patch("app._get_db", return_value=_mock_conn(rows=rows)):
        resp = client.get("/api/financeiro/raiox")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "entradas" in data and "fixas" in data and "variaveis" in data
    assert data["entradas"][0]["nome"] == "Dentto"


# ── PUT /api/financeiro/raiox ────────────────────────────────────────────────

def test_salvar_raiox(client):
    payload = {
        "entradas": [{"nome": "Dentto", "valores": [4300,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950,4950]}],
        "fixas": [],
        "variaveis": []
    }
    with patch("app._get_db", return_value=_mock_conn()):
        resp = client.put("/api/financeiro/raiox", json=payload)
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_rotas_requerem_login(client_anonimo):
    for url, method in [
        ("/api/financeiro/transacoes", "GET"),
        ("/api/financeiro/transacoes", "POST"),
        ("/api/financeiro/raiox", "GET"),
        ("/api/financeiro/raiox", "PUT"),
    ]:
        resp = getattr(client_anonimo, method.lower())(url, json={})
        assert resp.status_code in (302, 401), f"{method} {url} deveria redirecionar"
```

- [ ] **Step 2: Confirmar que os testes falham**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_financeiro_api.py -v 2>&1 | tail -15
```

Esperado: `FAILED` — `404` pois as rotas ainda não existem.

- [ ] **Step 3: Implementar as 6 rotas em `app.py`**

Localizar o bloco de rotas do financeiro existente (`grep -n "financeiro" /root/jake_desktop/app.py`) e adicionar as 6 rotas novas logo após `/api/financeiro/analise`:

```python
# ── Financeiro: CRUD Transações ──────────────────────────────────────────────

@app.route("/api/financeiro/transacoes", methods=["GET"])
@login_required
def financeiro_listar_transacoes():
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute(
            "SELECT id, descricao, valor, tipo, categoria, recorrente, data::text "
            "FROM fin_transacoes ORDER BY data DESC"
        )
        rows = cur.fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/transacoes", methods=["POST"])
@login_required
def financeiro_criar_transacao():
    d = request.get_json() or {}
    for campo in ["descricao", "valor", "tipo", "categoria", "data"]:
        if not d.get(campo):
            return jsonify({"error": f"Campo obrigatório: {campo}"}), 400
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO fin_transacoes (descricao,valor,tipo,categoria,recorrente,data) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (d["descricao"], d["valor"], d["tipo"], d["categoria"],
             d.get("recorrente", False), d["data"])
        )
        novo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/transacoes/<int:tid>", methods=["PUT"])
@login_required
def financeiro_atualizar_transacao(tid):
    d = request.get_json() or {}
    campos_validos = ["descricao", "valor", "tipo", "categoria", "recorrente", "data"]
    campos = {k: v for k, v in d.items() if k in campos_validos}
    if not campos:
        return jsonify({"error": "Nenhum campo válido"}), 400
    try:
        conn = _get_db()
        cur  = conn.cursor()
        sets   = ", ".join(f"{k} = %s" for k in campos)
        valores = list(campos.values()) + [tid]
        cur.execute(f"UPDATE fin_transacoes SET {sets} WHERE id = %s", valores)
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/transacoes/<int:tid>", methods=["DELETE"])
@login_required
def financeiro_deletar_transacao(tid):
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("DELETE FROM fin_transacoes WHERE id = %s", (tid,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Financeiro: CRUD Raio-X ──────────────────────────────────────────────────

@app.route("/api/financeiro/raiox", methods=["GET"])
@login_required
def financeiro_get_raiox():
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("SELECT id, nome, grupo, valores FROM fin_raiox ORDER BY grupo, id")
        rows = cur.fetchall()
        conn.close()
        resultado = {"entradas": [], "fixas": [], "variaveis": []}
        for r in rows:
            resultado[r["grupo"]].append({
                "id": r["id"], "nome": r["nome"], "valores": r["valores"]
            })
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/financeiro/raiox", methods=["PUT"])
@login_required
def financeiro_salvar_raiox():
    d = request.get_json() or {}
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("DELETE FROM fin_raiox")
        for grupo in ["entradas", "fixas", "variaveis"]:
            for item in d.get(grupo, []):
                cur.execute(
                    "INSERT INTO fin_raiox (nome, grupo, valores) VALUES (%s, %s, %s)",
                    (item["nome"], grupo, json.dumps(item["valores"]))
                )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 4: Verificar sintaxe**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "import app; print('OK')" 2>&1 | head -3
```

Esperado: `OK`

- [ ] **Step 5: Rodar os testes**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_financeiro_api.py -v 2>&1 | tail -15
```

Esperado: **8 passed**

- [ ] **Step 6: Confirmar testes anteriores ainda passam**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/ -q 2>&1 | tail -3
```

Esperado: `42 passed` (34 anteriores + 8 novos)

- [ ] **Step 7: Commit**

```bash
cd /root && git add jake_desktop/tests/test_financeiro_api.py jake_desktop/app.py
git commit -m "feat: API CRUD financeiro — 6 rotas /api/financeiro/* (TDD)"
```

---

## Task 3: Frontend — migrar financeiro.js + CSS responsivo

**Files:**
- Modify: `jake_desktop/static/js/financeiro.js`
- Modify: `jake_desktop/static/css/dashboard.css`

**Contexto crítico:**
- `TRANSACOES` (array hardcoded linhas 10-57) → remover; substituir por `var TRANSACOES = [];` carregado da API
- `RAIOX_PADRAO` (linhas 60-90) → manter como fallback local
- `_nextId` (linha 9) → remover; IDs vêm do banco
- `RAIOX_KEY`, `salvarRaioX()` (localStorage), `carregarRaioX()` (linhas 92-131) → remover/substituir
- `var RAIOX = carregarRaioX() || JSON.parse(...)` (linha 142) → mudar para `var RAIOX = JSON.parse(JSON.stringify(RAIOX_PADRAO));` (fallback local até API carregar)
- Rename `.v[` → `.valores[` e `.v.` → `.valores.` — 6 ocorrências: linhas 181, 350, 391, 400, 417, 424
- `initFinanceiro()` (linha 202) chama `atualizarTudo(); renderRaioX();` no final (linhas 235-236) — substituir por `carregarDados();`
- `salvarRaioX()` deve fazer `PUT /api/financeiro/raiox` ao invés de `localStorage.setItem`

Não tem TDD — testar manualmente no browser após as mudanças.

- [ ] **Step 1: Remover dados hardcoded e adicionar variáveis iniciais**

No início do IIFE (logo após `(function () {`), substituir as linhas 9-57 (var _nextId e array TRANSACOES):

```javascript
  var TRANSACOES = [];  // carregado da API em carregarDados()
```

- [ ] **Step 2: Remover localStorage e adicionar `salvarRaioX()` via API**

Substituir as funções `salvarRaioX()`, `carregarRaioX()` e a constante `RAIOX_KEY` (linhas 92-131) por:

```javascript
  function salvarRaioX() {
    fetch('/api/financeiro/raiox', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(RAIOX)
    })
    .then(function(r) { return r.json(); })
    .then(function() { flashRaioX('✓ Salvo'); })
    .catch(function() { flashRaioX('⚠ Erro ao salvar'); });
    sincronizarPatrimonioMilhao();
  }
```

- [ ] **Step 3: Atualizar a inicialização de `RAIOX` (linha 142)**

Substituir:
```javascript
  var RAIOX = carregarRaioX() || JSON.parse(JSON.stringify(RAIOX_PADRAO));
```
por:
```javascript
  var RAIOX = JSON.parse(JSON.stringify(RAIOX_PADRAO));
```

- [ ] **Step 4: Renomear `.v` → `.valores` (6 ocorrências)**

Localizar e substituir cada ocorrência:

```bash
grep -n "\.v\[" /root/jake_desktop/static/js/financeiro.js
grep -n "\.v\." /root/jake_desktop/static/js/financeiro.js
grep -n "{ nome.*v:" /root/jake_desktop/static/js/financeiro.js
```

Substituições a fazer:
- Linha ~181: `item.v[mes]` → `item.valores[mes]`
- Linha ~350: `{ nome: 'Nova linha', v: [0,0,0,0,0,0,0,0,0,0,0,0] }` → `{ nome: 'Nova linha', valores: [0,0,0,0,0,0,0,0,0,0,0,0] }`
- Linha ~391: `RAIOX[sec][idx].v[mes]` → `RAIOX[sec][idx].valores[mes]`
- Linha ~400: `RAIOX[sec][idx].v[mes]` → `RAIOX[sec][idx].valores[mes]`
- Linha ~417: `item.v.reduce` → `item.valores.reduce`
- Linha ~424: `item.v.forEach` → `item.valores.forEach`

Também atualizar `RAIOX_PADRAO` (linhas 62-89): todas as chaves `v:` → `valores:` (5 entradas + 16 fixas + 2 variaveis = 23 ocorrências).

- [ ] **Step 5: Adicionar `carregarDados()` e atualizar `initFinanceiro()`**

Adicionar imediatamente antes de `function initFinanceiro()`:

```javascript
  function carregarDados() {
    var container = document.getElementById('fin-pane-visao-geral');
    if (container) container.innerHTML = '<p style="text-align:center;padding:2rem;color:var(--cyan)">Carregando...</p>';

    Promise.all([
      fetch('/api/financeiro/transacoes').then(function(r){ return r.json(); }),
      fetch('/api/financeiro/raiox').then(function(r){ return r.json(); })
    ]).then(function(resultados) {
      TRANSACOES = resultados[0];
      var raiox   = resultados[1];
      if (raiox && raiox.entradas) RAIOX = raiox;
      if (container) container.innerHTML = '';
      atualizarTudo();
      renderRaioX();
    }).catch(function(e) {
      console.error('Erro ao carregar dados financeiros:', e);
      if (container) container.innerHTML = '<p style="text-align:center;padding:2rem;color:#ff6b6b">Erro ao carregar dados. Verifique conexão.</p>';
    });
  }
```

No final de `initFinanceiro()`, substituir as linhas:
```javascript
    atualizarTudo();
    renderRaioX();
```
por:
```javascript
    carregarDados();
```

- [ ] **Step 6: Adicionar CSS responsivo**

No final de `jake_desktop/static/css/dashboard.css`, adicionar:

```css
/* ── Financeiro: layout responsivo mobile ─────────────────────────────────── */
@media (max-width: 768px) {
  .fin-layout {
    padding: 1rem 1rem 1.5rem;
  }

  .fin-kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .fin-header {
    flex-direction: column;
    align-items: flex-start;
    gap: .5rem;
  }

  .fin-tabs-nav {
    flex-wrap: wrap;
    gap: .5rem;
  }

  /* Coluna de nome do raio-x fica sticky no scroll horizontal */
  .fin-raiox-table td:first-child,
  .fin-raiox-table th:first-child {
    position: sticky;
    left: 0;
    z-index: 2;
    background: var(--bg-card);
  }

  /* Botões com toque confortável */
  .fin-rx-del-btn,
  .fin-tab-btn,
  .fin-ai-btn,
  button[class^="fin-"] {
    min-height: 44px;
    min-width: 44px;
  }

  /* Formulários em coluna única */
  .fin-add-form,
  .fin-form-row {
    flex-direction: column;
  }
}
```

- [ ] **Step 7: Verificar sintaxe do app.py (não mudamos, mas confirmar)**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "import app; print('OK')"
```

- [ ] **Step 8: Testar no browser**

Subir o Jake OS:
```bash
cd /root/jake_desktop && source venv/bin/activate && python app.py &
```

Abrir `http://localhost:5050` → login → ir em Financeiro.

Checklist manual:
- [ ] Página carrega com dados (KPIs preenchidos)
- [ ] Raio-x exibe as linhas com valores corretos
- [ ] Editar um valor no raio-x → aba outra → voltar → valor persistido (banco)
- [ ] Abrir DevTools → 390px → layout em 2 colunas nos KPIs
- [ ] Raio-x scroll horizontal dentro do container

- [ ] **Step 9: Commit**

```bash
cd /root && git add jake_desktop/static/js/financeiro.js jake_desktop/static/css/dashboard.css
git commit -m "feat: financeiro.js migra localStorage → API; layout responsivo mobile"
```

---

## Task 4: Cloudflared Tunnel

**Files:**
- Create: `/root/.cloudflared/config.yml`
- Create: `/etc/systemd/system/cloudflared-jake.service`

Sem TDD — setup manual com verificação de status.

**Pré-requisito:** ter uma conta Cloudflare com domínio configurado (ou usar subdomínio `*.pages.dev`).

- [ ] **Step 1: Autenticar no Cloudflare**

```bash
/root/cloudflared tunnel login
```

Abrirá uma URL no terminal. Copiar e abrir no browser → selecionar o domínio → autorizar. Um arquivo `cert.pem` será salvo em `/root/.cloudflared/`.

- [ ] **Step 2: Criar o tunnel**

```bash
/root/cloudflared tunnel create jake-os
```

Saída esperada:
```
Created tunnel jake-os with id <UUID>
```

Anotar o `<UUID>` (também disponível via `ls /root/.cloudflared/*.json`).

- [ ] **Step 3: Criar config.yml**

Criar `/root/.cloudflared/config.yml` (substituir `<UUID>` e `seudominio.com`):

```yaml
tunnel: <UUID>
credentials-file: /root/.cloudflared/<UUID>.json

ingress:
  - hostname: jake-os.seudominio.com
    service: http://localhost:5050
  - service: http_status:404
```

- [ ] **Step 4: Adicionar DNS no Cloudflare**

```bash
/root/cloudflared tunnel route dns jake-os jake-os.seudominio.com
```

Ou adicionar manualmente no painel Cloudflare: CNAME `jake-os` → `<UUID>.cfargotunnel.com`.

- [ ] **Step 5: Testar tunnel antes do systemd**

```bash
/root/cloudflared tunnel run jake-os
```

Em outro terminal, curl:
```bash
curl -I https://jake-os.seudominio.com
```

Esperado: `HTTP/2 302` (redirect para /login — Jake OS respondendo). Parar o tunnel com Ctrl+C.

- [ ] **Step 6: Criar serviço systemd**

Criar `/etc/systemd/system/cloudflared-jake.service`:

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

- [ ] **Step 7: Habilitar e iniciar**

```bash
systemctl daemon-reload
systemctl enable cloudflared-jake
systemctl start cloudflared-jake
systemctl status cloudflared-jake
```

Esperado: `Active: active (running)`

- [ ] **Step 8: Testar URL pública**

```bash
curl -I https://jake-os.seudominio.com
```

Esperado: `HTTP/2 302` (redirect para /login)

Testar no celular: abrir `https://jake-os.seudominio.com` → fazer login → ir em Financeiro.

- [ ] **Step 9: Commit das configs**

```bash
cd /root
git add .cloudflared/config.yml
git commit -m "feat: cloudflared tunnel jake-os — Jake OS acessível publicamente"
```

---

## Verificação Final

```bash
# 1. Testes passando
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/ -q 2>&1 | tail -3
# Esperado: 42 passed

# 2. Dados no banco
PYTHONPATH=/root python3 -c "
from core.db import get_conn
conn = get_conn(); cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM fin_transacoes'); print('transacoes:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM fin_raiox'); print('raiox:', cur.fetchone()[0])
conn.close()
"
# Esperado: transacoes >= 44, raiox >= 23

# 3. Tunnel ativo
systemctl is-active cloudflared-jake
# Esperado: active

# 4. Sintaxe app.py
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "import app; print('OK')"
# Esperado: OK
```
