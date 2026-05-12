/* gestor.js — Gestor IA dashboard IIFE */
(function () {
  'use strict';

  // ── State ─────────────────────────────────────────────────────────────────
  var _acoes     = [];
  var _contas    = [];
  var _filtro    = 'tudo';
  var _acoesMap  = {};   // id → acao
  var _eventoSel = null; // acao_id selecionado

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

  // ── Timeline ──────────────────────────────────────────────────────────────
  function _carregarTimeline() {
    var url = '/api/gestor/acoes?limit=200';
    if (_filtro === 'piloti' || _filtro === 'dentto') url += '&agencia=' + _filtro;
    if (_filtro === 'alertas') url += '&tipo=alerta_saldo';

    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _acoes = data.acoes || [];
        _acoesMap = {};
        _acoes.forEach(function(a){ _acoesMap[a.id] = a; });
        _renderizarTimeline();
      });
  }

  function _renderizarTimeline() {
    var el = document.getElementById('gestor-timeline');
    if (!el) return;

    // Agrupar por data
    var grupos = {};
    _acoes.forEach(function (a) {
      var dt = new Date(a.executado_em);
      var key = dt.toLocaleDateString('pt-BR');
      if (!grupos[key]) grupos[key] = [];
      grupos[key].push(a);
    });

    var html = '';
    Object.keys(grupos).forEach(function (data) {
      html += '<div class="gs-data-header">' + data.toUpperCase() + '</div>';
      grupos[data].forEach(function (a) {
        html += _htmlEvento(a);
      });
    });

    el.innerHTML = html || '<div style="font-size:11px;color:rgba(176,190,197,.3);padding:12px;">Nenhuma ação registrada.</div>';
  }

  function _htmlEvento(a) {
    var cores = {
      'pausar_ad': '#ff6464', 'pausar_conta': '#ff6464',
      'escalar_orcamento': '#4caf50',
      'alerta_saldo': '#ffb74d',
    };
    var tipos = {
      'pausar_ad': 'PAUSA AD', 'pausar_conta': 'PAUSA CONTA',
      'escalar_orcamento': 'ESCALA', 'alerta_saldo': 'ALERTA SALDO',
    };
    var cor   = cores[a.tipo]  || 'rgba(176,190,197,.5)';
    var label = tipos[a.tipo]  || a.tipo.toUpperCase();
    var hora  = new Date(a.executado_em).toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'});
    var sel   = (_eventoSel === a.id) ? ' selected' : '';

    return '<div class="gs-evento' + sel + '" onclick="gestorSelecionarEvento(' + a.id + ')">' +
      '<div class="gs-evento-header">' +
        '<div class="gs-evento-dot" style="background:' + cor + '"></div>' +
        '<div class="gs-evento-tipo" style="color:' + cor + '">' + label + '</div>' +
        '<div class="gs-evento-hora">' + hora + '</div>' +
      '</div>' +
      '<div class="gs-evento-conta">' + _esc(a.cliente_nome) + '</div>' +
      '<div class="gs-evento-resumo">' + _esc(a.entidade_nome || '') + '</div>' +
    '</div>';
  }

  window.gestorSelecionarEvento = function (acoId) {
    _eventoSel = acoId;
    _renderizarTimeline();
    _renderizarDetalhe(_acoesMap[acoId]);
  };

  // ── Painel detalhe ────────────────────────────────────────────────────────
  function _renderizarDetalhe(acao) {
    var el = document.getElementById('gestor-detalhe');
    if (!el || !acao) return;

    var cores = {
      'pausar_ad': '#ff6464', 'pausar_conta': '#ff6464',
      'escalar_orcamento': '#4caf50', 'alerta_saldo': '#ffb74d',
    };
    var cor = cores[acao.tipo] || 'rgba(176,190,197,.5)';
    var hora = new Date(acao.executado_em).toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'});

    // Buscar todas as ações da mesma varredura e mesmo cliente
    var acoesConta = _acoes.filter(function(a){
      return a.varredura_id === acao.varredura_id && a.cliente_id === acao.cliente_id && a.tipo !== 'alerta_saldo';
    });

    var linhasAcoes = acoesConta.map(function (a) {
      var iconeClass = (a.tipo === 'escalar_orcamento') ? 'escalar' : 'pausar';
      var icone = (a.tipo === 'escalar_orcamento') ? '↑' : '⏸';
      var disabled = a.revertido ? ' disabled' : '';
      var label = a.revertido ? 'Revertido' : 'Reverter';
      return '<div class="gs-acao-row">' +
        '<div class="gs-acao-icone ' + iconeClass + '">' + icone + '</div>' +
        '<div style="flex:1">' +
          '<div class="gs-acao-titulo">' + _esc(a.tipo.replace(/_/g,' ')) + ': ' + _esc(a.entidade_nome || '') + '</div>' +
          '<div class="gs-acao-sub">' + _esc(a.motivo || '') + '</div>' +
        '</div>' +
        '<button class="gs-acao-rev"' + disabled + ' onclick="gestorReverterAcao(' + a.id + ')">' + label + '</button>' +
      '</div>';
    }).join('');

    var temAcoes = acoesConta.length > 0;

    el.innerHTML =
      '<div class="gestor-detalhe-header">' +
        '<div>' +
          '<div class="gs-detalhe-tipo" style="color:' + cor + '">' +
            acao.tipo.replace(/_/g,' ').toUpperCase() + ' · ' + hora +
          '</div>' +
          '<div class="gs-detalhe-conta">' + _esc(acao.cliente_nome) + '</div>' +
          '<div class="gs-detalhe-sub">' + _esc(acao.agencia) + ' · ' + _esc(acao.account_id) + '</div>' +
        '</div>' +
        (temAcoes ? '<button class="anu-btn-secondary" style="font-size:10px;color:#ff6464;border-color:rgba(255,100,100,.3)" onclick="gestorReverterEvento(' + acao.varredura_id + ')">↩ Reverter tudo</button>' : '') +
      '</div>' +
      '<div class="gs-analise-box">' +
        '<div class="gs-analise-label">ANÁLISE DO AGENTE</div>' +
        '<div class="gs-analise-texto">' + _esc(acao.motivo || 'Sem detalhes disponíveis.') + '</div>' +
      '</div>' +
      (temAcoes ? '<div style="font-size:9px;color:rgba(176,190,197,.4);margin-bottom:8px;">AÇÕES DESTA VARREDURA</div><div class="gs-acoes-lista">' + linhasAcoes + '</div>' : '');
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
    ['timeline', 'contas', 'relatorios', 'config'].forEach(function (t) {
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
