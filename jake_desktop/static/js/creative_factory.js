(function () {
  var generateBtn = document.getElementById('cf-generate-btn');
  if (!generateBtn) return;

  // ── Elementos principais ─────────────────────────────────────────────────────
  var modePromptBtn = document.getElementById('cf-mode-prompt-btn');
  var modeUploadBtn = document.getElementById('cf-mode-upload-btn');
  var promptBlock   = document.getElementById('cf-prompt-block');
  var uploadBlock   = document.getElementById('cf-upload-block');

  var promptEl      = document.getElementById('cf-prompt');
  var imageInputEl  = document.getElementById('cf-image-input');
  var dropzoneEl    = document.getElementById('cf-dropzone');
  var imgPlaceholder = document.getElementById('cf-img-placeholder');
  var imgPreviewEl  = document.getElementById('cf-image-preview');

  var imageEngineEl = document.getElementById('cf-image-engine');
  var textEngineEl  = document.getElementById('cf-text-engine');
  var focusEl       = document.getElementById('cf-focus');
  var nicheEl       = document.getElementById('cf-nicho');

  var statusEl      = document.getElementById('cf-status');

  var badgesEl      = document.getElementById('cf-badges');
  var emptyEl       = document.getElementById('cf-empty');
  var loadingEl     = document.getElementById('cf-loading');
  var gridEl        = document.getElementById('cf-grid');

  var currentMode   = 'prompt'; // 'prompt' | 'upload'

  // ── Helpers de UI ────────────────────────────────────────────────────────────
  function setMode(mode) {
    currentMode = mode;
    if (mode === 'prompt') {
      promptBlock.classList.remove('hidden');
      uploadBlock.classList.add('hidden');
      modePromptBtn.classList.add('cp-btn-primary');
      modeUploadBtn.classList.remove('cp-btn-primary');
      // Restaura placeholder padrão do prompt
      if (promptEl) promptEl.placeholder = 'Descreva a cena do criativo (em português ou inglês)...';
      var promptLabel = promptBlock.querySelector('label');
      if (promptLabel) promptLabel.textContent = 'Prompt da cena';
    } else {
      // Upload mode: mostra ambos os blocos — upload para imagem, prompt para instrução Kontext
      promptBlock.classList.remove('hidden');
      uploadBlock.classList.remove('hidden');
      modeUploadBtn.classList.add('cp-btn-primary');
      modePromptBtn.classList.remove('cp-btn-primary');
      updateKontextUI();
    }
  }

  function updateKontextUI() {
    if (currentMode !== 'upload') return;
    var hasImage = imageInputEl && imageInputEl.files && imageInputEl.files[0];
    if (promptEl) {
      promptEl.placeholder = hasImage
        ? '(Opcional) Instrução de edição: ex. "Mude o fundo para uma praia ao pôr do sol" — ativa o Flux Kontext Pro'
        : '(Opcional) Instrução de edição para a imagem enviada...';
    }
    var promptLabel = promptBlock.querySelector('label');
    if (promptLabel) promptLabel.textContent = 'Instrução Kontext (opcional)';
    // Atualiza texto do botão conforme se há instrução preenchida
    var hasInstruction = promptEl && (promptEl.value || '').trim().length > 0;
    var txt = generateBtn.querySelector('.cp-btn-text');
    if (txt) {
      txt.textContent = hasInstruction
        ? '✏️ Editar Imagem com Kontext Pro'
        : 'Gerar 5 Variações de Alto CTR';
    }
  }

  function setLoading(on) {
    if (on) {
      emptyEl.classList.add('hidden');
      gridEl.classList.add('hidden');
      loadingEl.classList.remove('hidden');
      statusEl.className = 'cs-status cs-status-loading visible';
      statusEl.textContent = 'Gerando criativos com IA...';
      generateBtn.disabled = true;
      var txt = generateBtn.querySelector('.cp-btn-text');
      if (txt) txt.textContent = 'Gerando...';
    } else {
      loadingEl.classList.add('hidden');
      generateBtn.disabled = false;
      var txt2 = generateBtn.querySelector('.cp-btn-text');
      if (txt2) txt2.textContent = 'Gerar 5 Variações de Alto CTR';
    }
  }

  function showError(msg) {
    statusEl.className = 'cs-status cs-status-error visible';
    statusEl.textContent = msg;
  }

  function clearError() {
    statusEl.className = 'cs-status hidden';
    statusEl.textContent = '';
  }

  // ── Upload / Preview de imagem ───────────────────────────────────────────────
  function setImagePreview(file) {
    if (!file) {
      imgPreviewEl.classList.add('hidden');
      imgPreviewEl.src = '';
      imgPlaceholder.classList.remove('hidden');
      return;
    }
    var reader = new FileReader();
    reader.onload = function (e) {
      imgPreviewEl.src = e.target.result;
      imgPreviewEl.classList.remove('hidden');
      imgPlaceholder.classList.add('hidden');
    };
    reader.readAsDataURL(file);
  }

  if (imageInputEl) {
    imageInputEl.addEventListener('change', function () {
      var f = imageInputEl.files && imageInputEl.files[0];
      setImagePreview(f || null);
      updateKontextUI();
    });
  }

  if (promptEl) {
    promptEl.addEventListener('input', function () {
      if (currentMode === 'upload') updateKontextUI();
    });
  }

  if (dropzoneEl) {
    dropzoneEl.addEventListener('dragover', function (e) {
      e.preventDefault();
      dropzoneEl.classList.add('drag-over');
    });
    dropzoneEl.addEventListener('dragleave', function () {
      dropzoneEl.classList.remove('drag-over');
    });
    dropzoneEl.addEventListener('drop', function (e) {
      e.preventDefault();
      dropzoneEl.classList.remove('drag-over');
      var f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) {
        imageInputEl.files = e.dataTransfer.files;
        setImagePreview(f);
      }
    });
    dropzoneEl.addEventListener('click', function () {
      if (imageInputEl) imageInputEl.click();
    });
  }

  // ── Renderização dos cards ───────────────────────────────────────────────────
  function renderBadges(data) {
    var plat = 'Meta Ads';
    var focus = data.focus || '';
    var textEngine = data.textEngine || '';
    var imgEngine  = data.imageEngine || '';

    var focusLabel = focus === 'whatsapp'
      ? 'Msg WhatsApp'
      : (focus === 'conversion' ? 'Conversão Direta' : 'Marca');

    var textLabel = textEngine === 'gpt4o' ? 'GPT‑4o' : 'Claude';
    var imgLabel  = imgEngine === 'kontext' ? 'Kontext Pro'
                  : imgEngine === 'imagen4' ? 'Imagen 4'
                  : 'Flux 1.1 Pro';

    var html = [
      '<span class="cp-badge">' + plat + '</span>',
      '<span class="cp-badge">' + focusLabel + '</span>',
      '<span class="cp-badge cp-badge-emoji">' + textLabel + '</span>',
      '<span class="cp-badge">' + imgLabel + '</span>',
    ];
    badgesEl.innerHTML = html.join('');
  }

  function renderCreatives(creatives, meta) {
    gridEl.innerHTML = '';
    if (!Array.isArray(creatives) || creatives.length === 0) {
      emptyEl.classList.remove('hidden');
      gridEl.classList.add('hidden');
      return;
    }

    renderBadges(meta || {});

    creatives.forEach(function (c, idx) {
      var card = document.createElement('article');
      card.className = 'cf-card';

      var imgWrap = document.createElement('div');
      imgWrap.className = 'cf-card-img-wrap';

      if (c.image) {
        var img = document.createElement('img');
        img.className = 'cf-card-img';
        img.src = c.image;
        img.alt = c.headline || ('Criativo ' + (idx + 1));
        imgWrap.appendChild(img);
      } else {
        var ph = document.createElement('div');
        ph.className = 'cf-card-img-ph';
        ph.textContent = 'Sem imagem (apenas texto)';
        imgWrap.appendChild(ph);
      }

      var badge = document.createElement('div');
      badge.className = 'cf-card-badge';
      badge.textContent = 'Criativo ' + (idx + 1);
      imgWrap.appendChild(badge);

      var body = document.createElement('div');
      body.className = 'cf-card-body';

      var h = document.createElement('h3');
      h.className = 'cf-card-headline';
      h.textContent = c.headline || '';

      var sub = document.createElement('p');
      sub.className = 'cf-card-subheadline';
      sub.textContent = c.subheadline || '';

      var actions = document.createElement('div');
      actions.className = 'cf-card-actions';

      var btnImg = document.createElement('button');
      btnImg.type = 'button';
      btnImg.className = 'cf-btn cf-btn-primary';
      btnImg.textContent = '⬇ Baixar Imagem';
      if (!c.image) {
        btnImg.disabled = true;
      } else {
        btnImg.addEventListener('click', function () {
          downloadImage(c.image, idx);
        });
      }

      var btnCopy = document.createElement('button');
      btnCopy.type = 'button';
      btnCopy.className = 'cf-btn cf-btn-secondary';
      btnCopy.textContent = '📋 Copiar Copy';
      btnCopy.addEventListener('click', function () {
        copyCopy(c.headline || '', c.subheadline || '', btnCopy);
      });

      actions.appendChild(btnImg);
      actions.appendChild(btnCopy);

      body.appendChild(h);
      body.appendChild(sub);
      body.appendChild(actions);

      card.appendChild(imgWrap);
      card.appendChild(body);
      gridEl.appendChild(card);
    });

    emptyEl.classList.add('hidden');
    gridEl.classList.remove('hidden');
  }

  function copyCopy(headline, subheadline, btn) {
    var text = headline + '\n\n' + subheadline;
    function markCopied() {
      btn.classList.add('copied');
      var original = btn.textContent;
      btn.textContent = 'Copiado!';
      setTimeout(function () {
        btn.classList.remove('copied');
        btn.textContent = original;
      }, 2000);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(markCopied).catch(function () {
        fallbackCopy(text);
        markCopied();
      });
    } else {
      fallbackCopy(text);
      markCopied();
    }
  }

  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }

  function downloadImage(dataUrl, idx) {
    try {
      var a = document.createElement('a');
      a.href = dataUrl;
      a.download = 'criativo-' + (idx + 1) + '.png';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (e) {
      console.error('downloadImage error', e);
    }
  }

  // ── Lógica principal ─────────────────────────────────────────────────────────
  async function handleGenerate() {
    clearError();

    var niche = (nicheEl.value || '').trim();
    if (!niche) {
      showError('Descreva o público/nicho antes de gerar.');
      nicheEl.focus();
      return;
    }

    if (currentMode === 'prompt') {
      var promptText = (promptEl.value || '').trim();
      if (!promptText) {
        showError('Descreva a cena do criativo (prompt).');
        promptEl.focus();
        return;
      }
    } else {
      var f = imageInputEl.files && imageInputEl.files[0];
      if (!f) {
        showError('Envie uma imagem base no modo Upload.');
        return;
      }
    }

    setLoading(true);

    try {
      var formData = new FormData();
      formData.append('mode', currentMode);
      formData.append('image_engine', imageEngineEl.value);
      formData.append('text_engine', textEngineEl.value);
      formData.append('campaign_focus', focusEl.value);
      formData.append('niche', niche);
      if (currentMode === 'prompt') {
        formData.append('prompt', (promptEl.value || '').trim());
      } else if (imageInputEl.files && imageInputEl.files[0]) {
        formData.append('image', imageInputEl.files[0]);
        // Instrução Kontext (opcional)
        var instruction = (promptEl.value || '').trim();
        if (instruction) formData.append('prompt', instruction);
      }

      var res = await fetch('/api/generate-creative', {
        method: 'POST',
        body: formData,
      });
      var json = await res.json();
      setLoading(false);

      if (!res.ok || json.error) {
        showError(json.error || ('Erro ao gerar criativos (HTTP ' + res.status + ')'));
        emptyEl.classList.remove('hidden');
        gridEl.classList.add('hidden');
        return;
      }

      var resMeta = json.meta || {};
      renderCreatives(json.creatives || [], {
        focus: resMeta.campaign_focus || focusEl.value,
        textEngine: resMeta.text_engine || textEngineEl.value,
        imageEngine: resMeta.image_engine || imageEngineEl.value,
      });
      statusEl.className = 'cs-status cs-status-ok visible';
      statusEl.textContent = 'Criativos gerados com sucesso.';

    } catch (err) {
      setLoading(false);
      showError('Erro de conexão: ' + err.message);
      emptyEl.classList.remove('hidden');
      gridEl.classList.add('hidden');
    }
  }

  // ── Eventos ──────────────────────────────────────────────────────────────────
  modePromptBtn.addEventListener('click', function () { setMode('prompt'); });
  modeUploadBtn.addEventListener('click', function () { setMode('upload'); });
  generateBtn.addEventListener('click', handleGenerate);

  // Modo inicial
  setMode('prompt');
  clearError();
})();

