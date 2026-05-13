# Módulo Rotina — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar módulo "ROTINA" ao Jake OS com checklist diário de hábitos, tracker de maconha, streaks, gráfico semanal e notificações do navegador.

**Architecture:** Novas rotas Flask em `app.py` acessam Neon/PostgreSQL via `_get_db()`. Frontend: nova seção `#page-rotina` no `dashboard.html` + arquivo `static/js/rotina.js`. Estilo inline no próprio JS/HTML seguindo glassmorphism do Jake OS.

**Tech Stack:** Flask, psycopg2, Neon/PostgreSQL, Vanilla JS, CSS glassmorphism (backdrop-filter), Chart.js (já pode estar carregado — verificar), Notification API do navegador.

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `jake_desktop/app.py` | Modificar | Adicionar 6 rotas `/api/rotina/*` + criação das tabelas |
| `jake_desktop/templates/dashboard.html` | Modificar | Adicionar nav-item + `<section id="page-rotina">` + `<script>` |
| `jake_desktop/static/js/rotina.js` | Criar | Toda a lógica do módulo: fetch, render, streaks, gráfico, notificações |
| `jake_desktop/static/js/app.js` | Modificar | Adicionar "rotina" ao array `valid` de rotas |

---

## Task 1: Criar tabelas no banco de dados

**Files:**
- Modify: `jake_desktop/app.py` (adicionar função `_init_rotina_tables()` chamada no startup)

- [ ] **Step 1: Localizar o trecho de inicialização do app em `app.py`**

Procurar por `if __name__ == "__main__"` ou qualquer função de `init_db` existente para entender onde encaixar.

- [ ] **Step 2: Adicionar função `_init_rotina_tables()` em `app.py`**

Inserir logo após a definição de `_get_db()` (linha ~48):

```python
def _init_rotina_tables():
    """Cria as tabelas do módulo Rotina se não existirem."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                icon TEXT DEFAULT '✓',
                active BOOLEAN DEFAULT TRUE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id SERIAL PRIMARY KEY,
                habit_id INTEGER REFERENCES habits(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                completed BOOLEAN DEFAULT FALSE,
                notes TEXT,
                UNIQUE(habit_id, date)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS maconha_log (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                used BOOLEAN DEFAULT TRUE,
                period TEXT CHECK(period IN ('dia','noite')),
                UNIQUE(date, period)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS streaks (
                habit_id INTEGER PRIMARY KEY REFERENCES habits(id) ON DELETE CASCADE,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_updated DATE
            )
        """)
        conn.commit()
        _seed_habits(cur, conn)
    finally:
        conn.close()
```

- [ ] **Step 3: Adicionar função `_seed_habits()` logo abaixo**

```python
def _seed_habits(cur, conn):
    """Popula hábitos iniciais se a tabela estiver vazia."""
    cur.execute("SELECT COUNT(*) as c FROM habits")
    if cur.fetchone()["c"] > 0:
        return
    habits = [
        ("Luz natural ao acordar", "MANHÃ", "☀️"),
        ("500ml água ao acordar", "MANHÃ", "💧"),
        ("Passeio com Odin (manhã)", "MANHÃ", "🐕"),
        ("Café da manhã com proteína", "MANHÃ", "🥚"),
        ("Pausa ativa 10h (sem tela)", "TRABALHO", "🧘"),
        ("Almoço sem tela", "TRABALHO", "🍽️"),
        ("Pausa ativa 15h", "TRABALHO", "🧘"),
        ("Encerrei expediente no horário", "TRABALHO", "✅"),
        ("Treinei (academia/bike/caminhada)", "TARDE/NOITE", "🏋️"),
        ("Jantar leve", "TARDE/NOITE", "🥗"),
        ("30 min fora de tela", "TARDE/NOITE", "🎨"),
        ("Tela OFF às 21h30", "TARDE/NOITE", "📵"),
        ("Dormi no horário", "TARDE/NOITE", "😴"),
        ("Meal prep feito", "SEMANA", "🍳"),
        ("Reserva financeira transferida", "SEMANA", "💰"),
        ("Gastos registrados no app", "SEMANA", "📊"),
    ]
    for name, category, icon in habits:
        cur.execute(
            "INSERT INTO habits (name, category, icon) VALUES (%s, %s, %s)",
            (name, category, icon)
        )
    conn.commit()
```

