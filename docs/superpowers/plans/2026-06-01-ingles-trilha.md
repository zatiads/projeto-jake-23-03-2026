# Módulo de Inglês — Trilha Estruturada (v3)

> **For agentic workers:** Use superpowers:subagent-driven-development to implement task-by-task.

**Goal:** Adicionar uma trilha de aprendizado linear com 12 módulos e 3-4 lições cada, onde o Jake conversa guiado pelo contexto da lição ativa.

**Architecture:** Dados do currículo como constante Python em app.py → tabela DB para progresso → 2 novas rotas → nova aba "Trilha" no frontend com módulos/lições + integração com tab Conversar.

**Tech Stack:** Flask, PostgreSQL (Neon), Anthropic Claude, JS vanilla, CSS glassmorphism existente

---

## File Map

| File | Change |
|---|---|
| `app.py` | Constante `INGLES_TRILHA`, migration table, 2 rotas, update conversar/voz |
| `templates/dashboard.html` | 4ª aba Trilha + HTML módulos/lições + CSS |
| `static/js/ingles.js` | `carregarTrilha`, `ingPraticarLicao`, `ingCompletarLicao`, atualizar `enviarVoz` |

---

## Currículo Completo (constante Python)

```python
INGLES_TRILHA = [
  {"id":1,"titulo":"Greetings & Introductions","descricao":"Como se apresentar e quebrar o gelo","icone":"👋","licoes":[
    {"id":1,"titulo":"First Meeting","objetivo":"Introduce yourself professionally","cenario":"You're meeting a new international business contact for the first time at a conference."},
    {"id":2,"titulo":"Small Talk","objetivo":"Keep a light conversation going","cenario":"You're waiting for a business meeting to start and chatting with someone you just met."},
    {"id":3,"titulo":"Video Call Intro","objetivo":"Introduce yourself on a video call","cenario":"You're starting a Zoom call with an international client for the first time."}
  ]},
  {"id":2,"titulo":"Daily Life","descricao":"Cotidiano, rotina e situações do dia a dia","icone":"🏠","licoes":[
    {"id":1,"titulo":"Your Routine","objetivo":"Describe your daily schedule","cenario":"A new English friend asks what your typical workday looks like."},
    {"id":2,"titulo":"Food & Cooking","objetivo":"Talk about food preferences and habits","cenario":"You're having lunch with an international colleague who asks about Brazilian food."},
    {"id":3,"titulo":"Weekend Plans","objetivo":"Make and discuss plans","cenario":"A friend asks what you did last weekend and what you plan to do next."}
  ]},
  {"id":3,"titulo":"Ordering & Service","descricao":"Pedir, reclamar e interagir com serviços","icone":"🍽️","licoes":[
    {"id":1,"titulo":"Restaurant","objetivo":"Order food and handle restaurant situations","cenario":"You're at a restaurant in New York. Order your meal, ask about the menu, and handle a wrong order."},
    {"id":2,"titulo":"Hotel","objetivo":"Check in and request hotel services","cenario":"You're checking into a hotel in Miami. Handle the check-in and request extra towels and a wake-up call."},
    {"id":3,"titulo":"Shopping","objetivo":"Shop, ask prices, handle problems","cenario":"You're shopping at a mall in the US. Find what you need, ask about sizes, and return an item."}
  ]},
  {"id":4,"titulo":"Travel","descricao":"Aeroporto, transporte e navegação","icone":"✈️","licoes":[
    {"id":1,"titulo":"At the Airport","objetivo":"Navigate check-in, security, boarding","cenario":"You're at JFK airport checking in for a flight. Handle check-in, baggage, and boarding questions."},
    {"id":2,"titulo":"Transportation","objetivo":"Use taxis, Uber, subway","cenario":"You just landed in London. Ask for directions to the hotel and use public transportation."},
    {"id":3,"titulo":"Asking Directions","objetivo":"Ask for and understand directions","cenario":"You're lost in downtown Chicago and need to find the nearest subway station."},
    {"id":4,"titulo":"Problem Solving","objetivo":"Handle travel problems (lost luggage, delays)","cenario":"Your luggage didn't arrive and your connecting flight was delayed. Talk to airline staff."}
  ]},
  {"id":5,"titulo":"Work & Business","descricao":"Reuniões, apresentações e e-mails","icone":"💼","licoes":[
    {"id":1,"titulo":"Starting a Meeting","objetivo":"Open, manage and close business meetings","cenario":"You're running a video call with international partners. Open the meeting, set the agenda, manage turns."},
    {"id":2,"titulo":"Presenting Ideas","objetivo":"Present a proposal or campaign results","cenario":"You're presenting last month's ad campaign results to an international client."},
    {"id":3,"titulo":"Professional Emails","objetivo":"Discuss email writing and tone","cenario":"Your colleague asks you to help write a follow-up email to a client who didn't respond."},
    {"id":4,"titulo":"Conference Calls","objetivo":"Participate actively in calls","cenario":"You're on a call with 3 international team members. Speak up, ask questions, summarize decisions."}
  ]},
  {"id":6,"titulo":"Job Interview","descricao":"Entrevistas e negociação de salário","icone":"🤝","licoes":[
    {"id":1,"titulo":"Tell Me About Yourself","objetivo":"Give a polished professional introduction","cenario":"You're in a job interview for a Senior Digital Marketing Manager role at a US company."},
    {"id":2,"titulo":"Strengths & Experience","objetivo":"Talk about skills and past work","cenario":"The interviewer asks about your biggest achievement and how you handled a difficult campaign."},
    {"id":3,"titulo":"Salary & Closing","objetivo":"Negotiate salary and ask questions","cenario":"The interview is ending. Discuss salary expectations and ask smart questions about the role."}
  ]},
  {"id":7,"titulo":"Health & Emergencies","descricao":"Médico, farmácia e situações de emergência","icone":"🏥","licoes":[
    {"id":1,"titulo":"Doctor's Appointment","objetivo":"Describe symptoms and understand diagnosis","cenario":"You're at a clinic in the US with a bad headache and fever. Describe your symptoms to the doctor."},
    {"id":2,"titulo":"Pharmacy","objetivo":"Buy medicine and understand instructions","cenario":"You're at a pharmacy. Ask for medicine for a cold and understand the dosage instructions."},
    {"id":3,"titulo":"Emergency","objetivo":"Handle urgent situations clearly","cenario":"There's been a minor car accident. Call for help, explain the situation, and talk to police."}
  ]},
  {"id":8,"titulo":"Social & Entertainment","descricao":"Lazer, planos e conversas informais","icone":"🎉","licoes":[
    {"id":1,"titulo":"Making Plans","objetivo":"Suggest, accept and decline invitations","cenario":"An English-speaking friend wants to make weekend plans. Suggest activities, negotiate times."},
    {"id":2,"titulo":"Talking About Culture","objetivo":"Discuss movies, music, sports","cenario":"You're at a party and someone asks about your taste in movies, music and sports."},
    {"id":3,"titulo":"Dining Out & Events","objetivo":"Socialize at events and dinners","cenario":"You're at a business dinner with international clients. Keep the conversation fun and professional."}
  ]},
  {"id":9,"titulo":"Digital Marketing in English","descricao":"Vocabulário e situações do marketing digital","icone":"📱","licoes":[
    {"id":1,"titulo":"Client Meeting","objetivo":"Present strategy to an international client","cenario":"You're meeting a US client to present a new paid traffic strategy for their brand."},
    {"id":2,"titulo":"Campaign Results","objetivo":"Report KPIs and metrics in English","cenario":"Present last month's Meta Ads results: CTR, ROAS, CPM. Explain what worked and what didn't."},
    {"id":3,"titulo":"Creative Brief","objetivo":"Brief a creative team in English","cenario":"You're briefing a US-based creative team on a new campaign. Describe the audience, tone, and goals."},
    {"id":4,"titulo":"Tech & Tools","objetivo":"Discuss platforms and tools in English","cenario":"A new client asks you to explain how you use Meta Ads Manager and your reporting process."}
  ]},
  {"id":10,"titulo":"Advanced Business","descricao":"Negociação, pitching e situações difíceis","icone":"🚀","licoes":[
    {"id":1,"titulo":"Negotiation","objetivo":"Negotiate prices, terms, and contracts","cenario":"You're negotiating your agency's monthly retainer with a potential US client who wants a lower price."},
    {"id":2,"titulo":"Pitching","objetivo":"Pitch a project or your agency","cenario":"You have 5 minutes to pitch your digital marketing agency to a US investor. Make it compelling."},
    {"id":3,"titulo":"Handling Complaints","objetivo":"Manage difficult client situations","cenario":"A client is unhappy with last month's campaign results and threatens to leave. Handle it professionally."}
  ]},
  {"id":11,"titulo":"Idioms & Phrasal Verbs","descricao":"Expressões naturais do inglês falado","icone":"💡","licoes":[
    {"id":1,"titulo":"Business Idioms","objetivo":"Use common business idioms naturally","cenario":"You're in a casual meeting. Practice using idioms like 'think outside the box', 'ballpark figure', 'touch base'."},
    {"id":2,"titulo":"Phrasal Verbs","objetivo":"Use phrasal verbs in conversation","cenario":"Chat about work and life using phrasal verbs: 'follow up', 'bring up', 'figure out', 'come up with'."},
    {"id":3,"titulo":"Informal vs Formal","objetivo":"Switch between registers","cenario":"First talk casually with a friend, then shift to a formal tone for a client email — same topic, different style."}
  ]},
  {"id":12,"titulo":"Fluency Polish","descricao":"Storytelling, opinião e humor — nível avançado","icone":"🌟","licoes":[
    {"id":1,"titulo":"Storytelling","objetivo":"Tell engaging stories with detail and flow","cenario":"Tell a story about an interesting experience you had — a trip, a difficult client, a funny situation."},
    {"id":2,"titulo":"Expressing Opinions","objetivo":"Argue and discuss confidently","cenario":"Debate a topic: Is remote work better than office work? Give your opinion, support it, respond to counterpoints."},
    {"id":3,"titulo":"Humor & Naturalness","objetivo":"Be funny, relaxed and natural","cenario":"Have a completely free, casual conversation as if with a friend. No agenda — just be yourself in English."}
  ]}
]
```

