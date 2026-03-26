# Engenheiro de Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir a página `#prompts` do Jake OS por um chat conversacional de engenharia de prompts com histórico de sessões persistido no Neon/PostgreSQL.

**Architecture:** Full backend — toda a IA (claude-sonnet-4-6) e persistência passam pelo Flask. O JS faz fetch para rotas internas. A `ANTHROPIC_API_KEY` nunca fica exposta no browser. Layout 2 colunas: sidebar de sessões (estilo ChatGPT) + área de chat.

**Tech Stack:** Python/Flask, Anthropic SDK, Neon PostgreSQL, Vanilla JS (IIFE), CSS custom properties (dark theme)

**Spec:** `docs/superpowers/specs/2026-03-25-engenheiro-de-prompts-design.md`

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `jake_desktop/app.py` | Modificar | 6 novas rotas Flask para sessões/chat/título |
| `jake_desktop/static/js/prompts.js` | Criar | Toda a lógica frontend do módulo |
| `jake_desktop/templates/dashboard.html` | Modificar (3 pontos) | Nav item + `#page-prompts` div + script tag |
| `jake_desktop/static/css/style.css` | Modificar | Estilos do módulo (sidebar, chat, prompt-box) |

---

## Task 1: Criar tabelas no Neon

**Files:**
- Executar SQL diretamente na console Neon (sem modificar arquivos)

- [ ] **Step 1: Rodar SQL no Neon**

Conecte na console do Neon (ou via psql com `DATABASE_URL`) e execute:

```sql
CREATE TABLE IF NOT EXISTS prompt_sessions (
  id            SERIAL PRIMARY KEY,
  titulo        TEXT,
  criado_em     TIMESTAMPTZ DEFAULT NOW(),
  atualizado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prompt_messages (
  id         SERIAL PRIMARY KEY,
  session_id INT REFERENCES prompt_sessions(id) ON DELETE CASCADE,
  role       TEXT NOT NULL,
  content    TEXT NOT NULL,
  criado_em  TIMESTAMPTZ DEFAULT NOW()
);
```

- [ ] **Step 2: Verificar criação**

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('prompt_sessions', 'prompt_messages');
```

Esperado: 2 linhas retornadas.

- [ ] **Step 3: Commit (sem arquivos novos ainda, só documentação)**

```bash
git -C /root add -A
git -C /root commit -m "chore: tabelas prompt_sessions e prompt_messages criadas no Neon"
```

---

## Task 2: Rotas Flask — CRUD de sessões e chat

**Files:**
- Modify: `jake_desktop/app.py` (adicionar após as rotas existentes, antes do bloco `_local_ip`)

- [ ] **Step 1: Localizar ponto de inserção no app.py**

```bash
grep -n "_local_ip\|def _local_ip" /root/jake_desktop/app.py
```

Anote o número da linha. Vamos inserir as novas rotas ANTES dessa função.

- [ ] **Step 2: Adicionar system prompt e rotas no app.py**

Inserir o bloco abaixo na linha encontrada (antes de `def _local_ip`):

```python
# ── Engenheiro de Prompts ─────────────────────────────────────────────────────

_PROMPT_ENGINEER_SYSTEM = """Você é um Engenheiro de Prompts Sênior com mais de 20 anos de experiência criando prompts estruturados de alta performance para os mais diversos contextos: marketing, tecnologia, educação, jurídico, criativo, negócios e muito mais.

Seu fluxo de trabalho tem DUAS ETAPAS obrigatórias:

---

**ETAPA 1 — PERGUNTAS ESTRATÉGICAS**

Quando o usuário apresentar uma ideia ou projeto, você NUNCA gera o prompt direto. Primeiro, você faz de 5 a 7 perguntas estratégicas e objetivas para entender:
- O objetivo principal do prompt
- O público-alvo ou destinatário
- O contexto de uso (plataforma, ferramenta, situação)
- Tom e linguagem desejados
- Restrições ou requisitos específicos
- Exemplos de resultados esperados (se houver)

Formate as perguntas assim (JSON obrigatório):
{"type":"questions","questions":["Pergunta 1?","Pergunta 2?","Pergunta 3?","Pergunta 4?","Pergunta 5?"]}

---

**ETAPA 2 — GERAÇÃO DO PROMPT ESTRUTURADO**

Após o usuário responder, gere o prompt final:

{"type":"prompt","title":"Título descritivo curto (máx 50 chars)","prompt":"O prompt completo e estruturado aqui, rico em detalhes, com persona se aplicável, contexto, formato de saída esperado, restrições e exemplos relevantes."}

---

**REGRAS:**
- Responda SEMPRE em português brasileiro
- Nunca gere o prompt sem fazer as perguntas primeiro
- Se a resposta for insuficiente, faça perguntas de refinamento (mesma estrutura JSON)
- Fora dos JSONs, pode conversar normalmente — o texto será exibido como mensagem normal"""