- [ ] **Step 4: Chamar `_init_rotina_tables()` no startup**

Localizar o bloco `if __name__ == "__main__":` no final de `app.py` e adicionar antes do `app.run(...)`:

```python
_init_rotina_tables()
```

- [ ] **Step 5: Testar criação das tabelas**

```bash
cd /root/jake_desktop && /root/jake_desktop/venv/bin/python -c "from app import _init_rotina_tables; _init_rotina_tables(); print('OK')"
```

Esperado: `OK` sem erros.

- [ ] **Step 6: Commit**

```bash
cd /root/jake_desktop
git add app.py
git commit -m "feat(rotina): criar tabelas habits, habit_logs, maconha_log, streaks"
```

---

## Task 2: Rotas Flask — `/api/rotina/*`

**Files:**
- Modify: `jake_desktop/app.py` (adicionar 6 rotas)

Inserir antes do bloco `if __name__ == "__main__":`.

- [ ] **Step 1: Rota GET `/api/rotina/hoje`**

```python
@app.route("/api/rotina/hoje", methods=["GET"])
@login_required
def rotina_hoje():
    from datetime import date
    today = date.today().isoformat()
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM habits WHERE active = TRUE ORDER BY category, id")
        habits = list(cur.fetchall())
        if not habits:
            return jsonify([])
        ids = [h["id"] for h in habits]
        cur.execute(
            "SELECT habit_id, completed FROM habit_logs WHERE date = %s AND habit_id = ANY(%s)",
            (today, ids)
        )
        logs = {r["habit_id"]: r["completed"] for r in cur.fetchall()}
        cur.execute(
            "SELECT habit_id, current_streak, best_streak FROM streaks WHERE habit_id = ANY(%s)",
            (ids,)
        )
        streaks = {r["habit_id"]: r for r in cur.fetchall()}
        result = []
        for h in habits:
            hid = h["id"]
            result.append({
                "id": hid,
                "name": h["name"],
                "category": h["category"],
                "icon": h["icon"],
                "completed": logs.get(hid, False),
                "current_streak": streaks.get(hid, {}).get("current_streak", 0),
                "best_streak": streaks.get(hid, {}).get("best_streak", 0),
            })
        return jsonify(result)
    finally:
        conn.close()
```

- [ ] **Step 2: Rota POST `/api/rotina/check`**

```python
@app.route("/api/rotina/check", methods=["POST"])
@login_required
def rotina_check():
    from datetime import date, timedelta
    data = request.get_json()
    habit_id = data.get("habit_id")
    log_date = data.get("date", date.today().isoformat())
    completed = data.get("completed", True)
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO habit_logs (habit_id, date, completed)
            VALUES (%s, %s, %s)
            ON CONFLICT (habit_id, date) DO UPDATE SET completed = EXCLUDED.completed
        """, (habit_id, log_date, completed))
        # Recalcular streak
        cur.execute("""
            SELECT date FROM habit_logs
            WHERE habit_id = %s AND completed = TRUE
            ORDER BY date DESC
        """, (habit_id,))
        rows = [r["date"] for r in cur.fetchall()]
        current_streak = 0
        if rows:
            check = date.today()
            for d in rows:
                if d >= check - timedelta(days=1):
                    current_streak += 1
                    check = d
                else:
                    break
        cur.execute("""
            INSERT INTO streaks (habit_id, current_streak, best_streak, last_updated)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (habit_id) DO UPDATE SET
                current_streak = EXCLUDED.current_streak,
                best_streak = GREATEST(streaks.best_streak, EXCLUDED.current_streak),
                last_updated = EXCLUDED.last_updated
        """, (habit_id, current_streak, current_streak, date.today().isoformat()))
        conn.commit()
        return jsonify({"ok": True, "current_streak": current_streak})
    finally:
        conn.close()
```

