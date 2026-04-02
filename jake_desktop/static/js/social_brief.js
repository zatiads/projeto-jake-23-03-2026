(function () {
  'use strict';

  var SBState = {
    clientes: [],
    ultimaGeracao: null,
    editandoId: null,
    tagsBuffer: [],
    gerando: false,
  };

  // ── Init ───────────────────────────────────────────────────────────────────

  window.initSocialBrief = function () {
    carregarClientes();
    carregarUltimaGeracao();
  };

  // ── Carregar dados ─────────────────────────────────────────────────────────

  function carregarClientes() {
    fetch('/api/social-brief/clientes')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        SBState.clientes = data.clientes || [];
        renderGrid();
      })
      .catch(function (e) { console.error('Erro carregar clientes:', e); });
  }

  function carregarUltimaGeracao() {
    fetch('/api/social-brief/ultima-geracao')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        SBState.ultimaGeracao = data.geracao || null;
        renderStatusPortal();
      });
  }

  // ── Renderização ───────────────────────────────────────────────────────────

  function renderStatusPortal() {
    var url = document.getElementById('sb-portal-url');
    var meta = document.getElementById('sb-portal-meta');
    var g = SBState.ultimaGeracao;
    if (!g) {
      if (url) url.textContent = '— não gerado ainda —';
      if (meta) meta.textContent = '';
      return;
    }
    var linkUrl = g.surge_url || '';
    if (url) {
      url.textContent = linkUrl || '— não publicado —';
      url.href = linkUrl || '#';
    }
    if (meta && g.criado_em) {
      var d = new Date(g.criado_em);
      meta.textContent = 'Gerado em ' + d.toLocaleString('pt-BR') +
        ' • Semana ' + g.semana_inicio + ' a ' + g.semana_fim;
    }
    var btnAbrir = document.getElementById('sb-btn-abrir-portal');
    if (btnAbrir) btnAbrir.style.display = linkUrl ? 'inline-block' : 'none';
  }

  function renderGrid() {
    var grid = document.getElementById('sb-clientes-grid');
    if (!grid) return;
    if (!SBState.clientes.length) {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:rgba(255,255,255,.4);padding:40px;">Nenhum cliente cadastrado. Clique em "+ Novo Cliente" para começar.</div>';
      return;
    }
    grid.innerHTML = SBState.clientes.map(function (c) {
      var concList = (c.concorrentes || []).slice(0, 3).map(function (cc) {
        return '<span class="sb-tag">' + cc + '</span>';
      }).join('');
      var campList = Object.keys(c.tipos_campanha || {}).filter(function (k) { return c.tipos_campanha[k]; }).map(function (k) {
        var icons = { mensagem: '💬', visita_perfil: '👤', lead: '📋', trafego: '🌐', conversao: '🎯' };
        return '<span class="sb-tag sb-tag-camp">' + (icons[k] || '📌') + ' ' + k + '</span>';
      }).join('');
      var metaMasked = c.meta_account_id ? c.meta_account_id.replace(/(\d{3})\d+(\d{3})/, '$1...$2') : '—';
      return '<div class="sb-card">' +
        '<div class="sb-card-header">' +
        '<div class="sb-card-status">' + (c.ativo ? '🟢' : '🔴') + '</div>' +
        '<div class="sb-card-nome">' + c.nome + '</div>' +
        '</div>' +
        '<div class="sb-card-nicho">📂 ' + (c.nicho || '—') + '</div>' +
        '<div class="sb-card-meta">📊 Meta: ' + metaMasked + '</div>' +
        '<div class="sb-tags-row">' + concList + '</div>' +
        '<div class="sb-tags-row">' + campList + '</div>' +
        '<div class="sb-card-acoes">' +
        '<button class="btn-sb-edit" onclick="sbAbrirModalCliente(' + c.id + ')">✏️ Editar</button>' +
        '<button class="btn-sb-del" onclick="sbDeletarCliente(' + c.id + ', \'' + c.nome.replace(/'/g, '') + '\')">🗑️</button>' +
        '</div>' +
        '</div>';
    }).join('');
  }

  // ── Modal cliente ──────────────────────────────────────────────────────────

  window.sbAbrirModalCliente = function (id) {
    SBState.editandoId = id || null;
    SBState.tagsBuffer = [];

    var titulo = document.getElementById('sb-modal-titulo');
    if (titulo) titulo.textContent = id ? 'Editar Cliente' : 'Novo Cliente';

    ['sb-cli-nome', 'sb-cli-slug', 'sb-cli-nicho', 'sb-cli-meta-id'].forEach(function (fId) {
      var el = document.getElementById(fId);
      if (el) el.value = '';
    });
    ['sb-camp-mensagem', 'sb-camp-visita', 'sb-camp-lead', 'sb-camp-trafego', 'sb-camp-conversao'].forEach(function (chk) {
      var el = document.getElementById(chk);
      if (el) el.checked = false;
    });

    if (id) {
      var cliente = SBState.clientes.find(function (c) { return c.id === id; });
      if (cliente) {
        document.getElementById('sb-cli-nome').value = cliente.nome || '';
        document.getElementById('sb-cli-slug').value = cliente.slug || '';
        document.getElementById('sb-cli-nicho').value = cliente.nicho || '';
        document.getElementById('sb-cli-meta-id').value = cliente.meta_account_id || '';
        SBState.tagsBuffer = (cliente.concorrentes || []).slice();
        var tipos = cliente.tipos_campanha || {};
        if (tipos.mensagem) document.getElementById('sb-camp-mensagem').checked = true;
        if (tipos.visita_perfil) document.getElementById('sb-camp-visita').checked = true;
        if (tipos.lead) document.getElementById('sb-camp-lead').checked = true;
        if (tipos.trafego) document.getElementById('sb-camp-trafego').checked = true;
        if (tipos.conversao) document.getElementById('sb-camp-conversao').checked = true;
      }
    }
    renderTagsConcorrentes();

    var modal = document.getElementById('sb-modal-cliente');
    if (modal) modal.classList.remove('sb-hidden');
  };

  function renderTagsConcorrentes() {
    var lista = document.getElementById('sb-tags-lista');
    if (!lista) return;
    lista.innerHTML = SBState.tagsBuffer.map(function (t, i) {
      return '<span class="sb-tag sb-tag-rem">🏢 ' + t + ' <button onclick="sbRemoverTag(' + i + ')">×</button></span>';
    }).join('');
  }

  window.sbAdicionarTagConcorrente = function (event) {
    if (event.key !== 'Enter') return;
    var inp = document.getElementById('sb-tag-input');
    var val = (inp.value || '').trim();
    if (val && !SBState.tagsBuffer.includes(val)) {
      SBState.tagsBuffer.push(val);
      renderTagsConcorrentes();
    }
    inp.value = '';
    event.preventDefault();
  };

  window.sbRemoverTag = function (idx) {
    SBState.tagsBuffer.splice(idx, 1);
    renderTagsConcorrentes();
  };

  window.sbSalvarCliente = function () {
    var nome = (document.getElementById('sb-cli-nome').value || '').trim();
    var slug = (document.getElementById('sb-cli-slug').value || '').trim();
    var nicho = (document.getElementById('sb-cli-nicho').value || '').trim();
    var metaId = (document.getElementById('sb-cli-meta-id').value || '').trim();

    if (!nome || !slug) {
      alert('Nome e slug são obrigatórios.');
      return;
    }
    if (!/^[a-z0-9-]+$/.test(slug)) {
      alert('Slug deve conter apenas letras minúsculas, números e hifens.');
      return;
    }

    var tipos = {
      mensagem: document.getElementById('sb-camp-mensagem').checked,
      visita_perfil: document.getElementById('sb-camp-visita').checked,
      lead: document.getElementById('sb-camp-lead').checked,
      trafego: document.getElementById('sb-camp-trafego').checked,
      conversao: document.getElementById('sb-camp-conversao').checked,
    };

    var payload = {
      nome: nome, slug: slug, nicho: nicho,
      meta_account_id: metaId, meta_agency: 'piloti',
      concorrentes: SBState.tagsBuffer,
      tipos_campanha: tipos, ativo: true,
    };

    var url = SBState.editandoId
      ? '/api/social-brief/clientes/' + SBState.editandoId
      : '/api/social-brief/clientes';
    var method = SBState.editandoId ? 'PUT' : 'POST';

    fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          sbFecharModal('sb-modal-cliente');
          carregarClientes();
        } else {
          alert('Erro: ' + (data.error || 'desconhecido'));
        }
      });
  };

  window.sbDeletarCliente = function (id, nome) {
    if (!confirm('Deletar "' + nome + '"?')) return;
    fetch('/api/social-brief/clientes/' + id, { method: 'DELETE' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) carregarClientes();
      });
  };

  window.sbFecharModal = function (modalId) {
    var modal = document.getElementById(modalId);
    if (modal) modal.classList.add('sb-hidden');
  };

  // ── Geração do portal ──────────────────────────────────────────────────────

  window.sbGerarPortal = function () {
    if (SBState.gerando) return;
    if (!SBState.clientes.length) {
      alert('Cadastre ao menos um cliente antes de gerar o portal.');
      return;
    }
    SBState.gerando = true;

    var modal = document.getElementById('sb-modal-geracao');
    if (modal) modal.classList.remove('sb-hidden');

    var lista = document.getElementById('sb-prog-lista');
    if (lista) {
      lista.innerHTML = SBState.clientes.map(function (c) {
        return '<div id="sb-prog-' + c.id + '" class="sb-prog-item">⏳ <b>' + c.nome + '</b> — Aguardando</div>';
      }).join('');
    }
    document.getElementById('sb-prog-fill').style.width = '0%';
    document.getElementById('sb-prog-texto').textContent = 'Iniciando...';
    document.getElementById('sb-modal-resultado').classList.add('sb-hidden');

    var source = new EventSource('/api/social-brief/gerar');

    source.onmessage = function (event) {
      var data;
      try { data = JSON.parse(event.data); } catch (e) { return; }

      if (data.progresso !== undefined) {
        document.getElementById('sb-prog-fill').style.width = data.progresso + '%';
      }

      if (data.etapa) {
        document.getElementById('sb-prog-texto').textContent = data.etapa;
      }

      if (data.cliente) {
        var clienteObj = SBState.clientes.find(function (c) { return c.nome === data.cliente; });
        if (clienteObj) {
          var el = document.getElementById('sb-prog-' + clienteObj.id);
          if (el) {
            if (data.status === 'concluido') {
              el.innerHTML = '✅ <b>' + data.cliente + '</b> — Concluído';
            } else {
              el.innerHTML = '🔄 <b>' + data.cliente + '</b> — ' + (data.etapa || 'Processando...');
            }
          }
        }
      }

      if (data.status === 'finalizado' || data.status === 'finalizado_sem_surge') {
        source.close();
        SBState.gerando = false;
        document.getElementById('sb-prog-texto').textContent = 'Concluído!';
        document.getElementById('sb-prog-fill').style.width = '100%';

        var resultado = document.getElementById('sb-modal-resultado');
        resultado.classList.remove('sb-hidden');

        if (data.url) {
          SBState.ultimaUrl = data.url;
          resultado.innerHTML = '<p style="color:#69f0ae;margin-bottom:12px;">✅ Portal publicado com sucesso!</p>' +
            '<a href="' + data.url + '" target="_blank" class="btn-neon" style="display:inline-block;margin-right:8px;">🔗 Abrir Portal</a>' +
            '<button onclick="sbCopiarLink(\'' + data.url + '\')" class="btn-outline">📋 Copiar link</button>';
          carregarUltimaGeracao();
        } else {
          resultado.innerHTML = '<p style="color:#ffd740;margin-bottom:12px;">⚠️ Portal gerado mas não publicado no Surge.</p>' +
            '<p style="color:#888;font-size:13px;">Erro: ' + (data.erro_surge || 'Verifique SURGE_TOKEN no .env') + '</p>';
        }
      }

      if (data.status === 'erro') {
        source.close();
        SBState.gerando = false;
        alert('Erro: ' + (data.mensagem || 'desconhecido'));
        sbFecharModal('sb-modal-geracao');
      }
    };

    source.onerror = function () {
      source.close();
      SBState.gerando = false;
      document.getElementById('sb-prog-texto').textContent = 'Erro na conexão.';
    };
  };

  window.sbCopiarLink = function (url) {
    navigator.clipboard.writeText(url).then(function () {
      alert('Link copiado!');
    });
  };

  window.sbAbrirPortal = function () {
    var g = SBState.ultimaGeracao;
    if (g && g.surge_url) window.open(g.surge_url, '_blank');
    else if (SBState.ultimaUrl) window.open(SBState.ultimaUrl, '_blank');
  };

  window.sbCopiarLinkPortal = function () {
    var g = SBState.ultimaGeracao;
    var url = (g && g.surge_url) || SBState.ultimaUrl;
    if (url) navigator.clipboard.writeText(url).then(function () { alert('Link copiado!'); });
  };

})();
