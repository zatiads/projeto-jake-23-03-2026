# Módulo de Inglês — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar seção `#ingles` ao Jake OS com Palavra do Dia, conversa com IA e painel de progresso.

**Architecture:** Nova seção SPA no Jake OS seguindo o padrão existente (section HTML + JS isolado + CSS inline + rotas Flask). Banco Neon com 3 tabelas novas. Claude gera palavras e responde nas conversas; OpenAI TTS produz áudio da pronúncia.

**Tech Stack:** Flask (Python), psycopg2 (Neon/PostgreSQL), Anthropic SDK (claude-sonnet-4-6), OpenAI SDK (tts-1/onyx), JavaScript ES5 vanilla, HTML/CSS inline

**Spec:** `docs/superpowers/specs/2026-06-01-modulo-ingles-design.md`

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `jake_desktop/app.py` | Modificar | Função `_init_ingles_tables()` + 7 rotas novas + registro no startup |
| `jake_desktop/templates/dashboard.html` | Modificar | Nav-item sidebar + `<section id="page-ingles">` + CSS inline |
| `jake_desktop/static/js/ingles.js` | Criar | Toda a lógica de UI do módulo (estado, fetch, render) |
| `jake_desktop/static/js/app.js` | Modificar | Registrar `"ingles"` como página válida + callback `initIngles` |
| `jake_desktop/tests/test_ingles_api.py` | Criar | Testes TDD para as 7 rotas |

---

## Task 1: Tabelas do banco de dados

**Files:**
- Modify: `jake_desktop/app.py` (após linha ~270, antes de `_init_dr_tables`)
- Modify: `jake_desktop/app.py:8744` (startup sequence)

- [ ] **Escrever o teste que verifica a criação das tabelas**

```python
# jake_desktop/tests/test_ingles_api.py
import sys, pytest
sys.path.insert(0, '/root/jake_desktop')
from unittest.mock import MagicMock, patch, call


def _mock_conn(rows=None, one=None):
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    if rows is not None:
        cur.fetchall.return_value = rows
    if one is not None:
        cur.fetchone.return_value = one
    return conn


def test_init_ingles_tables_cria_tabelas():
    """_init_ingles_tables() deve executar CREATE TABLE IF NOT EXISTS para as 3 tabelas."""
    conn = _mock_conn()
    with patch("app._get_db", return_value=conn):
        import app
        app._init_ingles_tables()
    sql_calls = " ".join(str(c) for c in conn.cursor().execute.call_args_list)
    assert "ingles_palavras" in sql_calls
    assert "ingles_sessoes" in sql_calls
    assert "ingles_atividades" in sql_calls
    conn.commit.assert_called()
```