- [ ] **Step 3: Rota GET `/api/rotina/streaks`**

```python
@app.route("/api/rotina/streaks", methods=["GET"])
@login_required
def rotina_streaks():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT h.id, h.name, h.icon, h.category,
                   COALESCE(s.current_streak, 0) as current_streak,
                   COALESCE(s.best_streak, 0) as best_streak
            FROM habits h
            LEFT JOIN streaks s ON s.habit_id = h.id
            WHERE h.active = TRUE
            ORDER BY s.current_streak DESC NULLS LAST
        """)
        return jsonify(list(cur.fetchall()))
    finally:
        conn.close()
```

- [ ] **Step 4: Rota GET `/api/rotina/semana`**

```python
@app.route("/api/rotina/semana", methods=["GET"])
@login_required
def rotina_semana():
    from datetime import date, timedelta
    today = date.today()
    days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT date::text, COUNT(*) FILTER (WHERE completed = TRUE) as done,
                   COUNT(*) as total
            FROM habit_logs
            WHERE date = ANY(%s)
            GROUP BY date ORDER BY date
        """, (days,))
        logs = {r["date"]: {"done": r["done"], "total": r["total"]} for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) as c FROM habits WHERE active = TRUE")
        total_habits = cur.fetchone()["c"]
        result = []
        for d in days:
            result.append({
                "date": d,
                "done": logs.get(d, {}).get("done", 0),
                "total": total_habits,
            })
        return jsonify(result)
    finally:
        conn.close()
```

- [ ] **Step 5: Rota POST `/api/rotina/maconha`**

```python
@app.route("/api/rotina/maconha", methods=["POST"])
@login_required
def rotina_maconha_post():
    from datetime import date
    data = request.get_json()
    log_date = data.get("date", date.today().isoformat())
    period = data.get("period", "noite")
    used = data.get("used", True)
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO maconha_log (date, used, period)
            VALUES (%s, %s, %s)
            ON CONFLICT (date, period) DO UPDATE SET used = EXCLUDED.used
        """, (log_date, used, period))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()
```

- [ ] **Step 6: Rota GET `/api/rotina/maconha/mes`**

```python
@app.route("/api/rotina/maconha/mes", methods=["GET"])
@login_required
def rotina_maconha_mes():
    from datetime import date
    today = date.today()
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT date::text, period, used FROM maconha_log
            WHERE EXTRACT(MONTH FROM date) = %s AND EXTRACT(YEAR FROM date) = %s
            ORDER BY date DESC
        """, (today.month, today.year))
        return jsonify(list(cur.fetchall()))
    finally:
        conn.close()
```

- [ ] **Step 7: Testar rotas com curl**

```bash
# Reiniciar Jake OS
pkill -f "venv/bin/python app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup ./venv/bin/python app.py > /tmp/jake_os.log 2>&1 &
sleep 2

# Teste básico (sem auth — espera 401 ou redirect, não 500)
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/api/rotina/hoje
```

Esperado: `302` ou `401` (rota existe, apenas redireciona para login).

- [ ] **Step 8: Commit**

```bash
cd /root/jake_desktop
git add app.py
git commit -m "feat(rotina): adicionar 6 rotas API /api/rotina/*"
```

---

## Task 3: Frontend — `rotina.js`

**Files:**
- Create: `jake_desktop/static/js/rotina.js`

- [ ] **Step 1: Criar `rotina.js` com estrutura base**

