/* ──────────────────────────────────────────────────────
   Jake OS — Módulo Subir Anúncios
────────────────────────────────────────────────────── */
(function () {
  'use strict';

  // ── Estado ─────────────────────────────────────────
  var _clientes     = [];
  var _clienteAtivo = null;
  var _modoPerfilId = null;    // null=novo, int=editando
  var _creativeRef  = null;    // {tipo, hash|video_id}
  var _creativeB64  = null;    // base64 da imagem para copy
  var _creativeMime = null;
  var _publicos     = [];
  var _pubEditId    = null;

  // ── Sub-navegação tabs ──────────────────────────────
  window.anuSwitchTab = function(tab) {
    ['publicar', 'publicos', 'lote'].forEach(function(t) {
      var el  = document.getElementById('anu-tab-' + t);
      var btn = document.querySelector('[data-tab="' + t + '"]');
      if (el)  el.style.display = (t === tab) ? '' : 'none';
      if (btn) btn.classList.toggle('active', t === tab);
    });
    if (tab === 'publicos') carregarPublicos();
    if (tab === 'lote' && typeof loteInit === 'function') loteInit();
  };

  // ── Init ───────────────────────────────────────────
  function init() {
    carregarClientes();
    bindSidebarEvents();
    bindPerfilFormEvents();
    bindCampanhaEvents();
    bindCreativoEvents();
    bindCopyEvents();
    bindRevisaoEvents();
    bindModalEvents();
    bindPublicosEvents();
    carregarPublicos();
  }

  // ── Carregar e renderizar clientes ─────────────────
  function carregarClientes() {
    fetch('/api/anuncios/clientes')
      .then(function(r){ return r.json(); })
      .then(function(d){ _clientes = d.clientes || []; renderSidebar(); })
      .catch(function(e){ console.error('Erro ao carregar clientes:', e); });
  }

  function renderSidebar() {
    var grupos = { piloti:[], dentto:[], freelance:[] };
    _clientes.forEach(function(c){ if(grupos[c.agencia]) grupos[c.agencia].push(c); });
    ['piloti','dentto','freelance'].forEach(function(ag) {
      var ul = document.getElementById('anu-lista-'+ag);
      if (!ul) return;
      ul.innerHTML = grupos[ag].map(function(c) {
        var ativo = _clienteAtivo && _clienteAtivo.id===c.id ? ' active':'';
        return '<li class="anu-cliente-item'+ativo+'" data-id="'+c.id+'">' +
          '<span>'+_esc(c.nome)+'</span>' +
          '<button class="anu-cliente-edit-btn" data-id="'+c.id+'" title="Editar">✎</button>' +
          '</li>';
      }).join('');
      ul.querySelectorAll('.anu-cliente-item').forEach(function(li) {
        li.addEventListener('click', function(e) {
          if (e.target.classList.contains('anu-cliente-edit-btn')) return;
          selecionarCliente(parseInt(this.dataset.id));
        });
      });
      ul.querySelectorAll('.anu-cliente-edit-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          abrirFormPerfil(parseInt(this.dataset.id));
        });
      });
    });
  }

  function selecionarCliente(id) {
    _clienteAtivo = _clientes.find(function(c){ return c.id===id; }) || null;
    window._anuClienteAtivo = _clienteAtivo;
    renderSidebar();
    mostrarCriacao();
  }

  function bindSidebarEvents() {
    var r = document.getElementById('anu-btn-refresh-clientes');
    if (r) r.addEventListener('click', carregarClientes);
    document.querySelectorAll('.anu-btn-novo-cliente').forEach(function(btn) {
      btn.addEventListener('click', function(){ abrirFormPerfil(null, this.dataset.agencia); });
    });
  }

  // ── Formulário de perfil ────────────────────────────
  function abrirFormPerfil(id, agenciaPadrao) {
    _modoPerfilId = id || null;
    _setText('anu-perfil-titulo', id ? 'Editar Cliente' : 'Novo Cliente');
    ['anu-pf-nome','anu-pf-account-id','anu-pf-page-id','anu-pf-whatsapp','anu-pf-segmento','anu-pf-orcamento'].forEach(function(fid){
      var el=document.getElementById(fid); if(el) el.value='';
    });
    var elLoc=document.getElementById('anu-pf-localizacao'); if(elLoc) elLoc.value='';
    var elPub=document.getElementById('anu-pf-publico');     if(elPub) elPub.value='';

    if (id) {
      var c = _clientes.find(function(x){ return x.id===id; });
      if (c) preencherFormPerfil(c);
    } else if (agenciaPadrao) {
      _set('anu-pf-agencia', agenciaPadrao);
    }
    esconder('anu-empty'); esconder('anu-criacao'); mostrar('anu-perfil-form');
  }

  function preencherFormPerfil(c) {
    _set('anu-pf-nome',       c.nome);
    _set('anu-pf-agencia',    c.agencia);
    _set('anu-pf-account-id', c.account_id);
    _set('anu-pf-token-key',  c.token_key);
    _set('anu-pf-business-id', c.business_id||'');
    _set('anu-pf-link-url',    c.link_url||'');
    // Pré-popular dropdown de páginas com o valor salvo
    var sel = document.getElementById('anu-pf-page-id');
    if (sel && c.page_id) {
      var exists = sel.querySelector('option[value="'+c.page_id+'"]');
      if (!exists) {
        var opt = document.createElement('option');
        opt.value = c.page_id;
        opt.textContent = c.page_id;
        opt.selected = true;
        sel.appendChild(opt);
      } else { exists.selected = true; }
    }
    _set('anu-pf-whatsapp',   c.whatsapp||'');
    _set('anu-pf-segmento',   c.segmento||'');
    _set('anu-pf-camp-tipo',  c.campanha_tipo||'MESSAGES');
    _set('anu-pf-optimization-goal', c.optimization_goal||'LINK_CLICKS');
    _set('anu-pf-pixel-id',  c.pixel_id||'');
    _set('anu-pf-orcamento',  c.orcamento_diario||'');
    var elLoc=document.getElementById('anu-pf-localizacao');
    if (elLoc) elLoc.value = c.localizacao_json ? JSON.stringify(c.localizacao_json,null,2):'';
    var elPub=document.getElementById('anu-pf-publico');
    if (elPub) elPub.value = c.publico_json ? JSON.stringify(c.publico_json,null,2):'';
  }

  function bindPerfilFormEvents() {
    var s=document.getElementById('anu-perfil-salvar');   if(s) s.addEventListener('click',salvarPerfil);
    var c=document.getElementById('anu-perfil-cancelar'); if(c) c.addEventListener('click',function(){
      esconder('anu-perfil-form');
      if (_clienteAtivo) mostrarCriacao(); else mostrar('anu-empty');
    });
    var e=document.getElementById('anu-btn-editar-cliente'); if(e) e.addEventListener('click',function(){
      if (_clienteAtivo) abrirFormPerfil(_clienteAtivo.id);
    });
    var b=document.getElementById('anu-btn-buscar-pages'); if(b) b.addEventListener('click',buscarPaginas);
  }

  function buscarPaginas() {
    var tokenKey = _val('anu-pf-token-key');
    var btn = document.getElementById('anu-btn-buscar-pages');
    var sel = document.getElementById('anu-pf-page-id');
    if (!tokenKey) { alert('Selecione o token primeiro.'); return; }
    if (btn) btn.textContent = 'Buscando...';
    var businessId = _val('anu-pf-business-id') || '';
    var qs = 'token_key=' + tokenKey + (businessId ? '&business_id=' + businessId : '');
    fetch('/api/anuncios/pages?' + qs)
      .then(function(r){ return r.json(); })
      .then(function(data){
        if (btn) btn.textContent = '🔍 Buscar Páginas';
        if (data.error) { alert('Erro: ' + data.error); return; }
        var pages = data.pages || [];
        if (!pages.length) { alert('Nenhuma página encontrada para esse token.'); return; }
        var current = sel ? sel.value : '';
        if (sel) {
          sel.innerHTML = '<option value="">— selecione —</option>';
          pages.forEach(function(p){
            var opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name + ' (' + p.id + ')';
            if (p.id === current) opt.selected = true;
            sel.appendChild(opt);
          });
        }
      })
      .catch(function(e){
        if (btn) btn.textContent = '🔍 Buscar Páginas';
        alert('Erro de rede: ' + e);
      });
  }

  function salvarPerfil() {
    var nome=_val('anu-pf-nome').trim(), account_id=_val('anu-pf-account-id').trim();
    var locStr=_val('anu-pf-localizacao').trim();
    if (!nome||!account_id||!locStr){ alert('Nome, Account ID e Localização são obrigatórios.'); return; }
    var loc,pub;
    try { loc=JSON.parse(locStr); } catch(e){ alert('Localização inválida — verifique o JSON.'); return; }
    var pubStr=_val('anu-pf-publico').trim();
    try { pub=pubStr?JSON.parse(pubStr):{};} catch(e){ alert('Público inválido — verifique o JSON.'); return; }

    var payload={
      nome:nome, agencia:_val('anu-pf-agencia'), account_id:account_id,
      token_key:_val('anu-pf-token-key'), page_id:_val('anu-pf-page-id'),
      business_id:_val('anu-pf-business-id'), link_url:_val('anu-pf-link-url'),
      whatsapp:_val('anu-pf-whatsapp'), segmento:_val('anu-pf-segmento'),
      campanha_tipo:_val('anu-pf-camp-tipo'),
      optimization_goal:_val('anu-pf-optimization-goal')||'LINK_CLICKS',
      pixel_id:_val('anu-pf-pixel-id')||null,
      orcamento_diario:parseFloat(_val('anu-pf-orcamento'))||null,
      localizacao_json:loc, publico_json:pub
    };
    var url=_modoPerfilId?'/api/anuncios/clientes/'+_modoPerfilId:'/api/anuncios/clientes';
    var method=_modoPerfilId?'PUT':'POST';

    fetch(url,{method:method,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){return r.json();})
      .then(function(data){
        if(data.error){alert('Erro: '+data.error);return;}
        var salvoId=_modoPerfilId||data.id;
        fetch('/api/anuncios/clientes')
          .then(function(r){return r.json();})
          .then(function(d){
            _clientes=d.clientes||[];
            _clienteAtivo=_clientes.find(function(c){return c.id===salvoId;})||null;
            renderSidebar();
            esconder('anu-perfil-form');
            if(_clienteAtivo) mostrarCriacao(); else mostrar('anu-empty');
          });
      })
      .catch(function(e){alert('Erro de rede: '+e);});
  }

  // ── Mostrar blocos de criação ───────────────────────
  function mostrarCriacao() {
    if (!_clienteAtivo) return;
    esconder('anu-empty'); esconder('anu-perfil-form'); mostrar('anu-criacao');
    _setText('anu-cliente-nome-display', _clienteAtivo.nome);
    _set('anu-camp-objetivo', _clienteAtivo.campanha_tipo||'MESSAGES');
    _set('anu-camp-orcamento', _clienteAtivo.orcamento_diario||'');
    atualizarRevisao();
  }

  // ── Campanha ────────────────────────────────────────
  function bindCampanhaEvents() {
    var btnNova=document.getElementById('anu-camp-nova-btn');
    var btnExist=document.getElementById('anu-camp-exist-btn');
    if(btnNova) btnNova.addEventListener('click',function(){
      btnNova.classList.add('active'); btnExist.classList.remove('active');
      mostrar('anu-camp-nova-form'); esconder('anu-camp-exist-form');
      atualizarStatusCampanha();
    });
    if(btnExist) btnExist.addEventListener('click',function(){
      btnExist.classList.add('active'); btnNova.classList.remove('active');
      esconder('anu-camp-nova-form'); mostrar('anu-camp-exist-form');
      if(_clienteAtivo) carregarCampanhasExistentes();
    });
    var btnCarregar=document.getElementById('anu-camp-carregar');
    if(btnCarregar) btnCarregar.addEventListener('click',carregarCampanhasExistentes);
    ['anu-camp-nome','anu-camp-orcamento'].forEach(function(id){
      var el=document.getElementById(id);
      if(el) el.addEventListener('input',function(){atualizarStatusCampanha();atualizarRevisao();});
    });
  }

  function carregarCampanhasExistentes() {
    if(!_clienteAtivo) return;
    var sel=document.getElementById('anu-camp-select');
    if(sel) sel.innerHTML='<option>Carregando...</option>';
    fetch('/api/anuncios/campanhas/'+_clienteAtivo.account_id+'?token_key='+_clienteAtivo.token_key)
      .then(function(r){return r.json();})
      .then(function(data){
        if(!sel) return;
        if(data.error){sel.innerHTML='<option>Erro: '+_esc(data.error)+'</option>';return;}
        sel.innerHTML=(data.campanhas||[]).map(function(c){
          return '<option value="'+_esc(c.id)+'">'+_esc(c.name)+' ('+_esc(c.objective)+')</option>';
        }).join('')||'<option value="">Nenhuma campanha ativa</option>';
        atualizarStatusCampanha(); atualizarRevisao();
      })
      .catch(function(){if(sel) sel.innerHTML='<option>Erro de rede</option>';});
  }

  function atualizarStatusCampanha() {
    var el=document.getElementById('anu-status-campanha'); if(!el) return;
    var modoNova=document.getElementById('anu-camp-nova-btn')&&
                 document.getElementById('anu-camp-nova-btn').classList.contains('active');
    var ok=false;
    if(modoNova){ok=!!_val('anu-camp-nome').trim()&&!!_val('anu-camp-orcamento');}
    else{var s=document.getElementById('anu-camp-select');ok=s&&s.value&&!s.value.startsWith('Carregando')&&!s.value.startsWith('Nenhuma');}
    el.textContent=ok?'✓ Configurada':'Pendente';
    el.className='anu-bloco-status'+(ok?' ok':'');
  }

  // ── Criativo ────────────────────────────────────────
  function bindCreativoEvents() {
    var dz=document.getElementById('anu-dropzone');
    var fi=document.getElementById('anu-file-input');
    if(!dz||!fi) return;
    dz.addEventListener('dragover',function(e){e.preventDefault();dz.classList.add('dragover');});
    dz.addEventListener('dragleave',function(){dz.classList.remove('dragover');});
    dz.addEventListener('drop',function(e){e.preventDefault();dz.classList.remove('dragover');var f=e.dataTransfer.files[0];if(f)processarArquivo(f);});
    fi.addEventListener('change',function(){if(this.files[0])processarArquivo(this.files[0]);});
  }

  function processarArquivo(file) {
    if(!_clienteAtivo){alert('Selecione um cliente primeiro.');return;}
    var preview=document.getElementById('anu-preview');
    var inner=document.getElementById('anu-dropzone-inner');
    if(preview){
      preview.innerHTML='';
      if(file.type.startsWith('video')){
        var vid=document.createElement('video');vid.src=URL.createObjectURL(file);vid.controls=true;preview.appendChild(vid);
      } else {
        var img=document.createElement('img');img.src=URL.createObjectURL(file);preview.appendChild(img);
      }
      preview.classList.remove('hidden');
      if(inner) inner.classList.add('hidden');
    }
    if(!file.type.startsWith('video')){
      var reader=new FileReader();
      reader.onload=function(e){var b64=e.target.result;_creativeB64=b64.split(',')[1];_creativeMime=file.type;};
      reader.readAsDataURL(file);
    } else {
      _creativeB64=null; _creativeMime='video/mp4';
    }
    subirCreativoMeta(file);
  }

  function subirCreativoMeta(file) {
    mostrar('anu-upload-progress');
    var fill=document.getElementById('anu-progress-fill');
    var msg=document.getElementById('anu-progress-msg');
    var stEl=document.getElementById('anu-status-criativo');
    if(fill) fill.style.width='30%';
    if(msg)  msg.textContent=file.type.startsWith('video')?'Enviando vídeo (~60s)...':'Enviando imagem...';
    if(stEl){stEl.textContent='Enviando...';stEl.className='anu-bloco-status';}

    var fd=new FormData();
    fd.append('arquivo',file);
    fd.append('account_id',_clienteAtivo.account_id);
    fd.append('token_key',_clienteAtivo.token_key);

    fetch('/api/anuncios/upload-criativo',{method:'POST',body:fd})
      .then(function(r){return r.json();})
      .then(function(data){
        esconder('anu-upload-progress');
        if(data.error){if(stEl){stEl.textContent='Erro';stEl.className='anu-bloco-status erro';}alert('Erro no upload: '+data.error);return;}
        _creativeRef=data;
        if(stEl){stEl.textContent='✓ Enviado';stEl.className='anu-bloco-status ok';}
        atualizarRevisao();
        gerarCopyIA();
      })
      .catch(function(e){esconder('anu-upload-progress');if(stEl){stEl.textContent='Erro';stEl.className='anu-bloco-status erro';}alert('Erro: '+e);});
  }

  // ── Copy IA ─────────────────────────────────────────
  function bindCopyEvents() {
    var r=document.getElementById('anu-copy-regerar'); if(r) r.addEventListener('click',gerarCopyIA);
    ['anu-copy-titulo','anu-copy-texto','anu-copy-cta'].forEach(function(id){
      var el=document.getElementById(id);
      if(el) el.addEventListener('input',function(){atualizarContadores();atualizarStatusCopy();atualizarRevisao();});
    });
  }

  function gerarCopyIA() {
    if(!_clienteAtivo) return;
    mostrar('anu-copy-loading');
    var stEl=document.getElementById('anu-status-copy');
    if(stEl){stEl.textContent='Gerando...';stEl.className='anu-bloco-status';}

    var payload={
      imagem_base64:_creativeB64||'', mime_type:_creativeMime||'image/jpeg',
      cliente_nome:_clienteAtivo.nome, campanha_tipo:_clienteAtivo.campanha_tipo||'MESSAGES',
      segmento:_clienteAtivo.segmento||''
    };

    fetch('/api/anuncios/copy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){return r.json();})
      .then(function(data){
        esconder('anu-copy-loading');
        if(data.error){if(stEl){stEl.textContent='Erro';stEl.className='anu-bloco-status erro';}alert('Erro: '+data.error);return;}
        _set('anu-copy-titulo',data.titulo||'');
        _set('anu-copy-texto',data.texto||'');
        _set('anu-copy-cta',data.cta||'SEND_MESSAGE');
        atualizarContadores(); atualizarStatusCopy();
        if(stEl){stEl.textContent='✓ Gerada';stEl.className='anu-bloco-status ok';}
        atualizarRevisao();
      })
      .catch(function(e){esconder('anu-copy-loading');alert('Erro: '+e);});
  }

  function atualizarContadores() {
    var t=_val('anu-copy-titulo'),x=_val('anu-copy-texto');
    _setText('anu-titulo-count',t.length+'/40');
    _setText('anu-texto-count',x.length+'/125');
  }

  function atualizarStatusCopy() {
    var el=document.getElementById('anu-status-copy'); if(!el) return;
    var ok=!!_val('anu-copy-titulo').trim()&&!!_val('anu-copy-texto').trim();
    el.textContent=ok?'✓ Pronta':'Pendente';
    el.className='anu-bloco-status'+(ok?' ok':'');
  }

  // ── Revisão ─────────────────────────────────────────
  function bindRevisaoEvents() {
    var bp=document.getElementById('anu-btn-publicar'); if(bp) bp.addEventListener('click',abrirModal);
  }

  function atualizarRevisao() {
    if(!_clienteAtivo) return;
    var grid=document.getElementById('anu-revisao-grid'); if(!grid) return;
    var loc=_clienteAtivo.localizacao_json||{};
    var temLoc=!!(loc.paises&&loc.paises.length||loc.cidades&&loc.cidades.length);
    var temPageId=!!(_clienteAtivo.page_id||'').trim();
    var locStr=temLoc?(loc.cidades&&loc.cidades.length?loc.cidades.length+' cidade(s)':(loc.paises||[]).join(', ')):'NÃO CONFIGURADA';
    var pub=_clienteAtivo.publico_json||{};
    var pubStr=pub.idade_min?(pub.idade_min+'–'+pub.idade_max+' anos'):'Padrão';
    var modoNova=document.getElementById('anu-camp-nova-btn')&&document.getElementById('anu-camp-nova-btn').classList.contains('active');
    var campNome=modoNova?(_val('anu-camp-nome')||'—'):(_val('anu-camp-select')||'—');

    var itens=[
      {label:'Conta Meta',    val:_clienteAtivo.account_id, ok:!!_clienteAtivo.account_id},
      {label:'Page ID',       val:_clienteAtivo.page_id||'—', ok:temPageId},
      {label:'Localização',   val:locStr, ok:temLoc},
      {label:'Público',       val:pubStr, ok:true},
      {label:'Orçamento',     val:_val('anu-camp-orcamento')?'R$ '+_val('anu-camp-orcamento')+'/dia':'—', ok:!!_val('anu-camp-orcamento')},
      {label:'Campanha',      val:campNome, ok:campNome!=='—'},
      {label:'Criativo',      val:_creativeRef?'✓ Enviado':'—', ok:!!_creativeRef},
      {label:'Título',        val:_val('anu-copy-titulo')||'—', ok:!!_val('anu-copy-titulo').trim()},
    ];

    grid.innerHTML=itens.map(function(item){
      var cls=item.ok?'anu-revisao-ok':'anu-revisao-erro';
      return '<div class="anu-revisao-item"><span class="anu-revisao-label">'+_esc(item.label)+'</span><span class="anu-revisao-val '+cls+'">'+_esc(String(item.val))+'</span></div>';
    }).join('');

    var alertaEl=document.getElementById('anu-localizacao-alerta');
    if(alertaEl) alertaEl.classList.toggle('hidden',temLoc&&temPageId);

    var tudo_ok=itens.every(function(i){return i.ok;});
    var bp=document.getElementById('anu-btn-publicar');
    if(bp) bp.disabled=!tudo_ok;
  }

  // ── Modal e publicação ──────────────────────────────
  function bindModalEvents() {
    var bc=document.getElementById('anu-modal-cancelar');   if(bc) bc.addEventListener('click',fecharModal);
    var bf=document.getElementById('anu-modal-confirmar');  if(bf) bf.addEventListener('click',publicarAnuncio);
    var ov=document.getElementById('anu-modal-overlay');
    if(ov) ov.addEventListener('click',function(e){if(e.target===ov)fecharModal();});
  }

  function abrirModal() {
    if(!_clienteAtivo) return;
    var resumo=document.getElementById('anu-modal-resumo');
    var modoNova=document.getElementById('anu-camp-nova-btn')&&document.getElementById('anu-camp-nova-btn').classList.contains('active');
    if(resumo) resumo.innerHTML=[
      '<strong>Cliente:</strong> '+_esc(_clienteAtivo.nome),
      '<strong>Conta:</strong> '+_esc(_clienteAtivo.account_id),
      '<strong>Page ID:</strong> '+_esc(_clienteAtivo.page_id||'—'),
      '<strong>Campanha:</strong> '+_esc(modoNova?(_val('anu-camp-nome')||'—'):'Existente: '+_val('anu-camp-select')),
      '<strong>Orçamento:</strong> R$ '+(_val('anu-camp-orcamento')||'—')+'/dia',
      '<strong>Título:</strong> '+_esc(_val('anu-copy-titulo')),
      '<strong>CTA:</strong> '+_esc(_val('anu-copy-cta')),
      '<strong>Criativo:</strong> '+(_creativeRef?(_creativeRef.tipo==='video'?'Vídeo':'Imagem')+' ✓':'—'),
    ].join('<br>');
    mostrar('anu-modal-overlay');
  }

  function fecharModal() {
    esconder('anu-modal-overlay');
    var bc=document.getElementById('anu-modal-confirmar');
    if(bc){bc.textContent='Confirmar e Criar';bc.classList.remove('loading');}
  }

  function publicarAnuncio() {
    if(!_clienteAtivo||!_creativeRef) return;
    var bc=document.getElementById('anu-modal-confirmar');
    if(bc){bc.textContent='Publicando...';bc.classList.add('loading');}

    var modoNova=document.getElementById('anu-camp-nova-btn')&&document.getElementById('anu-camp-nova-btn').classList.contains('active');
    var payload={
      cliente_id:_clienteAtivo.id,
      campanha_existente_id:modoNova?null:(_val('anu-camp-select')||null),
      campanha_nome:_val('anu-camp-nome')||('Campanha '+_clienteAtivo.nome),
      orcamento_diario:parseFloat(_val('anu-camp-orcamento'))||30,
      creative_ref:_creativeRef,
      copy:{titulo:_val('anu-copy-titulo'),texto:_val('anu-copy-texto'),cta:_val('anu-copy-cta')||'SEND_MESSAGE'},
      audience_id: parseInt(_val('anu-pub-selector')) || null
    };

    fetch('/api/anuncios/publicar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){return r.json();})
      .then(function(data){
        fecharModal();
        if(data.error){alert('✕ Erro: '+data.error);return;}
        alert('✓ Anúncio criado!\n\nCampaign ID: '+data.campaign_id+'\nAd Set ID: '+data.adset_id+'\nAd ID: '+data.ad_id+'\n\n'+data.msg);
        _creativeRef=null; _creativeB64=null;
        mostrarCriacao();
      })
      .catch(function(e){fecharModal();alert('Erro de rede: '+e);});
  }

  // ── Públicos Salvos ─────────────────────────────────
  function carregarPublicos() {
    var accountId = _clienteAtivo ? _clienteAtivo.account_id : '';
    var url = '/api/anuncios/audiences' + (accountId ? '?account_id=' + accountId : '');
    fetch(url).then(function(r){return r.json();}).then(function(d){
      _publicos = d.audiences || [];
      renderPublicos();
      popularSeletorPublico();
    });
  }

  function renderPublicos() {
    var el = document.getElementById('anu-publicos-lista');
    if (!el) return;
    if (!_publicos.length) {
      el.innerHTML = '<div style="color:#888;font-size:13px;padding:12px 0">Nenhum público salvo. Importe do Meta ou crie manualmente.</div>';
      return;
    }
    var badge = {'manual':'Manual','salvo_meta':'Meta Salvo','custom_meta':'Custom'};
    el.innerHTML = _publicos.map(function(p){
      var editBtn = p.tipo !== 'custom_meta'
        ? '<button class="anu-btn-secondary" style="padding:2px 10px;font-size:12px" onclick="abrirEditPublico('+p.id+')">Editar</button>'
        : '<button class="anu-btn-secondary" style="padding:2px 10px;font-size:12px" onclick="abrirEditPublicoNome('+p.id+')">Renomear</button>';
      return '<div class="anu-bloco" style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;margin-bottom:6px">'
        + '<div><strong>'+_esc(p.nome)+'</strong><span style="font-size:11px;color:#888;margin-left:8px">['+badge[p.tipo]+']</span></div>'
        + '<div style="display:flex;gap:6px;">'+editBtn
        + '<button class="anu-btn-secondary" style="padding:2px 10px;font-size:12px;color:#e55" onclick="deletarPublico('+p.id+')">✕</button>'
        + '</div></div>';
    }).join('');
  }

  window.abrirEditPublico = function(id) {
    var p = _publicos.find(function(x){return x.id===id;});
    if (!p) return;
    _pubEditId = id;
    _set('anu-pub-nome', p.nome);
    _set('anu-pub-age-min', (p.targeting_json||{}).age_min||18);
    _set('anu-pub-age-max', (p.targeting_json||{}).age_max||65);
    _set('anu-pub-genero', ((p.targeting_json||{}).genders||[])[0]||'');
    _set('anu-pub-pais', ((p.targeting_json||{}).countries||[])[0]||'BR');
    _setText('anu-publico-form-titulo','Editar Público');
    mostrar('anu-publico-form');
  };

  window.abrirEditPublicoNome = function(id) {
    var p = _publicos.find(function(x){return x.id===id;});
    if (!p) return;
    _pubEditId = id;
    _set('anu-pub-nome', p.nome);
    _setText('anu-publico-form-titulo','Renomear Público');
    mostrar('anu-publico-form');
  };

  window.deletarPublico = function(id) {
    if (!confirm('Deletar este público?')) return;
    fetch('/api/anuncios/audiences/'+id,{method:'DELETE'})
      .then(function(r){return r.json();})
      .then(function(d){ if(d.ok) carregarPublicos(); else alert('Erro: '+d.error); });
  };

  function popularClientesDropdowns() {
    ['anu-pub-cliente','anu-imp-cliente'].forEach(function(selId){
      var sel = document.getElementById(selId);
      if (!sel) return;
      sel.innerHTML = '<option value="">— selecione —</option>';
      _clientes.forEach(function(c){
        var opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = c.nome + ' (' + c.account_id + ')';
        opt.dataset.accountId = c.account_id;
        opt.dataset.tokenKey  = c.token_key;
        sel.appendChild(opt);
      });
    });
  }

  function popularSeletorPublico() {
    var sel = document.getElementById('anu-pub-selector');
    if (!sel) return;
    sel.innerHTML = '<option value="">Usar perfil do cliente</option>';
    _publicos.forEach(function(p){
      var opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.nome;
      sel.appendChild(opt);
    });
  }

  function bindPublicosEvents() {
    var btnNovo = document.getElementById('anu-btn-novo-publico');
    if (btnNovo) btnNovo.addEventListener('click', function(){
      _pubEditId = null;
      _set('anu-pub-nome',''); _set('anu-pub-age-min','18'); _set('anu-pub-age-max','65');
      _set('anu-pub-genero',''); _set('anu-pub-pais','BR');
      _setText('anu-publico-form-titulo','Novo Público');
      popularClientesDropdowns();
      mostrar('anu-publico-form');
      esconder('anu-modal-importar');
    });

    var btnSalvar = document.getElementById('anu-pub-salvar');
    if (btnSalvar) btnSalvar.addEventListener('click', function(){
      var nome = _val('anu-pub-nome').trim();
      if (!nome) { alert('Nome obrigatório'); return; }
      var generoVal = _val('anu-pub-genero');
      var targeting = {
        age_min: parseInt(_val('anu-pub-age-min'))||18,
        age_max: parseInt(_val('anu-pub-age-max'))||65,
        genders: generoVal ? [parseInt(generoVal)] : [],
        countries: [(_val('anu-pub-pais').trim()||'BR')]
      };
      if (_pubEditId) {
        var payload = {nome: nome, targeting_json: targeting};
        fetch('/api/anuncios/audiences/'+_pubEditId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
          .then(function(r){return r.json();})
          .then(function(d){ if(d.ok){esconder('anu-publico-form');carregarPublicos();}else alert('Erro: '+d.error); });
      } else {
        var sel = document.getElementById('anu-pub-cliente');
        var opt = sel ? sel.options[sel.selectedIndex] : null;
        if (!opt||!opt.dataset.accountId) { alert('Selecione um cliente'); return; }
        fetch('/api/anuncios/audiences',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
          nome:nome, account_id:opt.dataset.accountId, token_key:opt.dataset.tokenKey,
          tipo:'manual', targeting_json:targeting
        })}).then(function(r){return r.json();})
          .then(function(d){ if(d.ok){esconder('anu-publico-form');carregarPublicos();}else alert('Erro: '+d.error); });
      }
    });

    var btnCancelar = document.getElementById('anu-pub-cancelar');
    if (btnCancelar) btnCancelar.addEventListener('click', function(){ esconder('anu-publico-form'); });

    var btnImportar = document.getElementById('anu-btn-importar-meta');
    if (btnImportar) btnImportar.addEventListener('click', function(){
      popularClientesDropdowns();
      _set('anu-imp-resultado','');
      mostrar('anu-modal-importar');
      esconder('anu-publico-form');
    });

    var btnImpConf = document.getElementById('anu-imp-confirmar');
    if (btnImpConf) btnImpConf.addEventListener('click', function(){
      var sel = document.getElementById('anu-imp-cliente');
      var opt = sel ? sel.options[sel.selectedIndex] : null;
      if (!opt||!opt.dataset.accountId) { alert('Selecione um cliente'); return; }
      btnImpConf.textContent = 'Importando...';
      fetch('/api/anuncios/audiences/importar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        account_id:opt.dataset.accountId, token_key:opt.dataset.tokenKey
      })}).then(function(r){return r.json();})
        .then(function(d){
          btnImpConf.textContent = 'Importar';
          var res = document.getElementById('anu-imp-resultado');
          if (d.ok) {
            if (res) res.textContent = 'Importados: '+d.importados+' | Atualizados: '+d.atualizados+(d.erros.length?' | Erros: '+d.erros.join('; '):'');
            carregarPublicos();
          } else { alert('Erro: '+d.error); }
        });
    });

    var btnImpCanc = document.getElementById('anu-imp-cancelar');
    if (btnImpCanc) btnImpCanc.addEventListener('click', function(){ esconder('anu-modal-importar'); });
  }

  // ── Utilitários ─────────────────────────────────────
  function _val(id){var el=document.getElementById(id);return el?el.value:'';}
  function _set(id,v){var el=document.getElementById(id);if(el)el.value=v||'';}
  function _setText(id,t){var el=document.getElementById(id);if(el)el.textContent=t||'';}
  function _esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function mostrar(id){var el=document.getElementById(id);if(el)el.classList.remove('hidden');}
  function esconder(id){var el=document.getElementById(id);if(el)el.classList.add('hidden');}

  // ── Observer ────────────────────────────────────────
  var _iniciado=false;
  var _obs=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.target.id==='page-anuncios'&&m.target.classList.contains('active')){
        if(!_iniciado){_iniciado=true;init();}
      }
    });
  });
  var pageAnu=document.getElementById('page-anuncios');
  if(pageAnu){
    _obs.observe(pageAnu,{attributes:true,attributeFilter:['class']});
    if(pageAnu.classList.contains('active')){_iniciado=true;init();}
  }

})();
