# Planejador de Campanhas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar aba "Planejador" no Jake OS — chat em linguagem natural onde o usuário descreve uma campanha Meta Ads, Claude extrai os parâmetros progressivamente, mostra card de confirmação e executa a criação via SSE.

**Architecture:** 4 endpoints Flask novos em `app.py` (interpretar, transcrever, subir POST, subir/stream GET/SSE) + IIFE `planejador.js` com state machine de 4 estados + `planejador.css`. O endpoint de stream reutiliza as helpers `criar_campanha`, `criar_conjunto`, `criar_anuncio` e `upload_imagem` já existentes em `meta_api.py`.

**Tech Stack:** Python/Flask, `anthropic` SDK (`claude-sonnet-4-6`), OpenAI Whisper-1, Meta Ads API v21.0, vanilla JS ES5 IIFE, Google Drive API v3.

---

## Context for Implementers

### Arquivos-chave
- Flask app: `/root/jake_desktop/app.py` (7862 linhas — ler em blocos, nunca inteiro)
- Meta API helpers: `/root/meta/meta_api.py`
- Exemplos de IIFE: `/root/jake_desktop/static/js/gestor.js`, `drive-batch.js`
- CSS existente de referência: `/root/jake_desktop/static/css/gestor.css`
- Dashboard HTML: `/root/jake_desktop/templates/dashboard.html`
- Router SPA: `/root/jake_desktop/static/js/app.js`

### Padrões de app.py
```python
# Helper DB — retorna RealDictCursor (acesso por nome de coluna)
conn = _get_db()

# Client Anthropic
client = _anthropic_client()

# Token inválido → obter via os.getenv diretamente (não _resolve_token do meta_api)
_VALID_TOKEN_KEYS  # set definido em app.py:43
_TMP_DIR = "/tmp"  # app.py:45
_lote_payloads = {}  # dict em memória para dois fases SSE — reutilizável

# Formato SSE
def _sse(data: dict) -> str:
    return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"
```

### Assinaturas das helpers meta_api.py
```python
# Atenção: ordem dos argumentos importa!
criar_campanha(token, account_id, campanha_tipo, nome, orcamento, cbo=True)
# campanha_tipo = "MESSAGES" | "ENGAGEMENT" | "PURCHASE"
# cbo=True → orçamento na campanha (MESSAGES); cbo=False → no adset (ENGAGEMENT/PURCHASE)

criar_conjunto(token, account_id, campaign_id, campanha_tipo, publico, localizacao,
               orcamento=None, optimization_goal=None, pixel_id=None, nome=None)
# publico: {"idade_min": 18, "idade_max": 65, "genders": [1,2]}
# localizacao: {"paises": ["BR"], "cidades": [...]}
# orcamento: float em R$ — a função converte para centavos internamente

criar_anuncio(token, account_id, adset_id, page_id, creative_ref, titulo, texto, cta, link_url="")
# creative_ref: {"tipo": "imagem", "hash": "..."} após upload_imagem
# cta: "SEND_MESSAGE" | "LEARN_MORE" | "SHOP_NOW"

upload_imagem(token, account_id, imagem_bytes, filename) → {"hash": "..."}

deletar_objeto_meta(token, objeto_id)  # rollback
```

### Drive Batch — padrão de duas fases SSE (reutilizar)
- Fase 1: POST armazena payload em `_lote_payloads[token] = data`, retorna `{"token": token}`
- Fase 2: GET SSE `_lote_payloads.pop(token, None)` e processa
- `threading.Timer(1800, cleanup).start()` expira token em 30 min
- Download Drive: parsear `folder_id` da URL → listar arquivos via Drive v3 API → baixar por `file_id`

### Drive download — código exato do padrão existente
```python
api_key = os.getenv("GOOGLE_API_KEY", "")
# 1. Parsear folder_id
if "/folders/" in drive_link:
    folder_id = drive_link.split("/folders/")[1].split("?")[0].split("/")[0]
# 2. Listar arquivos
resp = requests.get("https://www.googleapis.com/drive/v3/files",
    params={"q": f"'{folder_id}' in parents",
            "fields": "files(id,name,mimeType)",
            "key": api_key, "pageSize": 100}, timeout=15)
files = [f for f in resp.json().get("files", []) if f.get("mimeType") in _DRIVE_MIME_EXT]
# 3. Baixar cada arquivo
dl = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}",
    params={"alt": "media", "key": api_key}, timeout=30)
file_bytes = dl.content
```

### CBO logic
```python
_CAMP_CTA = {"MESSAGES": "SEND_MESSAGE", "PURCHASE": "SHOP_NOW", "ENGAGEMENT": "LEARN_MORE"}
cbo = objetivo not in ("ENGAGEMENT", "PURCHASE")
# Se cbo=True (MESSAGES): orcamento vai para criar_campanha, criar_conjunto recebe orcamento=None
# Se cbo=False (ENGAGEMENT/PURCHASE): criar_campanha recebe orcamento=0 (ignorado), criar_conjunto recebe orcamento=orcamento_diario
```

### Onde inserir em app.py
Inserir a nova seção `# ABA PLANEJADOR DE CAMPANHAS` na linha 4948 — antes de `# FÁBRICA DE CRIATIVOS v2` (linha 4949). Grep para confirmar: `grep -n "FÁBRICA DE CRIATIVOS" /root/jake_desktop/app.py`.

### Nenhum teste automatizado no projeto
Testes manuais via curl + verificação de logs. Não criar pytest.

---

## File Structure

```
Criar:
  jake_desktop/static/js/planejador.js     # IIFE chat
  jake_desktop/static/css/planejador.css   # estilos chat

Modificar:
  jake_desktop/app.py                      # 4 endpoints novos (linha ~4948)
  jake_desktop/templates/dashboard.html   # nav + page section + tags CSS/JS
  jake_desktop/static/js/app.js           # rota #planejador
```