---

## Task 1: DB migration + constante + rotas trilha

**Files:** `app.py`, `tests/test_ingles_api.py`

### Step 1: Locate insertion points
```bash
grep -n "_init_ingles_tables\|INGLES_TRILHA\|ingles_trilha" /root/jake_desktop/app.py | head -10
grep -n "_INGLES_PALAVRAS_PROMPT\|# ── INGLÊS" /root/jake_desktop/app.py | head -5
```

### Step 2: Write failing tests

Add to `tests/test_ingles_api.py`:

```python
def test_trilha_retorna_modulos(app_client, mock_db):
    """GET /api/ingles/trilha retorna 12 módulos com lições e progresso."""
    mock_conn, mock_cur = mock_db
    mock_cur.fetchall.return_value = []  # no progress yet
    r = app_client.get("/api/ingles/trilha")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) == 12
    assert "licoes" in data[0]
    assert len(data[0]["licoes"]) >= 3


def test_trilha_completar_licao(app_client, mock_db):
    """POST /api/ingles/trilha/completar marca lição como concluída."""
    mock_conn, mock_cur = mock_db
    mock_cur.fetchone.return_value = None
    r = app_client.post("/api/ingles/trilha/completar",
        json={"modulo_id": 1, "licao_id": 1})
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    mock_conn.commit.assert_called_once()
```

