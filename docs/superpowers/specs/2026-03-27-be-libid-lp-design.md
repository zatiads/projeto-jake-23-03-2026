# Be Libid — Landing Page Pós-Parto

**Data:** 2026-03-27
**Tipo:** Landing Page de conversão (venda direta)
**Produto:** Be Libid — suplemento feminino (energia, disposição, libido)
**Público-alvo:** Mulheres no pós-parto
**Estilo visual:** Bold/moderno — dark mode, alto contraste, urgência
**Checkout:** Redirecionamento para plataforma externa (Ticto)

---

## Oferta

### Kit 1 Pote
- **Preço original:** R$177,00
- **Preço promocional:** R$99,00 à vista ou 10x de R$10,33
- **Checkout:** https://payment.ticto.app/O93D81015
- **Bônus:** Ebook "Manual do Prazer"

### Kit 2 Potes
- **Cada pote:** R$87,95
- **Preço original:** R$275,90
- **Preço promocional:** R$175,90 à vista ou 12x de R$18,19
- **Checkout:** https://payment.ticto.app/OED5F9B5D
- **Bônus:** Ebook "Manual do Prazer"

### Kit 3 Potes
- **Cada pote:** R$86,63
- **Preço original:** R$359,90
- **Preço promocional:** R$259,90 à vista ou 12x de R$26,87
- **Checkout:** https://payment.ticto.app/OA2E4D9DA
- **Bônus:** Ebook "Manual do Prazer"

### Diferenciais gerais
- Frete grátis para todo Brasil
- Garantia de 60 dias com devolução total do dinheiro

---

## Abordagem

Single-scroll LP com countdown de urgência (fake — reseta a cada visita). Narrativa focada nas dores do pós-parto → solução → tabela de kits → garantia.

---

## Estrutura de Seções

### 1. Hero
- Fundo escuro (preto #0a0a0a ou vinho escuro #1a0010)
- Headline focada na dor: *"Seu corpo mudou. Sua energia sumiu. Sua libido foi junto."*
- Sub-headline curta: *"Be Libid foi criado para a mulher que passou pelo pós-parto e quer se reconhecer de novo."*
- Countdown regressivo de 24h (fake — JS simples, reseta ao carregar a página, exibe HH:MM:SS)
- Ao zerar: timer trava em 00:00:00, CTA mantém o link ativo
- CTA principal: botão laranja `#e8872a` bold — **"QUERO APROVEITAR A OFERTA"** → link para kit 1 pote

### 2. O Problema (Pós-Parto)
- Fundo: cinza escuro (#111111) ou vinho suave
- Título: *"Você não está sozinha"*
- 3 cards com ícone + texto:
  - 😴 **Cansaço constante** — Mesmo dormindo, você acorda exausta
  - ⚡ **Zero disposição** — Não tem energia pra nada além do básico
  - 💔 **Libido sumiu** — O desejo que existia antes simplesmente foi embora
- Texto de fechamento: *"Se você se reconheceu em pelo menos uma dessas situações, o Be Libid foi criado pra você."*

### 3. A Solução (Be Libid)
- Imagem do produto: placeholder (será substituída pelo cliente)
  - Formato esperado: PNG ou JPG, fundo transparente ou escuro, proporção vertical ~1:1.5
- Título: *"Be Libid — Energia, Disposição e Libido de volta"*
- Bullets diretos:
  - ✅ Recupera energia e disposição
  - ✅ Reequilibra o desejo sexual
  - ✅ Formulado para o corpo feminino pós-parto
  - ✅ 60 cápsulas — 1 pote por mês
- Sem listagem de ingredientes (mantém foco no CTA)

### 4. Prova Social
- Título: *"O que outras mulheres estão dizendo"*
- 3 cards texto estilo depoimento (CSS simulando print de mensagem)
- Estrutura de cada card: aspas + texto + nome + idade + ícone de verificado
- Conteúdo: **placeholder** — a ser preenchido pelo cliente com depoimentos reais
- Placeholder de avatar: círculo com inicial do nome

### 5. A Oferta — 3 Kits
- Título: *"Escolha o seu kit e aproveite a oferta"*
- Subtítulo com urgência: *"⚠️ Preço promocional por tempo limitado"*
- Layout: 3 cards lado a lado (desktop) / empilhados (mobile)
- Card do kit 2 potes marcado como **"MAIS POPULAR"** (badge)
- Estrutura de cada card:
  - Nome do kit (1 Pote / 2 Potes / 3 Potes)
  - Preço por pote em destaque
  - Preço original riscado
  - Preço final à vista em bold grande
  - Parcelamento em texto menor
  - Badge de bônus: "🎁 + Ebook Manual do Prazer"
  - Botão CTA laranja com link para o checkout correspondente
- Abaixo dos cards (ícones + texto):
  - 🚚 Frete grátis para todo Brasil
  - 🛡️ Garantia de 60 dias
  - 🔒 Compra 100% segura

### 6. Garantia (reforço)
- Ícone grande de escudo (SVG ou emoji)
- Título: *"Risco zero para você"*
- Copy: *"Testou, não gostou, devolvemos 100% do seu dinheiro. Sem perguntas, sem burocracia. Você tem 60 dias para decidir."*
- Nota: seção intencional — reforça confiança após o bloco de preço

### 7. CTA Final + Footer
- Repetição do botão CTA (link kit 1 pote como padrão)
- Texto: *"Ainda dá tempo — garanta o seu com desconto"*
- Footer minimalista: logo Be Libid, links para Política de Privacidade e Termos de Uso (placeholder href="#"), CNPJ/razão social (placeholder — a ser preenchido pelo cliente)

---

## Sticky Bar (Mobile)
- Barra fixa no rodapé apenas em mobile
- Conteúdo: preço à vista (R$99) + botão CTA pequeno
- Link: kit 1 pote

---

## Paleta e Tipografia

| Elemento | Valor |
|---|---|
| Fundo principal | `#0a0a0a` |
| Fundo alternado | `#111111` |
| Texto | `#f5f5f5` |
| Destaque / CTA | `#e8872a` |
| Cards | `#1a1a1a` com borda `#2a2a2a` |
| Preço riscado | `#888888` |
| Tipografia | Inter ou Montserrat (Google Fonts), bold para headings |

---

## Responsividade

- **Mobile-first**
- Breakpoint principal: `768px`
- Abaixo de 768px: cards empilhados, sticky bar visível, font-size reduzido
- Acima de 768px: 3 cards lado a lado, sticky bar oculta

---

## Entregável

- Arquivo HTML único com CSS embutido (ou `style.css` separado no mesmo diretório)
- JS mínimo inline para o countdown (sem dependências externas)
- Google Fonts via CDN
- Sem framework JS (sem React, Vue, etc.)
- Imagem do produto: placeholder (`<div>` estilizado ou `img` com `src="#"`)
- Responsivo, testado em mobile e desktop
- O cliente enviará HTML inicial como ponto de partida
