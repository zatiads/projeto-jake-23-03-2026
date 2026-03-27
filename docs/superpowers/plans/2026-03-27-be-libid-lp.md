# Be Libid Landing Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir uma landing page de conversão para o suplemento feminino Be Libid, focada em mulheres no pós-parto, com 3 opções de kit, countdown fake de urgência e dark mode bold.

**Architecture:** Arquivos estáticos separados (`index.html`, `style.css`, `script.js`) em `/root/clientes/be-libid/`. Sem framework JS, sem build tool. CSS mobile-first com um breakpoint em 768px. O HTML inicial será fornecido pelo cliente e deve ser usado como ponto de partida — se ainda não chegou, iniciar do zero.

**Tech Stack:** HTML5, CSS3 (custom properties, flexbox, grid), JavaScript vanilla (countdown), Google Fonts (Inter ou Montserrat via CDN).

---

## File Map

| Arquivo | Responsabilidade |
|---|---|
| `clientes/be-libid/index.html` | Estrutura HTML completa da LP |
| `clientes/be-libid/style.css` | Todos os estilos, mobile-first, variáveis CSS |
| `clientes/be-libid/script.js` | Countdown fake + sticky bar toggle |

---

## Paleta e variáveis CSS (referência para todos os tasks)

```css
:root {
  --bg: #0a0a0a;
  --bg-alt: #111111;
  --card-bg: #1a1a1a;
  --card-border: #2a2a2a;
  --text: #f5f5f5;
  --text-muted: #888888;
  --accent: #e8872a;
  --font: 'Inter', sans-serif;
}
```

---

## Task 1: Setup — estrutura de arquivos

**Files:**
- Create: `clientes/be-libid/index.html`
- Create: `clientes/be-libid/style.css`
- Create: `clientes/be-libid/script.js`

- [ ] **Step 1: Criar diretório e arquivos**

```bash
mkdir -p /root/clientes/be-libid
touch /root/clientes/be-libid/index.html
touch /root/clientes/be-libid/style.css
touch /root/clientes/be-libid/script.js
```

- [ ] **Step 2: Verificar se o cliente enviou HTML inicial**

Se sim, copiar o conteúdo para `index.html` e adaptar a partir dele.
Se não, criar o esqueleto abaixo em `index.html`:

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Be Libid — Energia, Disposição e Libido de Volta</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <!-- HERO -->
  <section id="hero"></section>
  <!-- PROBLEMA -->
  <section id="problema"></section>
  <!-- SOLUCAO -->
  <section id="solucao"></section>
  <!-- DEPOIMENTOS -->
  <section id="depoimentos"></section>
  <!-- OFERTA -->
  <section id="oferta"></section>
  <!-- GARANTIA -->
  <section id="garantia"></section>
  <!-- FOOTER -->
  <footer id="footer"></footer>
  <!-- STICKY BAR (mobile) -->
  <div id="sticky-bar"></div>

  <script src="script.js"></script>
</body>
</html>
```

- [ ] **Step 3: Inicializar style.css com variáveis e reset**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #0a0a0a;
  --bg-alt: #111111;
  --card-bg: #1a1a1a;
  --card-border: #2a2a2a;
  --text: #f5f5f5;
  --text-muted: #888888;
  --accent: #e8872a;
  --font: 'Inter', sans-serif;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  line-height: 1.6;
}

img { max-width: 100%; display: block; }

a { color: inherit; text-decoration: none; }

section { padding: 64px 24px; }

.container { max-width: 900px; margin: 0 auto; }
```

- [ ] **Step 4: Commit inicial**

```bash
git add clientes/be-libid/
git commit -m "feat: setup estrutura LP Be Libid"
```

---

## Task 2: Seção Hero com Countdown