```javascript
// rotina.js — Módulo Rotina Jake OS
(function () {
  "use strict";

  // ── CONFIG ──────────────────────────────────────────────
  const INICIO_PLANO = localStorage.getItem("rotina_inicio") || new Date().toISOString().slice(0, 10);
  if (!localStorage.getItem("rotina_inicio")) {
    localStorage.setItem("rotina_inicio", INICIO_PLANO);
  }

  const NOTIF_SCHEDULE = [
    { h: 6,  m: 0,  msg: "Bom dia. Odin tá esperando 🐕" },
    { h: 10, m: 0,  msg: "Pausa ativa — sai da tela por 10 min" },
    { h: 12, m: 30, msg: "Almoço sem celular 🍽️" },
    { h: 15, m: 0,  msg: "Pausa ativa — água e estica 💧" },
    { h: 17, m: 30, msg: "Hora do treino 🏋️" },
    { h: 21, m: 0,  msg: "Começa a desacelerar — última rede social" },
    { h: 21, m: 30, msg: "TELA OFF — coloca o celular pra dormir 📵" },
  ];

  // ── HELPERS ─────────────────────────────────────────────
  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function semanaAtual() {
    const inicio = new Date(INICIO_PLANO);
    const agora = new Date();
    const diff = Math.floor((agora - inicio) / (1000 * 60 * 60 * 24 * 7));
    return Math.min(diff + 1, 4);
  }

  function metaSemana(semana) {
    const metas = [
      "Não usar antes das 18h",
      "Só terça + quinta + FDS",
      "Só quinta à noite + FDS",
      "Só sexta após 18h + FDS ✅",
    ];
    return metas[Math.min(semana - 1, 3)];
  }

  function saudacao() {
    const h = new Date().getHours();
    if (h < 12) return "Bom dia";
    if (h < 18) return "Boa tarde";
    return "Boa noite";
  }

  function formatDate(iso) {
    const [y, m, d] = iso.split("-");
    return `${d}/${m}`;
  }

  // ── NOTIFICAÇÕES ─────────────────────────────────────────
  function agendarNotificacoes() {
    if (!("Notification" in window)) return;
    if (Notification.permission === "denied") return;
    if (Notification.permission === "default") {
      Notification.requestPermission();
      return;
    }
    const agora = new Date();
    NOTIF_SCHEDULE.forEach(({ h, m, msg }) => {
      const alvo = new Date();
      alvo.setHours(h, m, 0, 0);
      let delay = alvo - agora;
      if (delay < 0) delay += 24 * 60 * 60 * 1000;
      setTimeout(() => {
        new Notification("Jake OS — Rotina", { body: msg, icon: "/static/img/jake-icon.png" });
      }, delay);
    });
  }

  // ── RENDER CHECKLIST ────────────────────────────────────
  function renderChecklist(habits) {
    const container = document.getElementById("rot-checklist");
    if (!container) return;

    const byCategory = {};
    habits.forEach((h) => {
      if (!byCategory[h.category]) byCategory[h.category] = [];
      byCategory[h.category].push(h);
    });

    const categoryOrder = ["MANHÃ", "TRABALHO", "TARDE/NOITE", "SEMANA"];
    let html = "";

    categoryOrder.forEach((cat) => {
      const items = byCategory[cat];
      if (!items) return;
      html += `
        <div class="rot-category">
          <div class="rot-cat-label">${cat}</div>
          <div class="rot-habits-grid">
      `;
      items.forEach((h) => {
        const done = h.completed;
        html += `
          <div class="rot-habit-card ${done ? "done" : ""}" data-id="${h.id}">
            <button class="rot-toggle" onclick="rotinaToggle(${h.id}, ${!done})">
              <span class="rot-icon">${h.icon}</span>
              <span class="rot-name">${h.name}</span>
              <span class="rot-check">${done ? "✓" : ""}</span>
            </button>
            ${h.current_streak > 1
              ? `<span class="rot-streak">🔥 ${h.current_streak}</span>`
              : ""}
          </div>
        `;
      });
      html += `</div></div>`;
    });

    container.innerHTML = html;
  }

  // ── TOGGLE HÁBITO ───────────────────────────────────────
  window.rotinaToggle = function (habitId, completed) {
    fetch("/api/rotina/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ habit_id: habitId, date: today(), completed }),
    })
      .then((r) => r.json())
      .then((data) => {
        rotinaLoad();
      });
  };

  // ── TRACKER MACONHA ─────────────────────────────────────
  function renderMaconha(logs) {
    const semana = semanaAtual();
    const meta = metaSemana(semana);
    const container = document.getElementById("rot-maconha");
    if (!container) return;

    // Dias da semana atual (últimos 7)
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      days.push(d.toISOString().slice(0, 10));
    }

    const logMap = {};
    logs.forEach((l) => { logMap[l.date] = l; });

    const diasHtml = days.map((d) => {
      const used = logMap[d]?.used;
      const label = formatDate(d);
      return `<div class="rot-mac-day ${used === true ? "used" : used === false ? "clean" : ""}">
        <span>${label}</span>
        <span>${used === true ? "🚬" : used === false ? "✓" : "—"}</span>
      </div>`;
    }).join("");

    // Progresso: semana 1→4, cor vermelho→verde
    const pct = Math.min((semana / 4) * 100, 100);
    const cor = semana >= 4 ? "#00e5ff" : semana === 3 ? "#8bc34a" : semana === 2 ? "#ff9800" : "#ff5252";

    container.innerHTML = `
      <div class="rot-mac-header">
        <span class="rot-mac-title">🌿 Tracker — Gerenciamento</span>
        <span class="rot-mac-semana">Semana ${semana}/4</span>
      </div>
      <div class="rot-mac-meta">Meta: <strong>${meta}</strong></div>
      <div class="rot-mac-progress">
        <div class="rot-mac-bar" style="width:${pct}%;background:${cor}"></div>
      </div>
      <div class="rot-mac-days">${diasHtml}</div>
      <button class="rot-mac-btn" onclick="rotinaMaconhaLog()">Registrar uso hoje</button>
    `;
  }

  window.rotinaMaconhaLog = function () {
    const period = new Date().getHours() < 18 ? "dia" : "noite";
    fetch("/api/rotina/maconha", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: today(), period, used: true }),
    }).then(() => rotinaLoadMaconha());
  };

  // ── GRÁFICO SEMANAL ─────────────────────────────────────
  function renderGrafico(semanaData) {
    const container = document.getElementById("rot-chart-wrap");
    if (!container) return;

    const labels = semanaData.map((d) => formatDate(d.date));
    const valores = semanaData.map((d) => d.total > 0 ? Math.round((d.done / d.total) * 100) : 0);

    const bars = valores.map((v, i) => {
      const cor = v >= 80 ? "#00e5ff" : v >= 50 ? "#8bc34a" : "#ff9800";
      return `
        <div class="rot-bar-wrap">
          <div class="rot-bar" style="height:${v}%;background:${cor}" title="${v}%">
            <span class="rot-bar-val">${v}%</span>
          </div>
          <span class="rot-bar-label">${labels[i]}</span>
        </div>
      `;
    }).join("");

    container.innerHTML = `<div class="rot-bars">${bars}</div>`;
  }

  // ── STREAKS PANEL ───────────────────────────────────────
  function renderStreaks(streaks) {
    const container = document.getElementById("rot-streaks");
    if (!container) return;

    const top = streaks.filter((s) => s.current_streak > 0).slice(0, 8);
    if (!top.length) {
      container.innerHTML = `<p class="rot-empty">Nenhum streak ativo ainda. Comece hoje!</p>`;
      return;
    }

    container.innerHTML = top.map((s) => `
      <div class="rot-streak-card">
        <span class="rot-streak-icon">${s.icon}</span>
        <span class="rot-streak-name">${s.name}</span>
        <span class="rot-streak-num">🔥 ${s.current_streak}</span>
      </div>
    `).join("");
  }

  // ── LOAD FUNCTIONS ───────────────────────────────────────
  function rotinaLoad() {
    fetch("/api/rotina/hoje")
      .then((r) => r.json())
      .then((data) => renderChecklist(data));

    fetch("/api/rotina/streaks")
      .then((r) => r.json())
      .then((data) => renderStreaks(data));

    fetch("/api/rotina/semana")
      .then((r) => r.json())
      .then((data) => renderGrafico(data));
  }

  function rotinaLoadMaconha() {
    fetch("/api/rotina/maconha/mes")
      .then((r) => r.json())
      .then((data) => renderMaconha(data));
  }

  // Expor saudacao para uso externo (hook inline no dashboard.html)
  window._rotSaudacao = saudacao;

  // ── INIT ────────────────────────────────────────────────
  window.rotinaInit = function () {
    rotinaLoad();
    rotinaLoadMaconha();
    agendarNotificacoes();
  };
})();
```

