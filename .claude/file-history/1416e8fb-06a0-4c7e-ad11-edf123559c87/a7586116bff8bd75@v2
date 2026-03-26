# Análise de Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a página `#performance` do Jake OS com dashboard por agência (Piloti/Dentto), alertas de saldo baixo via badge + Telegram, e drill-down por cliente com comparação semanal e análise IA integrada ao vault Obsidian.

**Architecture:** 3 novas rotas Flask + enriquecimento de rota existente no backend; novo `performance.js` + HTML substituindo placeholder no frontend. Dados vêm da Meta Ads API (Graph API v21.0) via tokens por agência. Vault Obsidian em `/root/jake-brain/` fornece contexto histórico para a IA.

**Tech Stack:** Flask, Python 3, Meta Ads Graph API v21.0, Claude claude-sonnet-4-6, Vanilla JS (ES5), Pytest + unittest.mock

**Spec:** `docs/superpowers/specs/2026-03-24-performance-analise-design.md`

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `jake_desktop/app.py` | Modificar (~linha 794) | 3 novas rotas + enriquecer `/api/relatorios/analise` |
| `jake_desktop/templates/dashboard.html` | Modificar (linhas 301-313 e 1441) | HTML da página + registrar script |
| `jake_desktop/static/js/performance.js` | Criar | Toda a lógica do módulo: fetch, render, drawer, alertas |
| `jake_desktop/tests/test_performance_api.py` | Criar | Testes TDD das 3 novas rotas + analise enriquecida |

---

## Task 1: Rota `/api/performance/saldo`

**Files:**
- Modify: `jake_desktop/app.py` (após linha 793, antes do comentário `# ── API: Fábrica de Criativos`)
- Test: `jake_desktop/tests/test_performance_api.py`

- [ ] **Step 1: Criar arquivo de testes com fixture padrão**

Criar `jake_desktop/tests/test_performance_api.py`:

```python
"""Testes TDD para as rotas /api/performance/*"""
import sys, json, pytest
sys.path.insert(0, '/root/jake_desktop')
from unittest.mock import MagicMock, patch, mock_open


@pytest.fixture
def client():
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.secret_key = 'test-secret'
    with flask_app.app.test_client() as c:
        with c.session_transaction() as sess:
            sess['logged_in'] = True
        yield c


def _mock_meta_saldo(balance=15000, amount_spent=120000, spend_cap=150000, currency="BRL"):
    """Meta API response para saldo (valores em centavos)."""
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = {
        "balance": str(balance),
        "amount_spent": str(amount_spent),
        "spend_cap": str(spend_cap),
        "currency": currency,
        "id": "act_123",
    }
    return resp


# ── GET /api/performance/saldo ──────────────────────────────────────────────

def test_saldo_retorna_campos_esperados(client):
    with patch("app.requests.get", return_value=_mock_meta_saldo()) as mock_get:
        r = client.get("/api/performance/saldo/piloti/act_123456789")
        assert r.status_code == 200
        d = r.get_json()
        assert "balance" in d
        assert "amount_spent" in d
        assert "remaining" in d
        assert "alerta" in d


def test_saldo_alerta_true_quando_abaixo_150(client):
    # remaining = (spend_cap - amount_spent) / 100 = (15000 - 14000) / 100 = 100.0 < 150
    mock = _mock_meta_saldo(balance=10000, amount_spent=140000, spend_cap=150000)
    with patch("app.requests.get", return_value=mock):
        r = client.get("/api/performance/saldo/piloti/act_123456789")
        d = r.get_json()
        assert d["alerta"] is True


def test_saldo_alerta_false_quando_acima_150(client):
    # remaining = (200000 - 120000) / 100 = 800.0 > 150
    mock = _mock_meta_saldo(amount_spent=120000, spend_cap=200000)
    with patch("app.requests.get", return_value=mock):
        r = client.get("/api/performance/saldo/piloti/act_123456789")
        d = r.get_json()
        assert d["alerta"] is False


def test_saldo_account_id_invalido(client):
    r = client.get("/api/performance/saldo/piloti/123invalido")
    assert r.status_code == 400


def test_saldo_agencia_invalida(client):
    r = client.get("/api/performance/saldo/agencia_inexistente/act_123456789")
    assert r.status_code == 500
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_performance_api.py -v 2>&1 | head -30
```
Esperado: `ERROR` ou `FAILED` — rota ainda não existe.

- [ ] **Step 3: Adicionar cache e rota no `app.py`**

Localizar no `app.py` a linha `# ── API: Fábrica de Criativos` (próxima após linha 794).
Inserir ANTES dessa linha:

```python
# ── API: Performance — Saldo ────────────────────────────────────────────────

_perf_saldo_cache: dict = {}
_PERF_SALDO_TTL = 1800  # 30 min

@app.route("/api/performance/saldo/<agency>/<account_id>")
@login_required
def api_performance_saldo(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    token_fn = _META_TOKENS.get(agency)
    if not token_fn:
        return jsonify({"error": f"Agência '{agency}' não configurada"}), 500
    token = token_fn()
    if not token:
        return jsonify({"error": f"Token da agência '{agency}' não configurado"}), 500

    cache_key = f"saldo:{agency}:{account_id}"
    now = time.time()
    if cache_key in _perf_saldo_cache:
        cached = _perf_saldo_cache[cache_key]
        if now - cached["ts"] < _PERF_SALDO_TTL:
            return jsonify(cached["data"])

    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}",
            params={"fields": "amount_spent,balance,spend_cap,currency", "access_token": token},
            timeout=15,
        )
        if not r.ok:
            err = r.json().get("error", {})
            return jsonify({"error": err.get("message", f"Meta API {r.status_code}")}), 502
        data = r.json()
        amount_spent = float(data.get("amount_spent", 0) or 0) / 100
        balance      = float(data.get("balance", 0) or 0) / 100
        spend_cap    = float(data.get("spend_cap", 0) or 0) / 100
        remaining    = max(0.0, spend_cap - amount_spent) if spend_cap else balance
        result = {
            "amount_spent": round(amount_spent, 2),
            "balance":      round(balance, 2),
            "spend_cap":    round(spend_cap, 2),
            "remaining":    round(remaining, 2),
            "currency":     data.get("currency", "BRL"),
            "alerta":       remaining < 150.0,
        }
        _perf_saldo_cache[cache_key] = {"ts": now, "data": result}
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
```

