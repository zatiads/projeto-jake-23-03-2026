// jake_desktop/static/js/nutricao.js
(function () {
  'use strict';

  var NState = {
    perfis: [],
    cardapioAtual: null,
    cardapioId: null,
    status: null,
    diaSelecionado: 0,
    gerando: false,
    editandoDia: null,
    editandoRefeicao: null,
    perfilEditandoId: null,
  };

  var DIAS_CURTOS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // ── INIT ────────────────────────────────────────────────────────────────────
  window.initNutricao = function () {
    carregarPerfis();
    carregarUltimoCardapio();
  };

  // ── PERFIS ──────────────────────────────────────────────────────────────────
  function carregarPerfis() {
    fetch('/api/nutricao/perfis')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        NState.perfis = data.perfis || [];
        renderPerfis();
      })
      .catch(function (e) { console.error('Erro perfis:', e); });
  }

  function renderPerfis() {
    var grid = document.getElementById('nutr-perfis-grid');
    if (!grid) return;
    grid.innerHTML = NState.perfis.map(function (p) {
      var avatar = p.nome === 'Bruno' ? '👨' : '👩';
      var imc = p.imc ? p.imc.toFixed(1) : '—';
      var tmb = p.tmb ? Math.round(p.tmb) : '—';
      var getVal = p.get ? Math.round(p.get) : '—';
      var peso = p.peso ? p.peso + 'kg' : '—';
      var altura = p.altura ? p.altura + 'cm' : '—';
      var kcal = p.meta_calorica || '—';
      var prot = p.meta_proteina ? p.meta_proteina + 'g' : '—';
      var carbo = p.meta_carbo ? p.meta_carbo + 'g' : '—';
      var gord = p.meta_gordura ? p.meta_gordura + 'g' : '—';
      var obj = p.objetivo === 'hipertrofia' ? '💪 Hipertrofia' :
               p.objetivo === 'emagrecimento' ? '🔥 Emagrecimento' : '⚖️ Manutenção';
      return '<div class="nutr-perfil-card">' +
        '<div class="nutr-perfil-header">' +
          '<span class="nutr-perfil-avatar">' + avatar + '</span>' +
          '<div style="flex:1">' +
            '<div class="nutr-perfil-nome">' + esc(p.nome) + '</div>' +
            '<div class="nutr-perfil-obj">' + obj + '</div>' +
          '</div>' +
          '<button class="btn-mini" onclick="nutricaoAbrirModalPerfil(' + p.id + ')">✏️</button>' +
        '</div>' +
        '<div class="nutr-perfil-stats">' +
          '<div class="nutr-stat"><span class="nutr-stat-label">Peso</span><span class="nutr-stat-val">' + peso + '</span></div>' +
          '<div class="nutr-stat"><span class="nutr-stat-label">Altura</span><span class="nutr-stat-val">' + altura + '</span></div>' +
          '<div class="nutr-stat"><span class="nutr-stat-label">IMC</span><span class="nutr-stat-val">' + imc + '</span></div>' +
          '<div class="nutr-stat"><span class="nutr-stat-label">TMB</span><span class="nutr-stat-val">' + tmb + '</span></div>' +
        '</div>' +
        '<div class="nutr-macros">' +
          '<div class="nutr-macro nutr-macro-cal"><span>' + kcal + '</span><small>kcal/dia</small></div>' +
          '<div class="nutr-macro nutr-macro-prot"><span>' + prot + '</span><small>proteína</small></div>' +
          '<div class="nutr-macro nutr-macro-carbo"><span>' + carbo + '</span><small>carbo</small></div>' +
          '<div class="nutr-macro nutr-macro-gord"><span>' + gord + '</span><small>gordura</small></div>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  // ── MODAL PERFIL ────────────────────────────────────────────────────────────
  window.nutricaoAbrirModalPerfil = function (id) {
    NState.perfilEditandoId = id;
    var p = NState.perfis.find(function (x) { return x.id === id; }) || {};
    var titulo = document.getElementById('nutr-modal-perfil-titulo');
    if (titulo) titulo.textContent = 'Editar Perfil — ' + (p.nome || '');

    document.getElementById('nutr-perf-idade').value = p.idade || '';
    document.getElementById('nutr-perf-peso').value = p.peso || '';
    document.getElementById('nutr-perf-altura').value = p.altura || '';
    document.getElementById('nutr-perf-objetivo').value = p.objetivo || 'hipertrofia';
    document.getElementById('nutr-perf-atividade').value = p.nivel_atividade || 'intenso';
    document.getElementById('nutr-perf-preferencias').value = p.preferencias || '';

    document.getElementById('nutr-modal-perfil').classList.remove('nutr-hidden');
  };

  window.nutricaoSalvarPerfil = function () {
    var id = NState.perfilEditandoId;
    if (!id) return;
    var payload = {
      idade: parseInt(document.getElementById('nutr-perf-idade').value) || null,
      peso: parseFloat(document.getElementById('nutr-perf-peso').value) || null,
      altura: parseInt(document.getElementById('nutr-perf-altura').value) || null,
      objetivo: document.getElementById('nutr-perf-objetivo').value,
      nivel_atividade: document.getElementById('nutr-perf-atividade').value,
      preferencias: document.getElementById('nutr-perf-preferencias').value,
    };
    fetch('/api/nutricao/perfis/' + id, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.ok || data.calorias) {
        nutricaoFecharModal('nutr-modal-perfil');
        carregarPerfis();
      } else {
        alert('Erro: ' + (data.error || 'desconhecido'));
      }
    });
  };

  window.nutricaoFecharModal = function (modalId) {
    var modal = document.getElementById(modalId);
    if (modal) modal.classList.add('nutr-hidden');
  };

  // ── GERAR CARDÁPIO ──────────────────────────────────────────────────────────
  window.nutricaoGerarCardapio = function () {
    if (NState.gerando) return;
    NState.gerando = true;

    var area = document.getElementById('nutr-cardapio-area');
    var listaArea = document.getElementById('nutr-lista-area');
    if (area) area.classList.add('nutr-hidden');
    if (listaArea) listaArea.classList.add('nutr-hidden');

    // Mostrar loading na área do histórico
    var histArea = document.getElementById('nutr-historico-area');
    if (histArea) histArea.innerHTML = '<div class="nutr-loading">' +
      '<div class="nutr-spinner"></div>' +
      '<div class="nutr-loading-msg" id="nutr-loading-msg">Calculando macros...</div>' +
    '</div>';

    var mensagens = [
      'Calculando macros...',
      'Consultando alimentos favoritos...',
      'Claude está criando seu cardápio...',
      'Montando as refeições da semana...',
      'Quase pronto...',
    ];
    var msgIdx = 0;
    var msgInterval = setInterval(function () {
      msgIdx = (msgIdx + 1) % mensagens.length;
      var el = document.getElementById('nutr-loading-msg');
      if (el) el.textContent = mensagens[msgIdx];
    }, 2500);

    fetch('/api/nutricao/gerar-cardapio', {method: 'POST'})
      .then(function (r) { return r.json(); })
      .then(function (data) {
        clearInterval(msgInterval);
        NState.gerando = false;
        if (data.error) {
          alert('Erro ao gerar cardápio: ' + data.error);
          if (histArea) histArea.innerHTML = '';
          return;
        }
        NState.cardapioAtual = data.cardapio;
        NState.cardapioId = data.id;
        NState.status = 'revisao';
        NState.diaSelecionado = 0;
        if (histArea) histArea.innerHTML = '';
        renderCardapio();
        carregarHistorico();
      })
      .catch(function (e) {
        clearInterval(msgInterval);
        NState.gerando = false;
        alert('Erro de conexão: ' + e.message);
        if (histArea) histArea.innerHTML = '';
      });
  };

  // ── RENDER CARDÁPIO ─────────────────────────────────────────────────────────
  function renderCardapio() {
    var cardapio = NState.cardapioAtual;
    if (!cardapio) return;

    var area = document.getElementById('nutr-cardapio-area');
    if (area) area.classList.remove('nutr-hidden');

    var semLabel = document.getElementById('nutr-semana-label');
    if (semLabel) semLabel.textContent = 'Semana ' + (cardapio.semana || '—');

    var badge = document.getElementById('nutr-status-badge');
    if (badge) {
      badge.textContent = NState.status === 'aprovado' ? 'Aprovado' :
                          NState.status === 'revisao' ? 'Em Revisão' : 'Rascunho';
      badge.className = 'nutr-badge nutr-badge-' + (NState.status || 'rascunho');
    }

    var btnAprovar = document.getElementById('nutr-btn-aprovar');
    if (btnAprovar) btnAprovar.style.display = NState.status === 'aprovado' ? 'none' : '';

    renderDiasNav();
    renderDia(NState.diaSelecionado);
  }

  function renderDiasNav() {
    var nav = document.getElementById('nutr-dias-nav');
    if (!nav || !NState.cardapioAtual) return;
    var dias = NState.cardapioAtual.dias || [];
    nav.innerHTML = dias.map(function (d, i) {
      var nome = d.dia || DIAS_CURTOS[i] || ('Dia ' + (i + 1));
      var curto = nome.substring(0, 3);
      return '<button class="nutr-dia-tab' + (i === NState.diaSelecionado ? ' ativo' : '') +
        '" onclick="nutricaoSelecionarDia(' + i + ')">' + esc(curto) + '</button>';
    }).join('');
  }

  window.nutricaoSelecionarDia = function (idx) {
    NState.diaSelecionado = idx;
    renderDiasNav();
    renderDia(idx);
  };

  function renderDia(idx) {
    var content = document.getElementById('nutr-dia-content');
    if (!content || !NState.cardapioAtual) return;
    var dia = (NState.cardapioAtual.dias || [])[idx];
    if (!dia) { content.innerHTML = ''; return; }

    var r = dia.refeicoes || {};

    function cardRefeicao(tipo, label, emoji) {
      var ref = r[tipo] || {};
      var congelavel = ref.congelavel ? '<span class="nutr-ref-congelavel" title="Pode congelar">🧊</span>' : '';
      var prato = '';
      if (tipo === 'almoco' || tipo === 'janta') {
        var partes = [ref.prato_principal, ref.acompanhamento, ref.verdura].filter(Boolean);
        prato = partes.join(' · ') || '—';
      } else {
        prato = ref.descricao || '—';
      }
      var brunoInfo = '';
      var camilaInfo = '';
      if (ref.bruno) {
        brunoInfo = '<span>👨 ' + esc(ref.bruno.porcao || '') + (ref.bruno.calorias ? ' · ' + ref.bruno.calorias + ' kcal' : '') + '</span>';
      }
      if (ref.camila) {
        camilaInfo = '<span>👩 ' + esc(ref.camila.porcao || '') + (ref.camila.calorias ? ' · ' + ref.camila.calorias + ' kcal' : '') + '</span>';
      }
      var tempo = (tipo === 'almoco' || tipo === 'janta') && ref.tempo_preparo ?
        '<span style="font-size:11px;color:#546e7a">⏱ ' + esc(ref.tempo_preparo) + '</span>' : '';
      var btnEditar = '<button class="nutr-btn-editar" onclick="nutricaoAbrirModalRefeicao(\'' + dia.dia + '\',\'' + tipo + '\')">✏️</button>';

      return '<div class="nutr-refeicao-card">' +
        congelavel +
        btnEditar +
        '<div class="nutr-ref-tipo">' + emoji + ' ' + label + '</div>' +
        '<div class="nutr-ref-prato">' + esc(prato) + '</div>' +
        tempo +
        '<div class="nutr-ref-pessoas">' + brunoInfo + camilaInfo + '</div>' +
      '</div>';
    }

    var suco = r.suco_dia || {};
    var fruta = r.fruta_dia || '';
    var sucoDesc = suco.nome ? esc(suco.nome) + (suco.beneficio ? ' · <small>' + esc(suco.beneficio) + '</small>' : '') : '—';
    var ingredientesStr = (suco.ingredientes || []).join(', ');

    content.innerHTML =
      '<div class="nutr-refeicoes-grid">' +
        cardRefeicao('cafe_manha', 'Café da Manhã', '☀️') +
        cardRefeicao('almoco', 'Almoço', '🍽') +
        cardRefeicao('cafe_tarde', 'Café da Tarde', '🫖') +
        cardRefeicao('janta', 'Janta', '🌙') +
      '</div>' +
      '<div class="nutr-extras-grid">' +
        '<div class="nutr-extra-card">' +
          '<div class="nutr-extra-tipo">🥤 Suco do Dia</div>' +
          '<div class="nutr-extra-desc">' + sucoDesc + '</div>' +
          (ingredientesStr ? '<div class="nutr-extra-sub">' + esc(ingredientesStr) + '</div>' : '') +
        '</div>' +
        '<div class="nutr-extra-card">' +
          '<div class="nutr-extra-tipo">🍎 Fruta do Dia</div>' +
          '<div class="nutr-extra-desc">' + esc(fruta || '—') + '</div>' +
        '</div>' +
      '</div>';
  }

  // ── APROVAR CARDÁPIO ─────────────────────────────────────────────────────────
  window.nutricaoAprovarCardapio = function () {
    if (!NState.cardapioId) return;
    if (!confirm('Aprovar este cardápio e gerar a lista de compras?')) return;

    fetch('/api/nutricao/cardapios/' + NState.cardapioId + '/aprovar', {method: 'PATCH'})
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { alert('Erro: ' + (data.error || '?')); return; }
        NState.status = 'aprovado';
        renderCardapio();
        return fetch('/api/nutricao/lista-compras/' + NState.cardapioId, {method: 'POST'});
      })
      .then(function (r) { if (r) return r.json(); })
      .then(function (data) {
        if (data && data.lista) {
          renderListaCompras(data.lista);
        }
      })
      .catch(function (e) { alert('Erro: ' + e.message); });
  };

  // ── EDITAR REFEIÇÃO ──────────────────────────────────────────────────────────
  window.nutricaoAbrirModalRefeicao = function (dia, tipo) {
    NState.editandoDia = dia;
    NState.editandoRefeicao = tipo;
    var labels = {cafe_manha: 'Café da Manhã', almoco: 'Almoço', cafe_tarde: 'Café da Tarde', janta: 'Janta'};
    var titulo = document.getElementById('nutr-modal-ref-titulo');
    if (titulo) titulo.textContent = 'Editar ' + (labels[tipo] || tipo) + ' — ' + dia;
    document.getElementById('nutr-modal-ref-input').value = '';
    document.getElementById('nutr-modal-refeicao').classList.remove('nutr-hidden');
  };

  window.nutricaoSalvarEdicaoRefeicao = function () {
    var input = document.getElementById('nutr-modal-ref-input').value.trim();
    if (!input) return;
    if (!NState.cardapioId) return;

    var novoConteudo = {descricao: input};

    fetch('/api/nutricao/cardapios/' + NState.cardapioId + '/editar-refeicao', {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        dia: NState.editandoDia,
        refeicao: NState.editandoRefeicao,
        novo_conteudo: novoConteudo,
      }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.ok && data.cardapio) {
        NState.cardapioAtual = data.cardapio;
        nutricaoFecharModal('nutr-modal-refeicao');
        renderDia(NState.diaSelecionado);
      }
    });
  };

  // ── LISTA DE COMPRAS ─────────────────────────────────────────────────────────
  function renderListaCompras(lista) {
    var area = document.getElementById('nutr-lista-area');
    var container = document.getElementById('nutr-lista-container');
    if (!area || !container) return;
    area.classList.remove('nutr-hidden');

    if (lista.dica) {
      container.innerHTML = '<p style="color:#90a4ae;font-size:13px;margin-bottom:12px;">💡 ' + esc(lista.dica) + '</p>';
    } else {
      container.innerHTML = '';
    }

    (lista.categorias || []).forEach(function (cat) {
      if (!cat.itens || !cat.itens.length) return;
      var itensHtml = cat.itens.map(function (item) {
        var obs = item.observacao ? ' <span style="color:#546e7a;font-size:11px;">(' + esc(item.observacao) + ')</span>' : '';
        return '<div class="nutr-lista-item" onclick="this.classList.toggle(\'marcado\')">' +
          '<input type="checkbox" onclick="event.stopPropagation();this.closest(\'.nutr-lista-item\').classList.toggle(\'marcado\')">' +
          '<span>' + esc(item.item) + obs + '</span>' +
          '<span class="nutr-lista-item-qtd">' + esc(item.quantidade || '') + '</span>' +
        '</div>';
      }).join('');
      container.innerHTML += '<div class="nutr-lista-cat">' +
        '<div class="nutr-lista-cat-header">' + (cat.emoji || '') + ' ' + esc(cat.nome) + '</div>' +
        itensHtml +
      '</div>';
    });
  }

  // ── EXPORTAR WHATSAPP ────────────────────────────────────────────────────────
  window.nutricaoCopiarWhatsapp = function () {
    if (!NState.cardapioId) return;
    fetch('/api/nutricao/exportar-whatsapp/' + NState.cardapioId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.sucesso || !data.texto) {
          alert('Erro ao gerar texto: ' + (data.error || '?'));
          return;
        }
        if (navigator.clipboard) {
          navigator.clipboard.writeText(data.texto).then(function () {
            alert('Lista copiada! Abrindo WhatsApp Web...');
            window.open('https://wa.me/?text=' + encodeURIComponent(data.texto), '_blank');
          });
        } else {
          window.open('https://wa.me/?text=' + encodeURIComponent(data.texto), '_blank');
        }
      });
  };

  // ── EXPORTAR PDF ─────────────────────────────────────────────────────────────
  window.nutricaoBaixarPDF = function () {
    if (!NState.cardapioId) return;
    window.open('/api/nutricao/exportar-pdf/' + NState.cardapioId, '_blank');
  };

  // ── HISTÓRICO ────────────────────────────────────────────────────────────────
  function carregarHistorico() {
    fetch('/api/nutricao/cardapios')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderHistorico(data.cardapios || []);
      });
  }

  function carregarUltimoCardapio() {
    fetch('/api/nutricao/cardapios')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var lista = data.cardapios || [];
        renderHistorico(lista);
        if (lista.length > 0 && !NState.cardapioAtual) {
          carregarCardapioById(lista[0].id);
        }
      });
  }

  function carregarCardapioById(id) {
    fetch('/api/nutricao/cardapios/' + id)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.cardapio_json) {
          NState.cardapioAtual = data.cardapio_json;
          NState.cardapioId = data.id;
          NState.status = data.status;
          NState.diaSelecionado = 0;
          renderCardapio();
          if (data.status === 'aprovado' && data.lista_compras_json) {
            renderListaCompras(data.lista_compras_json);
          }
        }
      });
  }

  function renderHistorico(lista) {
    var el = document.getElementById('nutr-historico-lista');
    if (!el) return;
    if (!lista.length) { el.innerHTML = '<p style="color:#546e7a;font-size:13px;">Nenhum cardápio anterior.</p>'; return; }
    el.innerHTML = lista.slice(0, 5).map(function (c) {
      var statusBadge = '<span class="nutr-badge nutr-badge-' + esc(c.status) + '" style="font-size:10px;">' +
        (c.status === 'aprovado' ? 'Aprovado' : c.status === 'revisao' ? 'Em Revisão' : 'Rascunho') + '</span>';
      var data = c.criado_em ? new Date(c.criado_em).toLocaleDateString('pt-BR') : '—';
      return '<div class="nutr-hist-item" onclick="nutricaoCarregarCardapio(' + c.id + ')">' +
        '<span class="nutr-hist-semana">Semana ' + esc(c.semana_inicio || '—') + ' a ' + esc(c.semana_fim || '—') + '</span>' +
        statusBadge +
        '<span class="nutr-hist-data">' + data + '</span>' +
      '</div>';
    }).join('');
  }

  window.nutricaoCarregarCardapio = function (id) {
    carregarCardapioById(id);
  };
})();
