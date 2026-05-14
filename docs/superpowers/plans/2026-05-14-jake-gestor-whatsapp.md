# Jake Gestor via WhatsApp — Fase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que Bruno suba anúncios e pause/ative campanhas enviando mensagens simples no WhatsApp.

**Architecture:** Jake WhatsApp (`jake_whatsapp.py`) interpreta mensagens com Claude, resolve clientes por fuzzy match, pede confirmação e chama Jake OS (`localhost:5050`) que executa toda lógica de Meta API. Dois novos endpoints são adicionados ao Jake OS: um para subir anúncio a partir de Drive e outro para pausar/ativar campanha. Um novo módulo `bot/gestor_whatsapp.py` encapsula as chamadas HTTP ao Jake OS.

**Tech Stack:** Python, Flask, requests, difflib (stdlib), Anthropic Claude, Jake OS (localhost:5050), Evolution API

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `jake_desktop/app.py` | Modificar | +2 endpoints: `/api/anuncios/wa/subir` e `PATCH /api/anuncios/campanha/<id>/status` |
| `bot/gestor_whatsapp.py` | Criar | Cliente HTTP do Jake OS: auth, subir_anuncio, pausar/ativar campanha |
| `bot/jake_whatsapp.py` | Modificar | +interpretar_comando, +resolver_clientes, +_sessoes, roteamento no processar_mensagem |
| `tests/test_gestor_whatsapp.py` | Criar | Testes unitários para gestor_whatsapp e resolver_clientes |

---

## Task 1: Endpoint Jake OS — `/api/anuncios/wa/subir`

**Objetivo:** Aceitar `{drive_url, cliente_ids, orcamento, campanha_nome, campanha_tipo}`, baixar o arquivo do Drive, salvar em tmp e retornar `mc_token` pronto para stream.

**Files:**
- Modify: `jake_desktop/app.py` — inserir após linha ~3380 (após `anuncios_lote_drive_download`)

- [ ] **Step 1: Localizar ponto de inserção**

```bash
grep -n "anuncios_lote_drive_download\|anuncios_upload_criativo" /root/jake_desktop/app.py
```

Expected: linha ~3300 para drive_download, ~3382 para upload_criativo. Inserir o novo endpoint entre elas.

- [ ] **Step 2: Adicionar endpoint `/api/anuncios/wa/subir`**

Inserir após a linha de fechamento de `anuncios_lote_drive_download` (após o `return jsonify(...)` dela, antes de `@app.route("/api/anuncios/upload-criativo"`):

```python
@app.route("/api/anuncios/wa/subir", methods=["POST"])
@login_required
def anuncios_wa_subir():
    """Endpoint para Jake WhatsApp: baixa Drive, salva tmp, prepara mc_token para stream."""
    import re as _re_wa
    from urllib.parse import urlparse as _urlparse_wa, parse_qs as _parse_qs_wa
    d             = request.get_json() or {}
    drive_url     = (d.get("drive_url") or "").strip()
    cliente_ids   = d.get("cliente_ids") or []
    orcamento_raw = d.get("orcamento")
    campanha_nome = (d.get("campanha_nome") or "").strip()
    campanha_tipo = (d.get("campanha_tipo") or "MESSAGES").strip().upper()

    if not drive_url:
        return jsonify({"error": "drive_url obrigatório"}), 400
    if not cliente_ids:
        return jsonify({"error": "cliente_ids obrigatório"}), 400
    if not campanha_nome:
        return jsonify({"error": "campanha_nome obrigatório"}), 400
    if campanha_tipo not in ("MESSAGES", "ENGAGEMENT", "PURCHASE"):
        return jsonify({"error": "campanha_tipo inválido"}), 400
    try:
        orcamento = float(orcamento_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "orcamento deve ser número"}), 400

    # Extrair file_id do Drive
    file_id = None
    m = _re_wa.search(r'/file/d/([a-zA-Z0-9_-]+)', drive_url)
    if m:
        file_id = m.group(1)
    elif "id=" in drive_url:
        file_id = _parse_qs_wa(_urlparse_wa(drive_url).query).get("id", [None])[0]
    if not file_id:
        return jsonify({"error": "URL do Drive inválida. Use drive.google.com/file/d/ID/view"}), 400

    # Baixar arquivo do Drive
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        resp = requests.get(download_url, stream=True, allow_redirects=True, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"error": f"Erro ao baixar do Drive: {e}"}), 400

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type:
        return jsonify({"error": "Arquivo não público. Compartilhe com 'qualquer pessoa com o link'"}), 400

    _MIME_EXT_WA = {"image/jpeg": ".jpg", "image/png": ".png", "video/mp4": ".mp4"}
    mime_base = content_type.split(";")[0].strip()
    ext = _MIME_EXT_WA.get(mime_base)
    if not ext:
        return jsonify({"error": f"Tipo não suportado: {mime_base}. Use JPG, PNG ou MP4"}), 400

    _MAX_WA = 100 * 1024 * 1024
    content = b""
    for chunk in resp.iter_content(chunk_size=65536):
        content += chunk
        if len(content) > _MAX_WA:
            return jsonify({"error": "Arquivo muito grande. Limite: 100 MB"}), 400

    # Salvar em tmp
    tmp_uuid_val = str(uuid.uuid4())
    tmp_path = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{ext}")
    with open(tmp_path, "wb") as fh:
        fh.write(content)
    def _del_tmp():
        try: os.remove(tmp_path)
        except Exception: pass
    threading.Timer(3600, _del_tmp).start()

    # Buscar clientes no banco
    conn = None
    try:
        conn = _get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, agencia, account_id, token_key, page_id, link_url, "
            "campanha_tipo, optimization_goal, pixel_id, localizacao_json, publico_json "
            "FROM ad_client_profiles WHERE id = ANY(%s)",
            (cliente_ids,)
        )
        clientes = [dict(c) for c in cur.fetchall()]
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar clientes: {e}"}), 500
    finally:
        try: conn.close()
        except Exception: pass

    if not clientes:
        return jsonify({"error": "Nenhum cliente encontrado"}), 404

    # Validar campos obrigatórios
    erros = []
    for c in clientes:
        if not c.get("page_id"):
            erros.append(f"{c['nome']}: page_id não configurado")
        if not c.get("account_id"):
            erros.append(f"{c['nome']}: account_id não configurado")
        if c.get("token_key") not in _VALID_TOKEN_KEYS:
            erros.append(f"{c['nome']}: token_key inválido")
    if erros:
        return jsonify({"error": "Clientes com configuração incompleta", "detalhes": erros}), 400

    # Armazenar payload para stream
    mc_token = str(uuid.uuid4())
    _lote_payloads[mc_token] = {
        "clientes":      clientes,
        "tmp_uuid":      tmp_uuid_val,
        "tmp_ext":       ext,
        "copy":          {},
        "campanha_nome": campanha_nome,
        "orcamento":     orcamento,
    }
    threading.Timer(1800, lambda: _lote_payloads.pop(mc_token, None)).start()

    return jsonify({"mc_token": mc_token, "clientes": len(clientes), "tipo": mime_base})
```