**Files:**
- Modify: `clientes/be-libid/index.html` (seção #hero)
- Modify: `clientes/be-libid/style.css` (estilos hero)
- Modify: `clientes/be-libid/script.js` (countdown)

- [ ] **Step 1: Preencher HTML do hero**

Substituir `<section id="hero"></section>` por:

```html
<section id="hero">
  <div class="container hero-inner">
    <p class="hero-eyebrow">Para a mulher que passou pelo pós-parto</p>
    <h1 class="hero-title">Seu corpo mudou.<br>Sua energia sumiu.<br>Sua libido foi junto.</h1>
    <p class="hero-sub">Be Libid foi criado para você se reconhecer de novo.</p>

    <div class="countdown-wrapper">
      <p class="countdown-label">⚠️ Oferta encerra em:</p>
      <div class="countdown" id="countdown">
        <span id="cd-hours">00</span>h
        <span id="cd-minutes">00</span>m
        <span id="cd-seconds">00</span>s
      </div>
    </div>

    <a href="https://payment.ticto.app/O93D81015" class="btn-cta" target="_blank" rel="noopener">
      QUERO APROVEITAR A OFERTA
    </a>
  </div>
</section>
```

- [ ] **Step 2: Estilizar hero no style.css**

```css
/* HERO */
#hero {
  background: linear-gradient(135deg, #0a0a0a 60%, #1a0010 100%);
  text-align: center;
  padding: 80px 24px;
}

.hero-eyebrow {
  color: var(--accent);
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 16px;
}

.hero-title {
  font-size: clamp(2rem, 6vw, 3.5rem);
  font-weight: 900;
  line-height: 1.15;
  margin-bottom: 20px;
}

.hero-sub {
  font-size: 1.125rem;
  color: var(--text-muted);
  margin-bottom: 40px;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
}

.countdown-wrapper {
  margin-bottom: 32px;
}

.countdown-label {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.countdown {
  font-size: clamp(2rem, 8vw, 3rem);
  font-weight: 900;
  color: var(--accent);
  letter-spacing: 0.05em;
}

.btn-cta {
  display: inline-block;
  background: var(--accent);
  color: #fff;
  font-size: 1rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 18px 40px;
  border-radius: 4px;
  cursor: pointer;
  transition: filter 0.2s;
}

.btn-cta:hover { filter: brightness(1.1); }
```

- [ ] **Step 3: Implementar countdown no script.js**

```javascript
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
```

- [ ] **Step 4: Abrir index.html no navegador e confirmar que o countdown conta regressivamente**

- [ ] **Step 5: Commit**

```bash
git add clientes/be-libid/
git commit -m "feat: hero + countdown Be Libid LP"
```

---

## Task 3: Seção Problema

**Files:**
- Modify: `clientes/be-libid/index.html` (seção #problema)
- Modify: `clientes/be-libid/style.css`

- [ ] **Step 1: Preencher HTML**

```html
<section id="problema">
  <div class="container">
    <h2 class="section-title">Você não está sozinha</h2>
    <div class="cards-3">
      <div class="card-dor">
        <span class="card-icon">😴</span>
        <h3>Cansaço constante</h3>
        <p>Mesmo dormindo, você acorda exausta e sem força para o dia.</p>
      </div>
      <div class="card-dor">
        <span class="card-icon">⚡</span>
        <h3>Zero disposição</h3>
        <p>Não tem energia para nada além do básico. O resto ficou pra depois.</p>
      </div>
      <div class="card-dor">
        <span class="card-icon">💔</span>
        <h3>Libido sumiu</h3>
        <p>O desejo que existia antes simplesmente foi embora com o parto.</p>
      </div>
    </div>
    <p class="problema-fechamento">
      Se você se reconheceu em pelo menos uma dessas situações,<br>
      <strong>o Be Libid foi criado pra você.</strong>
    </p>
  </div>
</section>
```

- [ ] **Step 2: Estilizar**

```css
/* PROBLEMA */
#problema {
  background: var(--bg-alt);
  text-align: center;
}

.section-title {
  font-size: clamp(1.5rem, 4vw, 2.25rem);
  font-weight: 900;
  margin-bottom: 48px;
}

.cards-3 {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  margin-bottom: 48px;
}

@media (min-width: 768px) {
  .cards-3 { grid-template-columns: repeat(3, 1fr); }
}

.card-dor {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 8px;
  padding: 32px 24px;
}

.card-icon {
  font-size: 2.5rem;
  display: block;
  margin-bottom: 16px;
}

.card-dor h3 {
  font-size: 1.125rem;
  font-weight: 700;
  margin-bottom: 12px;
}

.card-dor p {
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.problema-fechamento {
  font-size: 1.125rem;
  line-height: 1.8;
}
```

- [ ] **Step 3: Verificar visualmente no browser (mobile e desktop)**

- [ ] **Step 4: Commit**

```bash
git add clientes/be-libid/
git commit -m "feat: seção problema Be Libid LP"
```

---

## Task 4: Seção Solução

**Files:**
- Modify: `clientes/be-libid/index.html`
- Modify: `clientes/be-libid/style.css`

- [ ] **Step 1: Preencher HTML**

```html
<section id="solucao">
  <div class="container solucao-inner">
    <div class="solucao-img">
      <!-- Placeholder: substituir pela foto real do pote -->
      <div class="img-placeholder">📦 Foto do produto</div>
    </div>
    <div class="solucao-texto">
      <h2>Be Libid<br><span class="accent">Energia, Disposição e Libido de volta</span></h2>
      <ul class="beneficios">
        <li>✅ Recupera energia e disposição</li>
        <li>✅ Reequilibra o desejo sexual</li>
        <li>✅ Formulado para o corpo feminino pós-parto</li>
        <li>✅ 60 cápsulas — 1 pote por mês</li>
      </ul>
      <a href="https://payment.ticto.app/O93D81015" class="btn-cta" target="_blank" rel="noopener">
        QUERO MEU BE LIBID
      </a>
    </div>
  </div>
</section>
```

- [ ] **Step 2: Estilizar**

```css
/* SOLUÇÃO */
#solucao { background: var(--bg); }

.solucao-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 48px;
}

@media (min-width: 768px) {
  .solucao-inner { flex-direction: row; gap: 64px; }
}

.solucao-img { flex: 1; text-align: center; }

.img-placeholder {
  background: var(--card-bg);
  border: 2px dashed var(--card-border);
  border-radius: 12px;
  padding: 80px 40px;
  color: var(--text-muted);
  font-size: 1.25rem;
}

.solucao-texto { flex: 1; }

.solucao-texto h2 {
  font-size: clamp(1.5rem, 3.5vw, 2rem);
  font-weight: 900;
  margin-bottom: 32px;
  line-height: 1.3;
}

.accent { color: var(--accent); }

.beneficios {
  list-style: none;
  margin-bottom: 40px;
}

.beneficios li {
  font-size: 1.0625rem;
  padding: 10px 0;
  border-bottom: 1px solid var(--card-border);
}

.beneficios li:last-child { border-bottom: none; }
```

- [ ] **Step 3: Verificar no browser**

- [ ] **Step 4: Commit**

```bash
git add clientes/be-libid/
git commit -m "feat: seção solução Be Libid LP"
```

---

## Task 5: Seção Depoimentos (Placeholder)

**Files:**
- Modify: `clientes/be-libid/index.html`
- Modify: `clientes/be-libid/style.css`

- [ ] **Step 1: Preencher HTML com placeholders**

```html
<section id="depoimentos">
  <div class="container">
    <h2 class="section-title">O que outras mulheres estão dizendo</h2>
    <div class="cards-3">
      <div class="card-depo">
        <p class="depo-texto">"[Depoimento real a ser inserido pelo cliente]"</p>
        <div class="depo-autor">
          <div class="depo-avatar">A</div>
          <div>
            <strong>Ana, 31 anos</strong>
            <span class="depo-verificado">✓ Verificado</span>
          </div>
        </div>
      </div>
      <div class="card-depo">
        <p class="depo-texto">"[Depoimento real a ser inserido pelo cliente]"</p>
        <div class="depo-autor">
          <div class="depo-avatar">M</div>
          <div>
            <strong>Maria, 28 anos</strong>
            <span class="depo-verificado">✓ Verificado</span>
          </div>
        </div>
      </div>
      <div class="card-depo">
        <p class="depo-texto">"[Depoimento real a ser inserido pelo cliente]"</p>
        <div class="depo-autor">
          <div class="depo-avatar">J</div>
          <div>
            <strong>Juliana, 34 anos</strong>
            <span class="depo-verificado">✓ Verificado</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 2: Estilizar**

```css
/* DEPOIMENTOS */
#depoimentos { background: var(--bg-alt); }

.card-depo {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 8px;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.depo-texto {
  font-size: 0.9375rem;
  font-style: italic;
  color: var(--text);
  line-height: 1.7;
  flex: 1;
}

.depo-autor {
  display: flex;
  align-items: center;
  gap: 12px;
}

.depo-avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: 1.125rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.depo-verificado {
  display: block;
  font-size: 0.75rem;
  color: #4caf7d;
  margin-top: 2px;
}
```

- [ ] **Step 3: Commit**

```bash
git add clientes/be-libid/
git commit -m "feat: seção depoimentos placeholder Be Libid LP"
```

---

## Task 6: Seção Oferta — 3 Kits

**Files:**
- Modify: `clientes/be-libid/index.html`
- Modify: `clientes/be-libid/style.css`

- [ ] **Step 1: Preencher HTML**

```html
<section id="oferta">
  <div class="container">
    <h2 class="section-title">Escolha o seu kit e aproveite a oferta</h2>
    <p class="oferta-urgencia">⚠️ Preço promocional por tempo limitado</p>

    <div class="kits">
      <!-- KIT 1 POTE -->
      <div class="kit-card">
        <h3 class="kit-nome">1 Pote</h3>
        <p class="kit-cada">R$99,00 por pote</p>
        <p class="kit-de"><s>De R$177,00</s></p>
        <p class="kit-por">R$ 99<span class="kit-centavos">,00</span></p>
        <p class="kit-parcela">ou 10x de R$10,33</p>
        <p class="kit-bonus">🎁 + Ebook Manual do Prazer</p>
        <a href="https://payment.ticto.app/O93D81015" class="btn-cta kit-btn" target="_blank" rel="noopener">
          COMPRAR AGORA
        </a>
      </div>

      <!-- KIT 2 POTES (MAIS POPULAR) -->
      <div class="kit-card kit-popular">
        <span class="badge-popular">MAIS POPULAR</span>
        <h3 class="kit-nome">2 Potes</h3>
        <p class="kit-cada">R$87,95 por pote</p>
        <p class="kit-de"><s>De R$275,90</s></p>
        <p class="kit-por">R$ 175<span class="kit-centavos">,90</span></p>
        <p class="kit-parcela">ou 12x de R$18,19</p>
        <p class="kit-bonus">🎁 + Ebook Manual do Prazer</p>
        <a href="https://payment.ticto.app/OED5F9B5D" class="btn-cta kit-btn" target="_blank" rel="noopener">
          COMPRAR AGORA
        </a>
      </div>

      <!-- KIT 3 POTES -->
      <div class="kit-card">
        <h3 class="kit-nome">3 Potes</h3>
        <p class="kit-cada">R$86,63 por pote</p>
        <p class="kit-de"><s>De R$359,90</s></p>
        <p class="kit-por">R$ 259<span class="kit-centavos">,90</span></p>
        <p class="kit-parcela">ou 12x de R$26,87</p>
        <p class="kit-bonus">🎁 + Ebook Manual do Prazer</p>
        <a href="https://payment.ticto.app/OA2E4D9DA" class="btn-cta kit-btn" target="_blank" rel="noopener">
          COMPRAR AGORA
        </a>
      </div>
    </div>

    <!-- Diferenciais -->
    <div class="diferenciais">
      <div class="diferencial">🚚 <span>Frete grátis para todo Brasil</span></div>
      <div class="diferencial">🛡️ <span>Garantia de 60 dias</span></div>
      <div class="diferencial">🔒 <span>Compra 100% segura</span></div>
    </div>
  </div>
</section>
```

- [ ] **Step 2: Estilizar**

```css
/* OFERTA */
#oferta { background: var(--bg); text-align: center; }

.oferta-urgencia {
  color: var(--accent);
  font-weight: 600;
  margin-bottom: 48px;
  font-size: 1rem;
}

.kits {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  margin-bottom: 48px;
}

@media (min-width: 768px) {
  .kits { grid-template-columns: repeat(3, 1fr); align-items: start; }
}

.kit-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 12px;
  padding: 36px 28px;
  position: relative;
}

.kit-popular {
  border-color: var(--accent);
  transform: scale(1.03);
}

.badge-popular {
  position: absolute;
  top: -14px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--accent);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 4px 16px;
  border-radius: 20px;
  white-space: nowrap;
}

.kit-nome {
  font-size: 1.25rem;
  font-weight: 700;
  margin-bottom: 8px;
}

.kit-cada {
  font-size: 0.875rem;
  color: var(--accent);
  font-weight: 600;
  margin-bottom: 8px;
}

.kit-de {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.kit-por {
  font-size: 2.5rem;
  font-weight: 900;
  margin: 8px 0 4px;
}

.kit-centavos { font-size: 1.25rem; }

.kit-parcela {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.kit-bonus {
  font-size: 0.875rem;
  background: rgba(232,135,42,0.1);
  border: 1px solid rgba(232,135,42,0.3);
  border-radius: 4px;
  padding: 8px 12px;
  margin-bottom: 24px;
}

.kit-btn { width: 100%; text-align: center; }

.diferenciais {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 24px;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.diferencial {
  display: flex;
  align-items: center;
  gap: 8px;
}
```

- [ ] **Step 3: Verificar todos os 3 links de checkout clicando neles**

- [ ] **Step 4: Commit**

```bash
git add clientes/be-libid/
git commit -m "feat: seção oferta 3 kits Be Libid LP"
```

---

## Task 7: Seção Garantia + CTA Final + Footer

**Files:**
- Modify: `clientes/be-libid/index.html`
- Modify: `clientes/be-libid/style.css`

- [ ] **Step 1: Preencher HTML (garantia + CTA final + footer)**

```html
<!-- GARANTIA -->
<section id="garantia">
  <div class="container garantia-inner">
    <div class="garantia-icon">🛡️</div>
    <div class="garantia-texto">
      <h2>Risco zero para você</h2>
      <p>Testou, não gostou, devolvemos 100% do seu dinheiro. Sem perguntas, sem burocracia. Você tem <strong>60 dias para decidir</strong>.</p>
    </div>
  </div>
</section>

<!-- CTA FINAL -->
<section id="cta-final">
  <div class="container" style="text-align:center;">
    <p class="cta-final-label">Ainda dá tempo — garanta o seu com desconto</p>
    <a href="https://payment.ticto.app/O93D81015" class="btn-cta" target="_blank" rel="noopener">
      QUERO APROVEITAR A OFERTA
    </a>
  </div>
</section>

<!-- FOOTER -->
<footer id="footer">
  <div class="container footer-inner">
    <p class="footer-marca">Be Libid</p>
    <div class="footer-links">
      <a href="#">Política de Privacidade</a>
      <a href="#">Termos de Uso</a>
    </div>
    <p class="footer-cnpj">[CNPJ/Razão Social — a preencher pelo cliente]</p>
  </div>
</footer>
```

- [ ] **Step 2: Estilizar**

```css
/* GARANTIA */
#garantia { background: var(--bg-alt); }

.garantia-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  text-align: center;
}

@media (min-width: 768px) {
  .garantia-inner { flex-direction: row; text-align: left; gap: 40px; }
}

.garantia-icon { font-size: 5rem; flex-shrink: 0; }

.garantia-texto h2 {
  font-size: 1.5rem;
  font-weight: 900;
  margin-bottom: 12px;
}

.garantia-texto p { color: var(--text-muted); font-size: 1rem; line-height: 1.8; }

/* CTA FINAL */
#cta-final { background: var(--bg); padding: 64px 24px; }

.cta-final-label {
  font-size: 1.125rem;
  margin-bottom: 24px;
  color: var(--text-muted);
}

/* FOOTER */
#footer {
  background: #050505;
  padding: 40px 24px;
  text-align: center;
}

.footer-inner { display: flex; flex-direction: column; gap: 16px; align-items: center; }

.footer-marca { font-weight: 900; font-size: 1.25rem; color: var(--accent); }

.footer-links { display: flex; gap: 24px; }

.footer-links a { color: var(--text-muted); font-size: 0.875rem; }
.footer-links a:hover { color: var(--text); }

.footer-cnpj { color: var(--text-muted); font-size: 0.75rem; }
```

- [ ] **Step 3: Commit**

```bash
git add clientes/be-libid/
git commit -m "feat: garantia, CTA final e footer Be Libid LP"
```

---

## Task 8: Sticky Bar Mobile

**Files:**
- Modify: `clientes/be-libid/index.html`
- Modify: `clientes/be-libid/style.css`
- Modify: `clientes/be-libid/script.js`

- [ ] **Step 1: Preencher HTML do sticky bar**

Já existe `<div id="sticky-bar"></div>`. Substituir por:

```html
<div id="sticky-bar">
  <span class="sticky-preco">Apenas <strong>R$99</strong> à vista</span>
  <a href="https://payment.ticto.app/O93D81015" class="btn-cta sticky-cta" target="_blank" rel="noopener">
    COMPRAR AGORA
  </a>
</div>
```

- [ ] **Step 2: Estilizar (só mobile)**

```css
/* STICKY BAR */
#sticky-bar {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #111;
  border-top: 1px solid var(--card-border);
  padding: 12px 20px;
  justify-content: space-between;
  align-items: center;
  z-index: 100;
}

@media (max-width: 767px) {
  #sticky-bar { display: flex; }
}

.sticky-preco { font-size: 0.9375rem; color: var(--text); }
.sticky-preco strong { color: var(--accent); }

.sticky-cta {
  padding: 10px 20px;
  font-size: 0.8125rem;
}
```

- [ ] **Step 3: Esconder sticky bar quando o hero estiver visível (scroll)**

Adicionar ao final do `script.js`:

```javascript
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
```

- [ ] **Step 4: Testar no DevTools em viewport mobile (375px)**

A sticky bar deve aparecer após rolar além do hero e sumir ao voltar ao topo.

- [ ] **Step 5: Commit**

```bash
git add clientes/be-libid/
git commit -m "feat: sticky bar mobile Be Libid LP"
```

---

## Task 9: Revisão Final e Entrega

**Files:**
- Review: todos os arquivos em `clientes/be-libid/`

- [ ] **Step 1: Checklist visual (abrir no browser)**

- [ ] Hero aparece correto com countdown ativo
- [ ] 3 cards de problema legíveis no mobile
- [ ] Seção solução com layout lado a lado no desktop
- [ ] 3 cards de kit com preços corretos e links de checkout funcionando
- [ ] Card "2 Potes" tem badge "MAIS POPULAR" e está levemente maior
- [ ] Garantia aparece bem
- [ ] Footer com links placeholder visíveis
- [ ] Sticky bar aparece no mobile após rolar o hero

- [ ] **Step 2: Verificar todos os links de checkout**

| Kit | URL esperada |
|---|---|
| 1 Pote | https://payment.ticto.app/O93D81015 |
| 2 Potes | https://payment.ticto.app/OED5F9B5D |
| 3 Potes | https://payment.ticto.app/OA2E4D9DA |

- [ ] **Step 3: Commit final**

```bash
git add clientes/be-libid/
git commit -m "feat: LP Be Libid completa — pronta para revisão do cliente"
```

- [ ] **Step 4: Avisar o Bruno para substituir placeholders**

Itens pendentes para o cliente preencher:
1. Foto do produto (substituir `.img-placeholder` por `<img src="foto-pote.png">`)
2. Depoimentos reais (substituir textos placeholder nos cards)
3. CNPJ/Razão Social no footer
4. Links de Política de Privacidade e Termos de Uso
