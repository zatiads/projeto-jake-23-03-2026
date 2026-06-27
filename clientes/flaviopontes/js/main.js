/* ── Header scroll ── */
var header = document.getElementById('header');
window.addEventListener('scroll', function () {
  header.classList.toggle('scrolled', window.scrollY > 50);
}, { passive: true });

/* ── Mobile menu ── */
document.getElementById('menuToggle').addEventListener('click', function () { document.getElementById('mobileNav').classList.add('open'); });
document.getElementById('mobileNavClose').addEventListener('click', function () { document.getElementById('mobileNav').classList.remove('open'); });
document.querySelectorAll('.mobile-nav a').forEach(function (a) { a.addEventListener('click', function () { document.getElementById('mobileNav').classList.remove('open'); }); });

/* ── Parallax Hero ── */
var heroWrap = document.getElementById('heroImgWrap');
window.addEventListener('scroll', function () {
  if (heroWrap) heroWrap.style.transform = 'translateY(' + (window.scrollY * 0.28) + 'px)';
}, { passive: true });

/* ── Scroll reveal ── */
var observer = new IntersectionObserver(function (entries) {
  entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); observer.unobserve(e.target); } });
}, { threshold: 0.12 });
document.querySelectorAll('[data-anim]').forEach(function (el) { observer.observe(el); });

/* ── Contador hero ── */
function animCounter(el) {
  var target = parseInt(el.dataset.counter, 10);
  var suffix = el.dataset.suffix || '';
  var duration = 1800, step = target / (duration / 16), cur = 0;
  var t = setInterval(function () {
    cur = Math.min(cur + step, target);
    el.textContent = Math.floor(cur) + suffix;
    if (cur >= target) clearInterval(t);
  }, 16);
}
var counterDone = false;
var heroObs = new IntersectionObserver(function (entries) {
  if (!counterDone && entries[0].isIntersecting) {
    counterDone = true;
    document.querySelectorAll('[data-counter]').forEach(animCounter);
    heroObs.disconnect();
  }
});
heroObs.observe(document.querySelector('.hero-stats'));

/* ── Ticker ── */
var DESTS = ['São Tomé das Letras','Ibitipoca','Pedra da Gávea','Serra dos Órgãos','Pico dos Marins','Itatiaia','Escalavrado','Agulhas Negras','Pico do Papagaio','Praias Selvagens','Pedra do Baú','PETAR','Travessia Serra Negra','Pão de Açúcar'];
var track = document.getElementById('tickerTrack');
var html = '';
for (var t2 = 0; t2 < 2; t2++) {
  DESTS.forEach(function (d) { html += '<span class="ticker-item">' + d + '<span class="ticker-dot">◆</span></span>'; });
}
track.innerHTML = html;

/* ── Agenda ── */
var WA = '5535988572800';
var WA_SVG = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>';

