// jake_desktop/static/js/ingles.js
(function () {
  'use strict';

  var IState = {
    palavraId: null,
    palavraTexto: '',
    sessaoId: null,
    enviando: false,
  };

  // ── INIT ─────────────────────────────────────────────────────────────────
  window.initIngles = function () {
    bindTabs();
    carregarPalavra();
  };

  // ── TABS ─────────────────────────────────────────────────────────────────
  function bindTabs() {
    document.querySelectorAll('.ing-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var tab = this.dataset.tab;
        document.querySelectorAll('.ing-tab').forEach(function (b) { b.classList.remove('active'); });
        document.querySelectorAll('.ing-tab-content').forEach(function (c) { c.classList.remove('active'); });
        this.classList.add('active');
        var el = document.getElementById('ing-tab-' + tab);
        if (el) el.classList.add('active');
        if (tab === 'conversar' && !IState.sessaoId) iniciarSessao();
        if (tab === 'progresso') carregarProgresso();
      }.bind(btn));
    });
  }

  // ── PALAVRA DO DIA ────────────────────────────────────────────────────────
  function carregarPalavra() {
    var loading = document.getElementById('ing-palavra-loading');
    var card = document.getElementById('ing-palavra-card');
    if (loading) loading.style.display = 'block';
    if (card) card.style.display = 'none';

    fetch('/api/ingles/palavra-do-dia')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.error) { if (loading) loading.textContent = 'Erro: ' + d.error; return; }
        IState.palavraId = d.id;
        IState.palavraTexto = d.palavra;
        document.getElementById('ing-word-text').textContent = d.palavra;
        document.getElementById('ing-pos-text').textContent = d.classe_gramatical || '';
        document.getElementById('ing-def-text').textContent = d.definicao_pt || '';
        document.getElementById('ing-example-text').textContent = '"' + (d.exemplo_en || '') + '"';
        document.getElementById('ing-fonetica-text').textContent = d.fonetica || '';
        if (d.estudada) {
          var btn = document.getElementById('ing-btn-estudada');
          if (btn) { btn.textContent = '✓ Estudada'; btn.classList.add('done'); btn.disabled = true; }
        }
        if (loading) loading.style.display = 'none';
        if (card) card.style.display = 'block';
      })
      .catch(function () {
        if (loading) loading.textContent = 'Erro ao carregar palavra.';
      });
  }

  window.inglesPlayAudio = function () {
    if (!IState.palavraTexto) return;
    fetch('/api/ingles/palavra/audio?palavra=' + encodeURIComponent(IState.palavraTexto))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.audio) return;
        var player = document.getElementById('ing-audio-player');
        player.src = 'data:audio/mpeg;base64,' + d.audio;
        player.play();
        fetch('/api/ingles/atividade', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({tipo: 'audio_played'})
        });
      });
  };

  window.inglesMarcarEstudada = function () {
    fetch('/api/ingles/atividade', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tipo: 'word_studied'})
    }).then(function (r) { return r.json(); })
      .then(function () {
        var btn = document.getElementById('ing-btn-estudada');
        if (btn) { btn.textContent = '✓ Estudada'; btn.classList.add('done'); btn.disabled = true; }
      });
  };

  // ── CONVERSAR ─────────────────────────────────────────────────────────────
  function iniciarSessao() {
    var box = document.getElementById('ing-chat-box');
    if (box) box.innerHTML = '<div class="ing-loading">Iniciando sessão...</div>';
    fetch('/api/ingles/sessoes', {method: 'POST'})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        IState.sessaoId = d.id;
        var badge = document.getElementById('ing-tema-badge');
        if (badge) badge.textContent = 'Topic: ' + (d.tema || '');
        renderMensagem('assistant', "Hi! I'm Jake, your English practice partner. Today's topic: " + (d.tema || 'free conversation') + ". How are you doing today?");
      });
  }

  window.inglesNovaSessao = function () {
    IState.sessaoId = null;
    iniciarSessao();
  };

  window.inglesEnviarMensagem = function (e) {
    e.preventDefault();
    if (IState.enviando) return false;
    var input = document.getElementById('ing-chat-input');
    var texto = (input.value || '').trim();
    if (!texto || !IState.sessaoId) return false;
    input.value = '';
    renderMensagem('user', texto);
    IState.enviando = true;
    var sendBtn = document.querySelector('.ing-chat-send');
    if (sendBtn) sendBtn.disabled = true;
    fetch('/api/ingles/sessoes/' + IState.sessaoId + '/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mensagem: texto})
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        IState.enviando = false;
        if (sendBtn) sendBtn.disabled = false;
        if (d.error) { renderMensagem('assistant', '⚠️ ' + d.error); return; }
        renderMensagem('assistant', d.resposta);
      })
      .catch(function () {
        IState.enviando = false;
        if (sendBtn) sendBtn.disabled = false;
        renderMensagem('assistant', '⚠️ Connection error. Try again.');
      });
    return false;
  };

  function renderMensagem(role, texto) {
    var box = document.getElementById('ing-chat-box');
    if (!box) return;
    var loading = box.querySelector('.ing-loading');
    if (loading) loading.remove();
    var div = document.createElement('div');
    div.className = 'ing-msg ' + role;
    div.textContent = texto;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  // ── PROGRESSO ────────────────────────────────────────────────────────────
  function carregarProgresso() {
    fetch('/api/ingles/progresso')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var streakEl = document.getElementById('ing-streak-val');
        var totalEl = document.getElementById('ing-total-val');
        if (streakEl) streakEl.textContent = d.streak + ' dias';
        if (totalEl) totalEl.textContent = d.total_palavras;
        renderCalendario(d.calendario || []);
        renderSessoes(d.ultimas_sessoes || []);
      });
  }

  function renderCalendario(diasEstudados) {
    var cal = document.getElementById('ing-cal');
    if (!cal) return;
    var hoje = new Date();
    var ano = hoje.getFullYear();
    var mes = hoje.getMonth();
    var diasNoMes = new Date(ano, mes + 1, 0).getDate();
    var html = '';
    for (var d = 1; d <= diasNoMes; d++) {
      var dataStr = ano + '-' + String(mes + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      var cls = diasEstudados.indexOf(dataStr) !== -1 ? 'ing-cal-day studied' : 'ing-cal-day';
      html += '<div class="' + cls + '">' + d + '</div>';
    }
    cal.innerHTML = html;
  }

  function renderSessoes(sessoes) {
    var lista = document.getElementById('ing-sessions-list');
    if (!lista) return;
    if (!sessoes.length) { lista.innerHTML = '<div class="ing-loading">Nenhuma sessão ainda.</div>'; return; }
    lista.innerHTML = sessoes.map(function (s) {
      var data = s.created_at ? s.created_at.substring(0, 10) : '';
      return '<div class="ing-session-item">' +
        '<span class="ing-session-tema">' + esc(s.tema || 'conversa') + '</span>' +
        '<span class="ing-session-data">' + data + '</span>' +
        '</div>';
    }).join('');
  }

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

})();
