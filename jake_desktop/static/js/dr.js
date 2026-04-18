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
  };

})();