- [ ] **Step 3: Reiniciar Jake OS e testar endpoint manualmente**

```bash
systemctl restart jake-os 2>/dev/null || pkill -f "python.*app.py" && sleep 2 && cd /root/jake_desktop && /root/venv/bin/python app.py &
```

Teste rápido (substituir TOKEN pela sessão válida):
```bash
curl -s -X POST http://localhost:5050/api/anuncios/wa/subir \
  -H "Content-Type: application/json" \
  -b "session=..." \
  -d '{"drive_url":"","cliente_ids":[],"orcamento":30,"campanha_nome":"teste","campanha_tipo":"MESSAGES"}' \
  | python3 -m json.tool
```
Expected: `{"error": "drive_url obrigatório"}`

- [ ] **Step 4: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(jake-os): endpoint /api/anuncios/wa/subir para Jake WhatsApp"
```

---

## Task 2: Endpoint Jake OS — `PATCH /api/anuncios/campanha/<id>/status`

**Objetivo:** Pausar ou ativar uma campanha Meta a partir do Jake WhatsApp.

**Files:**
- Modify: `jake_desktop/app.py` — inserir após o endpoint de listar campanhas (~linha 3298)

- [ ] **Step 1: Adicionar endpoint de pause/ativar**

Inserir logo após `anuncios_listar_campanhas`:

```python
@app.route("/api/anuncios/campanha/<campaign_id>/status", methods=["PATCH"])
@login_required
def anuncios_campanha_status(campaign_id):
    """Pausa ou ativa uma campanha Meta. Body: {status: 'PAUSED'|'ACTIVE', token_key: '...'}"""
    d         = request.get_json() or {}
    status    = (d.get("status") or "").strip().upper()
    token_key = (d.get("token_key") or "META_ACCESS_TOKEN").strip()

    if status not in ("PAUSED", "ACTIVE"):
        return jsonify({"error": "status deve ser PAUSED ou ACTIVE"}), 400
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    try:
        resp = requests.post(
            f"https://graph.facebook.com/v21.0/{campaign_id}",
            data={"status": status, "access_token": token},
            timeout=15,
        )
        data = resp.json()
        if data.get("success"):
            return jsonify({"ok": True, "campaign_id": campaign_id, "status": status})
        return jsonify({"error": data.get("error", {}).get("message", "Erro desconhecido")}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 2: Reiniciar Jake OS**

```bash
pkill -f "python.*app.py"; sleep 2; cd /root/jake_desktop && nohup /root/venv/bin/python app.py >> /tmp/jakeos.log 2>&1 &
```

- [ ] **Step 3: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(jake-os): endpoint PATCH /api/anuncios/campanha/<id>/status"
```

---

## Task 3: Criar `bot/gestor_whatsapp.py`

**Objetivo:** Módulo que autentica no Jake OS e expõe funções de alto nível para o bot WhatsApp.

**Files:**
- Create: `bot/gestor_whatsapp.py`
- Create: `tests/test_gestor_whatsapp.py`

- [ ] **Step 1: Escrever teste primeiro**

Criar `tests/test_gestor_whatsapp.py`:

```python
"""Testes para bot/gestor_whatsapp.py"""
import pytest
from unittest.mock import patch, MagicMock


def _make_gestor():
    """Instancia GestorJakeOS com Jake OS URL mockado."""
    from bot.gestor_whatsapp import GestorJakeOS
    return GestorJakeOS(base_url="http://localhost:5050", email="admin@jakeos.local", senha="Jake@2024!")


def test_login_sucesso():
    gestor = _make_gestor()
    mock_resp = MagicMock()
    mock_resp.url = "http://localhost:5050/"
    mock_resp.status_code = 200

    with patch.object(gestor._session, "post", return_value=mock_resp):
        result = gestor.login()
    assert result is True


def test_login_falha():
    gestor = _make_gestor()
    mock_resp = MagicMock()
    mock_resp.url = "http://localhost:5050/login?error=1"

    with patch.object(gestor._session, "post", return_value=mock_resp):
        result = gestor.login()
    assert result is False


def test_subir_anuncio_retorna_mc_token():
    gestor = _make_gestor()
    gestor._autenticado = True

    mock_preparar = MagicMock()
    mock_preparar.json.return_value = {"mc_token": "abc-123", "clientes": 2}
    mock_preparar.status_code = 200

    with patch.object(gestor._session, "post", return_value=mock_preparar):
        result = gestor.subir_anuncio(
            cliente_ids=[1, 2],
            drive_url="https://drive.google.com/file/d/XYZ/view",
            orcamento=30.0,
            campanha_nome="Teste WA",
            campanha_tipo="MESSAGES",
        )
    assert result["mc_token"] == "abc-123"


def test_listar_campanhas():
    gestor = _make_gestor()
    gestor._autenticado = True

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"campanhas": [{"id": "123", "name": "Camp A", "status": "ACTIVE"}]}
    mock_resp.status_code = 200

    with patch.object(gestor._session, "get", return_value=mock_resp):
        result = gestor.listar_campanhas(account_id="act_123", token_key="META_TOKEN_PILOTI")
    assert len(result) == 1
    assert result[0]["id"] == "123"