- [ ] **Step 4: Rodar testes — devem passar**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_performance_api.py::test_saldo_retorna_campos_esperados tests/test_performance_api.py::test_saldo_alerta_true_quando_abaixo_150 tests/test_performance_api.py::test_saldo_alerta_false_quando_acima_150 tests/test_performance_api.py::test_saldo_account_id_invalido tests/test_performance_api.py::test_saldo_agencia_invalida -v
```
Esperado: 5 PASSED

- [ ] **Step 5: Commit**

```bash
cd /root && git add jake_desktop/app.py jake_desktop/tests/test_performance_api.py
git commit -m "feat: GET /api/performance/saldo com cache e alerta < R\$150"
```

---

## Task 2: Rota `/api/performance/alerta-saldo`

**Files:**
- Modify: `jake_desktop/app.py` (após a rota de saldo)
- Test: `jake_desktop/tests/test_performance_api.py`

- [ ] **Step 1: Adicionar testes de alerta**

Adicionar ao final de `test_performance_api.py`:

```python
# ── POST /api/performance/alerta-saldo ──────────────────────────────────────

def test_alerta_saldo_envia_telegram(client):
    with patch("app._send_telegram", return_value=(True, "Enviado")) as mock_tg:
        # Limpar cache de dedup
        import app as flask_app
        flask_app._alerta_sent_cache.clear()
        r = client.post("/api/performance/alerta-saldo",
                        json={"agency": "piloti", "account_id": "act_111", "nome": "TestClient", "saldo": 80.0})
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d.get("dedup") is not True
        mock_tg.assert_called_once()


def test_alerta_saldo_deduplica_dentro_de_1h(client):
    import app as flask_app, time as _t
    flask_app._alerta_sent_cache["act_222"] = _t.time()  # simula envio recente
    with patch("app._send_telegram") as mock_tg:
        r = client.post("/api/performance/alerta-saldo",
                        json={"agency": "piloti", "account_id": "act_222", "nome": "TestClient", "saldo": 80.0})
        assert r.status_code == 200
        d = r.get_json()
        assert d.get("dedup") is True
        mock_tg.assert_not_called()


def test_alerta_saldo_reenvia_apos_1h(client):
    import app as flask_app, time as _t
    flask_app._alerta_sent_cache["act_333"] = _t.time() - 3700  # 1h atrás
    with patch("app._send_telegram", return_value=(True, "Enviado")) as mock_tg:
        r = client.post("/api/performance/alerta-saldo",
                        json={"agency": "piloti", "account_id": "act_333", "nome": "TestClient", "saldo": 80.0})
        d = r.get_json()
        assert d.get("dedup") is not True
        mock_tg.assert_called_once()
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_performance_api.py::test_alerta_saldo_envia_telegram -v 2>&1 | tail -5
```
Esperado: FAILED — rota não existe.

- [ ] **Step 3: Adicionar rota no `app.py`** (logo após a rota de saldo)

```python
# ── API: Performance — Alerta de Saldo ─────────────────────────────────────

_alerta_sent_cache: dict = {}  # account_id -> timestamp último envio
_ALERTA_TTL = 3600  # 1 hora

@app.route("/api/performance/alerta-saldo", methods=["POST"])
@login_required
def api_performance_alerta_saldo():
    data       = request.get_json() or {}
    account_id = (data.get("account_id") or "").strip()
    nome       = (data.get("nome") or "conta").strip()
    agency     = (data.get("agency") or "").strip()
    saldo      = data.get("saldo", 0)

    now = time.time()
    last = _alerta_sent_cache.get(account_id, 0)
    if now - last < _ALERTA_TTL:
        return jsonify({"ok": True, "dedup": True})

    msg = f"⚠️ Patrão, saldo baixo em {nome} ({agency}): R$ {float(saldo):,.2f}"
    ok, detail = _send_telegram(msg)
    _alerta_sent_cache[account_id] = now
    return jsonify({"ok": ok, "detail": detail})
```

- [ ] **Step 4: Rodar testes de alerta**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_performance_api.py::test_alerta_saldo_envia_telegram tests/test_performance_api.py::test_alerta_saldo_deduplica_dentro_de_1h tests/test_performance_api.py::test_alerta_saldo_reenvia_apos_1h -v
```
Esperado: 3 PASSED

- [ ] **Step 5: Commit**

```bash
cd /root && git add jake_desktop/app.py jake_desktop/tests/test_performance_api.py
git commit -m "feat: POST /api/performance/alerta-saldo com deduplicação 1h"
```

---

## Task 3: Rota `/api/performance/semana-anterior`

**Files:**
- Modify: `jake_desktop/app.py`
- Test: `jake_desktop/tests/test_performance_api.py`

- [ ] **Step 1: Adicionar testes**

```python
# ── GET /api/performance/semana-anterior ────────────────────────────────────

def _mock_insights_resp(spend="320.00", messaging=27):
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = {"data": [{
        "spend": spend,
        "impressions": "50000",
        "clicks": "800",
        "reach": "18000",
        "cpm": "6.40",
        "ctr": "1.60",
        "frequency": "2.78",
        "actions": [{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": str(messaging)}],
        "cost_per_action_type": [{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": str(float(spend)/messaging)}],
    }]}
    return resp


def test_semana_anterior_retorna_atual_e_anterior(client):
    with patch("app.requests.get", return_value=_mock_insights_resp()):
        r = client.get("/api/performance/semana-anterior/piloti/act_123456789")
        assert r.status_code == 200
        d = r.get_json()
        assert "atual" in d
        assert "anterior" in d
        assert "spend" in d["atual"]
        assert "spend" in d["anterior"]


def test_semana_anterior_account_id_invalido(client):
    r = client.get("/api/performance/semana-anterior/piloti/invalido")
    assert r.status_code == 400
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_performance_api.py::test_semana_anterior_retorna_atual_e_anterior -v 2>&1 | tail -5
```