---

## Task 1: Flask — `/api/planejador/interpretar` + `/api/planejador/transcrever`

**Files:**
- Modify: `/root/jake_desktop/app.py` (inserir em ~linha 4948)

### O que faz
- `/interpretar`: recebe histórico + params acumulados, chama Claude, retorna JSON com resposta + params atualizados + pronto flag
- `/transcrever`: recebe arquivo de áudio, chama Whisper-1, retorna texto transcrito

- [ ] **Step 1: Localizar ponto de inserção em app.py**

```bash
grep -n "FÁBRICA DE CRIATIVOS" /root/jake_desktop/app.py
```
Expected: algo como `4949:#  FÁBRICA DE CRIATIVOS v2`

- [ ] **Step 2: Ler as 5 linhas antes da linha encontrada**

```bash
# ex: se linha é 4949, leia 4944-4949
```
Use o Read tool com `offset=4944, limit=6`. Confirmar que termina com código Python seguido de linha em branco.

- [ ] **Step 3: Inserir seção com os dois endpoints**

Inserir ANTES da linha `# ══...FÁBRICA DE CRIATIVOS`:

```python
# ══════════════════════════════════════════════════════════════════════════
#  ABA PLANEJADOR DE CAMPANHAS
# ══════════════════════════════════════════════════════════════════════════

_planejador_payloads = {}   # {token: payload} — two-phase SSE

_PLANEJADOR_OBJETIVOS = {"MESSAGES", "ENGAGEMENT", "PURCHASE"}
_PLANEJADOR_CTA       = {"MESSAGES": "SEND_MESSAGE", "PURCHASE": "SHOP_NOW", "ENGAGEMENT": "LEARN_MORE"}
_PLANEJADOR_LABEL     = {"MESSAGES": "Mensagens", "ENGAGEMENT": "Engajamento", "PURCHASE": "Conversões"}

_PLANEJADOR_PROMPT = """\
Você é o Jake, assistente de tráfego pago. Extraia parâmetros de campanha Meta Ads a partir da conversa.

CLIENTES DISPONÍVEIS:
{clientes_txt}

PARÂMETROS JÁ EXTRAÍDOS:
{params_txt}

CONVERSA:
{conversa_txt}

Retorne APENAS JSON válido (sem markdown):
{{
  "resposta": "<mensagem amigável, direta, em português — máximo 2 frases>",
  "params": {{
    "cliente_id": <int ou null>,
    "cliente_nome": "<string ou null>",
    "campanha_nome": "<string ou null — auto-gerar se null e pronto=true: '{{nome}} — {{objetivo_label}} {{mês}}/{{ano}}' onde label: MESSAGES=Mensagens, ENGAGEMENT=Engajamento, PURCHASE=Conversões>",
    "objetivo": "<MESSAGES|ENGAGEMENT|PURCHASE ou null>",
    "drive_link": "<URL do Google Drive ou null>",
    "orcamento_diario": <float ou null>,
    "publico_descricao": "<descrição livre do público ou null>",
    "copy_titulo": "<string ou null>",
    "copy_texto": "<string ou null>"
  }},
  "duvidas": ["<campo faltando>"],
  "pronto": <true somente se cliente_id, objetivo, drive_link e orcamento_diario estão todos preenchidos>
}}

Regras:
- Preserve params já extraídos — só atualize se o usuário corrigir explicitamente
- Se cliente não identificado na lista, coloque cliente_id: null e pergunte
- Se pronto=true e copy_titulo/copy_texto são null, gere copy baseado no cliente e objetivo
- Seja conciso
"""


@app.route("/api/planejador/interpretar", methods=["POST"])
@login_required
def planejador_interpretar():
    d        = request.get_json() or {}
    messages = d.get("messages", [])
    params   = d.get("params", {})

    # Buscar clientes para contexto
    conn = None
    clientes = []
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute("SELECT id, nome, agencia, campanha_tipo FROM ad_client_profiles ORDER BY nome")
        clientes = cur.fetchall()
    except Exception:
        pass
    finally:
        try: conn.close()
        except Exception: pass

    clientes_txt = "\n".join(
        f"- id={c['id']} | {c['nome']} ({c.get('agencia','')}) | tipo padrão: {c.get('campanha_tipo','')}"
        for c in clientes
    ) or "(nenhum cliente cadastrado)"

    import datetime as _dt
    params_txt  = json.dumps(params, ensure_ascii=False)
    conversa_txt = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )

    prompt = _PLANEJADOR_PROMPT.format(
        clientes_txt=clientes_txt,
        params_txt=params_txt,
        conversa_txt=conversa_txt,
    )

    try:
        client = _anthropic_client()
        if not client:
            return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()

        # Extrair JSON — Claude pode envolver em markdown
        if "```" in raw:
            import re as _re
            m = _re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
            raw = m.group(1).strip() if m else raw
        try:
            result = json.loads(raw)
        except Exception:
            import re as _re
            m = _re.search(r'\{[\s\S]*\}', raw)
            if m:
                result = json.loads(m.group(0))
            else:
                return jsonify({"error": "Não consegui interpretar. Pode reformular?"}), 200

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Erro ao interpretar: {e}"}), 500


@app.route("/api/planejador/transcrever", methods=["POST"])
@login_required
def planejador_transcrever():
    audio_file = request.files.get("audio")
    if not audio_file or not audio_file.filename:
        return jsonify({"error": "Arquivo de áudio obrigatório"}), 400

    try:
        from openai import OpenAI as _OpenAI
        oai = _OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        audio_bytes = audio_file.read()
        file_like      = io.BytesIO(audio_bytes)
        file_like.name = audio_file.filename or "audio.webm"
        transcript = oai.audio.transcriptions.create(
            model="whisper-1", file=file_like, language="pt"
        )
        return jsonify({"text": transcript.text})
    except Exception as e:
        return jsonify({"error": f"Erro na transcrição: {e}"}), 500