def test_pausar_campanha():
    gestor = _make_gestor()
    gestor._autenticado = True

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_resp.status_code = 200

    with patch.object(gestor._session, "patch", return_value=mock_resp):
        result = gestor.pausar_campanha(campaign_id="123", token_key="META_TOKEN_PILOTI")
    assert result is True


def test_ativar_campanha():
    gestor = _make_gestor()
    gestor._autenticado = True

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_resp.status_code = 200

    with patch.object(gestor._session, "patch", return_value=mock_resp):
        result = gestor.ativar_campanha(campaign_id="123", token_key="META_TOKEN_PILOTI")
    assert result is True
```

- [ ] **Step 2: Rodar testes — confirmar que falham**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_gestor_whatsapp.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError: No module named 'bot.gestor_whatsapp'`

- [ ] **Step 3: Criar `bot/gestor_whatsapp.py`**

```python
"""
gestor_whatsapp.py — Cliente HTTP do Jake OS para Jake WhatsApp.

Encapsula autenticação e chamadas aos endpoints de anúncios.
Nunca chama a Meta API diretamente — todo trabalho pesado fica no Jake OS.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

JAKE_OS_URL   = os.environ.get("JAKE_OS_URL", "http://localhost:5050")
JAKE_OS_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@jakeos.local")
JAKE_OS_SENHA = os.environ.get("ADMIN_PASSWORD", "Jake@2024!")


class GestorJakeOS:
    def __init__(self, base_url: str = JAKE_OS_URL, email: str = JAKE_OS_EMAIL, senha: str = JAKE_OS_SENHA):
        self._base    = base_url.rstrip("/")
        self._email   = email
        self._senha   = senha
        self._session = requests.Session()
        self._autenticado = False

    def login(self) -> bool:
        """Faz login no Jake OS e mantém cookie de sessão. Retorna True se OK."""
        try:
            resp = self._session.post(
                f"{self._base}/auth/login",
                data={"email": self._email, "password": self._senha},
                allow_redirects=True,
                timeout=10,
            )
            # Sucesso: redirect para "/" — falha: redirect para "/login?error=1"
            if "login" in resp.url and "error" in resp.url:
                logger.error("Jake OS: login falhou — credenciais incorretas")
                self._autenticado = False
                return False
            self._autenticado = True
            logger.info("Jake OS: login OK")
            return True
        except Exception as e:
            logger.error(f"Jake OS: erro no login: {e}")
            self._autenticado = False
            return False

    def _garantir_auth(self):
        if not self._autenticado:
            self.login()

    def subir_anuncio(self, cliente_ids: list, drive_url: str, orcamento: float,
                      campanha_nome: str, campanha_tipo: str = "MESSAGES") -> dict:
        """
        Prepara lote via Jake OS. Retorna dict com mc_token para consumir o stream.
        Lança RuntimeError em caso de falha.
        """
        self._garantir_auth()
        resp = self._session.post(
            f"{self._base}/api/anuncios/wa/subir",
            json={
                "drive_url":     drive_url,
                "cliente_ids":   cliente_ids,
                "orcamento":     orcamento,
                "campanha_nome": campanha_nome,
                "campanha_tipo": campanha_tipo,
            },
            timeout=60,
        )
        if resp.status_code == 401:
            # Sessão expirou — re-login e tenta uma vez mais
            self._autenticado = False
            self._garantir_auth()
            resp = self._session.post(
                f"{self._base}/api/anuncios/wa/subir",
                json={
                    "drive_url":     drive_url,
                    "cliente_ids":   cliente_ids,
                    "orcamento":     orcamento,
                    "campanha_nome": campanha_nome,
                    "campanha_tipo": campanha_tipo,
                },
                timeout=60,
            )
        data = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(data.get("error", "Erro desconhecido no Jake OS"))
        return data  # {"mc_token": "...", "clientes": N, "tipo": "video/mp4"}

    def consumir_stream(self, mc_token: str) -> list[dict]:
        """
        Consome o SSE de /api/anuncios/multi-cliente/stream/<mc_token>.
        Retorna lista de eventos {tipo, cliente, status, ...}.
        """
        self._garantir_auth()
        eventos = []
        try:
            with self._session.get(
                f"{self._base}/api/anuncios/multi-cliente/stream/{mc_token}",
                stream=True,
                timeout=300,
            ) as resp:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode("utf-8")
                    if line.startswith("data:"):
                        import json
                        try:
                            ev = json.loads(line[5:].strip())
                            eventos.append(ev)
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Erro ao consumir stream: {e}")
        return eventos

    def listar_campanhas(self, account_id: str, token_key: str) -> list:
        """Retorna lista de campanhas ativas/pausadas de uma conta."""
        self._garantir_auth()
        resp = self._session.get(
            f"{self._base}/api/anuncios/campanhas/{account_id}",
            params={"token_key": token_key},
            timeout=15,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(data.get("error", "Erro ao listar campanhas"))
        return data.get("campanhas", [])

    def pausar_campanha(self, campaign_id: str, token_key: str) -> bool:
        """Pausa uma campanha. Retorna True se OK."""
        return self._set_status(campaign_id, "PAUSED", token_key)

    def ativar_campanha(self, campaign_id: str, token_key: str) -> bool:
        """Ativa uma campanha. Retorna True se OK."""
        return self._set_status(campaign_id, "ACTIVE", token_key)

    def _set_status(self, campaign_id: str, status: str, token_key: str) -> bool:
        self._garantir_auth()
        resp = self._session.patch(
            f"{self._base}/api/anuncios/campanha/{campaign_id}/status",
            json={"status": status, "token_key": token_key},
            timeout=15,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(data.get("error", "Erro ao atualizar status"))
        return data.get("ok", False)


# Instância singleton — reutilizar sessão entre chamadas
_gestor = None

def get_gestor() -> GestorJakeOS:
    global _gestor
    if _gestor is None:
        _gestor = GestorJakeOS()
        _gestor.login()
    return _gestor
```

