(function () {
  const timeEl = document.getElementById("time");
  const dateEl = document.getElementById("date");
  const tempEl = document.getElementById("temp");
  const humidityEl = document.getElementById("humidity");
  const greetingEl = document.getElementById("greeting");
  const greetingEmojiEl = document.getElementById("greeting-emoji");

  function updateTime() {
    fetch("/api/now")
      .then((r) => r.json())
      .then((data) => {
        if (timeEl) timeEl.textContent = data.time; // já vem HH:MM do backend
        if (dateEl) dateEl.textContent = (data.weekday || "") + " · " + data.date;
      })
      .catch(() => {
        const now = new Date();
        if (timeEl) timeEl.textContent = now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", hour12: false });
        if (dateEl) dateEl.textContent = now.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" });
      });
  }

  function updateWeather() {
    fetch("/api/weather")
      .then((r) => r.json())
      .then((data) => {
        if (tempEl) tempEl.textContent = data.temp != null ? data.temp + " °C" : "— °C";
        if (humidityEl) humidityEl.textContent = data.humidity != null ? "Umidade: " + data.humidity + "%" : "—";
      })
      .catch(() => {
        if (tempEl) tempEl.textContent = "— °C";
        if (humidityEl) humidityEl.textContent = "—";
      });
  }

  function updateGreeting() {
    const h = new Date().getHours();
    let text, emoji;
    if (h < 12) {
      text = "Bom dia, patrão";
      emoji = "☀️";
    } else if (h < 18) {
      text = "Boa tarde, patrão";
      emoji = "🌤️";
    } else {
      text = "Boa noite, patrão";
      emoji = "🌙";
    }
    if (greetingEl) greetingEl.textContent = text;
    if (greetingEmojiEl) greetingEmojiEl.textContent = emoji;
  }

  updateTime();
  updateWeather();
  updateGreeting();
  setInterval(updateTime, 30000);
  setInterval(updateWeather, 60000);
  setInterval(updateGreeting, 60000);
})();
