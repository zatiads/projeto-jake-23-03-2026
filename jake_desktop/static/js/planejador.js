/* planejador.js — Planejador de Campanhas IIFE */
(function () {
  'use strict';

  var _messages  = [];
  var _params    = {};
  var _estado    = 'chat';
  var _gravando  = false;
  var _recorder  = null;
  var _chunks    = [];
  var _evtSource = null;

  window.planejadorInit = function () {
    if (_estado === 'chat' && _messages.length === 0) {
      _addMsgJake('Olá! Me diga qual campanha você quer criar. Pode mandar texto ou áudio 🎤');
    }
    var inp = document.getElementById('plan-input');
    if (inp) inp.focus();
    _syncInput();
  };

  window.planejadorEnviar = function () {
    if (_estado !== 'chat') return;
    var inp = document.getElementById('plan-input');
    if (!inp) return;
    var texto = inp.value.trim();
    if (!texto) return;
    inp.value = '';

    _addMsgUser(texto);
    _messages.push({role: 'user', content: texto});
    _showTyping();
    _syncInput();

    fetch('/api/planejador/interpretar', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({messages: _messages, params: _params}),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        _removeTyping();
        if (d.error) {
          _addMsgErro(d.error);
          _syncInput();
          return;
        }
        if (d.params) {
          Object.keys(d.params).forEach(function (k) {
            if (d.params[k] !== null && d.params[k] !== undefined) {
              _params[k] = d.params[k];
            }
          });
        }
        if (d.pronto) {
          _messages.push({role: 'assistant', content: d.resposta || ''});
          _estado = 'confirmando';
          if (d.resposta) _addMsgJake(d.resposta);
          _renderCard();
          _syncInput();
        } else {
          var resposta = d.resposta || 'Hmm, pode reformular?';
          _addMsgJake(resposta);
          _messages.push({role: 'assistant', content: resposta});
          _syncInput();
        }
      })
      .catch(function (e) {
        _removeTyping();
        _addMsgErro('Erro de conexão: ' + e.message);
        _syncInput();
      });
  };

  window.planejadorConfirmar = function () {
    if (_estado !== 'confirmando') return;
    _estado = 'subindo';
    _syncInput();

    var btns = document.querySelector('.plan-card-btns');
    if (btns) btns.style.display = 'none';

    fetch('/api/planejador/subir', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(_params),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (e) { throw new Error(e.error || r.statusText); });
        return r.json();
      })
      .then(function (d) {
        var token = d.token;
        _evtSource = new EventSource('/api/planejador/subir/stream/' + token);
        _evtSource.onmessage = function (e) {
          var ev = JSON.parse(e.data);
          if (ev.status === 'concluido') {
            _evtSource.close();
            _estado = 'concluido';
            _addMsgJake('✅ ' + ev.msg + (ev.campaign_id ? '\nCampaign ID: ' + ev.campaign_id : ''));
            _syncInput();
          } else if (ev.status === 'erro') {
            _evtSource.close();
            _estado = 'chat';
            _addMsgErro('❌ ' + ev.msg);
            _syncInput();
          } else {
            _addMsgProgress('⏳ ' + ev.msg);
          }
        };
        _evtSource.onerror = function () {
          _evtSource.close();
          _estado = 'chat';
          _addMsgErro('Conexão SSE perdida. Tente novamente.');
          _syncInput();
        };
      })
      .catch(function (e) {
        _estado = 'chat';
        _addMsgErro('Erro ao iniciar: ' + e.message);
        if (btns) btns.style.display = '';
        _syncInput();
      });
  };

  window.planejadorCancelar = function () {
    _estado = 'chat';
    var chat = document.getElementById('plan-chat');
    if (chat) {
      var cards = chat.querySelectorAll('.plan-msg-card');
      if (cards.length) cards[cards.length - 1].remove();
    }
    _addMsgJake('Ok! Me diga o que quer ajustar.');
    _syncInput();
  };

  window.planejadorNovaConversa = function () {
    if (_evtSource) { _evtSource.close(); _evtSource = null; }
    _messages = [];
    _params   = {};
    _estado   = 'chat';
    var chat = document.getElementById('plan-chat');
    if (chat) chat.innerHTML = '';
    _syncInput();
    planejadorInit();
  };

  window.planejadorToggleMic = function () {
    if (_gravando) {
      _pararGravacao();
    } else {
      _iniciarGravacao();
    }
  };

  function _iniciarGravacao() {
    if (!navigator.mediaDevices) {
      alert('Microfone não suportado neste browser.');
      return;
    }
    navigator.mediaDevices.getUserMedia({audio: true})
      .then(function (stream) {
        _chunks = [];
        var mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : MediaRecorder.isTypeSupported('audio/mp4')
            ? 'audio/mp4'
            : 'audio/ogg';
        _recorder = new MediaRecorder(stream, {mimeType: mimeType});
        _recorder.ondataavailable = function (e) {
          if (e.data.size > 0) _chunks.push(e.data);
        };
        _recorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          var blob = new Blob(_chunks, {type: mimeType});
          _transcrever(blob, mimeType);
        };
        _recorder.start();
        _gravando = true;
        var btn = document.getElementById('plan-mic-btn');
        if (btn) btn.classList.add('gravando');
      })
      .catch(function (e) {
        alert('Erro ao acessar microfone: ' + e.message);
      });
  }

  function _pararGravacao() {
    if (_recorder && _recorder.state !== 'inactive') _recorder.stop();
    _gravando = false;
    var btn = document.getElementById('plan-mic-btn');
    if (btn) btn.classList.remove('gravando');
  }

  function _transcrever(blob, mimeType) {
    var ext = mimeType.indexOf('mp4') !== -1 ? '.mp4'
            : mimeType.indexOf('ogg') !== -1 ? '.ogg' : '.webm';
    var fd = new FormData();
    fd.append('audio', blob, 'audio' + ext);
    fetch('/api/planejador/transcrever', {method: 'POST', body: fd})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.error) { _addMsgErro('Transcrição falhou: ' + d.error); return; }
        var inp = document.getElementById('plan-input');
        if (inp) { inp.value = d.text; inp.focus(); }
      })
      .catch(function (e) { _addMsgErro('Erro de transcrição: ' + e.message); });
  }

  function _addMsgUser(texto) {
    _appendChat('<div class="plan-msg-user">' + _esc(texto) + '</div>');
  }

  function _addMsgJake(texto) {
    _appendChat('<div class="plan-msg-jake">' + _esc(texto).replace(/\n/g, '<br>') + '</div>');
  }

  function _addMsgErro(texto) {
    _appendChat('<div class="plan-msg-erro">' + _esc(texto) + '</div>');
  }

  function _addMsgProgress(texto) {
    _appendChat('<div class="plan-msg-progress">' + _esc(texto) + '</div>');
  }

  function _showTyping() {
    var el = document.createElement('div');
    el.id = 'plan-typing-indicator';
    el.className = 'plan-typing';
    el.innerHTML = '<span></span><span></span><span></span>';
    var chat = document.getElementById('plan-chat');
    if (chat) { chat.appendChild(el); chat.scrollTop = chat.scrollHeight; }
  }

  function _removeTyping() {
    var el = document.getElementById('plan-typing-indicator');
    if (el) el.remove();
  }

  function _renderCard() {
    var p   = _params;
    var obj = {'MESSAGES': 'Mensagens', 'ENGAGEMENT': 'Engajamento', 'PURCHASE': 'Conversões'};
    var link = p.drive_link
      ? p.drive_link.replace(/https?:\/\/(www\.)?/, '').substring(0, 35) + '…'
      : '—';

    var html =
      '<div class="plan-msg-card">' +
        '<div class="plan-card-title">RESUMO DA CAMPANHA</div>' +
        '<div class="plan-card-rows">' +
          _row('Cliente',   p.cliente_nome || '—') +
          _row('Objetivo',  obj[p.objetivo] || p.objetivo || '—') +
          _row('Drive',     link) +
          _row('Orçamento', p.orcamento_diario ? 'R$ ' + Number(p.orcamento_diario).toFixed(0) + '/dia' : '—') +
          _row('Público',   p.publico_descricao || '(padrão do cliente)') +
          (p.copy_titulo ? _row('Copy', '"' + p.copy_titulo + '"') : '') +
        '</div>' +
        '<div class="plan-card-btns">' +
          '<button class="anu-btn-primary" style="font-size:11px" onclick="planejadorConfirmar()">Confirmar e Subir</button>' +
          '<button class="anu-btn-secondary" style="font-size:11px" onclick="planejadorCancelar()">Ajustar</button>' +
        '</div>' +
      '</div>';
    _appendChat(html);
  }

  function _row(label, value) {
    return '<div class="plan-card-row"><span class="plan-card-label">' + _esc(label) + '</span>' +
           '<span class="plan-card-value">' + _esc(String(value)) + '</span></div>';
  }

  function _appendChat(html) {
    var chat = document.getElementById('plan-chat');
    if (!chat) return;
    var div = document.createElement('div');
    div.innerHTML = html;
    while (div.firstChild) chat.appendChild(div.firstChild);
    chat.scrollTop = chat.scrollHeight;
  }

  function _syncInput() {
    var inp      = document.getElementById('plan-input');
    var send     = document.querySelector('.plan-send-btn');
    var mic      = document.getElementById('plan-mic-btn');
    var disabled = _estado !== 'chat';
    if (inp)  inp.disabled  = disabled;
    if (send) send.disabled = disabled;
    if (mic)  mic.disabled  = disabled;
  }

  function _esc(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

}());