- [ ] **Step 4: Rodar testes — confirmar que passam**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_gestor_whatsapp.py -v
```
Expected: 6 testes passando

- [ ] **Step 5: Commit**

```bash
git add bot/gestor_whatsapp.py tests/test_gestor_whatsapp.py
git commit -m "feat(whatsapp): GestorJakeOS — cliente HTTP do Jake OS"
```

---

## Task 4: Adicionar `interpretar_comando` e `resolver_clientes` em `jake_whatsapp.py`

**Files:**
- Modify: `bot/jake_whatsapp.py`
- Create/Modify: `tests/test_jake_whatsapp_gestor.py`

- [ ] **Step 1: Escrever testes**

Criar `tests/test_jake_whatsapp_gestor.py`:

```python
"""Testes para interpretar_comando e resolver_clientes em jake_whatsapp.py"""
import pytest
from unittest.mock import patch, MagicMock


# ── interpretar_comando ────────────────────────────────────────────────────────

def test_interpretar_subir_anuncio():
    from bot.jake_whatsapp import interpretar_comando
    mock_claude = MagicMock()
    mock_claude.return_value = '{"intencao":"subir_anuncio","drive_link":"https://drive.google.com/file/d/ABC/view","clientes":["cordeirópolis"],"orcamento":30,"campanha_tipo":"MESSAGES"}'

    with patch("bot.jake_whatsapp.chamar_claude", mock_claude):
        result = interpretar_comando("Sobe esse vídeo https://drive.google.com/file/d/ABC/view para cordeirópolis, R$30")

    assert result["intencao"] == "subir_anuncio"
    assert result["orcamento"] == 30
    assert "cordeirópolis" in result["clientes"]


def test_interpretar_pausar_campanha():
    from bot.jake_whatsapp import interpretar_comando
    mock_claude = MagicMock()
    mock_claude.return_value = '{"intencao":"pausar_campanha","clientes":["schroeder"],"orcamento":null,"campanha_tipo":null,"drive_link":null}'

    with patch("bot.jake_whatsapp.chamar_claude", mock_claude):
        result = interpretar_comando("Pausa as campanhas do Schroeder")

    assert result["intencao"] == "pausar_campanha"
    assert "schroeder" in result["clientes"]


def test_interpretar_json_invalido_retorna_desconhecida():
    from bot.jake_whatsapp import interpretar_comando
    mock_claude = MagicMock()
    mock_claude.return_value = "Não entendi o comando."

    with patch("bot.jake_whatsapp.chamar_claude", mock_claude):
        result = interpretar_comando("blablabla")

    assert result["intencao"] == "desconhecida"