Run to confirm fail:
```bash
cd /root/jake_desktop && .venv/bin/python -m pytest tests/test_ingles_api.py::test_trilha_retorna_modulos tests/test_ingles_api.py::test_trilha_completar_licao -v 2>&1
```

### Step 3: Add migration to `_init_ingles_tables`

After existing migration block (after `conn.commit()` of migration v2), add:
```python
        # Migration v3: trilha de aprendizado
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingles_trilha_progresso (
                id SERIAL PRIMARY KEY,
                modulo_id INTEGER NOT NULL,
                licao_id INTEGER NOT NULL,
                status VARCHAR(20) DEFAULT 'completed',
                completed_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(modulo_id, licao_id)
            )
        """)
        conn.commit()
```

### Step 4: Add `INGLES_TRILHA` constant

Add BEFORE the `# ── INGLÊS` comment block (locate with grep). Paste the full `INGLES_TRILHA` list from above.

### Step 5: Add routes (after `ingles_progresso` route)

Locate `ingles_progresso` route:
```bash
grep -n "def ingles_progresso\|api/ingles/progresso" /root/jake_desktop/app.py | head -5
```

After that route, add:

```python
@app.route("/api/ingles/trilha")
@login_required
def ingles_get_trilha():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT modulo_id, licao_id, status FROM ingles_trilha_progresso")
        progresso = {(r["modulo_id"], r["licao_id"]): r["status"] for r in cur.fetchall()}
    finally:
        conn.close()
    resultado = []
    for modulo in INGLES_TRILHA:
        m = dict(modulo)
        licoes = []
        for l in modulo["licoes"]:
            li = dict(l)
            li["status"] = progresso.get((modulo["id"], l["id"]), "pending")
            licoes.append(li)
        m["licoes"] = licoes
        total = len(licoes)
        concluidas = sum(1 for li in licoes if li["status"] == "completed")
        m["progresso"] = {"total": total, "concluidas": concluidas}
        resultado.append(m)
    return jsonify(resultado)


@app.route("/api/ingles/trilha/completar", methods=["POST"])
@login_required
def ingles_completar_licao():
    data = request.get_json() or {}
    modulo_id = data.get("modulo_id")
    licao_id = data.get("licao_id")
    if not modulo_id or not licao_id:
        return jsonify({"error": "modulo_id e licao_id obrigatórios"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ingles_trilha_progresso (modulo_id, licao_id, status)
            VALUES (%s, %s, 'completed')
            ON CONFLICT (modulo_id, licao_id) DO UPDATE SET status = 'completed', completed_at = NOW()
        """, (int(modulo_id), int(licao_id)))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()
```

