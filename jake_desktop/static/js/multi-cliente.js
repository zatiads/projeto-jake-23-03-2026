/* ──────────────────────────────────────────────────────
   Jake OS — Multi-Cliente: mesmo criativo, N clientes
────────────────────────────────────────────────────── */
(function () {
  'use strict';

  var _clientes     = [];   // todos os clientes carregados
  var _selecionados = {};   // id -> true
  var _tmpUuid      = null; // retornado pelo upload-temp
  var _tmpExt       = '.jpg';
  var _revisaoToken = null; // token do /preparar
  var _revisaoData  = null; // array de clientes com público

  function _val(id) { var el=document.getElementById(id); return el?el.value.trim():''; }
  function _el(id)  { return document.getElementById(id); }
  function _esc(s)  { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'); }
  function _status(msg) { var el=_el('mc-upload-status'); if(el) el.textContent=msg; }

  // ── Init (chamado ao trocar para tab) ──────────────
  window.mcInit = function() {
    if (_clientes.length) { renderListaClientes(); return; }
    fetch('/api/anuncios/clientes')
      .then(function(r){ return r.json(); })
      .then(function(d){ _clientes = d.clientes || []; renderListaClientes(); })
      .catch(function(){ _clientes = []; });
  };

  // ── Passo 1: lista de clientes ─────────────────────
  function renderListaClientes() {
    var cont = _el('mc-lista-clientes'); if (!cont) return;
    if (!_clientes.length) {
      cont.innerHTML = '<p style="font-size:12px;color:rgba(176,190,197,.4)">Nenhum cliente cadastrado.</p>';
      return;
    }
    cont.innerHTML = _clientes.map(function(c) {
      var checked = _selecionados[c.id] ? 'checked' : '';
      return '<label style="display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:6px;background:rgba(255,255,255,.03);cursor:pointer;">' +
        '<input type="checkbox" value="' + c.id + '" ' + checked + ' onchange="mcToggleCliente(' + c.id + ')">' +
        '<span style="font-size:13px">' + _esc(c.nome) + '</span>' +
        '<span style="font-size:11px;color:rgba(176,190,197,.35);margin-left:auto">' + _esc(c.agencia) + '</span>' +
        '</label>';
    }).join('');
    atualizarBtnPasso2();
  }

  window.mcToggleCliente = function(id) {
    if (_selecionados[id]) { delete _selecionados[id]; } else { _selecionados[id] = true; }
    atualizarBtnPasso2();
  };

  window.mcSelecionarAgencia = function(ag) {
    _clientes.forEach(function(c){ if (c.agencia === ag) _selecionados[c.id] = true; });
    renderListaClientes();
  };

  window.mcLimparSelecao = function() {
    _selecionados = {};
    renderListaClientes();
  };

  function atualizarBtnPasso2() {
    var btn = _el('mc-btn-passo2');
    if (btn) btn.disabled = Object.keys(_selecionados).length === 0;
  }

  // ── Passo 2: upload de imagem ──────────────────────
  function bindUpload() {
    var input = _el('mc-file-input');
    if (!input || input._mcBound) return;
    input._mcBound = true;
    input.addEventListener('change', function() {
      var file = input.files[0]; if (!file) return;
      // Preview local
      var preview     = _el('mc-preview-img');
      var placeholder = _el('mc-dropzone-placeholder');
      if (preview && file.type.indexOf('image') === 0) {
        preview.src = URL.createObjectURL(file);
        preview.style.display = '';
        if (placeholder) placeholder.style.display = 'none';
      }
      uploadTemp(file);
    });
  }

  function uploadTemp(file) {
    _tmpUuid = null;
    _status('Enviando...');
    var fd = new FormData();
    fd.append('criativo', file);
    fetch('/api/anuncios/multi-cliente/upload-temp', { method: 'POST', body: fd })
      .then(function(r){ return r.json(); })
      .then(function(d){
        if (d.tmp_uuid) {
          _tmpUuid = d.tmp_uuid;
          _tmpExt  = d.ext || '.jpg';
          _status('Arquivo pronto \u2713');
        } else {
          _status('Erro: ' + (d.error || 'desconhecido'));
        }
      })
      .catch(function(){ _status('Erro ao enviar arquivo.'); });
  }

  // ── Navegação entre passos ─────────────────────────
  window.mcIrPasso = function(n) {
    if (n === 2) {
      if (Object.keys(_selecionados).length === 0) return;
      bindUpload();
      mostrarPasso(2);
      return;
    }
    if (n === 3) {
      if (!_tmpUuid)           { alert('Aguarde o upload da imagem.'); return; }
      if (!_val('mc-camp-nome'))  { alert('Informe o nome da campanha.'); return; }
      if (!_val('mc-orcamento'))  { alert('Informe o orçamento diário.'); return; }
      mcPreparar();
      return;
    }
    mostrarPasso(n);
  };

  function mostrarPasso(n) {
    [1,2,3].forEach(function(i){
      var el = _el('mc-passo-' + i);
      if (el) el.style.display = (i === n) ? '' : 'none';
      var step = document.querySelector('.mc-step[data-step="' + i + '"]');
      if (step) step.classList.toggle('active', i === n);
    });
  }

  // ── Preparar (/preparar → dados de revisão) ────────
  function mcPreparar() {
    var btn = _el('mc-btn-passo3');
    if (btn) { btn.disabled = true; btn.textContent = 'Carregando...'; }

    var payload = {
      cliente_ids:   Object.keys(_selecionados).map(Number),
      tmp_uuid:      _tmpUuid,
      tmp_ext:       _tmpExt,
      copy: {
        titulo: _val('mc-copy-titulo'),
        texto:  _val('mc-copy-texto'),
        cta:    'SEND_MESSAGE'
      },
      campanha_nome: _val('mc-camp-nome'),
      orcamento:     parseFloat(_val('mc-orcamento')) || 0,
    };

    fetch('/api/anuncios/multi-cliente/preparar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (btn) { btn.disabled = false; btn.textContent = 'Revisar \u2192'; }
      if (d.error) {
        alert(d.error + (d.detalhes ? '\n' + d.detalhes.join('\n') : ''));
        return;
      }
      _revisaoToken = d.token;
      _revisaoData  = d.clientes;
      renderRevisao();
      mostrarPasso(3);
    })
    .catch(function(){
      if (btn) { btn.disabled = false; btn.textContent = 'Revisar \u2192'; }
      alert('Erro ao preparar publicação.');
    });
  }

  // ── Passo 3: cards de revisão ──────────────────────
  function renderRevisao() {
    var cont = _el('mc-revisao-cards');
    if (!cont || !_revisaoData) return;
    cont.innerHTML = _revisaoData.map(function(c) {
      var pub = c.publico;
      var generoLabel = (!pub.genero || !pub.genero.length) ? 'Todos' : (pub.genero[0] === 1 ? 'Masculino' : 'Feminino');
      var locLabel = (pub.cidades && pub.cidades.length) ? pub.cidades.join(', ') : (pub.paises || []).join(', ');
      return '<div style="padding:12px 14px;border-radius:8px;background:rgba(255,255,255,.04);border:1px solid rgba(176,190,197,.08);">' +
        '<div style="font-weight:600;font-size:13px;margin-bottom:6px">' + _esc(c.nome) +
          ' <span style="font-size:11px;color:rgba(176,190,197,.4)">' + _esc(c.agencia) + '</span></div>' +
        '<div style="font-size:12px;color:rgba(176,190,197,.6);display:flex;flex-wrap:wrap;gap:10px;">' +
          '<span>Idade: ' + pub.idade_min + '\u2013' + pub.idade_max + '</span>' +
          '<span>G\u00eanero: ' + generoLabel + '</span>' +
          '<span>Local: ' + _esc(locLabel || 'n\u00e3o configurado') + '</span>' +
          '<span>Or\u00e7amento: R$ ' + c.orcamento + '</span>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  // ── Publicar tudo (SSE) ────────────────────────────
  window.mcPublicar = function() {
    if (!_revisaoToken) return;
    var btnPublicar = _el('mc-btn-publicar');
    var btnVoltar   = _el('mc-btn-voltar3');
    var progDiv     = _el('mc-progresso');
    var progLista   = _el('mc-prog-lista');
    if (btnPublicar) { btnPublicar.disabled = true; btnPublicar.textContent = 'Publicando...'; }
    if (btnVoltar)   btnVoltar.disabled = true;
    if (progDiv)     progDiv.style.display = '';
    if (progLista)   progLista.innerHTML = '';

    var es = new EventSource('/api/anuncios/multi-cliente/stream/' + _revisaoToken);
    es.onmessage = function(evt) {
      var d; try { d = JSON.parse(evt.data); } catch(e) { return; }
      if (!progLista) return;

      if (d.status === 'publicando') {
        var li = document.createElement('div');
        li.id = 'mc-prog-' + d.idx;
        li.style.cssText = 'color:rgba(176,190,197,.5)';
        li.textContent = '\u23f3 (' + d.idx + '/' + d.total + ') ' + d.cliente + '...';
        progLista.appendChild(li);
      } else if (d.status === 'ok') {
        var el = document.getElementById('mc-prog-' + d.idx);
        if (el) { el.textContent = '\u2713 ' + d.cliente; el.style.color = '#4caf50'; }
      } else if (d.status === 'erro') {
        var el = document.getElementById('mc-prog-' + d.idx);
        if (el) { el.textContent = '\u2717 ' + d.cliente + ' \u2014 ' + d.erro; el.style.color = '#ef5350'; }
      } else if (d.status === 'concluido') {
        es.close();
        if (btnPublicar) { btnPublicar.disabled = false; btnPublicar.textContent = 'Conclu\u00eddo \u2713'; }
        if (btnVoltar)   btnVoltar.disabled = false;
      }
    };
    es.onerror = function() {
      es.close();
      if (btnPublicar) { btnPublicar.disabled = false; btnPublicar.textContent = 'Publicar Tudo'; }
      if (btnVoltar)   btnVoltar.disabled = false;
    };
  };

})();