- [ ] **Step 3: Adicionar helper e rota no `app.py`**

Logo após a rota de alerta-saldo:

```python
# ── API: Performance — Semana Anterior ─────────────────────────────────────

def _extract_insights_row(row: dict) -> dict:
    """Extrai métricas de uma linha de insights da Meta API."""
    actions = row.get("actions") or []
    costs   = row.get("cost_per_action_type") or []

    def _fa(arr, *types):
        for entry in (arr or []):
            if entry.get("action_type") in types:
                try: return float(entry.get("value", 0) or 0)
                except: return 0.0
        return 0.0

    leads     = int(_fa(actions, "lead"))
    messaging = int(_fa(actions,
        "onsite_conversion.messaging_conversation_started_7d",
        "onsite_conversion.messaging_conversation_started"))
    purchases = int(_fa(actions, "purchase", "omni_purchase"))
    profile_visits = int(_fa(actions, "instagram_profile_visit"))
    spend     = float(row.get("spend", 0) or 0)

    return {
        "spend":          round(spend, 2),
        "impressions":    int(row.get("impressions", 0) or 0),
        "clicks":         int(row.get("clicks", 0) or 0),
        "reach":          int(row.get("reach", 0) or 0),
        "cpm":            row.get("cpm", "0.00"),
        "ctr":            row.get("ctr", "0.00"),
        "frequency":      row.get("frequency", "1.00"),
        "leads":          leads,
        "messaging":      messaging,
        "purchases":      purchases,
        "profile_visits": profile_visits,
    }


def _fetch_meta_period(account_id: str, token: str, since: str, until: str) -> dict:
    """Busca insights de um período específico (since/until em YYYY-MM-DD)."""
    r = requests.get(
        f"https://graph.facebook.com/v21.0/{account_id}/insights",
        params={
            "fields": "spend,impressions,clicks,reach,cpm,ctr,frequency,actions,cost_per_action_type",
            "time_range": '{"since":"' + since + '","until":"' + until + '"}',
            "access_token": token,
        },
        timeout=15,
    )
    if not r.ok:
        return {}
    data = r.json().get("data", [])
    if not data:
        return {"spend": 0, "impressions": 0, "clicks": 0, "reach": 0,
                "leads": 0, "messaging": 0, "purchases": 0, "profile_visits": 0}
    return _extract_insights_row(data[0])


@app.route("/api/performance/semana-anterior/<agency>/<account_id>")
@login_required
def api_performance_semana_anterior(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    token_fn = _META_TOKENS.get(agency)
    if not token_fn:
        return jsonify({"error": f"Agência '{agency}' não configurada"}), 500
    token = token_fn()
    if not token:
        return jsonify({"error": f"Token não configurado"}), 500

    from datetime import date, timedelta
    today     = date.today()
    # Semana atual: últimos 7 dias (hoje-6 até hoje)
    since_atual     = (today - timedelta(days=6)).isoformat()
    until_atual     = today.isoformat()
    # Semana anterior: 7 dias antes disso
    since_anterior  = (today - timedelta(days=13)).isoformat()
    until_anterior  = (today - timedelta(days=7)).isoformat()

    try:
        atual    = _fetch_meta_period(account_id, token, since_atual, until_atual)
        anterior = _fetch_meta_period(account_id, token, since_anterior, until_anterior)
        return jsonify({"atual": atual, "anterior": anterior})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
```

- [ ] **Step 4: Rodar testes**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_performance_api.py::test_semana_anterior_retorna_atual_e_anterior tests/test_performance_api.py::test_semana_anterior_account_id_invalido -v
```
Esperado: 2 PASSED

- [ ] **Step 5: Commit**

```bash
cd /root && git add jake_desktop/app.py jake_desktop/tests/test_performance_api.py
git commit -m "feat: GET /api/performance/semana-anterior com períodos explícitos"
```

---

## Task 4: Enriquecer `/api/relatorios/analise` com vault + delta

**Files:**
- Modify: `jake_desktop/app.py` (função `api_relatorios_analise`, ~linha 765)
- Test: `jake_desktop/tests/test_performance_api.py`

- [ ] **Step 1: Adicionar testes**

```python
# ── /api/relatorios/analise enriquecida ─────────────────────────────────────

def test_analise_aceita_delta_no_payload(client):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="Boa performance esta semana.")]
    with patch("app._anthropic_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_client_fn.return_value = mock_client
        with patch("os.path.isdir", return_value=False):
            r = client.post("/api/relatorios/analise", json={
                "nome": "HiperClin",
                "metricas": {"Gasto": "R$ 320,00", "Leads": 27},
                "metricas_anterior": {"Gasto": "R$ 290,00", "Leads": 22},
                "delta": {"Gasto": "+10,3%", "Leads": "+22,7%"},
            })
            assert r.status_code == 200
            d = r.get_json()
            assert "analise" in d
            assert len(d["analise"]) > 0
            # Verificar que delta foi injetado no prompt
            call_args = mock_client.messages.create.call_args
            prompt_text = call_args[1]["messages"][0]["content"]
            assert "anterior" in prompt_text.lower() or "delta" in prompt_text.lower() or "variação" in prompt_text.lower()


def test_analise_salva_snapshot_no_vault(client):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="Análise gerada.")]
    with patch("app._anthropic_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_client_fn.return_value = mock_client
        with patch("os.path.isdir", return_value=False), \
             patch("os.makedirs") as mock_mkdir, \
             patch("builtins.open", mock_open()) as mock_file:
            r = client.post("/api/relatorios/analise", json={
                "nome": "HiperClin",
                "metricas": {"Gasto": "R$ 320,00"},
                "metricas_anterior": {"Gasto": "R$ 290,00"},
                "delta": {"Gasto": "+10,3%"},
            })
            assert r.status_code == 200
            mock_mkdir.assert_called()
            mock_file.assert_called()
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_performance_api.py::test_analise_aceita_delta_no_payload -v 2>&1 | tail -10
```

- [ ] **Step 3: Modificar `api_relatorios_analise` no `app.py`**

Substituir a função existente (linhas ~765-793):

```python
# ── helpers vault ──────────────────────────────────────────────────────────

import unicodedata as _unicodedata

def _slug(name: str) -> str:
    n = _unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if _unicodedata.category(c) != "Mn")
    return _re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")