- [ ] **Step 2: Commit**

```bash
cd /root/jake_desktop
git add static/js/rotina.js
git commit -m "feat(rotina): adicionar rotina.js com checklist, maconha, streaks, gráfico, notificações"
```

---

## Task 4: HTML — seção `#page-rotina` + CSS inline + nav-item

**Files:**
- Modify: `jake_desktop/templates/dashboard.html`

- [ ] **Step 1: Adicionar nav-item no sidebar**

Localizar o nav-item do financeiro (linha ~29) e adicionar logo abaixo:

```html
        <a class="nav-item" data-page="rotina" href="#">
          <span class="nav-icon">🔄</span>
          <span class="nav-label">Rotina</span>
        </a>
```

- [ ] **Step 2: Adicionar `<section id="page-rotina">` antes do `</main>` ou após `page-financeiro`**

Inserir após a seção `page-prompts` (ou antes do `</main>`):

```html
      <!-- ========== ROTINA ========== -->
      <section class="page" id="page-rotina" style="display:none">
        <div class="rot-page">

          <!-- HEADER -->
          <div class="rot-header">
            <div>
              <div id="rot-saudacao" class="rot-saudacao"></div>
              <div id="rot-data" class="rot-data"></div>
            </div>
            <div class="rot-header-badge">Jake Rotina</div>
          </div>

          <div class="rot-grid">

            <!-- CHECKLIST -->
            <div class="rot-col-main">
              <div class="rot-section-title">📋 Checklist do Dia</div>
              <div id="rot-checklist">
                <div class="rot-loading">Carregando hábitos...</div>
              </div>
            </div>

            <!-- SIDEBAR -->
            <div class="rot-col-side">

              <!-- TRACKER MACONHA -->
              <div id="rot-maconha" class="rot-glass-card">
                <div class="rot-loading">Carregando tracker...</div>
              </div>

              <!-- STREAKS -->
              <div class="rot-glass-card">
                <div class="rot-section-title">🔥 Streaks Ativos</div>
                <div id="rot-streaks">
                  <div class="rot-loading">Carregando streaks...</div>
                </div>
              </div>

              <!-- GRÁFICO SEMANAL -->
              <div class="rot-glass-card">
                <div class="rot-section-title">📊 Últimos 7 Dias</div>
                <div id="rot-chart-wrap" class="rot-chart-wrap"></div>
              </div>

            </div>
          </div>

        </div>
      </section>
```

