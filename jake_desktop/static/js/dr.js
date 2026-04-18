// jake_desktop/static/js/dr.js
(function () {
  'use strict';

  var DR = {
    ofertas: [],
    ofertaAtiva: null,
    stepAtivo: 1,
  };

  var SESSION_KEY = 'dr_contexto';

  function esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function showAlert(containerId, msg, tipo) {
    var el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = '<div class="dr-alert dr-alert-' + tipo + '">' + esc(msg) + '</div>';
    setTimeout(function () { if (el) el.innerHTML = ''; }, 5000);
  }

  function copyText(text) {
    navigator.clipboard.writeText(text).catch(function () {
      var ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    });
  }

  function irParaStep(n) {
    DR.stepAtivo = n;
    document.querySelectorAll('.dr-step-btn').forEach(function (b) {
      b.classList.toggle('active', parseInt(b.dataset.step) === n);
    });
    document.querySelectorAll('.dr-step-content').forEach(function (c) {
      c.classList.toggle('active', parseInt(c.dataset.stepContent) === n);
    });
  }

  function carregarOfertas() {
    fetch('/api/dr/ofertas')
      .then(function (r) { return r.json(); })
      .then(function (lista) {
        DR.ofertas = lista;
        renderOfertas();
      })
      .catch(function (e) { console.error('DR: erro ao carregar ofertas', e); });
  }

  function renderOfertas() {
    var container = document.getElementById('dr-ofertas-cards');
    if (!container) return;
    if (!DR.ofertas.length) {
      container.innerHTML = '<span class="dr-empty">Nenhuma oferta ainda. Clique em "+ Nova Oferta" para começar.</span>';
      return;
    }
    container.innerHTML = DR.ofertas.map(function (o) {
      var dataStr = o.created_at ? o.created_at.substring(0, 10) : '';
      var isAtiva = DR.ofertaAtiva && DR.ofertaAtiva.id === o.id;
      return '<div class="dr-oferta-card' + (isAtiva ? ' active' : '') + '" data-id="' + o.id + '">' +
        '<button class="dr-oferta-del" data-del="' + o.id + '" title="Excluir">✕</button>' +
        '<div class="dr-oferta-nome">' + esc(o.nome) + '</div>' +
        '<div class="dr-oferta-nicho">' + esc(o.nicho || '—') + '</div>' +
        '<div class="dr-oferta-data">' + dataStr + '</div>' +
        '</div>';
    }).join('');

    container.querySelectorAll('.dr-oferta-card').forEach(function (card) {
      card.addEventListener('click', function (e) {
        if (e.target.dataset.del) return;
        carregarOfertaAtiva(parseInt(card.dataset.id));
      });
    });
    container.querySelectorAll('[data-del]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        deletarOferta(parseInt(btn.dataset.del));
      });
    });
  }

  function carregarOfertaAtiva(id) {
    fetch('/api/dr/ofertas/' + id)
      .then(function (r) { return r.json(); })
      .then(function (oferta) {
        DR.ofertaAtiva = oferta;
        sessionStorage.setItem(SESSION_KEY, JSON.stringify(oferta));
        renderOfertas();
        document.getElementById('dr-pipeline').style.display = 'block';
        preencherFormOferta(oferta);
        irParaStep(1);
      })
      .catch(function (e) { console.error('DR: erro ao carregar oferta', e); });
  }

  function deletarOferta(id) {
    if (!confirm('Excluir oferta?')) return;
    fetch('/api/dr/ofertas/' + id, { method: 'DELETE' })
      .then(function () {
        if (DR.ofertaAtiva && DR.ofertaAtiva.id === id) {
          DR.ofertaAtiva = null;
          sessionStorage.removeItem(SESSION_KEY);
          document.getElementById('dr-pipeline').style.display = 'none';
        }
        carregarOfertas();
      });
  }

  function novaOferta() {
    DR.ofertaAtiva = null;
    sessionStorage.removeItem(SESSION_KEY);
    limparFormOferta();
    document.getElementById('dr-pipeline').style.display = 'block';
    renderOfertas();
    irParaStep(1);
  }

  function preencherFormOferta(o) {
    var campos = ['nome','nicho','angulo','hook','promessa','publico','contexto_raw'];
    campos.forEach(function (c) {
      var el = document.getElementById('dr-f-' + c);
      if (el) el.value = o[c] || '';
    });
    var sel = document.getElementById('dr-f-tipo_funil');
    if (sel) sel.value = o.tipo_funil || 'vsl_direto';
  }

  function limparFormOferta() {
    document.querySelectorAll('#dr-step-1 .dr-input, #dr-step-1 .dr-textarea, #dr-step-1 .dr-select')
      .forEach(function (el) { el.value = ''; });
  }

  // ── PASSO 1: Copy + VSL ───────────────────────────────────────────────────
  var _p1CopyRaw = '';
  var _p1ScriptRaw = '';
  var _p1AngulosRaw = '';

  function formatarCopy(copy) {
    if (!copy) return '';
    return [
      '📌 HEADLINE\n' + (copy.headline || ''),
      '📝 SUBHEADLINE\n' + (copy.subheadline || ''),
      '✅ BULLETS\n' + (copy.bullets || []).map(function (b) { return '• ' + b; }).join('\n'),
      '🎯 CTA\n' + (copy.cta || ''),
      '📱 ANÚNCIO CURTO\n' + (copy.anuncio_curto || ''),
      '📄 ANÚNCIO MÉDIO\n' + (copy.anuncio_medio || ''),
      '📃 ANÚNCIO LONGO\n' + (copy.anuncio_longo || ''),
    ].join('\n\n');
  }

  function formatarScript(script) {
    if (!script) return '';
    var blocos = ['hook','problema','agitacao','solucao','prova','oferta','garantia','cta'];
    var labels = { hook:'🎣 HOOK', problema:'😩 PROBLEMA', agitacao:'🔥 AGITAÇÃO',
                   solucao:'💡 SOLUÇÃO', prova:'✅ PROVA', oferta:'🎁 OFERTA',
                   garantia:'🛡 GARANTIA', cta:'🚀 CTA' };
    return blocos.map(function (b) {
      return (labels[b] || b.toUpperCase()) + '\n' + (script[b] || '');
    }).join('\n\n');
  }

  function formatarAngulos(angulos) {
    if (!angulos || !angulos.length) return '';
    return angulos.map(function (a, i) {
      return '【Ângulo ' + (i+1) + '】 ' + (a.titulo || '') +
             '\n' + (a.descricao || '') +
             '\nHook: ' + (a.hook || '');
    }).join('\n\n');
  }

  function coletarDadosOferta() {
    var modoRapido = document.getElementById('dr-form-rapido').style.display !== 'none';
    if (modoRapido) {
      return {
        nome: document.getElementById('dr-f-nome').value.trim(),
        produto: document.getElementById('dr-f-produto').value.trim(),
        publico: document.getElementById('dr-f-publico').value.trim(),
        contexto_raw: document.getElementById('dr-f-contexto_raw').value.trim(),
      };
    } else {
      return {
        nome: document.getElementById('dr-f-nome-e').value.trim(),
        nicho: document.getElementById('dr-f-nicho').value.trim(),
        angulo: document.getElementById('dr-f-angulo').value.trim(),
        hook: document.getElementById('dr-f-hook').value.trim(),
        promessa: document.getElementById('dr-f-promessa').value.trim(),
        publico: document.getElementById('dr-f-publico-e').value.trim(),
        tipo_funil: document.getElementById('dr-f-tipo_funil').value,
        contexto_raw: document.getElementById('dr-f-extras').value.trim(),
      };
    }
  }

  function initPasso1() {
    var btnRapido = document.getElementById('dr-modo-rapido');
    var btnEst    = document.getElementById('dr-modo-estruturado');
    var formR     = document.getElementById('dr-form-rapido');
    var formE     = document.getElementById('dr-form-estruturado');

    if (btnRapido) {
      btnRapido.addEventListener('click', function () {
        btnRapido.classList.add('active'); btnEst.classList.remove('active');
        formR.style.display = ''; formE.style.display = 'none';
      });
    }
    if (btnEst) {
      btnEst.addEventListener('click', function () {
        btnEst.classList.add('active'); btnRapido.classList.remove('active');
        formE.style.display = ''; formR.style.display = 'none';
      });
    }

    document.querySelectorAll('#dr-step-1 .dr-output-tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        document.querySelectorAll('#dr-step-1 .dr-output-tab').forEach(function (t) { t.classList.remove('active'); });
        document.querySelectorAll('#dr-step-1 .dr-output-pane').forEach(function (p) { p.classList.remove('active'); });
        tab.classList.add('active');
        var pane = document.getElementById('dr-tab-' + tab.dataset.tab);
        if (pane) pane.classList.add('active');
      });
    });

    var btnCopiarCopy = document.getElementById('dr-btn-copiar-copy');
    if (btnCopiarCopy) btnCopiarCopy.addEventListener('click', function () { copyText(_p1CopyRaw); });
    var btnCopiarScript = document.getElementById('dr-btn-copiar-script');
    if (btnCopiarScript) btnCopiarScript.addEventListener('click', function () { copyText(_p1ScriptRaw); });
    var btnCopiarAngulos = document.getElementById('dr-btn-copiar-angulos');
    if (btnCopiarAngulos) btnCopiarAngulos.addEventListener('click', function () { copyText(_p1AngulosRaw); });

    var btnIrLP = document.getElementById('dr-btn-ir-lp');
    if (btnIrLP) btnIrLP.addEventListener('click', function () { irParaStep(2); });

    var btnGerar = document.getElementById('dr-btn-gerar-copy');
    if (!btnGerar) return;
    btnGerar.addEventListener('click', function () {
      var dados = coletarDadosOferta();
      if (!dados.nome) { showAlert('dr-p1-alert', 'Informe o nome da oferta.', 'warn'); return; }

      btnGerar.disabled = true;
      document.getElementById('dr-p1-loading').style.display = 'flex';
      document.getElementById('dr-p1-output').style.display = 'none';

      var payload = Object.assign({}, dados);
      if (DR.ofertaAtiva) payload.oferta_id = DR.ofertaAtiva.id;

      var salvarPromise;
      if (DR.ofertaAtiva) {
        salvarPromise = Promise.resolve({ id: DR.ofertaAtiva.id });
      } else {
        salvarPromise = fetch('/api/dr/ofertas', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(dados)
        }).then(function (r) { return r.json(); });
      }

      salvarPromise.then(function (res) {
        if (res.error) { showAlert('dr-p1-alert', res.error, 'error'); return Promise.reject(); }
        payload.oferta_id = res.id;
        if (!DR.ofertaAtiva) {
          DR.ofertaAtiva = Object.assign({ id: res.id }, dados);
          carregarOfertas();
        }
        return fetch('/api/dr/gerar-copy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        }).then(function (r) { return r.json(); });
      }).then(function (result) {
        if (!result || result.error) {
          showAlert('dr-p1-alert', (result && result.error) || 'Erro ao gerar copy.', 'error');
          return;
        }
        _p1CopyRaw    = formatarCopy(result.copy);
        _p1ScriptRaw  = formatarScript(result.script_vsl);
        _p1AngulosRaw = formatarAngulos(result.angulos);

        document.getElementById('dr-copy-box').textContent    = _p1CopyRaw;
        document.getElementById('dr-script-box').textContent  = _p1ScriptRaw;
        document.getElementById('dr-angulos-box').textContent = _p1AngulosRaw;

        DR.ofertaAtiva = Object.assign(DR.ofertaAtiva || {}, dados, { copy_json: result.copy, script_vsl: JSON.stringify(result.script_vsl), angulos_json: result.angulos });
        sessionStorage.setItem(SESSION_KEY, JSON.stringify(DR.ofertaAtiva));

        document.getElementById('dr-p1-output').style.display = 'block';
      }).catch(function () {}).finally(function () {
        btnGerar.disabled = false;
        document.getElementById('dr-p1-loading').style.display = 'none';
      });
    });
  }

  window.initDR = function () {
    carregarOfertas();

    try {
      var cached = sessionStorage.getItem(SESSION_KEY);
      if (cached) {
        DR.ofertaAtiva = JSON.parse(cached);
        document.getElementById('dr-pipeline').style.display = 'block';
        preencherFormOferta(DR.ofertaAtiva);
      }
    } catch (e) { /* ignore */ }

    var btnNova = document.getElementById('dr-btn-nova-oferta');
    if (btnNova) btnNova.addEventListener('click', novaOferta);

    document.querySelectorAll('.dr-step-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!DR.ofertaAtiva) {
          alert('Selecione ou crie uma oferta primeiro.');
          return;
        }
        irParaStep(parseInt(btn.dataset.step));
      });
    });

    initPasso1();
  };

})();
