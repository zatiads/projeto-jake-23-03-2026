(function () {
  // ── SPA Router ──────────────────────────────────────────────────────────
  function showPage(id) {
    document.querySelectorAll(".page").forEach(function (p) {
      p.classList.toggle("active", p.id === "page-" + id);
    });
    document.querySelectorAll(".nav-item").forEach(function (n) {
      n.classList.toggle("active", n.dataset.page === id);
    });
    history.replaceState(null, "", "#" + id);
    if (id === "nutricao" && typeof window.initNutricao === "function") {
      window.initNutricao();
    }
    if (id === "social-brief" && typeof window.initSocialBrief === "function") {
      window.initSocialBrief();
    }
    if (id === "dr" && typeof window.initDR === "function") {
      window.initDR();
    }
    if (id === "gestor" && typeof window.gestorInit === "function") {
      window.gestorInit();
    }
    if (id === "planejador" && typeof window.planejadorInit === "function") {
      window.planejadorInit();
    }
  }

  document.querySelectorAll(".nav-item").forEach(function (item) {
    item.addEventListener("click", function (e) {
      e.preventDefault();
      showPage(this.dataset.page);
    });
  });

  // Carrega a página correta se houver hash na URL
  var hash = location.hash.replace("#", "");
  var valid = ["painel","architect","performance","anuncios","gestor","planejador","copys","criativos","relatorios","carrossel","prompts","financeiro","agenda","rotina","social-brief","nutricao","dr"];
  if (hash && valid.indexOf(hash) !== -1) showPage(hash);
  else showPage("painel");

  window.showPage = showPage;
})();