- [ ] **Step 3: Adicionar CSS inline no `<style>` do dashboard ou no `<head>`**

Inserir no `<head>` do `dashboard.html` após os outros `<link>` de CSS:

```html
      <style id="rotina-styles">
        /* ── ROTINA MODULE ──────────────────────── */
        .rot-page { padding: 32px; min-height: 100vh; }
        .rot-header {
          display: flex; justify-content: space-between; align-items: center;
          margin-bottom: 32px;
        }
        .rot-saudacao { font-family: 'Orbitron', sans-serif; font-size: 1.4rem; color: #00e5ff; }
        .rot-data { font-size: 0.85rem; color: rgba(255,255,255,0.4); margin-top: 4px; }
        .rot-header-badge {
          font-family: 'Rajdhani', sans-serif; font-size: 0.75rem; letter-spacing: 2px;
          text-transform: uppercase; color: #00e5ff; border: 1px solid rgba(0,229,255,0.3);
          padding: 6px 14px; border-radius: 20px;
        }
        .rot-grid { display: grid; grid-template-columns: 1fr 360px; gap: 24px; align-items: start; }
        .rot-glass-card {
          background: rgba(255,255,255,0.04);
          backdrop-filter: blur(12px);
          border: 1px solid rgba(0,229,255,0.12);
          border-radius: 12px;
          padding: 20px;
          margin-bottom: 20px;
        }
        .rot-section-title {
          font-family: 'Rajdhani', sans-serif; font-size: 0.8rem; letter-spacing: 2px;
          text-transform: uppercase; color: #00e5ff; margin-bottom: 16px;
        }
        .rot-category { margin-bottom: 28px; }
        .rot-cat-label {
          font-size: 0.7rem; letter-spacing: 3px; text-transform: uppercase;
          color: rgba(0,229,255,0.5); margin-bottom: 10px; padding-left: 4px;
        }
        .rot-habits-grid { display: flex; flex-direction: column; gap: 8px; }
        .rot-habit-card {
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 8px; overflow: hidden;
          transition: all 0.2s ease; position: relative;
        }
        .rot-habit-card.done {
          background: rgba(0,229,255,0.06);
          border-color: rgba(0,229,255,0.2);
        }
        .rot-toggle {
          width: 100%; background: none; border: none; cursor: pointer;
          display: flex; align-items: center; gap: 12px;
          padding: 12px 16px; text-align: left; color: #fff;
        }
        .rot-icon { font-size: 1.1rem; width: 24px; }
        .rot-name { flex: 1; font-family: 'Rajdhani', sans-serif; font-size: 0.95rem; }
        .rot-habit-card.done .rot-name { color: rgba(255,255,255,0.5); text-decoration: line-through; }
        .rot-check { color: #00e5ff; font-size: 1rem; font-weight: bold; }
        .rot-streak {
          position: absolute; right: 12px; bottom: 8px;
          font-size: 0.7rem; color: #ff7043;
        }
        /* Maconha tracker */
        .rot-mac-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
        .rot-mac-title { font-family: 'Rajdhani',sans-serif; font-size: 0.85rem; letter-spacing: 1px; color: #00e5ff; }
        .rot-mac-semana { font-size: 0.75rem; color: rgba(255,255,255,0.4); }
        .rot-mac-meta { font-size: 0.8rem; color: rgba(255,255,255,0.6); margin-bottom: 12px; }
        .rot-mac-meta strong { color: #fff; }
        .rot-mac-progress {
          height: 4px; background: rgba(255,255,255,0.1);
          border-radius: 2px; margin-bottom: 16px; overflow: hidden;
        }
        .rot-mac-bar { height: 100%; border-radius: 2px; transition: width 0.5s ease; }
        .rot-mac-days { display: flex; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
        .rot-mac-day {
          flex: 1; min-width: 36px; text-align: center;
          padding: 6px 4px; border-radius: 6px; font-size: 0.7rem;
          background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08);
          display: flex; flex-direction: column; gap: 4px;
        }
        .rot-mac-day.used { background: rgba(255,82,82,0.15); border-color: rgba(255,82,82,0.3); }
        .rot-mac-day.clean { background: rgba(0,229,255,0.1); border-color: rgba(0,229,255,0.3); }
        .rot-mac-btn {
          width: 100%; padding: 10px; background: rgba(0,229,255,0.1);
          border: 1px solid rgba(0,229,255,0.3); border-radius: 8px;
          color: #00e5ff; font-family: 'Rajdhani',sans-serif; font-size: 0.85rem;
          letter-spacing: 1px; cursor: pointer; transition: all 0.2s;
        }
        .rot-mac-btn:hover { background: rgba(0,229,255,0.2); }
        /* Streaks */
        .rot-streak-card {
          display: flex; align-items: center; gap: 10px;
          padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .rot-streak-card:last-child { border-bottom: none; }
        .rot-streak-icon { width: 24px; }
        .rot-streak-name { flex: 1; font-size: 0.85rem; color: rgba(255,255,255,0.7); }
        .rot-streak-num { color: #ff7043; font-weight: bold; font-size: 0.9rem; }
        /* Gráfico */
        .rot-chart-wrap { }
        .rot-bars { display: flex; gap: 8px; align-items: flex-end; height: 120px; }
        .rot-bar-wrap { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; height: 100%; justify-content: flex-end; }
        .rot-bar { width: 100%; border-radius: 4px 4px 0 0; min-height: 4px; position: relative; transition: height 0.4s ease; }
        .rot-bar-val { position: absolute; top: -18px; left: 50%; transform: translateX(-50%); font-size: 0.65rem; color: rgba(255,255,255,0.5); white-space: nowrap; }
        .rot-bar-label { font-size: 0.65rem; color: rgba(255,255,255,0.3); }
        .rot-loading { color: rgba(255,255,255,0.3); font-size: 0.85rem; padding: 12px 0; }
        .rot-empty { color: rgba(255,255,255,0.3); font-size: 0.85rem; }
        @media (max-width: 900px) {
          .rot-grid { grid-template-columns: 1fr; }
          .rot-col-side { order: -1; }
        }
      </style>
```