/* ─────────────────────────────────────────────────────────────
   EVENTOS 2026 — Programação 2º Semestre
   Para adicionar fotos: preencha o array "fotos" com caminhos relativos.
   Exemplo: fotos: ['img/foto1.jpg', 'img/foto2.jpg']
───────────────────────────────────────────────────────────── */
var EVENTOS = [
  { mes:'Junho',    ano:2026, data:'20/06',      nome:'Mirante do Inferno — PARNASO',                       local:'Teresópolis · RJ',                tipo:'Bate e volta',               transporte:'Van Executiva Luxo',    vagas:'3 vagas disponíveis',  esgotado:false, guias:'Guia Leo Silva + Prof. Flávio Pontes',          fotos:['img/mirante_1.jpg','img/mirante_2.jpg','img/mirante_3.jpg','img/mirante_4.jpg','img/mirante_5.jpg'], saidaPocos:false },
  { mes:'Julho',    ano:2026, data:'04 e 05/07', nome:'Costão do Pão de Açúcar',                            local:'Rio de Janeiro · RJ',             tipo:'1 pernoite em Hotel',         transporte:'Van Executiva Luxo',    vagas:'Esgotado',             esgotado:true,  guias:'Guia Ana Paula + Prof. Flávio Pontes',          fotos:[], saidaPocos:false },
  { mes:'Julho',    ano:2026, data:'12/07',      nome:'Serra da Tormenta',                                   local:'Carmo do Rio Claro · MG',         tipo:'Bate e volta',               transporte:'Microônibus Executivo', vagas:'Vagas abertas',        esgotado:false, guias:'Prof. Flávio Pontes e equipe',                  fotos:['img/tormenta_1.jpg','img/tormenta_2.jpg','img/tormenta_3.jpg','img/tormenta_4.jpg'], saidaPocos:false },
  { mes:'Julho',    ano:2026, data:'18 e 19/07', nome:'Travessia Serra Negra',                               local:'Parque Nacional do Itatiaia · RJ', tipo:'1 pernoite em Pousada',      transporte:'Van Executiva Luxo',    vagas:'Esgotado',             esgotado:true,  guias:'Guia Leo Silva + Prof. Flávio Pontes',          fotos:['img/serranegra_1.jpg','img/serranegra_2.jpg','img/serranegra_3.jpg','img/serranegra_4.jpg','img/serranegra_5.jpg'], saidaPocos:false },
  { mes:'Agosto',   ano:2026, data:'01/08',      nome:'Canion Eldorado',                                     local:'Sobradinho · MG',                 tipo:'Bate e volta',               transporte:'Van Executiva Luxo',    vagas:'Esgotado',             esgotado:true,  guias:'Guia Carlinhos + Prof. Flávio Pontes',          fotos:[], saidaPocos:false },
  { mes:'Agosto',   ano:2026, data:'02/08',      nome:'Pico do Lopo',                                        local:'MG',                              tipo:'Bate e volta',               transporte:'Van Executiva Luxo',    vagas:'Vagas abertas',        esgotado:false, guias:'Prof. Flávio Pontes e equipe',                  fotos:['img/lopo_1.jpg','img/lopo_2.jpg','img/lopo_3.jpg','img/lopo_4.jpg'], saidaPocos:false },
  { mes:'Agosto',   ano:2026, data:'15 e 16/08', nome:'Ibitipoca — Janela do Céu + Circuito das Águas',     local:'Ibitipoca · MG',                  tipo:'1 pernoite em Hotel/Pousada', transporte:'Van Executiva Luxo',    vagas:'2 vagas disponíveis',  esgotado:false, guias:'Guia Jamaica + Prof. Flávio Pontes',            fotos:['img/ibitipoca_1.jpg','img/ibitipoca_2.jpg','img/ibitipoca_3.jpg','img/ibitipoca_4.jpg','img/ibitipoca_5.jpg'], saidaPocos:false },
  { mes:'Agosto',   ano:2026, data:'29 e 30/08', nome:'Serra da Canastra — Complexo do Luquinha',           local:'Serra da Canastra · MG',          tipo:'1 pernoite · Pousada com jantar, café da manhã e almoço', transporte:'Van Executiva Luxo',    vagas:'2 vagas disponíveis',  esgotado:false, guias:'Guia Nenego + Prof. Flávio Pontes',             fotos:[], saidaPocos:false },
  { mes:'Setembro', ano:2026, data:'12/09',      nome:'Parte Baixa do Itatiaia',                             local:'Itatiaia · RJ',                   tipo:'Bate e volta',               transporte:'Microônibus Executivo', vagas:'10 vagas disponíveis', esgotado:false, guias:'Prof. Flávio Pontes e equipe',                  fotos:['img/itatiaia_baixa_1.jpg','img/itatiaia_baixa_2.jpg','img/itatiaia_baixa_3.jpg'], saidaPocos:false },
  { mes:'Setembro', ano:2026, data:'19 e 20/09', nome:'Praias Selvagens',                                   local:'Rio de Janeiro · RJ',             tipo:'2 dias · Hotel com café da manhã', transporte:'Ônibus Semi Leito',     vagas:'Esgotado',             esgotado:true,  guias:'Guia Leo Silva + Prof. Flávio Pontes',          fotos:['img/praias_1.jpg','img/praias_2.jpg','img/praias_3.jpg','img/praias_4.jpg','img/praias_5.jpg','img/praias_6.jpg','img/praias_7.jpg','img/praias_8.jpg','img/praias_9.jpg','img/praias_10.jpg','img/praias_11.jpg'], saidaPocos:true  },
  { mes:'Setembro', ano:2026, data:'27/09',      nome:'Nascer do Sol no Pico do Papagaio',                   local:'Aiuruoca · MG',                   tipo:'Bate e volta',               transporte:'Van Executiva Luxo',    vagas:'Vagas abertas',        esgotado:false, guias:'Prof. Flávio Pontes e equipe',                  fotos:['img/papagaio_1.jpg','img/papagaio_2.jpg','img/papagaio_3.jpg','img/papagaio_4.jpg'], saidaPocos:false },
  { mes:'Outubro',  ano:2026, data:'10 e 11/10', nome:'Pedra da Gávea',                                     local:'Rio de Janeiro · RJ',             tipo:'1 pernoite com café da manhã', transporte:'Microônibus',           vagas:'17 vagas disponíveis', esgotado:false, guias:'Guia Leo Silva + Prof. Flávio Pontes',          fotos:['img/gavea_1.jpg','img/gavea_2.jpg','img/gavea_3.jpg','img/gavea_4.jpg','img/gavea_5.jpg','img/gavea_6.jpg','img/gavea_7.jpg','img/gavea_8.jpg'], saidaPocos:false },
  { mes:'Outubro',  ano:2026, data:'17 e 18/10', nome:'Cavernas de Petar',                                  local:'PETAR · SP',                      tipo:'1 pernoite · Pousada com 2 cafés da manhã', transporte:'Microônibus',           vagas:'10 vagas disponíveis', esgotado:false, guias:'Guia Sandra + Prof. Flávio Pontes',             fotos:['img/petar_1.jpg','img/petar_2.jpg','img/petar_3.jpg'], saidaPocos:false },
  { mes:'Novembro', ano:2026, data:'29 e 30/11', nome:'Parque Nacional da Tijuca',                          local:'Rio de Janeiro · RJ',             tipo:'1 pernoite',                 transporte:'Microônibus Executivo', vagas:'30 vagas disponíveis', esgotado:false, guias:'Guia Leo Silva + Prof. Flávio Pontes',          fotos:[], saidaPocos:false },
  { mes:'Março',    ano:2027, data:'07 e 08/03', nome:'Serra da Canastra — Paraíso Selvagem + Complexo do Campo Claro', local:'Campo Claro · MG',                tipo:'1 pernoite · Pousada com café da manhã', transporte:'Van Executiva Luxo',    vagas:'19 vagas disponíveis', esgotado:false, guias:'Guia Anderson Jacob + Prof. Flávio Pontes',     fotos:['img/canastra_1.jpg','img/canastra_2.jpg','img/canastra_3.jpg','img/canastra_4.jpg','img/canastra_5.jpg','img/canastra2_1.jpg','img/canastra2_2.jpg','img/canastra2_3.jpg','img/canastra2_4.jpg','img/canastra2_5.jpg'], saidaPocos:true  }
];

