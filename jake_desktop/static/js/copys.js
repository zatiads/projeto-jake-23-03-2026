(function () {
  // ── Elementos ────────────────────────────────────────────────────────────────
  var gerarBtn     = document.getElementById('cp-gerar-btn');
  var variacaoBtn  = document.getElementById('cp-variacao-btn');
  var outputEl     = document.getElementById('cp-output');
  var sectionsEl   = document.getElementById('cp-sections');
  var loadingEl    = document.getElementById('cp-loading');
  var loadingText  = loadingEl ? loadingEl.querySelector('.cp-loading-text') : null;
  var emptyEl      = document.getElementById('cp-empty');
  var footerEl     = document.getElementById('cp-footer');
  var copyBtn      = document.getElementById('cp-copy-btn');
  var copyLabel    = document.getElementById('cp-copy-label');
  var copyIconSvg  = document.getElementById('cp-copy-icon-svg');
  var checkIconSvg = document.getElementById('cp-check-icon-svg');
  var badgesEl     = document.getElementById('cp-badges');

  if (!gerarBtn) return;

  // ── Texto completo (para "copiar tudo") ───────────────────────────────────────
  var _fullText = '';

  // ── Parser de seções [LABEL] ──────────────────────────────────────────────────
  function parseSections(text) {
    var re = /\[([^\]]+)\]/g;
    var matches = [];
    var m;
    while ((m = re.exec(text)) !== null) {
      matches.push({ label: m[1].trim(), index: m.index, end: m.index + m[0].length });
    }
    if (matches.length < 2) return null;

    var sections = [];
    for (var i = 0; i < matches.length; i++) {
      var start   = matches[i].end;
      var end     = (i + 1 < matches.length) ? matches[i + 1].index : text.length;
      var content = text.slice(start, end).trim();
      if (content) {
        sections.push({ label: matches[i].label, content: content });
      }
    }
    return sections.length >= 2 ? sections : null;
  }

  // ── Ícone de copiar (SVG inline) ─────────────────────────────────────────────
  var SVG_COPY  = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
  var SVG_CHECK = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';

  // ── Copiar texto genérico ─────────────────────────────────────────────────────
  function copyText(text, btnEl, labelEl) {
    function onSuccess() {
      btnEl.classList.add('copied');
      if (labelEl) labelEl.textContent = 'Copiado!';
      btnEl.innerHTML = SVG_CHECK + (labelEl ? ' <span>' + labelEl.textContent + '</span>' : '');
      setTimeout(function () {
        btnEl.classList.remove('copied');
        if (labelEl) {
          btnEl.innerHTML = SVG_COPY + ' <span>Copiar</span>';
        }
      }, 2000);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(onSuccess).catch(function () {
        fallbackCopy(text); onSuccess();
      });
    } else {
      fallbackCopy(text); onSuccess();
    }
  }

  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity  = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }

  // ── Renderizar seções (cards individuais) ─────────────────────────────────────
  function renderSections(sections) {
    sectionsEl.innerHTML = '';
    sections.forEach(function (sec) {
      var card = document.createElement('div');
      card.className = 'cp-section';

      var head = document.createElement('div');
      head.className = 'cp-section-head';

      var lbl = document.createElement('span');
      lbl.className   = 'cp-section-label';
      lbl.textContent = sec.label;

      var btn = document.createElement('button');
      btn.className = 'cp-section-copy';
      btn.innerHTML = SVG_COPY + ' <span>Copiar</span>';
      btn.addEventListener('click', function () {
        copyText(sec.content, btn, null);
        // Atualiza manualmente pois o innerHTML é reconstruído
        btn.classList.add('copied');
        btn.innerHTML = SVG_CHECK + ' <span>Copiado!</span>';
        setTimeout(function () {
          btn.classList.remove('copied');
          btn.innerHTML = SVG_COPY + ' <span>Copiar</span>';
        }, 2000);
      });

      head.appendChild(lbl);
      head.appendChild(btn);

      var body = document.createElement('div');
      body.className   = 'cp-section-body';
      body.textContent = sec.content;

      card.appendChild(head);
      card.appendChild(body);
      sectionsEl.appendChild(card);
    });
  }

  // ── Coletar dados do formulário ───────────────────────────────────────────────
  function getFormData() {
    return {
      plataforma:  document.getElementById('cp-plataforma').value,
      framework:   document.getElementById('cp-framework').value,
      tom:         document.getElementById('cp-tom').value,
      consciencia: document.getElementById('cp-consciencia').value,
      gatilho:     document.getElementById('cp-gatilho').value,
      tamanho:     document.getElementById('cp-tamanho').value,
      profissao:   (document.getElementById('cp-profissao').value || '').trim(),
      nicho:       (document.getElementById('cp-nicho').value     || '').trim(),
      oferta:      (document.getElementById('cp-oferta').value    || '').trim(),
      cta:         (document.getElementById('cp-cta').value       || '').trim(),
      usar_emojis: document.getElementById('cp-emojis').checked,
    };
  }

  // ── Estado de carregamento ────────────────────────────────────────────────────
  function setLoading(on, isVariacao) {
    if (on) {
      emptyEl.classList.add('hidden');
      outputEl.classList.add('hidden');
      sectionsEl.classList.add('hidden');
      footerEl.classList.add('hidden');
      loadingEl.classList.remove('hidden');
      if (loadingText) {
        loadingText.textContent = isVariacao
          ? 'Gerando variação A/B com novo ângulo...'
          : 'Gerando copy de alta conversão...';
      }
      gerarBtn.disabled    = true;
      variacaoBtn.disabled = true;
      gerarBtn.querySelector('.cp-btn-text').textContent = 'Gerando...';
    } else {
      loadingEl.classList.add('hidden');
      gerarBtn.disabled    = false;
      variacaoBtn.disabled = false;
      gerarBtn.querySelector('.cp-btn-text').textContent = 'Gerar Copy';
    }
  }

  // ── Exibir erro ───────────────────────────────────────────────────────────────
  function showError(msg) {
    sectionsEl.classList.add('hidden');
    outputEl.textContent = '⚠ ' + msg;
    outputEl.classList.remove('hidden');
    footerEl.classList.add('hidden');
    badgesEl.innerHTML = '';
    _fullText = '';
  }

  // ── Exibir resultado ──────────────────────────────────────────────────────────
  function showResult(text, data, isVariacao) {
    _fullText = text;

    var sections = parseSections(text);

    if (sections) {
      // Modo seções: cards individuais
      outputEl.classList.add('hidden');
      renderSections(sections);
      sectionsEl.classList.remove('hidden');
      copyLabel.textContent = 'Copiar Tudo';
    } else {
      // Modo plain: pre
      sectionsEl.classList.add('hidden');
      outputEl.textContent = text;
      outputEl.classList.remove('hidden');
      copyLabel.textContent = 'Copiar para a Área de Transferência';
    }

    footerEl.classList.remove('hidden');

    // Badges
    var platShort = data.plataforma.split('(')[0].trim();
    var fwShort   = data.framework.split('(')[0].split('—')[0].trim();
    var funil     = data.consciencia.split('(')[0].replace('Público', '').trim();
    var gatilho   = data.gatilho.replace(/[⏰🔒⭐🏆🎯]\s*/g, '');
    var tamanho   = data.tamanho.split('(')[0].trim();
    var emojiTag  = data.usar_emojis ? '😊 Emojis' : '✗ Sem emojis';

    var html = [
      '<span class="cp-badge">'              + platShort + '</span>',
      '<span class="cp-badge">'              + fwShort   + '</span>',
      '<span class="cp-badge cp-badge-funil">' + funil   + '</span>',
      '<span class="cp-badge">'              + gatilho   + '</span>',
      '<span class="cp-badge">'              + tamanho   + '</span>',
      '<span class="cp-badge cp-badge-emoji">' + emojiTag + '</span>',
    ];
    if (isVariacao) html.push('<span class="cp-badge cp-badge-ab">🔄 VARIAÇÃO A/B</span>');
    badgesEl.innerHTML = html.join('');
  }

  // ── Validar e disparar requisição ─────────────────────────────────────────────
  async function gerarCopy(isVariacao) {
    var data     = getFormData();
    var ofertaEl = document.getElementById('cp-oferta');

    if (!data.oferta) {
      ofertaEl.focus();
      ofertaEl.style.borderColor = 'rgba(255,82,82,.7)';
      ofertaEl.style.boxShadow   = '0 0 0 2px rgba(255,82,82,.15)';
      setTimeout(function () {
        ofertaEl.style.borderColor = '';
        ofertaEl.style.boxShadow   = '';
      }, 2000);
      return;
    }

    setLoading(true, isVariacao);

    try {
      var res  = await fetch('/api/copys/gerar', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plataforma:        data.plataforma,
          framework:         data.framework,
          tom:               data.tom,
          nivel_consciencia: data.consciencia,
          gatilho:           data.gatilho,
          tamanho:           data.tamanho,
          profissao:         data.profissao,
          nicho:             data.nicho,
          oferta:            data.oferta,
          cta:               data.cta,
          usar_emojis:       data.usar_emojis,
          variacao:          isVariacao,
        }),
      });
      var json = await res.json();
      setLoading(false, isVariacao);

      if (json.error) { showError(json.error); return; }
      showResult(json.copy, data, isVariacao);

    } catch (err) {
      setLoading(false, isVariacao);
      showError('Erro de conexão: ' + err.message);
    }
  }

  // ── Listeners dos botões de geração ──────────────────────────────────────────
  gerarBtn.addEventListener('click',    function () { gerarCopy(false); });
  variacaoBtn.addEventListener('click', function () { gerarCopy(true);  });

  // ── Copiar tudo (rodapé) ──────────────────────────────────────────────────────
  copyBtn.addEventListener('click', function () {
    if (!_fullText || _fullText.startsWith('⚠')) return;

    function onSuccess() {
      copyLabel.textContent = 'Copiado!';
      copyIconSvg.classList.add('hidden');
      checkIconSvg.classList.remove('hidden');
      copyBtn.classList.add('copied');
      setTimeout(function () {
        var hasSections = !sectionsEl.classList.contains('hidden');
        copyLabel.textContent = hasSections
          ? 'Copiar Tudo'
          : 'Copiar para a Área de Transferência';
        copyIconSvg.classList.remove('hidden');
        checkIconSvg.classList.add('hidden');
        copyBtn.classList.remove('copied');
      }, 2200);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(_fullText).then(onSuccess).catch(function () {
        fallbackCopy(_fullText); onSuccess();
      });
    } else {
      fallbackCopy(_fullText); onSuccess();
    }
  });

})();
