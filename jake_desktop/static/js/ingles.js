// jake_desktop/static/js/ingles.js
(function () {
  'use strict';

  var IState = {
    sessaoId: null,
    gravando: false,
    mediaRecorder: null,
    chunks: []
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
    return '<div class="ing-word-card' + estClass + '" id="ing-card-' + p.id + '">' +
      '<div class="ing-word-card-top">' +
      '<span class="ing-word-title">' + esc(p.palavra) + '</span>' +
      (p.classe_gramatical ? '<span class="ing-pos-badge">' + esc(p.classe_gramatical) + '</span>' : '') +
      (p.categoria ? '<span class="ing-cat-badge">' + esc(p.categoria) + '</span>' : '') +
      '</div>' +
      '<p class="ing-word-def">' + esc(p.definicao_pt) + '</p>' +
      '<p class="ing-word-ex">&ldquo;' + esc(p.exemplo_en) + '&rdquo;</p>' +
      '<div class="ing-word-footer">' +
      '<span class="ing-fonetica">' + esc(p.fonetica || '') + '</span>' +
      '<button class="ing-btn-sm" onclick="inglesPlayAudioWord(\'' + esc(p.palavra).replace(/'/g, "\\'") + '\',this)">&#128266;</button>' +
      '<button class="ing-btn-sm' + (p.estudada ? ' done' : '') + '" id="ing-estudada-' + p.id + '" onclick="inglesMarcarEstudada(' + p.id + ')"' + btnDisabled + '>' + btnLabel + '</button>' +
      '</div></div>';
  }

  window.inglesPlayAudioWord = function (palavra, btn) {
    if (btn) btn.textContent = '...';
    fetch('/api/ingles/palavra/audio?palavra=' + encodeURIComponent(palavra))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (btn) btn.innerHTML = '&#128266;';
        if (!d.audio) { if (btn) btn.textContent = '!'; return; }
        new Audio('data:audio/mpeg;base64,' + d.audio).play().catch(function () {});
      })
      .catch(function () { if (btn) btn.innerHTML = '&#128266;'; });
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
    var btn = document.getElementById('ing-mic-btn');
    if (IState.gravando) {
      if (IState.mediaRecorder) IState.mediaRecorder.stop();
      IState.gravando = false;
    } else {
      if (!IState.sessaoId) {
        alert('Aguarde a sessão carregar e tente novamente.');
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
            var blob = new Blob(IState.chunks, { type: 'audio/webm' });
            enviarVoz(blob);
          };
          IState.mediaRecorder.start();
          IState.gravando = true;
          if (btn) { btn.textContent = '\u23F9 Parar'; btn.classList.add('gravando'); }
        })
        .catch(function (e) { alert('Microfone bloqueado: ' + e.message); });
    }
  };

  function enviarVoz(blob) {
    var btn = document.getElementById('ing-mic-btn');
    if (btn) { btn.textContent = '\u23F3 Processando...'; btn.classList.remove('gravando'); btn.disabled = true; }

    var fd = new FormData();
    fd.append('audio', blob, 'audio.webm');
    fd.append('sessao_id', String(IState.sessaoId));

    fetch('/api/ingles/conversar/voz', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (btn) { btn.textContent = '\uD83C\uDFA4 Falar com Jake'; btn.disabled = false; }
        if (d.error) { alert('Erro: ' + d.error); return; }

        var ubub = document.getElementById('ing-bubble-user');
        var utext = document.getElementById('ing-user-text');
        if (ubub) ubub.style.display = 'block';
        if (utext) utext.textContent = d.transcricao;

        var jtext = document.getElementById('ing-jake-text');
        if (jtext) jtext.textContent = d.resposta_texto;

        var wrap = document.getElementById('ing-avatar-wrap');
        var audio = new Audio('data:audio/mpeg;base64,' + d.audio_base64);
        if (wrap) wrap.classList.add('speaking');
        audio.play().catch(function () {});
        audio.onended = function () { if (wrap) wrap.classList.remove('speaking'); };
      })
      .catch(function (e) {
        if (btn) { btn.textContent = '\uD83C\uDFA4 Falar com Jake'; btn.disabled = false; }
        alert('Erro de rede: ' + e.message);
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

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

})();
