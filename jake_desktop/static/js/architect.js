;(function () {
  'use strict';

  var htmlState = '';
  var STORAGE_KEY = 'jake_site_architect_v1';
  var assetsState = {
    logo: null,
    hero: null,
    gallery: [],
    benefits: [],
    social: []
  };

  function qs(id) { return document.getElementById(id); }

  function showSaStatus(msg, type) {
    var el = qs('sa-status');
    if (!el) return;
    el.textContent = msg;
    el.className = 'sa-status sa-status-' + (type || 'ok') + ' visible';
  }
  function hideSaStatus() {
    var el = qs('sa-status');
    if (el) el.className = 'sa-status';
  }

  function dataUrlFromFile(file, cb) {
    if (!file) return cb(null);
    var r = new FileReader();
    r.onload = function (e) { cb(e.target.result || null); };
    r.onerror = function () { cb(null); };
    r.readAsDataURL(file);
  }

  function bindUploads() {
    document.querySelectorAll('.sa-dropzone').forEach(function (dz) {
      var kind = dz.dataset.kind;
      var input = dz.querySelector('.sa-file-input');
      if (!input) return;

      dz.addEventListener('dragover', function (e) {
        e.preventDefault();
        dz.classList.add('sa-dragover');
      });
      dz.addEventListener('dragleave', function () {
        dz.classList.remove('sa-dragover');
      });
      dz.addEventListener('drop', function (e) {
        e.preventDefault();
        dz.classList.remove('sa-dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length) {
          handleFiles(kind, dz, e.dataTransfer.files);
        }
      });
      input.addEventListener('change', function (e) {
        if (e.target.files && e.target.files.length) {
          handleFiles(kind, dz, e.target.files);
        }
      });
    });
  }

  function handleFiles(kind, dz, fileList) {
    if (kind === 'gallery' || kind === 'benefits' || kind === 'social') {
      var grid = dz.querySelector('.sa-preview-grid');
      if (!grid) return;
      grid.innerHTML = '';
      var maxFiles = 6;
      var arrName = kind === 'gallery' ? 'gallery' : (kind === 'benefits' ? 'benefits' : 'social');
      assetsState[arrName] = [];
      Array.prototype.slice.call(fileList, 0, maxFiles).forEach(function (file) {
        dataUrlFromFile(file, function (url) {
          if (!url) return;
          assetsState[arrName].push(url);
          var img = document.createElement('img');
          img.src = url;
          grid.appendChild(img);
        });
      });
    } else {
      var file = fileList[0];
      var img = dz.querySelector('.sa-preview');
      var ph  = dz.querySelector('.sa-drop-placeholder');
      dataUrlFromFile(file, function (url) {
        if (!url) return;
        if (img) {
          img.src = url;
          img.classList.remove('hidden');
        }
        if (ph) ph.classList.add('hidden');
        if (kind === 'logo') assetsState.logo = url;
        if (kind === 'hero') assetsState.hero = url;
      });
    }
  }

  function loadHtmlInIframe(html) {
    var iframe = qs('sa-iframe');
    if (!iframe) return;
    var doc = iframe.contentDocument || iframe.contentWindow.document;
    doc.open();
    doc.write(html);
    doc.close();
  }

  function setViewMode(mode) {
    var iframe = qs('sa-iframe');
    var htmlView = qs('sa-html-view');
    var previewBtn = qs('sa-view-code-btn');
    var htmlBtn = qs('sa-view-html-btn');
    if (!iframe || !htmlView || !previewBtn || !htmlBtn) return;
    if (mode === 'html') {
      iframe.classList.add('hidden');
      htmlView.classList.remove('hidden');
      htmlView.textContent = htmlState || '<!-- GERE A LANDING PAGE PRIMEIRO -->';
      previewBtn.classList.remove('sa-active');
      htmlBtn.classList.add('sa-active');
    } else {
      iframe.classList.remove('hidden');
      htmlView.classList.add('hidden');
      previewBtn.classList.add('sa-active');
      htmlBtn.classList.remove('sa-active');
    }
  }

  function appendChat(role, text) {
    var log = qs('sa-chat-log');
    if (!log || !text) return;
    var div = document.createElement('div');
    div.className = 'sa-chat-msg ' + (role === 'user' ? 'sa-chat-msg-user' : 'sa-chat-msg-ai');
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  function generateSite() {
    var urlRef   = (qs('sa-ref-url') && qs('sa-ref-url').value.trim()) || '';
    var contexto = (qs('sa-contexto') && qs('sa-contexto').value.trim()) || '';
    var heroCopy = (qs('sa-copy-hero') && qs('sa-copy-hero').value.trim()) || '';
    var extra    = (qs('sa-copy-extra') && qs('sa-copy-extra').value.trim()) || '';
    var template = (qs('sa-template') && qs('sa-template').value) || '';

    if (!urlRef && !contexto && !heroCopy) {
      showSaStatus('Preencha pelo menos a URL de referência ou o contexto/hero.', 'error');
      return;
    }

    var btn = qs('sa-generate-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="sa-btn-icon">⟳</span><span>Gerando…</span>';
    }
    showSaStatus('Gerando estrutura de landing page com IA…', 'loading');

    fetch('/api/site-architect/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reference_url: urlRef,
        business_context: contexto,
        hero_copy: heroCopy,
        extra_copy: extra,
        template_kind: template,
        assets: assetsState
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.html) {
          showSaStatus(data && data.error ? data.error : 'Não foi possível gerar o HTML.', 'error');
          return;
        }
        htmlState = data.html;
        loadHtmlInIframe(htmlState);
        setViewMode('preview');
        try {
          window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
            html: htmlState,
            refUrl: urlRef,
            contexto: contexto,
            heroCopy: heroCopy,
            extra: extra,
            template: template
          }));
        } catch (e) {
          // storage opcional
        }
        showSaStatus('Landing page gerada. Você pode refinar pelo chat abaixo.', 'ok');
      })
      .catch(function () {
        showSaStatus('Erro de conexão ao gerar a landing page.', 'error');
      })
      .finally(function () {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<span class="sa-btn-icon">✦</span><span>Gerar estrutura de site</span>';
        }
        setTimeout(hideSaStatus, 5000);
      });
  }

  function refineSite(promptText) {
    if (!htmlState) {
      showSaStatus('Gere a primeira versão do site antes de refinar.', 'error');
      return;
    }
    var body = {
      instruction: promptText,
      html: htmlState
    };
    showSaStatus('Aplicando ajuste no código com IA…', 'loading');
    fetch('/api/site-architect/refine', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.html) {
          showSaStatus(data && data.error ? data.error : 'Não foi possível aplicar o ajuste.', 'error');
          return;
        }
        htmlState = data.html;
        loadHtmlInIframe(htmlState);
        setViewMode('preview');
        appendChat('ai', data.summary || 'Ajuste aplicado.');
        try {
          var stored = window.localStorage.getItem(STORAGE_KEY);
          var prev = stored ? JSON.parse(stored) : {};
          prev = prev && typeof prev === 'object' ? prev : {};
          prev.html = htmlState;
          window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prev));
        } catch (e) {
          // storage opcional
        }
        showSaStatus('Ajuste aplicado com sucesso.', 'ok');
      })
      .catch(function () {
        showSaStatus('Erro de conexão ao refinar o site.', 'error');
      })
      .finally(function () {
        setTimeout(hideSaStatus, 5000);
      });
  }

  function exportHtml() {
    if (!htmlState) {
      showSaStatus('Gere a landing page antes de exportar.', 'error');
      return;
    }
    showSaStatus('Preparando download do index.html…', 'loading');
    fetch('/api/site-architect/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html: htmlState })
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.html) {
          showSaStatus(data && data.error ? data.error : 'Resposta inválida da exportação.', 'error');
          return;
        }
        var blob = new Blob([data.html], { type: 'text/html;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = data.filename || 'index.html';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showSaStatus('index.html baixado com sucesso.', 'ok');
      })
      .catch(function () {
        showSaStatus('Erro ao exportar o index.html.', 'error');
      })
      .finally(function () {
        setTimeout(hideSaStatus, 4000);
      });
  }

  function exportReact() {
    if (!htmlState) {
      showSaStatus('Gere a landing page antes de exportar como React.', 'error');
      return;
    }
    showSaStatus('Preparando componente React…', 'loading');
    fetch('/api/site-architect/export-react', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html: htmlState, component_name: 'LandingGenerated' })
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.code) {
          showSaStatus(data && data.error ? data.error : 'Resposta inválida da exportação React.', 'error');
          return;
        }
        var blob = new Blob([data.code], { type: 'text/plain;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = data.filename || 'LandingGenerated.tsx';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showSaStatus('Componente React baixado com sucesso.', 'ok');
      })
      .catch(function () {
        showSaStatus('Erro ao exportar o componente React.', 'error');
      })
      .finally(function () {
        setTimeout(hideSaStatus, 4000);
      });
  }

  function deployToVercel() {
    if (!htmlState) {
      showSaStatus('Gere a landing page antes de publicar na Vercel.', 'error');
      return;
    }
    showSaStatus('Enviando index.html para a Vercel…', 'loading');
    var contexto = (qs('sa-contexto') && qs('sa-contexto').value.trim()) || '';
    var projectName = 'jake-architect-site';
    if (contexto) {
      var slug = contexto.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
      if (slug) projectName = 'jake-' + slug.slice(0, 24);
    }
    fetch('/api/site-architect/deploy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html: htmlState, project_name: projectName })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || data.error) {
          showSaStatus(data && data.error ? data.error : 'Falha ao criar deploy na Vercel.', 'error');
          if (data && data.hint) appendChat('ai', data.hint);
          return;
        }
        var msg = 'Deploy criado na Vercel: ' + (data.url || data.inspectorUrl || '');
        appendChat('ai', msg);
        showSaStatus('Deploy criado com sucesso na Vercel.', 'ok');
      })
      .catch(function () {
        showSaStatus('Erro de conexão ao falar com a Vercel.', 'error');
      })
      .finally(function () {
        setTimeout(hideSaStatus, 5000);
      });
  }

  function bindCore() {
    var genBtn = qs('sa-generate-btn');
    if (genBtn) genBtn.addEventListener('click', function (e) {
      e.preventDefault();
      generateSite();
    });

    var resetBtn = qs('sa-reset-btn');
    if (resetBtn) resetBtn.addEventListener('click', function (e) {
      e.preventDefault();
      ['sa-ref-url','sa-contexto','sa-copy-hero','sa-copy-extra'].forEach(function (id) {
        var el = qs(id); if (el) el.value = '';
      });
      var tmpl = qs('sa-template');
      if (tmpl) tmpl.selectedIndex = 0;
      assetsState = { logo: null, hero: null, gallery: [], benefits: [], social: [] };
      htmlState = '';
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch (e) {
        // ignore
      }
      var iframe = qs('sa-iframe');
      if (iframe) loadHtmlInIframe('<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;font-family:sans-serif;background:#02030a;color:#e0f7fa;display:flex;align-items:center;justify-content:center;height:100vh}p{opacity:.7;font-size:14px;}</style></head><body><p>Gere a landing page no painel esquerdo.</p></body></html>');
      var htmlView = qs('sa-html-view');
      if (htmlView) htmlView.textContent = '';
      var log = qs('sa-chat-log');
      if (log) log.innerHTML = '';
      document.querySelectorAll('.sa-preview').forEach(function (img) {
        img.src = ''; img.classList.add('hidden');
      });
      document.querySelectorAll('.sa-drop-placeholder').forEach(function (ph) {
        ph.classList.remove('hidden');
      });
      document.querySelectorAll('.sa-preview-grid').forEach(function (g) { g.innerHTML = ''; });
      hideSaStatus();
    });

    var previewBtn = qs('sa-view-code-btn');
    var htmlBtn = qs('sa-view-html-btn');
    var exportBtn = qs('sa-export-btn');
    var exportReactBtn = qs('sa-export-react-btn');
    if (previewBtn) {
      previewBtn.classList.add('sa-active');
      previewBtn.addEventListener('click', function () { setViewMode('preview'); });
    }
    if (htmlBtn) {
      htmlBtn.addEventListener('click', function () { setViewMode('html'); });
    }
    if (exportBtn) {
      exportBtn.addEventListener('click', function () {
        exportHtml();
      });
    }
    if (exportReactBtn) {
      exportReactBtn.addEventListener('click', function () {
        exportReact();
      });
    }

    var chatForm = qs('sa-chat-form');
    var chatInput = qs('sa-chat-input');
    if (chatForm && chatInput) {
      chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var text = chatInput.value.trim();
        if (!text) return;
        appendChat('user', text);
        chatInput.value = '';
        refineSite(text);
      });
    }

    var publishBtn = qs('sa-publish-btn');
    if (publishBtn) {
      publishBtn.addEventListener('click', function () {
        deployToVercel();
      });
    }

    // Bootstrap iframe com placeholder
    if (qs('sa-iframe')) {
      loadHtmlInIframe('<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;font-family:sans-serif;background:#02030a;color:#e0f7fa;display:flex;align-items:center;justify-content:center;height:100vh}p{opacity:.7;font-size:14px;text-align:center;max-width:260px}</style></head><body><p>Preencha as informações à esquerda e clique em "Gerar estrutura de site".</p></body></html>');
    }
  }

  function init() {
    if (!qs('page-architect')) return;
    bindUploads();
    bindCore();
    // restaura último estado salvo, se existir
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        var saved = JSON.parse(raw);
        if (saved && saved.html) {
          htmlState = saved.html;
          loadHtmlInIframe(htmlState);
          if (qs('sa-ref-url') && saved.refUrl) qs('sa-ref-url').value = saved.refUrl;
          if (qs('sa-contexto') && saved.contexto) qs('sa-contexto').value = saved.contexto;
          if (qs('sa-copy-hero') && saved.heroCopy) qs('sa-copy-hero').value = saved.heroCopy;
          if (qs('sa-copy-extra') && saved.extra) qs('sa-copy-extra').value = saved.extra;
          if (qs('sa-template') && saved.template) qs('sa-template').value = saved.template;
          setViewMode('preview');
          showSaStatus('Última landing recarregada. Você pode continuar refinando.', 'ok');
          setTimeout(hideSaStatus, 5000);
        }
      }
    } catch (e) {
      // storage é opcional
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

