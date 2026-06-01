// jake_desktop/static/js/ingles.js
(function () {
  'use strict';

  var IState = {
    sessaoId: null,
    gravando: false,
    mediaRecorder: null,
    chunks: [],
    silenceCheck: null,
    licaoAtiva: null,
    trocasMensagens: 0
  };

  // ── Tab switching ────────────────────────────────
  window.ingTab = function (nome, btn) {
    document.querySelectorAll('.ing-tab-panel').forEach(function (p) {
      p.classList.remove('active');
    });
    document.querySelectorAll('.ing-tab-btn').forEach(function (b) {
      b.classList.remove('active');
    });
    document.getElementById('ing-panel-' + nome).classList.add('active');
    btn.classList.add('active');
    if (nome === 'progresso') carregarProgresso();
    if (nome === 'trilha') carregarTrilha();
  };

  // ── Init ─────────────────────────────────────────
  window.initIngles = function () {
    carregarPalavras();
    if (!IState.sessaoId) iniciarSessao();
  };

  // ── Palavras do dia ──────────────────────────────
  function carregarPalavras() {
    var loading = document.getElementById('ing-palavras-loading');
    var lista = document.getElementById('ing-palavras-lista');
    var prog = document.getElementById('ing-prog-count');
    if (loading) loading.style.display = 'block';
    if (lista) lista.innerHTML = '';

    fetch('/api/ingles/palavras-do-dia')
      .then(function (r) { return r.json(); })
      .then(function (palavras) {
        if (loading) loading.style.display = 'none';
        if (!Array.isArray(palavras) || palavras.length === 0) {
          if (loading) { loading.style.display = 'block'; loading.textContent = 'Erro ao carregar palavras.'; }
          return;
        }
        var estudadas = palavras.filter(function (p) { return p.estudada; }).length;
        if (prog) prog.textContent = estudadas + '/' + palavras.length + ' estudadas';
        palavras.forEach(function (p) {
          if (lista) lista.insertAdjacentHTML('beforeend', renderWordCard(p));
        });
      })
      .catch(function () {
        if (loading) { loading.style.display = 'block'; loading.textContent = 'Erro de rede.'; }
      });
  }

  function renderWordCard(p) {
    var estClass = p.estudada ? ' estudada' : '';
    var btnLabel = p.estudada ? '&#10003; Estudada' : 'Marcar estudada';
    var btnDisabled = p.estudada ? ' disabled' : '';
    var foneticaHtml = p.fonetica
      ? '<span class="ing-fonetica"><span style="color:#555;font-size:11px">pronúncia </span>' + esc(p.fonetica) + '</span>'
      : '<span class="ing-fonetica"></span>';
    return '<div class="ing-word-card' + estClass + '" id="ing-card-' + p.id + '">' +
      '<div class="ing-word-card-top">' +
      '<span class="ing-word-title">' + esc(p.palavra) + '</span>' +
      (p.classe_gramatical ? '<span class="ing-pos-badge">' + esc(p.classe_gramatical) + '</span>' : '') +
      (p.categoria ? '<span class="ing-cat-badge">' + esc(p.categoria) + '</span>' : '') +
      '</div>' +
      '<p class="ing-word-def">' + esc(p.definicao_pt) + '</p>' +
      '<p class="ing-word-ex">&ldquo;' + esc(p.exemplo_en) + '&rdquo;</p>' +
      '<div class="ing-word-footer">' +
      foneticaHtml +
      '<button class="ing-btn-sm" onclick="inglesPlayAudioWord(\'' + esc(p.palavra).replace(/'/g, "\\'") + '\',this)" title="Ouvir pronúncia">&#128266;</button>' +
      '<button class="ing-btn-sm' + (p.estudada ? ' done' : '') + '" id="ing-estudada-' + p.id + '" onclick="inglesMarcarEstudada(' + p.id + ')"' + btnDisabled + '>' + btnLabel + '</button>' +
      '</div></div>';
  }

  window.inglesPlayAudioWord = function (palavra, btn) {
    if (btn) { btn.textContent = '...'; }
    fetch('/api/ingles/palavra/audio?palavra=' + encodeURIComponent(palavra))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.audio) {
          if (btn) { btn.innerHTML = '&#128266;'; }
          var msg = d.error || 'Erro ao gerar áudio';
          if (msg.indexOf('Incorrect API key') !== -1 || msg.indexOf('invalid_api_key') !== -1) {
            msg = 'Chave OpenAI inválida — atualize a OPENAI_API_KEY no .env';
          }
          _ingShowToast(msg, 'error');
          return;
        }
        if (btn) { btn.innerHTML = '&#128266;'; }
        new Audio('data:audio/mpeg;base64,' + d.audio).play().catch(function () {});
      })
      .catch(function (e) {
        if (btn) { btn.innerHTML = '&#128266;'; }
        _ingShowToast('Erro de rede: ' + e.message, 'error');
      });
  };

  window.inglesMarcarEstudada = function (id) {
    var btn = document.getElementById('ing-estudada-' + id);
    if (btn) { btn.disabled = true; btn.textContent = '...'; }
    fetch('/api/ingles/atividade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tipo: 'word_studied' })
    })
      .then(function () {
        if (btn) { btn.innerHTML = '&#10003; Estudada'; btn.classList.add('done'); }
        var card = document.getElementById('ing-card-' + id);
        if (card) card.classList.add('estudada');
        var prog = document.getElementById('ing-prog-count');
        if (prog) {
          var m = prog.textContent.match(/(\d+)\/(\d+)/);
          if (m) prog.textContent = (parseInt(m[1]) + 1) + '/' + m[2] + ' estudadas';
        }
      })
      .catch(function () {
        if (btn) { btn.disabled = false; btn.textContent = 'Marcar estudada'; }
      });
  };

  // ── Toast notification ───────────────────────────
  function _ingShowToast(msg, type) {
    var t = document.createElement('div');
    t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);' +
      'background:' + (type === 'error' ? 'rgba(200,50,50,0.92)' : 'rgba(0,180,100,0.92)') + ';' +
      'color:#fff;padding:10px 20px;border-radius:8px;font-size:13px;z-index:9999;' +
      'max-width:80%;text-align:center;box-shadow:0 4px 12px rgba(0,0,0,0.4);';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 5000);
  }

  // ── Voice conversation ───────────────────────────
  function iniciarSessao() {
    fetch('/api/ingles/sessoes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    })
      .then(function (r) { return r.json(); })
      .then(function (d) { IState.sessaoId = d.id || d.sessao_id; });
  }

  window.inglesNovaSessao = function () {
    IState.sessaoId = null;
    var jtext = document.getElementById('ing-jake-text');
    if (jtext) jtext.textContent = 'Click the mic button to start speaking with me!';
    var ubub = document.getElementById('ing-bubble-user');
    if (ubub) ubub.style.display = 'none';
    iniciarSessao();
  };

  window.inglesToggleMic = function () {
    if (IState.gravando) {
      _pararGravacao();
    } else {
      if (!IState.sessaoId) {
        _ingShowToast('Aguarde a sessão carregar e tente novamente.', 'error');
        return;
      }
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function (stream) {
          IState.chunks = [];
          IState.mediaRecorder = new MediaRecorder(stream);
          IState.mediaRecorder.ondataavailable = function (e) {
            if (e.data.size > 0) IState.chunks.push(e.data);
          };
          IState.mediaRecorder.onstop = function () {
            stream.getTracks().forEach(function (t) { t.stop(); });
            if (IState.silenceCheck) { clearInterval(IState.silenceCheck); IState.silenceCheck = null; }
            var blob = new Blob(IState.chunks, { type: 'audio/webm' });
            enviarVoz(blob);
          };
          IState.mediaRecorder.start();
          IState.gravando = true;
          var btn = document.getElementById('ing-mic-btn');
          if (btn) { btn.textContent = '\uD83D\uDD34 Gravando...'; btn.classList.add('gravando'); }

          // ── Silence detection ───────────────────
          try {
            var AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;
            var audioCtx = new AudioCtx();
            var analyser = audioCtx.createAnalyser();
            var source = audioCtx.createMediaStreamSource(stream);
            source.connect(analyser);
            analyser.fftSize = 256;
            var buf = new Uint8Array(analyser.frequencyBinCount);
            var silenceStart = null;
            var recordStart = Date.now();
            var SILENCE_THRESH = 12;
            var SILENCE_MS = 1800;
            var MIN_REC_MS = 800;

            IState.silenceCheck = setInterval(function () {
              if (!IState.gravando) {
                clearInterval(IState.silenceCheck);
                IState.silenceCheck = null;
                audioCtx.close();
                return;
              }
              analyser.getByteTimeDomainData(buf);
              var sum = 0;
              for (var i = 0; i < buf.length; i++) {
                var v = (buf[i] - 128) / 128;
                sum += v * v;
              }
              var rms = Math.sqrt(sum / buf.length) * 100;
              var elapsed = Date.now() - recordStart;

              if (rms < SILENCE_THRESH) {
                if (!silenceStart) silenceStart = Date.now();
                else if (elapsed > MIN_REC_MS && (Date.now() - silenceStart) > SILENCE_MS) {
                  clearInterval(IState.silenceCheck);
                  IState.silenceCheck = null;
                  audioCtx.close();
                  _pararGravacao();
                }
              } else {
                silenceStart = null;
              }
            }, 100);
          } catch (e) {
            // silence detection unavailable — manual stop only
          }
        })
        .catch(function (e) { _ingShowToast('Microfone bloqueado: ' + e.message, 'error'); });
    }
  };

  function _pararGravacao() {
    IState.gravando = false;
    if (IState.silenceCheck) { clearInterval(IState.silenceCheck); IState.silenceCheck = null; }
    if (IState.mediaRecorder && IState.mediaRecorder.state !== 'inactive') {
      IState.mediaRecorder.stop();
    }
    var btn = document.getElementById('ing-mic-btn');
    if (btn) { btn.textContent = '\u23F3 Processando...'; btn.classList.remove('gravando'); }
  }

  function enviarVoz(blob) {
    var btn = document.getElementById('ing-mic-btn');
    if (btn) { btn.disabled = true; }

    var fd = new FormData();
    fd.append('audio', blob, 'audio.webm');
    fd.append('sessao_id', String(IState.sessaoId));
    if (IState.licaoAtiva) {
      fd.append('licao_context', IState.licaoAtiva.cenario + ' | Objetivo: ' + IState.licaoAtiva.objetivo);
    }

    fetch('/api/ingles/conversar/voz', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (btn) { btn.textContent = '\uD83C\uDFA4 Falar com Jake'; btn.disabled = false; }
        if (d.error) {
          var msg = d.error;
          if (msg.indexOf('Incorrect API key') !== -1 || msg.indexOf('invalid_api_key') !== -1) {
            msg = 'Chave OpenAI inválida — atualize a OPENAI_API_KEY no .env';
          }
          _ingShowToast(msg, 'error');
          return;
        }

        var ubub = document.getElementById('ing-bubble-user');
        var utext = document.getElementById('ing-user-text');
        if (ubub) ubub.style.display = 'block';
        if (utext) utext.textContent = d.transcricao;

        var jtext = document.getElementById('ing-jake-text');
        if (jtext) jtext.textContent = d.resposta_en || '';

        var jpt = document.getElementById('ing-jake-pt');
        if (jpt) {
          if (d.resposta_pt) { jpt.textContent = d.resposta_pt; jpt.style.display = 'block'; }
          else jpt.style.display = 'none';
        }

        var jversao = document.getElementById('ing-jake-versao');
        var jversaoText = document.getElementById('ing-jake-versao-text');
        if (jversao && jversaoText) {
          if (d.versao_en) {
            jversaoText.textContent = d.versao_en;
            jversao.style.display = 'block';
          } else {
            jversao.style.display = 'none';
          }
        }

        if (IState.licaoAtiva) {
          IState.trocasMensagens += 1;
          if (IState.trocasMensagens >= 3) {
            var btnCompletar = document.getElementById('ing-btn-completar');
            if (btnCompletar) btnCompletar.style.display = 'block';
          }
        }

        var wrap = document.getElementById('ing-avatar-wrap');
        var audio = new Audio('data:audio/mpeg;base64,' + d.audio_base64);
        if (wrap) wrap.classList.add('speaking');
        audio.play().catch(function () {});
        audio.onended = function () { if (wrap) wrap.classList.remove('speaking'); };
      })
      .catch(function (e) {
        if (btn) { btn.textContent = '\uD83C\uDFA4 Falar com Jake'; btn.disabled = false; }
        _ingShowToast('Erro de rede: ' + e.message, 'error');
      });
  }

  // ── Progresso ────────────────────────────────────
  function carregarProgresso() {
    fetch('/api/ingles/progresso')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var el = document.getElementById('ing-streak');
        if (el) el.textContent = d.streak || 0;
        var tw = document.getElementById('ing-total-palavras');
        if (tw) tw.textContent = d.total_palavras || 0;
        renderCalendario(d.dias_ativos || []);
        renderSessoes(d.sessoes_recentes || []);
      })
      .catch(function () {});
  }

  function renderCalendario(diasAtivos) {
    var cal = document.getElementById('ing-cal');
    if (!cal) return;
    cal.innerHTML = '';
    var hoje = new Date();
    var ano = hoje.getFullYear();
    var mes = hoje.getMonth();
    var diasNoMes = new Date(ano, mes + 1, 0).getDate();
    var diaHoje = hoje.getDate();
    for (var d = 1; d <= diasNoMes; d++) {
      var dd = (d < 10 ? '0' + d : '' + d);
      var mm = ((mes + 1) < 10 ? '0' + (mes + 1) : '' + (mes + 1));
      var dataStr = ano + '-' + mm + '-' + dd;
      var cls = 'ing-cal-day';
      if (diasAtivos.indexOf(dataStr) !== -1) cls += ' active';
      if (d === diaHoje) cls += ' today';
      cal.insertAdjacentHTML('beforeend', '<div class="' + cls + '" title="' + dataStr + '"></div>');
    }
  }

  function renderSessoes(sessoes) {
    var el = document.getElementById('ing-sessoes-lista');
    if (!el) return;
    if (!sessoes.length) {
      el.innerHTML = '<p style="color:#666;font-size:13px">Nenhuma sess\u00e3o ainda.</p>';
      return;
    }
    el.innerHTML = sessoes.map(function (s) {
      return '<div class="ing-sessao-item"><span>' + esc(s.tema || 'Conversa livre') + '</span><span>' + esc((s.created_at || '').slice(0, 10)) + '</span></div>';
    }).join('');
  }

  // ── Trilha ───────────────────────────────────────
  function carregarTrilha() {
    var loading = document.getElementById('ing-trilha-loading');
    var lista = document.getElementById('ing-trilha-lista');
    if (loading) loading.style.display = 'block';
    if (lista) lista.innerHTML = '';
    fetch('/api/ingles/trilha')
      .then(function (r) { return r.json(); })
      .then(function (modulos) {
        if (loading) loading.style.display = 'none';
        modulos.forEach(function (m) {
          if (lista) lista.insertAdjacentHTML('beforeend', renderModulo(m));
        });
      })
      .catch(function () {
        if (loading) loading.textContent = 'Erro ao carregar trilha.';
      });
  }

  function renderModulo(m) {
    var pct = m.progresso.total > 0 ? Math.round(m.progresso.concluidas / m.progresso.total * 100) : 0;
    var licoesHtml = m.licoes.map(function (l) {
      var done = l.status === 'completed';
      var isAtiva = IState.licaoAtiva && IState.licaoAtiva.moduloId === m.id && IState.licaoAtiva.licaoId === l.id;
      return '<div class="ing-licao-item">' +
        '<div class="ing-licao-status' + (done ? ' completed' : '') + '">' + (done ? '\u2713' : '') + '</div>' +
        '<div class="ing-licao-info">' +
        '<div class="ing-licao-titulo">' + esc(l.titulo) + '</div>' +
        '<div class="ing-licao-obj">' + esc(l.objetivo) + '</div>' +
        '</div>' +
        '<button class="ing-licao-btn' + (isAtiva ? ' active-lesson' : '') + '" ' +
        'onclick="ingPraticarLicao(' + m.id + ',' + l.id + ',' +
        '\'' + esc(l.titulo).replace(/\\/g,'\\\\').replace(/'/g,"\\'") + '\',' +
        '\'' + esc(l.cenario).replace(/\\/g,'\\\\').replace(/'/g,"\\'") + '\',' +
        '\'' + esc(l.objetivo).replace(/\\/g,'\\\\').replace(/'/g,"\\'") + '\')">' +
        (isAtiva ? '\u25B6 Praticando' : (done ? '\u21A9 Repetir' : '\u25B6 Praticar')) +
        '</button>' +
        '</div>';
    }).join('');
    return '<div class="ing-modulo-card" id="ing-mod-' + m.id + '">' +
      '<div class="ing-modulo-header" onclick="ingToggleModulo(' + m.id + ')">' +
      '<span class="ing-modulo-icone">' + esc(m.icone) + '</span>' +
      '<div class="ing-modulo-info">' +
      '<div class="ing-modulo-titulo">' + m.id + '. ' + esc(m.titulo) + '</div>' +
      '<div class="ing-modulo-desc">' + esc(m.descricao) + '</div>' +
      '</div>' +
      '<div class="ing-modulo-prog">' +
      '<span class="ing-modulo-prog-text">' + m.progresso.concluidas + '/' + m.progresso.total + '</span>' +
      '<div class="ing-modulo-prog-bar"><div class="ing-modulo-prog-fill" style="width:' + pct + '%"></div></div>' +
      '</div>' +
      '<span class="ing-modulo-arrow">\u25B6</span>' +
      '</div>' +
      '<div class="ing-licoes-lista">' + licoesHtml + '</div>' +
      '</div>';
  }

  window.ingToggleModulo = function (id) {
    var card = document.getElementById('ing-mod-' + id);
    if (card) card.classList.toggle('open');
  };

  window.ingPraticarLicao = function (moduloId, licaoId, titulo, cenario, objetivo) {
    IState.licaoAtiva = { moduloId: moduloId, licaoId: licaoId, titulo: titulo, cenario: cenario, objetivo: objetivo };
    IState.trocasMensagens = 0;
    var ctx = document.getElementById('ing-licao-context');
    var ctxText = document.getElementById('ing-licao-context-text');
    if (ctx) ctx.style.display = 'block';
    if (ctxText) ctxText.textContent = titulo + ' \u2014 ' + cenario;
    var btnCompletar = document.getElementById('ing-btn-completar');
    if (btnCompletar) btnCompletar.style.display = 'none';
    var jtext = document.getElementById('ing-jake-text');
    if (jtext) jtext.textContent = 'Ready! ' + cenario + ' Start whenever you\'re ready!';
    var ubub = document.getElementById('ing-bubble-user');
    if (ubub) ubub.style.display = 'none';
    IState.sessaoId = null;
    iniciarSessao();
    document.querySelectorAll('.ing-tab-panel').forEach(function (p) { p.classList.remove('active'); });
    document.querySelectorAll('.ing-tab-btn').forEach(function (b) { b.classList.remove('active'); });
    var conversar = document.getElementById('ing-panel-conversar');
    if (conversar) conversar.classList.add('active');
    document.querySelectorAll('.ing-tab-btn').forEach(function (b) {
      if (b.textContent.indexOf('Conversar') !== -1) b.classList.add('active');
    });
  };

  window.ingCompletarLicao = function () {
    if (!IState.licaoAtiva) return;
    fetch('/api/ingles/trilha/completar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modulo_id: IState.licaoAtiva.moduloId, licao_id: IState.licaoAtiva.licaoId })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) {
          _ingShowToast('Li\u00e7\u00e3o conclu\u00edda! \uD83C\uDF89', 'success');
          var btnCompletar = document.getElementById('ing-btn-completar');
          if (btnCompletar) btnCompletar.style.display = 'none';
          IState.licaoAtiva = null;
          var ctx = document.getElementById('ing-licao-context');
          if (ctx) ctx.style.display = 'none';
        }
      });
  };

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

})();
