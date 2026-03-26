# Subir Anúncios — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a aba "Subir Anúncios" no Jake OS com perfis por cliente, geração de copy via IA e publicação na Meta API com aprovação obrigatória.

**Architecture:** Backend Flask com 8 novas rotas em `app.py`, funções Meta API em `meta/meta_api.py`, tabelas no Neon/PostgreSQL. Frontend em `static/js/anuncios.js` (IIFE pattern) com sidebar de clientes agrupados, 4 blocos de criação e modal de confirmação.

**Tech Stack:** Python/Flask, psycopg2 (Neon PostgreSQL), Meta Graph API v21.0, Anthropic claude-sonnet-4-6 (multimodal), Vanilla JS (IIFE), CSS Glassmorphism (padrão Jake OS)

**Spec:** `docs/superpowers/specs/2026-03-20-subir-anuncios-design.md`

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `meta/meta_api.py` | Modificar | Atualizar GRAPH_URL v21.0, substituir stub, adicionar funções de escrita |
| `jake_desktop/app.py` | Modificar | Adicionar psycopg2, helper DB, 8 novas rotas `/api/anuncios/*` |
| `jake_desktop/templates/dashboard.html` | Modificar | Substituir placeholder page-anuncios + script/css tags |
| `jake_desktop/static/js/anuncios.js` | Criar | IIFE: sidebar, formulário cliente, 4 blocos, modal publicação |
| `jake_desktop/static/css/anuncios.css` | Criar | Estilos da aba (sidebar, blocos, modal, validação) |
| `scripts/migrar_anuncios.py` | Criar | Script one-shot para criar as 2 tabelas no Neon |

---

## Mapeamento de valores internos → Meta API

| Campo interno (`campanha_tipo`) | Objective Meta API v21.0 |
|---|---|
| `MESSAGES` | `OUTCOME_MESSAGES` |
| `ENGAGEMENT` | `OUTCOME_ENGAGEMENT` |

Este mapeamento é crítico — usar strings erradas retorna erro 400 da Meta API.

---

## Task 1: Criar tabelas no banco (migration)

**Files:**
- Create: `scripts/migrar_anuncios.py`

- [ ] **Step 1: Criar script de migração**

O schema adiciona `page_id` (obrigatório pela Meta API para criar AdCreative) e `segmento` (para geração de copy mais precisa via IA). A localização tem default `'{}'` para evitar NOT NULL violation no INSERT, mas validação ocorre no backend antes de publicar.

```python
#!/usr/bin/env python3
"""
Script one-shot: cria as tabelas ad_client_profiles e ad_publish_log no Neon.
Executar: PYTHONPATH=/root python3 scripts/migrar_anuncios.py
"""
import sys
sys.path.insert(0, '/root')
from core.db import get_conn

SQL = """
CREATE TABLE IF NOT EXISTS ad_client_profiles (
    id                    SERIAL PRIMARY KEY,
    nome                  VARCHAR(100) NOT NULL,
    agencia               VARCHAR(20)  NOT NULL CHECK (agencia IN ('piloti','dentto','freelance')),
    account_id            VARCHAR(50)  NOT NULL,
    token_key             VARCHAR(50)  NOT NULL,
    page_id               VARCHAR(50),
    whatsapp              VARCHAR(20),
    segmento              VARCHAR(100),
    campanha_tipo         VARCHAR(20)  NOT NULL DEFAULT 'MESSAGES'
                              CHECK (campanha_tipo IN ('MESSAGES','ENGAGEMENT')),
    localizacao_json      JSONB        NOT NULL DEFAULT '{}',
    publico_json          JSONB,
    orcamento_diario      NUMERIC(10,2),
    campanha_id_existente VARCHAR(50),
    criado_em             TIMESTAMP    DEFAULT NOW(),
    atualizado_em         TIMESTAMP    DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ad_publish_log (
    id           SERIAL PRIMARY KEY,
    cliente_id   INTEGER REFERENCES ad_client_profiles(id),
    account_id   VARCHAR(50)  NOT NULL,
    campaign_id  VARCHAR(50),
    adset_id     VARCHAR(50),
    ad_id        VARCHAR(50),
    status       VARCHAR(20)  NOT NULL CHECK (status IN ('sucesso','erro')),
    erro_msg     TEXT,
    payload_json JSONB,
    criado_em    TIMESTAMP    DEFAULT NOW()
);
"""

if __name__ == "__main__":
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(SQL)
        conn.commit()
        print("✓ Tabelas criadas com sucesso.")
    except Exception as e:
        print(f"✕ Erro: {e}")
        sys.exit(1)
    finally:
        conn.close()
```

- [ ] **Step 2: Executar migração**

```bash
PYTHONPATH=/root python3 /root/scripts/migrar_anuncios.py
```

Expected: `✓ Tabelas criadas com sucesso.`

- [ ] **Step 3: Verificar tabelas**

```bash
PYTHONPATH=/root python3 -c "
from core.db import get_conn
conn = get_conn()
cur = conn.cursor()
cur.execute(\"SELECT table_name FROM information_schema.tables WHERE table_name IN ('ad_client_profiles','ad_publish_log')\")
print(cur.fetchall())
conn.close()
"
```

Expected: `[('ad_client_profiles',), ('ad_publish_log',)]`

- [ ] **Step 4: Commit**

```bash
git add scripts/migrar_anuncios.py
git commit -m "feat: migration — tabelas ad_client_profiles e ad_publish_log"
```

---

## Task 2: Atualizar meta/meta_api.py com funções de escrita

**Files:**
- Modify: `/root/meta/meta_api.py`

**Atenção:** Atualizar GRAPH_URL de v20.0 para v21.0 afeta as funções existentes (`get_saldo_conta`, `puxar_relatorio`, `_get_insights`). A Meta API v21.0 é retrocompatível com essas chamadas GET, mas se houver regressão, reverter apenas para as novas funções criando uma constante separada.

- [ ] **Step 1: Atualizar GRAPH_URL para v21.0**

Em `/root/meta/meta_api.py` linha 12:
```python
# ANTES:
GRAPH_URL = "https://graph.facebook.com/v20.0"
# DEPOIS:
GRAPH_URL = "https://graph.facebook.com/v21.0"
```

- [ ] **Step 2: Substituir stub e adicionar funções de escrita**

Localizar a função `criar_campanha` (stub, linha ~222) e **deletar o bloco inteiro** (da linha `def criar_campanha...` até o final do arquivo). Substituir por:

```python
# ── FUNÇÕES DE ESCRITA (Meta Ads API v21.0) ───────────────────────────────
import time as _time
import json as _json_meta

# Mapeamento interno → Meta API objective strings
_OBJETIVO_MAP = {
    "MESSAGES":   "OUTCOME_MESSAGES",
    "ENGAGEMENT": "OUTCOME_ENGAGEMENT",
}

VALID_TOKEN_KEYS = {"META_TOKEN_PILOTI", "META_TOKEN_DENTTO", "META_ACCESS_TOKEN"}


def _resolve_token(token_key: str) -> str:
    """Resolve token_key para valor da env var. Lança ValueError se inválido."""
    import os
    if token_key not in VALID_TOKEN_KEYS:
        raise ValueError(f"token_key inválido: {token_key}")
    token = os.getenv(token_key, "").strip()
    if not token:
        raise ValueError(f"Variável {token_key} não definida ou vazia")
    return token


def upload_imagem(token: str, account_id: str, imagem_bytes: bytes, filename: str) -> dict:
    """Upload via /adimages. Retorna {'hash': '...'}."""
    url = f"{GRAPH_URL}/{account_id}/adimages"
    resp = requests.post(url, params={"access_token": token},
                         files={"filename": (filename, imagem_bytes)})
    data = resp.json()
    if "images" in data:
        img_data = list(data["images"].values())[0]
        return {"hash": img_data["hash"]}
    raise Exception(data.get("error", {}).get("message", "Erro no upload de imagem"))


def upload_video(token: str, account_id: str, video_bytes: bytes, filename: str) -> str:
    """Upload via /advideos. Polling até status=ready (máx 60s). Retorna video_id."""
    url = f"{GRAPH_URL}/{account_id}/advideos"
    resp = requests.post(url, params={"access_token": token},
                         files={"source": (filename, video_bytes)})
    data = resp.json()
    if "id" not in data:
        raise Exception(data.get("error", {}).get("message", "Erro no upload de vídeo"))

    video_id = data["id"]
    for _ in range(20):  # 20 x 3s = 60s máx
        _time.sleep(3)
        check = requests.get(f"{GRAPH_URL}/{video_id}",
                             params={"fields": "status", "access_token": token})
        video_status = check.json().get("status", {}).get("video_status", "")
        if video_status == "ready":
            return video_id
        if video_status == "error":
            raise Exception("Vídeo retornou status=error durante processamento")

    raise Exception("Timeout: vídeo não ficou pronto em 60 segundos")


def listar_campanhas(token: str, account_id: str) -> list:
    """Lista campanhas ativas/pausadas da conta. Retorna lista de dicts."""
    url = f"{GRAPH_URL}/{account_id}/campaigns"
    resp = requests.get(url, params={
        "fields": "id,name,objective,status",
        "effective_status": '["ACTIVE","PAUSED"]',
        "access_token": token,
        "limit": 50,
    })
    data = resp.json()
    if "data" in data:
        return data["data"]
    raise Exception(data.get("error", {}).get("message", "Erro ao listar campanhas"))


def criar_campanha(token: str, account_id: str, campanha_tipo: str,
                   nome: str, orcamento: float, cbo: bool = True) -> str:
    """
    Cria campanha com status PAUSED.
    campanha_tipo: 'MESSAGES' ou 'ENGAGEMENT' (mapeado para objective correto).
    cbo=True: orçamento ao nível da campanha (MESSAGES).
    Retorna campaign_id.
    """
    objetivo = _OBJETIVO_MAP.get(campanha_tipo, "OUTCOME_MESSAGES")
    url = f"{GRAPH_URL}/{account_id}/campaigns"
    payload = {
        "name": nome,
        "objective": objetivo,
        "status": "PAUSED",
        "access_token": token,
    }
    if cbo:
        payload["daily_budget"] = int(orcamento * 100)  # Meta usa centavos
        payload["bid_strategy"] = "LOWEST_COST_WITHOUT_CAP"

    resp = requests.post(url, data=payload)
    data = resp.json()
    if "id" in data:
        return data["id"]
    raise Exception(data.get("error", {}).get("message", "Erro ao criar campanha"))


def criar_conjunto(token: str, account_id: str, campaign_id: str,
                   campanha_tipo: str, publico: dict, localizacao: dict,
                   orcamento: float = None) -> str:
    """
    Cria ad set com status PAUSED.
    campanha_tipo: 'MESSAGES' → optimization_goal=CONVERSATIONS
                   'ENGAGEMENT' → optimization_goal=POST_ENGAGEMENT + orcamento no adset
    publico: {'idade_min': int, 'idade_max': int, 'genero': [1,2]}
    localizacao: {'paises': ['BR'], 'cidades': [{'key': '...', 'radius': 15, 'distance_unit': 'kilometer'}]}
    Retorna adset_id.
    """
    url = f"{GRAPH_URL}/{account_id}/adsets"
    targeting = {
        "age_min": publico.get("idade_min", 18),
        "age_max": publico.get("idade_max", 65),
        "geo_locations": {
            "countries": localizacao.get("paises", ["BR"]),
            "cities": localizacao.get("cidades", []),
        }
    }
    if publico.get("genero"):
        targeting["genders"] = publico["genero"]

    payload = {
        "campaign_id": campaign_id,
        "name": f"Conjunto - {campanha_tipo}",
        "targeting": _json_meta.dumps(targeting),
        "status": "PAUSED",
        "access_token": token,
    }

    if campanha_tipo == "MESSAGES":
        payload["optimization_goal"] = "CONVERSATIONS"
        payload["billing_event"] = "IMPRESSIONS"
    else:  # ENGAGEMENT
        payload["optimization_goal"] = "POST_ENGAGEMENT"
        payload["billing_event"] = "IMPRESSIONS"
        if orcamento:
            payload["daily_budget"] = int(orcamento * 100)

    resp = requests.post(url, data=payload)
    data = resp.json()
    if "id" in data:
        return data["id"]
    raise Exception(data.get("error", {}).get("message", "Erro ao criar conjunto"))


def criar_anuncio(token: str, account_id: str, adset_id: str, page_id: str,
                  creative_ref: dict, titulo: str, texto: str, cta: str) -> str:
    """
    Cria AdCreative + Ad com status PAUSED.
    creative_ref: {'tipo': 'imagem', 'hash': '...'} ou {'tipo': 'video', 'video_id': '...'}
    page_id: obrigatório para object_story_spec (Facebook Page ID do cliente).
    cta: 'SEND_MESSAGE' | 'LEARN_MORE' | 'SIGN_UP'
    Retorna ad_id.
    """
    creative_url = f"{GRAPH_URL}/{account_id}/adcreatives"

    if creative_ref["tipo"] == "imagem":
        story_spec = {
            "page_id": page_id,
            "link_data": {
                "image_hash": creative_ref["hash"],
                "message": texto,
                "name": titulo,
                "call_to_action": {"type": cta},
            }
        }
    else:
        story_spec = {
            "page_id": page_id,
            "video_data": {
                "video_id": creative_ref["video_id"],
                "message": texto,
                "title": titulo,
                "call_to_action": {"type": cta},
            }
        }

    cr = requests.post(creative_url, data={
        "name": f"Criativo - {titulo[:30]}",
        "object_story_spec": _json_meta.dumps(story_spec),
        "access_token": token,
    })
    cr_data = cr.json()
    if "id" not in cr_data:
        raise Exception(cr_data.get("error", {}).get("message", "Erro ao criar criativo"))
    creative_id = cr_data["id"]

    ad_url = f"{GRAPH_URL}/{account_id}/ads"
    ad = requests.post(ad_url, data={
        "name": titulo[:40],
        "adset_id": adset_id,
        "creative": _json_meta.dumps({"creative_id": creative_id}),
        "status": "PAUSED",
        "access_token": token,
    })
    ad_data = ad.json()
    if "id" in ad_data:
        return ad_data["id"]
    raise Exception(ad_data.get("error", {}).get("message", "Erro ao criar anúncio"))


def deletar_objeto_meta(token: str, objeto_id: str) -> None:
    """Deleta campanha/conjunto/anúncio pelo ID (usado em rollback)."""
    requests.delete(f"{GRAPH_URL}/{objeto_id}", params={"access_token": token})
```

- [ ] **Step 3: Verificar sintaxe**

```bash
PYTHONPATH=/root /root/venv/bin/python3 -c "import meta.meta_api; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add meta/meta_api.py
git commit -m "feat: meta_api v21.0 — funções de escrita (upload, campanha, conjunto, anúncio, rollback)"
```

---

## Task 3: Rotas Flask — CRUD de perfis de clientes

**Files:**
- Modify: `jake_desktop/app.py`

O `app.py` não usa Neon atualmente. Vamos adicionar helper de conexão diretamente no arquivo.

- [ ] **Step 1: Verificar que psycopg2 está no venv do jake_desktop**

```bash
/root/jake_desktop/venv/bin/pip show psycopg2-binary 2>/dev/null || \
/root/jake_desktop/venv/bin/pip install psycopg2-binary
```

Expected: mostra info do pacote ou instala sem erros.

- [ ] **Step 2: Adicionar imports e helper DB em app.py**

Após `import requests` (linha ~22), adicionar:

```python
import psycopg2
import psycopg2.extras

def _get_db():
    """Abre conexão com Neon usando DATABASE_URL do .env."""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido no .env")
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
```

- [ ] **Step 3: Adicionar import do meta_api e constante de tokens**

Logo após os imports da OpenAI/Anthropic, adicionar:

```python
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import meta.meta_api as _meta_api

_VALID_TOKEN_KEYS = {"META_TOKEN_PILOTI", "META_TOKEN_DENTTO", "META_ACCESS_TOKEN"}
```

- [ ] **Step 4: Adicionar rotas CRUD no final de app.py**

```python
# ══════════════════════════════════════════════════════════════════════════
#  ABA SUBIR ANÚNCIOS — CRUD de perfis de clientes
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/anuncios/clientes", methods=["GET"])
@login_required
def anuncios_listar_clientes():
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, nome, agencia, account_id, token_key, page_id, whatsapp,
                   segmento, campanha_tipo, localizacao_json, publico_json,
                   orcamento_diario, campanha_id_existente
            FROM ad_client_profiles ORDER BY agencia, nome
        """)
        rows = cur.fetchall()
        conn.close()
        return jsonify({"clientes": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/clientes", methods=["POST"])
@login_required
def anuncios_criar_cliente():
    d = request.get_json() or {}
    obrigatorios = ["nome", "agencia", "account_id", "token_key", "localizacao_json"]
    faltando = [f for f in obrigatorios if not d.get(f)]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios: {faltando}"}), 400
    if d["token_key"] not in _VALID_TOKEN_KEYS:
        return jsonify({"error": f"token_key inválido. Válidos: {list(_VALID_TOKEN_KEYS)}"}), 400
    if d["agencia"] not in ("piloti", "dentto", "freelance"):
        return jsonify({"error": "agencia deve ser piloti, dentto ou freelance"}), 400

    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO ad_client_profiles
                (nome, agencia, account_id, token_key, page_id, whatsapp, segmento,
                 campanha_tipo, localizacao_json, publico_json, orcamento_diario,
                 campanha_id_existente)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            d["nome"], d["agencia"], d["account_id"], d["token_key"],
            d.get("page_id"), d.get("whatsapp"), d.get("segmento"),
            d.get("campanha_tipo", "MESSAGES"),
            json.dumps(d["localizacao_json"]),
            json.dumps(d.get("publico_json") or {}),
            d.get("orcamento_diario"), d.get("campanha_id_existente")
        ))
        novo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/clientes/<int:cid>", methods=["PUT"])
@login_required
def anuncios_atualizar_cliente(cid):
    d = request.get_json() or {}
    if "token_key" in d and d["token_key"] not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400

    campos, valores = [], []
    mapa = {
        "nome": "nome", "agencia": "agencia", "account_id": "account_id",
        "token_key": "token_key", "page_id": "page_id", "whatsapp": "whatsapp",
        "segmento": "segmento", "campanha_tipo": "campanha_tipo",
        "orcamento_diario": "orcamento_diario", "campanha_id_existente": "campanha_id_existente"
    }
    for k, col in mapa.items():
        if k in d:
            campos.append(f"{col} = %s")
            valores.append(d[k])
    for jk in ("localizacao_json", "publico_json"):
        if jk in d:
            campos.append(f"{jk} = %s")
            valores.append(json.dumps(d[jk]))
    if not campos:
        return jsonify({"error": "Nenhum campo para atualizar"}), 400

    campos.append("atualizado_em = NOW()")
    valores.append(cid)
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute(f"UPDATE ad_client_profiles SET {', '.join(campos)} WHERE id = %s", valores)
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anuncios/clientes/<int:cid>", methods=["DELETE"])
@login_required
def anuncios_deletar_cliente(cid):
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("DELETE FROM ad_client_profiles WHERE id = %s", (cid,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 5: Reiniciar e verificar**

```bash
fuser -k 5050/tcp 2>/dev/null; sleep 2
cd /root/jake_desktop && nohup /root/jake_desktop/venv/bin/python app.py > /tmp/jake_flask.log 2>&1 &
sleep 4 && tail -5 /tmp/jake_flask.log
```

Expected: Flask rodando sem ImportError ou AttributeError.

Verificar que a rota existe (redirecionamento = protegida por login = OK):
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/api/anuncios/clientes
```
Expected: `302`

