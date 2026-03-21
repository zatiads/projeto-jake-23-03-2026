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
  function bindResultadoAcoes() {
    var btnDl = document.getElementById('cri-btn-download');
    if (btnDl) btnDl.addEventListener('click', function () {
      if (!_resultadoUrl) return;
      var a = document.createElement('a');
      a.href = _resultadoUrl; a.download = 'criativo-jakeos.' + (_tipo === 'video' ? 'mp4' : 'webp');
      a.target = '_blank'; a.click();
    });

    var btnAnu = document.getElementById('cri-btn-enviar-anuncios');
    if (btnAnu) btnAnu.addEventListener('click', function () {
      if (!_resultadoUrl) return;
      if (window.JakeAnuncios && window.JakeAnuncios.receberCriativo) {
        window.JakeAnuncios.receberCriativo({ url: _resultadoUrl, tipo: _tipo });
      } else {
        alert('Abra a aba Subir Anúncios e use a URL: ' + _resultadoUrl);
      }
    });

    var btnSalvar = document.getElementById('cri-btn-salvar-historico');
    if (btnSalvar) btnSalvar.addEventListener('click', _abrirModalSalvar);

    var btnCancelar = document.getElementById('cri-modal-salvar-cancelar');
    if (btnCancelar) btnCancelar.addEventListener('click', function () { esconder('cri-modal-salvar'); });

    var btnConfirmar = document.getElementById('cri-modal-salvar-confirmar');
    if (btnConfirmar) btnConfirmar.addEventListener('click', _confirmarSalvar);
  }

  function _abrirModalSalvar() {
    if (!_resultadoUrl) return;
    carregarPastasModal();
    mostrar('cri-modal-salvar');
  }

  function carregarPastasModal() {
    var sel = document.getElementById('cri-modal-pasta');
    if (!sel) return;
    fetch('/api/criativos/pastas')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        sel.innerHTML = '<option value="">Sem pasta</option>' +
          (data.pastas || []).map(function (p) {
            return '<option value="' + p.id + '">' + _esc(p.nome) + '</option>';
          }).join('');
      });
  }

  function _confirmarSalvar() {
    var folderId = _val('cri-modal-pasta') || null;
    var payload = {
      tipo: _tipo, modo: _modo, modelo: _modelo,
      prompt_original: _val('cri-prompt') || '(referência)',
      prompt_expandido: _promptExp || _val('cri-expandido-texto'),
      url_resultado: _resultadoUrl,
      folder_id: folderId ? parseInt(folderId) : null,
    };
    fetch('/api/criativos/historico', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        esconder('cri-modal-salvar');
        if (data.error) { alert('Erro ao salvar: ' + data.error); return; }
        carregarHistorico();
      })
      .catch(function (e) { alert('Erro: ' + e); });
  }

  function bindAbas() {
    document.querySelectorAll('.cri-aba').forEach(function (aba) {
      aba.addEventListener('click', function () {
        var alvo = this.dataset.aba;
        document.querySelectorAll('.cri-aba').forEach(function (a) { a.classList.remove('active'); });
        this.classList.add('active');
        if (alvo === 'resultado') {
          mostrar('cri-painel-resultado'); esconder('cri-painel-historico');
        } else {
          esconder('cri-painel-resultado'); mostrar('cri-painel-historico');
          carregarHistorico();
        }
      });
    });
  }

  function carregarPastas() {
    fetch('/api/criativos/pastas')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var sel = document.getElementById('cri-filtro-pasta');
        if (!sel) return;
        sel.innerHTML = '<option value="">Todas as pastas</option>' +
          (data.pastas || []).map(function (p) {
            return '<option value="' + p.id + '">' + _esc(p.nome) + '</option>';
          }).join('');
      });
  }

  function bindHistoricoEvents() {
    var filtPasta = document.getElementById('cri-filtro-pasta');
    var filtTipo  = document.getElementById('cri-filtro-tipo');
    if (filtPasta) filtPasta.addEventListener('change', function () {
      _histFiltros.folder_id = this.value; _histPage = 1; carregarHistorico();
    });
    if (filtTipo) filtTipo.addEventListener('change', function () {
      _histFiltros.tipo = this.value; _histPage = 1; carregarHistorico();
    });

    var btnNovaPasta = document.getElementById('cri-btn-nova-pasta');
    if (btnNovaPasta) btnNovaPasta.addEventListener('click', function () {
      var nome = prompt('Nome da nova pasta:');
      if (!nome || !nome.trim()) return;
      fetch('/api/criativos/pastas', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome: nome.trim() }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.error) { alert('Erro: ' + data.error); return; }
          carregarPastas(); carregarHistorico();
        });
    });

    // Deletar pasta selecionada no filtro (com aviso de quantos criativos serão desvinculados)
    var btnDelPasta = document.getElementById('cri-btn-del-pasta');
    if (btnDelPasta) btnDelPasta.addEventListener('click', function () {
      var sel = document.getElementById('cri-filtro-pasta');
      var pid = sel && sel.value;
      if (!pid) { alert('Selecione uma pasta no filtro para deletar.'); return; }
      var nomePasta = sel.options[sel.selectedIndex].text;
      // Primeiro busca contagem de criativos na pasta
      fetch('/api/criativos/historico?folder_id=' + pid + '&limit=1')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var n = data.total || 0;
          var msg = n > 0
            ? 'Deletar pasta "' + nomePasta + '"?\n' + n + ' criativo(s) serão desvinculados (não deletados).'
            : 'Deletar pasta "' + nomePasta + '"? Está vazia.';
          if (!confirm(msg)) return;
          fetch('/api/criativos/pastas/' + pid, { method: 'DELETE' })
            .then(function () { carregarPastas(); _histFiltros.folder_id = ''; carregarHistorico(); });
        });
    });

    var btnAnterior = document.getElementById('cri-pag-anterior');
    var btnProximo  = document.getElementById('cri-pag-proximo');
    if (btnAnterior) btnAnterior.addEventListener('click', function () {
      if (_histPage > 1) { _histPage--; carregarHistorico(); }
    });
    if (btnProximo) btnProximo.addEventListener('click', function () {
      _histPage++; carregarHistorico();
    });
  }

  function carregarHistorico() {
    var params = '?page=' + _histPage + '&limit=20';
    if (_histFiltros.folder_id) params += '&folder_id=' + _histFiltros.folder_id;
    if (_histFiltros.tipo)      params += '&tipo=' + _histFiltros.tipo;
    fetch('/api/criativos/historico' + params)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var grid = document.getElementById('cri-historico-grid');
        if (!grid) return;
        var items = data.items || [];
        if (!items.length) {
          grid.innerHTML = '<div class="cri-historico-empty">Nenhum criativo salvo</div>';
        } else {
          grid.innerHTML = items.map(function (item) {
            var thumb = item.tipo === 'video'
              ? '<video class="cri-hist-thumb-video" src="' + _esc(item.url_resultado) + '" muted></video>'
              : '<img class="cri-hist-thumb" src="' + _esc(item.url_resultado) + '" alt="">';
            var data_fmt = item.criado_em ? item.criado_em.substring(0, 10) : '';
            return '<div class="cri-hist-card" data-id="' + item.id + '">' +
              thumb +
              '<div class="cri-hist-info">' +
              '<span class="cri-hist-modelo">' + _esc(item.modelo) + '</span>' +
              '<span class="cri-hist-data">' + data_fmt + '</span>' +
              '<div class="cri-hist-acoes">' +
              '<button class="cri-hist-btn cri-hist-btn-dl" title="Download" data-url="' + _esc(item.url_resultado) + '" data-tipo="' + item.tipo + '">⬇</button>' +
              '<button class="cri-hist-btn cri-hist-btn-pasta" title="Mover de pasta" data-id="' + item.id + '">📁</button>' +
              '<button class="cri-hist-btn cri-hist-btn-del" title="Deletar" data-id="' + item.id + '">✕</button>' +
              '</div></div></div>';
          }).join('');
          // Bind actions
          grid.querySelectorAll('.cri-hist-btn-dl').forEach(function (btn) {
            btn.addEventListener('click', function () {
              var a = document.createElement('a');
              a.href = this.dataset.url; a.download = 'criativo.' + (this.dataset.tipo === 'video' ? 'mp4' : 'webp');
              a.target = '_blank'; a.click();
            });
          });
          grid.querySelectorAll('.cri-hist-btn-del').forEach(function (btn) {
            btn.addEventListener('click', function () {
              if (!confirm('Deletar este criativo do histórico?')) return;
              var id = this.dataset.id;
              fetch('/api/criativos/historico/' + id, { method: 'DELETE' })
                .then(function () { carregarHistorico(); });
            });
          });
          grid.querySelectorAll('.cri-hist-btn-pasta').forEach(function (btn) {
            btn.addEventListener('click', function () {
              var id = this.dataset.id;
              carregarPastas(); // garante lista atualizada
              fetch('/api/criativos/pastas')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                  var opcoes = ['Sem pasta (null)'].concat((data.pastas || []).map(function (p, i) { return (i + 1) + ') ' + p.nome; }));
                  var escolha = prompt('Mover para pasta:\n' + opcoes.join('\n') + '\n\nDigite 0 para sem pasta, ou o número da pasta:');
                  if (escolha === null) return;
                  var idx = parseInt(escolha);
                  var folderId = idx === 0 ? null : ((data.pastas || [])[idx - 1] || {}).id || null;
                  fetch('/api/criativos/historico/' + id + '/pasta', {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder_id: folderId }),
                  }).then(function () { carregarHistorico(); });
                });
            });
          });
        }
        // Paginação
        var total = data.total || 0;
        var pages = data.pages || 1;
        _setText('cri-pag-info', _histPage + ' / ' + pages);
        var btnAnt = document.getElementById('cri-pag-anterior');
        var btnPro = document.getElementById('cri-pag-proximo');
        if (btnAnt) btnAnt.disabled = _histPage <= 1;
        if (btnPro) btnPro.disabled = _histPage >= pages;
      });
  }

})();