# ── resolver_clientes ──────────────────────────────────────────────────────────

def test_resolver_match_exato():
    from bot.jake_whatsapp import resolver_clientes
    clientes_db = [
        {"id": 1, "nome": "Odontocompany Cordeiropolis"},
        {"id": 2, "nome": "ODC Tijucas"},
    ]
    with patch("bot.jake_whatsapp._buscar_clientes_db", return_value=clientes_db):
        resultado = resolver_clientes(["cordeiropolis"])
    assert len(resultado["confirmados"]) == 1
    assert resultado["confirmados"][0]["id"] == 1
    assert resultado["ambiguos"] == []


def test_resolver_sem_match():
    from bot.jake_whatsapp import resolver_clientes
    clientes_db = [{"id": 1, "nome": "Odontocompany Cordeiropolis"}]
    with patch("bot.jake_whatsapp._buscar_clientes_db", return_value=clientes_db):
        resultado = resolver_clientes(["xyz123"])
    assert resultado["confirmados"] == []
    assert len(resultado["nao_encontrados"]) == 1


def test_resolver_multiplos():
    from bot.jake_whatsapp import resolver_clientes
    clientes_db = [
        {"id": 1, "nome": "Odontocompany Cordeiropolis"},
        {"id": 2, "nome": "ODC Tijucas"},
        {"id": 3, "nome": "ODC Schroeder"},
    ]
    with patch("bot.jake_whatsapp._buscar_clientes_db", return_value=clientes_db):
        resultado = resolver_clientes(["cordeiropolis", "tijucas"])
    assert len(resultado["confirmados"]) == 2
```

- [ ] **Step 2: Rodar testes — confirmar que falham**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_jake_whatsapp_gestor.py -v 2>&1 | head -20
```
Expected: `ImportError` — funções ainda não existem.

- [ ] **Step 3: Adicionar `PROMPT_GESTOR` e `interpretar_comando` em `jake_whatsapp.py`**

Inserir após a linha de `PROMPT_ANALISTA` (após linha ~75):

```python
PROMPT_GESTOR = """Você é um parser de comandos de gestão de tráfego. Analise a mensagem e retorne SOMENTE um JSON válido (sem markdown, sem texto extra) com esta estrutura:

{
  "intencao": "subir_anuncio" | "pausar_campanha" | "ativar_campanha" | "desconhecida",
  "drive_link": "URL completa do Google Drive ou null",
  "clientes": ["lista", "de", "nomes", "mencionados"],
  "orcamento": numero_float_ou_null,
  "campanha_tipo": "MESSAGES" | "ENGAGEMENT" | "PURCHASE" | null
}

Regras:
- Se mencionar "sobe", "subir", "upload", "anuncio" com link do Drive → subir_anuncio
- Se mencionar "pausa", "pausar", "desativa" → pausar_campanha
- Se mencionar "ativa", "ativar", "liga", "retoma" → ativar_campanha
- campanha_tipo padrão: MESSAGES se não informado e intencao = subir_anuncio
- Extraia o valor em R$ como orcamento float (ex: "R$30" → 30.0)
- clientes: lista exatamente como o usuário escreveu, em minúsculas"""


def interpretar_comando(texto: str) -> dict:
    """Interpreta mensagem do Bruno e retorna dict de intenção. Nunca lança exceção."""
    import json as _json
    try:
        raw = chamar_claude(PROMPT_GESTOR, texto)
        # Limpar possível markdown
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return _json.loads(raw.strip())
    except Exception:
        return {"intencao": "desconhecida", "drive_link": None, "clientes": [], "orcamento": None, "campanha_tipo": None}
```

- [ ] **Step 4: Adicionar `_buscar_clientes_db` e `resolver_clientes`**

Inserir após `interpretar_comando`:

```python
def _buscar_clientes_db() -> list:
    """Busca todos os clientes ativos do banco. Retorna lista de dicts."""
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_root, ".env"))
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, nome, agencia, account_id, token_key FROM ad_client_profiles ORDER BY nome")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Erro ao buscar clientes: {e}")
        return []


def resolver_clientes(nomes: list[str]) -> dict:
    """
    Faz fuzzy match dos nomes digitados contra o banco.
    Retorna:
      {
        "confirmados": [{"id": ..., "nome": ..., ...}],
        "ambiguos": [{"digitado": "...", "candidato": {...}, "score": 0.85}],
        "nao_encontrados": ["nome1", ...]
      }
    """
    from difflib import SequenceMatcher
    clientes_db = _buscar_clientes_db()
    confirmados, ambiguos, nao_encontrados = [], [], []

    for nome_digitado in nomes:
        nd = nome_digitado.lower().strip()
        melhor_score = 0.0
        melhor_cliente = None

        for c in clientes_db:
            score = SequenceMatcher(None, nd, c["nome"].lower()).ratio()
            # Bonus se o nome digitado está contido no nome do cliente
            if nd in c["nome"].lower():
                score = max(score, 0.85)
            if score > melhor_score:
                melhor_score = score
                melhor_cliente = c

        if melhor_score >= 0.80 and melhor_cliente:
            confirmados.append(melhor_cliente)
        elif melhor_score >= 0.50 and melhor_cliente:
            ambiguos.append({"digitado": nome_digitado, "candidato": melhor_cliente, "score": melhor_score})
        else:
            nao_encontrados.append(nome_digitado)

    return {"confirmados": confirmados, "ambiguos": ambiguos, "nao_encontrados": nao_encontrados}
```