### Step 6: Update `ingles_conversar_voz` to use lesson system prompt

Locate it:
```bash
grep -n "def ingles_conversar_voz" /root/jake_desktop/app.py
```

Read ~10 lines from there to find where `system = _INGLES_CONVERSA_SYSTEM.format(tema=tema)` is.

Replace that single line with:
```python
        licao_context = request.form.get("licao_context", "").strip()
        if licao_context:
            system = (
                "You are Jake, an English teacher and conversation partner for a Brazilian at intermediate level.\n"
                "Lesson context: " + licao_context + "\n"
                "Rules: respond ONLY in English. When the student makes grammar mistakes, naturally use the correct form in your response without pointing it out. "
                "Keep replies concise (2-4 sentences). Guide conversation toward the lesson objectives. "
                "You understand Portuguese but always respond in English."
            )
        else:
            system = _INGLES_CONVERSA_SYSTEM.format(tema=tema)
```

### Step 7: Run all tests
```bash
cd /root/jake_desktop && .venv/bin/python -m pytest tests/test_ingles_api.py -v 2>&1 | tail -20
```
Expected: 15 tests pass.

### Step 8: Commit
```bash
cd /root/jake_desktop && git add app.py tests/test_ingles_api.py && git commit -m "feat(trilha): currículo 12 módulos, tabela progresso, rotas trilha"
```

---

## Task 2: Frontend HTML + CSS — aba Trilha

**Files:** `templates/dashboard.html`

### Context
Locate ingles section tabs:
```bash
grep -n "ing-tabs\|ing-tab-btn\|ing-panel-trilha" /root/jake_desktop/templates/dashboard.html | head -10
```

Read from `<div class="ing-tabs">` for ~10 lines to see current tab buttons.

### Step 1: Add 4th tab button

Find:
```html
          <button class="ing-tab-btn" onclick="ingTab('progresso',this)">📈 Progresso</button>
```

Replace with:
```html
          <button class="ing-tab-btn" onclick="ingTab('progresso',this)">📈 Progresso</button>
          <button class="ing-tab-btn" onclick="ingTab('trilha',this)">🗺️ Trilha</button>
```

### Step 2: Add Trilha panel

Find the closing tag of the progresso panel: `</div>` that closes `ing-panel-progresso`. Add after it:

```html
        <!-- ABA TRILHA -->
        <div class="ing-tab-panel" id="ing-panel-trilha">
          <div id="ing-trilha-loading" class="ing-loading">Carregando trilha...</div>
          <div id="ing-trilha-lista"></div>
        </div>
```

### Step 3: Add Trilha CSS

