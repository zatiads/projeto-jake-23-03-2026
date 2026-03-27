(function() {
  var DURATION_MS = 24 * 60 * 60 * 1000; // 24 horas
  var end = Date.now() + DURATION_MS;

  var elH = document.getElementById('cd-hours');
  var elM = document.getElementById('cd-minutes');
  var elS = document.getElementById('cd-seconds');

  if (!elH) return; // elementos do countdown ausentes, abortar

  function pad(n) { return String(n).padStart(2, '0'); }

  var timer = setInterval(tick, 1000);

  function tick() {
    var diff = end - Date.now();
    if (diff <= 0) {
      elH.textContent = '00';
      elM.textContent = '00';
      elS.textContent = '00';
      clearInterval(timer);
      return;
    }
    var h = Math.floor(diff / 3600000);
    var m = Math.floor((diff % 3600000) / 60000);
    var s = Math.floor((diff % 60000) / 1000);
    elH.textContent = pad(h);
    elM.textContent = pad(m);
    elS.textContent = pad(s);
  }

  tick();
})();

(function() {
  var stickyBar = document.getElementById('sticky-bar');
  var hero = document.getElementById('hero');

  function onScroll() {
    if (window.innerWidth >= 768) return; // só mobile
    var heroBottom = hero.getBoundingClientRect().bottom;
    stickyBar.style.display = heroBottom < 0 ? 'flex' : 'none';
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();
