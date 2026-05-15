/* ══════════════════════════════════════════════════════
   Jake OS — Módulo: Análise de Performance
   Dashboard por agência + drill-down por cliente + alertas
══════════════════════════════════════════════════════ */
(function () {

  /* ── Config de clientes (espelho do relatorios.js) ── */
  var AGENCIES = {
    piloti: [
      { id: "act_3790140084580806", name: "Infinita Hiperbárica" },
      { id: "act_465321557197081",  name: "MR Runners"           },
      { id: "act_1076847820195449", name: "Saucker"              },
      { id: "act_1095710212746155", name: "Daniele Taveira"      },
      { id: "act_1006436427517079", name: "IOB"                  },
      { id: "act_126503999415274",  name: "Isac Academia"        },
      { id: "act_812220691454430",  name: "Maíra Castaldi"       },
      { id: "act_507545471090485",  name: "Odonto Uberaba"       },
      { id: "act_323137203122197",  name: "Queen Poltronas"      },
      { id: "act_840594572249284",  name: "RD Contabilidade"     },
      { id: "act_7838846752907408", name: "Realize Sorrisos"     },
      { id: "act_510054631964792",  name: "RunWay"               }
    ],
    dentto: []
  };

  var currentAgency = "piloti";
  var _rowData = {};  // account_id -> {insights, saldo}
  var _initialized = false;

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

    // Fetch paralelo real: insights e saldo simultaneamente por cliente
    list.forEach(function(c) {
      _rowData[c.id] = {insights: undefined, saldo: undefined};
      function _tryUpdate() {
        if (_rowData[c.id].insights !== undefined && _rowData[c.id].saldo !== undefined) {
          updateRow(agency, c, _rowData[c.id].insights, _rowData[c.id].saldo);
          updateGlobalCards(agency);
        }
      }
      fetchInsights(agency, c.id, function(err, ins) {
        _rowData[c.id].insights = err ? null : ins;
        _tryUpdate();
      });
      fetchSaldo(agency, c.id, function(errS, sal) {
        _rowData[c.id].saldo = errS ? {error: errS} : sal;
        _tryUpdate();
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
    var perfTab = document.getElementById("gestor-tab-performance");
    if (!perfTab) return;

    renderTable(currentAgency);

    if (!_initialized) {
      _initialized = true;

      // Tabs de agência
      perfTab.querySelectorAll(".rel-tab").forEach(function(tab) {
        tab.addEventListener("click", function() {
          perfTab.querySelectorAll(".rel-tab").forEach(function(t) { t.classList.remove("active"); });
          tab.classList.add("active");
          currentAgency = tab.dataset.agency;
          renderTable(currentAgency);
        });
      });

      // Clique na tabela (detalhe)
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
  }

  // Expor para gestorSwitchTab chamar quando ativa a aba Performance
  window.perfInit = init;

})();