function waLink(nome, data) {
  return 'https://wa.me/' + WA + '?text=' + encodeURIComponent('Olá, Prof. Flávio! Tenho interesse no destino: ' + nome + ' (' + data + '). Poderia me passar mais informações sobre valores e disponibilidade?');
}

function buildFotos(fotos) {
  if (!fotos || !fotos.length) {
    return '<div class="event-no-photo">📸 Fotos em breve</div>';
  }
  var list = fotos.slice(0, 5);
  var imgs = list.map(function (url, i) {
    return '<img src="' + url + '" alt="" loading="lazy" class="' + (i === 0 ? 'active' : '') + '">';
  }).join('');
  var arrows = list.length > 1
    ? '<button class="slider-btn slider-prev">&#8249;</button><button class="slider-btn slider-next">&#8250;</button><div class="slider-counter">1 / ' + list.length + '</div>'
    : '';
  return '<div class="event-slider" data-cur="0" data-total="' + list.length + '">' + imgs + arrows + '</div>';
}

function buildAgenda() {
  var container = document.getElementById('agendaContainer');
  var meses = [], map = {};
  EVENTOS.forEach(function (ev) {
    if (!map[ev.mes]) { map[ev.mes] = []; meses.push(ev.mes); }
    map[ev.mes].push(ev);
  });
  meses.forEach(function (mes) {
    var ano = map[mes][0].ano || 2026;
    var g = document.createElement('div');
    g.className = 'month-group';
    g.setAttribute('data-anim', '');
    g.innerHTML = '<div class="month-label">' + mes + ' · ' + ano + '</div>';
    var grid = document.createElement('div');
    grid.className = 'month-events';
    map[mes].forEach(function (ev) {
      var c = document.createElement('div');
      c.className = 'event-card' + (ev.esgotado ? ' esgotado' : '');

      var saidaPocos = ev.saidaPocos
        ? '<span>📌 <span class="saida-pocos">Saída Poços + Varginha</span></span>'
        : '';

      var botao = '<a class="btn-wa" href="' + waLink(ev.nome, ev.data) + '" target="_blank">' + WA_SVG + 'Consultar disponibilidade</a>';

      c.innerHTML =
        buildFotos(ev.fotos) +
        '<div class="event-body">' +
          '<div class="event-date">' + ev.data + '</div>' +
          '<div class="event-name">' + ev.nome + '</div>' +
          '<div class="event-meta">' +
            '<span>📍 ' + ev.local + '</span>' +
            '<span>🕐 ' + ev.tipo + '</span>' +
            '<span>🚐 ' + ev.transporte + '</span>' +
            '<span>🧢 ' + ev.guias + '</span>' +
            saidaPocos +
          '</div>' +
          botao +
        '</div>';
      grid.appendChild(c);
    });
    g.appendChild(grid);
    container.appendChild(g);
    observer.observe(g);
  });
}

