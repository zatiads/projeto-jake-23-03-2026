/* ──────────────────────────────────────────────────────
   Jake OS — Fábrica de Criativos v2
────────────────────────────────────────────────────── */
(function () {
  'use strict';

  // ── Estado ─────────────────────────────────────────
  var _tipo        = 'imagem';   // 'imagem' | 'video'
  var _modo        = 'anuncios'; // modo do especialista
  var _modelo      = 'flux-1.1-pro';
  var _promptExp   = '';
  var _resultadoUrl= '';
  var _uploadUrl   = '';         // URL Replicate da imagem uploadada (para I2V)
  var _uploadB64   = '';         // base64 da imagem (para análise)
  var _uploadMime  = 'image/jpeg';
  var _usarI2V     = false;
  var _predId      = '';         // prediction_id do vídeo em andamento
  var _pollTimer   = null;
  var _histPage    = 1;
  var _histFiltros = { folder_id: '', tipo: '' };

  // ── Definição de modelos ────────────────────────────
  var _MODELOS_IMAGEM = [
    { key:'flux-1.1-pro',    nome:'Flux 1.1 Pro',       vel:'fast', custo:2 },
    { key:'flux-dev',        nome:'Flux Dev',            vel:'med',  custo:2 },
    { key:'recraft-v3',      nome:'Recraft V3',          vel:'fast', custo:2 },
    { key:'ideogram-v3-turbo',nome:'Ideogram V3 Turbo', vel:'fast', custo:1 },
    { key:'imagen-4',        nome:'Imagen 4',            vel:'med',  custo:3 },
  ];
  var _MODELOS_VIDEO = [
    { key:'wan-t2v-fast',  nome:'Wan T2V Fast',     tipo:'T2V', vel:'fast', custo:1 },
    { key:'wan-5b-fast',   nome:'Wan 5B Fast',      tipo:'T2V', vel:'med',  custo:2 },
    { key:'hailuo-02',     nome:'Hailuo 02 Fast',   tipo:'T2V', vel:'fast', custo:2 },
    { key:'seedance-lite', nome:'Seedance Lite',    tipo:'T2V', vel:'med',  custo:2 },
    { key:'runway-gen4',   nome:'Runway Gen-4',     tipo:'T2V', vel:'fast', custo:3 },
    { key:'wan-i2v-fast',  nome:'Wan I2V Fast',     tipo:'I2V', vel:'fast', custo:1 },
  ];

  // ── Init ───────────────────────────────────────────
  function init() {
    bindTipoToggle();
    bindModos();
    renderModelos();
    bindUpload();
    bindPromptActions();
    bindGerarBtn();
    bindResultadoAcoes();
    bindAbas();
    bindHistoricoEvents();
    carregarPastas();
    carregarHistorico();
  }

  // ── Toggle Imagem / Vídeo ───────────────────────────
  function bindTipoToggle() {
    var btnImg = document.getElementById('cri-tipo-imagem');
    var btnVid = document.getElementById('cri-tipo-video');
    if (btnImg) btnImg.addEventListener('click', function () {
      _tipo = 'imagem'; _modelo = 'flux-1.1-pro'; _usarI2V = false;
      btnImg.classList.add('active'); btnVid.classList.remove('active');
      renderModelos();
      _setText('cri-modelos-label', 'Modelo de imagem');
    });
    if (btnVid) btnVid.addEventListener('click', function () {
      _tipo = 'video'; _modelo = 'wan-t2v-fast';
      btnVid.classList.add('active'); btnImg.classList.remove('active');
      renderModelos();
      _setText('cri-modelos-label', 'Modelo de vídeo');
    });
  }

  // ── Seletor de Modo ─────────────────────────────────
  function bindModos() {
    document.querySelectorAll('.cri-modo-card').forEach(function (card) {
      card.addEventListener('click', function () {
        _modo = this.dataset.modo;
        document.querySelectorAll('.cri-modo-card').forEach(function (c) { c.classList.remove('active'); });
        this.classList.add('active');
        esconder('cri-expandido-painel'); _promptExp = '';
      });
    });
  }

  // ── Render modelos ──────────────────────────────────
  function renderModelos() {
    var grid = document.getElementById('cri-modelos-grid');
    if (!grid) return;
    var lista = _tipo === 'imagem' ? _MODELOS_IMAGEM : _MODELOS_VIDEO;
    grid.innerHTML = lista.map(function (m) {
      var ativo = m.key === _modelo ? ' active' : '';
      var disabled = (m.tipo === 'I2V' && !_usarI2V) ? ' disabled' : '';
      var badges = '';
      if (_tipo === 'imagem') {
        badges = '<span class="cri-badge cri-badge-tipo-imagem">IMG</span>';
      } else {
        badges = '<span class="cri-badge cri-badge-tipo-' + (m.tipo === 'I2V' ? 'i2v' : 't2v') + '">' + m.tipo + '</span>';
      }
      badges += '<span class="cri-badge cri-badge-vel-' + m.vel + '">' + (m.vel === 'fast' ? '⚡' : '◑') + '</span>';
      badges += '<span class="cri-badge cri-badge-custo-' + m.custo + '">' + '$'.repeat(m.custo) + '</span>';
      return '<div class="cri-modelo-card' + ativo + disabled + '" data-key="' + m.key + '">' +
        '<span class="cri-modelo-nome">' + _esc(m.nome) + '</span>' +
        '<div class="cri-modelo-badges">' + badges + '</div></div>';
    }).join('');
    grid.querySelectorAll('.cri-modelo-card:not(.disabled)').forEach(function (card) {
      card.addEventListener('click', function () {
        _modelo = this.dataset.key;
        grid.querySelectorAll('.cri-modelo-card').forEach(function (c) { c.classList.remove('active'); });
        this.classList.add('active');
      });
    });
  }

  // ── Utilitários ─────────────────────────────────────
  function _val(id) { var el = document.getElementById(id); return el ? el.value : ''; }
  function _set(id, v) { var el = document.getElementById(id); if (el) el.value = v || ''; }
  function _setText(id, t) { var el = document.getElementById(id); if (el) el.textContent = t || ''; }
  function _esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function mostrar(id) { var el = document.getElementById(id); if (el) el.classList.remove('hidden'); }
  function esconder(id) { var el = document.getElementById(id); if (el) el.classList.add('hidden'); }

  // ── Observer para init lazy ─────────────────────────
  var _iniciado = false;
  var _obs = new MutationObserver(function (muts) {
    muts.forEach(function (m) {
      if (m.target.id === 'page-criativos' && m.target.classList.contains('active')) {
        if (!_iniciado) { _iniciado = true; init(); }
      }
    });
  });
  var page = document.getElementById('page-criativos');
  if (page) {
    _obs.observe(page, { attributes: true, attributeFilter: ['class'] });
    if (page.classList.contains('active')) { _iniciado = true; init(); }
  }

  // ── Stubs para tasks seguintes ──────────────────────
  function bindUpload() {
    var zone  = document.getElementById('cri-upload-zone');
    var input = document.getElementById('cri-upload-input');
    if (!zone || !input) return;
    zone.addEventListener('dragover', function (e) { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', function () { zone.classList.remove('dragover'); });
    zone.addEventListener('drop', function (e) {
      e.preventDefault(); zone.classList.remove('dragover');
      var f = e.dataTransfer.files[0]; if (f) _processarUpload(f);
    });
    input.addEventListener('change', function () { if (this.files[0]) _processarUpload(this.files[0]); });
    var btnI2V = document.getElementById('cri-btn-i2v');
    var btnAna = document.getElementById('cri-btn-analisar');
    var btnRem = document.getElementById('cri-btn-remover-img');
    if (btnI2V) btnI2V.addEventListener('click', function () {
      _usarI2V = true;
      if (_tipo !== 'video') {
        _tipo = 'video';
        document.getElementById('cri-tipo-video').classList.add('active');
        document.getElementById('cri-tipo-imagem').classList.remove('active');
        _modelo = 'wan-i2v-fast';
        _setText('cri-modelos-label', 'Modelo de vídeo');
      } else {
        _modelo = 'wan-i2v-fast';
      }
      renderModelos();
      alert('Imagem definida como input I2V. Modelo Wan I2V Fast selecionado.');
    });
    if (btnAna) btnAna.addEventListener('click', _analisarReferencia);
    if (btnRem) btnRem.addEventListener('click', function () {
      _uploadUrl = ''; _uploadB64 = ''; _usarI2V = false;
      esconder('cri-upload-preview-wrap'); mostrar('cri-upload-placeholder');
      document.getElementById('cri-upload-input').value = '';
      renderModelos();
    });
  }

  function _processarUpload(file) {
    var reader = new FileReader();
    reader.onload = function (e) {
      var img = document.getElementById('cri-upload-img');
      if (img) { img.src = e.target.result; }
      esconder('cri-upload-placeholder'); mostrar('cri-upload-preview-wrap');
    };
    reader.readAsDataURL(file);
    // Upload para Replicate
    var fd = new FormData();
    fd.append('arquivo', file);
    fetch('/api/criativos/upload-imagem', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { alert('Erro no upload: ' + data.error); return; }
        _uploadUrl  = data.url   || '';
        _uploadB64  = data.base64 || '';
        _uploadMime = data.mime_type || 'image/jpeg';
      })
      .catch(function (e) { alert('Erro de rede no upload: ' + e); });
  }

  function _analisarReferencia() {
    if (!_uploadB64) { alert('Faça upload de uma imagem primeiro.'); return; }
    _setLoading('🔍 Analisando estilo da imagem...');
    fetch('/api/criativos/analisar-referencia', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imagem_base64: _uploadB64, mime_type: _uploadMime }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _clearLoading();
        if (data.error) { alert('Erro na análise: ' + data.error); return; }
        _set('cri-prompt', '(Analisado da referência)');
        _promptExp = data.prompt_sugerido || '';
        // Selecionar modo sugerido
        if (data.modo_sugerido) {
          _modo = data.modo_sugerido;
          document.querySelectorAll('.cri-modo-card').forEach(function (c) {
            c.classList.toggle('active', c.dataset.modo === _modo);
          });
        }
        _setText('cri-expandido-original', 'Gerado a partir da análise da referência');
        _set('cri-expandido-texto', _promptExp);
        mostrar('cri-expandido-painel');
      })
      .catch(function (e) { _clearLoading(); alert('Erro: ' + e); });
  }

  function bindPromptActions() {
    var btnReg = document.getElementById('cri-btn-regerar');
    if (btnReg) btnReg.addEventListener('click', _expandirPrompt);
  }

  function _expandirPrompt(callback) {
    var prompt = _val('cri-prompt').trim();
    if (!prompt || prompt === '(Analisado da referência)') {
      if (_promptExp && typeof callback === 'function') { callback(); return; }
      alert('Digite um prompt antes de gerar.'); return;
    }
    _setLoading('✨ Claude expandindo o prompt...');
    fetch('/api/criativos/expandir-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt, modo: _modo, tipo: _tipo }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _clearLoading();
        if (data.error) { alert('Erro ao expandir: ' + data.error); return; }
        _promptExp = data.prompt_expandido || '';
        _setText('cri-expandido-original', 'Original: ' + prompt);
        _set('cri-expandido-texto', _promptExp);
        mostrar('cri-expandido-painel');
        if (typeof callback === 'function') callback();
      })
      .catch(function (e) { _clearLoading(); alert('Erro: ' + e); });
  }

  function bindGerarBtn() {
    var btn = document.getElementById('cri-btn-gerar');
    if (btn) btn.addEventListener('click', function () {
      // Prompt expandido já existe? Ir direto para geração
      var promptFinal = _val('cri-expandido-texto').trim() || _promptExp;
      if (promptFinal) {
        _promptExp = promptFinal;
        _gerar();
      } else {
        // Expandir primeiro, depois gerar
        _expandirPrompt(function () { _gerar(); });
      }
    });
  }

  function _gerar() {
    if (_tipo === 'imagem') {
      _gerarImagem();
    } else {
      _gerarVideo();
    }
  }

  function _gerarImagem() {
    _setLoading('🖼️ Gerando imagem...', 40);
    fetch('/api/criativos/gerar-imagem', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt_expandido: _promptExp, modelo: _modelo }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _clearLoading();
        if (data.error) { alert('Erro na geração: ' + data.error); return; }
        _resultadoUrl = data.url;
        _mostrarResultado('imagem');
      })
      .catch(function (e) { _clearLoading(); alert('Erro: ' + e); });
  }

  function _gerarVideo() {
    _setLoading('🎬 Iniciando geração de vídeo...', 10);
    var payload = { prompt_expandido: _promptExp, modelo: _modelo };
    if (_usarI2V && _uploadUrl) payload.imagem_url = _uploadUrl;
    fetch('/api/criativos/gerar-video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { _clearLoading(); alert('Erro: ' + data.error); return; }
        _predId = data.prediction_id;
        _pollVideo(0);
      })
      .catch(function (e) { _clearLoading(); alert('Erro: ' + e); });
  }

  function _pollVideo(tentativa) {
    var progresso = Math.min(10 + tentativa * 4, 85);
    _setLoading('🎬 Gerando vídeo (' + (tentativa * 3) + 's)...', progresso);
    fetch('/api/criativos/status/' + _predId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.status === 'succeeded') {
          _clearLoading(); _resultadoUrl = data.url; _mostrarResultado('video');
        } else if (data.status === 'failed') {
          _clearLoading(); alert('Geração falhou: ' + (data.error || 'erro desconhecido'));
        } else {
          // Continuar polling
          _pollTimer = setTimeout(function () { _pollVideo(tentativa + 1); }, 3000);
        }
      })
      .catch(function () { _pollTimer = setTimeout(function () { _pollVideo(tentativa + 1); }, 3000); });
  }

  function _setLoading(texto, progresso) {
    esconder('cri-empty'); esconder('cri-preview-wrap'); esconder('cri-acoes');
    mostrar('cri-loading-wrap');
    _setText('cri-loading-text', texto);
    var fill = document.getElementById('cri-progress-fill');
    if (fill && progresso) fill.style.width = progresso + '%';
    var btn = document.getElementById('cri-btn-gerar');
    if (btn) { btn.textContent = 'Gerando...'; btn.classList.add('loading'); }
  }

  function _clearLoading() {
    esconder('cri-loading-wrap');
    var btn = document.getElementById('cri-btn-gerar');
    if (btn) { btn.textContent = '✦ Gerar Criativo'; btn.classList.remove('loading'); }
  }

  function _mostrarResultado(tipo) {
    esconder('cri-empty'); esconder('cri-loading-wrap');
    mostrar('cri-preview-wrap'); mostrar('cri-acoes');
    var img = document.getElementById('cri-preview-img');
    var vid = document.getElementById('cri-preview-video');
    if (tipo === 'imagem') {
      if (img) { img.src = _resultadoUrl; img.classList.remove('hidden'); }
      if (vid) vid.classList.add('hidden');
    } else {
      if (vid) { vid.src = _resultadoUrl; vid.classList.remove('hidden'); }
      if (img) img.classList.add('hidden');
    }
  }
  function bindResultadoAcoes() {}
  function bindAbas() {}
  function bindHistoricoEvents() {}
  function carregarPastas() {}
  function carregarHistorico() {}

})();
