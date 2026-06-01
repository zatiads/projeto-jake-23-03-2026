# Design: Módulo de Inglês — Jake OS

**Data:** 2026-06-01
**Status:** Aprovado
**Contexto:** Bruno quer aprender inglês fluente (nível intermediário atual). Módulo dentro do Jake OS com prática diária estruturada.

---

## Objetivo

Criar uma nova seção no Jake OS (`#ingles`) com três abas:
1. **Palavra do Dia** — vocabulário temático com áudio
2. **Conversar** — prática de conversação com IA
3. **Progresso** — streak e histórico

---

## Arquitetura

### Backend (`app.py`)
Novas rotas Flask:

| Rota | Método | Função |
|---|---|---|
| `/api/ingles/palavra-do-dia` | GET | Retorna/gera a palavra do dia |
| `/api/ingles/palavra/audio` | GET | Retorna áudio TTS da palavra (OpenAI TTS, voz onyx) |
| `/api/ingles/sessoes` | GET | Lista sessões de conversa (últimas 10) |
| `/api/ingles/sessoes` | POST | Cria nova sessão |
| `/api/ingles/sessoes/<id>/chat` | POST | Envia mensagem na sessão |
| `/api/ingles/progresso` | GET | Streak, contadores, calendário |
| `/api/ingles/atividade` | POST | Registra atividade do usuário |

Adicionar `_init_ingles_tables()` chamada no startup do app (padrão de `_init_nutricao_tables()`).

### Banco de Dados (Neon/PostgreSQL)

**`ingles_palavras`**
```sql
id SERIAL PRIMARY KEY,
palavra TEXT NOT NULL,
classe_gramatical TEXT,       -- noun, verb, adj, etc.
definicao_pt TEXT NOT NULL,
exemplo_en TEXT NOT NULL,
fonetica TEXT,                -- IPA ex: /ˈmɑːrkɪtɪŋ/
categoria TEXT,               -- marketing, negocios, cotidiano, tecnologia
data_exibicao DATE UNIQUE,    -- uma palavra por dia
estudada BOOLEAN DEFAULT FALSE,
created_at TIMESTAMP DEFAULT NOW()
```

**`ingles_sessoes`**
```sql
id SERIAL PRIMARY KEY,
tema TEXT,
mensagens JSONB DEFAULT '[]',
created_at TIMESTAMP DEFAULT NOW()
```
Política de retenção: manter as últimas 10 sessões (o GET `/api/ingles/sessoes` retorna as 10 mais recentes; sem auto-delete por ora).

**`ingles_atividades`**
```sql
id SERIAL PRIMARY KEY,
tipo VARCHAR(30),             -- 'word_studied', 'audio_played', 'message_sent'
data_atividade DATE NOT NULL,
created_at TIMESTAMP DEFAULT NOW()
```
Usada para cálculo do streak e calendário de progresso.

### Frontend
- `static/js/ingles.js` — lógica do módulo
- Bloco `<style id="ingles-styles">` inline no `dashboard.html`
- Seção `<section class="page" id="page-ingles">` com 3 abas
- Item na sidebar: `🇺🇸 Inglês` com `data-page="ingles"`
- `app.js`: adicionar `"ingles"` ao array `valid` e callback `initIngles`

---

## Aba 1 — Palavra do Dia

**Geração:** Claude (`claude-sonnet-4-6`) gera a palavra com JSON estruturado. Persiste no banco por `data_exibicao`. Se a palavra do dia já existir no banco, retorna a existente (sem chamar Claude novamente). Em caso de falha, retorna erro 503.

**Rotação de categorias:** calculada por `DAY_OF_YEAR % 4` → [marketing, negocios, cotidiano, tecnologia]. Determinístico, sem estado extra no banco.

**UI:**
- Palavra em destaque (fonte Orbitron, grande)
- Badge de classe gramatical
- Definição em PT
- Exemplo em inglês em itálico
- Pronúncia fonética IPA
- Botão 🔊 → chama `/api/ingles/palavra/audio` → toca áudio via `<audio>` + registra atividade `audio_played`
- Botão "Marcar como estudada" → atualiza `estudada=TRUE` + registra atividade `word_studied`

---

## Aba 2 — Conversar

**Fluxo:**
1. Ao abrir (ou criar nova sessão), gera tema do dia via `DAY_OF_YEAR % 5` → [marketing, viagem, negocios, cotidiano, tecnologia]
2. Sistema prompt instrui Claude a: responder em inglês, nível intermediário-avançado, correção dupla (modela a forma correta naturalmente na resposta sem apontar o erro explicitamente), variar entre chat livre e tópico proposto
3. Histórico da sessão armazenado em `ingles_sessoes.mensagens` (JSONB)
4. Botão "Nova sessão" cria nova entrada no banco e limpa o chat
5. Cada mensagem enviada registra atividade `message_sent`

**Correção dupla — exemplo:**
> User: "I work with trafic paid since 3 years"
> IA: "That's impressive! I've been working with paid traffic for 3 years too..."

**System prompt base:**
```
You are an English conversation partner for a Brazilian digital marketer at intermediate level.
Your job: have natural, engaging conversations in English.
When the user makes grammar or vocabulary mistakes, naturally use the correct form in your response without explicitly pointing it out.
Topics rotate between: marketing/ads, travel, business, tech, daily life.
Keep messages short (2-4 sentences). Ask follow-up questions to keep the conversation going.
Today's suggested topic: {tema_do_dia}
```

---

## Aba 3 — Progresso

**Componentes:**
- Streak atual (dias consecutivos com atividade em `ingles_atividades`)
- Total de palavras estudadas (`COUNT WHERE tipo='word_studied'`)
- Mini calendário do mês atual (dias com atividade marcados em azul; mês vazio = mostra "Comece hoje!")
- Lista das últimas 5 sessões (data + tema)

**Lógica de streak:** qualquer atividade conta. Query: dias distintos com atividade em `ingles_atividades`, contando regressivamente a partir de hoje sem gap > 1 dia.

---

## Padrões de UI (Jake OS)

Seguir o padrão existente:
- Fundo escuro `#0d1117`, glassmorphism `rgba(255,255,255,0.04)`
- Cor primária: `#00e5ff`
- Fontes: Orbitron (títulos), Rajdhani (labels), sistema (corpo)
- Botões: border `rgba(0,229,255,0.3)`, hover com opacidade aumentada
- Cards com `border-radius: 12px`, `backdrop-filter: blur(12px)`

---

## Decisões de design

- **Sem exercícios de múltipla escolha** — Bruno preferiu conversa e vocabulário, não gramática formal
- **Correção dupla** (não explícita) — mais natural, mantém fluxo, pedagogicamente eficaz
- **Claude para geração de palavras** — gera contexto rico (IPA, exemplo, categoria) vs. banco de palavras estático
- **OpenAI TTS** (voz onyx) para áudio — já disponível no projeto, qualidade boa
- **Uma palavra por dia** — consistência > volume
- **Rotação determinística por dia do ano** — sem estado extra, sem ambiguidade
- **Tabela `ingles_atividades`** — base para streak e calendário, extensível para futuras métricas