Inside the `<style id="ingles-styles">` block, add before `</style>`:

```css
/* ── TRILHA ─────────────────────────────────────── */
.ing-modulo-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(0,229,255,0.15);
  border-radius: 12px; margin-bottom: 16px; overflow: hidden; }
.ing-modulo-header { padding: 16px 20px; cursor: pointer; display: flex; align-items: center; gap: 12px;
  transition: background 0.2s; }
.ing-modulo-header:hover { background: rgba(0,229,255,0.05); }
.ing-modulo-icone { font-size: 22px; flex-shrink: 0; }
.ing-modulo-info { flex: 1; }
.ing-modulo-titulo { font-family: Orbitron, sans-serif; font-size: 14px; color: #fff; margin-bottom: 2px; }
.ing-modulo-desc { color: #888; font-size: 12px; }
.ing-modulo-prog { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.ing-modulo-prog-text { color: #00e5ff; font-family: Rajdhani, sans-serif; font-size: 13px; font-weight: 700; }
.ing-modulo-prog-bar { width: 60px; height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; overflow: hidden; }
.ing-modulo-prog-fill { height: 100%; background: #00e5ff; border-radius: 2px; transition: width 0.4s; }
.ing-modulo-arrow { color: #555; font-size: 12px; transition: transform 0.2s; }
.ing-modulo-card.open .ing-modulo-arrow { transform: rotate(90deg); }
.ing-licoes-lista { border-top: 1px solid rgba(0,229,255,0.08); display: none; }
.ing-modulo-card.open .ing-licoes-lista { display: block; }
.ing-licao-item { display: flex; align-items: center; gap: 12px; padding: 12px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.04); }
.ing-licao-item:last-child { border-bottom: none; }
.ing-licao-status { width: 20px; height: 20px; border-radius: 50%; border: 2px solid rgba(0,229,255,0.3);
  flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 10px; }
.ing-licao-status.completed { background: #00e5ff; border-color: #00e5ff; color: #000; }
.ing-licao-info { flex: 1; }
.ing-licao-titulo { color: #ddd; font-size: 14px; margin-bottom: 2px; }
.ing-licao-obj { color: #666; font-size: 12px; }
.ing-licao-btn { background: transparent; border: 1px solid rgba(0,229,255,0.3); color: #00e5ff;
  padding: 5px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; font-family: Rajdhani, sans-serif;
  font-weight: 700; white-space: nowrap; transition: all 0.2s; }
.ing-licao-btn:hover { background: rgba(0,229,255,0.1); }
.ing-licao-btn.active-lesson { background: rgba(0,229,255,0.15); border-color: #00e5ff; }
.ing-licao-context { background: rgba(0,229,255,0.06); border: 1px solid rgba(0,229,255,0.2);
  border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; }
.ing-licao-context-label { font-family: Rajdhani, sans-serif; font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 1px; color: #00e5ff; margin-bottom: 4px; }
.ing-licao-context-text { color: #ccc; font-size: 13px; }
.ing-btn-completar { background: rgba(0,229,255,0.1); border: 1px solid rgba(0,229,255,0.4);
  color: #00e5ff; padding: 8px 20px; border-radius: 8px; cursor: pointer;
  font-family: Rajdhani, sans-serif; font-size: 14px; font-weight: 700; align-self: center; transition: all 0.2s; }
.ing-btn-completar:hover { background: rgba(0,229,255,0.2); }
```

### Step 4: Add lesson context area to Conversar panel

In the Conversar panel (`ing-panel-conversar`), find:
```html
            <div class="ing-conversa-area">
```

Replace with:
```html
            <div class="ing-conversa-area">
              <div class="ing-licao-context" id="ing-licao-context" style="display:none">
                <div class="ing-licao-context-label">Lição ativa</div>
                <div class="ing-licao-context-text" id="ing-licao-context-text"></div>
              </div>
```

Also find inside `ing-conversa-actions` div:
```html
                <button class="ing-btn-link" onclick="inglesNovaSessao()">Nova sessão</button>
```
Replace with:
```html
                <button class="ing-btn-completar" id="ing-btn-completar" style="display:none" onclick="ingCompletarLicao()">✓ Concluir lição</button>
                <button class="ing-btn-link" onclick="inglesNovaSessao()">Nova sessão</button>
```