- [ ] **Step 4: Adicionar script tag no final do body e chamar `rotinaInit` ao entrar na página**

No final do `<body>`, após os outros `<script src=...>`, adicionar:

```html
  <script src="{{ url_for('static', filename='js/rotina.js') }}"></script>
```

Localizar a função `showPage` em `app.js` — ela já está definida e apenas esconde/mostra seções. Adicionar chamada ao init no `dashboard.html` inline:

```html
  <script>
    // Hook rotina init
    (function(){
      var _origShow = window._showPage || null;
      document.querySelectorAll('.nav-item').forEach(function(item){
        item.addEventListener('click', function(){
          if(this.dataset.page === 'rotina' && typeof rotinaInit === 'function'){
            setTimeout(rotinaInit, 50);
            // Header dinâmico
            var s = document.getElementById('rot-saudacao');
            var d = document.getElementById('rot-data');
            if(s) s.textContent = window._rotSaudacao ? window._rotSaudacao() : '';
            if(d) d.textContent = new Date().toLocaleDateString('pt-BR', {weekday:'long', day:'numeric', month:'long'});
          }
        });
      });
      // Se carregar direto no hash
      if(location.hash === '#rotina' && typeof rotinaInit === 'function'){
        setTimeout(rotinaInit, 200);
      }
    })();
  </script>
```

