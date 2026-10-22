/*
 * Guarda o cockpit na central: com o hotspot ainda conectando (ou sem sinal), a tela abre na hora,
 * com carro, som e animação. Só os dados (clima, agenda, rota, voz) esperam a internet.
 * - a página: tenta a rede (3 s) e, sem resposta, usa a cópia guardada
 * - imagens, sons, scripts e fontes: usa a cópia guardada e atualiza por trás
 * - dados (/carro/painel, /carro/rota, /carro/realtime…): sempre da rede, nunca guardados
 */
const CACHE = 'jake-cockpit-v1';
const BASE = '/carro/cockpit/';
const ESSENCIAIS = [
  BASE, BASE + 'index.html', BASE + 'tempo_real.js', BASE + 'marca.png', BASE + 'carro_frente.webp',
  BASE + 'carro_tras.webp', BASE + 'carro_pose.webp', BASE + 'hb20_giro_alfa.webp', BASE + 'sons/abertura_B_nave.mp3',
];
const DE_FORA = [
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css',
  'https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;500;600&family=Inter+Tight:wght@300;400;500&display=swap',
];

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    await Promise.all(ESSENCIAIS.map((u) => c.add(u).catch(() => {})));
    await Promise.all(DE_FORA.map((u) => fetch(u, { mode: 'no-cors' }).then((r) => c.put(u, r)).catch(() => {})));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const nome of await caches.keys()) if (nome !== CACHE) await caches.delete(nome);
    await self.clients.claim();
  })());
});

function guardavel(url) {
  if (url.origin === location.origin) return url.pathname.startsWith(BASE);
  return /cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com|arcgisonline\.com/.test(url.hostname);
}

async function redePrimeiro(req) {
  const c = await caches.open(CACHE);
  try {
    const resp = await Promise.race([fetch(req), new Promise((_, n) => setTimeout(() => n(new Error('lento')), 3000))]);
    if (resp && resp.ok) c.put(BASE + 'index.html', resp.clone());
    return resp;
  } catch (e) {
    return (await c.match(BASE + 'index.html')) || Response.error();
  }
}

async function guardadoPrimeiro(req) {
  const c = await caches.open(CACHE);
  const guardado = await c.match(req, { ignoreSearch: true });
  const daRede = fetch(req).then((r) => { if (r && (r.ok || r.type === 'opaque')) c.put(req, r.clone()); return r; }).catch(() => null);
  return guardado || (await daRede) || Response.error();
}

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (!guardavel(url)) return;                       // dados e voz: direto da rede
  if (e.request.mode === 'navigate') e.respondWith(redePrimeiro(e.request));
  else e.respondWith(guardadoPrimeiro(e.request));
});