- [ ] **Rodar o teste para confirmar que falha**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py::test_init_ingles_tables_cria_tabelas -v
```
Esperado: `FAILED` com `AttributeError: module 'app' has no attribute '_init_ingles_tables'`

- [ ] **Implementar `_init_ingles_tables()` em `app.py`**

Adicionar após a linha da função `_init_dr_tables` (por volta da linha 300), antes do próximo `def`:

```python
def _init_ingles_tables():
    """Cria tabelas do módulo de inglês se não existirem."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingles_palavras (
                id SERIAL PRIMARY KEY,
                palavra TEXT NOT NULL,
                classe_gramatical TEXT,
                definicao_pt TEXT NOT NULL,
                exemplo_en TEXT NOT NULL,
                fonetica TEXT,
                categoria TEXT,
                data_exibicao DATE UNIQUE,
                estudada BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingles_sessoes (
                id SERIAL PRIMARY KEY,
                tema TEXT,
                mensagens JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingles_atividades (
                id SERIAL PRIMARY KEY,
                tipo VARCHAR(30) NOT NULL,
                data_atividade DATE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Registrar no startup** — em `app.py` por volta da linha 8744, após `_init_ativos_personalizados_table()`:

```python
    _init_ingles_tables()
```

- [ ] **Rodar o teste para confirmar que passa**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py::test_init_ingles_tables_cria_tabelas -v
```
Esperado: `PASSED`

- [ ] **Commit**

```bash
cd /root/jake_desktop && git add app.py tests/test_ingles_api.py && git commit -m "feat(ingles): cria tabelas ingles_palavras, ingles_sessoes, ingles_atividades"
```

---

## Task 2: Rota GET `/api/ingles/palavra-do-dia`

**Files:**
- Modify: `jake_desktop/app.py` (adicionar após rotas de nutricao, por volta da linha 8260)
- Modify: `jake_desktop/tests/test_ingles_api.py`

**Lógica:** Verifica se `ingles_palavras` tem registro com `data_exibicao = TODAY()`. Se sim, retorna. Se não, chama Claude para gerar e persiste. Categoria determinística: `DAY_OF_YEAR % 4` → `['marketing', 'negocios', 'cotidiano', 'tecnologia']`.

**Prompt Claude para geração de palavra:**
```
Gere UMA palavra em inglês do vocabulário de {categoria} para um profissional de marketing digital brasileiro de nível intermediário.
Retorne SOMENTE este JSON (sem markdown):
{
  "palavra": "...",
  "classe_gramatical": "noun|verb|adj|adv|phrase",
  "definicao_pt": "Definição clara em português (1 frase)",
  "exemplo_en": "Exemplo de frase completa em inglês usando a palavra em contexto profissional",
  "fonetica": "/transcrição IPA/"
}
Escolha uma palavra útil mas não óbvia — não use palavras como 'marketing' ou 'business' que qualquer pessoa já conhece.
```

- [ ] **Escrever os testes**

```python
# Adicionar ao tests/test_ingles_api.py

@pytest.fixture
def client():
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.secret_key = 'test-secret'
    with flask_app.app.test_client() as c:
        with c.session_transaction() as sess:
            sess['logged_in'] = True
        yield c


def test_palavra_do_dia_retorna_existente(client):
    """Se já existe palavra para hoje no banco, retorna sem chamar Claude."""
    row = {
        "id": 1, "palavra": "leverage", "classe_gramatical": "verb",
        "definicao_pt": "Aproveitar ao máximo", "exemplo_en": "We leverage data to grow.",
        "fonetica": "/ˈlevərɪdʒ/", "categoria": "marketing",
        "data_exibicao": "2026-06-01", "estudada": False
    }
    conn = _mock_conn(one=row)
    with patch("app._get_db", return_value=conn):
        resp = client.get("/api/ingles/palavra-do-dia")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["palavra"] == "leverage"


def test_palavra_do_dia_gera_quando_nao_existe(client):
    """Se não existe palavra para hoje, chama Claude e persiste."""
    conn = _mock_conn(one=None)
    # segundo fetchone para o INSERT RETURNING id
    conn.cursor().fetchone.side_effect = [None, {"id": 2}]

    palavra_gerada = {
        "palavra": "nurture", "classe_gramatical": "verb",
        "definicao_pt": "Cultivar relacionamentos", "exemplo_en": "Nurture your leads.",
        "fonetica": "/ˈnɜːrtʃər/"
    }
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=str(palavra_gerada).replace("'", '"'))]

    import json
    mock_msg.content[0].text = json.dumps(palavra_gerada)

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.return_value = mock_msg

    with patch("app._get_db", return_value=conn), \
         patch("app._anthropic_client", return_value=mock_anthropic):
        resp = client.get("/api/ingles/palavra-do-dia")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["palavra"] == "nurture"
```

- [ ] **Rodar para confirmar falha**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py::test_palavra_do_dia_retorna_existente tests/test_ingles_api.py::test_palavra_do_dia_gera_quando_nao_existe -v
```
Esperado: `FAILED` com `404`

- [ ] **Implementar a rota em `app.py`**

Adicionar após as rotas de nutricao (por volta da linha 8260, procurar `# ── DR` e inserir antes):

```python
# ── INGLÊS ─────────────────────────────────────────────────────────────────

_INGLES_CATEGORIAS = ['marketing', 'negocios', 'cotidiano', 'tecnologia']
_INGLES_TEMAS_CONVERSA = ['marketing and advertising', 'travel and places', 'business and entrepreneurship', 'daily life and routines', 'technology and innovation']

_INGLES_PALAVRA_PROMPT = """Gere UMA palavra em inglês do vocabulário de {categoria} para um profissional de marketing digital brasileiro de nível intermediário.
Retorne SOMENTE este JSON (sem markdown):
{{"palavra": "...", "classe_gramatical": "noun|verb|adj|adv|phrase", "definicao_pt": "Definição clara em português (1 frase)", "exemplo_en": "Exemplo de frase completa em inglês usando a palavra em contexto profissional", "fonetica": "/transcrição IPA/"}}
Escolha uma palavra útil mas não óbvia — não use palavras como 'marketing' ou 'business' que qualquer pessoa já conhece."""

_INGLES_CONVERSA_SYSTEM = """You are an English conversation partner for a Brazilian digital marketer at intermediate level.
Your job: have natural, engaging conversations in English.
When the user makes grammar or vocabulary mistakes, naturally use the correct form in your response without explicitly pointing it out — model correct English, don't correct.
Keep messages concise (2-4 sentences). Always end with a follow-up question to keep the conversation going.
Today's suggested topic: {tema}"""