- [ ] **Step 5: Rodar testes — confirmar que passam**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_jake_whatsapp_gestor.py -v
```
Expected: todos passando.

- [ ] **Step 6: Commit**

```bash
git add bot/jake_whatsapp.py tests/test_jake_whatsapp_gestor.py
git commit -m "feat(whatsapp): interpretar_comando + resolver_clientes com fuzzy match"
```

---

## Task 5: Gerenciamento de Estado e Roteamento em `jake_whatsapp.py`

**Files:**
- Modify: `bot/jake_whatsapp.py`

- [ ] **Step 1: Adicionar `_sessoes` e funções de estado**

Inserir após as definições de `_KEYWORDS_GRUPO` (após linha ~112):

```python
import time as _time

# ── Sessões de conversa (estado por JID) ──────────────────────────────────────
_sessoes: dict = {}
_TTL_SESSAO = 600  # 10 minutos


def _get_sessao(jid: str) -> dict | None:
    s = _sessoes.get(jid)
    if s and _time.time() > s["expira_em"]:
        _sessoes.pop(jid, None)
        return None
    return s


def _set_sessao(jid: str, estado: str, payload: dict):
    _sessoes[jid] = {
        "estado":    estado,
        "payload":   payload,
        "expira_em": _time.time() + _TTL_SESSAO,
    }


def _limpar_sessao(jid: str):
    _sessoes.pop(jid, None)
```

- [ ] **Step 2: Adicionar `_eh_gestor_cmd` e funções de resposta formatada**

Inserir após `_eh_grupo`:

```python
_KEYWORDS_GESTOR = [
    "sobe", "subir", "upload", "anuncio", "anúncio",
    "pausa", "pausar", "ativa", "ativar", "drive.google",
    "campanha", "campanhas",
]

def _eh_gestor_cmd(texto: str) -> bool:
    t = texto.lower()
    return any(k in t for k in _KEYWORDS_GESTOR)


def _formatar_resumo_subida(clientes: list, orcamento: float, campanha_tipo: str, campanha_nome: str) -> str:
    linhas = [f"Vou subir *{campanha_nome}* para:"]
    for c in clientes:
        linhas.append(f"  • {c['nome']} ({c['account_id']})")
    linhas.append(f"Orçamento: R${orcamento:.0f}/dia cada | Tipo: {campanha_tipo}")
    linhas.append("Confirma? (sim/não)")
    return "\n".join(linhas)


def _formatar_resultado_stream(eventos: list, total_clientes: int) -> str:
    ok = [e for e in eventos if e.get("tipo") == "concluido" or e.get("status") == "ok"]
    erros = [e for e in eventos if e.get("tipo") == "erro" or e.get("status") == "erro"]
    linhas = [f"Anúncio subido! {len(ok)}/{total_clientes} concluídos"]
    for e in ok:
        camp = e.get("campanha_id", "")
        nome = e.get("cliente", "")
        linhas.append(f"  ✅ {nome}" + (f" (camp. {camp})" if camp else ""))
    for e in erros:
        nome = e.get("cliente", "")
        msg = e.get("erro", e.get("message", "erro"))
        linhas.append(f"  ❌ {nome}: {msg}")
    return "\n".join(linhas)
```

- [ ] **Step 3: Substituir `processar_mensagem` adicionando roteamento de gestor**

Localizar `def processar_mensagem` no arquivo. Adicionar o bloco de roteamento gestor ANTES do bloco `_eh_grupo`, logo após `historico = carregar_historico(chat_id)`:

```python
    # Verificar sessão ativa (confirmação pendente)
    sessao = _get_sessao(sender_jid)
    if sessao:
        _processar_confirmacao(sender_jid, texto, sessao)
        return

    # Intenção: comando de gestor
    if _eh_gestor_cmd(texto):
        _processar_gestor_cmd(sender_jid, texto)
        return