_VAULT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jake-brain", "Clientes")

def _vault_ler_contexto(nome: str) -> str:
    """Lê o .md mais recente de jake-brain/Clientes/<slug>/Performance/"""
    slug = _slug(nome)
    pasta = os.path.join(_VAULT_ROOT, slug, "Performance")
    if not os.path.isdir(pasta):
        return ""
    arquivos = sorted([f for f in os.listdir(pasta) if f.endswith(".md")], reverse=True)
    if not arquivos:
        return ""
    try:
        with open(os.path.join(pasta, arquivos[0]), encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def _vault_salvar_snapshot(nome: str, metricas: dict, metricas_anterior: dict, delta: dict, analise: str):
    """Salva snapshot semanal em jake-brain/Clientes/<slug>/Performance/YYYY-WXX.md"""
    from datetime import date
    slug  = _slug(nome)
    pasta = os.path.join(_VAULT_ROOT, slug, "Performance")
    os.makedirs(pasta, exist_ok=True)
    hoje   = date.today()
    semana = hoje.strftime("%Y-W%W")
    path   = os.path.join(pasta, f"{semana}.md")
    linhas_met = "\n".join(f"| {k} | {v} | {metricas_anterior.get(k,'--')} | {delta.get(k,'--')} |"
                           for k, v in metricas.items())
    conteudo = f"""# Performance — {nome} — {semana}

**Data de análise:** {hoje.isoformat()}

## Métricas
| Métrica | Atual | Anterior | Delta |
|---|---|---|---|
{linhas_met}

## Análise IA
{analise}
"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(conteudo)
    except Exception as e:
        print(f"[Jake vault] erro ao salvar snapshot: {e}")


@app.route("/api/relatorios/analise", methods=["POST"])
@login_required
def api_relatorios_analise():
    data             = request.get_json() or {}
    nome             = (data.get("nome") or "").strip()
    metricas         = data.get("metricas") or {}
    metricas_anterior = data.get("metricas_anterior") or {}
    delta            = data.get("delta") or {}

    client = _anthropic_client()
    if not client:
        return jsonify({"analise": ""})

    metricas_str = "\n".join(f"- {k}: {v}" for k, v in metricas.items())

    # Contexto histórico do vault
    contexto_vault = _vault_ler_contexto(nome)
    bloco_vault = (
        f"\n\nContexto histórico do cliente (semanas anteriores):\n{contexto_vault[:800]}"
        if contexto_vault else ""
    )

    # Comparação com semana anterior
    bloco_anterior = ""
    if metricas_anterior:
        ant_str   = "\n".join(f"- {k}: {v}" for k, v in metricas_anterior.items())
        delta_str = "\n".join(f"- {k}: {v}" for k, v in delta.items()) if delta else ""
        bloco_anterior = (
            f"\n\nSemana anterior:\n{ant_str}"
            + (f"\n\nVariação (atual vs anterior):\n{delta_str}" if delta_str else "")
        )

    prompt = (
        f"Você é analista de tráfego pago. Gere uma análise BREVE (2-3 frases, máximo 140 palavras) "
        f"sobre os resultados das campanhas Meta Ads de '{nome}' nos últimos 7 dias.\n\n"
        f"Dados atuais:\n{metricas_str}"
        f"{bloco_anterior}"
        f"{bloco_vault}\n\n"
        f"Seja direto, profissional, em português brasileiro. "
        f"Destaque o principal resultado, compare com semana anterior se disponível, e dê UMA recomendação prática. "
        f"NÃO use markdown, asteriscos, negrito ou formatação. Apenas texto corrido simples."
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        analise = (msg.content[0].text or "").strip()
        # Salvar snapshot no vault
        if metricas:
            _vault_salvar_snapshot(nome, metricas, metricas_anterior, delta, analise)
        return jsonify({"analise": analise})
    except Exception as exc:
        return jsonify({"analise": "", "error": str(exc)})
```

- [ ] **Step 4: Rodar todos os testes de performance**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_performance_api.py -v
```
Esperado: todos PASSED

- [ ] **Step 5: Commit**

```bash
cd /root && git add jake_desktop/app.py jake_desktop/tests/test_performance_api.py
git commit -m "feat: enriquece /api/relatorios/analise com vault Obsidian e comparação semanal"
```

---

## Task 5: HTML da página de performance

**Files:**
- Modify: `jake_desktop/templates/dashboard.html` (linhas 301-313)

- [ ] **Step 1: Substituir placeholder pelo HTML real**

No `dashboard.html`, substituir o bloco entre as linhas 301 e 313:

```html
      <!-- 2. ANÁLISE DE PERFORMANCE ───────────────────── -->
      <section class="page" id="page-performance">
        <div class="placeholder-page">
          <div class="placeholder-icon">◈</div>
          <h2 class="placeholder-title">Análise de Performance</h2>
          <p class="placeholder-sub">Em desenvolvimento — em breve aqui você terá gasto, CPL, ROAS e CPA por cliente.</p>
          <div class="placeholder-grid">
            <div class="ph-card"><span>Gasto Total</span><b>-- R$</b></div>
            <div class="ph-card"><span>CPL</span><b>-- R$</b></div>
            <div class="ph-card"><span>ROAS</span><b>--x</b></div>
            <div class="ph-card"><span>CPA</span><b>-- R$</b></div>
          </div>
        </div>
      </section>
```

Por:

```html
      <!-- 2. ANÁLISE DE PERFORMANCE ───────────────────── -->
      <section class="page" id="page-performance">
        <div class="perf-wrap">

          <!-- Tabs agência -->
          <div class="rel-tabs" style="margin-bottom:1.5rem;">
            <button class="rel-tab active" data-agency="piloti">Piloti</button>
            <button class="rel-tab" data-agency="dentto">Dentto</button>
          </div>

          <!-- Cards globais -->
          <div class="perf-cards" id="perf-cards">
            <div class="perf-card">
              <span class="perf-card-label">Gasto Total</span>
              <b class="perf-card-val" id="perf-total-gasto">--</b>
            </div>
            <div class="perf-card" id="perf-card-saldo">
              <span class="perf-card-label">Saldo (menor)</span>
              <b class="perf-card-val" id="perf-total-saldo">--</b>
            </div>
            <div class="perf-card">
              <span class="perf-card-label">CPL Médio</span>
              <b class="perf-card-val" id="perf-total-cpl">--</b>
            </div>
            <div class="perf-card">
              <span class="perf-card-label">Leads / Msgs</span>
              <b class="perf-card-val" id="perf-total-leads">--</b>
            </div>
          </div>

          <!-- Tabela de clientes -->
          <div class="rel-table-wrap" style="margin-top:1.5rem;">
            <table class="rel-table" style="width:100%;">
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>Gasto</th>
                  <th>Saldo</th>
                  <th>Leads / Msgs</th>
                  <th>CPL</th>
                  <th></th>
                </tr>
              </thead>
              <tbody id="perf-tbody"></tbody>
            </table>
          </div>
        </div>

        <!-- Toast -->
        <div id="perf-toast" class="rel-toast"></div>

        <!-- Drawer de detalhe -->
        <div id="perf-drawer-overlay" class="perf-drawer-overlay" style="display:none;">
          <div class="perf-drawer" id="perf-drawer">
            <div class="perf-drawer-header">
              <span id="perf-drawer-title">Cliente</span>
              <button id="perf-drawer-close" class="perf-drawer-close">✕</button>
            </div>
            <div id="perf-drawer-body" class="perf-drawer-body">
              <div class="perf-drawer-loading">Carregando dados...</div>
            </div>
          </div>
        </div>
      </section>
```

- [ ] **Step 2: Adicionar tag do script e CSS inline**

No final do `dashboard.html`, antes de `</body>`, adicionar após a linha do `relatorios.js`:

```html
  <script src="{{ url_for('static', filename='js/performance.js') }}"></script>
```

Também adicionar estilos do drawer/cards antes do `</head>` ou em bloco `<style>` no final do body (antes dos scripts):

```html
  <style>
    .perf-wrap { padding: 0 0.5rem; }
    .perf-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
    @media (max-width: 700px) { .perf-cards { grid-template-columns: repeat(2, 1fr); } }
    .perf-card { background: rgba(0,212,255,.06); border: 1px solid rgba(0,212,255,.15); border-radius: 10px; padding: 1rem 1.2rem; display:flex; flex-direction:column; gap:.4rem; }
    .perf-card-label { font-size: .75rem; color: rgba(176,190,197,.6); text-transform: uppercase; letter-spacing:.06em; }
    .perf-card-val { font-size: 1.4rem; color: #e0f7fa; }
    .perf-card.alerta { border-color: rgba(255,80,80,.5); background: rgba(255,80,80,.07); }
    .perf-card.alerta .perf-card-val { color: #ff6b6b; }
    .perf-badge-alerta { color: #ff6b6b; font-size: .8rem; margin-left: .3rem; }
    /* Drawer */
    .perf-drawer-overlay { position:fixed; inset:0; background:rgba(0,0,0,.55); z-index:200; display:flex; align-items:flex-end; justify-content:flex-end; }
    .perf-drawer { background:#0d1b2a; border-left:1px solid rgba(0,212,255,.2); width:420px; max-width:100vw; height:100vh; overflow-y:auto; padding:1.5rem; display:flex; flex-direction:column; gap:1rem; }
    .perf-drawer-header { display:flex; justify-content:space-between; align-items:center; }
    .perf-drawer-header span { font-size:1.1rem; color:#e0f7fa; font-weight:600; }
    .perf-drawer-close { background:none; border:none; color:rgba(176,190,197,.6); font-size:1.2rem; cursor:pointer; }
    .perf-drawer-loading { color:rgba(176,190,197,.5); font-size:.9rem; }
    .perf-comparativo { width:100%; border-collapse:collapse; font-size:.85rem; }
    .perf-comparativo th { color:rgba(176,190,197,.5); font-weight:500; padding:.4rem .6rem; text-align:left; border-bottom:1px solid rgba(255,255,255,.07); }
    .perf-comparativo td { padding:.4rem .6rem; color:#cfd8dc; border-bottom:1px solid rgba(255,255,255,.04); }
    .perf-delta-pos { color:#4ade80; }
    .perf-delta-neg { color:#f87171; }
    .perf-analise-box { background:rgba(0,212,255,.05); border:1px solid rgba(0,212,255,.12); border-radius:8px; padding:1rem; font-size:.88rem; color:#b0bec5; line-height:1.6; }
    .perf-btn-ia { background:linear-gradient(135deg,rgba(0,212,255,.15),rgba(0,212,255,.05)); border:1px solid rgba(0,212,255,.3); color:#e0f7fa; padding:.6rem 1.2rem; border-radius:8px; cursor:pointer; font-size:.85rem; width:100%; }
    .perf-btn-ia:hover { background:rgba(0,212,255,.2); }
    .perf-btn-ia:disabled { opacity:.5; cursor:default; }
  </style>
```

- [ ] **Step 3: Verificar HTML no browser**

```bash
# Verificar que o Jake OS sobe sem erro de template
cd /root/jake_desktop && /root/venv/bin/python -c "import app; print('OK')"
```
Esperado: `OK` sem exceção.

- [ ] **Step 4: Commit**

```bash
cd /root && git add jake_desktop/templates/dashboard.html
git commit -m "feat: HTML da página Análise de Performance com drawer e cards"
```

---

## Task 6: Frontend `performance.js`

**Files:**
- Create: `jake_desktop/static/js/performance.js`

- [ ] **Step 1: Criar o arquivo completo**

Criar `jake_desktop/static/js/performance.js`:

```javascript
/* ══════════════════════════════════════════════════════
   Jake OS — Módulo: Análise de Performance
   Dashboard por agência + drill-down por cliente + alertas
══════════════════════════════════════════════════════ */
(function () {

  /* ── Config de clientes (espelho do relatorios.js) ── */
  var AGENCIES = {
    piloti: [
      { id: "act_712297048202295",  name: "61 eventos"       },
      { id: "act_2162454744176337", name: "Amanda"           },
      { id: "act_1006820257491698", name: "Calixta"          },
      { id: "act_1095710212746155", name: "Daniele Taveira"  },
      { id: "act_5684689948235819", name: "HiperClin"        },
      { id: "act_1006436427517079", name: "IOB"              },
      { id: "act_126503999415274",  name: "Isac Academia"    },
      { id: "act_812220691454430",  name: "Maíra Castaldi"   },
      { id: "act_1693935704869895", name: "Marcus"           },
      { id: "act_507545471090485",  name: "Odonto Uberaba"   },
      { id: "act_323137203122197",  name: "Queen Poltronas"  },
      { id: "act_840594572249284",  name: "RD Contabilidade" },
      { id: "act_7838846752907408", name: "Realize Sorrisos" },
      { id: "act_510054631964792",  name: "RunWay"           }
    ],
    dentto: []
  };

  var currentAgency = "piloti";
  var _rowData = {};  // account_id -> {insights, saldo}

  /* ── Helpers de formatação ───────────────────────── */
  function brl(v)  { return "R$ " + parseFloat(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function fmtN(n) { return parseInt(n || 0, 10).toLocaleString("pt-BR"); }
  function custo(spend, count) {
    return (count && count > 0) ? brl(parseFloat(spend) / count) : "R$ 0,00";
  }
  function esc(s) {
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  /* ── Métrica principal do cliente ───────────────── */
  function metricaPrincipal(d) {
    var s = parseFloat(d.spend || 0);
    if (d.messaging > 0) return { label: "Msgs", val: d.messaging, cpl: custo(s, d.messaging) };
    if (d.leads > 0)     return { label: "Leads", val: d.leads,    cpl: custo(s, d.leads) };
    if (d.profile_visits > 0) return { label: "Visitas", val: d.profile_visits, cpl: custo(s, d.profile_visits) };
    return { label: "Cliques", val: d.clicks || 0, cpl: custo(s, d.clicks) };
  }

  /* ── Fetch insights (rota existente) ────────────── */
  function fetchInsights(agency, id, cb) {
    fetch("/api/relatorios/insights/" + agency + "/" + id)
      .then(function(r) { return r.json(); })
      .then(function(d) { cb(null, d); })
      .catch(function(e) { cb(e.message || "Erro", null); });
  }

  /* ── Fetch saldo (nova rota) ─────────────────────── */
  function fetchSaldo(agency, id, cb) {
    fetch("/api/performance/saldo/" + agency + "/" + id)
      .then(function(r) { return r.json(); })
      .then(function(d) { cb(null, d); })
      .catch(function(e) { cb(e.message || "Erro", null); });
  }

  /* ── Alerta Telegram (deduplicado por localStorage) */
  var _ALERTA_TTL = 3600000; // 1h em ms
  function dispararAlertaSaldo(agency, id, nome, saldo) {
    var lsKey = "perf_alerta_" + id;
    var ultimo = parseInt(localStorage.getItem(lsKey) || "0", 10);
    if (Date.now() - ultimo < _ALERTA_TTL) return;
    fetch("/api/performance/alerta-saldo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agency: agency, account_id: id, nome: nome, saldo: saldo })
    }).then(function(r) { return r.json(); })
      .then(function(d) { if (!d.dedup) localStorage.setItem(lsKey, Date.now()); })
      .catch(function() {});
  }

  /* ── Construir linha da tabela ───────────────────── */
  function buildRow(client) {
    var tr = document.createElement("tr");
    tr.dataset.id = client.id;
    tr.innerHTML =
      '<td>' + esc(client.name) + '</td>' +
      '<td class="perf-td-gasto"><span class="rel-week-loading"><span class="rel-week-spinner"></span> ...</span></td>' +
      '<td class="perf-td-saldo"><span class="rel-week-loading"><span class="rel-week-spinner"></span> ...</span></td>' +
      '<td class="perf-td-leads">--</td>' +
      '<td class="perf-td-cpl">--</td>' +
      '<td><button class="rel-btn-copy perf-btn-detail" data-id="' + esc(client.id) + '" title="Ver detalhe">›</button></td>';
    return tr;
  }

  /* ── Atualizar linha com dados ───────────────────── */
  function updateRow(agency, client, insights, saldo) {
    var tbody = document.getElementById("perf-tbody");
    if (!tbody) return;
    var tr = tbody.querySelector("tr[data-id='" + client.id + "']");
    if (!tr) return;

    var s = parseFloat((insights || {}).spend || 0);
    var m = insights ? metricaPrincipal(insights) : null;
    var saldoVal = saldo ? saldo.remaining : null;
    var alerta = saldo && saldo.alerta;

    // Gasto
    tr.querySelector(".perf-td-gasto").innerHTML = insights
      ? (s > 0 ? '<span>' + brl(s) + '</span>' : '<span style="opacity:.4">Sem gasto</span>')
      : '<span class="rel-week-error">⚠</span>';

    // Saldo
    if (saldo && saldo.error) {
      tr.querySelector(".perf-td-saldo").innerHTML = '<span style="opacity:.4">--</span>';
    } else if (saldo) {
      var badge = alerta ? ' <span class="perf-badge-alerta">⚠</span>' : '';
      tr.querySelector(".perf-td-saldo").innerHTML = brl(saldoVal) + badge;
      if (alerta) dispararAlertaSaldo(agency, client.id, client.name, saldoVal);
    }

    // Leads / CPL
    if (m) {
      tr.querySelector(".perf-td-leads").textContent = m.label + ": " + fmtN(m.val);
      tr.querySelector(".perf-td-cpl").textContent   = m.cpl;
    }
  }

  /* ── Atualizar cards globais ─────────────────────── */
  function updateGlobalCards(agency) {
    var list = AGENCIES[agency] || [];
    var totalGasto = 0, totalLeads = 0, cpls = [], menorSaldo = Infinity, temAlerta = false;

    list.forEach(function(c) {
      var d = _rowData[c.id];
      if (!d) return;
      var ins = d.insights, sal = d.saldo;
      if (ins) {
        totalGasto += parseFloat(ins.spend || 0);
        var m = metricaPrincipal(ins);
        totalLeads += parseInt(m.val || 0, 10);
        var s = parseFloat(ins.spend || 0);
        if (m.val > 0) cpls.push(s / m.val);
      }
      if (sal && !sal.error && sal.remaining !== undefined) {
        if (sal.remaining < menorSaldo) menorSaldo = sal.remaining;
        if (sal.alerta) temAlerta = true;
      }
    });

    var cplMedio = cpls.length ? cpls.reduce(function(a,b){return a+b;}, 0) / cpls.length : 0;

    var el = function(id) { return document.getElementById(id); };
    if (el("perf-total-gasto")) el("perf-total-gasto").textContent = brl(totalGasto);
    if (el("perf-total-leads")) el("perf-total-leads").textContent = fmtN(totalLeads);
    if (el("perf-total-cpl"))   el("perf-total-cpl").textContent   = cplMedio > 0 ? brl(cplMedio) : "--";
    if (el("perf-total-saldo")) {
      el("perf-total-saldo").textContent = menorSaldo < Infinity ? brl(menorSaldo) : "--";
    }
    var cardSaldo = document.getElementById("perf-card-saldo");
    if (cardSaldo) {
      cardSaldo.classList.toggle("alerta", temAlerta);
    }
  }

  /* ── Renderizar tabela ───────────────────────────── */
  function renderTable(agency) {
    var tbody = document.getElementById("perf-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    _rowData = {};
    var list = AGENCIES[agency] || [];
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:2.5rem;color:rgba(176,190,197,.3);">Nenhum cliente cadastrado</td></tr>';
      return;
    }
    list.forEach(function(c) { tbody.appendChild(buildRow(c)); });

    // Fetch paralelo: insights + saldo
    list.forEach(function(c) {
      _rowData[c.id] = {};
      fetchInsights(agency, c.id, function(err, ins) {
        _rowData[c.id].insights = err ? null : ins;
        fetchSaldo(agency, c.id, function(errS, sal) {
          _rowData[c.id].saldo = errS ? {error: errS} : sal;
          updateRow(agency, c, _rowData[c.id].insights, _rowData[c.id].saldo);
          updateGlobalCards(agency);
        });
      });
    });
  }

  /* ── Drawer de detalhe ───────────────────────────── */
  function openDrawer(agency, clientId) {
    var client = (AGENCIES[agency] || []).filter(function(c){return c.id===clientId;})[0];
    if (!client) return;
    var overlay = document.getElementById("perf-drawer-overlay");
    var title   = document.getElementById("perf-drawer-title");
    var body    = document.getElementById("perf-drawer-body");
    if (!overlay) return;
    title.textContent = client.name;
    body.innerHTML = '<div class="perf-drawer-loading">Carregando comparativo semanal...</div>';
    overlay.style.display = "flex";

    fetch("/api/performance/semana-anterior/" + agency + "/" + clientId)
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.error) { body.innerHTML = '<p style="color:#f87171;">Erro: ' + esc(d.error) + '</p>'; return; }
        renderDrawerContent(client, d.atual, d.anterior, body);
      })
      .catch(function(e) { body.innerHTML = '<p style="color:#f87171;">Erro de rede</p>'; });
  }

  function delta(atual, anterior) {
    if (!anterior || anterior === 0) return null;
    var pct = ((atual - anterior) / anterior) * 100;
    return pct;
  }

  function fmtDelta(pct) {
    if (pct === null) return '<span style="opacity:.4">--</span>';
    var sinal = pct >= 0 ? "+" : "";
    var cls   = pct >= 0 ? "perf-delta-pos" : "perf-delta-neg";
    return '<span class="' + cls + '">' + sinal + pct.toFixed(1) + '%</span>';
  }

  function renderDrawerContent(client, atual, anterior, body) {
    var sa = parseFloat(atual.spend || 0);
    var sb = parseFloat(anterior.spend || 0);
    var ma = metricaPrincipal(atual);
    var mb = metricaPrincipal(anterior);
    var cplA = ma.val > 0 ? sa / ma.val : 0;
    var cplB = mb.val > 0 ? sb / mb.val : 0;

    var linhas = [
      ["Gasto",        brl(sa),         brl(sb),          delta(sa, sb)],
      [ma.label,       fmtN(ma.val),    fmtN(mb.val),     delta(ma.val, mb.val)],
      ["CPL",          brl(cplA),       brl(cplB),        delta(cplA, cplB) !== null ? -delta(cplA, cplB) : null],
      ["Alcance",      fmtN(atual.reach), fmtN(anterior.reach), delta(atual.reach, anterior.reach)],
      ["Cliques",      fmtN(atual.clicks), fmtN(anterior.clicks), delta(atual.clicks, anterior.clicks)],
      ["CTR",          (atual.ctr||"0") + "%", (anterior.ctr||"0") + "%", null],
    ];

    // Montar payload de delta para o backend
    var metricasObj  = {};
    var anteriorObj  = {};
    var deltaObj     = {};
    linhas.forEach(function(l) {
      metricasObj[l[0]] = l[1];
      anteriorObj[l[0]] = l[2];
      if (l[3] !== null) {
        var sinal = l[3] >= 0 ? "+" : "";
        deltaObj[l[0]] = sinal + l[3].toFixed(1) + "%";
      }
    });

    var rows = linhas.map(function(l) {
      return '<tr><td>' + esc(l[0]) + '</td><td>' + l[1] + '</td><td>' + l[2] + '</td><td>' + fmtDelta(l[3]) + '</td></tr>';
    }).join("");

    body.innerHTML =
      '<table class="perf-comparativo">' +
        '<thead><tr><th>Métrica</th><th>Esta semana</th><th>Semana anterior</th><th>Δ</th></tr></thead>' +
        '<tbody>' + rows + '</tbody>' +
      '</table>' +
      '<button class="perf-btn-ia" id="perf-btn-ia" style="margin-top:1.2rem;">Analisar com IA</button>' +
      '<div id="perf-analise-result" style="margin-top:.8rem;"></div>';

    document.getElementById("perf-btn-ia").addEventListener("click", function() {
      var btn = this;
      btn.disabled = true;
      btn.textContent = "Analisando...";
      fetch("/api/relatorios/analise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nome: client.name,
          metricas: metricasObj,
          metricas_anterior: anteriorObj,
          delta: deltaObj
        })
      }).then(function(r) { return r.json(); })
        .then(function(d) {
          var res = document.getElementById("perf-analise-result");
          if (!res) return;
          if (d.analise) {
            res.innerHTML = '<div class="perf-analise-box">' + esc(d.analise) + '</div>';
          } else {
            res.innerHTML = '<p style="color:#f87171;font-size:.85rem;">Erro ao gerar análise.</p>';
          }
          btn.textContent = "Analisar com IA";
          btn.disabled = false;
        })
        .catch(function() {
          btn.textContent = "Analisar com IA";
          btn.disabled = false;
        });
    });
  }

  /* ── Init ────────────────────────────────────────── */
  function init() {
    var perfSection = document.getElementById("page-performance");
    if (!perfSection) return;

    renderTable(currentAgency);

    // Tabs
    perfSection.querySelectorAll(".rel-tab").forEach(function(tab) {
      tab.addEventListener("click", function() {
        perfSection.querySelectorAll(".rel-tab").forEach(function(t) { t.classList.remove("active"); });
        tab.classList.add("active");
        currentAgency = tab.dataset.agency;
        renderTable(currentAgency);
      });
    });

    // Clique na tabela (detalhe ou futuro)
    var tbody = document.getElementById("perf-tbody");
    if (tbody) {
      tbody.addEventListener("click", function(e) {
        var btn = e.target.closest(".perf-btn-detail");
        if (btn) openDrawer(currentAgency, btn.dataset.id);
      });
    }

    // Fechar drawer
    var closeBtn = document.getElementById("perf-drawer-close");
    var overlay  = document.getElementById("perf-drawer-overlay");
    if (closeBtn) closeBtn.addEventListener("click", function() { overlay.style.display = "none"; });
    if (overlay)  overlay.addEventListener("click", function(e) {
      if (e.target === overlay) overlay.style.display = "none";
    });
  }

  // Rodar init quando a página de performance for ativada (SPA)
  // NOTA: showPage() é local no IIFE de app.js — não exposta em window.
  // Usamos MutationObserver para detectar quando #page-performance recebe a classe "active".
  document.addEventListener("DOMContentLoaded", function() {
    var perfPage = document.getElementById("page-performance");
    if (!perfPage) return;
    // init imediato se já ativa (ex: hash direto na URL)
    if (perfPage.classList.contains("active")) init();
    // Observar quando app.js adiciona classe "active" à seção
    new MutationObserver(function() {
      if (perfPage.classList.contains("active")) init();
    }).observe(perfPage, { attributes: true, attributeFilter: ["class"] });
  });

})();
```

- [ ] **Step 2: Verificar que não há erro de sintaxe**

```bash
node --check /root/jake_desktop/static/js/performance.js 2>&1 || echo "SEM NODE — verificar manualmente"
```

- [ ] **Step 3: Rodar todos os testes**

```bash
cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_performance_api.py -v
```
Esperado: todos PASSED

- [ ] **Step 4: Commit final**

```bash
cd /root && git add jake_desktop/static/js/performance.js jake_desktop/templates/dashboard.html
git commit -m "feat: performance.js — dashboard completo com alertas, drawer e análise IA"
```

---

## Task 7: Smoke test no browser

- [ ] **Step 1: Reiniciar Jake OS**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/venv/bin/python app.py > /tmp/jakeos.log 2>&1 &
sleep 2 && tail -5 /tmp/jakeos.log
```
Esperado: `* Running on http://0.0.0.0:5050`

- [ ] **Step 2: Verificar rotas respondem**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/api/performance/saldo/piloti/act_712297048202295 \
  -b "session=..." 2>/dev/null || echo "Sem cookie — testar no browser"
```

- [ ] **Step 3: Checar logs por erros**

```bash
tail -20 /tmp/jakeos.log
```
Esperado: nenhum `Traceback` ou `ImportError`

- [ ] **Step 4: Commit de encerramento**

```bash
cd /root && git add -A
git status  # confirmar que só arquivos esperados estão staged
git commit -m "feat: módulo Análise de Performance — Fase 1 completa" --allow-empty-message || true
```