@app.route("/api/ingles/palavra-do-dia")
@login_required
def ingles_palavra_do_dia():
    import datetime, json as _json
    conn = _get_db()
    try:
        cur = conn.cursor()
        hoje = datetime.date.today()
        cur.execute("SELECT * FROM ingles_palavras WHERE data_exibicao = %s", (hoje,))
        row = cur.fetchone()
        if row:
            return jsonify(dict(row))
        # Gerar nova palavra via Claude
        client = _anthropic_client()
        if not client:
            return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500
        day_of_year = hoje.timetuple().tm_yday
        categoria = _INGLES_CATEGORIAS[day_of_year % len(_INGLES_CATEGORIAS)]
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": _INGLES_PALAVRA_PROMPT.format(categoria=categoria)}]
            )
            raw = msg.content[0].text.strip()
            # limpa possível markdown ```json
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            dados = _json.loads(raw)
        except Exception as e:
            return jsonify({"error": f"Erro ao gerar palavra: {e}"}), 503
        cur.execute("""
            INSERT INTO ingles_palavras (palavra, classe_gramatical, definicao_pt, exemplo_en, fonetica, categoria, data_exibicao)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            dados.get("palavra"), dados.get("classe_gramatical"),
            dados.get("definicao_pt"), dados.get("exemplo_en"),
            dados.get("fonetica"), categoria, hoje
        ))
        novo_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({
            "id": novo_id,
            "palavra": dados.get("palavra"),
            "classe_gramatical": dados.get("classe_gramatical"),
            "definicao_pt": dados.get("definicao_pt"),
            "exemplo_en": dados.get("exemplo_en"),
            "fonetica": dados.get("fonetica"),
            "categoria": categoria,
            "data_exibicao": str(hoje),
            "estudada": False
        })
    finally:
        conn.close()
```

- [ ] **Rodar os testes**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py::test_palavra_do_dia_retorna_existente tests/test_ingles_api.py::test_palavra_do_dia_gera_quando_nao_existe -v
```
Esperado: `2 passed`

- [ ] **Commit**

```bash
cd /root/jake_desktop && git add app.py tests/test_ingles_api.py && git commit -m "feat(ingles): rota GET /api/ingles/palavra-do-dia com geração Claude"
```

---

## Task 3: Rota GET `/api/ingles/palavra/audio`

**Files:**
- Modify: `jake_desktop/app.py`
- Modify: `jake_desktop/tests/test_ingles_api.py`

**Lógica:** Recebe `?palavra=leverage` como query param. Chama OpenAI TTS (model `tts-1`, voice `onyx`). Retorna `{"audio": "<base64>"}`.

- [ ] **Escrever o teste**

```python
def test_audio_palavra(client):
    """GET /api/ingles/palavra/audio?palavra=leverage retorna base64 de áudio."""
    mock_tts = MagicMock()
    mock_tts.content = b"fake-audio-bytes"

    mock_openai = MagicMock()
    mock_openai.audio.speech.create.return_value = mock_tts

    with patch("app._openai_client", return_value=mock_openai):
        resp = client.get("/api/ingles/palavra/audio?palavra=leverage")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "audio" in data
    assert len(data["audio"]) > 0
```

- [ ] **Rodar para confirmar falha**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py::test_audio_palavra -v
```

- [ ] **Implementar a rota**

Adicionar logo após a rota `ingles_palavra_do_dia`:

```python
@app.route("/api/ingles/palavra/audio")
@login_required
def ingles_palavra_audio():
    palavra = (request.args.get("palavra") or "").strip()
    if not palavra:
        return jsonify({"error": "Parâmetro 'palavra' obrigatório"}), 400
    client = _openai_client()
    if not client:
        return jsonify({"error": "OPENAI_API_KEY não configurada"}), 500
    try:
        tts = client.audio.speech.create(model="tts-1", voice="onyx", input=palavra)
        audio_bytes = (getattr(tts, "content", None)
                       or (b"".join(tts.iter_bytes()) if hasattr(tts, "iter_bytes") else b""))
        return jsonify({"audio": base64.b64encode(audio_bytes).decode()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Rodar e confirmar passa**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py::test_audio_palavra -v
```

- [ ] **Commit**

```bash
cd /root/jake_desktop && git add app.py tests/test_ingles_api.py && git commit -m "feat(ingles): rota GET /api/ingles/palavra/audio com OpenAI TTS"
```

---

## Task 4: Rotas de sessões de conversa

**Files:**
- Modify: `jake_desktop/app.py`
- Modify: `jake_desktop/tests/test_ingles_api.py`

Três rotas:
- `GET /api/ingles/sessoes` → últimas 10 sessões
- `POST /api/ingles/sessoes` → cria nova sessão com tema determinístico
- `POST /api/ingles/sessoes/<id>/chat` → envia mensagem, Claude responde, salva no JSONB

- [ ] **Escrever os testes**

```python
def test_listar_sessoes(client):
    """GET /api/ingles/sessoes retorna lista."""
    rows = [{"id": 1, "tema": "marketing", "mensagens": [], "created_at": "2026-06-01"}]
    with patch("app._get_db", return_value=_mock_conn(rows=rows)):
        resp = client.get("/api/ingles/sessoes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)


def test_criar_sessao(client):
    """POST /api/ingles/sessoes cria sessão com tema."""
    conn = _mock_conn(one={"id": 5})
    with patch("app._get_db", return_value=conn):
        resp = client.post("/api/ingles/sessoes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 5
    assert "tema" in data


def test_chat_sessao(client):
    """POST /api/ingles/sessoes/1/chat retorna resposta da IA."""
    sessao = {"id": 1, "tema": "marketing", "mensagens": []}
    conn = _mock_conn(one=sessao)

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="That's a great question about marketing!")]
    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.return_value = mock_msg

    with patch("app._get_db", return_value=conn), \
         patch("app._anthropic_client", return_value=mock_anthropic):
        resp = client.post("/api/ingles/sessoes/1/chat",
                           json={"mensagem": "What do you think about paid traffic?"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "resposta" in data
    assert len(data["resposta"]) > 0
```

- [ ] **Rodar para confirmar falha**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py::test_listar_sessoes tests/test_ingles_api.py::test_criar_sessao tests/test_ingles_api.py::test_chat_sessao -v
```

- [ ] **Implementar as 3 rotas**

Adicionar após `ingles_palavra_audio` em `app.py`:

```python
@app.route("/api/ingles/sessoes")
@login_required
def ingles_listar_sessoes():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, tema, mensagens, created_at FROM ingles_sessoes ORDER BY created_at DESC LIMIT 10")
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["created_at"] = str(r["created_at"])
        return jsonify(rows)
    finally:
        conn.close()


@app.route("/api/ingles/sessoes", methods=["POST"])
@login_required
def ingles_criar_sessao():
    import datetime
    day_of_year = datetime.date.today().timetuple().tm_yday
    tema = _INGLES_TEMAS_CONVERSA[day_of_year % len(_INGLES_TEMAS_CONVERSA)]
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ingles_sessoes (tema, mensagens) VALUES (%s, %s) RETURNING id",
            (tema, _json_mod.dumps([]))
        )
        novo_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"id": novo_id, "tema": tema, "mensagens": []})
    finally:
        conn.close()


@app.route("/api/ingles/sessoes/<int:sid>/chat", methods=["POST"])
@login_required
def ingles_chat(sid):
    import json as _json
    data = request.get_json() or {}
    mensagem = (data.get("mensagem") or "").strip()
    if not mensagem:
        return jsonify({"error": "mensagem obrigatória"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ingles_sessoes WHERE id = %s", (sid,))
        sessao = cur.fetchone()
        if not sessao:
            return jsonify({"error": "sessão não encontrada"}), 404
        sessao = dict(sessao)
        historico = sessao.get("mensagens") or []
        if isinstance(historico, str):
            historico = _json.loads(historico)
        client = _anthropic_client()
        if not client:
            return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500
        system = _INGLES_CONVERSA_SYSTEM.format(tema=sessao.get("tema", "general conversation"))
        msgs_api = [{"role": m["role"], "content": m["content"]} for m in historico]
        msgs_api.append({"role": "user", "content": mensagem})
        resp_claude = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=system,
            messages=msgs_api
        )
        resposta = resp_claude.content[0].text.strip()
        historico.append({"role": "user", "content": mensagem})
        historico.append({"role": "assistant", "content": resposta})
        cur.execute(
            "UPDATE ingles_sessoes SET mensagens = %s WHERE id = %s",
            (_json.dumps(historico), sid)
        )
        # Registrar atividade
        import datetime
        cur.execute(
            "INSERT INTO ingles_atividades (tipo, data_atividade) VALUES (%s, %s)",
            ("message_sent", datetime.date.today())
        )
        conn.commit()
        return jsonify({"resposta": resposta, "mensagens": historico})
    finally:
        conn.close()
```

- [ ] **Verificar se `import json` já existe no topo de `app.py`**

```bash
grep -n "^import json" /root/jake_desktop/app.py
```

Se retornar uma linha (ex: `42: import json`), use `json` diretamente nos snippets acima substituindo `_json_mod` por `json`.
Se não retornar nada, adicionar no topo do bloco INGLÊS (antes de `ingles_listar_sessoes`):
```python
import json as _json_mod
```

- [ ] **Rodar os testes**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py::test_listar_sessoes tests/test_ingles_api.py::test_criar_sessao tests/test_ingles_api.py::test_chat_sessao -v
```
Esperado: `3 passed`

- [ ] **Commit**

```bash
cd /root/jake_desktop && git add app.py tests/test_ingles_api.py && git commit -m "feat(ingles): rotas sessoes de conversa (listar, criar, chat Claude)"
```

---

## Task 5: Rotas de atividade e progresso

**Files:**
- Modify: `jake_desktop/app.py`
- Modify: `jake_desktop/tests/test_ingles_api.py`

- [ ] **Escrever os testes**

```python
def test_registrar_atividade(client):
    """POST /api/ingles/atividade registra atividade."""
    conn = _mock_conn()
    with patch("app._get_db", return_value=conn):
        resp = client.post("/api/ingles/atividade",
                           json={"tipo": "word_studied"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_registrar_atividade_tipo_invalido(client):
    """POST /api/ingles/atividade rejeita tipo inválido."""
    resp = client.post("/api/ingles/atividade",
                       json={"tipo": "hacking_stuff"})
    assert resp.status_code == 400


def test_progresso(client):
    """GET /api/ingles/progresso retorna streak, total e calendario."""
    from datetime import date
    conn_mock = _mock_conn()
    # streak query
    conn_mock.cursor().fetchall.side_effect = [
        [{"data_atividade": date.today()}],  # atividades para streak
        [],                                    # sessoes
    ]
    conn_mock.cursor().fetchone.return_value = {"total": 5}
    with patch("app._get_db", return_value=conn_mock):
        resp = client.get("/api/ingles/progresso")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "streak" in data
    assert "total_palavras" in data
    assert "calendario" in data
```

- [ ] **Rodar para confirmar falha**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py::test_registrar_atividade tests/test_ingles_api.py::test_registrar_atividade_tipo_invalido tests/test_ingles_api.py::test_progresso -v
```

- [ ] **Implementar as rotas**

```python
_INGLES_TIPOS_ATIVIDADE = {"word_studied", "audio_played", "message_sent"}


@app.route("/api/ingles/atividade", methods=["POST"])
@login_required
def ingles_registrar_atividade():
    import datetime
    data = request.get_json() or {}
    tipo = data.get("tipo", "")
    if tipo not in _INGLES_TIPOS_ATIVIDADE:
        return jsonify({"error": f"tipo inválido. Use: {', '.join(_INGLES_TIPOS_ATIVIDADE)}"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ingles_atividades (tipo, data_atividade) VALUES (%s, %s)",
            (tipo, datetime.date.today())
        )
        # Marcar palavra como estudada se for word_studied
        if tipo == "word_studied":
            cur.execute(
                "UPDATE ingles_palavras SET estudada = TRUE WHERE data_exibicao = %s",
                (datetime.date.today(),)
            )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/ingles/progresso")
@login_required
def ingles_progresso():
    import datetime
    conn = _get_db()
    try:
        cur = conn.cursor()
        # Total de palavras estudadas
        cur.execute("SELECT COUNT(*) as total FROM ingles_atividades WHERE tipo = 'word_studied'")
        total_palavras = (cur.fetchone() or {}).get("total", 0)
        # Dias com atividade (para streak e calendário)
        cur.execute("""
            SELECT DISTINCT data_atividade
            FROM ingles_atividades
            ORDER BY data_atividade DESC
            LIMIT 60
        """)
        dias_ativos = [r["data_atividade"] for r in cur.fetchall()]
        # Calcular streak
        streak = 0
        hoje = datetime.date.today()
        data_check = hoje
        for d in dias_ativos:
            if d == data_check:
                streak += 1
                data_check = data_check - datetime.timedelta(days=1)
            elif d < data_check:
                break
        # Calendário do mês atual
        mes_atual = hoje.month
        ano_atual = hoje.year
        calendario = [str(d) for d in dias_ativos if d.month == mes_atual and d.year == ano_atual]
        # Últimas 5 sessões
        cur.execute("SELECT id, tema, created_at FROM ingles_sessoes ORDER BY created_at DESC LIMIT 5")
        sessoes = [{"id": r["id"], "tema": r["tema"], "created_at": str(r["created_at"])} for r in cur.fetchall()]
        return jsonify({
            "streak": streak,
            "total_palavras": total_palavras,
            "calendario": calendario,
            "ultimas_sessoes": sessoes
        })
    finally:
        conn.close()
```

- [ ] **Rodar os testes**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py -v
```
Esperado: todos os testes passando

- [ ] **Commit**

```bash
cd /root/jake_desktop && git add app.py tests/test_ingles_api.py && git commit -m "feat(ingles): rotas atividade e progresso (streak, calendario)"
```

---

## Task 6: HTML — sidebar + section + CSS

**Files:**
- Modify: `jake_desktop/templates/dashboard.html`

**IMPORTANTE:** Este arquivo tem ~2200 linhas. Sempre ler o trecho exato antes de editar. Usar Grep para localizar linhas.

### 6a — Nav item na sidebar

- [ ] **Localizar a linha do item "Nutrição" na sidebar**

```bash
grep -n "nutricao\|Nutrição" /root/jake_desktop/templates/dashboard.html | head -5
```

- [ ] **Adicionar item após o item Nutrição** (antes de `<!-- Direct Response desativado -->`):

```html
        <a class="nav-item" data-page="ingles" href="#">
          <span class="nav-icon">🇺🇸</span>
          <span class="nav-label">Inglês</span>
        </a>
```

### 6b — Bloco CSS inline

- [ ] **Localizar onde inserir o CSS** — adicionar antes de `</head>`, após o último bloco `<style>` existente:

```html
  <style id="ingles-styles">
    .ing-page { padding: 28px; max-width: 900px; }
    .ing-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
    .ing-title { font-family: 'Orbitron', sans-serif; font-size: 1.3rem; color: #00e5ff; }
    .ing-tabs { display: flex; gap: 8px; margin-bottom: 28px; }
    .ing-tab { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 8px 20px; color: rgba(255,255,255,0.5); font-family: 'Rajdhani', sans-serif; font-size: 0.85rem; letter-spacing: 1px; cursor: pointer; transition: all 0.2s; }
    .ing-tab.active { background: rgba(0,229,255,0.12); border-color: rgba(0,229,255,0.4); color: #00e5ff; }
    .ing-tab-content { display: none; }
    .ing-tab-content.active { display: block; }

    /* Palavra do Dia */
    .ing-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(0,229,255,0.12); border-radius: 12px; padding: 28px; backdrop-filter: blur(12px); }
    .ing-word { font-family: 'Orbitron', sans-serif; font-size: 2.2rem; color: #fff; margin-bottom: 8px; }
    .ing-pos { display: inline-block; background: rgba(0,229,255,0.12); color: #00e5ff; border-radius: 20px; padding: 3px 12px; font-size: 0.75rem; font-family: 'Rajdhani', sans-serif; letter-spacing: 1px; margin-bottom: 16px; }
    .ing-def { font-size: 1rem; color: rgba(255,255,255,0.8); margin-bottom: 12px; }
    .ing-example { font-style: italic; color: rgba(255,255,255,0.5); font-size: 0.9rem; margin-bottom: 16px; border-left: 2px solid rgba(0,229,255,0.3); padding-left: 12px; }
    .ing-fonetica { font-size: 0.9rem; color: rgba(0,229,255,0.7); margin-bottom: 20px; font-family: monospace; }
    .ing-actions { display: flex; gap: 10px; }
    .ing-btn { padding: 8px 18px; border-radius: 8px; font-family: 'Rajdhani', sans-serif; font-size: 0.85rem; letter-spacing: 1px; cursor: pointer; transition: all 0.2s; border: 1px solid rgba(0,229,255,0.3); background: rgba(0,229,255,0.08); color: #00e5ff; }
    .ing-btn:hover { background: rgba(0,229,255,0.18); }
    .ing-btn.done { background: rgba(0,229,255,0.2); color: #fff; cursor: default; }
    .ing-loading { color: rgba(255,255,255,0.3); font-size: 0.9rem; padding: 20px 0; }

    /* Conversar */
    .ing-chat-box { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 16px; height: 380px; overflow-y: auto; margin-bottom: 16px; display: flex; flex-direction: column; gap: 12px; }
    .ing-msg { max-width: 80%; padding: 10px 14px; border-radius: 10px; font-size: 0.9rem; line-height: 1.5; }
    .ing-msg.user { align-self: flex-end; background: rgba(0,229,255,0.12); color: #fff; border-bottom-right-radius: 2px; }
    .ing-msg.assistant { align-self: flex-start; background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.85); border-bottom-left-radius: 2px; }
    .ing-chat-form { display: flex; gap: 10px; }
    .ing-chat-input { flex: 1; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 10px 14px; color: #fff; font-size: 0.9rem; outline: none; }
    .ing-chat-input:focus { border-color: rgba(0,229,255,0.4); }
    .ing-chat-send { padding: 10px 20px; background: rgba(0,229,255,0.12); border: 1px solid rgba(0,229,255,0.3); border-radius: 8px; color: #00e5ff; font-family: 'Rajdhani', sans-serif; cursor: pointer; font-size: 0.9rem; transition: all 0.2s; }
    .ing-chat-send:hover { background: rgba(0,229,255,0.22); }
    .ing-tema-badge { font-size: 0.75rem; color: rgba(0,229,255,0.6); font-family: 'Rajdhani', sans-serif; letter-spacing: 1px; margin-bottom: 12px; }

    /* Progresso */
    .ing-stats-row { display: flex; gap: 16px; margin-bottom: 24px; }
    .ing-stat-card { flex: 1; background: rgba(255,255,255,0.04); border: 1px solid rgba(0,229,255,0.12); border-radius: 12px; padding: 20px; text-align: center; }
    .ing-stat-val { font-family: 'Orbitron', sans-serif; font-size: 2rem; color: #00e5ff; }
    .ing-stat-label { font-size: 0.75rem; color: rgba(255,255,255,0.4); font-family: 'Rajdhani', sans-serif; letter-spacing: 1px; text-transform: uppercase; margin-top: 4px; }
    .ing-cal { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 24px; }
    .ing-cal-day { width: 32px; height: 32px; border-radius: 6px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: center; font-size: 0.75rem; color: rgba(255,255,255,0.3); }
    .ing-cal-day.studied { background: rgba(0,229,255,0.15); border-color: rgba(0,229,255,0.4); color: #00e5ff; }
    .ing-sessions-list { display: flex; flex-direction: column; gap: 8px; }
    .ing-session-item { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; }
    .ing-session-tema { font-size: 0.85rem; color: rgba(255,255,255,0.7); }
    .ing-session-data { font-size: 0.75rem; color: rgba(255,255,255,0.3); }
    .ing-section-title { font-family: 'Rajdhani', sans-serif; font-size: 0.8rem; letter-spacing: 2px; text-transform: uppercase; color: #00e5ff; margin-bottom: 12px; }
  </style>
```

### 6c — Seção HTML

- [ ] **Localizar a linha final do `</section>` de nutricao**

```bash
grep -n "page-nutricao\|</section>" /root/jake_desktop/templates/dashboard.html | grep -A1 "page-nutricao"
```

- [ ] **Adicionar após o fechamento da section nutricao:**

```html
      <section class="page" id="page-ingles" style="display:none">
        <div class="ing-page">
          <div class="ing-header">
            <h1 class="ing-title">English Practice</h1>
          </div>

          <div class="ing-tabs">
            <button class="ing-tab active" data-tab="palavra">📖 Palavra do Dia</button>
            <button class="ing-tab" data-tab="conversar">💬 Conversar</button>
            <button class="ing-tab" data-tab="progresso">📊 Progresso</button>
          </div>

          <!-- Aba: Palavra do Dia -->
          <div class="ing-tab-content active" id="ing-tab-palavra">
            <div id="ing-palavra-loading" class="ing-loading">Carregando palavra do dia...</div>
            <div id="ing-palavra-card" class="ing-card" style="display:none">
              <div class="ing-word" id="ing-word-text"></div>
              <div class="ing-pos" id="ing-pos-text"></div>
              <div class="ing-def" id="ing-def-text"></div>
              <div class="ing-example" id="ing-example-text"></div>
              <div class="ing-fonetica" id="ing-fonetica-text"></div>
              <div class="ing-actions">
                <button class="ing-btn" id="ing-btn-audio" onclick="inglesPlayAudio()">🔊 Ouvir</button>
                <button class="ing-btn" id="ing-btn-estudada" onclick="inglesMarcarEstudada()">✓ Estudada</button>
              </div>
              <audio id="ing-audio-player" style="display:none"></audio>
            </div>
          </div>

          <!-- Aba: Conversar -->
          <div class="ing-tab-content" id="ing-tab-conversar">
            <div class="ing-tema-badge" id="ing-tema-badge"></div>
            <div class="ing-chat-box" id="ing-chat-box">
              <div class="ing-loading">Iniciando sessão...</div>
            </div>
            <form class="ing-chat-form" onsubmit="return inglesEnviarMensagem(event)">
              <input type="text" class="ing-chat-input" id="ing-chat-input"
                     placeholder="Type in English..." autocomplete="off">
              <button type="submit" class="ing-chat-send">Send →</button>
            </form>
            <div style="margin-top:10px;text-align:right">
              <button class="ing-btn" style="font-size:0.75rem;padding:6px 12px"
                      onclick="inglesNovaSessao()">+ Nova Sessão</button>
            </div>
          </div>

          <!-- Aba: Progresso -->
          <div class="ing-tab-content" id="ing-tab-progresso">
            <div class="ing-stats-row">
              <div class="ing-stat-card">
                <div class="ing-stat-val" id="ing-streak-val">—</div>
                <div class="ing-stat-label">🔥 Streak</div>
              </div>
              <div class="ing-stat-card">
                <div class="ing-stat-val" id="ing-total-val">—</div>
                <div class="ing-stat-label">📖 Palavras</div>
              </div>
            </div>
            <div class="ing-section-title">Calendário do Mês</div>
            <div class="ing-cal" id="ing-cal"></div>
            <div class="ing-section-title">Sessões Recentes</div>
            <div class="ing-sessions-list" id="ing-sessions-list"></div>
          </div>
        </div>
      </section>
```

- [ ] **Commit do HTML**

```bash
cd /root/jake_desktop && git add templates/dashboard.html && git commit -m "feat(ingles): HTML section, nav-item e CSS inline"
```

---

## Task 7: JavaScript (`ingles.js`)

**Files:**
- Create: `jake_desktop/static/js/ingles.js`

- [ ] **Criar o arquivo `static/js/ingles.js`**

```javascript
// jake_desktop/static/js/ingles.js
(function () {
  'use strict';

  var IState = {
    palavraId: null,
    palavraTexto: '',
    sessaoId: null,
    enviando: false,
  };

  // ── INIT ─────────────────────────────────────────────────────────────────
  window.initIngles = function () {
    bindTabs();
    carregarPalavra();
  };

  // ── TABS ─────────────────────────────────────────────────────────────────
  function bindTabs() {
    document.querySelectorAll('.ing-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var tab = this.dataset.tab;
        document.querySelectorAll('.ing-tab').forEach(function (b) { b.classList.remove('active'); });
        document.querySelectorAll('.ing-tab-content').forEach(function (c) { c.classList.remove('active'); });
        this.classList.add('active');
        var el = document.getElementById('ing-tab-' + tab);
        if (el) el.classList.add('active');
        if (tab === 'conversar' && !IState.sessaoId) iniciarSessao();
        if (tab === 'progresso') carregarProgresso();
      }.bind(btn));
    });
  }

  // ── PALAVRA DO DIA ────────────────────────────────────────────────────────
  function carregarPalavra() {
    var loading = document.getElementById('ing-palavra-loading');
    var card = document.getElementById('ing-palavra-card');
    if (loading) loading.style.display = 'block';
    if (card) card.style.display = 'none';

    fetch('/api/ingles/palavra-do-dia')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.error) { if (loading) loading.textContent = 'Erro: ' + d.error; return; }
        IState.palavraId = d.id;
        IState.palavraTexto = d.palavra;
        document.getElementById('ing-word-text').textContent = d.palavra;
        document.getElementById('ing-pos-text').textContent = d.classe_gramatical || '';
        document.getElementById('ing-def-text').textContent = d.definicao_pt || '';
        document.getElementById('ing-example-text').textContent = '"' + (d.exemplo_en || '') + '"';
        document.getElementById('ing-fonetica-text').textContent = d.fonetica || '';
        if (d.estudada) {
          var btn = document.getElementById('ing-btn-estudada');
          if (btn) { btn.textContent = '✓ Estudada'; btn.classList.add('done'); btn.disabled = true; }
        }
        if (loading) loading.style.display = 'none';
        if (card) card.style.display = 'block';
      })
      .catch(function (e) {
        if (loading) loading.textContent = 'Erro ao carregar palavra.';
      });
  }

  window.inglesPlayAudio = function () {
    if (!IState.palavraTexto) return;
    fetch('/api/ingles/palavra/audio?palavra=' + encodeURIComponent(IState.palavraTexto))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.audio) return;
        var player = document.getElementById('ing-audio-player');
        player.src = 'data:audio/mpeg;base64,' + d.audio;
        player.play();
        // Registrar atividade
        fetch('/api/ingles/atividade', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({tipo: 'audio_played'})
        });
      });
  };

  window.inglesMarcarEstudada = function () {
    fetch('/api/ingles/atividade', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tipo: 'word_studied'})
    }).then(function (r) { return r.json(); })
      .then(function () {
        var btn = document.getElementById('ing-btn-estudada');
        if (btn) { btn.textContent = '✓ Estudada'; btn.classList.add('done'); btn.disabled = true; }
      });
  };

  // ── CONVERSAR ─────────────────────────────────────────────────────────────
  function iniciarSessao() {
    var box = document.getElementById('ing-chat-box');
    if (box) box.innerHTML = '<div class="ing-loading">Iniciando sessão...</div>';
    fetch('/api/ingles/sessoes', {method: 'POST'})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        IState.sessaoId = d.id;
        var badge = document.getElementById('ing-tema-badge');
        if (badge) badge.textContent = 'Topic: ' + (d.tema || '');
        // Mensagem inicial da IA
        renderMensagem('assistant', "Hi! I'm Jake, your English practice partner. Today's topic: " + (d.tema || 'free conversation') + ". How are you doing today?");
      });
  }

  window.inglesNovaSessao = function () {
    IState.sessaoId = null;
    iniciarSessao();
  };

  window.inglesEnviarMensagem = function (e) {
    e.preventDefault();
    if (IState.enviando) return false;
    var input = document.getElementById('ing-chat-input');
    var texto = (input.value || '').trim();
    if (!texto || !IState.sessaoId) return false;
    input.value = '';
    renderMensagem('user', texto);
    IState.enviando = true;
    var sendBtn = document.querySelector('.ing-chat-send');
    if (sendBtn) sendBtn.disabled = true;
    fetch('/api/ingles/sessoes/' + IState.sessaoId + '/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mensagem: texto})
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        IState.enviando = false;
        if (sendBtn) sendBtn.disabled = false;
        if (d.error) { renderMensagem('assistant', '⚠️ ' + d.error); return; }
        renderMensagem('assistant', d.resposta);
      })
      .catch(function () {
        IState.enviando = false;
        if (sendBtn) sendBtn.disabled = false;
        renderMensagem('assistant', '⚠️ Connection error. Try again.');
      });
    return false;
  };

  function renderMensagem(role, texto) {
    var box = document.getElementById('ing-chat-box');
    if (!box) return;
    // Limpa loading se presente
    var loading = box.querySelector('.ing-loading');
    if (loading) loading.remove();
    var div = document.createElement('div');
    div.className = 'ing-msg ' + role;
    div.textContent = texto;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  // ── PROGRESSO ────────────────────────────────────────────────────────────
  function carregarProgresso() {
    fetch('/api/ingles/progresso')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var streakEl = document.getElementById('ing-streak-val');
        var totalEl = document.getElementById('ing-total-val');
        if (streakEl) streakEl.textContent = d.streak + ' dias';
        if (totalEl) totalEl.textContent = d.total_palavras;
        renderCalendario(d.calendario || []);
        renderSessoes(d.ultimas_sessoes || []);
      });
  }

  function renderCalendario(diasEstudados) {
    var cal = document.getElementById('ing-cal');
    if (!cal) return;
    var hoje = new Date();
    var ano = hoje.getFullYear();
    var mes = hoje.getMonth();
    var diasNoMes = new Date(ano, mes + 1, 0).getDate();
    var html = '';
    for (var d = 1; d <= diasNoMes; d++) {
      var dataStr = ano + '-' + String(mes + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      var cls = diasEstudados.indexOf(dataStr) !== -1 ? 'ing-cal-day studied' : 'ing-cal-day';
      html += '<div class="' + cls + '">' + d + '</div>';
    }
    cal.innerHTML = html;
  }

  function renderSessoes(sessoes) {
    var lista = document.getElementById('ing-sessions-list');
    if (!lista) return;
    if (!sessoes.length) { lista.innerHTML = '<div class="ing-loading">Nenhuma sessão ainda.</div>'; return; }
    lista.innerHTML = sessoes.map(function (s) {
      var data = s.created_at ? s.created_at.substring(0, 10) : '';
      return '<div class="ing-session-item">' +
        '<span class="ing-session-tema">' + esc(s.tema || 'conversa') + '</span>' +
        '<span class="ing-session-data">' + data + '</span>' +
        '</div>';
    }).join('');
  }

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

})();
```

- [ ] **Incluir o script no `dashboard.html`**

Localizar onde os outros scripts são incluídos (antes do `</body>`) e adicionar:
```html
  <script src="{{ url_for('static', filename='js/ingles.js') }}"></script>
```

- [ ] **Commit**

```bash
cd /root/jake_desktop && git add static/js/ingles.js templates/dashboard.html && git commit -m "feat(ingles): ingles.js com Palavra do Dia, Conversar e Progresso"
```

---

## Task 8: Wiring — app.js

**Files:**
- Modify: `jake_desktop/static/js/app.js`

- [ ] **Adicionar `"ingles"` ao array `valid` na linha 37**

Antes:
```javascript
var valid = ["painel","architect","gestor","planejador","copys","criativos","financeiro","agenda","rotina","social-brief","nutricao","dr"];
```

Depois:
```javascript
var valid = ["painel","architect","gestor","planejador","copys","criativos","financeiro","agenda","rotina","social-brief","nutricao","dr","ingles"];
```

- [ ] **Localizar o bloco do planejador em `app.js`**

```bash
grep -n "planejador" /root/jake_desktop/static/js/app.js
```
Esperado: linhas com `if (id === "planejador" ...)`. Inserir o bloco abaixo imediatamente após esse `if`.

- [ ] **Adicionar callback `initIngles` no `showPage`**

```javascript
    if (id === "ingles" && typeof window.initIngles === "function") {
      window.initIngles();
    }
```

- [ ] **Commit**

```bash
cd /root/jake_desktop && git add static/js/app.js && git commit -m "feat(ingles): registra pagina ingles no SPA router"
```

---

## Task 9: Smoke test e ajustes finais

- [ ] **Reiniciar o Jake OS**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/jake_desktop/.venv/bin/python app.py >> /tmp/jakeos.log 2>&1 &
sleep 3 && tail -20 /tmp/jakeos.log
```

Esperado: sem erros Python, "Jake OS" aparece no log com a porta 5050.

- [ ] **Verificar navegação para `#ingles`**

Acesse `http://localhost:5050/#ingles` e verifique:
- Item "Inglês" aparece na sidebar e fica ativo
- Aba "Palavra do Dia" carrega e exibe a palavra (pode demorar ~3s pela chamada Claude)
- Botão 🔊 toca o áudio
- Botão "✓ Estudada" funciona e desabilita após clicar

- [ ] **Verificar aba Conversar**

- Clica em "Conversar"
- Mensagem inicial da IA aparece no chat
- Digita algo em inglês e envia — IA responde
- Botão "Nova Sessão" limpa o chat e cria nova sessão

- [ ] **Verificar aba Progresso**

- Streak e total de palavras aparecem
- Calendário mostra dias do mês atual
- Sessões recentes listadas

- [ ] **Rodar todos os testes da suite**

```bash
cd /root/jake_desktop && python -m pytest tests/test_ingles_api.py -v
```
Esperado: todos passando.

- [ ] **Commit final**

```bash
cd /root/jake_desktop && git add -A && git commit -m "feat(ingles): modulo de ingles completo no Jake OS

- Palavra do dia gerada por Claude com audio TTS
- Conversacao em ingles com correcao dupla
- Painel de progresso com streak e calendario

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Referências rápidas

- **Padrão de init tables:** `app.py:180` (`_init_nutricao_tables`)
- **Padrão de chamada Claude:** `app.py:741` (carousel copy)
- **Padrão de TTS:** `app.py:634` (`api_falar`)
- **Padrão de JS module:** `static/js/nutricao.js`
- **Padrão de teste Flask:** `tests/test_financeiro_api.py`
- **Startup sequence:** `app.py:8739`
