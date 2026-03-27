(function() {
  var DURATION_MS = 24 * 60 * 60 * 1000; // 24 horas
  var end = Date.now() + DURATION_MS;

  function pad(n) { return String(n).padStart(2, '0'); }

  function tick() {
    var diff = end - Date.now();
    if (diff <= 0) {
      document.getElementById('cd-hours').textContent = '00';
      document.getElementById('cd-minutes').textContent = '00';
      document.getElementById('cd-seconds').textContent = '00';
      return;
    }
    var h = Math.floor(diff / 3600000);
    var m = Math.floor((diff % 3600000) / 60000);
    var s = Math.floor((diff % 60000) / 1000);
    document.getElementById('cd-hours').textContent = pad(h);
    document.getElementById('cd-minutes').textContent = pad(m);
    document.getElementById('cd-seconds').textContent = pad(s);
  }

  tick();
  setInterval(tick, 1000);
})();