- [ ] **Step 5: Commit**

```bash
cd /root/jake_desktop
git add templates/dashboard.html
git commit -m "feat(rotina): adicionar seção HTML, CSS e nav-item do módulo rotina"
```

---

## Task 5: Registrar rota no router do `app.js`

**Files:**
- Modify: `jake_desktop/static/js/app.js`

- [ ] **Step 1: Adicionar "rotina" ao array `valid`**

Localizar linha:
```javascript
var valid = ["painel","architect","performance","anuncios","copys","criativos","relatorios","carrossel","prompts","financeiro","agenda"];
```

Substituir por:
```javascript
var valid = ["painel","architect","performance","anuncios","copys","criativos","relatorios","carrossel","prompts","financeiro","agenda","rotina"];
```

- [ ] **Step 2: Commit**

```bash
cd /root/jake_desktop
git add static/js/app.js
git commit -m "feat(rotina): registrar rota #/rotina no router do app.js"
```

---

## Task 6: Teste de integração + deploy

- [ ] **Step 1: Reiniciar Jake OS**

```bash
pkill -f "venv/bin/python app.py" 2>/dev/null
sleep 1
cd /root/jake_desktop && nohup ./venv/bin/python app.py > /tmp/jake_os.log 2>&1 &
sleep 3
echo "Jake OS rodando"
```

- [ ] **Step 2: Verificar log de inicialização**

```bash
tail -20 /tmp/jake_os.log
```

Esperado: sem erros, `Running on http://0.0.0.0:5050`.

- [ ] **Step 3: Verificar rotas existem**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/api/rotina/hoje
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/api/rotina/streaks
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/api/rotina/semana
```

Esperado: `302` ou `401` para todas (login_required funcionando).

- [ ] **Step 4: Abrir no browser e navegar para #rotina**

Acessar `http://localhost:5050/#rotina` — verificar:
- Nav-item "Rotina" aparece no sidebar
- Seção carrega com header, checklist, tracker de maconha, streaks e gráfico
- Toggle de hábito funciona (marcar/desmarcar)
- Botão "Registrar uso hoje" funciona

- [ ] **Step 5: Commit final**

```bash
cd /root/jake_desktop
git add -A
git commit -m "feat(rotina): módulo completo integrado ao Jake OS"
```