/* ── FAQ ── */
var FAQS = [
  { q:'Tem trilhas para iniciantes?', a:'Sim! Temos roteiros leves para quem está começando. Recomendamos a realização de um check-up médico antes de iniciar nas atividades, especialmente para quem está há algum tempo sem praticar exercícios.' },
  { q:'E para quem já tem experiência?', a:'Também! Trabalhamos com trilhas de nível difícil a superdifícil, além de escaladas que exigem técnica e preparo físico específicos. Cada saída tem seu nível de dificuldade informado.' },
  { q:'O que acontece se chover?', a:'Sempre que as condições climáticas forem ruins e impedirem a realização segura da trilha, uma nova data é agendada com antecedência. Assim todos conseguem se programar novamente com segurança e tranquilidade.' },
  { q:'Como posso reservar minha vaga?', a:'Você pode reservar diretamente pelo WhatsApp, Instagram ou Facebook. O pagamento é feito via Pix antecipado parcelado ou cartão. Entre em contato e o Prof. Flávio orienta todo o processo.' },
  { q:'Quantas pessoas participam por saída?', a:'Depende do transporte: van executiva comporta 18 a 20 pessoas, microônibus aproximadamente 30, e ônibus até 45 pessoas. Cada saída tem sua capacidade definida.' },
  { q:'Preciso ter experiência para participar?', a:'Não! Cada saída tem seu nível informado. Temos opções para todos os perfis — do iniciante ao experiente. O importante é vir com disposição e vontade de aproveitar!' },
  { q:'Quais estados são atendidos?', a:'Atuamos principalmente em Minas Gerais, Rio de Janeiro e São Paulo, com destinos que vão de Varginha até grandes atrativos como Itatiaia, Pedra da Gávea e Serra dos Órgãos.' },
  { q:'Como fico sabendo o que levar?', a:'Após confirmar sua vaga, o Prof. Flávio passa todas as informações sobre equipamentos e o que levar para aquele roteiro via WhatsApp. Cada trilha tem sua orientação própria.' },
  { q:'Qual é o transporte utilizado?', a:'Vans executivas luxo e microônibus com ar condicionado — conforto e segurança desde a saída de Varginha até o destino. O transporte faz parte da experiência!' }
];

