/*
 * Jake em tempo real (OpenAI Realtime por WebRTC) — o mesmo esquema do modo voz do ChatGPT.
 * Tocou na bolinha: conecta, ouve, responde falando e chama as ferramentas (rota, música, Meta, agenda, internet).
 * Fica escutando a continuação da conversa e desliga sozinho depois de um tempo em silêncio.
 * Se não conseguir conectar, devolve false e o cockpit usa o esquema antigo (gravar → servidor → voz).
 */
window.JakeTempoReal = (function () {
  const OCIOSO_MS = 25000;          // desliga depois de 25 s sem ninguém falar

  let ui = null;                    // { estado(nome, frase), nivel(v), token(), nativo, destino(nome) }
  let pc = null, canal = null, mic = null, saida = null, ocioso = null;
  let analisarMic = null, analisarVoz = null, falando = false, textoResposta = '';
  let pendentes = [];               // ações que abrem outro app: só depois do Jake terminar de falar

  function marcarAtividade() {
    clearTimeout(ocioso);
    ocioso = setTimeout(encerrar, OCIOSO_MS);
  }

  function analisador(stream) {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const an = ctx.createAnalyser(); an.fftSize = 256;
      ctx.createMediaStreamSource(stream).connect(an);
      const buf = new Uint8Array(an.frequencyBinCount);
      return () => { an.getByteTimeDomainData(buf); let m = 0; for (const v of buf) m = Math.max(m, Math.abs(v - 128)); return m / 128; };
    } catch (e) { return () => 0; }
  }

  function laçoNivel() {
    if (!pc) return;
    const v = falando ? (analisarVoz ? analisarVoz() : 0) : (analisarMic ? analisarMic() : 0);
    ui.nivel(v * 1.6);
    requestAnimationFrame(laçoNivel);
  }

  function enviar(evento) {
    if (canal && canal.readyState === 'open') canal.send(JSON.stringify(evento));
  }

  async function ferramentaServidor(nome, args) {
    const r = await fetch('/carro/realtime/ferramenta', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + ui.token() },
      body: JSON.stringify({ nome, args }) });
    return (await r.json()).saida;
  }

  async function executar(item) {
    let args = {};
    try { args = JSON.parse(item.arguments || '{}'); } catch (e) {}
    let resultado = 'ok';
    try {
      if (item.name === 'navegar') {
        pendentes.push({ acao: 'navegar', parametros: { destino: args.destino, app: args.app || 'maps' } });
        ui.destino(args.destino);
        resultado = 'Rota pronta, o Maps vai abrir assim que você terminar de falar.';
      } else if (item.name === 'controlar_midia') {
        ui.nativo && ui.nativo.acao(JSON.stringify({ acao: 'midia', parametros: { comando: args.comando } }));
      } else if (item.name === 'tocar_musica') {
        const uri = await ferramentaServidor('tocar_musica', args);
        pendentes.push({ acao: 'tocar_musica', parametros: { busca: args.busca, tipo: args.tipo, uri: uri || '' } });
        resultado = uri ? 'Achei no Spotify, vai começar a tocar.' : 'Vou pedir pro Spotify buscar e tocar.';
      } else {
        ui.estado('pensando', 'Buscando…');
        resultado = await ferramentaServidor(item.name, args);
      }
    } catch (e) {
      resultado = 'Não consegui fazer isso agora.';
    }
    enviar({ type: 'conversation.item.create', item: { type: 'function_call_output', call_id: item.call_id, output: String(resultado) } });
  }

  function rodarPendentes() {
    if (!pendentes.length || !ui.nativo) return;
    const lista = pendentes; pendentes = [];
    lista.forEach((p) => ui.nativo.acao(JSON.stringify(p)));
    ui.estado('feito', textoResposta || 'Feito.');
  }

  const depurar = new URLSearchParams(location.search).get('depurar');

  async function aoEvento(e) {
    if (depurar) console.log('RT', Math.round(performance.now()), e.type, JSON.stringify(e).slice(0, 300));
    marcarAtividade();
    switch (e.type) {
      case 'input_audio_buffer.speech_started':
        falando = false; ui.estado('ouvindo', ''); break;
      case 'input_audio_buffer.speech_stopped':
        ui.estado('pensando'); break;
      case 'conversation.item.input_audio_transcription.completed':
        if (e.transcript) ui.estado('pensando', '“' + e.transcript.trim() + '”'); break;
      case 'response.created':
        textoResposta = ''; break;
      case 'response.output_audio_transcript.delta':
      case 'response.audio_transcript.delta':
        textoResposta += e.delta || ''; ui.estado('falando', textoResposta); break;
      case 'output_audio_buffer.started':
        falando = true; ui.estado('falando', textoResposta); break;
      case 'output_audio_buffer.stopped':
        falando = false;
        if (pendentes.length) setTimeout(rodarPendentes, 250);
        else ui.estado('ouvindo', textoResposta);
        break;
      case 'response.done': {
        const chamadas = ((e.response && e.response.output) || []).filter((i) => i.type === 'function_call');
        if (chamadas.length) {
          await Promise.all(chamadas.map(executar));
          // ações do carro (rota, música, mídia): ele já falou antes de chamar, então não fala de novo.
          // Consultas (Meta, agenda, internet): precisa responder com o resultado.
          if (chamadas.some((c) => !['navegar', 'controlar_midia', 'tocar_musica'].includes(c.name))) {
            enviar({ type: 'response.create' });
          } else if (!falando) setTimeout(rodarPendentes, 300);
        } else if (pendentes.length && !falando) {
          setTimeout(rodarPendentes, 400);
        }
        break;
      }
      case 'error':
        console.warn('realtime', e.error); break;
    }
  }

  async function conectar() {
    const r = await fetch('/carro/realtime/sessao', { method: 'POST', headers: { Authorization: 'Bearer ' + ui.token() } });
    if (!r.ok) throw new Error('sessão ' + r.status);
    const { chave, modelo } = await r.json();

    mic = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    pc = new RTCPeerConnection();
    saida = document.createElement('audio'); saida.autoplay = true;
    pc.ontrack = (ev) => { saida.srcObject = ev.streams[0]; analisarVoz = analisador(ev.streams[0]); };
    mic.getTracks().forEach((t) => pc.addTrack(t, mic));
    analisarMic = analisador(mic);
    canal = pc.createDataChannel('oai-events');
    canal.onmessage = (m) => { try { aoEvento(JSON.parse(m.data)); } catch (err) {} };
    const aberto = new Promise((ok, falha) => { canal.onopen = ok; setTimeout(() => falha(new Error('canal')), 8000); });

    const oferta = await pc.createOffer();
    await pc.setLocalDescription(oferta);
    const resp = await fetch(`https://api.openai.com/v1/realtime/calls?model=${encodeURIComponent(modelo)}`, {
      method: 'POST', body: oferta.sdp, headers: { Authorization: 'Bearer ' + chave, 'Content-Type': 'application/sdp' } });
    if (!resp.ok) throw new Error('sdp ' + resp.status);
    await pc.setRemoteDescription({ type: 'answer', sdp: await resp.text() });
    await aberto;
  }

  function encerrar() {
    clearTimeout(ocioso);
    rodarPendentes();
    try { mic && mic.getTracks().forEach((t) => t.stop()); } catch (e) {}
    try { canal && canal.close(); } catch (e) {}
    try { pc && pc.close(); } catch (e) {}
    pc = canal = mic = null; analisarMic = analisarVoz = null; falando = false;
    if (ui) { ui.nativo && ui.nativo.foco && ui.nativo.foco(false); ui.estado('pronto', 'Toque em mim ou diga “Jake”.'); }
  }

  /** Começa (ou continua) a conversa. Devolve false se não deu pra usar o tempo real. */
  async function conversar(opcoes) {
    ui = opcoes;
    if (pc) { ui.estado('ouvindo', 'Pode falar, patrão.'); marcarAtividade(); return true; }
    try {
      ui.estado('pensando', 'Conectando…');
      ui.nativo && ui.nativo.foco && ui.nativo.foco(true);
      await conectar();
      ui.estado('ouvindo', 'Pode falar, patrão.');
      marcarAtividade();
      requestAnimationFrame(laçoNivel);
      return true;
    } catch (e) {
      console.warn('tempo real indisponível', e);
      encerrar();
      return false;
    }
  }

  return { conversar, encerrar, ativo: () => !!pc };
})();
