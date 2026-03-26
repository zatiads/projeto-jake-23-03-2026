/* ══════════════════════════════════════════════════════
   Jake IA — Módulo: Envio de Relatórios
   Templates exatos por cliente + Meta API + IA (Claude)
══════════════════════════════════════════════════════ */

(function () {

  /* ── Clientes reais (ordem alfabética) ──────────── */
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

  /* ── Helpers de formatação ───────────────────────── */
  function fmtN(n)   { return parseInt(n || 0, 10).toLocaleString("pt-BR"); }
  function brl(v)    { return parseFloat(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function custo(spend, count) {
    return (count && count > 0) ? "R$ " + brl(spend / count) : "R$ 0,00";
  }

  /* ── Google Ads — zerado até integração ─────────── */
  var G = { imp: 0, cli: 0, conv: 0, cust: "R$ 0,00", alc: 0, ctr: "0,00%", cpc: "R$ 0,00" };

  /* ══════════════════════════════════════════════════
     TEMPLATES POR CLIENTE
     Cada função recebe (m = meta insights, ai = texto IA)
     e retorna o texto final a ser copiado.
  ══════════════════════════════════════════════════ */
  var REPORTS = {

    /* ── RunWay ─────────────────────────────────── */
    "act_510054631964792": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!",
        "Segue relatório das nossas campanhas nos últimos 7 dias:",
        "",
        "RunWay",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯 Leads: " + (m.messaging || 0),
        "💰Custo por lead: " + custo(s, m.messaging),
        "",
        "Google",
        "",
        "👥Impressões: " + fmtN(G.imp),
        "▶️Cliques: " + fmtN(G.cli),
        "🎯Conversão (Clique botão WhatsApp): " + fmtN(G.conv),
        "💰Custo por conversão: " + G.cust,
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos🙏"
      ].join("\n");
    },

    /* ── Queen Poltronas ─────────────────────────── */
    "act_323137203122197": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!",
        "Segue relatório das nossas campanhas nos últimos 7 dias:",
        "",
        "Queen",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯 Leads: " + (m.messaging || 0),
        "💰Custo por lead: " + custo(s, m.messaging),
        "",
        "Google",
        "",
        "👥Impressões: " + fmtN(G.imp),
        "▶️Cliques: " + fmtN(G.cli),
        "🎯Conversão (Clique botão WhatsApp): " + fmtN(G.conv),
        "💰Custo por conversão: " + G.cust,
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos🙏"
      ].join("\n");
    },

    /* ── IOB ─────────────────────────────────────── */
    "act_1006436427517079": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!",
        "Segue relatório das nossas campanhas nos últimos 7 dias:",
        "",
        "IOB",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯 Vistas ao perfil: " + fmtN(m.clicks),
        "💰Custo por visita ao perfil: " + custo(s, m.clicks),
        "",
        "Google",
        "",
        "👥Impressões: " + fmtN(G.imp),
        "▶️Cliques: " + fmtN(G.cli),
        "🎯Conversão (Clique botão WhatsApp): " + fmtN(G.conv),
        "💰Custo por conversão: " + G.cust,
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos🙏"
      ].join("\n");
    },

    /* ── Maíra Castaldi ──────────────────────────── */
    "act_812220691454430": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!",
        "Segue relatório das nossas campanhas nos últimos 7 dias:",
        "",
        "Maíra Castaldi",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯 Visitas ao perfil: " + (m.profile_visits || 0),
        "💰Custo por visita ao perfi: " + custo(s, m.profile_visits),
        "",
        "Google",
        "",
        "👥Impressões: " + fmtN(G.imp),
        "▶️Cliques: " + fmtN(G.cli),
        "🎯Conversão (Clique botão WhatsApp): " + fmtN(G.conv),
        "💰Custo por conversão: " + G.cust,
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos🙏"
      ].join("\n");
    },

    /* ── Isac Academia ───────────────────────────── */
    "act_126503999415274": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!",
        "Segue relatório das nossas campanhas nos últimos 7 dias:",
        "",
        "Isac Rocha",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯Mensagens: " + (m.messaging || 0),
        "💰Custo por mensagem: " + custo(s, m.messaging),
        "",
        "Google",
        "👥Alcance: " + fmtN(G.alc),
        "🎯Cliques: " + fmtN(G.cli),
        "🎯Taxa de cliques: " + G.ctr,
        "💰Custo por clique: " + G.cpc,
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos!🙏"
      ].join("\n");
    },

    /* ── Calixta ─────────────────────────────────── */
    "act_1006820257491698": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!",
        "Segue relatório das nossas campanhas últimos 7 dias:",
        "",
        "Calixta",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯Leads: " + (m.messaging || 0),
        "💰Custo por lead: " + custo(s, m.messaging),
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos!🙏"
      ].join("\n");
    },

    /* ── HiperClin ───────────────────────────────── */
    "act_5684689948235819": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!!",
        "Segue relatório das nossas campanhas:",
        "",
        "HiperClin",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯Leads: " + (m.messaging || 0),
        "💰Custo por lead: " + custo(s, m.messaging),
        "",
        "Google",
        "👥Alcance: " + fmtN(G.alc),
        "▶️Cliques: " + fmtN(G.cli),
        "▶️Taxa de cliques: " + G.ctr,
        "💰Custo por clique: " + G.cpc,
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos!🙏"
      ].join("\n");
    },

    /* ── RD Contabilidade ────────────────────────── */
    "act_840594572249284": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!!",
        "Segue relatório das nossas campanhas:",
        "",
        "RD Contabilidade",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯 Visitas ao perfil: " + (m.profile_visits || 0),
        "💰Custo por visita ao perfi: " + custo(s, m.profile_visits),
        "",
        "Google",
        "👥Alcance: " + fmtN(G.alc),
        "▶️Cliques: " + fmtN(G.cli),
        "▶️Taxa de cliques: " + G.ctr,
        "💰Custo por clique: " + G.cpc,
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos!🙏"
      ].join("\n");
    },

    /* ── Daniele Taveira ─────────────────────────── */
    "act_1095710212746155": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!!",
        "Segue relatório das nossas campanhas:",
        "",
        "Daniele Taveira",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯 Visitas ao perfil: " + (m.profile_visits || 0),
        "💰Custo por visita ao perfi: " + custo(s, m.profile_visits),
        "",
        "Google",
        "👥Alcance: " + fmtN(G.alc),
        "▶️Cliques: " + fmtN(G.cli),
        "▶️Taxa de cliques: " + G.ctr,
        "💰Custo por clique: " + G.cpc,
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos!🙏"
      ].join("\n");
    },

    /* ── 61 eventos ──────────────────────────────── */
    "act_712297048202295": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!",
        "Segue relatório das nossas campanhas nos últimos 7 dias:",
        "",
        "61 Eventos",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯 Visitas ao perfil: " + (m.profile_visits || 0),
        "💰Custo por visita ao perfi: " + custo(s, m.profile_visits),
        "",
        "Google",
        "",
        "👥Impressões: " + fmtN(G.imp),
        "▶️Cliques: " + fmtN(G.cli),
        "🎯Conversão (Clique botão WhatsApp): " + fmtN(G.conv),
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos🙏"
      ].join("\n");
    },

    /* ── Odonto Uberaba ──────────────────────────── */
    "act_507545471090485": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal! ",
        "Segue relatório das nossas campanhas nos últimos 7 dias:",
        "",
        "Odonto Uberaba",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "🎯 Leads: " + (m.messaging || 0),
        "Custo por lead: R$ " + brl(s > 0 && m.messaging > 0 ? s / m.messaging : 0),
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos!🙏"
      ].join("\n");
    },

    /* ── Realize Sorrisos ────────────────────────── */
    "act_7838846752907408": function (m, ai) {
      var s = parseFloat(m.spend || 0);
      return [
        "Boa tarde pessoal!",
        "Segue relatório das nossas campanhas nos últimos 7 dias:",
        "",
        "Realize Sorrisos",
        "",
        "Meta",
        "👥Alcance: " + fmtN(m.reach),
        "▶️Cliques: " + fmtN(m.clicks),
        "",
        "🎯 Leads: " + (m.messaging || 0),
        "💰Custo por lead: R$ " + brl(s > 0 && m.messaging > 0 ? s / m.messaging : 0),
        "",
        "🎯 Visitas ao perfil: " + (m.profile_visits || 0),
        "💰Custo por visita ao perfi: " + custo(s, m.profile_visits),
        "",
        "Google",
        "",
        "👥Impressões: " + fmtN(G.imp),
        "▶️Cliques: " + fmtN(G.cli),
        "🎯Conversão (Clique botão WhatsApp): " + fmtN(G.conv),
        "💰Custo por conversão: " + G.cust,
        "",
        "*" + (ai || "Análise não disponível."),
        "",
        "Boa semana a todos🙏"
      ].join("\n");
    }

  }; // fim REPORTS

  /* ── Template genérico (Amanda, Marcus, etc.) ─── */
  function genericReport(client, m, ai) {
    var s = parseFloat(m.spend || 0);
    var lines = [
      "Boa tarde pessoal!",
      "Segue relatório das nossas campanhas nos últimos 7 dias:",
      "",
      client.name,
      "",
      "Meta",
      "👥Alcance: " + fmtN(m.reach),
      "▶️Cliques: " + fmtN(m.clicks)
    ];
    if (m.messaging > 0) {
      lines.push("🎯Leads: " + m.messaging);
      lines.push("💰Custo por lead: " + custo(s, m.messaging));
    } else if (m.profile_visits > 0) {
      lines.push("🎯Visitas ao perfil: " + m.profile_visits);
      lines.push("💰Custo por visita: " + custo(s, m.profile_visits));
    } else if (m.messaging > 0) {
      lines.push("🎯Mensagens: " + m.messaging);
      lines.push("💰Custo por mensagem: " + custo(s, m.messaging));
    }
    lines.push("");
    lines.push("*" + (ai || "Análise não disponível."));
    lines.push("");
    lines.push("Boa semana a todos!🙏");
    return lines.join("\n");
  }

  /* ── Gerar relatório final ───────────────────────── */
  function generateReport(client, m, ai) {
    var builder = REPORTS[client.id];
    return builder ? builder(m, ai) : genericReport(client, m, ai);
  }


  /* ── Fetch Meta insights (proxy Flask) ───────────── */
  var _cache = {}; // key -> {ts, data}
  var _TTL   = 1800000; // 30 min

  function fetchInsights(agency, id, cb) {
    var key = agency + ":" + id;
    var now = Date.now();
    if (_cache[key] && now - _cache[key].ts < _TTL) { cb(null, _cache[key].data); return; }
    fetch("/api/relatorios/insights/" + agency + "/" + id)
      .then(function (r) {
        if (!r.headers.get("content-type").includes("application/json"))
          throw new Error("Reinicie o servidor Jake");
        return r.json();
      })
      .then(function (d) {
        if (d.error) { cb(d.error, null); return; }
        _cache[key] = { ts: now, data: d };
        cb(null, d);
      })
      .catch(function (e) { cb(e.message || "Erro de rede", null); });
  }

  /* ── Texto fixo de análise ───────────────────────── */
  var ANALISE = "Seguimos com os testes e otimizações nas campanhas. Precisamos de um feedback comercial para darmos os próximos passos 🙏";

  /* ── LocalStorage (reset segunda às 05:00) ───────── */
  function getLastMondayAt5AM() {
    var now = new Date(), day = now.getDay();
    var d = new Date(now);
    d.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
    d.setHours(5, 0, 0, 0);
    if (d > now) d.setDate(d.getDate() - 7);
    return d;
  }
  function lsKey(agency, id) { return "rel_" + agency + "_" + id; }
  function saveState(agency, id, ts) { localStorage.setItem(lsKey(agency, id), ts); }
  function loadState(agency, id) { var v = localStorage.getItem(lsKey(agency, id)); return v ? parseInt(v, 10) : null; }
  function getStatus(agency, id) {
    var ts = loadState(agency, id);
    if (!ts || ts < getLastMondayAt5AM().getTime()) return { sent: false, ts: null };
    return { sent: true, ts: ts };
  }

  /* ── Formatação de timestamp ─────────────────────── */
  function fmtTs(ts) {
    if (!ts) return "";
    var d = new Date(ts);
    return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  }

  /* ── SVGs ────────────────────────────────────────── */
  var ICO_CLIP  = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>';
  var ICO_CHECK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
  var ICO_SPIN  = '<span class="rel-week-spinner"></span>';

  /* ── HTML de status ──────────────────────────────── */
  function mkStatus(agency, id, sent, ts) {
    if (sent) return (
      '<span class="rel-status enviado rel-status-clickable" title="Clique para reverter" data-action="revert" data-client-id="' + esc(id) + '" data-agency="' + agency + '"><span class="rel-status-dot"></span>Enviado ↩</span>' +
      (ts ? '<span class="rel-status-ts">' + fmtTs(ts) + '</span>' : '')
    );
    return '<span class="rel-status pendente"><span class="rel-status-dot"></span>Pendente</span>';
  }

  /* ── Construir linha ─────────────────────────────── */
  function buildRow(agency, client) {
    var st = getStatus(agency, client.id);
    var tr = document.createElement("tr");
    tr.dataset.clientId = client.id;
    tr.dataset.agency   = agency;
    tr.innerHTML =
      '<td class="rel-td-name">' + esc(client.name) + '</td>' +
      '<td class="rel-td-week"><span class="rel-week-loading">' + ICO_SPIN + ' Carregando...</span></td>' +
      '<td class="rel-td-status">' + mkStatus(agency, client.id, st.sent, st.ts) + '</td>' +
      '<td><button class="rel-btn-copy" title="Copiar relatório" data-client-id="' + esc(client.id) + '" data-agency="' + agency + '">' + ICO_CLIP + '</button></td>';
    return tr;
  }

  /* ── Renderizar tabela ───────────────────────────── */
  function renderTable(agency) {
    var tbody = document.getElementById("rel-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    var list = AGENCIES[agency] || [];
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:2.5rem;color:rgba(176,190,197,.3);letter-spacing:.06em;">Nenhum cliente cadastrado</td></tr>';
      return;
    }
    list.forEach(function (c) { tbody.appendChild(buildRow(agency, c)); });
    list.forEach(function (c) {
      fetchInsights(agency, c.id, function (err, data) { setWeekCell(agency, c.id, err, data); });
    });
  }

  /* ── Célula "Esta Semana" ────────────────────────── */
  function setWeekCell(agency, id, err, data) {
    var row = findRow(agency, id); if (!row) return;
    var cell = row.querySelector(".rel-td-week"); if (!cell) return;
    if (err) { cell.innerHTML = '<span class="rel-week-error" title="' + esc(err) + '">⚠ Sem dados</span>'; return; }
    var s = parseFloat(data.spend || 0);
    if (!s) { cell.innerHTML = '<span class="rel-week-empty">Sem gasto</span>'; return; }
    var metric = "";
    if (data.messaging > 0)      metric = "💬 " + data.messaging + " msgs · CPL " + custo(s, data.messaging);
    else if (data.profile_visits > 0) metric = "👁 " + data.profile_visits + " visitas · " + custo(s, data.profile_visits);
    else if (data.messaging > 0) metric = "💬 " + data.messaging + " msgs · " + custo(s, data.messaging);
    else                         metric = "🖱 " + fmtN(data.clicks) + " cliques";
    cell.innerHTML = '<div class="rel-week-data"><span class="rel-week-spend">R$ ' + brl(s) + '</span><span class="rel-week-metric">' + metric + '</span></div>';
  }

  /* ── Copiar relatório ────────────────────────────── */
  function handleCopy(btn) {
    var id = btn.dataset.clientId, agency = btn.dataset.agency;
    var client = findClient(agency, id);
    if (!client || btn.disabled) return;
    btn.innerHTML = ICO_SPIN;
    btn.disabled  = true;

    fetchInsights(agency, id, function (err, data) {
      if (err || !data) {
        btn.innerHTML = ICO_CLIP; btn.disabled = false;
        showToast("⚠ " + (err || "Erro ao buscar dados")); return;
      }
      var text = generateReport(client, data, ANALISE);
      var now  = Date.now();
      var done = function () {
        saveState(agency, id, now);
        btn.innerHTML = ICO_CHECK; btn.classList.add("copied"); btn.disabled = false;
        setTimeout(function () { btn.innerHTML = ICO_CLIP; btn.classList.remove("copied"); }, 2200);
        setStatusCell(agency, id, true, now);
        setWeekCell(agency, id, null, data);
        showToast("Relatório de <b>" + esc(client.name) + "</b> copiado!");
      };
      if (navigator.clipboard && navigator.clipboard.writeText)
        navigator.clipboard.writeText(text).then(done).catch(function () { fallback(text); done(); });
      else { fallback(text); done(); }
    });
  }

  function fallback(text) {
    try { var ta = document.createElement("textarea"); ta.value = text; ta.style.cssText = "position:fixed;opacity:0;"; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); document.body.removeChild(ta); } catch (e) {}
  }

  /* ── Reverter para Pendente ──────────────────────── */
  function handleRevert(badge) {
    localStorage.removeItem(lsKey(badge.dataset.agency, badge.dataset.clientId));
    setStatusCell(badge.dataset.agency, badge.dataset.clientId, false, null);
  }

  /* ── Helpers ─────────────────────────────────────── */
  function setStatusCell(agency, id, sent, ts) {
    var row = findRow(agency, id); if (!row) return;
    var c = row.querySelector(".rel-td-status"); if (c) c.innerHTML = mkStatus(agency, id, sent, ts);
  }
  function findRow(agency, id) {
    var rows = (document.getElementById("rel-tbody") || {}).querySelectorAll && document.getElementById("rel-tbody").querySelectorAll("tr[data-client-id]");
    if (!rows) return null;
    for (var i = 0; i < rows.length; i++) if (rows[i].dataset.clientId === id && rows[i].dataset.agency === agency) return rows[i];
    return null;
  }
  function findClient(agency, id) {
    var list = AGENCIES[agency] || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  }
  function esc(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

  /* ── Toast ───────────────────────────────────────── */
  var _tt = null;
  function showToast(msg) {
    var el = document.getElementById("rel-toast"); if (!el) return;
    el.innerHTML = '<span class="rel-toast-icon">📋</span> ' + msg;
    el.classList.add("show");
    if (_tt) clearTimeout(_tt);
    _tt = setTimeout(function () { el.classList.remove("show"); }, 3200);
  }

  /* ── Init ────────────────────────────────────────── */
  function init() {
    renderTable(currentAgency);
    document.querySelectorAll(".rel-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll(".rel-tab").forEach(function (t) { t.classList.remove("active"); });
        tab.classList.add("active");
        currentAgency = tab.dataset.agency;
        renderTable(currentAgency);
      });
    });
    var tbody = document.getElementById("rel-tbody");
    if (tbody) {
      tbody.addEventListener("click", function (e) {
        var btn = e.target.closest(".rel-btn-copy");
        if (btn) { handleCopy(btn); return; }
        var badge = e.target.closest("[data-action='revert']");
        if (badge) handleRevert(badge);
      });
    }
  }

  document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", init)
    : init();

})();