@app.route("/api/prompts/sessoes", methods=["GET"])
@login_required
def prompts_listar_sessoes():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, titulo, criado_em, atualizado_em FROM prompt_sessions "
            "ORDER BY atualizado_em DESC LIMIT 100"
        )
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify({"sessoes": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/prompts/sessoes", methods=["POST"])
@login_required
def prompts_criar_sessao():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO prompt_sessions (titulo) VALUES (NULL) RETURNING id, criado_em, atualizado_em"
        )
        row = dict(cur.fetchone())
        conn.commit()
        return jsonify(row)
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/prompts/sessoes/<int:sid>/mensagens", methods=["GET"])
@login_required
def prompts_listar_mensagens(sid):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, role, content, criado_em FROM prompt_messages "
            "WHERE session_id = %s ORDER BY criado_em ASC",
            (sid,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify({"mensagens": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/prompts/sessoes/<int:sid>/chat", methods=["POST"])
@login_required
def prompts_chat(sid):
    d = request.get_json() or {}
    user_msg = (d.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Mensagem vazia"}), 400

    conn = _get_db()
    try:
        cur = conn.cursor()

        # Verifica que a sessão existe
        cur.execute("SELECT id FROM prompt_sessions WHERE id = %s", (sid,))
        if not cur.fetchone():
            return jsonify({"error": "Sessão não encontrada"}), 404

        # Carrega histórico
        cur.execute(
            "SELECT role, content FROM prompt_messages "
            "WHERE session_id = %s ORDER BY criado_em ASC",
            (sid,)
        )
        history = [{"role": r["role"], "content": r["content"]} for r in cur.fetchall()]

        # Adiciona nova mensagem do usuário ao histórico
        history.append({"role": "user", "content": user_msg})

        # Chama Claude
        client = _anthropic_client_46()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_PROMPT_ENGINEER_SYSTEM,
            messages=history
        )
        reply = response.content[0].text

        # Salva par user + assistant
        cur.execute(
            "INSERT INTO prompt_messages (session_id, role, content) VALUES (%s, %s, %s)",
            (sid, "user", user_msg)
        )
        cur.execute(
            "INSERT INTO prompt_messages (session_id, role, content) VALUES (%s, %s, %s)",
            (sid, "assistant", reply)
        )

        # Atualiza atualizado_em da sessão
        cur.execute(
            "UPDATE prompt_sessions SET atualizado_em = NOW() WHERE id = %s", (sid,)
        )
        conn.commit()
        return jsonify({"reply": reply})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/prompts/sessoes/<int:sid>/titulo", methods=["PATCH"])
@login_required
def prompts_atualizar_titulo(sid):
    d = request.get_json() or {}
    titulo = (d.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"error": "Título vazio"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prompt_sessions SET titulo = %s, atualizado_em = NOW() WHERE id = %s",
            (titulo, sid)
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/prompts/sessoes/<int:sid>", methods=["DELETE"])
@login_required
def prompts_deletar_sessao(sid):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM prompt_sessions WHERE id = %s", (sid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
```

- [ ] **Step 3: Verificar sintaxe Python**

```bash
cd /root/jake_desktop && /root/venv/bin/python3 -c "import ast; ast.parse(open('app.py').read()); print('OK')"
```

Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git -C /root add jake_desktop/app.py
git -C /root commit -m "feat: rotas Flask Engenheiro de Prompts (sessoes + chat)"
```

---

## Task 3: HTML — nav item + página `#page-prompts`

**Files:**
- Modify: `jake_desktop/templates/dashboard.html`

- [ ] **Step 1: Adicionar nav item**

Localizar a linha com `data-page="carrossel"`:
```bash
grep -n 'data-page="carrossel"' /root/jake_desktop/templates/dashboard.html
```

Após o bloco do nav item "carrossel", adicionar:

```html
        <a class="nav-item" data-page="prompts" href="#">
          <span class="nav-icon">🧠</span>
          <span class="nav-label">Prompts</span>
        </a>
```

- [ ] **Step 2: Adicionar seção `#page-prompts`**

Localizar a linha com `<!-- ROTINAS & AGENDA` (final do conteúdo, antes do `</main>`):
```bash
grep -n "ROTINAS\|AGENDA" /root/jake_desktop/templates/dashboard.html
```

Antes desse comentário, inserir:

```html
      <!-- ENGENHEIRO DE PROMPTS ──────────────────────────── -->
      <section class="page" id="page-prompts">
        <div class="pe-layout">

          <!-- Sidebar de sessões -->
          <aside class="pe-sidebar" id="peSidebar">
            <div class="pe-sidebar-header">
              <span class="pe-sidebar-title">🧠 Conversas</span>
              <button class="pe-new-btn" id="peNewBtn" title="Nova conversa">＋</button>
            </div>
            <div class="pe-session-list" id="peSessionList">
              <!-- preenchido por JS -->
            </div>
          </aside>

          <!-- Área de chat -->
          <div class="pe-chat-wrap">

            <!-- Toggle sidebar mobile -->
            <button class="pe-sidebar-toggle" id="peSidebarToggle" title="Sessões">☰</button>

            <!-- Mensagens -->
            <div class="pe-chat-area" id="peChatArea">
              <!-- preenchido por JS -->
            </div>

            <!-- Input -->
            <div class="pe-input-area">
              <textarea
                id="peInput"
                class="pe-textarea"
                placeholder="Descreva sua ideia ou projeto..."
                rows="1"
              ></textarea>
              <button class="pe-send-btn" id="peSendBtn">➤</button>
            </div>
            <p class="pe-hint">Enter para enviar · Shift+Enter para nova linha</p>

          </div><!-- /.pe-chat-wrap -->
        </div><!-- /.pe-layout -->
      </section>
```

- [ ] **Step 3: Adicionar script tag**

No final do `dashboard.html`, antes de `</body>`, após a última tag `<script>`:
```html
  <script src="{{ url_for('static', filename='js/prompts.js') }}"></script>
```

- [ ] **Step 4: Verificar HTML**

```bash
grep -n "page-prompts\|pe-layout\|prompts.js\|data-page=\"prompts\"" /root/jake_desktop/templates/dashboard.html
```

Esperado: 4+ linhas encontradas.

- [ ] **Step 5: Commit**

```bash
git -C /root add jake_desktop/templates/dashboard.html
git -C /root commit -m "feat: nav item e seção #page-prompts no dashboard"
```

---

## Task 4: CSS — estilos do módulo

**Files:**
- Modify: `jake_desktop/static/css/style.css` (adicionar ao final)

- [ ] **Step 1: Adicionar estilos ao final de style.css**

```css
/* ── Engenheiro de Prompts ────────────────────────────────────── */
.pe-layout {
  display: flex;
  height: calc(100vh - 60px);
  overflow: hidden;
}

/* Sidebar */
.pe-sidebar {
  width: 240px;
  min-width: 240px;
  background: var(--surface, #111118);
  border-right: 1px solid var(--border, rgba(255,255,255,0.08));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: transform 0.25s ease;
}
.pe-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border, rgba(255,255,255,0.08));
  flex-shrink: 0;
}
.pe-sidebar-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--text-muted, rgba(176,190,197,0.8));
  text-transform: uppercase;
}
.pe-new-btn {
  background: rgba(0,212,255,0.1);
  border: 1px solid rgba(0,212,255,0.3);
  color: #00d4ff;
  width: 28px; height: 28px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s;
}
.pe-new-btn:hover { background: rgba(0,212,255,0.2); }
.pe-session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.pe-session-list::-webkit-scrollbar { width: 3px; }
.pe-session-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
.pe-session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}
.pe-session-item:hover { background: rgba(255,255,255,0.04); }
.pe-session-item.active {
  border-left-color: #00d4ff;
  background: rgba(0,212,255,0.06);
}
.pe-session-info { flex: 1; overflow: hidden; }
.pe-session-title {
  font-size: 13px;
  color: var(--text, #e0f7fa);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pe-session-date {
  font-size: 11px;
  color: var(--text-muted, rgba(176,190,197,0.5));
  margin-top: 2px;
}
.pe-session-del {
  background: none;
  border: none;
  color: rgba(176,190,197,0.3);
  cursor: pointer;
  font-size: 14px;
  padding: 2px 4px;
  border-radius: 4px;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
  flex-shrink: 0;
}
.pe-session-item:hover .pe-session-del { opacity: 1; }
.pe-session-del:hover { color: #ff6b6b; }
.pe-empty-sidebar {
  padding: 20px 16px;
  font-size: 12px;
  color: rgba(176,190,197,0.4);
  text-align: center;
  line-height: 1.6;
}

/* Chat area */
.pe-chat-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}
.pe-sidebar-toggle {
  display: none;
  position: absolute;
  top: 12px; left: 12px;
  z-index: 10;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  color: var(--text, #e0f7fa);
  width: 36px; height: 36px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
}
.pe-chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 820px;
  width: 100%;
  margin: 0 auto;
  align-self: stretch;
}
.pe-chat-area::-webkit-scrollbar { width: 4px; }
.pe-chat-area::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

/* Messages */
.pe-msg { display: flex; gap: 10px; animation: peSlideUp 0.25s ease; }
@keyframes peSlideUp {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
.pe-msg.user { flex-direction: row-reverse; }
.pe-msg-avatar {
  width: 32px; height: 32px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; flex-shrink: 0; margin-top: 2px;
}
.pe-msg.agent .pe-msg-avatar {
  background: linear-gradient(135deg, rgba(0,212,255,0.3), rgba(0,212,255,0.1));
  border: 1px solid rgba(0,212,255,0.3);
}
.pe-msg.user .pe-msg-avatar {
  background: rgba(255,255,255,0.07);
  border: 1px solid rgba(255,255,255,0.1);
}
.pe-bubble {
  max-width: 78%;
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.65;
}
.pe-msg.agent .pe-bubble {
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(255,255,255,0.07);
  border-top-left-radius: 4px;
  color: #cfd8dc;
}
.pe-msg.user .pe-bubble {
  background: rgba(0,212,255,0.08);
  border: 1px solid rgba(0,212,255,0.15);
  border-top-right-radius: 4px;
  color: #e0f7fa;
}

/* Questions list */
.pe-questions {
  margin-top: 10px;
  display: flex; flex-direction: column; gap: 7px;
}
.pe-question-item {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  padding: 9px 13px;
  font-size: 13px;
  color: #b0bec5;
}
.pe-question-item span { color: #00d4ff; font-weight: 700; margin-right: 6px; }

/* Prompt result box */
.pe-prompt-box {
  background: rgba(0,30,20,0.8);
  border: 1px solid rgba(0,212,100,0.4);
  border-radius: 10px;
  padding: 14px 16px;
  margin-top: 10px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.7;
  color: #a8f0c8;
  white-space: pre-wrap;
}
.pe-prompt-box-header {
  font-family: inherit;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #4ecca3;
  margin-bottom: 10px;
  display: flex; align-items: center; justify-content: space-between;
}
.pe-copy-btn {
  background: transparent;
  border: 1px solid rgba(78,204,163,0.5);
  color: #4ecca3;
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.pe-copy-btn:hover { background: rgba(78,204,163,0.15); }

/* Typing indicator */
.pe-typing { display: flex; gap: 5px; align-items: center; padding: 8px 0; }
.pe-typing span {
  width: 7px; height: 7px;
  background: rgba(0,212,255,0.4);
  border-radius: 50%;
  animation: peBounce 1.2s infinite;
}
.pe-typing span:nth-child(2) { animation-delay: 0.2s; }
.pe-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes peBounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
}

/* Empty state */
.pe-empty-state {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 16px; color: rgba(176,190,197,0.4); text-align: center;
  padding: 40px;
}
.pe-empty-state .pe-empty-icon { font-size: 48px; opacity: 0.5; }
.pe-empty-state p { font-size: 14px; line-height: 1.6; }
.pe-empty-start-btn {
  background: rgba(0,212,255,0.1);
  border: 1px solid rgba(0,212,255,0.3);
  color: #00d4ff;
  padding: 10px 24px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}
.pe-empty-start-btn:hover { background: rgba(0,212,255,0.2); }

/* Input area */
.pe-input-area {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 12px 20px;
  border-top: 1px solid rgba(255,255,255,0.07);
  background: rgba(0,0,0,0.2);
  max-width: 820px;
  width: 100%;
  margin: 0 auto;
  align-self: stretch;
}
.pe-textarea {
  flex: 1;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  color: #e0f7fa;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
  padding: 11px 14px;
  resize: none;
  outline: none;
  min-height: 46px;
  max-height: 150px;
  transition: border-color 0.2s;
}
.pe-textarea:focus { border-color: rgba(0,212,255,0.4); }
.pe-textarea::placeholder { color: rgba(176,190,197,0.35); }
.pe-send-btn {
  width: 46px; height: 46px;
  background: linear-gradient(135deg, rgba(0,212,255,0.3), rgba(0,212,255,0.1));
  border: 1px solid rgba(0,212,255,0.4);
  border-radius: 12px;
  color: #00d4ff;
  cursor: pointer;
  font-size: 18px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s, transform 0.1s;
  flex-shrink: 0;
}
.pe-send-btn:hover { background: rgba(0,212,255,0.25); }
.pe-send-btn:active { transform: scale(0.95); }
.pe-send-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.pe-hint {
  font-size: 11px;
  color: rgba(176,190,197,0.3);
  text-align: center;
  padding: 4px 0 10px;
}

/* Mobile */
@media (max-width: 768px) {
  .pe-sidebar {
    position: fixed;
    top: 0; left: 0; bottom: 0;
    z-index: 300;
    transform: translateX(-100%);
  }
  .pe-sidebar.open { transform: translateX(0); }
  .pe-sidebar-toggle { display: flex; align-items: center; justify-content: center; }
  .pe-chat-area { padding-top: 60px; }
}
```

- [ ] **Step 2: Commit**

```bash
git -C /root add jake_desktop/static/css/style.css
git -C /root commit -m "feat: CSS módulo Engenheiro de Prompts"
```

---

## Task 5: JavaScript — `prompts.js`

**Files:**
- Create: `jake_desktop/static/js/prompts.js`

- [ ] **Step 1: Criar o arquivo**

```javascript
(function () {
  'use strict';

  // ── Estado ────────────────────────────────────────────────────
  var currentSessionId = null;
  var isWaiting = false;
  var primeiraMsg = null; // primeira mensagem do usuário na sessão atual (para fallback de título)

  // ── Mensagem de boas-vindas (exibida localmente, sem chamar API) ──
  var WELCOME_MSG = 'Olá! Sou seu <strong>Engenheiro de Prompts Sênior</strong>, com mais de 20 anos estruturando prompts de alta performance.\n\nMeu processo: você me apresenta uma ideia ou projeto, eu faço de <strong>5 a 7 perguntas estratégicas</strong> para entender o contexto, e então gero um <strong>prompt estruturado e assertivo</strong> pronto para uso.\n\nMe conta: <strong>qual é o projeto ou ideia que você quer transformar em prompt?</strong>';

  // ── Refs DOM ──────────────────────────────────────────────────
  function el(id) { return document.getElementById(id); }

  // ── Inicialização ─────────────────────────────────────────────
  function init() {
    // Só inicializa quando a página prompts está ativa
    var page = document.getElementById('page-prompts');
    if (!page) return;

    el('peNewBtn').addEventListener('click', novaConversa);
    el('peSendBtn').addEventListener('click', enviarMensagem);
    el('peInput').addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviarMensagem(); }
    });
    el('peInput').addEventListener('input', autoResize);
    el('peSidebarToggle').addEventListener('click', function () {
      el('peSidebar').classList.toggle('open');
    });

    carregarSessoes();
  }

  // ── Sessões ───────────────────────────────────────────────────
  function carregarSessoes() {
    fetch('/api/prompts/sessoes')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderSidebar(data.sessoes || []);
      })
      .catch(function () {
        el('peSessionList').innerHTML = '<div class="pe-empty-sidebar">Erro ao carregar sessões.</div>';
      });
  }

  function renderSidebar(sessoes) {
    var list = el('peSessionList');
    if (!sessoes.length) {
      list.innerHTML = '<div class="pe-empty-sidebar">Nenhuma conversa ainda.<br>Clique em ＋ para começar.</div>';
      mostrarEstadoVazio();
      return;
    }
    list.innerHTML = sessoes.map(function (s) {
      var titulo = s.titulo || 'Nova conversa';
      var data = new Date(s.atualizado_em).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
      var ativo = s.id === currentSessionId ? ' active' : '';
      return '<div class="pe-session-item' + ativo + '" data-id="' + s.id + '">' +
        '<div class="pe-session-info">' +
        '<div class="pe-session-title">' + escapeHtml(titulo) + '</div>' +
        '<div class="pe-session-date">' + data + '</div>' +
        '</div>' +
        '<button class="pe-session-del" data-del="' + s.id + '" title="Deletar">🗑</button>' +
        '</div>';
    }).join('');

    list.querySelectorAll('.pe-session-item').forEach(function (item) {
      item.addEventListener('click', function (e) {
        if (e.target.closest('[data-del]')) return;
        abrirSessao(parseInt(this.dataset.id));
      });
    });

    list.querySelectorAll('[data-del]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        deletarSessao(parseInt(this.dataset.del));
      });
    });
  }

  function novaConversa() {
    fetch('/api/prompts/sessoes', { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { alert('Erro: ' + data.error); return; }
        currentSessionId = data.id;
        primeiraMsg = null; // reset para nova sessão
        limparChat();
        adicionarMensagem('agent', WELCOME_MSG);
        carregarSessoes();
      });
  }

  function abrirSessao(id) {
    currentSessionId = id;
    limparChat();

    // Atualiza destaque na sidebar
    document.querySelectorAll('.pe-session-item').forEach(function (el) {
      el.classList.toggle('active', parseInt(el.dataset.id) === id);
    });

    fetch('/api/prompts/sessoes/' + id + '/mensagens')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var msgs = data.mensagens || [];
        // Sessão existente: nunca exibe mensagem de boas-vindas,
        // mesmo que ainda não tenha mensagens (ex: clicou na sidebar antes de digitar)
        msgs.forEach(function (m) {
          adicionarMensagem(m.role === 'user' ? 'user' : 'agent', m.content);
        });
        if (!msgs.length) {
          mostrarEstadoVazio();
        }
        scrollBottom();
      });
  }

  function deletarSessao(id) {
    if (!confirm('Deletar esta conversa?')) return;
    fetch('/api/prompts/sessoes/' + id, { method: 'DELETE' })
      .then(function (r) { return r.json(); })
      .then(function () {
        if (currentSessionId === id) {
          currentSessionId = null;
          limparChat();
          mostrarEstadoVazio();
        }
        carregarSessoes();
      });
  }

  // ── Chat ──────────────────────────────────────────────────────
  function enviarMensagem() {
    if (isWaiting || !currentSessionId) return;
    var input = el('peInput');
    var texto = input.value.trim();
    if (!texto) return;

    input.value = '';
    input.style.height = 'auto';
    isWaiting = true;
    el('peSendBtn').disabled = true;

    // Registra primeira mensagem para fallback de título
    if (!primeiraMsg) primeiraMsg = texto;

    adicionarMensagem('user', texto);
    mostrarTyping();

    fetch('/api/prompts/sessoes/' + currentSessionId + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: texto })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        removerTyping();
        if (data.error) {
          adicionarMensagem('agent', '⚠️ Erro ao processar. Tente novamente.');
        } else {
          adicionarMensagem('agent', data.reply);
          // Gerar título se for prompt final
          tentarGerarTitulo(data.reply);
        }
      })
      .catch(function () {
        removerTyping();
        adicionarMensagem('agent', '⚠️ Erro de conexão. Tente novamente.');
      })
      .finally(function () {
        isWaiting = false;
        el('peSendBtn').disabled = false;
      });
  }

  function tentarGerarTitulo(reply) {
    // Só gera título se a sessão ainda não tem título
    var itemAtivo = document.querySelector('.pe-session-item.active .pe-session-title');
    if (itemAtivo && itemAtivo.textContent !== 'Nova conversa') return;

    var json = extrairJson(reply);
    if (!json || json.type !== 'prompt') return;

    var titulo = (json.title || '').trim();
    if (!titulo) {
      // Fallback: primeiras 40 chars da PRIMEIRA mensagem do usuário na sessão
      var src = primeiraMsg || '';
      titulo = src.substring(0, 40);
      if (src.length > 40) titulo += '...';
    }
    if (!titulo) return;

    fetch('/api/prompts/sessoes/' + currentSessionId + '/titulo', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ titulo: titulo })
    }).then(function () { carregarSessoes(); });
  }

  // ── Renderização de mensagens ─────────────────────────────────
  function adicionarMensagem(role, content) {
    var area = el('peChatArea');

    // Remove estado vazio se existir
    var empty = area.querySelector('.pe-empty-state');
    if (empty) empty.remove();

    var div = document.createElement('div');
    div.className = 'pe-msg ' + role;

    var avatar = document.createElement('div');
    avatar.className = 'pe-msg-avatar';
    avatar.textContent = role === 'agent' ? '🧠' : '👤';

    var bubble = document.createElement('div');
    bubble.className = 'pe-bubble';

    if (role === 'agent') {
      bubble.innerHTML = renderizarAgente(content);
    } else {
      bubble.textContent = content;
    }

    div.appendChild(avatar);
    div.appendChild(bubble);
    area.appendChild(div);
    scrollBottom();
  }

  function renderizarAgente(texto) {
    var json = extrairJson(texto);

    if (json && json.type === 'questions' && Array.isArray(json.questions)) {
      var antes = texto.substring(0, texto.indexOf('{')).trim();
      var html = '';
      if (antes) html += '<p>' + formatarTexto(antes) + '</p>';
      html += '<p style="margin-top:' + (antes ? '10px' : '0') + '">Para criar o melhor prompt possível, preciso entender melhor o projeto:</p>';
      html += '<div class="pe-questions">' +
        json.questions.map(function (q, i) {
          return '<div class="pe-question-item"><span>' + (i + 1) + '.</span>' + escapeHtml(q) + '</div>';
        }).join('') +
        '</div>';
      return html;
    }

    if (json && json.type === 'prompt' && json.prompt) {
      var antes2 = texto.substring(0, texto.indexOf('{')).trim();
      var html2 = '';
      if (antes2) html2 += '<p>' + formatarTexto(antes2) + '</p>';
      html2 += '<p style="margin-top:' + (antes2 ? '10px' : '0') + '">✅ <strong>Prompt gerado com sucesso!</strong></p>';
      html2 += '<div class="pe-prompt-box">' +
        '<div class="pe-prompt-box-header">' +
        '<span>📋 ' + escapeHtml(json.title || 'PROMPT FINAL') + '</span>' +
        '<button class="pe-copy-btn" onclick="(function(btn,txt){navigator.clipboard.writeText(txt).then(function(){btn.textContent=\'✓ Copiado!\';setTimeout(function(){btn.textContent=\'Copiar\';},2000);})})(this,' + JSON.stringify(json.prompt) + ')">Copiar</button>' +
        '</div>' +
        escapeHtml(json.prompt) +
        '</div>';
      return html2;
    }

    // Texto simples (incluindo fallback se JSON inválido)
    return formatarTexto(texto);
  }

  function extrairJson(texto) {
    // Procura o bloco JSON mais externo (robusto a qualquer ordenação de chaves)
    var start = texto.indexOf('{');
    if (start === -1) return null;
    // Encontra o fechamento correto contando chaves
    var depth = 0, end = -1;
    for (var i = start; i < texto.length; i++) {
      if (texto[i] === '{') depth++;
      else if (texto[i] === '}') { depth--; if (depth === 0) { end = i; break; } }
    }
    if (end === -1) return null;
    try {
      var obj = JSON.parse(texto.substring(start, end + 1));
      if (obj.type === 'questions' || obj.type === 'prompt') return obj;
      return null;
    } catch (e) { return null; }
  }

  function formatarTexto(texto) {
    return escapeHtml(texto)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Typing indicator ──────────────────────────────────────────
  function mostrarTyping() {
    var area = el('peChatArea');
    var div = document.createElement('div');
    div.className = 'pe-msg agent';
    div.id = 'peTyping';
    div.innerHTML = '<div class="pe-msg-avatar">🧠</div>' +
      '<div class="pe-bubble"><div class="pe-typing"><span></span><span></span><span></span></div></div>';
    area.appendChild(div);
    scrollBottom();
  }

  function removerTyping() {
    var el2 = document.getElementById('peTyping');
    if (el2) el2.remove();
  }

  // ── Helpers ───────────────────────────────────────────────────
  function limparChat() {
    el('peChatArea').innerHTML = '';
  }

  function mostrarEstadoVazio() {
    el('peChatArea').innerHTML =
      '<div class="pe-empty-state">' +
      '<div class="pe-empty-icon">🧠</div>' +
      '<p>Nenhuma conversa ainda.<br>Crie uma nova para começar.</p>' +
      '<button class="pe-empty-start-btn" onclick="document.getElementById(\'peNewBtn\').click()">＋ Nova conversa</button>' +
      '</div>';
  }

  function scrollBottom() {
    var area = el('peChatArea');
    setTimeout(function () { area.scrollTop = area.scrollHeight; }, 50);
  }

  function autoResize() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
  }

  // ── Boot ──────────────────────────────────────────────────────
  // Inicializa quando o DOM estiver pronto
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
```

- [ ] **Step 2: Commit**

```bash
git -C /root add jake_desktop/static/js/prompts.js
git -C /root commit -m "feat: prompts.js — Engenheiro de Prompts conversacional"
```

---

## Task 6: Teste e deploy

- [ ] **Step 1: Reiniciar Jake OS**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup /root/venv/bin/python3 app.py >> /tmp/jakeos.log 2>&1 &
sleep 3
tail -20 /tmp/jakeos.log
```

Esperado: sem erros de sintaxe, Flask rodando na porta 5050.

- [ ] **Step 2: Teste manual — fluxo completo**

1. Abrir `http://localhost:5050/#prompts`
2. Verificar: nav item "🧠 Prompts" visível na sidebar
3. Clicar "＋ Nova conversa" → boas-vindas aparecem → sessão criada na sidebar
4. Digitar: "Quero criar um prompt para um bot de atendimento de clínica médica"
5. Verificar: Claude retorna perguntas numeradas (formato `{"type":"questions",...}`)
6. Responder as perguntas
7. Verificar: Claude retorna prompt-box verde com botão Copiar
8. Verificar: título aparece na sidebar (ex: "Bot Atendimento Clínica")
9. Recarregar página → sessão persiste na sidebar → clicar carrega histórico correto
10. Clicar 🗑 → confirmar → sessão removida

- [ ] **Step 3: Verificar tabelas no Neon**

```sql
SELECT COUNT(*) FROM prompt_sessions;
SELECT COUNT(*) FROM prompt_messages;
```

Esperado: números correspondentes às mensagens trocadas no teste.

- [ ] **Step 4: Commit final**

```bash
git -C /root add -A
git -C /root commit -m "feat: Engenheiro de Prompts completo no Jake OS"
```