```

- [ ] **Step 4: Criar `_processar_gestor_cmd` e `_processar_confirmacao`**

Inserir antes de `processar_mensagem`:

```python
def _processar_gestor_cmd(sender_jid: str, texto: str):
    """Interpreta comando de gestor, resolve clientes e pede confirmação."""
    from bot.gestor_whatsapp import get_gestor
    destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid

    cmd = interpretar_comando(texto)
    intencao = cmd.get("intencao", "desconhecida")

    if intencao == "desconhecida":
        send_text(destino, "Não entendi o comando, Patrão. Tenta algo como: 'Sobe [link drive] para [cliente], R$30'")
        return

    nomes = cmd.get("clientes") or []
    if not nomes:
        send_text(destino, "Não consegui identificar os clientes. Menciona o nome do cliente no comando.")
        return

    resolucao = resolver_clientes(nomes)

    # Tratar não encontrados
    if resolucao["nao_encontrados"]:
        nomes_str = ", ".join(resolucao["nao_encontrados"])
        send_text(destino, f"Não encontrei: {nomes_str}. Verifica o nome ou lista os clientes com 'lista clientes'.")
        return

    # Tratar ambíguos — pedir confirmação do primeiro ambíguo
    if resolucao["ambiguos"]:
        amb = resolucao["ambiguos"][0]
        _set_sessao(sender_jid, "aguardando_confirmacao_clientes", {
            "cmd": cmd,
            "confirmados": resolucao["confirmados"],
            "ambiguos": resolucao["ambiguos"],
            "ambiguo_atual": 0,
        })
        cand = amb["candidato"]
        send_text(destino, f"Encontrei *{cand['nome']}* para '{amb['digitado']}', é esse? (sim/não)")
        return

    # Todos resolvidos — montar resumo e pedir confirmação final
    clientes = resolucao["confirmados"]
    _montar_confirmacao_final(sender_jid, destino, cmd, clientes)


def _montar_confirmacao_final(sender_jid: str, destino: str, cmd: dict, clientes: list):
    intencao = cmd["intencao"]

    if intencao == "subir_anuncio":
        drive_link = cmd.get("drive_link") or ""
        if not drive_link:
            send_text(destino, "Não encontrei o link do Drive no comando. Inclui o link e tenta de novo.")
            return
        orcamento = cmd.get("orcamento")
        if not orcamento:
            # Tenta usar o orcamento_diario cadastrado do primeiro cliente
            orcamento = clientes[0].get("orcamento_diario") if clientes else None
        if not orcamento:
            send_text(destino, "Qual o orçamento diário por cliente? (ex: R$30)")
            _set_sessao(sender_jid, "aguardando_orcamento", {"cmd": cmd, "clientes": clientes})
            return
        campanha_tipo = cmd.get("campanha_tipo") or "MESSAGES"
        import datetime
        campanha_nome = cmd.get("campanha_nome") or f"WA {datetime.date.today().strftime('%d/%m')}"
        resumo = _formatar_resumo_subida(clientes, float(orcamento), campanha_tipo, campanha_nome)
        send_text(destino, resumo)
        _set_sessao(sender_jid, "aguardando_confirmacao_subida", {
            "cmd": cmd, "clientes": clientes,
            "orcamento": float(orcamento),
            "campanha_tipo": campanha_tipo,
            "campanha_nome": campanha_nome,
            "drive_link": drive_link,
        })

    elif intencao in ("pausar_campanha", "ativar_campanha"):
        from bot.gestor_whatsapp import get_gestor
        acao = "pausar" if intencao == "pausar_campanha" else "ativar"
        try:
            gestor = get_gestor()
            todas_campanhas = []
            for c in clientes:
                camps = gestor.listar_campanhas(c["account_id"], c["token_key"])
                status_filtro = "ACTIVE" if acao == "pausar" else "PAUSED"
                camps_filtradas = [cp for cp in camps if cp.get("status") == status_filtro or cp.get("effective_status") == status_filtro]
                for cp in camps_filtradas:
                    cp["_cliente"] = c
                todas_campanhas.extend(camps_filtradas)

            if not todas_campanhas:
                send_text(destino, f"Nenhuma campanha para {acao} encontrada nos clientes informados.")
                return

            nomes_camps = "\n".join(f"  • {cp['name']} ({cp['_cliente']['nome']})" for cp in todas_campanhas[:10])
            send_text(destino, f"Vou {acao} {len(todas_campanhas)} campanha(s):\n{nomes_camps}\nConfirma? (sim/não)")
            _set_sessao(sender_jid, f"aguardando_confirmacao_{acao}", {
                "campanhas": todas_campanhas,
                "clientes": clientes,
            })
        except Exception as e:
            send_text(destino, f"Erro ao buscar campanhas: {e}")


