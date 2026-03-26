(function () {
  const btnActivate = document.getElementById("btn-activate");
  const voiceStatus = document.getElementById("voice-status");
  const voiceResponse = document.getElementById("voice-response");
  const sphereWrap = document.getElementById("sphere-wrap");

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    if (voiceStatus) voiceStatus.textContent = "Navegador não suporta voz. Use Chrome.";
    if (btnActivate) btnActivate.remove();
    return;
  }

  let recognition = null;
  let isProcessing = false;
  let voiceRafId = null;
  let audioCtx = null;
  const MIN_TRANSCRIPT_LEN = 2;

  function setStatus(text) {
    if (voiceStatus) voiceStatus.textContent = text || "";
  }

  function setResponse(text) {
    if (!voiceResponse) return;
    voiceResponse.textContent = text || "";
  }

  function setVoiceLevel(value) {
    if (!sphereWrap) return;
    sphereWrap.style.setProperty("--voice-level", String(Math.max(0, Math.min(1, value))));
  }

  function stopVoiceVisualizer() {
    if (voiceRafId != null) {
      cancelAnimationFrame(voiceRafId);
      voiceRafId = null;
    }
    if (sphereWrap) {
      sphereWrap.classList.remove("voice-active");
      setVoiceLevel(0);
    }
  }

  function startVoiceVisualizer(audioElement) {
    if (!sphereWrap || !audioElement) return;
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === "suspended") audioCtx.resume();
      const source = audioCtx.createMediaElementSource(audioElement);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.7;
      source.connect(analyser);
      analyser.connect(audioCtx.destination);
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      sphereWrap.classList.add("voice-active");
      function update() {
        if (!sphereWrap.classList.contains("voice-active")) return;
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const level = (sum / dataArray.length) / 255;
        setVoiceLevel(level * 1.2);
        voiceRafId = requestAnimationFrame(update);
      }
      voiceRafId = requestAnimationFrame(update);
    } catch (e) {
      sphereWrap.classList.add("voice-active");
    }
  }

  function sendText(text) {
    const t = (text || "").trim();
    if (t.length < MIN_TRANSCRIPT_LEN) return;
    if (isProcessing) return;
    isProcessing = true;
    if (recognition) try { recognition.abort(); } catch (e) {}
    setStatus("Processando...");

    fetch("/api/falar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: t }),
    })
      .then(function (res) {
        if (!res.ok) return res.json().then(function (d) { throw new Error(d.error || res.statusText); });
        return res.json();
      })
      .then(function (data) {
        setStatus("");
        setResponse("");
        if (data.audio) {
          const binary = atob(data.audio);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
          const audioBlob = new Blob([bytes], { type: "audio/mpeg" });
          const url = URL.createObjectURL(audioBlob);
          const audio = new Audio(url);
          audio.onended = function () {
            stopVoiceVisualizer();
            URL.revokeObjectURL(url);
            isProcessing = false;
            startListening();
          };
          audio.onerror = function () {
            stopVoiceVisualizer();
            URL.revokeObjectURL(url);
            isProcessing = false;
            startListening();
          };
          audio.play();
          startVoiceVisualizer(audio);
        } else {
          isProcessing = false;
          startListening();
        }
      })
      .catch(function (err) {
        setStatus("Erro: " + (err.message || "tente de novo."));
        isProcessing = false;
        startListening();
      });
  }

  function startListening() {
    if (!recognition || isProcessing) return;
    try {
      recognition.start();
      setStatus("Ouvindo...");
    } catch (e) {}
  }

  function initRecognition() {
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "pt-BR";
    recognition.onresult = function (e) {
      if (isProcessing) return;
      var last = e.results.length - 1;
      var result = e.results[last];
      var transcript = (result[0] && result[0].transcript) ? result[0].transcript.trim() : "";
      if (result.isFinal && transcript.length >= MIN_TRANSCRIPT_LEN) {
        sendText(transcript);
      }
    };
    recognition.onend = function () {
      if (!isProcessing && recognition) try { recognition.start(); } catch (e) {}
    };
    recognition.onerror = function (e) {
      if (e.error === "not-allowed") setStatus("Microfone negado. Atualize a página e permita.");
      else if (e.error !== "aborted") setStatus("");
    };
  }

  function activate() {
    if (!btnActivate) return;
    btnActivate.classList.add("hidden");
    setStatus("Ativando...");
    initRecognition();
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function () {
        startListening();
      })
      .catch(function () {
        setStatus("Permita o microfone e atualize a página.");
      });
  }

  if (btnActivate) btnActivate.addEventListener("click", activate);
})();
