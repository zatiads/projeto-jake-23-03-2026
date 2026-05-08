/* ──────────────────────────────────────────────────────
   Jake OS — Builder de Anúncios em Lote
────────────────────────────────────────────────────── */
(function () {
  'use strict';

  // ── Estado ─────────────────────────────────────────
  var _conjuntos = [];       // [{nome, audience_id, criativos:[]}]
  var _conjIdx   = null;     // índice do conjunto ativo
  var _criatIdx  = null;     // índice do criativo ativo
  var _publicos  = [];       // cache de públicos salvos
  var _cliente   = null;     // cliente ativo (objeto)
  var MAX_CONJ   = 10;
  var MAX_CRIAT  = 10;

  // ── Helpers ────────────────────────────────────────
  function _val(id)       { var el=document.getElementById(id); return el?el.value:''; }
  function _set(id, v)    { var el=document.getElementById(id); if(el) el.value=String(v||''); }
  function _el(id)        { return document.getElementById(id); }
  function _show(id)      { var el=_el(id); if(el) el.classList.remove('hidden'); }
  function _hide(id)      { var el=_el(id); if(el) el.classList.add('hidden'); }
  function _esc(s)        { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'); }

  // ── Init (chamado por anuSwitchTab) ────────────────
  window.loteInit = function() {
    if (typeof window._anuClienteAtivo !== 'undefined') {
      _cliente = window._anuClienteAtivo;
    }
    _carregarPublicos();
    _renderTopo();
    _renderConjuntos();
    _renderCriativos();
    _renderCopy();
    _bindEvents();
  };

  function _renderTopo() {
    if (_cliente) {
      _set('lote-camp-tipo', _cliente.campanha_tipo || 'MESSAGES');
    }
    _atualizarContador();
  }

  function _atualizarContador() {
    var nConj  = _conjuntos.length;
    var nCriat = _conjuntos.reduce(function(s,c){ return s+c.criativos.length; }, 0);
    var el = _el('lote-contador');
    if (el) el.textContent = nConj + ' conjuntos × ' + (nConj ? Math.round(nCriat/nConj*10)/10 : 0) + ' criativos ≈ ' + nCriat + ' anúncios';
    _atualizarBotaoPublicar();
  }

  function _atualizarBotaoPublicar() {
    var btn = _el('lote-btn-publicar');
    if (!btn) return;
    var ok = _conjuntos.length > 0 && _conjuntos.every(function(c) {
      return c.criativos.length > 0 && c.criativos.every(function(r) {
        return r.creative_ref && r.copy && r.copy.titulo && r.copy.texto;
      });
    });
    btn.disabled = !ok;
    btn.title = ok ? '' : 'Preencha todos os criativos e copies antes de publicar';
  }

  // ── Públicos ───────────────────────────────────────
  function _carregarPublicos() {
    if (!_cliente) return;
    fetch('/api/anuncios/audiences?account_id=' + (_cliente.account_id || ''))
      .then(function(r){ return r.json(); })
      .then(function(d){ _publicos = d.audiences || []; })
      .catch(function(){});
  }

  function _pubOptions(selected) {
    var opts = '<option value="">— padrão do perfil —</option>';
    _publicos.forEach(function(p) {
      opts += '<option value="'+p.id+'"'+(p.id===selected?' selected':'')+'>'+_esc(p.nome)+'</option>';
    });
    return opts;
  }

  // ── Renderizar Conjuntos ───────────────────────────
  function _renderConjuntos() {
    var body = _el('lote-conjuntos-body');
    if (!body) return;
    if (_conjuntos.length === 0) {
      body.innerHTML = '<div class="anu-empty-state" style="height:auto;padding:1.5rem 0"><div class="anu-empty-text" style="font-size:.82rem">Clique + para adicionar um conjunto</div></div>';
      return;
    }
    body.innerHTML = _conjuntos.map(function(c, i) {
      var isActive = i === _conjIdx;
      return '<div class="lote-card'+(isActive?' active':'')+'" onclick="loteSelConj('+i+')">' +
        '<div class="lote-card-titulo">'+
          '<span>'+_esc(c.nome)+'</span>'+
          '<span style="margin-left:auto;font-size:.7rem;color:rgba(176,190,197,.4)">'+c.criativos.length+' criativos</span>'+
        '</div>'+
        '<div class="lote-publico-row">'+
          '<select class="anu-select" style="font-size:.75rem" onchange="loteSetPublico('+i+',this.value)" onclick="event.stopPropagation()">'+_pubOptions(c.audience_id)+'</select>'+
        '</div>'+
        '<div class="lote-card-actions">'+
          '<button class="anu-btn-icon" onclick="event.stopPropagation();loteRenomearConj('+i+')" title="Renomear">✎</button>'+
          '<button class="anu-btn-icon" style="color:rgba(255,82,82,.5)" onclick="event.stopPropagation();loteRemoverConj('+i+')" title="Remover">✕</button>'+
        '</div>'+
      '</div>';
    }).join('');
  }

  window.loteSelConj = function(i) {
    _conjIdx  = i;
    _criatIdx = null;
    _renderConjuntos();
    _renderCriativos();
    _renderCopy();
  };

  window.loteSetPublico = function(i, val) {
    _conjuntos[i].audience_id = val ? parseInt(val) : null;
  };

  window.loteRenomearConj = function(i) {
    var novo = prompt('Nome do conjunto:', _conjuntos[i].nome);
    if (novo && novo.trim()) { _conjuntos[i].nome = novo.trim(); _renderConjuntos(); }
  };

  window.loteRemoverConj = function(i) {
    if (!confirm('Remover conjunto "'+_conjuntos[i].nome+'" e todos os seus criativos?')) return;
    _conjuntos.splice(i, 1);
    if (_conjIdx >= _conjuntos.length) _conjIdx = _conjuntos.length ? _conjuntos.length-1 : null;
    _criatIdx = null;
    _renderConjuntos(); _renderCriativos(); _renderCopy();
    _atualizarContador();
  };

  function _adicionarConjunto() {
    if (_conjuntos.length >= MAX_CONJ) { alert('Máximo de '+MAX_CONJ+' conjuntos.'); return; }
    var n = _conjuntos.length + 1;
    _conjuntos.push({ nome: 'Conjunto ' + n, audience_id: null, criativos: [] });
    _conjIdx  = _conjuntos.length - 1;
    _criatIdx = null;
    _renderConjuntos(); _renderCriativos(); _renderCopy();
    _atualizarContador();
  }

  // ── Renderizar Criativos ───────────────────────────
  function _renderCriativos() {
    var body   = _el('lote-criativos-body');
    var header = _el('lote-criativos-header');
    var btnAdd = _el('lote-btn-add-criativo');
    if (!body) return;

    if (_conjIdx === null) {
      body.innerHTML = '<div class="anu-empty-state" style="height:auto;padding:2rem 0"><div class="anu-empty-text" style="font-size:.82rem">Selecione um conjunto</div></div>';
      if (header) header.textContent = 'Criativos';
      if (btnAdd) btnAdd.style.display = 'none';
      return;
    }
    var conj = _conjuntos[_conjIdx];
    if (header) header.textContent = 'Criativos — ' + conj.nome;
    if (btnAdd) btnAdd.style.display = '';

    if (conj.criativos.length === 0) {
      body.innerHTML = '<div class="anu-empty-state" style="height:auto;padding:1.5rem 0"><div class="anu-empty-text" style="font-size:.82rem">Clique + para adicionar um criativo</div></div>';
      return;
    }
    body.innerHTML = conj.criativos.map(function(r, i) {
      var isActive = i === _criatIdx;
      var tipoIcon = {imagem:'🖼', video:'🎬', url:'🔗', carrossel:'🎠'}[r.tipo] || '?';
      var temCopy  = r.copy && r.copy.titulo && r.copy.texto;
      var temRef   = !!r.creative_ref;
      return '<div class="lote-card'+(isActive?' active':'')+((!temRef||!temCopy)?' erro':'')+'" onclick="loteSelCriat('+i+')">' +
        '<div class="lote-card-titulo">' +
          tipoIcon + ' Criativo ' + (i+1) +
          (temRef ? ' <span style="color:#69f0ae;font-size:.7rem">✓ upload</span>' : ' <span style="color:#ff5252;font-size:.7rem">✕ sem criativo</span>') +
          (temCopy ? ' <span style="color:#69f0ae;font-size:.7rem">✓ copy</span>' : ' <span style="color:#ffd740;font-size:.7rem">! sem copy</span>') +
        '</div>' +
        '<div class="lote-card-actions">' +
          '<button class="anu-btn-icon" style="color:rgba(255,82,82,.5)" onclick="event.stopPropagation();loteRemoverCriat('+i+')" title="Remover">✕</button>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  window.loteSelCriat = function(i) {
    _criatIdx = i;
    _renderCriativos();
    _renderCopy();
  };

  window.loteRemoverCriat = function(i) {
    _conjuntos[_conjIdx].criativos.splice(i, 1);
    if (_criatIdx >= _conjuntos[_conjIdx].criativos.length) _criatIdx = null;
    _renderCriativos(); _renderCopy();
    _atualizarContador();
  };

  function _adicionarCriativo() {
    if (_conjIdx === null) return;
    var conj = _conjuntos[_conjIdx];
    if (conj.criativos.length >= MAX_CRIAT) { alert('Máximo de '+MAX_CRIAT+' criativos por conjunto.'); return; }
    conj.criativos.push({ tipo: 'imagem', creative_ref: null, copy: { titulo:'', texto:'', cta: _ctaPadrao() } });
    _criatIdx = conj.criativos.length - 1;
    _renderCriativos();
    _renderCopy();
    _atualizarContador();
  }

  function _ctaPadrao() {
    return _val('lote-camp-tipo') === 'MESSAGES' ? 'SEND_MESSAGE' : 'LEARN_MORE';
  }

  // ── Renderizar Copy ────────────────────────────────
  function _renderCopy() {
    var body   = _el('lote-copy-body');
    var header = _el('lote-copy-header');
    if (!body) return;

    if (_conjIdx === null || _criatIdx === null) {
      body.innerHTML = '<div class="anu-empty-state" style="height:auto;padding:2rem 0"><div class="anu-empty-text" style="font-size:.82rem">Selecione um criativo</div></div>';
      if (header) header.textContent = 'Copy';
      return;
    }
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    if (header) header.textContent = 'Copy — Criativo ' + (_criatIdx+1);

    body.innerHTML =
      '<div id="lote-criativo-upload-area"></div>' +
      '<label class="anu-label" style="margin-top:.75rem">Título (máx 40)<input type="text" id="lote-copy-titulo" class="anu-input" maxlength="40" placeholder="Título do anúncio" value="'+_esc(r.copy.titulo||'')+'"></label>' +
      '<label class="anu-label">Texto (máx 125)<textarea id="lote-copy-texto" class="anu-textarea" rows="3" maxlength="125" placeholder="Texto do anúncio">'+_esc(r.copy.texto||'')+'</textarea></label>' +
      '<label class="anu-label">CTA<select id="lote-copy-cta" class="anu-select">' +
        '<option value="SEND_MESSAGE"'+(r.copy.cta==='SEND_MESSAGE'?' selected':'')+'>Enviar mensagem</option>' +
        '<option value="LEARN_MORE"'+(r.copy.cta==='LEARN_MORE'?' selected':'')+'>Saiba mais</option>' +
        '<option value="SIGN_UP"'+(r.copy.cta==='SIGN_UP'?' selected':'')+'>Cadastre-se</option>' +
        '<option value="SHOP_NOW"'+(r.copy.cta==='SHOP_NOW'?' selected':'')+'>Comprar agora</option>' +
      '</select></label>';

    _renderUploadArea(r);

    ['lote-copy-titulo','lote-copy-texto','lote-copy-cta'].forEach(function(id) {
      var el = _el(id);
      if (el) el.addEventListener('change', _saveCopyField);
      if (el && id !== 'lote-copy-cta') el.addEventListener('input', _saveCopyField);
    });
  }

  function _saveCopyField() {
    if (_conjIdx === null || _criatIdx === null) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    r.copy.titulo = _val('lote-copy-titulo');
    r.copy.texto  = _val('lote-copy-texto');
    r.copy.cta    = _val('lote-copy-cta');
    _renderCriativos();
    _atualizarBotaoPublicar();
  }

  // ── Upload de Criativos ────────────────────────────
  function _renderUploadArea(r) {
    var area = _el('lote-criativo-upload-area');
    if (!area) return;

    var tiposHTML = ['imagem','video','url','carrossel'].map(function(t) {
      var icon = {imagem:'🖼',video:'🎬',url:'🔗',carrossel:'🎠'}[t];
      return '<button class="lote-tipo-btn'+(r.tipo===t?' active':'')+'" onclick="loteTipoChange(\''+t+'\')">'+ icon +' '+t+'</button>';
    }).join('');

    var uploadHTML = '';
    if (r.tipo === 'imagem' || r.tipo === 'video') {
      uploadHTML =
        '<div class="anu-dropzone" onclick="document.getElementById(\'lote-file-input\').click()">' +
          '<input type="file" id="lote-file-input" class="anu-file-hidden" accept="'+(r.tipo==='video'?'video/*':'image/*')+'">' +
          '<span class="anu-dropzone-icon">'+(r.tipo==='video'?'🎬':'🖼')+'</span>' +
          '<p>'+(r.creative_ref ? 'Criativo enviado ✓ — clique para trocar' : 'Clique para selecionar '+r.tipo)+'</p>' +
        '</div>' +
        (r.preview ? '<img class="lote-slot-preview" src="'+r.preview+'">' : '');
    } else if (r.tipo === 'url') {
      uploadHTML =
        '<div class="lote-url-row">' +
          '<input type="text" id="lote-url-input" class="anu-input" placeholder="https://...jpg ou .mp4" value="'+_esc(r._url||'')+'">' +
          '<button class="anu-btn-secondary" onclick="lotePreviewUrl()">Pré-visualizar</button>' +
        '</div>' +
        (r.preview ? '<img class="lote-slot-preview" src="'+r.preview+'"><br><button class="anu-btn-primary" style="margin-top:.4rem;font-size:.8rem" onclick="loteConfirmarUrl()">✓ Confirmar e enviar</button>' : '');
    } else if (r.tipo === 'carrossel') {
      var thumbs = (r.creative_ref && r.creative_ref.cards ? r.creative_ref.cards : []).map(function(card) {
        return card._preview ? '<img class="lote-carrossel-thumb" src="'+card._preview+'">' : '';
      }).join('');
      uploadHTML =
        '<div class="lote-carrossel-cards" id="lote-carrossel-thumbs">' + thumbs + '</div>' +
        '<button class="anu-btn-secondary" style="margin-top:.4rem;font-size:.8rem" onclick="document.getElementById(\'lote-carrossel-input\').click()">+ Adicionar imagem</button>' +
        '<input type="file" id="lote-carrossel-input" class="anu-file-hidden" accept="image/*">';
    }

    area.innerHTML = '<div class="lote-tipo-btns">' + tiposHTML + '</div>' + uploadHTML;

    var fi = _el('lote-file-input');
    if (fi) fi.onchange = function() { if(this.files[0]) _uploadArquivo(this.files[0]); };
    var ci = _el('lote-carrossel-input');
    if (ci) ci.onchange = function() { if(this.files[0]) _uploadCarrosselCard(this.files[0]); };
  }

  window.loteTipoChange = function(tipo) {
    if (_conjIdx === null || _criatIdx === null) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    r.tipo = tipo;
    r.creative_ref = null;
    r.preview = null;
    r._url = null;
    _renderCopy();
  };

  function _getCliente() { return _cliente || {}; }

  function _uploadArquivo(file) {
    if (_conjIdx === null || _criatIdx === null) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    var c = _getCliente();
    var fd = new FormData();
    fd.append('arquivo', file);
    fd.append('account_id', c.account_id || '');
    fd.append('token_key', c.token_key || 'META_ACCESS_TOKEN');

    var area = _el('lote-criativo-upload-area');
    if (area) area.innerHTML += '<div class="anu-copy-loading"><span class="anu-spinner"></span> Enviando...</div>';

    fetch('/api/anuncios/upload-criativo', { method:'POST', body: fd })
      .then(function(resp){ return resp.json(); })
      .then(function(d) {
        if (d.error) { alert('Erro upload: ' + d.error); return; }
        r.creative_ref = d;
        r.preview = URL.createObjectURL(file);
        _renderCriativos();
        _renderCopy();
        _atualizarBotaoPublicar();
      })
      .catch(function(e){ alert('Erro de rede: ' + e); });
  }

  function _uploadCarrosselCard(file) {
    if (_conjIdx === null || _criatIdx === null) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    var c = _getCliente();
    var fd = new FormData();
    fd.append('arquivo', file);
    fd.append('account_id', c.account_id || '');
    fd.append('token_key', c.token_key || 'META_ACCESS_TOKEN');

    fetch('/api/anuncios/upload-criativo', { method:'POST', body: fd })
      .then(function(resp){ return resp.json(); })
      .then(function(d) {
        if (d.error) { alert('Erro upload: ' + d.error); return; }
        if (!r.creative_ref) r.creative_ref = { tipo: 'carrossel', cards: [] };
        r.creative_ref.cards.push({ hash: d.hash, _preview: URL.createObjectURL(file) });
        _renderCriativos();
        _renderCopy();
        _atualizarBotaoPublicar();
      })
      .catch(function(e){ alert('Erro de rede: ' + e); });
  }

  window.lotePreviewUrl = function() {
    if (_conjIdx === null || _criatIdx === null) return;
    var url = _val('lote-url-input');
    if (!url) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    r._url = url;

    fetch('/api/anuncios/preview-url', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url: url})
    })
    .then(function(resp){ return resp.json(); })
    .then(function(d) {
      if (d.error) { alert('Erro: ' + d.error); return; }
      r._tmp_uuid = d.tmp_uuid;
      r._tipo_url = d.tipo;
      r.preview = '/api/anuncios/tmp-preview/' + d.tmp_uuid;
      _renderCopy();
    })
    .catch(function(e){ alert('Erro de rede: ' + e); });
  };

  window.loteConfirmarUrl = function() {
    if (_conjIdx === null || _criatIdx === null) return;
    var r = _conjuntos[_conjIdx].criativos[_criatIdx];
    if (!r._tmp_uuid) return;
    var c = _getCliente();
    var fd = new FormData();
    fd.append('tmp_uuid', r._tmp_uuid);
    fd.append('account_id', c.account_id || '');
    fd.append('token_key', c.token_key || 'META_ACCESS_TOKEN');

    fetch('/api/anuncios/upload-criativo', { method:'POST', body: fd })
      .then(function(resp){ return resp.json(); })
      .then(function(d) {
        if (d.error) { alert('Erro upload: ' + d.error); return; }
        r.creative_ref = d;
        r.tipo = d.tipo;
        _renderCriativos();
        _renderCopy();
        _atualizarBotaoPublicar();
      })
      .catch(function(e){ alert('Erro de rede: ' + e); });
  };

  // ── Gerar Copies ───────────────────────────────────
  function _gerarCopies() {
    if (!_cliente) { alert('Selecione um cliente primeiro.'); return; }
    var todos = [];
    _conjuntos.forEach(function(conj, ci) {
      conj.criativos.forEach(function(r, ri) {
        todos.push({ indice: ci+'-'+ri, tipo: r.tipo, descricao: r._url ? 'Criativo importado de URL' : 'Criativo '+r.tipo });
      });
    });
    if (todos.length === 0) { alert('Adicione criativos antes de gerar copies.'); return; }

    var btn = _el('lote-btn-gerar-copies');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Gerando...'; }

    fetch('/api/anuncios/copy-lote', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        cliente_id: _cliente.id,
        campanha_tipo: _val('lote-camp-tipo'),
        criativos: todos
      })
    })
    .then(function(r){ return r.json(); })
    .then(function(d) {
      if (d.error) { alert('Erro: ' + d.error); return; }
      (d.copies || []).forEach(function(cp) {
        var parts = cp.indice.split('-');
        var ci = parseInt(parts[0]), ri = parseInt(parts[1]);
        if (_conjuntos[ci] && _conjuntos[ci].criativos[ri]) {
          _conjuntos[ci].criativos[ri].copy = {
            titulo: cp.titulo || '',
            texto:  cp.texto  || '',
            cta:    _ctaPadrao()
          };
        }
      });
      _renderCriativos();
      _renderCopy();
      _atualizarBotaoPublicar();
    })
    .catch(function(e){ alert('Erro de rede: ' + e); })
    .finally(function() {
      if (btn) { btn.disabled = false; btn.textContent = '✦ Gerar todas as copies'; }
    });
  }

  // ── Publicar Lote via SSE ──────────────────────────
  function _publicarLote() {
    if (!_cliente) { alert('Selecione um cliente.'); return; }

    var conjuntosPayload = _conjuntos.map(function(conj) {
      return {
        nome:        conj.nome,
        audience_id: conj.audience_id || null,
        criativos:   conj.criativos.map(function(r) {
          return { creative_ref: r.creative_ref, copy: r.copy };
        })
      };
    });

    var loteId = _uuid4();
    var payload = {
      cliente_id:             _cliente.id,
      campanha_nome:          _val('lote-camp-nome') || 'Campanha Jake OS',
      campanha_tipo:          _val('lote-camp-tipo'),
      orcamento_diario_total: parseFloat(_val('lote-orcamento')) || 0,
      lote_id:                loteId,
      conjuntos:              conjuntosPayload
    };

    fetch('/api/anuncios/publicar-lote', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    })
    .then(function(r){ return r.json(); })
    .then(function(d) {
      if (d.error) { alert('Erro: ' + d.error); return; }
      _abrirModalProgresso();
      var es = new EventSource('/api/anuncios/publicar-lote/stream/' + d.lote_token);
      var totalAnuncios = conjuntosPayload.reduce(function(s,c){ return s+c.criativos.length; }, 0);
      var feito = 0;

      es.onmessage = function(e) {
        var ev = JSON.parse(e.data);
        _logProgresso(ev);
        if (ev.tipo === 'anuncio_ok' || ev.tipo === 'anuncio_erro') {
          feito++;
          var pct = Math.round(feito / totalAnuncios * 100);
          var fill = _el('lote-prog-fill');
          var stats = _el('lote-prog-stats');
          if (fill) fill.style.width = pct + '%';
          if (stats) stats.textContent = feito + ' / ' + totalAnuncios + ' anúncios processados';
        }
        if (ev.tipo === 'fim' || ev.tipo === 'erro_fatal') {
          es.close();
          _finalizarProgresso(ev);
        }
      };
      es.onerror = function() {
        es.close();
        _logProgresso({tipo:'anuncio_erro', erro:'Conexão interrompida'});
        _finalizarProgresso({tipo:'fim', total:0, sucesso:0, falha:0});
      };
    })
    .catch(function(e){ alert('Erro de rede: ' + e); });
  }

  function _abrirModalProgresso() {
    var overlay = _el('lote-modal-progresso');
    if (overlay) overlay.classList.remove('hidden');
    var log = _el('lote-prog-log');
    if (log) log.innerHTML = '';
    var fill = _el('lote-prog-fill');
    if (fill) fill.style.width = '0%';
    var stats = _el('lote-prog-stats');
    if (stats) stats.textContent = 'Iniciando...';
    _hide('lote-prog-fechar');
  }

  function _logProgresso(ev) {
    var log = _el('lote-prog-log');
    if (!log) return;
    var cls = 'info', txt = '';
    if (ev.tipo === 'campanha_ok')    { cls='ok';   txt='✓ Campanha criada: ' + ev.campaign_id; }
    else if (ev.tipo === 'conjunto_ok')   { cls='ok';   txt='✓ Conjunto '+(ev.conjunto_idx+1)+' criado: ' + ev.adset_id; }
    else if (ev.tipo === 'conjunto_erro') { cls='erro';  txt='✕ Conjunto '+(ev.conjunto_idx+1)+' falhou: ' + ev.erro; }
    else if (ev.tipo === 'anuncio_ok')    { cls='ok';   txt='✓ Anúncio '+(ev.criativo_idx+1)+' do conj '+(ev.conjunto_idx+1)+': ' + ev.ad_id; }
    else if (ev.tipo === 'anuncio_erro')  { cls='erro';  txt='✕ Anúncio '+(ev.criativo_idx+1)+' do conj '+(ev.conjunto_idx+1)+': ' + ev.erro; }
    else if (ev.tipo === 'erro_fatal')    { cls='erro';  txt='✕ Erro fatal: ' + ev.erro; }
    else if (ev.tipo === 'fim')           { cls='info';  txt='━━ Finalizado: '+ev.sucesso+' criados, '+ev.falha+' falhas'; }
    var line = document.createElement('div');
    line.className = cls;
    line.textContent = txt;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
  }

  function _finalizarProgresso(ev) {
    var modal = _el('lote-modal-progresso');
    var title = modal && modal.querySelector('.lote-progress-title');
    if (title) title.textContent = ev.tipo === 'erro_fatal' ? 'Erro na publicação' : 'Publicação concluída';
    var stats = _el('lote-prog-stats');
    if (stats && ev.tipo === 'fim') stats.textContent = ev.sucesso + ' anúncios criados, ' + ev.falha + ' falhas';
    var fill = _el('lote-prog-fill');
    if (fill && ev.tipo === 'fim') fill.style.width = '100%';
    _show('lote-prog-fechar');
    var btn = _el('lote-prog-fechar');
    if (btn) btn.onclick = function() {
      var overlay = _el('lote-modal-progresso');
      if (overlay) overlay.classList.add('hidden');
    };
  }

  // ── Bind Events ────────────────────────────────────
  function _bindEvents() {
    var btnConj = _el('lote-btn-add-conjunto');
    if (btnConj) btnConj.onclick = _adicionarConjunto;

    var btnCriat = _el('lote-btn-add-criativo');
    if (btnCriat) btnCriat.onclick = _adicionarCriativo;

    var btnGerar = _el('lote-btn-gerar-copies');
    if (btnGerar) btnGerar.onclick = _gerarCopies;

    var btnPublicar = _el('lote-btn-publicar');
    if (btnPublicar) btnPublicar.onclick = _publicarLote;
  }

  // ── UUID v4 ────────────────────────────────────────
  function _uuid4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random()*16|0, v = c==='x'?r:(r&0x3|0x8);
      return v.toString(16);
    });
  }

})();