```

- [ ] **Step 4: Verificar que app.py sobe sem erros de sintaxe**

```bash
cd /root/jake_desktop && /root/jake_desktop/.venv/bin/python -c "import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Testar `/api/planejador/transcrever` (sem áudio real — só estrutura)**

```bash
curl -s -c /tmp/p_cookies.txt -b /tmp/p_cookies.txt -X POST http://localhost:5050/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=admin@jakeos.local&password=Jake@2024!" -o /dev/null
curl -s -c /tmp/p_cookies.txt -b /tmp/p_cookies.txt -X POST http://localhost:5050/api/planejador/transcrever \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','ok'))"
```
Expected: `Arquivo de áudio obrigatório`

- [ ] **Step 6: Testar `/api/planejador/interpretar` com mensagem simples**

```bash
curl -s -c /tmp/p_cookies.txt -b /tmp/p_cookies.txt -X POST http://localhost:5050/api/planejador/interpretar \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"oi"}],"params":{}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('resposta' in d or d.get('error'))"
```
Expected: `True`

- [ ] **Step 7: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(planejador): endpoints interpretar e transcrever"
```

---

## Task 2: Flask — `/api/planejador/subir` (POST) + `/api/planejador/subir/stream/<token>` (GET/SSE)

**Files:**
- Modify: `/root/jake_desktop/app.py` (adicionar após os endpoints do Task 1)

- [ ] **Step 1: Inserir os dois endpoints após o bloco do Task 1**

Adicionar após o endpoint `planejador_transcrever`, ainda dentro da seção `ABA PLANEJADOR`:

```python
@app.route("/api/planejador/subir", methods=["POST"])
@login_required
def planejador_subir():
    """Fase 1: valida payload, armazena em memória, retorna token."""
    d = request.get_json() or {}
    cliente_id     = d.get("cliente_id")
    objetivo       = d.get("objetivo", "")
    drive_link     = (d.get("drive_link") or "").strip()
    orcamento      = d.get("orcamento_diario")
    campanha_nome  = d.get("campanha_nome") or ""
    copy_titulo    = d.get("copy_titulo") or ""
    copy_texto     = d.get("copy_texto") or ""

    if not cliente_id:
        return jsonify({"error": "cliente_id obrigatório"}), 400
    if objetivo not in _PLANEJADOR_OBJETIVOS:
        return jsonify({"error": f"objetivo deve ser: {', '.join(_PLANEJADOR_OBJETIVOS)}"}), 400
    if not drive_link:
        return jsonify({"error": "drive_link obrigatório"}), 400
    if not orcamento:
        return jsonify({"error": "orcamento_diario obrigatório"}), 400

    # Buscar cliente e validar público
    conn = None
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute("SELECT * FROM ad_client_profiles WHERE id = %s", (cliente_id,))
        cliente = cur.fetchone()
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar cliente: {e}"}), 500
    finally:
        try: conn.close()
        except Exception: pass

    if not cliente:
        return jsonify({"error": "Cliente não encontrado"}), 404
    if not cliente.get("publico_json"):
        return jsonify({"error": "Público não configurado neste cliente. Configure em Subir Anúncios → perfil do cliente antes de usar o Planejador."}), 400
    if not cliente.get("page_id"):
        return jsonify({"error": "page_id não configurado neste cliente"}), 400
    if not cliente.get("localizacao_json"):
        return jsonify({"error": "Localização não configurada neste cliente"}), 400

    import datetime as _dt
    now = _dt.datetime.now()
    if not campanha_nome:
        campanha_nome = f"{cliente['nome']} — {_PLANEJADOR_LABEL.get(objetivo, objetivo)} {now.strftime('%b/%y')}"

    token = str(uuid.uuid4())
    _planejador_payloads[token] = {
        "cliente":      dict(cliente),
        "objetivo":     objetivo,
        "drive_link":   drive_link,
        "orcamento":    float(orcamento),
        "campanha_nome": campanha_nome,
        "copy_titulo":  copy_titulo,
        "copy_texto":   copy_texto,
    }

    def _cleanup():
        _planejador_payloads.pop(token, None)
    threading.Timer(1800, _cleanup).start()

    return jsonify({"token": token})


