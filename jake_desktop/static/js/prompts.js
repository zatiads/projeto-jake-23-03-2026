(function () {
  'use strict';

  // ── Estado ────────────────────────────────────────────────────
  var currentSessionId = null;
  var isWaiting = false;
  var primeiraMsg = null; // primeira mensagem do usuário na sessão atual (para fallback de título)

  // ── Mensagem de boas-vindas (exibida localmente, sem chamar API) ──
  var WELCOME_MSG = 'Olá! Sou seu <strong>Engenheiro de Prompts Sênior</strong>, com mais de 20 anos estruturando prompts de alta performance.\n\nMeu processo: você me apresenta uma ideia ou projeto, eu faço de <strong>5 a 7 perguntas estratégicas</strong> para entender o contexto, e então gero um <strong>prompt estruturado e assertivo</strong> pronto para uso.\n\nMe conta: <strong>qual é o projeto ou ideia que você quer transformar em prompt?</strong>';

  // ── Refs DOM ──────────────────────────────────────────────────
  function el(id) { return document.getElementById(id); }

  // ── Inicialização ─────────────────────────────────────────────
  function init() {
    // Só inicializa quando a página prompts está ativa
    var page = document.getElementById('page-prompts');
    if (!page) return;

    el('peNewBtn').addEventListener('click', novaConversa);
    el('peSendBtn').addEventListener('click', enviarMensagem);
    el('peInput').addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviarMensagem(); }
    });
    el('peInput').addEventListener('input', autoResize);
    el('peSidebarToggle').addEventListener('click', function () {
      el('peSidebar').classList.toggle('open');
    });

    carregarSessoes();
  }

  // ── Sessões ───────────────────────────────────────────────────
  function carregarSessoes() {
    fetch('/api/prompts/sessoes')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderSidebar(data.sessoes || []);
      })
      .catch(function () {
        el('peSessionList').innerHTML = '<div class="pe-empty-sidebar">Erro ao carregar sessões.</div>';
      });
  }

  function renderSidebar(sessoes) {
    var list = el('peSessionList');
    if (!sessoes.length) {
      list.innerHTML = '<div class="pe-empty-sidebar">Nenhuma conversa ainda.<br>Clique em ＋ para começar.</div>';
      mostrarEstadoVazio();
      return;
    }
    list.innerHTML = sessoes.map(function (s) {
      var titulo = s.titulo || 'Nova conversa';
      var data = new Date(s.atualizado_em).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
      var ativo = s.id === currentSessionId ? ' active' : '';
      return '<div class="pe-session-item' + ativo + '" data-id="' + s.id + '">' +
        '<div class="pe-session-info">' +
        '<div class="pe-session-title">' + escapeHtml(titulo) + '</div>' +
        '<div class="pe-session-date">' + data + '</div>' +
        '</div>' +
        '<button class="pe-session-del" data-del="' + s.id + '" title="Deletar">🗑</button>' +
        '</div>';
    }).join('');

    list.querySelectorAll('.pe-session-item').forEach(function (item) {
      item.addEventListener('click', function (e) {
        if (e.target.closest('[data-del]')) return;
        abrirSessao(parseInt(this.dataset.id));
      });
    });

    list.querySelectorAll('[data-del]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        deletarSessao(parseInt(this.dataset.del));
      });
    });
  }

  function novaConversa() {
    fetch('/api/prompts/sessoes', { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { alert('Erro: ' + data.error); return; }
        currentSessionId = data.id;
        primeiraMsg = null; // reset para nova sessão
        limparChat();
        adicionarMensagem('agent', WELCOME_MSG);
        carregarSessoes();
      });
  }

  function abrirSessao(id) {
    currentSessionId = id;
    limparChat();

    // Atualiza destaque na sidebar
    document.querySelectorAll('.pe-session-item').forEach(function (el) {
      el.classList.toggle('active', parseInt(el.dataset.id) === id);
    });

    fetch('/api/prompts/sessoes/' + id + '/mensagens')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var msgs = data.mensagens || [];
        // Sessão existente: nunca exibe mensagem de boas-vindas,
        // mesmo que ainda não tenha mensagens (ex: clicou na sidebar antes de digitar)
        msgs.forEach(function (m) {
          adicionarMensagem(m.role === 'user' ? 'user' : 'agent', m.content);
        });
        if (!msgs.length) {
          mostrarEstadoVazio();
        }
        scrollBottom();
      });
  }

  function deletarSessao(id) {
    if (!confirm('Deletar esta conversa?')) return;
    fetch('/api/prompts/sessoes/' + id, { method: 'DELETE' })
      .then(function (r) { return r.json(); })
      .then(function () {
        if (currentSessionId === id) {
          currentSessionId = null;
          limparChat();
          mostrarEstadoVazio();
        }
        carregarSessoes();
      });
  }

  // ── Chat ──────────────────────────────────────────────────────
  function enviarMensagem() {
    if (isWaiting || !currentSessionId) return;
    var input = el('peInput');
    var texto = input.value.trim();
    if (!texto) return;

    input.value = '';
    input.style.height = 'auto';
    isWaiting = true;
    el('peSendBtn').disabled = true;

    // Registra primeira mensagem para fallback de título
    if (!primeiraMsg) primeiraMsg = texto;

    adicionarMensagem('user', texto);
    mostrarTyping();

    fetch('/api/prompts/sessoes/' + currentSessionId + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: texto })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        removerTyping();
        if (data.error) {
          adicionarMensagem('agent', '⚠️ Erro ao processar. Tente novamente.');
        } else {
          adicionarMensagem('agent', data.reply);
          // Gerar título se for prompt final
          tentarGerarTitulo(data.reply);
        }
      })
      .catch(function () {
        removerTyping();
        adicionarMensagem('agent', '⚠️ Erro de conexão. Tente novamente.');
      })
      .finally(function () {
        isWaiting = false;
        el('peSendBtn').disabled = false;
      });
  }

  function tentarGerarTitulo(reply) {
    // Só gera título se a sessão ainda não tem título
    var itemAtivo = document.querySelector('.pe-session-item.active .pe-session-title');
    if (itemAtivo && itemAtivo.textContent !== 'Nova conversa') return;

    var json = extrairJson(reply);
    if (!json || json.type !== 'prompt') return;

    var titulo = (json.title || '').trim();
    if (!titulo) {
      // Fallback: primeiras 40 chars da PRIMEIRA mensagem do usuário na sessão
      var src = primeiraMsg || '';
      titulo = src.substring(0, 40);
      if (src.length > 40) titulo += '...';
    }
    if (!titulo) return;

    fetch('/api/prompts/sessoes/' + currentSessionId + '/titulo', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ titulo: titulo })
    }).then(function () { carregarSessoes(); });
  }

  // ── Renderização de mensagens ─────────────────────────────────
  function adicionarMensagem(role, content) {
    var area = el('peChatArea');

    // Remove estado vazio se existir
    var empty = area.querySelector('.pe-empty-state');
    if (empty) empty.remove();

    var div = document.createElement('div');
    div.className = 'pe-msg ' + role;

    var avatar = document.createElement('div');
    avatar.className = 'pe-msg-avatar';
    avatar.textContent = role === 'agent' ? '🧠' : '👤';

    var bubble = document.createElement('div');
    bubble.className = 'pe-bubble';

    if (role === 'agent') {
      bubble.innerHTML = renderizarAgente(content);
    } else {
      bubble.textContent = content;
    }

    div.appendChild(avatar);
    div.appendChild(bubble);
    area.appendChild(div);
    scrollBottom();
  }

  function renderizarAgente(texto) {
    var json = extrairJson(texto);

    if (json && json.type === 'questions' && Array.isArray(json.questions)) {
      var antes = texto.substring(0, texto.indexOf('{')).trim();
      var html = '';
      if (antes) html += '<p>' + formatarTexto(antes) + '</p>';
      html += '<p style="margin-top:' + (antes ? '10px' : '0') + '">Para criar o melhor prompt possível, preciso entender melhor o projeto:</p>';
      html += '<div class="pe-questions">' +
        json.questions.map(function (q, i) {
          return '<div class="pe-question-item"><span>' + (i + 1) + '.</span>' + escapeHtml(q) + '</div>';
        }).join('') +
        '</div>';
      return html;
    }

    if (json && json.type === 'prompt' && json.prompt) {
      var antes2 = texto.substring(0, texto.indexOf('{')).trim();
      var html2 = '';
      if (antes2) html2 += '<p>' + formatarTexto(antes2) + '</p>';
      html2 += '<p style="margin-top:' + (antes2 ? '10px' : '0') + '">✅ <strong>Prompt gerado com sucesso!</strong></p>';
      html2 += '<div class="pe-prompt-box">' +
        '<div class="pe-prompt-box-header">' +
        '<span>📋 ' + escapeHtml(json.title || 'PROMPT FINAL') + '</span>' +
        '<button class="pe-copy-btn" onclick="(function(btn,txt){navigator.clipboard.writeText(txt).then(function(){btn.textContent=\'✓ Copiado!\';setTimeout(function(){btn.textContent=\'Copiar\';},2000);})})(this,' + JSON.stringify(json.prompt) + ')">Copiar</button>' +
        '</div>' +
        escapeHtml(json.prompt) +
        '</div>';
      return html2;
    }

    // Texto simples (incluindo fallback se JSON inválido)
    return formatarTexto(texto);
  }

  function extrairJson(texto) {
    // Procura o bloco JSON mais externo (robusto a qualquer ordenação de chaves)
    var start = texto.indexOf('{');
    if (start === -1) return null;
    // Encontra o fechamento correto contando chaves
    var depth = 0, end = -1;
    for (var i = start; i < texto.length; i++) {
      if (texto[i] === '{') depth++;
      else if (texto[i] === '}') { depth--; if (depth === 0) { end = i; break; } }
    }
    if (end === -1) return null;
    try {
      var obj = JSON.parse(texto.substring(start, end + 1));
      if (obj.type === 'questions' || obj.type === 'prompt') return obj;
      return null;
    } catch (e) { return null; }
  }

  function formatarTexto(texto) {
    return escapeHtml(texto)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Typing indicator ──────────────────────────────────────────
  function mostrarTyping() {
    var area = el('peChatArea');
    var div = document.createElement('div');
    div.className = 'pe-msg agent';
    div.id = 'peTyping';
    div.innerHTML = '<div class="pe-msg-avatar">🧠</div>' +
      '<div class="pe-bubble"><div class="pe-typing"><span></span><span></span><span></span></div></div>';
    area.appendChild(div);
    scrollBottom();
  }

  function removerTyping() {
    var el2 = document.getElementById('peTyping');
    if (el2) el2.remove();
  }

  // ── Helpers ───────────────────────────────────────────────────
  function limparChat() {
    el('peChatArea').innerHTML = '';
  }

  function mostrarEstadoVazio() {
    el('peChatArea').innerHTML =
      '<div class="pe-empty-state">' +
      '<div class="pe-empty-icon">🧠</div>' +
      '<p>Nenhuma conversa ainda.<br>Crie uma nova para começar.</p>' +
      '<button class="pe-empty-start-btn" onclick="document.getElementById(\'peNewBtn\').click()">＋ Nova conversa</button>' +
      '</div>';
  }

  function scrollBottom() {
    var area = el('peChatArea');
    setTimeout(function () { area.scrollTop = area.scrollHeight; }, 50);
  }

  function autoResize() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
  }

  // ── Boot ──────────────────────────────────────────────────────
  // Inicializa quando o DOM estiver pronto
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