function buildFaq() {
  var list = document.getElementById('faqList');
  FAQS.forEach(function (item) {
    var el = document.createElement('div');
    el.className = 'faq-item';
    el.setAttribute('data-anim', '');
    el.innerHTML = '<div class="faq-q">' + item.q + '<span class="faq-icon">+</span></div><div class="faq-a">' + item.a + '</div>';
    el.querySelector('.faq-q').addEventListener('click', function () { el.classList.toggle('open'); });
    list.appendChild(el);
    observer.observe(el);
  });
}

/* ── Depoimentos ──
   Para preencher: edite o array DEPOIMENTOS abaixo.
   "foto" aceita caminho relativo (ex: 'img/nome.jpg') ou deixe vazio para ícone padrão.
── */
var DEPOIMENTOS = [
  {
    nome: 'Fagner',
    cidade: 'Varginha · MG',
    texto: 'Conhecer o grupo de Caminhada e Trekking Varginha mudou completamente o meu olhar sobre a vida. A experiência nas trilhas me trouxe novos hábitos e me fez valorizar muito mais cada momento. Foi a melhor escolha que fiz e indico de olhos fechados para qualquer amigo. Se você está na dúvida, apenas vá. Eu super recomendo!',
    stars: 5,
    foto: 'img/fagner.jpg'
  },
  {
    nome: 'Mariana Reis',
    cidade: 'Varginha · MG',
    texto: 'Até que um dia criei coragem e fui, e foi uma das melhores decisões que tomei. Vivi experiências incríveis, conheci lugares que jamais imaginei conhecer, enfrentei desafios e descobri que era mais capaz do que imaginava. Cada trilha tem uma energia única, com uma turma incrível e o Prof. Flávio sempre conduz tudo com muita atenção, gentileza e cuidado, o que faz toda a diferença. Hoje posso dizer que estou amando fazer parte desse mundo e trilhas e montanhas.',
    stars: 5,
    foto: 'img/mari.jpg'
  },
  {
    nome: 'Éder Evander',
    cidade: 'Varginha · MG',
    texto: 'Conheci o grupo de caminhada a mais ou menos uns 6 anos e foi um diferencial na minha vida pois estava pensando por uma fase muito difícil. Mas graças a Deus e ao grupo hoje me sinto outra pessoa.',
    stars: 5,
    foto: 'img/eder.jpg'
  },
  {
    nome: 'Juarez',
    cidade: 'Varginha · MG',
    texto: 'Trilhas e montanhas? Muitas já fui através do Grupo de Caminhadas e Trekking Varginha! São experiências fantásticas não apenas os trajetos e destinos. Trata-se mais de vivências, de experiências e boas querências. Bora pra outras tantas! 🫶🤛😍',
    stars: 5,
    foto: 'img/juarez.jpg'
  },
  {
    nome: 'Laemis',
    cidade: 'Varginha · MG',
    texto: 'Sabe a diferença de caminhar com direção? É ter um ponto de início e um ponto de fim e o que existe no percurso que faz você crescer. Porque existe, amizade, ajuda, risadas, superação, troca de experiências, paisagens maravilhosas e a presença de Deus em cada instante! Toda pessoa deve permitir-se a um encontro como esse, depois você me conta o resultado? 😉',
    stars: 5,
    foto: 'img/nn.jpg'
  }
];