@app.route("/api/planejador/subir/stream/<pl_token>")
@login_required
def planejador_subir_stream(pl_token):
    """Fase 2: SSE — baixa Drive, faz upload no Meta, cria campanha."""
    payload = _planejador_payloads.pop(pl_token, None)

    def _sse(data: dict) -> str:
        return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

    def _gerar():
        if not payload:
            yield _sse({"status": "erro", "msg": "Token inválido ou expirado"})
            return

        cliente      = payload["cliente"]
        objetivo     = payload["objetivo"]
        drive_link   = payload["drive_link"]
        orcamento    = payload["orcamento"]
        camp_nome    = payload["campanha_nome"]
        copy_titulo  = payload["copy_titulo"]
        copy_texto   = payload["copy_texto"]

        account_id   = cliente["account_id"]
        token_key    = cliente["token_key"]
        page_id      = cliente["page_id"]
        publico      = cliente["publico_json"]
        localizacao  = cliente["localizacao_json"]
        opt_goal     = cliente.get("optimization_goal")
        pixel_id     = cliente.get("pixel_id")
        link_url     = cliente.get("link_url") or ""
        cta          = _PLANEJADOR_CTA[objetivo]
        cbo          = objetivo not in ("ENGAGEMENT", "PURCHASE")

        if token_key not in _VALID_TOKEN_KEYS:
            yield _sse({"status": "erro", "msg": f"token_key inválido: {token_key}"})
            return
        meta_token = os.getenv(token_key, "")
        if not meta_token:
            yield _sse({"status": "erro", "msg": f"{token_key} não configurado"})
            return

        api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            yield _sse({"status": "erro", "msg": "GOOGLE_API_KEY não configurada"})
            return

        # ── Passo 1: parsear folder_id do Drive ──────────────────────────
        folder_id = None
        if "/folders/" in drive_link:
            folder_id = drive_link.split("/folders/")[1].split("?")[0].split("/")[0]
        elif "id=" in drive_link:
            from urllib.parse import urlparse, parse_qs
            folder_id = parse_qs(urlparse(drive_link).query).get("id", [None])[0]
        if not folder_id:
            yield _sse({"status": "erro", "msg": "Não consegui extrair o ID da pasta. Use drive.google.com/drive/folders/..."})
            return

        yield _sse({"status": "baixando", "msg": "Conectando ao Drive..."})

        # ── Passo 2: listar arquivos ──────────────────────────────────────
        try:
            resp = requests.get(
                "https://www.googleapis.com/drive/v3/files",
                params={"q": f"'{folder_id}' in parents",
                        "fields": "files(id,name,mimeType)",
                        "key": api_key, "pageSize": 100},
                timeout=15,
            )
            resp.raise_for_status()
            files = [f for f in resp.json().get("files", [])
                     if f.get("mimeType") in _DRIVE_MIME_EXT]
        except Exception as e:
            yield _sse({"status": "erro", "msg": f"Erro ao listar Drive: {e}"})
            return

        if not files:
            yield _sse({"status": "erro", "msg": "Nenhuma imagem encontrada na pasta"})
            return

        yield _sse({"status": "baixando", "msg": f"{len(files)} criativo(s) encontrado(s)"})

        # ── Passo 3: baixar e fazer upload para Meta ──────────────────────
        creative_refs = []
        tmp_paths     = []
        for idx, f in enumerate(files):
            file_id  = f["id"]
            ext      = _DRIVE_MIME_EXT.get(f.get("mimeType", ""), ".jpg")
            try:
                dl = requests.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}",
                    params={"alt": "media", "key": api_key},
                    timeout=30,
                )
                dl.raise_for_status()
                file_bytes = dl.content
            except Exception as e:
                yield _sse({"status": "erro", "msg": f"Download criativo {idx+1} falhou: {e}"})
                return

            tmp_path = os.path.join(_TMP_DIR, f"{uuid.uuid4()}{ext}")
            with open(tmp_path, "wb") as fp:
                fp.write(file_bytes)
            tmp_paths.append(tmp_path)

            yield _sse({"status": "baixando", "msg": f"Fazendo upload criativo {idx+1}/{len(files)}..."})
            try:
                up = _meta_api.upload_imagem(meta_token, account_id, file_bytes, f"plan_{uuid.uuid4()}{ext}")
                creative_refs.append({"tipo": "imagem", "hash": up["hash"]})
            except Exception as e:
                yield _sse({"status": "erro", "msg": f"Upload criativo {idx+1} falhou: {e}"})
                return

        # ── Passo 4: criar campanha ───────────────────────────────────────
        yield _sse({"status": "criando", "msg": f"Criando campanha \"{camp_nome}\"..."})
        campaign_id = None
        newly_created_campaign = False
        try:
            camp_orcamento = orcamento if cbo else 0
            campaign_id = _meta_api.criar_campanha(
                meta_token, account_id, objetivo, camp_nome, camp_orcamento, cbo=cbo
            )
            newly_created_campaign = True
        except Exception as e:
            yield _sse({"status": "erro", "msg": f"Erro ao criar campanha: {e}"})
            return

        # ── Passo 5: criar conjunto ───────────────────────────────────────
        yield _sse({"status": "criando", "msg": "Criando conjunto de anúncios..."})
        adset_id = None
        try:
            adset_orcamento = orcamento if not cbo else None
            adset_id = _meta_api.criar_conjunto(
                meta_token, account_id, campaign_id, objetivo,
                publico, localizacao,
                orcamento=adset_orcamento,
                optimization_goal=opt_goal,
                pixel_id=pixel_id,
                nome=f"Conjunto — {camp_nome}",
            )
        except Exception as e:
            if newly_created_campaign:
                try: _meta_api.deletar_objeto_meta(meta_token, campaign_id)
                except Exception: pass
            yield _sse({"status": "erro", "msg": f"Erro ao criar conjunto: {e}"})
            return

        # ── Passo 6: criar anúncios ───────────────────────────────────────
        ad_ids = []
        for idx, cr in enumerate(creative_refs):
            yield _sse({"status": "publicando", "msg": f"Publicando anúncio {idx+1}/{len(creative_refs)}..."})
            try:
                ad_id = _meta_api.criar_anuncio(
                    meta_token, account_id, adset_id, page_id,
                    cr, copy_titulo, copy_texto, cta, link_url=link_url,
                )
                ad_ids.append(ad_id)
                # Log em ad_publish_log (padrão existente)
                try:
                    conn = _get_db(); cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO ad_publish_log
                            (cliente_id, account_id, campaign_id, adset_id, ad_id, status, audience_id, payload_json)
                        VALUES (%s,%s,%s,%s,%s,'sucesso',NULL,%s)
                    """, (cliente["id"], account_id, campaign_id, adset_id, ad_id,
                          json.dumps({"titulo": copy_titulo, "texto": copy_texto})))
                    conn.commit()
                except Exception:
                    pass
                finally:
                    try: conn.close()
                    except Exception: pass
            except Exception as e:
                yield _sse({"status": "erro", "msg": f"Anúncio {idx+1} falhou: {e}"})
                return

        # ── Limpeza tmp ───────────────────────────────────────────────────
        for p in tmp_paths:
            try: os.remove(p)
            except Exception: pass

        yield _sse({"status": "concluido", "msg": "✅ Campanha criada com sucesso!", "campaign_id": campaign_id})

    return Response(
        stream_with_context(_gerar()),
        content_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
```

- [ ] **Step 2: Verificar sintaxe**

```bash
cd /root/jake_desktop && /root/jake_desktop/.venv/bin/python -c "import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Testar `/api/planejador/subir` sem cliente_id**

```bash
curl -s -c /tmp/p_cookies.txt -b /tmp/p_cookies.txt -X POST http://localhost:5050/api/planejador/subir \
  -H "Content-Type: application/json" -d '{}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error'))"
```
Expected: `cliente_id obrigatório`

- [ ] **Step 4: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(planejador): endpoints subir POST + subir/stream GET/SSE"
```

---

## Task 3: `dashboard.html` — nav + page section + CSS link + script tag

**Files:**
- Modify: `/root/jake_desktop/templates/dashboard.html`

- [ ] **Step 1: Localizar o nav item do Gestor IA**

```bash
grep -n "gestor\|Gestor" /root/jake_desktop/templates/dashboard.html | head -10
```
Identificar a linha do `<a class="nav-item" data-page="gestor"`.

- [ ] **Step 2: Adicionar nav item do Planejador após o do Gestor IA**

Após o bloco `<a class="nav-item" data-page="gestor" ...>...</a>`, adicionar:

```html
        <a class="nav-item" data-page="planejador" href="#">
          <span class="nav-icon">💬</span>
          <span class="nav-label">Planejador</span>
        </a>
```

- [ ] **Step 3: Localizar a section page-gestor**

```bash
grep -n "page-gestor\|page-copys" /root/jake_desktop/templates/dashboard.html | head -5
```

- [ ] **Step 4: Adicionar page section após o fechamento de page-gestor**

Após `</section><!-- /page-gestor -->` (ou o `</section>` que fecha page-gestor), adicionar:

```html
      <!-- PLANEJADOR DE CAMPANHAS ──────────────────────── -->
      <section class="page" id="page-planejador">
        <div class="plan-layout">

          <div class="plan-header">
            <div class="plan-title">Planejador de Campanhas</div>
            <button onclick="planejadorNovaConversa()" class="anu-btn-secondary" style="font-size:11px">+ Nova conversa</button>
          </div>

          <div id="plan-chat" class="plan-chat"></div>

          <div class="plan-input-bar">
            <button id="plan-mic-btn" class="plan-mic-btn" onclick="planejadorToggleMic()">🎤</button>
            <input id="plan-input" class="plan-input" type="text"
                   placeholder="Ex: sobe campanha para Queen Poltronas, engajamento, link do drive..."
                   onkeydown="if(event.key==='Enter')planejadorEnviar()">
            <button class="plan-send-btn" onclick="planejadorEnviar()">→</button>
          </div>

        </div>
      </section>
```

- [ ] **Step 5: Adicionar link CSS (localizar gestor.css e adicionar planejador.css após)**

```bash
grep -n "gestor.css" /root/jake_desktop/templates/dashboard.html
```

Após `<link rel="stylesheet" href="{{ url_for('static', filename='css/gestor.css') }}">`, adicionar:

```html
  <link rel="stylesheet" href="{{ url_for('static', filename='css/planejador.css') }}">
```

- [ ] **Step 6: Adicionar script tag (localizar gestor.js e adicionar planejador.js após)**

```bash
grep -n "gestor.js" /root/jake_desktop/templates/dashboard.html
```

Após `<script src="{{ url_for('static', filename='js/gestor.js') }}"></script>`, adicionar:

```html
  <script src="{{ url_for('static', filename='js/planejador.js') }}"></script>
```

- [ ] **Step 7: Commit**

```bash
git add jake_desktop/templates/dashboard.html
git commit -m "feat(planejador): HTML — nav item, page section, CSS/JS tags"
```

---

## Task 4: `planejador.css` — estilos do chat

**Files:**
- Create: `/root/jake_desktop/static/css/planejador.css`

- [ ] **Step 1: Criar o arquivo CSS**

```css
/* ── Planejador de Campanhas ────────────────────────────────────────────── */

.plan-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  gap: 0;
}

.plan-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(176,190,197,.08);
  flex-shrink: 0;
}

.plan-title {
  font-size: 16px;
  font-weight: 700;
  color: rgba(176,190,197,.95);
  letter-spacing: .04em;
}

/* Área de chat */
.plan-chat {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Bolhas de mensagem */
.plan-msg-user {
  align-self: flex-end;
  max-width: 70%;
  background: rgba(0,180,216,.12);
  border: 1px solid rgba(0,180,216,.2);
  border-radius: 12px 12px 2px 12px;
  padding: 8px 14px;
  font-size: 12px;
  color: rgba(176,190,197,.9);
  line-height: 1.5;
}

.plan-msg-jake {
  align-self: flex-start;
  max-width: 75%;
  background: rgba(176,190,197,.06);
  border: 1px solid rgba(176,190,197,.1);
  border-radius: 12px 12px 12px 2px;
  padding: 8px 14px;
  font-size: 12px;
  color: rgba(176,190,197,.85);
  line-height: 1.5;
}

.plan-msg-erro {
  align-self: flex-start;
  max-width: 75%;
  background: rgba(255,100,100,.08);
  border: 1px solid rgba(255,100,100,.15);
  border-radius: 12px;
  padding: 8px 14px;
  font-size: 12px;
  color: #ff8080;
}

/* Indicador "digitando" */
.plan-typing {
  align-self: flex-start;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 14px;
}

.plan-typing span {
  width: 6px; height: 6px; border-radius: 50%;
  background: rgba(176,190,197,.3);
  animation: plan-bounce .8s infinite;
}
.plan-typing span:nth-child(2) { animation-delay: .15s; }
.plan-typing span:nth-child(3) { animation-delay: .3s; }

@keyframes plan-bounce {
  0%, 80%, 100% { transform: translateY(0); }
  40%           { transform: translateY(-5px); background: rgba(0,180,216,.6); }
}

/* Card de confirmação */
.plan-msg-card {
  align-self: flex-start;
  width: 90%;
  max-width: 420px;
  background: rgba(0,180,216,.05);
  border: 1px solid rgba(0,180,216,.18);
  border-radius: 10px;
  padding: 16px;
}

.plan-card-title {
  font-size: 10px;
  color: #00b4d8;
  letter-spacing: .07em;
  margin-bottom: 12px;
}

.plan-card-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}

.plan-card-row {
  display: flex;
  gap: 8px;
  font-size: 11px;
}
.plan-card-label { color: rgba(176,190,197,.4); width: 76px; flex-shrink: 0; }
.plan-card-value { color: rgba(176,190,197,.85); word-break: break-word; }

.plan-card-btns {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

/* Mensagem de progresso SSE */
.plan-msg-progress {
  align-self: flex-start;
  font-size: 11px;
  color: rgba(176,190,197,.5);
  padding: 2px 4px;
}

/* Barra de input */
.plan-input-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid rgba(176,190,197,.08);
  flex-shrink: 0;
}

.plan-mic-btn {
  background: rgba(176,190,197,.08);
  border: 1px solid rgba(176,190,197,.15);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 14px;
  cursor: pointer;
  transition: all .15s;
  flex-shrink: 0;
}
.plan-mic-btn:hover { background: rgba(176,190,197,.14); }
.plan-mic-btn.gravando {
  background: rgba(255,100,100,.15);
  border-color: rgba(255,100,100,.3);
  animation: plan-pulse 1s infinite;
}
@keyframes plan-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: .6; }
}

.plan-input {
  flex: 1;
  background: rgba(176,190,197,.06);
  border: 1px solid rgba(176,190,197,.12);
  border-radius: 6px;
  color: rgba(176,190,197,.9);
  font-size: 12px;
  padding: 8px 12px;
  outline: none;
  transition: border-color .15s;
}
.plan-input:focus { border-color: rgba(0,180,216,.35); }
.plan-input:disabled { opacity: .5; cursor: not-allowed; }
.plan-input::placeholder { color: rgba(176,190,197,.25); }

.plan-send-btn {
  background: rgba(0,180,216,.12);
  border: 1px solid rgba(0,180,216,.2);
  border-radius: 6px;
  color: #00b4d8;
  font-size: 14px;
  padding: 6px 14px;
  cursor: pointer;
  transition: all .15s;
  flex-shrink: 0;
}
.plan-send-btn:hover { background: rgba(0,180,216,.2); }
.plan-send-btn:disabled { opacity: .4; cursor: not-allowed; }
```

- [ ] **Step 2: Commit**

```bash
git add jake_desktop/static/css/planejador.css
git commit -m "feat(planejador): CSS — estilos do chat"
```

---

## Task 5: `planejador.js` — IIFE completo

**Files:**
- Create: `/root/jake_desktop/static/js/planejador.js`

- [ ] **Step 1: Criar o arquivo JS**

```javascript
/* planejador.js — Planejador de Campanhas IIFE */
(function () {
  'use strict';

  // ── State ─────────────────────────────────────────────────────────────────
  var _messages  = [];       // [{role: 'user'|'assistant', content: string}]
  var _params    = {};       // parâmetros acumulados
  var _estado    = 'chat';   // 'chat' | 'confirmando' | 'subindo' | 'concluido'
  var _gravando  = false;
  var _recorder  = null;
  var _chunks    = [];
  var _evtSource = null;

  // ── Init ──────────────────────────────────────────────────────────────────
  window.planejadorInit = function () {
    if (_estado === 'chat' && _messages.length === 0) {
      _addMsgJake('Olá! Me diga qual campanha você quer criar. Pode mandar texto ou áudio 🎤');
    }
    var inp = document.getElementById('plan-input');
    if (inp) inp.focus();
    _syncInput();
  };

  // ── Enviar mensagem ────────────────────────────────────────────────────────
  window.planejadorEnviar = function () {
    if (_estado !== 'chat') return;
    var inp = document.getElementById('plan-input');
    if (!inp) return;
    var texto = inp.value.trim();
    if (!texto) return;
    inp.value = '';

    _addMsgUser(texto);
    _messages.push({role: 'user', content: texto});
    _showTyping();
    _syncInput();

    fetch('/api/planejador/interpretar', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({messages: _messages, params: _params}),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        _removeTyping();
        if (d.error) {
          _addMsgErro(d.error);
          _syncInput();
          return;
        }
        // Atualizar params acumulados
        if (d.params) {
          Object.keys(d.params).forEach(function (k) {
            if (d.params[k] !== null && d.params[k] !== undefined) {
              _params[k] = d.params[k];
            }
          });
        }
        if (d.pronto) {
          _messages.push({role: 'assistant', content: d.resposta || ''});
          _estado = 'confirmando';
          _renderCard();
          _syncInput();
        } else {
          var resposta = d.resposta || 'Hmm, pode reformular?';
          _addMsgJake(resposta);
          _messages.push({role: 'assistant', content: resposta});
          _syncInput();
        }
      })
      .catch(function (e) {
        _removeTyping();
        _addMsgErro('Erro de conexão: ' + e.message);
        _syncInput();
      });
  };

  // ── Confirmar ──────────────────────────────────────────────────────────────
  window.planejadorConfirmar = function () {
    if (_estado !== 'confirmando') return;
    _estado = 'subindo';
    _syncInput();

    // Esconder botões do card
    var btns = document.querySelector('.plan-card-btns');
    if (btns) btns.style.display = 'none';

    fetch('/api/planejador/subir', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(_params),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (e) { throw new Error(e.error || r.statusText); });
        return r.json();
      })
      .then(function (d) {
        var token = d.token;
        _evtSource = new EventSource('/api/planejador/subir/stream/' + token);
        _evtSource.onmessage = function (e) {
          var ev = JSON.parse(e.data);
          if (ev.status === 'concluido') {
            _evtSource.close();
            _estado = 'concluido';
            _addMsgJake('✅ ' + ev.msg + (ev.campaign_id ? '\nCampaign ID: ' + ev.campaign_id : ''));
            _syncInput();
          } else if (ev.status === 'erro') {
            _evtSource.close();
            _estado = 'chat';
            _addMsgErro('❌ ' + ev.msg);
            _syncInput();
          } else {
            _addMsgProgress('⏳ ' + ev.msg);
          }
        };
        _evtSource.onerror = function () {
          _evtSource.close();
          _estado = 'chat';
          _addMsgErro('Conexão SSE perdida. Tente novamente.');
          _syncInput();
        };
      })
      .catch(function (e) {
        _estado = 'chat';
        _addMsgErro('Erro ao iniciar: ' + e.message);
        if (btns) btns.style.display = '';
        _syncInput();
      });
  };

  // ── Cancelar (Ajustar) ────────────────────────────────────────────────────
  window.planejadorCancelar = function () {
    _estado = 'chat';
    // Remover card do chat (último elemento)
    var chat = document.getElementById('plan-chat');
    if (chat) {
      var cards = chat.querySelectorAll('.plan-msg-card');
      if (cards.length) cards[cards.length - 1].remove();
    }
    _addMsgJake('Ok! Me diga o que quer ajustar.');
    _syncInput();
  };

  // ── Nova conversa ──────────────────────────────────────────────────────────
  window.planejadorNovaConversa = function () {
    if (_evtSource) { _evtSource.close(); _evtSource = null; }
    _messages = [];
    _params   = {};
    _estado   = 'chat';
    var chat = document.getElementById('plan-chat');
    if (chat) chat.innerHTML = '';
    _syncInput();
    planejadorInit();
  };

  // ── Microfone ──────────────────────────────────────────────────────────────
  window.planejadorToggleMic = function () {
    if (_gravando) {
      _pararGravacao();
    } else {
      _iniciarGravacao();
    }
  };

  function _iniciarGravacao() {
    if (!navigator.mediaDevices) {
      alert('Microfone não suportado neste browser.');
      return;
    }
    navigator.mediaDevices.getUserMedia({audio: true})
      .then(function (stream) {
        _chunks = [];
        var mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : MediaRecorder.isTypeSupported('audio/mp4')
            ? 'audio/mp4'
            : 'audio/ogg';
        _recorder = new MediaRecorder(stream, {mimeType: mimeType});
        _recorder.ondataavailable = function (e) {
          if (e.data.size > 0) _chunks.push(e.data);
        };
        _recorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          var blob = new Blob(_chunks, {type: mimeType});
          _transcrever(blob, mimeType);
        };
        _recorder.start();
        _gravando = true;
        var btn = document.getElementById('plan-mic-btn');
        if (btn) btn.classList.add('gravando');
      })
      .catch(function (e) {
        alert('Erro ao acessar microfone: ' + e.message);
      });
  }

  function _pararGravacao() {
    if (_recorder && _recorder.state !== 'inactive') _recorder.stop();
    _gravando = false;
    var btn = document.getElementById('plan-mic-btn');
    if (btn) btn.classList.remove('gravando');
  }

  function _transcrever(blob, mimeType) {
    var ext = mimeType.indexOf('mp4') !== -1 ? '.mp4'
            : mimeType.indexOf('ogg') !== -1 ? '.ogg' : '.webm';
    var fd = new FormData();
    fd.append('audio', blob, 'audio' + ext);
    fetch('/api/planejador/transcrever', {method: 'POST', body: fd})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.error) { _addMsgErro('Transcrição falhou: ' + d.error); return; }
        var inp = document.getElementById('plan-input');
        if (inp) { inp.value = d.text; inp.focus(); }
      })
      .catch(function (e) { _addMsgErro('Erro de transcrição: ' + e.message); });
  }

  // ── Render helpers ─────────────────────────────────────────────────────────
  function _addMsgUser(texto) {
    _appendChat('<div class="plan-msg-user">' + _esc(texto) + '</div>');
  }

  function _addMsgJake(texto) {
    _appendChat('<div class="plan-msg-jake">' + _esc(texto).replace(/\n/g, '<br>') + '</div>');
  }

  function _addMsgErro(texto) {
    _appendChat('<div class="plan-msg-erro">' + _esc(texto) + '</div>');
  }

  function _addMsgProgress(texto) {
    _appendChat('<div class="plan-msg-progress">' + _esc(texto) + '</div>');
  }

  function _showTyping() {
    var el = document.createElement('div');
    el.id = 'plan-typing-indicator';
    el.className = 'plan-typing';
    el.innerHTML = '<span></span><span></span><span></span>';
    var chat = document.getElementById('plan-chat');
    if (chat) { chat.appendChild(el); chat.scrollTop = chat.scrollHeight; }
  }

  function _removeTyping() {
    var el = document.getElementById('plan-typing-indicator');
    if (el) el.remove();
  }

  function _renderCard() {
    var p    = _params;
    var obj  = {'MESSAGES': 'Mensagens', 'ENGAGEMENT': 'Engajamento', 'PURCHASE': 'Conversões'};
    var link = p.drive_link
      ? p.drive_link.replace(/https?:\/\/(www\.)?/, '').substring(0, 35) + '…'
      : '—';

    var html =
      '<div class="plan-msg-card">' +
        '<div class="plan-card-title">📋 RESUMO DA CAMPANHA</div>' +
        '<div class="plan-card-rows">' +
          _row('Cliente',   p.cliente_nome || '—') +
          _row('Objetivo',  obj[p.objetivo] || p.objetivo || '—') +
          _row('Drive',     link) +
          _row('Orçamento', p.orcamento_diario ? 'R$ ' + Number(p.orcamento_diario).toFixed(0) + '/dia' : '—') +
          _row('Público',   p.publico_descricao || '(padrão do cliente)') +
          (p.copy_titulo ? _row('Copy',  '"' + p.copy_titulo + '"') : '') +
        '</div>' +
        '<div class="plan-card-btns">' +
          '<button class="anu-btn-primary" style="font-size:11px" onclick="planejadorConfirmar()">✓ Confirmar e Subir</button>' +
          '<button class="anu-btn-secondary" style="font-size:11px" onclick="planejadorCancelar()">✎ Ajustar</button>' +
        '</div>' +
      '</div>';
    _appendChat(html);
  }

  function _row(label, value) {
    return '<div class="plan-card-row"><span class="plan-card-label">' + label + '</span>' +
           '<span class="plan-card-value">' + _esc(String(value)) + '</span></div>';
  }

  function _appendChat(html) {
    var chat = document.getElementById('plan-chat');
    if (!chat) return;
    var div = document.createElement('div');
    div.innerHTML = html;
    while (div.firstChild) chat.appendChild(div.firstChild);
    chat.scrollTop = chat.scrollHeight;
  }

  // ── Sync UI por estado ──────────────────────────────────────────────────────
  function _syncInput() {
    var inp  = document.getElementById('plan-input');
    var send = document.querySelector('.plan-send-btn');
    var mic  = document.getElementById('plan-mic-btn');
    var disabled = _estado !== 'chat';
    if (inp)  { inp.disabled  = disabled; }
    if (send) { send.disabled = disabled; }
    if (mic)  { mic.disabled  = disabled; }
  }

  // ── Utils ──────────────────────────────────────────────────────────────────
  function _esc(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  }

}());
```

- [ ] **Step 2: Commit**

```bash
git add jake_desktop/static/js/planejador.js
git commit -m "feat(planejador): JS — IIFE chat com estado, confirmação, SSE, áudio"
```

---

## Task 6: `app.js` — registrar rota `#planejador`

**Files:**
- Modify: `/root/jake_desktop/static/js/app.js`

- [ ] **Step 1: Ler o arquivo app.js inteiro**

```bash
# app.js é pequeno (~37 linhas)
```
Use Read tool em `/root/jake_desktop/static/js/app.js` sem limit/offset.

- [ ] **Step 2: Adicionar callback dentro de `showPage()` após o bloco do gestor**

Localizar:
```javascript
    if (id === "gestor" && typeof window.gestorInit === "function") {
      window.gestorInit();
    }
```

Adicionar logo após:
```javascript
    if (id === "planejador" && typeof window.planejadorInit === "function") {
      window.planejadorInit();
    }
```

- [ ] **Step 3: Adicionar `"planejador"` na lista `valid`**

Localizar a linha `var valid = [...]` e adicionar `"planejador"` após `"gestor"`:
```javascript
var valid = ["painel","architect","performance","anuncios","gestor","planejador","copys",...];
```

- [ ] **Step 4: Verificar as duas mudanças estão corretas**

```bash
grep -n "planejador" /root/jake_desktop/static/js/app.js
```
Expected: 2 linhas — uma no array `valid`, uma no if callback.

- [ ] **Step 5: Commit**

```bash
git add jake_desktop/static/js/app.js
git commit -m "feat(planejador): registrar rota #planejador em app.js"
```

---

## Task 7: Smoke test

**Files:** nenhum

- [ ] **Step 1: Reiniciar Jake OS**

```bash
pkill -f "python app.py" 2>/dev/null
lsof -ti:5050 | xargs kill -9 2>/dev/null
sleep 2
cd /root/jake_desktop && /root/jake_desktop/.venv/bin/python app.py > /tmp/jakeos_plan.log 2>&1 &
sleep 6 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/login
```
Expected: `200`

- [ ] **Step 2: Login**

```bash
curl -s -c /tmp/plan_cookies.txt -b /tmp/plan_cookies.txt -X POST http://localhost:5050/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=admin@jakeos.local&password=Jake@2024!" -o /dev/null
```

- [ ] **Step 3: Testar `/api/planejador/interpretar`**

```bash
curl -s -c /tmp/plan_cookies.txt -b /tmp/plan_cookies.txt \
  -X POST http://localhost:5050/api/planejador/interpretar \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"quero subir campanha para Queen Poltronas"}],"params":{}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'resposta' in d else d)"
```
Expected: `OK`

- [ ] **Step 4: Testar `/api/planejador/subir` com payload inválido**

```bash
curl -s -c /tmp/plan_cookies.txt -b /tmp/plan_cookies.txt \
  -X POST http://localhost:5050/api/planejador/subir \
  -H "Content-Type: application/json" \
  -d '{"cliente_id":1,"objetivo":"INVALIDO","drive_link":"x","orcamento_diario":50}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','ok'))"
```
Expected: mensagem sobre `objetivo`

- [ ] **Step 5: Verificar que a aba aparece no dashboard**

```bash
curl -s -c /tmp/plan_cookies.txt -b /tmp/plan_cookies.txt http://localhost:5050/ \
  | grep -o "planejador" | head -3
```
Expected: `planejador` (3x — nav + page + script)

- [ ] **Step 6: Verificar logs sem erros de import**

```bash
tail -20 /tmp/jakeos_plan.log
```
Expected: sem `ImportError` ou `SyntaxError`

- [ ] **Step 7: Commit final**

```bash
git add -A  # só se houver arquivos não commitados
git log --oneline -7
```
Verificar que todos os commits do planejador estão presentes.