def _processar_confirmacao(sender_jid: str, texto: str, sessao: dict):
    """Processa resposta do Bruno em uma sessão de confirmação ativa."""
    from bot.gestor_whatsapp import get_gestor
    destino   = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid
    estado    = sessao["estado"]
    payload   = sessao["payload"]
    resposta  = texto.lower().strip()
    negativo  = any(r in resposta for r in ["não", "nao", "n", "cancela", "cancel"])
    positivo  = any(r in resposta for r in ["sim", "s", "yes", "ok", "confirma"])

    if negativo:
        _limpar_sessao(sender_jid)
        send_text(destino, "Cancelado, Patrão.")
        return

    if not positivo:
        send_text(destino, "Responde sim ou não, Patrão.")
        return

    # ── Confirmação de cliente ambíguo ────────────────────────────────────────
    if estado == "aguardando_confirmacao_clientes":
        idx       = payload["ambiguo_atual"]
        ambiguos  = payload["ambiguos"]
        amb       = ambiguos[idx]
        confirmados = payload["confirmados"] + [amb["candidato"]]
        idx += 1

        if idx < len(ambiguos):
            payload["confirmados"] = confirmados
            payload["ambiguo_atual"] = idx
            _set_sessao(sender_jid, "aguardando_confirmacao_clientes", payload)
            prox = ambiguos[idx]
            send_text(destino, f"E *{prox['candidato']['nome']}* para '{prox['digitado']}', é esse? (sim/não)")
        else:
            _limpar_sessao(sender_jid)
            _montar_confirmacao_final(sender_jid, destino, payload["cmd"], confirmados)
        return

    # ── Aguardando orçamento ──────────────────────────────────────────────────
    if estado == "aguardando_orcamento":
        import re as _re_orc
        m = _re_orc.search(r'[\d,.]+', texto)
        if not m:
            send_text(destino, "Não entendi o valor. Manda só o número, ex: 30")
            return
        orcamento = float(m.group().replace(",", "."))
        payload["cmd"]["orcamento"] = orcamento
        _limpar_sessao(sender_jid)
        _montar_confirmacao_final(sender_jid, destino, payload["cmd"], payload["clientes"])
        return

    # ── Confirmação final de subida ───────────────────────────────────────────
    if estado == "aguardando_confirmacao_subida":
        _limpar_sessao(sender_jid)
        send_text(destino, "Subindo anúncios... aguarda, Patrão.")
        _set_sessao(sender_jid, "executando", {})
        import threading

        def _executar():
            try:
                gestor = get_gestor()
                cliente_ids = [c["id"] for c in payload["clientes"]]
                dados = gestor.subir_anuncio(
                    cliente_ids=cliente_ids,
                    drive_url=payload["drive_link"],
                    orcamento=payload["orcamento"],
                    campanha_nome=payload["campanha_nome"],
                    campanha_tipo=payload["campanha_tipo"],
                )
                mc_token = dados["mc_token"]
                eventos = gestor.consumir_stream(mc_token)
                resultado = _formatar_resultado_stream(eventos, len(payload["clientes"]))
                send_text(destino, resultado)
            except Exception as e:
                send_text(destino, f"Erro ao subir anúncios: {e}")
            finally:
                _limpar_sessao(sender_jid)

        threading.Thread(target=_executar, daemon=True).start()
        return

    # ── Confirmação de pausar/ativar ──────────────────────────────────────────
    if estado in ("aguardando_confirmacao_pausar", "aguardando_confirmacao_ativar"):
        acao = "pausar" if "pausar" in estado else "ativar"
        _limpar_sessao(sender_jid)
        campanhas = payload["campanhas"]
        send_text(destino, f"Executando... {len(campanhas)} campanha(s)")

        def _executar_status():
            try:
                gestor = get_gestor()
                ok, erros = 0, 0
                for cp in campanhas:
                    try:
                        if acao == "pausar":
                            gestor.pausar_campanha(cp["id"], cp["_cliente"]["token_key"])
                        else:
                            gestor.ativar_campanha(cp["id"], cp["_cliente"]["token_key"])
                        ok += 1
                    except Exception:
                        erros += 1
                msg = f"{ok}/{len(campanhas)} campanhas {'pausadas' if acao == 'pausar' else 'ativadas'}"
                if erros:
                    msg += f" ({erros} com erro)"
                send_text(destino, msg)
            except Exception as e:
                send_text(destino, f"Erro: {e}")

        threading.Thread(target=_executar_status, daemon=True).start()
        return
```

- [ ] **Step 5: Rodar todos os testes**

```bash
cd /root && /root/venv/bin/python -m pytest tests/test_jake_whatsapp_gestor.py tests/test_gestor_whatsapp.py -v
```
Expected: todos passando.

- [ ] **Step 6: Commit**

```bash
git add bot/jake_whatsapp.py
git commit -m "feat(whatsapp): roteamento gestor — _sessoes, pausar/ativar, subir anuncio"
```

---

## Task 6: Reiniciar Jake WhatsApp e Smoke Test

- [ ] **Step 1: Reiniciar jake-whatsapp**

```bash
systemctl restart jake-whatsapp
sleep 3
systemctl status jake-whatsapp | head -10
```
Expected: `active (running)`

- [ ] **Step 2: Verificar logs por erros de import**

```bash
journalctl -u jake-whatsapp -n 30 --no-pager
```
Expected: sem ImportError ou SyntaxError.

- [ ] **Step 3: Testar health**

```bash
curl -s http://localhost:5052/health | python3 -m json.tool
```
Expected: `{"ok": true, ...}`

- [ ] **Step 4: Commit final**

```bash
git add -A
git commit -m "feat(whatsapp): Jake Gestor via WhatsApp — Fase 1 completa"
```

---

## Notas de Implementação

- **Orçamento ausente:** se `orcamento_diario` não estiver cadastrado no cliente e Bruno não informar, Jake pergunta antes de confirmar.
- **Campanha nome padrão:** `"WA DD/MM"` se Bruno não informar.
- **Stream SSE:** `consumir_stream` é bloqueante mas roda em thread separada — não trava o webhook.
- **Jake OS auth:** usa form POST (`email`, `password`) — não JSON. O cookie de sessão Flask é mantido no `requests.Session()`.
- **Endpoint `/auth/login`** retorna redirect 302 — checar `resp.url` para detectar sucesso/falha.
- **Clientes ambíguos:** confirmados um a um em sequência antes de montar o resumo final.
