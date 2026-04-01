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
      .then(() => { rotinaLoad(); });
  };

  // ── TRACKER MACONHA ─────────────────────────────────────
  function renderMaconha(logs) {
    const semana = semanaAtual();
    const meta = metaSemana(semana);
    const container = document.getElementById("rot-maconha");
    if (!container) return;

    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      days.push(d.toISOString().slice(0, 10));
    }

    const logMap = {};
    logs.forEach((l) => { logMap[l.date] = l; });

    const diasHtml = days.map((d) => {
      const used = logMap[d] ? logMap[d].used : undefined;
      const label = formatDate(d);
      return `<div class="rot-mac-day ${used === true ? "used" : used === false ? "clean" : ""}">
        <span>${label}</span>
        <span>${used === true ? "🚬" : used === false ? "✓" : "—"}</span>
      </div>`;
    }).join("");

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
    })
      .then(() => rotinaLoadMaconha())
      .catch((e) => console.error("Erro ao registrar uso:", e));
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
      .then((data) => renderChecklist(data))
      .catch((e) => console.error("Erro ao carregar hábitos:", e));

    fetch("/api/rotina/streaks")
      .then((r) => r.json())
      .then((data) => renderStreaks(data))
      .catch((e) => console.error("Erro ao carregar streaks:", e));

    fetch("/api/rotina/semana")
      .then((r) => r.json())
      .then((data) => renderGrafico(data))
      .catch((e) => console.error("Erro ao carregar semana:", e));
  }

  function rotinaLoadMaconha() {
    fetch("/api/rotina/maconha/mes")
      .then((r) => r.json())
      .then((data) => renderMaconha(data))
      .catch((e) => console.error("Erro ao carregar maconha:", e));
  }

  // Expor saudacao para uso externo
  window._rotSaudacao = saudacao;

  // ── INIT ────────────────────────────────────────────────
  window.rotinaInit = function () {
    rotinaLoad();
    rotinaLoadMaconha();
    agendarNotificacoes();
  };
})();
