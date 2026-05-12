/* drive-batch.js — Drive Batch Ads wizard */
(function () {
  'use strict';

  // ── State ────────────────────────────────────────────────────────────────
  var _clientes    = [];   // all ad_client_profiles
  var _selecionados = [];  // selected client ids (multi mode)
  var _driveFiles  = [];   // [{id, name, thumbnailLink, ext, mimeType}]
  var _copies      = [];   // [{file_id, file_name, tmp_uuid, ext, titulo, texto}] (one per image)
  var _campanha    = {};   // {tipo, id, nome}
  var _conjuntos          = {};   // {num, orcamento, criativos_por}
  var _publicosDisponiveis = [];  // [{id, nome, tipo, data}] carregados da conta Meta
  var _campTipo    = 'MESSAGES';
  var _pubToken    = null;
  var _copiesLoaded = false;

  // ── Init ─────────────────────────────────────────────────────────────────
  window.driveBatchInit = function () {
    if (!_clientes.length) _carregarClientes();
    _irPasso(1);
    _atualizarSalvaOpt();
  };

  function _carregarClientes() {
    fetch('/api/anuncios/clientes')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _clientes = data.clientes || [];
        _renderizarClienteSelect();
        _renderizarListaClientes();
      });
  }

  function _renderizarClienteSelect() {
    var sel = document.getElementById('db-cliente-select');
    if (!sel) return;
    sel.innerHTML = _clientes.map(function (c) {
      return '<option value="' + c.id + '">' + c.nome + ' (' + c.agencia + ')</option>';
    }).join('');
  }

  function _renderizarListaClientes() {
    var el = document.getElementById('db-lista-clientes');
    if (!el) return;
    el.innerHTML = _clientes.map(function (c) {
      return '<label style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:rgba(176,190,197,.05);border-radius:6px;cursor:pointer;font-size:13px;">' +
        '<input type="checkbox" value="' + c.id + '" onchange="dbToggleCliente(' + c.id + ')" style="accent-color:#00b4d8">' +
        '<span>' + c.nome + '</span>' +
        '<span style="font-size:11px;color:rgba(176,190,197,.4)">(' + c.agencia + ')</span>' +
        '</label>';
    }).join('');
  }

  // ── Step navigation ───────────────────────────────────────────────────────
  function _irPasso(n) {
    [1, 2, 3, 4].forEach(function (i) {
      var p = document.getElementById('db-passo-' + i);
      if (p) p.style.display = (i === n) ? '' : 'none';
      var s = document.querySelector('.db-step[data-step="' + i + '"]');
      if (s) s.classList.toggle('active', i === n);
    });
    if (n === 4) _renderizarResumo();
  }
  window.dbIrPasso = _irPasso;

  // ── Passo 1: Drive loading ────────────────────────────────────────────────
  window.dbCarregarDrive = function () {
    var url = (document.getElementById('db-drive-url').value || '').trim();
    if (!url) return;
    var btn    = document.getElementById('db-btn-carregar');
    var status = document.getElementById('db-drive-status');
    btn.disabled = true;
    status.textContent = 'Carregando...';

    fetch('/api/anuncios/drive/listar', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: url}),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        btn.disabled = false;
        if (data.error) { status.textContent = '✗ ' + data.error; return; }
        _driveFiles = data.files || [];
        _copies = [];
        _copiesLoaded = false;
        status.textContent = '✓ ' + _driveFiles.length + ' imagens encontradas';
        _renderizarThumbs();
        document.getElementById('db-drive-preview').style.display = '';
        document.getElementById('db-cliente-section').style.display = '';
        document.getElementById('db-btn-passo2').disabled = false;
      })
      .catch(function (e) {
        btn.disabled = false;
        status.textContent = '✗ Erro: ' + e.message;
      });
  };

  function _renderizarThumbs() {
    var el = document.getElementById('db-drive-thumbs');
    var count = document.getElementById('db-drive-count');
    if (!el) return;
    count.textContent = _driveFiles.length + ' imagens';
    el.innerHTML = _driveFiles.slice(0, 30).map(function (f) {
      return '<img src="/api/anuncios/drive/thumb/' + f.id + '" style="width:48px;height:48px;object-fit:cover;border-radius:4px;" title="' + f.name + '" onerror="this.style.opacity=\'0.2\'">';
    }).join('');
    if (_driveFiles.length > 30) {
      el.innerHTML += '<div style="font-size:11px;color:rgba(176,190,197,.3);align-self:center">+' + (_driveFiles.length - 30) + ' mais</div>';
    }
  }

  window.dbModoChange = function () {
    var modo = document.querySelector('input[name="db-mode"]:checked');
    if (!modo) return;
    document.getElementById('db-single-cliente').style.display = modo.value === 'single' ? '' : 'none';
    document.getElementById('db-multi-clientes').style.display = modo.value === 'multi' ? '' : 'none';
    _atualizarSalvaOpt();
  };

  function _atualizarSalvaOpt() {
    var modo = document.querySelector('input[name="db-mode"]:checked');
    var salvaOpt = document.getElementById('db-salva-opt');
    if (salvaOpt) salvaOpt.style.display = (modo && modo.value === 'multi') ? 'flex' : 'none';
  }

  window.dbToggleCliente = function (id) {
    var idx = _selecionados.indexOf(id);
    if (idx >= 0) _selecionados.splice(idx, 1);
    else _selecionados.push(id);
  };

  window.dbSelecionarAgencia = function (agencia) {
    _selecionados = _clientes.filter(function (c) {
      return c.agencia === agencia;
    }).map(function (c) { return c.id; });
    var checkboxes = document.querySelectorAll('#db-lista-clientes input[type="checkbox"]');
    checkboxes.forEach(function (cb) {
      cb.checked = _selecionados.indexOf(parseInt(cb.value)) >= 0;
    });
  };

  window.dbLimparClientes = function () {
    _selecionados = [];
    var checkboxes = document.querySelectorAll('#db-lista-clientes input[type="checkbox"]');
    checkboxes.forEach(function (cb) { cb.checked = false; });
  };

  // ── Passo 2: Configuração ─────────────────────────────────────────────────
  window.dbCampTipoChange = function () {
    _campTipo = document.getElementById('db-camp-tipo').value || 'MESSAGES';
    dbValidarConfig();
  };

  window.dbCampSelChange = function () {
    var tipo = document.querySelector('input[name="db-camp-tipo-sel"]:checked');
    if (!tipo) return;
    document.getElementById('db-camp-nova').style.display     = tipo.value === 'nova' ? '' : 'none';
    document.getElementById('db-camp-existente').style.display = tipo.value === 'existente' ? '' : 'none';
  };

  window.dbBuscarCampanhas = function () {
    var modo = document.querySelector('input[name="db-mode"]:checked');
    var clienteId;
    if (modo && modo.value === 'single') {
      clienteId = document.getElementById('db-cliente-select').value;
    } else {
      clienteId = _selecionados[0];
    }
    if (!clienteId) { alert('Selecione um cliente primeiro.'); return; }

    var lista = document.getElementById('db-campanhas-lista');
    lista.innerHTML = '<div style="font-size:12px;color:rgba(176,190,197,.4)">Buscando...</div>';

    fetch('/api/anuncios/drive/campanhas?cliente_id=' + clienteId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { lista.innerHTML = '<div style="color:#ff6464;font-size:12px">✗ ' + data.error + '</div>'; return; }
        var camps = data.campanhas || [];
        lista.innerHTML = camps.map(function (c) {
          return '<label style="display:flex;align-items:center;gap:8px;padding:6px 8px;background:rgba(176,190,197,.05);border-radius:4px;cursor:pointer;font-size:12px;">' +
            '<input type="radio" name="db-camp-sel" value="' + c.id + '">' +
            '<span>' + c.name + '</span>' +
            '<span style="font-size:10px;color:rgba(176,190,197,.3)">(' + c.status + ')</span>' +
            '</label>';
        }).join('') || '<div style="font-size:12px;color:rgba(176,190,197,.4)">Nenhuma campanha encontrada.</div>';
      });
  };

  window.dbValidarConfig = function () {
    var num   = parseInt(document.getElementById('db-num-conj').value) || 0;
    var criat = parseInt(document.getElementById('db-criat-por').value) || 0;
    var total = _driveFiles.length;
    var status = document.getElementById('db-config-status');
    var btn    = document.getElementById('db-btn-passo3');

    if (num > 0 && criat > 0) {
      var calc = num * criat;
      if (calc === total) {
        status.textContent = '✓ ' + num + ' conjuntos × ' + criat + ' criativos = ' + calc + ' imagens ✓';
        status.style.color = '#4caf50';
        if (btn) btn.disabled = false;
        _renderPublicosConj(num);
        document.getElementById('db-publicos-conj').style.display = '';
      } else {
        status.textContent = '✗ ' + num + ' × ' + criat + ' = ' + calc + ', mas a pasta tem ' + total + ' imagens';
        status.style.color = '#ff6464';
        if (btn) btn.disabled = true;
        document.getElementById('db-publicos-conj').style.display = 'none';
      }
    } else {
      status.textContent = '';
      if (btn) btn.disabled = true;
      document.getElementById('db-publicos-conj').style.display = 'none';
    }
  };

  function _renderPublicosConj(num) {
    var container = document.getElementById('db-publicos-rows');
    if (!container) return;
    container.innerHTML = '<div style="font-size:11px;color:rgba(176,190,197,.35);padding:4px 0;">Carregando públicos da conta...</div>';

    var modo = document.querySelector('input[name="db-mode"]:checked');
    var clienteId = (modo && modo.value === 'multi') ? _selecionados[0] : document.getElementById('db-cliente-select').value;
    if (!clienteId) { container.innerHTML = ''; return; }

    fetch('/api/anuncios/drive/publicos?cliente_id=' + clienteId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _publicosDisponiveis = data.publicos || [];
        _renderPublicosRows(num);
      })
      .catch(function () {
        _publicosDisponiveis = [];
        _renderPublicosRows(num);
      });
  }

  function _renderPublicosRows(num) {
    var container = document.getElementById('db-publicos-rows');
    if (!container) return;
    container.innerHTML = '';

    var opts = '<option value="padrao">— Padrão do cliente —</option>';
    if (_publicosDisponiveis.length) {
      var salvos  = _publicosDisponiveis.filter(function (p) { return p.tipo === 'salvo'; });
      var customs = _publicosDisponiveis.filter(function (p) { return p.tipo === 'custom'; });
      if (salvos.length) {
        opts += '<optgroup label="Públicos salvos">';
        salvos.forEach(function (p) { opts += '<option value="' + p.id + '">' + p.nome + '</option>'; });
        opts += '</optgroup>';
      }
      if (customs.length) {
        opts += '<optgroup label="Públicos personalizados (rmkt)">';
        customs.forEach(function (p) { opts += '<option value="' + p.id + '">' + p.nome + '</option>'; });
        opts += '</optgroup>';
      }
    } else {
      opts += '<option disabled style="color:rgba(176,190,197,.3)">Nenhum público salvo encontrado</option>';
    }

    for (var i = 1; i <= num; i++) {
      var div = document.createElement('div');
      div.className = 'db-pub-row';
      div.style.cssText = 'display:flex;align-items:center;gap:12px;padding:8px 10px;background:rgba(176,190,197,.04);border:1px solid rgba(176,190,197,.08);border-radius:6px;margin-bottom:5px;';
      div.innerHTML =
        '<span style="font-size:11px;font-weight:600;color:rgba(176,190,197,.55);flex-shrink:0;min-width:72px;">Conjunto ' + i + '</span>' +
        '<select id="db-pub-sel-' + i + '" class="anu-input" style="flex:1;">' + opts + '</select>';
      container.appendChild(div);
    }
  }

  function _getPublicosConj() {
    var num = parseInt(document.getElementById('db-num-conj').value) || 0;
    var result = [];
    for (var i = 1; i <= num; i++) {
      var sel = document.getElementById('db-pub-sel-' + i);
      var val = sel ? sel.value : 'padrao';
      if (!val || val === 'padrao') {
        result.push({tipo: 'padrao'});
      } else {
        var pub = _publicosDisponiveis.filter(function (p) { return p.id === val; })[0];
        result.push(pub ? {tipo: pub.tipo, id: pub.id, data: pub.data} : {tipo: 'padrao'});
      }
    }
    return result;
  }

  // ── Passo 3: Gerar copies ─────────────────────────────────────────────────
  window.dbGerarCopies = function () {
    var modo = document.querySelector('input[name="db-mode"]:checked');
    var clienteId;
    if (modo && modo.value === 'single') {
      clienteId = document.getElementById('db-cliente-select').value;
    } else {
      clienteId = _selecionados[0];
    }

    document.getElementById('db-copies-idle').style.display = 'none';
    document.getElementById('db-copies-progresso').style.display = '';
    document.getElementById('db-copies-grid').style.display = 'none';
    document.getElementById('db-copies-rows').innerHTML = '';
    _copies = [];
    _copiesLoaded = false;

    var total   = _driveFiles.length;
    var counter = document.getElementById('db-copies-counter');
    var bar     = document.getElementById('db-copies-bar');
    var done    = 0;

    fetch('/api/anuncios/drive/iniciar-copies', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        files: _driveFiles,
        campanha_tipo: _campTipo,
        cliente_id: clienteId,
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { alert('Erro: ' + data.error); _resetCopiesUI(); return; }

        var es = new EventSource('/api/anuncios/drive/gerar-copies/stream/' + data.copies_token);

        es.addEventListener('copy', function (e) {
          var d = JSON.parse(e.data);
          done++;
          counter.textContent = 'Gerando ' + done + '/' + total + '...';
          bar.style.width = Math.round((done / total) * 100) + '%';
          _copies.push({
            file_id:   d.file_id,
            file_name: d.file_name,
            tmp_uuid:  d.tmp_uuid,
            ext:       d.ext,
            titulo:    d.titulo,
            texto:     d.texto,
          });
          _renderizarCopyRow(d, _copies.length - 1);
        });

        es.addEventListener('erro', function (e) {
          var d = JSON.parse(e.data);
          done++;
          counter.textContent = 'Gerando ' + done + '/' + total + '...';
          bar.style.width = Math.round((done / total) * 100) + '%';
          _copies.push({
            file_id:   d.file_id,
            file_name: '',
            tmp_uuid:  d.tmp_uuid || '',
            ext:       d.ext || '.jpg',
            titulo:    '',
            texto:     '',
          });
          _renderizarCopyRowErro(d, _copies.length - 1);
        });

        es.addEventListener('concluido', function () {
          es.close();
          document.getElementById('db-copies-progresso').style.display = 'none';
          document.getElementById('db-copies-grid').style.display = '';
          _copiesLoaded = true;
        });

        es.onerror = function () {
          es.close();
          _resetCopiesUI();
          alert('Erro na geração de copies. Tente novamente.');
        };
      });
  };

  function _resetCopiesUI() {
    document.getElementById('db-copies-idle').style.display = '';
    document.getElementById('db-copies-progresso').style.display = 'none';
  }

  function _renderizarCopyRow(d, idx) {
    var grid = document.getElementById('db-copies-rows');
    if (!grid) return;
    grid.style.display = '';
    var thumb = d.file_id
      ? '<img src="/api/anuncios/drive/thumb/' + d.file_id + '" style="width:48px;height:48px;object-fit:cover;border-radius:4px;flex-shrink:0;" onerror="this.style.opacity=\'0.2\'">'
      : '<div style="width:48px;height:48px;background:rgba(176,190,197,.1);border-radius:4px;flex-shrink:0;"></div>';
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:10px;align-items:flex-start;padding:10px;background:rgba(176,190,197,.05);border-radius:6px;';
    row.innerHTML = thumb +
      '<div style="flex:1;display:flex;flex-direction:column;gap:6px;">' +
        '<div style="font-size:11px;color:rgba(176,190,197,.3)">' + (d.file_name || '') + '</div>' +
        '<input type="text" class="anu-input db-copy-titulo" data-idx="' + idx + '" ' +
               'value="' + _esc(d.titulo) + '" placeholder="Título" style="font-size:12px;" ' +
               'oninput="dbUpdateCopy(' + idx + ',\'titulo\',this.value)">' +
        '<textarea class="anu-input db-copy-texto" data-idx="' + idx + '" rows="2" ' +
                  'placeholder="Texto" style="font-size:12px;resize:vertical;" ' +
                  'oninput="dbUpdateCopy(' + idx + ',\'texto\',this.value)">' + _esc(d.texto) + '</textarea>' +
      '</div>';
    grid.appendChild(row);
  }

  function _renderizarCopyRowErro(d, idx) {
    var grid = document.getElementById('db-copies-rows');
    if (!grid) return;
    grid.style.display = '';
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:10px;align-items:flex-start;padding:10px;background:rgba(255,100,100,.05);border-radius:6px;border:1px solid rgba(255,100,100,.1);';
    row.innerHTML =
      '<div style="flex:1;display:flex;flex-direction:column;gap:6px;">' +
        '<div style="font-size:11px;color:#ff6464">✗ Erro: ' + (d.msg || '') + '. Preencha manualmente:</div>' +
        '<input type="text" class="anu-input db-copy-titulo" data-idx="' + idx + '" ' +
               'placeholder="Título" style="font-size:12px;" ' +
               'oninput="dbUpdateCopy(' + idx + ',\'titulo\',this.value)">' +
        '<textarea class="anu-input db-copy-texto" data-idx="' + idx + '" rows="2" ' +
                  'placeholder="Texto" style="font-size:12px;resize:vertical;" ' +
                  'oninput="dbUpdateCopy(' + idx + ',\'texto\',this.value)"></textarea>' +
      '</div>';
    grid.appendChild(row);
  }

  window.dbUpdateCopy = function (idx, field, value) {
    if (_copies[idx]) _copies[idx][field] = value;
  };

  // ── Passo 4: Resumo + Publicar ────────────────────────────────────────────
  function _renderizarResumo() {
    var modo     = document.querySelector('input[name="db-mode"]:checked');
    var modoVal  = modo ? modo.value : 'single';
    var numClientes = modoVal === 'single' ? 1 : _selecionados.length;
    var num      = parseInt(document.getElementById('db-num-conj').value) || 0;
    var criat    = parseInt(document.getElementById('db-criat-por').value) || 0;
    var orc      = parseFloat(document.getElementById('db-orcamento').value) || 0;
    var total    = numClientes * num * criat;

    var resumoEl = document.getElementById('db-resumo');
    if (resumoEl) {
      resumoEl.innerHTML =
        '<strong>' + numClientes + '</strong> cliente(s) × ' +
        '<strong>' + num + '</strong> conjuntos × ' +
        '<strong>' + criat + '</strong> criativos = ' +
        '<strong>' + total + '</strong> publicações' +
        '<br><small style="color:rgba(176,190,197,.4)">R$ ' + orc.toFixed(2) + ' por conjunto</small>';
    }

    var breakdownEl = document.getElementById('db-breakdown');
    if (breakdownEl) {
      var lines = [];
      for (var i = 0; i < num; i++) {
        var start = i * criat + 1;
        var end   = (i + 1) * criat;
        lines.push('Conjunto ' + (i + 1) + ': imagens ' + start + '–' + end);
      }
      breakdownEl.textContent = lines.join(' | ');
    }

    document.getElementById('db-expired-msg').style.display = 'none';
    document.getElementById('db-btn-publicar').disabled = false;
    document.getElementById('db-btn-voltar4').disabled = false;
  }

  window.dbPublicar = function () {
    var modo    = document.querySelector('input[name="db-mode"]:checked');
    var modoVal = modo ? modo.value : 'single';
    var clienteIds;
    if (modoVal === 'single') {
      clienteIds = [parseInt(document.getElementById('db-cliente-select').value)];
    } else {
      clienteIds = _selecionados.slice();
    }
    if (!clienteIds.length) { alert('Selecione ao menos um cliente.'); return; }

    var campTipoSel = document.querySelector('input[name="db-camp-tipo-sel"]:checked');
    var campSel     = campTipoSel ? campTipoSel.value : 'nova';
    var campNome    = document.getElementById('db-camp-nome').value || '';
    var campId      = '';
    if (campSel === 'existente') {
      var campRadio = document.querySelector('input[name="db-camp-sel"]:checked');
      campId = campRadio ? campRadio.value : '';
      if (!campId) { alert('Selecione uma campanha existente.'); return; }
    }

    var body = {
      cliente_ids:   clienteIds,
      mode:          modoVal,
      campanha:      {tipo: campSel, id: campId, nome: campNome},
      conjuntos: {
        num:           parseInt(document.getElementById('db-num-conj').value) || 0,
        orcamento:     parseFloat(document.getElementById('db-orcamento').value) || 0,
        criativos_por: parseInt(document.getElementById('db-criat-por').value) || 0,
      },
      campanha_tipo:  _campTipo,
      copies:         _copies,
      publicos_conj:  _getPublicosConj(),
    };

    document.getElementById('db-btn-publicar').disabled = true;
    document.getElementById('db-btn-voltar4').disabled = true;
    document.getElementById('db-pub-progresso').style.display = '';
    document.getElementById('db-pub-lista').innerHTML = '';
    document.getElementById('db-expired-msg').style.display = 'none';

    fetch('/api/anuncios/drive/preparar', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.expired) {
          document.getElementById('db-expired-msg').style.display = '';
          document.getElementById('db-btn-publicar').disabled = false;
          document.getElementById('db-btn-voltar4').disabled = false;
          document.getElementById('db-pub-progresso').style.display = 'none';
          return;
        }
        if (data.error) {
          alert('Erro: ' + data.error + (data.detalhes ? '\n' + data.detalhes.join('\n') : ''));
          document.getElementById('db-btn-publicar').disabled = false;
          document.getElementById('db-btn-voltar4').disabled = false;
          document.getElementById('db-pub-progresso').style.display = 'none';
          return;
        }
        _pubToken = data.token;
        _iniciarStream(data.token);
      })
      .catch(function (e) {
        alert('Erro: ' + e.message);
        document.getElementById('db-btn-publicar').disabled = false;
        document.getElementById('db-btn-voltar4').disabled = false;
      });
  };

  function _iniciarStream(token) {
    var lista = document.getElementById('db-pub-lista');
    var es    = new EventSource('/api/anuncios/drive/stream/' + token);

    es.onmessage = function (e) {
      var d = JSON.parse(e.data);
      var color = d.status === 'ok' ? '#4caf50' : d.status === 'erro' ? '#ff6464' : 'rgba(176,190,197,.5)';
      var icon  = d.status === 'ok' ? '✓' : d.status === 'erro' ? '✗' : '⏳';
      var item  = document.createElement('div');
      item.style.color = color;
      item.textContent = icon + ' ' + (d.msg || '');
      lista.appendChild(item);
      lista.scrollTop = lista.scrollHeight;

      if (d.status === 'concluido') {
        es.close();
        _pubToken = null;
        document.getElementById('db-btn-voltar4').disabled = false;
      }
    };

    es.onerror = function () {
      es.close();
      var item = document.createElement('div');
      item.style.color = '#ff6464';
      item.textContent = '✗ Conexão interrompida.';
      lista.appendChild(item);
      document.getElementById('db-btn-publicar').disabled = false;
      document.getElementById('db-btn-voltar4').disabled = false;
    };
  }

  // ── Utils ─────────────────────────────────────────────────────────────────
  function _esc(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

}());