- [ ] **Step 6: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: rotas CRUD de perfis de clientes (/api/anuncios/clientes)"
```

---

## Task 4: Rotas Flask — Meta API (campanhas, upload, copy, publicar)

**Files:**
- Modify: `jake_desktop/app.py`

- [ ] **Step 1: Adicionar rota de listar campanhas**

```python
@app.route("/api/anuncios/campanhas/<account_id>")
@login_required
def anuncios_listar_campanhas(account_id):
    token_key = request.args.get("token_key", "META_ACCESS_TOKEN")
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500
    try:
        campanhas = _meta_api.listar_campanhas(token, account_id)
        return jsonify({"campanhas": campanhas})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 2: Adicionar rota de upload de criativo**

```python
@app.route("/api/anuncios/upload-criativo", methods=["POST"])
@login_required
def anuncios_upload_criativo():
    if "arquivo" not in request.files:
        return jsonify({"error": "Campo 'arquivo' ausente"}), 400
    arquivo    = request.files["arquivo"]
    account_id = request.form.get("account_id", "")
    token_key  = request.form.get("token_key", "META_ACCESS_TOKEN")
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    if not account_id:
        return jsonify({"error": "account_id obrigatório"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    filename   = arquivo.filename or "criativo"
    file_bytes = arquivo.read()
    mime       = arquivo.content_type or ""
    try:
        if "video" in mime or filename.lower().endswith(".mp4"):
            video_id = _meta_api.upload_video(token, account_id, file_bytes, filename)
            return jsonify({"tipo": "video", "video_id": video_id, "ok": True})
        else:
            resultado = _meta_api.upload_imagem(token, account_id, file_bytes, filename)
            return jsonify({"tipo": "imagem", "hash": resultado["hash"], "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 3: Adicionar rota de geração de copy via Claude**

```python
@app.route("/api/anuncios/copy", methods=["POST"])
@login_required
def anuncios_gerar_copy():
    d            = request.get_json() or {}
    imagem_b64   = d.get("imagem_base64", "")
    mime_type    = d.get("mime_type", "image/jpeg")
    cliente_nome = d.get("cliente_nome", "cliente")
    camp_tipo    = d.get("campanha_tipo", "MESSAGES")
    segmento     = d.get("segmento", "")

    cta_sugerido = "SEND_MESSAGE" if camp_tipo == "MESSAGES" else "LEARN_MORE"
    objetivo_txt = "gerar mensagens no WhatsApp" if camp_tipo == "MESSAGES" else "gerar engajamento"

    system = (
        "Você é especialista em copywriting para anúncios do Facebook/Instagram. "
        "Crie copies curtas, diretas e persuasivas em português brasileiro. "
        "Retorne APENAS um JSON válido, sem markdown ou texto adicional."
    )
    prompt = (
        f"Analise este criativo de anúncio para '{cliente_nome}'"
        + (f" (segmento: {segmento})" if segmento else "")
        + f". Objetivo: {objetivo_txt}.\n"
        "Crie:\n"
        "- titulo: até 40 caracteres, chamativo\n"
        "- texto: até 125 caracteres, copy persuasiva\n"
        f"- cta: use exatamente '{cta_sugerido}'\n\n"
        'Responda APENAS com JSON: {"titulo":"...","texto":"...","cta":"..."}'
    )

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    try:
        content = []
        if imagem_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime_type, "data": imagem_b64}
            })
        content.append({"type": "text", "text": prompt})

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": content}]
        )
        raw = msg.content[0].text.strip()
        # Limpar possível markdown
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json\n"):
                raw = raw[5:]
        resultado = json.loads(raw)
        return jsonify(resultado)
    except json.JSONDecodeError:
        return jsonify({"error": "IA retornou formato inválido"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 4: Adicionar rota de publicação com rollback**

```python
@app.route("/api/anuncios/publicar", methods=["POST"])
@login_required
def anuncios_publicar():
    d                 = request.get_json() or {}
    cliente_id        = d.get("cliente_id")
    campanha_exist_id = d.get("campanha_existente_id")
    campanha_nome     = d.get("campanha_nome", "Campanha Jake OS")
    orcamento         = float(d.get("orcamento_diario", 0))
    creative_ref      = d.get("creative_ref", {})
    copy_data         = d.get("copy", {})

    if not cliente_id:
        return jsonify({"error": "cliente_id obrigatório"}), 400
    if not creative_ref:
        return jsonify({"error": "creative_ref obrigatório"}), 400
    if not copy_data.get("titulo") or not copy_data.get("texto"):
        return jsonify({"error": "copy.titulo e copy.texto obrigatórios"}), 400

    # Buscar perfil
    try:
        conn = _get_db()
        cur  = conn.cursor()
        cur.execute("SELECT * FROM ad_client_profiles WHERE id = %s", (cliente_id,))
        cliente = cur.fetchone()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar cliente: {e}"}), 500

    if not cliente:
        return jsonify({"error": "Cliente não encontrado"}), 404

    # Hard block: localização
    localizacao = cliente.get("localizacao_json") or {}
    tem_loc = localizacao and (localizacao.get("paises") or localizacao.get("cidades"))
    if not tem_loc:
        return jsonify({"error": "Localização não configurada — publicação bloqueada"}), 400

    # Hard block: page_id obrigatório para AdCreative
    page_id = cliente.get("page_id", "")
    if not page_id:
        return jsonify({"error": "page_id não configurado no perfil do cliente"}), 400

    token_key  = cliente["token_key"]
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token      = os.getenv(token_key, "")
    account_id = cliente["account_id"]
    camp_tipo  = cliente.get("campanha_tipo", "MESSAGES")
    publico    = cliente.get("publico_json") or {}

    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    campaign_id = adset_id = ad_id = None
    try:
        # Passo 1: Campanha
        if campanha_exist_id:
            campaign_id = campanha_exist_id
        else:
            cbo = camp_tipo == "MESSAGES"
            campaign_id = _meta_api.criar_campanha(
                token, account_id, camp_tipo, campanha_nome, orcamento, cbo=cbo
            )

        # Passo 2: Conjunto
        try:
            adset_id = _meta_api.criar_conjunto(
                token, account_id, campaign_id, camp_tipo, publico, localizacao,
                orcamento=(orcamento if camp_tipo == "ENGAGEMENT" else None)
            )
        except Exception as e2:
            if not campanha_exist_id:
                _meta_api.deletar_objeto_meta(token, campaign_id)
            raise Exception(f"Falha no conjunto (campanha removida): {e2}")

        # Passo 3: Anúncio
        try:
            ad_id = _meta_api.criar_anuncio(
                token, account_id, adset_id, page_id, creative_ref,
                copy_data["titulo"], copy_data["texto"],
                copy_data.get("cta", "SEND_MESSAGE")
            )
        except Exception as e3:
            _meta_api.deletar_objeto_meta(token, adset_id)
            if not campanha_exist_id:
                _meta_api.deletar_objeto_meta(token, campaign_id)
            raise Exception(f"Falha no anúncio (conjunto e campanha removidos): {e3}")

        # Sucesso — log
        try:
            conn = _get_db()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO ad_publish_log
                    (cliente_id, account_id, campaign_id, adset_id, ad_id, status, payload_json)
                VALUES (%s,%s,%s,%s,%s,'sucesso',%s)
            """, (cliente_id, account_id, campaign_id, adset_id, ad_id, json.dumps(d)))
            conn.commit()
            conn.close()
        except Exception:
            pass  # falha no log não bloqueia retorno de sucesso

        return jsonify({
            "ok": True,
            "campaign_id": campaign_id,
            "adset_id": adset_id,
            "ad_id": ad_id,
            "msg": "Anúncio criado com status PAUSADO. Ative no Gerenciador da Meta para publicar."
        })

    except Exception as e:
        try:
            conn = _get_db()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO ad_publish_log
                    (cliente_id, account_id, campaign_id, adset_id, ad_id, status, erro_msg, payload_json)
                VALUES (%s,%s,%s,%s,%s,'erro',%s,%s)
            """, (cliente_id, account_id, campaign_id, adset_id, ad_id, str(e), json.dumps(d)))
            conn.commit()
            conn.close()
        except Exception:
            pass
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 5: Reiniciar e verificar**

```bash
fuser -k 5050/tcp 2>/dev/null; sleep 2
cd /root/jake_desktop && nohup /root/jake_desktop/venv/bin/python app.py > /tmp/jake_flask.log 2>&1 &
sleep 4 && tail -8 /tmp/jake_flask.log
```

Expected: sem ImportError. Todas as rotas retornam 302 (redirect para login):
```bash
for rota in "/api/anuncios/clientes" "/api/anuncios/campanhas/test"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5050$rota")
  echo "$rota → $code"
done
```
Expected: ambas `→ 302`

- [ ] **Step 6: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: rotas Meta API (campanhas, upload, copy IA, publicar com rollback)"
```

---

## Task 5: HTML — Substituir placeholder

**Files:**
- Modify: `jake_desktop/templates/dashboard.html`

O arquivo tem ~1300 linhas — ler em blocos. O placeholder está nas linhas 314-326.

- [ ] **Step 1: Localizar e substituir o bloco page-anuncios**

Localizar (grep para confirmar linha atual):
```bash
grep -n "page-anuncios\|placeholder-page" /root/jake_desktop/templates/dashboard.html
```

Substituir o bloco `<section class="page" id="page-anuncios">...</section>` por:

```html
      <section class="page" id="page-anuncios">
        <div class="anu-layout">

          <!-- ── Sidebar de Clientes ── -->
          <aside class="anu-sidebar">
            <div class="anu-sidebar-header">
              <span class="anu-sidebar-title">Clientes</span>
              <button class="anu-btn-icon" id="anu-btn-refresh-clientes" title="Recarregar">↺</button>
            </div>
            <div class="anu-agencia-group">
              <div class="anu-agencia-header">
                <span>📁 Piloti</span>
                <button class="anu-btn-novo-cliente" data-agencia="piloti">+</button>
              </div>
              <ul class="anu-cliente-list" id="anu-lista-piloti"></ul>
            </div>
            <div class="anu-agencia-group">
              <div class="anu-agencia-header">
                <span>📁 Dentto</span>
                <button class="anu-btn-novo-cliente" data-agencia="dentto">+</button>
              </div>
              <ul class="anu-cliente-list" id="anu-lista-dentto"></ul>
            </div>
            <div class="anu-agencia-group">
              <div class="anu-agencia-header">
                <span>📁 Freelance</span>
                <button class="anu-btn-novo-cliente" data-agencia="freelance">+</button>
              </div>
              <ul class="anu-cliente-list" id="anu-lista-freelance"></ul>
            </div>
          </aside>

          <!-- ── Área Principal ── -->
          <main class="anu-main">

            <div class="anu-empty-state" id="anu-empty">
              <div class="anu-empty-icon">◈</div>
              <p class="anu-empty-text">Selecione um cliente na sidebar<br>para começar</p>
            </div>

            <!-- Formulário de perfil -->
            <div class="anu-perfil-form hidden" id="anu-perfil-form">
              <div class="anu-bloco">
                <div class="anu-bloco-header">
                  <span class="anu-bloco-num">✎</span>
                  <h3 class="anu-bloco-title" id="anu-perfil-titulo">Novo Cliente</h3>
                </div>
                <div class="anu-perfil-grid">
                  <label class="anu-label">Nome do cliente<input type="text" id="anu-pf-nome" class="anu-input" placeholder="Ex: Clínica Odonto"></label>
                  <label class="anu-label">Agência<select id="anu-pf-agencia" class="anu-select"><option value="piloti">Piloti</option><option value="dentto">Dentto</option><option value="freelance">Freelance</option></select></label>
                  <label class="anu-label">Account ID (Meta)<input type="text" id="anu-pf-account-id" class="anu-input" placeholder="act_XXXXXXXXX"></label>
                  <label class="anu-label">Token<select id="anu-pf-token-key" class="anu-select"><option value="META_TOKEN_PILOTI">META_TOKEN_PILOTI</option><option value="META_TOKEN_DENTTO">META_TOKEN_DENTTO</option><option value="META_ACCESS_TOKEN">META_ACCESS_TOKEN</option></select></label>
                  <label class="anu-label">Page ID (Facebook)<input type="text" id="anu-pf-page-id" class="anu-input" placeholder="Ex: 123456789"><span class="anu-hint">⚠ Obrigatório para criar anúncios</span></label>
                  <label class="anu-label">WhatsApp<input type="text" id="anu-pf-whatsapp" class="anu-input" placeholder="+5554999999999"></label>
                  <label class="anu-label">Segmento<input type="text" id="anu-pf-segmento" class="anu-input" placeholder="Ex: odontologia, advocacia"></label>
                  <label class="anu-label">Tipo campanha padrão<select id="anu-pf-camp-tipo" class="anu-select"><option value="MESSAGES">Mensagem (WhatsApp)</option><option value="ENGAGEMENT">Engajamento</option></select></label>
                  <label class="anu-label">Orçamento diário (R$)<input type="number" id="anu-pf-orcamento" class="anu-input" placeholder="30.00" step="0.01" min="1"></label>
                  <label class="anu-label anu-label-full">Localização (JSON)<textarea id="anu-pf-localizacao" class="anu-textarea" rows="3" placeholder='{"paises": ["BR"], "cidades": [{"key": "1521902", "radius": 15, "distance_unit": "kilometer"}]}'></textarea><span class="anu-hint">⚠ Obrigatório — sem localização a publicação é bloqueada</span></label>
                  <label class="anu-label anu-label-full">Público (JSON)<textarea id="anu-pf-publico" class="anu-textarea" rows="2" placeholder='{"idade_min": 25, "idade_max": 55, "genero": [1, 2]}'></textarea></label>
                </div>
                <div class="anu-perfil-actions">
                  <button class="anu-btn-secondary" id="anu-perfil-cancelar">Cancelar</button>
                  <button class="anu-btn-primary" id="anu-perfil-salvar">Salvar Perfil</button>
                </div>
              </div>
            </div>

            <!-- Blocos de criação -->
            <div class="anu-criacao hidden" id="anu-criacao">
              <div class="anu-cliente-header">
                <span class="anu-cliente-nome" id="anu-cliente-nome-display">—</span>
                <button class="anu-btn-icon" id="anu-btn-editar-cliente" title="Editar perfil">✎</button>
              </div>

              <!-- Bloco 1: Campanha -->
              <div class="anu-bloco">
                <div class="anu-bloco-header">
                  <span class="anu-bloco-num">①</span>
                  <h3 class="anu-bloco-title">Campanha</h3>
                  <span class="anu-bloco-status" id="anu-status-campanha">—</span>
                </div>
                <div class="anu-toggle-row">
                  <button class="anu-toggle-btn active" id="anu-camp-nova-btn" data-mode="nova">Nova campanha</button>
                  <button class="anu-toggle-btn" id="anu-camp-exist-btn" data-mode="existente">Usar existente</button>
                </div>
                <div id="anu-camp-nova-form">
                  <label class="anu-label">Nome da campanha<input type="text" id="anu-camp-nome" class="anu-input" placeholder="Campanha Março 2026"></label>
                  <label class="anu-label">Objetivo<input type="text" id="anu-camp-objetivo" class="anu-input" readonly></label>
                  <label class="anu-label">Orçamento diário (R$)<input type="number" id="anu-camp-orcamento" class="anu-input" step="0.01" min="1"></label>
                </div>
                <div id="anu-camp-exist-form" class="hidden">
                  <label class="anu-label">Campanha existente<select id="anu-camp-select" class="anu-select"><option value="">Carregando...</option></select></label>
                  <button class="anu-btn-secondary" id="anu-camp-carregar">↺ Carregar campanhas</button>
                </div>
              </div>

              <!-- Bloco 2: Criativo -->
              <div class="anu-bloco">
                <div class="anu-bloco-header">
                  <span class="anu-bloco-num">②</span>
                  <h3 class="anu-bloco-title">Criativo</h3>
                  <span class="anu-bloco-status" id="anu-status-criativo">—</span>
                </div>
                <div class="anu-dropzone" id="anu-dropzone">
                  <input type="file" id="anu-file-input" accept="image/jpeg,image/png,video/mp4" class="anu-file-hidden">
                  <div class="anu-dropzone-inner" id="anu-dropzone-inner">
                    <span class="anu-dropzone-icon">⬆</span>
                    <p>Arraste ou clique para selecionar<br><small>JPG, PNG ou MP4</small></p>
                  </div>
                  <div class="anu-preview hidden" id="anu-preview"></div>
                </div>
                <div class="anu-upload-progress hidden" id="anu-upload-progress">
                  <div class="anu-progress-bar"><div class="anu-progress-fill" id="anu-progress-fill"></div></div>
                  <span id="anu-progress-msg">Enviando...</span>
                </div>
              </div>

              <!-- Bloco 3: Copy IA -->
              <div class="anu-bloco">
                <div class="anu-bloco-header">
                  <span class="anu-bloco-num">③</span>
                  <h3 class="anu-bloco-title">Copy</h3>
                  <span class="anu-bloco-status" id="anu-status-copy">—</span>
                </div>
                <div class="anu-copy-loading hidden" id="anu-copy-loading">
                  <span class="anu-spinner"></span> Jake gerando copy...
                </div>
                <div id="anu-copy-form">
                  <label class="anu-label">Título <small>(máx 40 caracteres)</small><input type="text" id="anu-copy-titulo" class="anu-input" maxlength="40"><span class="anu-char-count" id="anu-titulo-count">0/40</span></label>
                  <label class="anu-label">Texto principal <small>(máx 125 caracteres)</small><textarea id="anu-copy-texto" class="anu-textarea" rows="3" maxlength="125"></textarea><span class="anu-char-count" id="anu-texto-count">0/125</span></label>
                  <label class="anu-label">CTA<select id="anu-copy-cta" class="anu-select"><option value="SEND_MESSAGE">Enviar mensagem (WhatsApp)</option><option value="LEARN_MORE">Saiba mais</option><option value="SIGN_UP">Cadastre-se</option></select></label>
                  <button class="anu-btn-secondary" id="anu-copy-regerar">↺ Regerar copy</button>
                </div>
              </div>

              <!-- Bloco 4: Revisão -->
              <div class="anu-bloco anu-bloco-revisao">
                <div class="anu-bloco-header">
                  <span class="anu-bloco-num">④</span>
                  <h3 class="anu-bloco-title">Revisão Final</h3>
                </div>
                <div class="anu-revisao-grid" id="anu-revisao-grid"></div>
                <div class="anu-localizacao-alerta hidden" id="anu-localizacao-alerta">⚠ Localização não configurada — edite o perfil do cliente antes de publicar</div>
                <button class="anu-btn-publicar" id="anu-btn-publicar" disabled>🚀 Publicar Anúncio</button>
              </div>
            </div>

          </main>
        </div>

        <!-- Modal de confirmação -->
        <div class="anu-modal-overlay hidden" id="anu-modal-overlay">
          <div class="anu-modal">
            <h3 class="anu-modal-title">⚠ Confirmar publicação</h3>
            <p class="anu-modal-sub">O anúncio será criado na Meta com status <strong>PAUSADO</strong>.<br>Você ativa manualmente no Gerenciador após revisão.</p>
            <div class="anu-modal-resumo" id="anu-modal-resumo"></div>
            <div class="anu-modal-actions">
              <button class="anu-btn-secondary" id="anu-modal-cancelar">Cancelar</button>
              <button class="anu-btn-publicar-confirm" id="anu-modal-confirmar">Confirmar e Criar</button>
            </div>
          </div>
        </div>
      </section>
```

- [ ] **Step 2: Adicionar CSS e script no dashboard.html**

No `<head>`, junto aos outros CSS:
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/anuncios.css') }}">
```

Antes do `</body>`, junto aos outros scripts:
```html
<script src="{{ url_for('static', filename='js/anuncios.js') }}"></script>
```

- [ ] **Step 3: Commit**

```bash
git add jake_desktop/templates/dashboard.html
git commit -m "feat: HTML da aba Subir Anúncios (layout completo com page_id e segmento)"
```

---

## Task 6: CSS da aba anúncios

**Files:**
- Create: `jake_desktop/static/css/anuncios.css`

- [ ] **Step 1: Criar arquivo**

```css
/* ──────────────────────────────────────────────────────
   Jake OS — Aba Subir Anúncios
────────────────────────────────────────────────────── */
.anu-layout { display:grid; grid-template-columns:240px 1fr; height:100%; overflow:hidden; }
.anu-sidebar { background:rgba(0,0,0,.3); border-right:1px solid rgba(0,229,255,.1); overflow-y:auto; padding:1rem 0; }
.anu-sidebar-header { display:flex; align-items:center; justify-content:space-between; padding:0 1rem .75rem; border-bottom:1px solid rgba(0,229,255,.08); margin-bottom:.5rem; }
.anu-sidebar-title { font-family:var(--ff-h); font-size:.85rem; letter-spacing:.1em; text-transform:uppercase; color:rgba(176,190,197,.6); }
.anu-agencia-header { display:flex; align-items:center; justify-content:space-between; padding:.4rem 1rem; font-size:.8rem; color:rgba(176,190,197,.5); letter-spacing:.06em; }
.anu-btn-novo-cliente { background:rgba(0,229,255,.08); border:1px solid rgba(0,229,255,.2); color:#00e5ff; width:22px; height:22px; border-radius:50%; font-size:.9rem; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:background .2s; }
.anu-btn-novo-cliente:hover { background:rgba(0,229,255,.18); }
.anu-cliente-list { list-style:none; padding:0; margin:0; }
.anu-cliente-item { display:flex; align-items:center; padding:.45rem 1rem .45rem 1.5rem; font-size:.82rem; color:#b0bec5; cursor:pointer; border-left:2px solid transparent; transition:all .15s; gap:.5rem; }
.anu-cliente-item:hover { background:rgba(0,229,255,.05); color:#fff; }
.anu-cliente-item.active { border-left-color:#00e5ff; background:rgba(0,229,255,.08); color:#00e5ff; }
.anu-cliente-edit-btn { margin-left:auto; opacity:0; background:none; border:none; color:rgba(0,229,255,.6); cursor:pointer; font-size:.8rem; padding:0; transition:opacity .15s; }
.anu-cliente-item:hover .anu-cliente-edit-btn, .anu-cliente-item.active .anu-cliente-edit-btn { opacity:1; }
.anu-main { overflow-y:auto; padding:1.5rem; display:flex; flex-direction:column; gap:1rem; }
.anu-empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; height:60%; gap:1rem; opacity:.4; }
.anu-empty-icon { font-size:2.5rem; color:#00e5ff; }
.anu-empty-text { text-align:center; color:#b0bec5; line-height:1.6; }
.anu-cliente-header { display:flex; align-items:center; gap:.75rem; padding-bottom:.75rem; border-bottom:1px solid rgba(0,229,255,.1); }
.anu-cliente-nome { font-family:var(--ff-h); font-size:1.2rem; color:#00e5ff; }
.anu-bloco { background:rgba(0,229,255,.03); border:1px solid rgba(0,229,255,.1); border-radius:10px; padding:1.1rem 1.2rem; }
.anu-bloco-header { display:flex; align-items:center; gap:.6rem; margin-bottom:.9rem; }
.anu-bloco-num { font-family:var(--ff-h); font-size:1rem; color:#00e5ff; min-width:24px; }
.anu-bloco-title { font-family:var(--ff-h); font-size:.95rem; color:#e0e0e0; margin:0; }
.anu-bloco-status { margin-left:auto; font-size:.75rem; padding:.15rem .5rem; border-radius:20px; background:rgba(176,190,197,.08); color:rgba(176,190,197,.5); }
.anu-bloco-status.ok { background:rgba(105,240,174,.1); color:#69f0ae; }
.anu-bloco-status.erro { background:rgba(255,82,82,.1); color:#ff5252; }
.anu-bloco-revisao { border-color:rgba(0,229,255,.25); }
.anu-label { display:flex; flex-direction:column; gap:.3rem; font-size:.78rem; letter-spacing:.05em; text-transform:uppercase; color:rgba(176,190,197,.5); margin-bottom:.75rem; }
.anu-input, .anu-select, .anu-textarea { background:rgba(0,0,0,.3); border:1px solid rgba(0,229,255,.15); border-radius:6px; color:#e0e0e0; padding:.5rem .75rem; font-size:.88rem; font-family:var(--ff-b); width:100%; transition:border-color .2s; box-sizing:border-box; }
.anu-input:focus, .anu-select:focus, .anu-textarea:focus { outline:none; border-color:rgba(0,229,255,.5); }
.anu-hint { font-size:.72rem; color:#ffd740; margin-top:.2rem; text-transform:none; letter-spacing:0; }
.anu-char-count { font-size:.7rem; color:rgba(176,190,197,.4); text-align:right; text-transform:none; }
.anu-perfil-grid { display:grid; grid-template-columns:1fr 1fr; gap:.75rem 1rem; }
.anu-label-full { grid-column:1/-1; }
.anu-perfil-actions { display:flex; justify-content:flex-end; gap:.75rem; margin-top:1rem; padding-top:.75rem; border-top:1px solid rgba(0,229,255,.08); }
.anu-toggle-row { display:flex; gap:.4rem; margin-bottom:.9rem; }
.anu-toggle-btn { background:rgba(0,0,0,.2); border:1px solid rgba(0,229,255,.15); color:rgba(176,190,197,.6); border-radius:6px; padding:.35rem .8rem; font-size:.8rem; cursor:pointer; transition:all .2s; }
.anu-toggle-btn.active { background:rgba(0,229,255,.12); border-color:rgba(0,229,255,.4); color:#00e5ff; }
.anu-dropzone { border:2px dashed rgba(0,229,255,.2); border-radius:10px; padding:2rem; text-align:center; cursor:pointer; transition:border-color .2s,background .2s; position:relative; }
.anu-dropzone:hover,.anu-dropzone.dragover { border-color:rgba(0,229,255,.5); background:rgba(0,229,255,.04); }
.anu-file-hidden { position:absolute; inset:0; opacity:0; cursor:pointer; width:100%; height:100%; }
.anu-dropzone-icon { font-size:1.8rem; color:rgba(0,229,255,.4); display:block; margin-bottom:.5rem; }
.anu-dropzone p { color:rgba(176,190,197,.6); font-size:.85rem; margin:0; }
.anu-preview { margin-top:.75rem; }
.anu-preview img, .anu-preview video { max-width:100%; max-height:200px; border-radius:8px; border:1px solid rgba(0,229,255,.2); }
.anu-upload-progress { margin-top:.75rem; }
.anu-progress-bar { height:4px; background:rgba(0,229,255,.1); border-radius:2px; overflow:hidden; margin-bottom:.4rem; }
.anu-progress-fill { height:100%; background:#00e5ff; width:0%; transition:width .3s; animation:anu-pulse 1.5s ease-in-out infinite; }
@keyframes anu-pulse { 0%,100% { opacity:.7; } 50% { opacity:1; } }
.anu-copy-loading { display:flex; align-items:center; gap:.6rem; color:#00e5ff; font-size:.85rem; padding:.5rem 0; }
.anu-spinner { width:16px; height:16px; border:2px solid rgba(0,229,255,.2); border-top-color:#00e5ff; border-radius:50%; animation:spin .7s linear infinite; display:inline-block; }
@keyframes spin { to { transform:rotate(360deg); } }
.anu-revisao-grid { display:grid; grid-template-columns:1fr 1fr; gap:.6rem; margin-bottom:1rem; }
.anu-revisao-item { background:rgba(0,0,0,.2); border-radius:8px; padding:.6rem .8rem; display:flex; flex-direction:column; gap:.2rem; }
.anu-revisao-label { font-size:.7rem; color:rgba(176,190,197,.4); text-transform:uppercase; letter-spacing:.06em; }
.anu-revisao-val { font-size:.85rem; color:#e0e0e0; }
.anu-revisao-ok::before { content:'✓ '; color:#69f0ae; }
.anu-revisao-erro::before { content:'✕ '; color:#ff5252; }
.anu-localizacao-alerta { background:rgba(255,82,82,.08); border:1px solid rgba(255,82,82,.25); border-radius:8px; padding:.7rem 1rem; color:#ff5252; font-size:.84rem; margin-bottom:.75rem; }
.anu-btn-primary { background:rgba(0,229,255,.12); border:1px solid rgba(0,229,255,.35); color:#00e5ff; border-radius:8px; padding:.55rem 1.2rem; font-size:.85rem; cursor:pointer; transition:all .2s; }
.anu-btn-primary:hover { background:rgba(0,229,255,.2); }
.anu-btn-secondary { background:rgba(176,190,197,.06); border:1px solid rgba(176,190,197,.15); color:rgba(176,190,197,.7); border-radius:8px; padding:.55rem 1.2rem; font-size:.85rem; cursor:pointer; transition:all .2s; }
.anu-btn-secondary:hover { background:rgba(176,190,197,.12); color:#b0bec5; }
.anu-btn-icon { background:none; border:none; color:rgba(0,229,255,.5); cursor:pointer; font-size:.9rem; padding:.2rem .4rem; border-radius:4px; transition:color .15s,background .15s; }
.anu-btn-icon:hover { color:#00e5ff; background:rgba(0,229,255,.08); }
.anu-btn-publicar { width:100%; background:linear-gradient(135deg,rgba(0,229,255,.15),rgba(105,240,174,.1)); border:1px solid rgba(0,229,255,.35); color:#00e5ff; border-radius:10px; padding:.85rem; font-family:var(--ff-h); font-size:1rem; letter-spacing:.06em; cursor:pointer; transition:all .2s; }
.anu-btn-publicar:hover:not(:disabled) { background:linear-gradient(135deg,rgba(0,229,255,.25),rgba(105,240,174,.18)); box-shadow:0 0 20px rgba(0,229,255,.15); }
.anu-btn-publicar:disabled { opacity:.35; cursor:not-allowed; filter:grayscale(.5); }
.anu-modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,.65); z-index:9999; display:flex; align-items:center; justify-content:center; }
.anu-modal { background:#0d1117; border:1px solid rgba(0,229,255,.25); border-radius:14px; padding:2rem; max-width:480px; width:90%; box-shadow:0 0 40px rgba(0,229,255,.1); }
.anu-modal-title { font-family:var(--ff-h); color:#ffd740; margin:0 0 .5rem; }
.anu-modal-sub { color:rgba(176,190,197,.7); font-size:.85rem; margin:0 0 1rem; line-height:1.6; }
.anu-modal-resumo { background:rgba(0,229,255,.04); border:1px solid rgba(0,229,255,.1); border-radius:8px; padding:.9rem 1rem; font-size:.82rem; color:#b0bec5; line-height:1.7; margin-bottom:1.25rem; }
.anu-modal-actions { display:flex; justify-content:flex-end; gap:.75rem; }
.anu-btn-publicar-confirm { background:rgba(0,229,255,.15); border:1px solid rgba(0,229,255,.4); color:#00e5ff; border-radius:8px; padding:.55rem 1.4rem; font-size:.88rem; cursor:pointer; font-family:var(--ff-h); transition:all .2s; }
.anu-btn-publicar-confirm:hover { background:rgba(0,229,255,.25); }
.anu-btn-publicar-confirm.loading { opacity:.6; pointer-events:none; }
.hidden { display:none !important; }
```

- [ ] **Step 2: Commit**

```bash
git add jake_desktop/static/css/anuncios.css
git commit -m "feat: CSS da aba Subir Anúncios"
```

---

## Task 7: JavaScript — anuncios.js (sidebar + gerenciamento de clientes)

**Files:**
- Create: `jake_desktop/static/js/anuncios.js`

- [ ] **Step 1: Criar o arquivo com IIFE, estado e sidebar**

```javascript
/* ──────────────────────────────────────────────────────
   Jake OS — Módulo Subir Anúncios
────────────────────────────────────────────────────── */
(function () {
  'use strict';

  // ── Estado ─────────────────────────────────────────
  var _clientes     = [];
  var _clienteAtivo = null;
  var _modoPerfilId = null;    // null=novo, int=editando
  var _creativeRef  = null;    // {tipo, hash|video_id}
  var _creativeB64  = null;    // base64 da imagem para copy
  var _creativeMime = null;

  // ── Init ───────────────────────────────────────────
  function init() {
    carregarClientes();
    bindSidebarEvents();
    bindPerfilFormEvents();
    bindCampanhaEvents();
    bindCreativoEvents();
    bindCopyEvents();
    bindRevisaoEvents();
    bindModalEvents();
  }

  // ── Carregar e renderizar clientes ─────────────────
  function carregarClientes() {
    fetch('/api/anuncios/clientes')
      .then(function(r){ return r.json(); })
      .then(function(d){ _clientes = d.clientes || []; renderSidebar(); })
      .catch(function(e){ console.error('Erro ao carregar clientes:', e); });
  }

  function renderSidebar() {
    var grupos = { piloti:[], dentto:[], freelance:[] };
    _clientes.forEach(function(c){ if(grupos[c.agencia]) grupos[c.agencia].push(c); });
    ['piloti','dentto','freelance'].forEach(function(ag) {
      var ul = document.getElementById('anu-lista-'+ag);
      if (!ul) return;
      ul.innerHTML = grupos[ag].map(function(c) {
        var ativo = _clienteAtivo && _clienteAtivo.id===c.id ? ' active':'';
        return '<li class="anu-cliente-item'+ativo+'" data-id="'+c.id+'">' +
          '<span>'+_esc(c.nome)+'</span>' +
          '<button class="anu-cliente-edit-btn" data-id="'+c.id+'" title="Editar">✎</button>' +
          '</li>';
      }).join('');
      ul.querySelectorAll('.anu-cliente-item').forEach(function(li) {
        li.addEventListener('click', function(e) {
          if (e.target.classList.contains('anu-cliente-edit-btn')) return;
          selecionarCliente(parseInt(this.dataset.id));
        });
      });
      ul.querySelectorAll('.anu-cliente-edit-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          abrirFormPerfil(parseInt(this.dataset.id));
        });
      });
    });
  }

  function selecionarCliente(id) {
    _clienteAtivo = _clientes.find(function(c){ return c.id===id; }) || null;
    renderSidebar();
    mostrarCriacao();
  }

  function bindSidebarEvents() {
    var r = document.getElementById('anu-btn-refresh-clientes');
    if (r) r.addEventListener('click', carregarClientes);
    document.querySelectorAll('.anu-btn-novo-cliente').forEach(function(btn) {
      btn.addEventListener('click', function(){ abrirFormPerfil(null, this.dataset.agencia); });
    });
  }

  // ── Formulário de perfil ────────────────────────────
  function abrirFormPerfil(id, agenciaPadrao) {
    _modoPerfilId = id || null;
    _setText('anu-perfil-titulo', id ? 'Editar Cliente' : 'Novo Cliente');
    ['anu-pf-nome','anu-pf-account-id','anu-pf-page-id','anu-pf-whatsapp','anu-pf-segmento','anu-pf-orcamento'].forEach(function(fid){
      var el=document.getElementById(fid); if(el) el.value='';
    });
    var elLoc=document.getElementById('anu-pf-localizacao'); if(elLoc) elLoc.value='';
    var elPub=document.getElementById('anu-pf-publico');     if(elPub) elPub.value='';

    if (id) {
      var c = _clientes.find(function(x){ return x.id===id; });
      if (c) preencherFormPerfil(c);
    } else if (agenciaPadrao) {
      _set('anu-pf-agencia', agenciaPadrao);
    }
    esconder('anu-empty'); esconder('anu-criacao'); mostrar('anu-perfil-form');
  }

  function preencherFormPerfil(c) {
    _set('anu-pf-nome',       c.nome);
    _set('anu-pf-agencia',    c.agencia);
    _set('anu-pf-account-id', c.account_id);
    _set('anu-pf-token-key',  c.token_key);
    _set('anu-pf-page-id',    c.page_id||'');
    _set('anu-pf-whatsapp',   c.whatsapp||'');
    _set('anu-pf-segmento',   c.segmento||'');
    _set('anu-pf-camp-tipo',  c.campanha_tipo||'MESSAGES');
    _set('anu-pf-orcamento',  c.orcamento_diario||'');
    var elLoc=document.getElementById('anu-pf-localizacao');
    if (elLoc) elLoc.value = c.localizacao_json ? JSON.stringify(c.localizacao_json,null,2):'';
    var elPub=document.getElementById('anu-pf-publico');
    if (elPub) elPub.value = c.publico_json ? JSON.stringify(c.publico_json,null,2):'';
  }

  function bindPerfilFormEvents() {
    var s=document.getElementById('anu-perfil-salvar');   if(s) s.addEventListener('click',salvarPerfil);
    var c=document.getElementById('anu-perfil-cancelar'); if(c) c.addEventListener('click',function(){
      esconder('anu-perfil-form');
      if (_clienteAtivo) mostrarCriacao(); else mostrar('anu-empty');
    });
    var e=document.getElementById('anu-btn-editar-cliente'); if(e) e.addEventListener('click',function(){
      if (_clienteAtivo) abrirFormPerfil(_clienteAtivo.id);
    });
  }

  function salvarPerfil() {
    var nome=_val('anu-pf-nome').trim(), account_id=_val('anu-pf-account-id').trim();
    var locStr=_val('anu-pf-localizacao').trim();
    if (!nome||!account_id||!locStr){ alert('Nome, Account ID e Localização são obrigatórios.'); return; }
    var loc,pub;
    try { loc=JSON.parse(locStr); } catch(e){ alert('Localização inválida — verifique o JSON.'); return; }
    var pubStr=_val('anu-pf-publico').trim();
    try { pub=pubStr?JSON.parse(pubStr):{};} catch(e){ alert('Público inválido — verifique o JSON.'); return; }

    var payload={
      nome:nome, agencia:_val('anu-pf-agencia'), account_id:account_id,
      token_key:_val('anu-pf-token-key'), page_id:_val('anu-pf-page-id'),
      whatsapp:_val('anu-pf-whatsapp'), segmento:_val('anu-pf-segmento'),
      campanha_tipo:_val('anu-pf-camp-tipo'),
      orcamento_diario:parseFloat(_val('anu-pf-orcamento'))||null,
      localizacao_json:loc, publico_json:pub
    };
    var url=_modoPerfilId?'/api/anuncios/clientes/'+_modoPerfilId:'/api/anuncios/clientes';
    var method=_modoPerfilId?'PUT':'POST';

    fetch(url,{method:method,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){return r.json();})
      .then(function(data){
        if(data.error){alert('Erro: '+data.error);return;}
        var salvoId=_modoPerfilId||data.id;
        carregarClientes();
        // Re-selecionar cliente após salvar
        fetch('/api/anuncios/clientes')
          .then(function(r){return r.json();})
          .then(function(d){
            _clientes=d.clientes||[];
            _clienteAtivo=_clientes.find(function(c){return c.id===salvoId;})||null;
            renderSidebar();
            esconder('anu-perfil-form');
            if(_clienteAtivo) mostrarCriacao(); else mostrar('anu-empty');
          });
      })
      .catch(function(e){alert('Erro de rede: '+e);});
  }

  // ── Mostrar blocos de criação ───────────────────────
  function mostrarCriacao() {
    if (!_clienteAtivo) return;
    esconder('anu-empty'); esconder('anu-perfil-form'); mostrar('anu-criacao');
    _setText('anu-cliente-nome-display', _clienteAtivo.nome);
    _set('anu-camp-objetivo', _clienteAtivo.campanha_tipo||'MESSAGES');
    _set('anu-camp-orcamento', _clienteAtivo.orcamento_diario||'');
    atualizarRevisao();
  }

  // ── Utilitários ─────────────────────────────────────
  function _val(id){var el=document.getElementById(id);return el?el.value:'';}
  function _set(id,v){var el=document.getElementById(id);if(el)el.value=v||'';}
  function _setText(id,t){var el=document.getElementById(id);if(el)el.textContent=t||'';}
  function _esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function mostrar(id){var el=document.getElementById(id);if(el)el.classList.remove('hidden');}
  function esconder(id){var el=document.getElementById(id);if(el)el.classList.add('hidden');}

  // ── Stubs (implementados nas tasks seguintes) ───────
  function bindCampanhaEvents(){}
  function bindCreativoEvents(){}
  function bindCopyEvents(){}
  function bindRevisaoEvents(){}
  function bindModalEvents(){}
  function atualizarRevisao(){}

  // ── Observer ────────────────────────────────────────
  var _iniciado=false;
  var _obs=new MutationObserver(function(muts){
    muts.forEach(function(m){
      if(m.target.id==='page-anuncios'&&m.target.classList.contains('active')){
        if(!_iniciado){_iniciado=true;init();}
      }
    });
  });
  var pageAnu=document.getElementById('page-anuncios');
  if(pageAnu){
    _obs.observe(pageAnu,{attributes:true,attributeFilter:['class']});
    if(pageAnu.classList.contains('active')){_iniciado=true;init();}
  }

})();
```

- [ ] **Step 2: Testar sidebar**

Reiniciar e acessar http://localhost:5050/#anuncios. Verificar:
- Sidebar exibe os 3 grupos (Piloti/Dentto/Freelance)
- Botão "+" abre formulário de novo cliente com campo Page ID e Segmento
- Salvar cliente exibe na lista

- [ ] **Step 3: Commit**

```bash
git add jake_desktop/static/js/anuncios.js
git commit -m "feat: anuncios.js — sidebar e formulário de perfis de clientes"
```

---

## Task 8: JavaScript — blocos campanha e criativo

**Files:**
- Modify: `jake_desktop/static/js/anuncios.js`

- [ ] **Step 1: Substituir stub bindCampanhaEvents**

```javascript
  function bindCampanhaEvents() {
    var btnNova=document.getElementById('anu-camp-nova-btn');
    var btnExist=document.getElementById('anu-camp-exist-btn');
    if(btnNova) btnNova.addEventListener('click',function(){
      btnNova.classList.add('active'); btnExist.classList.remove('active');
      mostrar('anu-camp-nova-form'); esconder('anu-camp-exist-form');
      atualizarStatusCampanha();
    });
    if(btnExist) btnExist.addEventListener('click',function(){
      btnExist.classList.add('active'); btnNova.classList.remove('active');
      esconder('anu-camp-nova-form'); mostrar('anu-camp-exist-form');
      if(_clienteAtivo) carregarCampanhasExistentes();
    });
    var btnCarregar=document.getElementById('anu-camp-carregar');
    if(btnCarregar) btnCarregar.addEventListener('click',carregarCampanhasExistentes);
    ['anu-camp-nome','anu-camp-orcamento'].forEach(function(id){
      var el=document.getElementById(id);
      if(el) el.addEventListener('input',function(){atualizarStatusCampanha();atualizarRevisao();});
    });
  }

  function carregarCampanhasExistentes() {
    if(!_clienteAtivo) return;
    var sel=document.getElementById('anu-camp-select');
    if(sel) sel.innerHTML='<option>Carregando...</option>';
    fetch('/api/anuncios/campanhas/'+_clienteAtivo.account_id+'?token_key='+_clienteAtivo.token_key)
      .then(function(r){return r.json();})
      .then(function(data){
        if(!sel) return;
        if(data.error){sel.innerHTML='<option>Erro: '+_esc(data.error)+'</option>';return;}
        sel.innerHTML=(data.campanhas||[]).map(function(c){
          return '<option value="'+_esc(c.id)+'">'+_esc(c.name)+' ('+_esc(c.objective)+')</option>';
        }).join('')||'<option value="">Nenhuma campanha ativa</option>';
        atualizarStatusCampanha(); atualizarRevisao();
      })
      .catch(function(){if(sel) sel.innerHTML='<option>Erro de rede</option>';});
  }

  function atualizarStatusCampanha() {
    var el=document.getElementById('anu-status-campanha'); if(!el) return;
    var modoNova=document.getElementById('anu-camp-nova-btn')&&
                 document.getElementById('anu-camp-nova-btn').classList.contains('active');
    var ok=false;
    if(modoNova){ok=!!_val('anu-camp-nome').trim()&&!!_val('anu-camp-orcamento');}
    else{var s=document.getElementById('anu-camp-select');ok=s&&s.value&&!s.value.startsWith('Carregando')&&!s.value.startsWith('Nenhuma');}
    el.textContent=ok?'✓ Configurada':'Pendente';
    el.className='anu-bloco-status'+(ok?' ok':'');
  }
```

- [ ] **Step 2: Substituir stub bindCreativoEvents**

```javascript
  function bindCreativoEvents() {
    var dz=document.getElementById('anu-dropzone');
    var fi=document.getElementById('anu-file-input');
    if(!dz||!fi) return;
    dz.addEventListener('dragover',function(e){e.preventDefault();dz.classList.add('dragover');});
    dz.addEventListener('dragleave',function(){dz.classList.remove('dragover');});
    dz.addEventListener('drop',function(e){e.preventDefault();dz.classList.remove('dragover');var f=e.dataTransfer.files[0];if(f)processarArquivo(f);});
    fi.addEventListener('change',function(){if(this.files[0])processarArquivo(this.files[0]);});
  }

  function processarArquivo(file) {
    if(!_clienteAtivo){alert('Selecione um cliente primeiro.');return;}
    var preview=document.getElementById('anu-preview');
    var inner=document.getElementById('anu-dropzone-inner');
    if(preview){
      preview.innerHTML='';
      if(file.type.startsWith('video')){
        var vid=document.createElement('video');vid.src=URL.createObjectURL(file);vid.controls=true;preview.appendChild(vid);
      } else {
        var img=document.createElement('img');img.src=URL.createObjectURL(file);preview.appendChild(img);
      }
      preview.classList.remove('hidden');
      if(inner) inner.classList.add('hidden');
    }
    if(!file.type.startsWith('video')){
      var reader=new FileReader();
      reader.onload=function(e){var b64=e.target.result;_creativeB64=b64.split(',')[1];_creativeMime=file.type;};
      reader.readAsDataURL(file);
    } else {
      _creativeB64=null; _creativeMime='video/mp4';
    }
    subirCreativoMeta(file);
  }

  function subirCreativoMeta(file) {
    mostrar('anu-upload-progress');
    var fill=document.getElementById('anu-progress-fill');
    var msg=document.getElementById('anu-progress-msg');
    var stEl=document.getElementById('anu-status-criativo');
    if(fill) fill.style.width='30%';
    if(msg)  msg.textContent=file.type.startsWith('video')?'Enviando vídeo (~60s)...':'Enviando imagem...';
    if(stEl){stEl.textContent='Enviando...';stEl.className='anu-bloco-status';}

    var fd=new FormData();
    fd.append('arquivo',file);
    fd.append('account_id',_clienteAtivo.account_id);
    fd.append('token_key',_clienteAtivo.token_key);

    fetch('/api/anuncios/upload-criativo',{method:'POST',body:fd})
      .then(function(r){return r.json();})
      .then(function(data){
        esconder('anu-upload-progress');
        if(data.error){if(stEl){stEl.textContent='Erro';stEl.className='anu-bloco-status erro';}alert('Erro no upload: '+data.error);return;}
        _creativeRef=data;
        if(stEl){stEl.textContent='✓ Enviado';stEl.className='anu-bloco-status ok';}
        atualizarRevisao();
        gerarCopyIA();
      })
      .catch(function(e){esconder('anu-upload-progress');if(stEl){stEl.textContent='Erro';stEl.className='anu-bloco-status erro';}alert('Erro: '+e);});
  }
```

- [ ] **Step 3: Testar campanha + upload**

Acessar #anuncios, selecionar cliente, fazer upload de JPG. Verificar:
- Status do bloco criativo vira "✓ Enviado" após upload

- [ ] **Step 4: Commit**

```bash
git add jake_desktop/static/js/anuncios.js
git commit -m "feat: anuncios.js — blocos campanha e criativo"
```

---

## Task 9: JavaScript — copy IA e revisão

**Files:**
- Modify: `jake_desktop/static/js/anuncios.js`

- [ ] **Step 1: Substituir stubs bindCopyEvents e bindRevisaoEvents**

```javascript
  function bindCopyEvents() {
    var r=document.getElementById('anu-copy-regerar'); if(r) r.addEventListener('click',gerarCopyIA);
    ['anu-copy-titulo','anu-copy-texto','anu-copy-cta'].forEach(function(id){
      var el=document.getElementById(id);
      if(el) el.addEventListener('input',function(){atualizarContadores();atualizarStatusCopy();atualizarRevisao();});
    });
  }

  function gerarCopyIA() {
    if(!_clienteAtivo) return;
    mostrar('anu-copy-loading');
    var stEl=document.getElementById('anu-status-copy');
    if(stEl){stEl.textContent='Gerando...';stEl.className='anu-bloco-status';}

    var payload={
      imagem_base64:_creativeB64||'', mime_type:_creativeMime||'image/jpeg',
      cliente_nome:_clienteAtivo.nome, campanha_tipo:_clienteAtivo.campanha_tipo||'MESSAGES',
      segmento:_clienteAtivo.segmento||''
    };

    fetch('/api/anuncios/copy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){return r.json();})
      .then(function(data){
        esconder('anu-copy-loading');
        if(data.error){if(stEl){stEl.textContent='Erro';stEl.className='anu-bloco-status erro';}alert('Erro: '+data.error);return;}
        _set('anu-copy-titulo',data.titulo||'');
        _set('anu-copy-texto',data.texto||'');
        _set('anu-copy-cta',data.cta||'SEND_MESSAGE');
        atualizarContadores(); atualizarStatusCopy();
        if(stEl){stEl.textContent='✓ Gerada';stEl.className='anu-bloco-status ok';}
        atualizarRevisao();
      })
      .catch(function(e){esconder('anu-copy-loading');alert('Erro: '+e);});
  }

  function atualizarContadores() {
    var t=_val('anu-copy-titulo'),x=_val('anu-copy-texto');
    _setText('anu-titulo-count',t.length+'/40');
    _setText('anu-texto-count',x.length+'/125');
  }

  function atualizarStatusCopy() {
    var el=document.getElementById('anu-status-copy'); if(!el) return;
    var ok=!!_val('anu-copy-titulo').trim()&&!!_val('anu-copy-texto').trim();
    el.textContent=ok?'✓ Pronta':'Pendente';
    el.className='anu-bloco-status'+(ok?' ok':'');
  }

  function bindRevisaoEvents() {
    var bp=document.getElementById('anu-btn-publicar'); if(bp) bp.addEventListener('click',abrirModal);
  }

  function atualizarRevisao() {
    if(!_clienteAtivo) return;
    var grid=document.getElementById('anu-revisao-grid'); if(!grid) return;
    var loc=_clienteAtivo.localizacao_json||{};
    var temLoc=!!(loc.paises&&loc.paises.length||loc.cidades&&loc.cidades.length);
    var temPageId=!!(_clienteAtivo.page_id||'').trim();
    var locStr=temLoc?(loc.cidades&&loc.cidades.length?loc.cidades.length+' cidade(s)':(loc.paises||[]).join(', ')):'NÃO CONFIGURADA';
    var pub=_clienteAtivo.publico_json||{};
    var pubStr=pub.idade_min?(pub.idade_min+'–'+pub.idade_max+' anos'):'Padrão';
    var modoNova=document.getElementById('anu-camp-nova-btn')&&document.getElementById('anu-camp-nova-btn').classList.contains('active');
    var campNome=modoNova?(_val('anu-camp-nome')||'—'):(_val('anu-camp-select')||'—');

    var itens=[
      {label:'Conta Meta',    val:_clienteAtivo.account_id, ok:!!_clienteAtivo.account_id},
      {label:'Page ID',       val:_clienteAtivo.page_id||'—', ok:temPageId},
      {label:'Localização',   val:locStr, ok:temLoc},
      {label:'Público',       val:pubStr, ok:true},
      {label:'Orçamento',     val:_val('anu-camp-orcamento')?'R$ '+_val('anu-camp-orcamento')+'/dia':'—', ok:!!_val('anu-camp-orcamento')},
      {label:'Campanha',      val:campNome, ok:campNome!=='—'},
      {label:'Criativo',      val:_creativeRef?'✓ Enviado':'—', ok:!!_creativeRef},
      {label:'Título',        val:_val('anu-copy-titulo')||'—', ok:!!_val('anu-copy-titulo').trim()},
    ];

    grid.innerHTML=itens.map(function(item){
      var cls=item.ok?'anu-revisao-ok':'anu-revisao-erro';
      return '<div class="anu-revisao-item"><span class="anu-revisao-label">'+_esc(item.label)+'</span><span class="anu-revisao-val '+cls+'">'+_esc(String(item.val))+'</span></div>';
    }).join('');

    var alertaEl=document.getElementById('anu-localizacao-alerta');
    if(alertaEl) alertaEl.classList.toggle('hidden',temLoc&&temPageId);

    var tudo_ok=itens.every(function(i){return i.ok;});
    var bp=document.getElementById('anu-btn-publicar');
    if(bp) bp.disabled=!tudo_ok;
  }
```

- [ ] **Step 2: Testar revisão**

Selecionar cliente COM localização E page_id configurados, fazer upload + aguardar copy. Verificar:
- Todos os cards do bloco 4 mostram ✓
- Botão "Publicar" habilita
- Para cliente SEM localização: alerta aparece, botão desabilitado

- [ ] **Step 3: Commit**

```bash
git add jake_desktop/static/js/anuncios.js
git commit -m "feat: anuncios.js — copy IA, revisão e validação de localização/page_id"
```

---

## Task 10: JavaScript — modal e publicação

**Files:**
- Modify: `jake_desktop/static/js/anuncios.js`

- [ ] **Step 1: Substituir stubs bindModalEvents**

```javascript
  function bindModalEvents() {
    var bc=document.getElementById('anu-modal-cancelar');   if(bc) bc.addEventListener('click',fecharModal);
    var bf=document.getElementById('anu-modal-confirmar');  if(bf) bf.addEventListener('click',publicarAnuncio);
    var ov=document.getElementById('anu-modal-overlay');
    if(ov) ov.addEventListener('click',function(e){if(e.target===ov)fecharModal();});
  }

  function abrirModal() {
    if(!_clienteAtivo) return;
    var resumo=document.getElementById('anu-modal-resumo');
    var modoNova=document.getElementById('anu-camp-nova-btn')&&document.getElementById('anu-camp-nova-btn').classList.contains('active');
    if(resumo) resumo.innerHTML=[
      '<strong>Cliente:</strong> '+_esc(_clienteAtivo.nome),
      '<strong>Conta:</strong> '+_esc(_clienteAtivo.account_id),
      '<strong>Page ID:</strong> '+_esc(_clienteAtivo.page_id||'—'),
      '<strong>Campanha:</strong> '+_esc(modoNova?(_val('anu-camp-nome')||'—'):'Existente: '+_val('anu-camp-select')),
      '<strong>Orçamento:</strong> R$ '+(_val('anu-camp-orcamento')||'—')+'/dia',
      '<strong>Título:</strong> '+_esc(_val('anu-copy-titulo')),
      '<strong>CTA:</strong> '+_esc(_val('anu-copy-cta')),
      '<strong>Criativo:</strong> '+(_creativeRef?(_creativeRef.tipo==='video'?'Vídeo':'Imagem')+' ✓':'—'),
    ].join('<br>');
    mostrar('anu-modal-overlay');
  }

  function fecharModal() {
    esconder('anu-modal-overlay');
    var bc=document.getElementById('anu-modal-confirmar');
    if(bc){bc.textContent='Confirmar e Criar';bc.classList.remove('loading');}
  }

  function publicarAnuncio() {
    if(!_clienteAtivo||!_creativeRef) return;
    var bc=document.getElementById('anu-modal-confirmar');
    if(bc){bc.textContent='Publicando...';bc.classList.add('loading');}

    var modoNova=document.getElementById('anu-camp-nova-btn')&&document.getElementById('anu-camp-nova-btn').classList.contains('active');
    var payload={
      cliente_id:_clienteAtivo.id,
      campanha_existente_id:modoNova?null:(_val('anu-camp-select')||null),
      campanha_nome:_val('anu-camp-nome')||('Campanha '+_clienteAtivo.nome),
      orcamento_diario:parseFloat(_val('anu-camp-orcamento'))||30,
      creative_ref:_creativeRef,
      copy:{titulo:_val('anu-copy-titulo'),texto:_val('anu-copy-texto'),cta:_val('anu-copy-cta')||'SEND_MESSAGE'}
    };

    fetch('/api/anuncios/publicar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){return r.json();})
      .then(function(data){
        fecharModal();
        if(data.error){alert('✕ Erro: '+data.error);return;}
        alert('✓ Anúncio criado!\n\nCampaign ID: '+data.campaign_id+'\nAd Set ID: '+data.adset_id+'\nAd ID: '+data.ad_id+'\n\n'+data.msg);
        _creativeRef=null; _creativeB64=null;
        mostrarCriacao();
      })
      .catch(function(e){fecharModal();alert('Erro de rede: '+e);});
  }
```

- [ ] **Step 2: Teste completo do fluxo**

1. Acessar http://localhost:5050/#anuncios
2. Criar cliente com page_id e localização configurados
3. Selecionar o cliente
4. Configurar campanha nova (nome + orçamento)
5. Fazer upload de imagem JPG
6. Aguardar copy gerada automaticamente
7. Verificar que bloco 4 mostra todos os ✓
8. Clicar "Publicar Anúncio" → modal abre com resumo
9. Confirmar → anúncio criado na Meta (status PAUSADO)
10. Verificar no Gerenciador da Meta que campanha/conjunto/anúncio foram criados

- [ ] **Step 3: Commit**

```bash
git add jake_desktop/static/js/anuncios.js
git commit -m "feat: anuncios.js — modal de confirmação e publicação"
```

---

## Task 11: Wiring final e smoke test

**Files:**
- Verify: `jake_desktop/templates/dashboard.html`
- Verify: `jake_desktop/static/js/anuncios.js`
- Verify: `jake_desktop/static/css/anuncios.css`

- [ ] **Step 1: Verificar todos os artefatos**

```bash
grep -c "anuncios" /root/jake_desktop/templates/dashboard.html
# Expected: > 5 ocorrências

grep -n "anuncios.css\|anuncios.js" /root/jake_desktop/templates/dashboard.html
# Expected: linha com CSS no head e linha com JS antes do </body>

wc -l /root/jake_desktop/static/js/anuncios.js
# Expected: > 200 linhas
```

- [ ] **Step 2: Verificar banco**

```bash
PYTHONPATH=/root python3 -c "
from core.db import get_conn
conn=get_conn(); cur=conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM ad_client_profiles\")
print('Clientes:', cur.fetchone()[0])
cur.execute(\"SELECT COUNT(*) FROM ad_publish_log\")
print('Logs:', cur.fetchone()[0])
conn.close()
"
```

Expected: sem erros.

- [ ] **Step 3: Verificar servidor**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/api/anuncios/clientes
```

Expected: `302`

- [ ] **Step 4: Commit final**

```bash
git add jake_desktop/static/js/anuncios.js jake_desktop/static/css/anuncios.css jake_desktop/templates/dashboard.html jake_desktop/app.py meta/meta_api.py
git commit -m "feat: aba Subir Anúncios — implementação completa v1"
```

---

## Checklist de critérios de sucesso

- [ ] Cadastrar perfil de cliente (com page_id e localização) leva menos de 3 minutos
- [ ] Da segunda vez, subir um anúncio completo leva menos de 2 minutos
- [ ] Publicar sem localização é impossível (botão desabilitado + validação backend)
- [ ] Publicar sem page_id é impossível (validação backend retorna 400)
- [ ] Copy gerada pela IA é aproveitável em pelo menos 60% dos casos
- [ ] Falhas parciais na Meta API não deixam campanhas órfãs (rollback ativo nos passos 2 e 3)
- [ ] Objective values corretos enviados à Meta API: `OUTCOME_MESSAGES` e `OUTCOME_ENGAGEMENT`
