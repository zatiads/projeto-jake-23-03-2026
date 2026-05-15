/* gestor.js — Gestor IA dashboard IIFE */
(function () {
  'use strict';

  // ── State ─────────────────────────────────────────────────────────────────
  var _contas       = [];
  var _varreduras   = [];
  var _varSel       = null;  // varredura_id selecionada
  var _semanaOffset = 0;     // 0 = semana atual, -1 = anterior, etc.

  // ── Init ──────────────────────────────────────────────────────────────────
  window.gestorInit = function () {
    _carregarStatus();
    _carregarTimeline();
  };

  // ── Status bar ────────────────────────────────────────────────────────────
  function _carregarStatus() {
    fetch('/api/gestor/contas')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _contas = data.contas || [];
        var ok  = _contas.filter(function(c){ return c.saude === 'saudavel'; }).length;
        var opt = _contas.filter(function(c){ return c.saude === 'otimizada'; }).length;
        var alt = _contas.filter(function(c){ return c.saude === 'alerta'; }).length;
        document.getElementById('gs-saudaveis').textContent = '● ' + ok + ' saudáveis';
        document.getElementById('gs-otimizadas').textContent = '⚡ ' + opt + ' otimizadas';
        document.getElementById('gs-alertas').textContent = '⚠ ' + alt + ' alertas';
      });

    fetch('/api/gestor/varreduras')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var vars = data.varreduras || [];
        if (vars.length) {
          var d = new Date(vars[0].executado_em);
          document.getElementById('gs-ultima').textContent =
            'Última: ' + d.toLocaleDateString('pt-BR') + ' ' + d.toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'});
        }
      });
  }

  // ── Navegação semana ──────────────────────────────────────────────────────
  window.gestorSemanaAnterior = function () { _semanaOffset--; _carregarTimeline(); };
  window.gestorSemanaProxima  = function () { if (_semanaOffset < 0) { _semanaOffset++; _carregarTimeline(); } };

  function _semanaLabel() {
    var hoje  = new Date();
    var ini   = new Date(hoje); ini.setDate(hoje.getDate() - hoje.getDay() + 1 + _semanaOffset * 7);
    var fim   = new Date(ini);  fim.setDate(ini.getDate() + 6);
    var fmt   = function(d) { return d.toLocaleDateString('pt-BR', {day:'2-digit', month:'2-digit'}); };
    return fmt(ini) + ' — ' + fmt(fim);
  }

  function _semanaRange() {
    var hoje = new Date();
    var ini  = new Date(hoje); ini.setDate(hoje.getDate() - hoje.getDay() + 1 + _semanaOffset * 7); ini.setHours(0,0,0,0);
    var fim  = new Date(ini);  fim.setDate(ini.getDate() + 6); fim.setHours(23,59,59,999);
    return { ini: ini, fim: fim };
  }

  // ── Timeline ──────────────────────────────────────────────────────────────
  function _carregarTimeline() {
    // Atualiza label da semana
    var navEl = document.getElementById('gs-semana-label');
    if (navEl) navEl.textContent = _semanaLabel();
    var btnProx = document.getElementById('gs-semana-prox');
    if (btnProx) btnProx.disabled = _semanaOffset >= 0;

    fetch('/api/gestor/varreduras')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _varreduras = data.varreduras || [];
        _renderizarTimeline();
      });
  }

  function _renderizarTimeline() {
    var el = document.getElementById('gestor-timeline');
    if (!el) return;

    var range = _semanaRange();
    var varsSemana = _varreduras.filter(function(v) {
      var d = new Date(v.executado_em);
      return d >= range.ini && d <= range.fim;
    });

    if (!varsSemana.length) {
      el.innerHTML = '<div style="font-size:11px;color:rgba(176,190,197,.3);padding:20px 12px;text-align:center;">Nenhuma varredura nesta semana.</div>';
      return;
    }

    el.innerHTML = varsSemana.map(function(v) {
      return _htmlVarreduraCard(v);
    }).join('');
  }

  var _STATUS_ACAO = {
    'sucesso':   { icon: '✅', cor: '#4caf50', label: 'Executado' },
    'pendente':  { icon: '⏳', cor: '#ffb74d', label: 'Pendente' },
    'cancelado': { icon: '❌', cor: '#ff6464', label: 'Cancelado' },
    'expirado':  { icon: '💀', cor: 'rgba(176,190,197,.3)', label: 'Expirado' },
    'erro':      { icon: '⚠️', cor: '#ff6464', label: 'Erro' },
  };

  var _TIPO_ICON = {
    'pausar_ad': '⏸',
    'reativar_ad': '▶',
    'escalar_orcamento': '📈',
    'reduzir_orcamento': '📉',
    'pausar_conta': '🛑',
    'duplicar_ad': '📋',
  };

  function _htmlVarreduraCard(v) {
    var d    = new Date(v.executado_em);
    var data = d.toLocaleDateString('pt-BR', {weekday:'short', day:'2-digit', month:'2-digit'}).toUpperCase();
    var hora = d.toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'});
    var sel  = (_varSel === v.id) ? ' style="border-color:rgba(100,181,246,.4);background:rgba(100,181,246,.04)"' : '';
    var nAcoes = v.contas_acao || 0;
    var badge  = nAcoes > 0
      ? '<span style="background:rgba(255,183,77,.15);color:#ffb74d;font-size:9px;padding:2px 7px;border-radius:10px;font-weight:700">' + nAcoes + ' ação' + (nAcoes > 1 ? 'ões' : '') + '</span>'
      : '<span style="font-size:9px;color:rgba(176,190,197,.3)">sem ações</span>';

    return '<div class="gs-evento"' + sel + ' onclick="gestorSelecionarVarredura(' + v.id + ')" style="cursor:pointer;margin-bottom:6px">' +
      '<div class="gs-evento-header">' +
        '<div style="font-size:10px;font-weight:700;color:rgba(176,190,197,.85);flex:1">' + data + ' · ' + hora + '</div>' +
        badge +
      '</div>' +
      '<div style="font-size:10px;color:rgba(176,190,197,.45);margin-top:3px">' +
        v.contas_total + ' contas analisadas' +
      '</div>' +
    '</div>';
  }

  window.gestorSelecionarVarredura = function (varId) {
    _varSel = varId;
    _renderizarTimeline();

    var el = document.getElementById('gestor-detalhe');
    if (el) el.innerHTML = '<div style="font-size:11px;color:rgba(176,190,197,.3);padding:20px;text-align:center">Carregando...</div>';

    fetch('/api/gestor/varreduras/' + varId + '/resumo')
      .then(function(r) { return r.json(); })
      .then(function(data) { _renderizarDetalheVarredura(data); });
  };

  // ── Painel detalhe (por varredura) ────────────────────────────────────────
  function _renderizarDetalheVarredura(data) {
    var el = document.getElementById('gestor-detalhe');
    if (!el) return;

    var v       = data.varredura || {};
    var acoes   = data.acoes    || [];
    var alertas = data.alertas  || [];

    var d    = new Date(v.executado_em);
    var data_str = d.toLocaleDateString('pt-BR', {weekday:'long', day:'2-digit', month:'long'});
    var hora = d.toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'});

    // Cabeçalho
    var html = '<div class="gestor-detalhe-header" style="flex-direction:column;align-items:flex-start;gap:4px">' +
      '<div style="font-size:13px;font-weight:700;color:rgba(176,190,197,.9);text-transform:capitalize">' + data_str + '</div>' +
      '<div style="font-size:10px;color:rgba(176,190,197,.4)">' + hora + ' · ' + (v.contas_total || 0) + ' contas analisadas</div>' +
      (acoes.length ? '<button class="anu-btn-secondary" style="font-size:10px;color:#ff6464;border-color:rgba(255,100,100,.3);margin-top:8px" onclick="gestorReverterEvento(' + v.id + ')">↩ Reverter tudo</button>' : '') +
    '</div>';

    // Ações
    if (acoes.length) {
      html += '<div style="font-size:9px;color:rgba(176,190,197,.35);letter-spacing:.05em;margin:12px 0 6px">AÇÕES (' + acoes.length + ')</div>';
      html += '<div class="gs-acoes-lista">';
      acoes.forEach(function(a) {
        var st     = _STATUS_ACAO[a.status] || { icon: '?', cor: 'rgba(176,190,197,.4)', label: a.status };
        var icone  = _TIPO_ICON[a.tipo] || '●';
        var rev    = a.revertido;
        var podRev = a.status === 'sucesso' && !rev;
        html += '<div class="gs-acao-row" style="align-items:flex-start">' +
          '<div class="gs-acao-icone" style="color:' + st.cor + ';font-size:13px;min-width:22px;text-align:center">' + icone + '</div>' +
          '<div style="flex:1;min-width:0">' +
            '<div class="gs-acao-titulo">' + _esc(a.tipo.replace(/_/g,' ').toUpperCase()) +
              ' <span style="font-weight:400;color:rgba(176,190,197,.5)">— ' + _esc(a.cliente_nome) + '</span></div>' +
            '<div class="gs-acao-sub">' + _esc(a.motivo || '') + '</div>' +
            (a.entidade_nome ? '<div class="gs-acao-sub" style="color:rgba(176,190,197,.35)">' + _esc(a.entidade_nome) + '</div>' : '') +
            (rev ? '<div style="font-size:9px;color:#ffb74d;margin-top:2px">↩ Revertido</div>' : '') +
          '</div>' +
          '<div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0">' +
            '<span style="font-size:9px;color:' + st.cor + '">' + st.icon + ' ' + st.label + '</span>' +
            (podRev ? '<button class="gs-acao-rev" onclick="gestorReverterAcao(' + a.id + ')">Reverter</button>' : '') +
          '</div>' +
        '</div>';
      });
      html += '</div>';
    }

    // Alertas
    if (alertas.length) {
      var _AL_EMOJI = { 'alerta_saldo_critico':'💰','alerta_zero_conv':'❌','alerta_freq_alta':'🔄','alerta_sem_veiculacao':'😴','alerta_learning_travado':'🔒','alerta_cpl_semanal':'📊' };
      html += '<div style="font-size:9px;color:rgba(176,190,197,.35);letter-spacing:.05em;margin:14px 0 6px">ALERTAS (' + alertas.length + ')</div>';
      html += '<div style="display:flex;flex-direction:column;gap:6px">';
      alertas.forEach(function(al) {
        var emoji = _AL_EMOJI[al.tipo] || '⚠️';
        html += '<div style="display:flex;gap:8px;padding:8px;background:rgba(255,183,77,.04);border-radius:6px;border-left:2px solid rgba(255,183,77,.2)">' +
          '<span style="font-size:12px">' + emoji + '</span>' +
          '<div>' +
            '<div style="font-size:10px;font-weight:600;color:rgba(176,190,197,.7)">' + _esc(al.cliente_nome) + '</div>' +
            '<div style="font-size:10px;color:rgba(176,190,197,.45)">' + _esc(al.motivo) + '</div>' +
          '</div>' +
        '</div>';
      });
      html += '</div>';
    }

    if (!acoes.length && !alertas.length) {
      html += '<div style="font-size:11px;color:rgba(176,190,197,.3);padding:20px;text-align:center">✅ Nenhuma ação ou alerta nesta varredura.</div>';
    }

    el.innerHTML = html;
  }

  // ── Rollback ──────────────────────────────────────────────────────────────
  window.gestorReverterAcao = function (acoId) {
    if (!confirm('Reverter esta ação?')) return;
    fetch('/api/gestor/reverter/' + acoId, {method: 'POST'})
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { alert('Erro: ' + data.error); return; }
        _carregarTimeline();
        _carregarStatus();
      });
  };

  window.gestorReverterEvento = function (varreduraId) {
    if (!confirm('Reverter TODAS as ações desta varredura?')) return;
    fetch('/api/gestor/reverter-evento/' + varreduraId, {method: 'POST'})
      .then(function (r) { return r.json(); })
      .then(function (data) {
        alert('Revertidas: ' + data.revertidas + (data.erros.length ? ' | Erros: ' + data.erros.length : ''));
        _carregarTimeline();
        _carregarStatus();
      });
  };

  // ── Rodar agora ───────────────────────────────────────────────────────────
  window.gestorRodar = function () {
    var btn = document.getElementById('gs-btn-rodar');
    btn.disabled = true;
    btn.textContent = '⏳ Rodando...';
    fetch('/api/gestor/rodar', {method: 'POST'})
      .then(function (r) { return r.json(); })
      .then(function (data) {
        btn.textContent = '▶ Rodar agora';
        btn.disabled = false;
        if (data.error) { alert('Erro: ' + data.error); return; }
        setTimeout(function () { _carregarTimeline(); _carregarStatus(); }, 3000);
      });
  };

  // ── Sub-abas ──────────────────────────────────────────────────────────────
  window.gestorSwitchTab = function (tab) {
    ['timeline', 'contas', 'relatorios', 'planejador', 'config'].forEach(function (t) {
      var el = document.getElementById('gestor-tab-' + t);
      if (el) el.style.display = (t === tab) ? '' : 'none';
      var btn = document.querySelector('.gestor-tab-btn[data-tab="' + t + '"]');
      if (btn) btn.classList.toggle('active', t === tab);
    });
    if (tab === 'contas') _carregarContas();
    if (tab === 'relatorios') _carregarRelatorios();
    if (tab === 'config') _carregarExecucoes();
  };

  // ── Sub-aba: Contas ───────────────────────────────────────────────────────
  function _carregarContas() {
    fetch('/api/gestor/contas')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _contas = data.contas || [];
        var el = document.getElementById('gestor-contas-grid');
        if (!el) return;
        el.innerHTML = _contas.map(function (c) {
          return '<div class="gs-conta-card" onclick="gestorAbrirContaModal(' + c.id + ')">' +
            '<div class="gs-conta-nome">' + _esc(c.nome) + '</div>' +
            '<div class="gs-conta-agencia">' + _esc(c.agencia) + '</div>' +
            '<div class="gs-conta-saude ' + (c.saude || 'saudavel') + '">' +
              (c.saude === 'alerta' ? '⚠ Alerta' : c.saude === 'otimizada' ? '⚡ Otimizada' : '● Saudável') +
            '</div>' +
            '<div style="margin-top:8px;display:flex;align-items:center;gap:8px;" onclick="event.stopPropagation()">' +
              '<label style="font-size:9px;color:rgba(176,190,197,.4)">Gestor ativo</label>' +
              '<input type="checkbox" ' + (c.gestor_ativo ? 'checked' : '') + ' onchange="gestorToggleConta(' + c.id + ',this.checked)">' +
            '</div>' +
          '</div>';
        }).join('');
      });
  }

  window.gestorToggleConta = function (id, ativo) {
    fetch('/api/gestor/contas/' + id, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({gestor_ativo: ativo}),
    });
  };

  // ── Modal de conta ────────────────────────────────────────────────────────
  window.gestorAbrirContaModal = function (id) {
    var c = _contas.filter(function(x){ return x.id === id; })[0];
    if (!c) return;
    var cfg = c.gestor_config_json || {};

    fetch('/api/gestor/acoes?cliente_id=' + id + '&limit=20')
      .then(function(r){ return r.json(); })
      .then(function(data){
        var acoes = data.acoes || [];
        var linhasHist = acoes.length
          ? acoes.map(function(a){
              var dt = new Date(a.executado_em).toLocaleDateString('pt-BR');
              return '<div style="font-size:10px;color:rgba(176,190,197,.6);padding:4px 0;border-bottom:1px solid rgba(176,190,197,.06)">' +
                '<span style="color:rgba(176,190,197,.35)">' + dt + '</span> ' +
                a.tipo.replace(/_/g,' ') + ' — ' + _esc(a.entidade_nome || '') +
                (a.revertido ? ' <span style="color:#ffb74d">(revertido)</span>' : '') +
              '</div>';
            }).join('')
          : '<p style="font-size:10px;color:rgba(176,190,197,.3)">Nenhuma ação registrada.</p>';

        var overlay = document.createElement('div');
        overlay.id = 'gs-conta-modal-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000;display:flex;align-items:center;justify-content:center';
        overlay.onclick = function(e){ if(e.target===overlay) gestorFecharContaModal(); };
        overlay.innerHTML =
          '<div style="background:#0f1520;border:1px solid rgba(176,190,197,.12);border-radius:10px;padding:24px;width:480px;max-height:80vh;overflow-y:auto;display:flex;flex-direction:column;gap:16px">' +
            '<div style="display:flex;align-items:center;justify-content:space-between">' +
              '<div>' +
                '<div style="font-size:14px;font-weight:700;color:rgba(176,190,197,.95)">' + _esc(c.nome) + '</div>' +
                '<div style="font-size:10px;color:rgba(176,190,197,.4)">' + _esc(c.agencia) + ' · ' + _esc(c.account_id) + '</div>' +
              '</div>' +
              '<button onclick="gestorFecharContaModal()" style="background:none;border:none;color:rgba(176,190,197,.4);font-size:16px;cursor:pointer">✕</button>' +
            '</div>' +
            '<div>' +
              '<div style="font-size:9px;color:rgba(176,190,197,.35);letter-spacing:.05em;margin-bottom:8px">CONFIG DE FALLBACK (usado quando histórico &lt; 14 dias)</div>' +
              '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px" id="gs-cfg-form-' + id + '">' +
                _cfgField('cpl_max',      'CPL máx (R$)',     cfg.cpl_max      || 70,   id) +
                _cfgField('ctr_min',      'CTR mín (%)',      cfg.ctr_min      || 1.0,  id) +
                _cfgField('freq_max',     'Freq. máx',        cfg.freq_max     || 3.5,  id) +
                _cfgField('escala_pct',   'Escala (%)',       cfg.escala_pct   || 15,   id) +
                _cfgField('saldo_alerta', 'Saldo alerta (R$)',cfg.saldo_alerta || 100,  id) +
                _cfgField('saldo_critico','Saldo crítico (R$)',cfg.saldo_critico|| 30,  id) +
              '</div>' +
              '<button onclick="gestorSalvarConfigConta(' + id + ')" class="anu-btn-primary" style="margin-top:12px;width:100%;font-size:11px">Salvar configuração</button>' +
            '</div>' +
            '<div>' +
              '<div style="font-size:9px;color:rgba(176,190,197,.35);letter-spacing:.05em;margin-bottom:8px">HISTÓRICO DE AÇÕES</div>' +
              linhasHist +
            '</div>' +
          '</div>';
        document.body.appendChild(overlay);
      });
  };

  function _cfgField(key, label, val, contaId) {
    return '<div style="display:flex;flex-direction:column;gap:3px">' +
      '<label style="font-size:9px;color:rgba(176,190,197,.4)">' + label + '</label>' +
      '<input id="gs-cfg-' + contaId + '-' + key + '" type="number" step="0.1" value="' + val + '" ' +
        'style="background:rgba(176,190,197,.06);border:1px solid rgba(176,190,197,.12);border-radius:4px;color:rgba(176,190,197,.85);font-size:11px;padding:5px 8px">' +
    '</div>';
  }

  window.gestorFecharContaModal = function () {
    var el = document.getElementById('gs-conta-modal-overlay');
    if (el) el.remove();
  };

  window.gestorSalvarConfigConta = function (id) {
    var keys = ['cpl_max','ctr_min','freq_max','escala_pct','saldo_alerta','saldo_critico'];
    var cfg = {};
    keys.forEach(function(k){
      var inp = document.getElementById('gs-cfg-' + id + '-' + k);
      if (inp) cfg[k] = parseFloat(inp.value);
    });
    fetch('/api/gestor/contas/' + id, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({gestor_config_json: cfg}),
    })
      .then(function(r){ return r.json(); })
      .then(function(data){
        if (data.error) { alert('Erro: ' + data.error); return; }
        gestorFecharContaModal();
        _carregarContas();
      });
  };

  // ── Sub-aba: Relatórios ───────────────────────────────────────────────────
  function _carregarRelatorios() {
    fetch('/api/gestor/relatorios')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var el = document.getElementById('gestor-relatorios-lista');
        if (!el) return;
        var lista = data.relatorios || [];
        if (!lista.length) {
          el.innerHTML = '<p style="font-size:12px;color:rgba(176,190,197,.3)">Nenhum relatório gerado ainda.</p>';
          return;
        }
        el.innerHTML = lista.map(function (r) {
          var dt = new Date(r.gerado_em).toLocaleDateString('pt-BR');
          return '<div style="display:flex;align-items:center;gap:12px;padding:10px;background:rgba(176,190,197,.04);border-radius:6px;margin-bottom:6px;">' +
            '<div style="flex:1">' +
              '<div style="font-size:11px;font-weight:600;color:rgba(176,190,197,.85)">' + r.agencia.toUpperCase() + ' — ' + dt + '</div>' +
              '<div style="font-size:10px;color:rgba(176,190,197,.4)">' + r.periodo_ini + ' a ' + r.periodo_fim + ' · ' + (r.tamanho_kb || '?') + ' KB</div>' +
            '</div>' +
            '<a href="/api/gestor/relatorios/' + r.id + '/download" class="anu-btn-secondary" style="font-size:10px">⬇ Download</a>' +
          '</div>';
        }).join('');
      });
  }

  window.gestorGerarRelatorio = function () {
    gestorRodar();
  };

  // ── Sub-aba: Configuração ─────────────────────────────────────────────────
  function _carregarExecucoes() {
    fetch('/api/gestor/varreduras')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var el = document.getElementById('gestor-log-execucoes');
        if (!el) return;
        var vars = (data.varreduras || []).slice(0, 10);
        if (!vars.length) {
          el.innerHTML = '<p style="font-size:11px;color:rgba(176,190,197,.3)">Nenhuma execução registrada.</p>';
          return;
        }
        el.innerHTML = vars.map(function (v) {
          var cor = v.status === 'sucesso' ? '#4caf50' : v.status === 'parcial' ? '#ffb74d' : '#ff6464';
          var dt  = new Date(v.executado_em).toLocaleString('pt-BR');
          return '<div style="display:flex;align-items:center;gap:8px;font-size:10px;">' +
            '<span style="color:' + cor + ';width:60px">' + v.status + '</span>' +
            '<span style="color:rgba(176,190,197,.5)">' + dt + '</span>' +
            '<span style="color:rgba(176,190,197,.35)">· ' + v.contas_total + ' contas · ' + v.contas_acao + ' ações</span>' +
          '</div>';
        }).join('');
      });
  }

  // ── Filtros ───────────────────────────────────────────────────────────────
  window.gestorFiltrar = function (filtro) {
    _filtro = filtro;
    document.querySelectorAll('.gs-filtro').forEach(function (btn) {
      btn.classList.toggle('active', btn.textContent.toLowerCase() === filtro ||
        (filtro === 'tudo' && btn.textContent === 'Tudo'));
    });
    _carregarTimeline();
  };

  // ── Utils ─────────────────────────────────────────────────────────────────
  function _esc(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  }

}());