### Step 5: Verify
```bash
grep -c "ing-panel-trilha\|ing-modulo-card\|ing-licao-item\|ing-btn-completar" /root/jake_desktop/templates/dashboard.html
```
Expected: 4 matches.

### Step 6: Commit
```bash
cd /root/jake_desktop && git add templates/dashboard.html && git commit -m "feat(trilha): HTML e CSS da aba Trilha com módulos e lições"
```

---

## Task 3: Frontend JS — Trilha logic

**Files:** `static/js/ingles.js`

### Context
Add to `IState`:
```javascript
var IState = {
  sessaoId: null,
  gravando: false,
  mediaRecorder: null,
  chunks: [],
  silenceCheck: null,
  licaoAtiva: null  // {moduloId, licaoId, titulo, cenario, objetivo}
};
```

### Step 1: Add `ingTab` handler for trilha

Find the `ingTab` function. Add after `if (nome === 'progresso') carregarProgresso();`:
```javascript
    if (nome === 'trilha') carregarTrilha();
```

### Step 2: Add trilha functions

Add these BEFORE the closing `})();` of the IIFE:

```javascript
  // ── Trilha ───────────────────────────────────────
  function carregarTrilha() {
    var loading = document.getElementById('ing-trilha-loading');
    var lista = document.getElementById('ing-trilha-lista');
    if (loading) loading.style.display = 'block';
    if (lista) lista.innerHTML = '';

    fetch('/api/ingles/trilha')
      .then(function (r) { return r.json(); })
      .then(function (modulos) {
        if (loading) loading.style.display = 'none';
        modulos.forEach(function (m) {
          if (lista) lista.insertAdjacentHTML('beforeend', renderModulo(m));
        });
      })
      .catch(function () {
        if (loading) loading.textContent = 'Erro ao carregar trilha.';
      });
  }

  function renderModulo(m) {
    var pct = m.progresso.total > 0 ? Math.round(m.progresso.concluidas / m.progresso.total * 100) : 0;
    var licoesHtml = m.licoes.map(function (l) {
      var done = l.status === 'completed';
      var isAtiva = IState.licaoAtiva && IState.licaoAtiva.moduloId === m.id && IState.licaoAtiva.licaoId === l.id;
      return '<div class="ing-licao-item">' +
        '<div class="ing-licao-status' + (done ? ' completed' : '') + '">' + (done ? '✓' : '') + '</div>' +
        '<div class="ing-licao-info">' +
        '<div class="ing-licao-titulo">' + esc(l.titulo) + '</div>' +
        '<div class="ing-licao-obj">' + esc(l.objetivo) + '</div>' +
        '</div>' +
        '<button class="ing-licao-btn' + (isAtiva ? ' active-lesson' : '') + '" ' +
        'onclick="ingPraticarLicao(' + m.id + ',' + l.id + ',\'' + esc(l.titulo).replace(/'/g,"\\'") + '\',\'' + esc(l.cenario).replace(/'/g,"\\'") + '\',\'' + esc(l.objetivo).replace(/'/g,"\\'") + '\')">' +
        (isAtiva ? '▶ Praticando' : (done ? '↩ Repetir' : '▶ Praticar')) +
        '</button>' +
        '</div>';
    }).join('');

    return '<div class="ing-modulo-card" id="ing-mod-' + m.id + '">' +
      '<div class="ing-modulo-header" onclick="ingToggleModulo(' + m.id + ')">' +
      '<span class="ing-modulo-icone">' + esc(m.icone) + '</span>' +
      '<div class="ing-modulo-info">' +
      '<div class="ing-modulo-titulo">' + m.id + '. ' + esc(m.titulo) + '</div>' +
      '<div class="ing-modulo-desc">' + esc(m.descricao) + '</div>' +
      '</div>' +
      '<div class="ing-modulo-prog">' +
      '<span class="ing-modulo-prog-text">' + m.progresso.concluidas + '/' + m.progresso.total + '</span>' +
      '<div class="ing-modulo-prog-bar"><div class="ing-modulo-prog-fill" style="width:' + pct + '%"></div></div>' +
      '</div>' +
      '<span class="ing-modulo-arrow">▶</span>' +
      '</div>' +
      '<div class="ing-licoes-lista">' + licoesHtml + '</div>' +
      '</div>';
  }

  window.ingToggleModulo = function (id) {
    var card = document.getElementById('ing-mod-' + id);
    if (card) card.classList.toggle('open');
  };

  window.ingPraticarLicao = function (moduloId, licaoId, titulo, cenario, objetivo) {
    IState.licaoAtiva = { moduloId: moduloId, licaoId: licaoId, titulo: titulo, cenario: cenario, objetivo: objetivo };
    IState.trocasMensagens = 0;

    // Show lesson context in Conversar tab
    var ctx = document.getElementById('ing-licao-context');
    var ctxText = document.getElementById('ing-licao-context-text');
    if (ctx) ctx.style.display = 'block';
    if (ctxText) ctxText.textContent = titulo + ' — ' + cenario;

    // Show complete button (hidden until 3 exchanges)
    var btnCompletar = document.getElementById('ing-btn-completar');
    if (btnCompletar) btnCompletar.style.display = 'none';

    // Reset conversation UI
    var jtext = document.getElementById('ing-jake-text');
    if (jtext) jtext.textContent = 'Ready! ' + cenario + ' Start whenever you\'re ready!';
    var ubub = document.getElementById('ing-bubble-user');
    if (ubub) ubub.style.display = 'none';

    // Start new session for this lesson
    IState.sessaoId = null;
    iniciarSessao();

    // Switch to Conversar tab
    document.querySelectorAll('.ing-tab-panel').forEach(function (p) { p.classList.remove('active'); });
    document.querySelectorAll('.ing-tab-btn').forEach(function (b) { b.classList.remove('active'); });
    document.getElementById('ing-panel-conversar').classList.add('active');
    // Mark the Conversar tab button active
    document.querySelectorAll('.ing-tab-btn').forEach(function (b) {
      if (b.textContent.indexOf('Conversar') !== -1) b.classList.add('active');
    });
  };

  window.ingCompletarLicao = function () {
    if (!IState.licaoAtiva) return;
    fetch('/api/ingles/trilha/completar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modulo_id: IState.licaoAtiva.moduloId, licao_id: IState.licaoAtiva.licaoId })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) {
          _ingShowToast('Lição concluída! 🎉', 'success');
          var btnCompletar = document.getElementById('ing-btn-completar');
          if (btnCompletar) btnCompletar.style.display = 'none';
          IState.licaoAtiva = null;
          var ctx = document.getElementById('ing-licao-context');
          if (ctx) ctx.style.display = 'none';
        }
      });
  };
```

