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
  function bindUpload() {}
  function bindPromptActions() {}
  function bindGerarBtn() {}
  function bindResultadoAcoes() {}
  function bindAbas() {}
  function bindHistoricoEvents() {}
  function carregarPastas() {}
  function carregarHistorico() {}

})();
