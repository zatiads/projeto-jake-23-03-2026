(function () {
  // ── SPA Router ──────────────────────────────────────────────────────────
  function showPage(id) {
    document.querySelectorAll(".page").forEach(function (p) {
      p.classList.toggle("active", p.id === "page-" + id);
    });
    document.querySelectorAll(".nav-item").forEach(function (n) {
      n.classList.toggle("active", n.dataset.page === id);
    });
    // Persiste no hash sem recarregar
    history.replaceState(null, "", "#" + id);
  }

  document.querySelectorAll(".nav-item").forEach(function (item) {
    item.addEventListener("click", function (e) {
      e.preventDefault();
      showPage(this.dataset.page);
    });
  });

  // Carrega a página correta se houver hash na URL
  var hash = location.hash.replace("#", "");
  var valid = ["painel","architect","performance","anuncios","copys","criativos","relatorios","carrossel","prompts","financeiro","agenda"];
  if (hash && valid.indexOf(hash) !== -1) showPage(hash);
  else showPage("painel");
})();