function buildDep() {
  var track = document.getElementById('depTrack');
  var dotsEl = document.getElementById('depDots');
  var btnPrev = document.getElementById('depPrev');
  var btnNext = document.getElementById('depNext');

  function perView() {
    return window.innerWidth <= 600 ? 1 : window.innerWidth <= 900 ? 2 : 3;
  }

  var total = DEPOIMENTOS.length;
  var cur = 0;

  DEPOIMENTOS.forEach(function (d) {
    var c = document.createElement('div');
    c.className = 'dep-card';
    var foto = d.foto
      ? '<img src="' + d.foto + '" alt="' + d.nome + '">'
      : '<div class="dep-photo-ph">👤</div>';
    var stars = '★'.repeat(d.stars) + '☆'.repeat(5 - d.stars);
    c.innerHTML =
      '<div class="dep-header">' +
        '<div class="dep-photo">' + foto + '</div>' +
        '<div class="dep-info"><div class="dep-name">' + d.nome + '</div><div class="dep-city">' + d.cidade + '</div><div class="dep-stars">' + stars + '</div></div>' +
      '</div>' +
      '<div class="dep-text">' + d.texto + '</div>';
    track.appendChild(c);
  });

  function numDots() { return Math.ceil(total / perView()); }
  function buildDots() {
    dotsEl.innerHTML = '';
    for (var i = 0; i < numDots(); i++) {
      var d = document.createElement('div');
      d.className = 'dep-dot' + (i === 0 ? ' active' : '');
      d.dataset.i = i;
      d.addEventListener('click', function () { goTo(parseInt(this.dataset.i)); });
      dotsEl.appendChild(d);
    }
  }

  function goTo(idx) {
    var pv = perView();
    var max = total - pv;
    cur = Math.max(0, Math.min(idx * pv, max));
    var cards = track.querySelectorAll('.dep-card');
    var cardW = cards[0] ? cards[0].offsetWidth : 0;
    var gap = 20;
    track.style.transform = 'translateX(-' + (cur * (cardW + gap)) + 'px)';
    var dotIdx = Math.floor(cur / pv);
    dotsEl.querySelectorAll('.dep-dot').forEach(function (d, i) {
      d.classList.toggle('active', i === dotIdx);
    });
    btnPrev.disabled = cur === 0;
    btnNext.disabled = cur >= max;
  }

  btnPrev.addEventListener('click', function () { goTo(Math.floor(cur / perView()) - 1); });
  btnNext.addEventListener('click', function () { goTo(Math.floor(cur / perView()) + 1); });

  var touchX = null;
  track.addEventListener('touchstart', function (e) { touchX = e.touches[0].clientX; }, { passive: true });
  track.addEventListener('touchend', function (e) {
    if (touchX === null) return;
    var diff = touchX - e.changedTouches[0].clientX;
    if (Math.abs(diff) > 40) goTo(Math.floor(cur / perView()) + (diff > 0 ? 1 : -1));
    touchX = null;
  });

  buildDots();
  goTo(0);
  window.addEventListener('resize', function () { buildDots(); goTo(0); });
}

function initSliders() {
  document.querySelectorAll('.event-slider[data-total]').forEach(function (sl) {
    var total = parseInt(sl.dataset.total);
    if (total <= 1) return;
    var imgs = sl.querySelectorAll('img');
    var counter = sl.querySelector('.slider-counter');
    var cur = 0;
    function goTo(n) {
      imgs[cur].classList.remove('active');
      cur = (n + total) % total;
      imgs[cur].classList.add('active');
      counter.textContent = (cur + 1) + ' / ' + total;
    }
    sl.querySelector('.slider-prev').addEventListener('click', function (e) { e.stopPropagation(); goTo(cur - 1); });
    sl.querySelector('.slider-next').addEventListener('click', function (e) { e.stopPropagation(); goTo(cur + 1); });
  });
}

buildAgenda();
buildFaq();
buildDep();
initSliders();