### Step 3: Update `IState` declaration

Add `licaoAtiva: null, trocasMensagens: 0` to the IState object at the top.

### Step 4: Update `enviarVoz` to send lesson context

In `enviarVoz` function, find where `fd.append('sessao_id', ...)` is. Add after it:

```javascript
    if (IState.licaoAtiva) {
      fd.append('licao_context', IState.licaoAtiva.cenario + ' | Objetivo: ' + IState.licaoAtiva.objetivo);
    }
```

Also in the `.then` handler of `enviarVoz`, after `if (jtext) jtext.textContent = d.resposta_texto;`, add:

```javascript
        // Show "complete lesson" button after 3 exchanges
        if (IState.licaoAtiva) {
          IState.trocasMensagens = (IState.trocasMensagens || 0) + 1;
          if (IState.trocasMensagens >= 3) {
            var btnCompletar = document.getElementById('ing-btn-completar');
            if (btnCompletar) btnCompletar.style.display = 'block';
          }
        }
```

### Step 5: Verify syntax
```bash
node --check /root/jake_desktop/static/js/ingles.js && echo "OK"
```

### Step 6: Run tests
```bash
cd /root/jake_desktop && .venv/bin/python -m pytest tests/test_ingles_api.py -v 2>&1 | tail -10
```

### Step 7: Commit
```bash
cd /root/jake_desktop && git add static/js/ingles.js && git commit -m "feat(trilha): JS — renderização da trilha, praticar lição, completar"
```

---

## Task 4: Smoke test e push

- [ ] Run tests (all 15 pass)
- [ ] `systemctl restart jake-ia.service`
- [ ] Verify `/api/ingles/trilha` returns 12 modules
- [ ] `git push origin main`
- [ ] Report results
