# Social Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar módulo "Social Brief" ao Jake OS que gera um portal HTML estático com análise semanal de criativos por cliente, publica no Surge.sh e agenda atualização automática toda segunda-feira.

**Architecture:** Flask backend com SSE para progresso em tempo real; dados coletados via Meta Ads API, DuckDuckGo e arquivos HTML de perfil; análise gerada pelo Claude Sonnet; portal HTML autocontido gerado e publicado no Surge.sh. APScheduler dispara a geração toda segunda às 08h.

**Tech Stack:** Flask, psycopg2 (Neon), anthropic, requests (Meta Ads API v21.0), duckduckgo_search, BeautifulSoup4, APScheduler, subprocess/surge CLI, EventSource (browser SSE)

---

## File Structure

**Files to create:**
- `jake_desktop/static/js/social_brief.js` — módulo frontend SPA do Jake OS

**Files to modify:**
- `jake_desktop/app.py` — novas rotas, init tables, scheduler, helpers (inserir antes do bloco `if __name__ == "__main__":`)
- `jake_desktop/templates/dashboard.html` — nav item + section + script tag + init hook
- `jake_desktop/static/js/app.js` — adicionar `"social-brief"` ao array `valid`

---

## Task 1: Instalar dependências e verificar ambiente

**Files:**
- Run: `jake_desktop/venv/bin/pip install ...`
- Verify: `/root/.env`

- [ ] **Step 1: Instalar dependências Python no venv do Jake OS**

```bash
cd /root/jake_desktop
venv/bin/pip install apscheduler beautifulsoup4 duckduckgo-search
```
Esperado: `Successfully installed apscheduler-... beautifulsoup4-... duckduckgo_search-...`

- [ ] **Step 2: Verificar que surge está disponível**

```bash
which surge && surge --version
```
Esperado: `/usr/local/bin/surge` + versão (já instalado).

- [ ] **Step 3: Verificar variáveis de ambiente no .env**

Abrir `/root/.env` e confirmar que estas variáveis existem (adicionar se faltarem):
```
SURGE_TOKEN=<token_do_surge>
SURGE_URL=piloti-brief.surge.sh
SOCIAL_BRIEF_LOGIN=social
SOCIAL_BRIEF_SENHA=piloti2026
```
Se SURGE_TOKEN não existir, rodar `surge token` no terminal para obtê-lo.

- [ ] **Step 4: Testar import dos novos pacotes**

```bash
venv/bin/python -c "from apscheduler.schedulers.background import BackgroundScheduler; from bs4 import BeautifulSoup; from duckduckgo_search import DDGS; print('OK')"
```
Esperado: `OK`

- [ ] **Step 5: Commit**

```bash
cd /root
git add -A
git commit -m "chore: instala apscheduler, beautifulsoup4, duckduckgo-search"
```

---

## Task 2: Tabelas do banco de dados + init

**Files:**
- Modify: `jake_desktop/app.py` (após `_init_rotina_tables`, antes de `app = Flask(...)`)

- [ ] **Step 1: Adicionar função `_init_social_brief_tables` em `app.py`**

Localizar no arquivo (via Grep) a linha com `app = Flask(` e inserir o seguinte bloco ANTES dela:

```python
def _init_social_brief_tables():
    """Cria tabelas do módulo Social Brief se não existirem."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_brief_clientes (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(200) NOT NULL,
                slug VARCHAR(100) UNIQUE NOT NULL,
                nicho VARCHAR(100),
                meta_account_id VARCHAR(100),
                meta_agency VARCHAR(50) DEFAULT 'piloti',
                concorrentes TEXT[] DEFAULT '{}',
                tipos_campanha JSONB DEFAULT '{}',
                ativo BOOLEAN DEFAULT TRUE,
                criado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_brief_geracoes (
                id SERIAL PRIMARY KEY,
                semana_inicio DATE NOT NULL,
                semana_fim DATE NOT NULL,
                html_completo TEXT,
                surge_url VARCHAR(300),
                publicado BOOLEAN DEFAULT FALSE,
                clientes_incluidos JSONB DEFAULT '[]',
                criado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_brief_cliente_dados (
                id SERIAL PRIMARY KEY,
                geracao_id INTEGER REFERENCES social_brief_geracoes(id) ON DELETE CASCADE,
                cliente_id INTEGER REFERENCES social_brief_clientes(id) ON DELETE CASCADE,
                analise_json JSONB,
                dados_meta JSONB,
                criado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 2: Chamar `_init_social_brief_tables()` no bloco `__main__`**

Localizar a linha `_init_rotina_tables()` em `if __name__ == "__main__":` e adicionar abaixo:

```python
    _init_social_brief_tables()
```

- [ ] **Step 3: Testar que o Jake OS sobe sem erro**

```bash
cd /root/jake_desktop
fuser -k 5050/tcp 2>/dev/null; sleep 1
nohup venv/bin/python app.py >> /tmp/jake_os.log 2>&1 &
sleep 3
grep -i "error\|traceback" /tmp/jake_os.log | head -5
curl -s http://localhost:5050/login | grep -q "Jake" && echo "OK"
```
Esperado: nenhum erro no log, `OK` no curl.

- [ ] **Step 4: Verificar tabelas criadas no Neon**

```bash
cd /root/jake_desktop
venv/bin/python -c "
from app import _get_db
conn = _get_db()
cur = conn.cursor()
cur.execute(\"\"\"SELECT table_name FROM information_schema.tables
WHERE table_name LIKE 'social_brief%'\"\"\")
print([r['table_name'] for r in cur.fetchall()])
conn.close()
"
```
Esperado: `['social_brief_clientes', 'social_brief_geracoes', 'social_brief_cliente_dados']`

- [ ] **Step 5: Commit**

```bash
cd /root
git add jake_desktop/app.py
git commit -m "feat: cria tabelas social_brief no Neon"
```

---

## Task 3: CRUD de clientes + endpoint última geração

**Files:**
- Modify: `jake_desktop/app.py` (adicionar 5 rotas antes de `if __name__ == "__main__":`)

- [ ] **Step 1: Adicionar rotas CRUD de clientes + última geração em `app.py`**

Localizar a linha `if __name__ == "__main__":` e inserir o bloco completo abaixo logo antes dela:

```python
# ── Social Brief — CRUD de clientes ─────────────────────────────────────────

@app.route("/api/social-brief/clientes", methods=["GET"])
@login_required
def sb_clientes_list():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM social_brief_clientes ORDER BY nome")
        clientes = [dict(r) for r in cur.fetchall()]
        # converte arrays e jsonb para json serializável
        for c in clientes:
            if c.get("concorrentes") is None:
                c["concorrentes"] = []
            if c.get("tipos_campanha") is None:
                c["tipos_campanha"] = {}
        return jsonify({"clientes": clientes})
    finally:
        conn.close()


@app.route("/api/social-brief/clientes", methods=["POST"])
@login_required
def sb_clientes_create():
    data = request.get_json()
    if not data or not data.get("nome") or not data.get("slug"):
        return jsonify({"error": "nome e slug obrigatórios"}), 400
    import re as _re_slug
    if not _re_slug.match(r'^[a-z0-9-]+$', data["slug"]):
        return jsonify({"error": "slug deve conter apenas letras minúsculas, números e hifens"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO social_brief_clientes
               (nome, slug, nicho, meta_account_id, meta_agency,
                concorrentes, tipos_campanha, ativo)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",
            (
                data["nome"], data["slug"],
                data.get("nicho", ""),
                data.get("meta_account_id", ""),
                data.get("meta_agency", "piloti"),
                data.get("concorrentes", []),
                json.dumps(data.get("tipos_campanha", {})),
                data.get("ativo", True),
            )
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"ok": True, "id": new_id})
    finally:
        conn.close()


@app.route("/api/social-brief/clientes/<int:cid>", methods=["PUT"])
@login_required
def sb_clientes_update(cid):
    data = request.get_json()
    if not data:
        return jsonify({"error": "body obrigatório"}), 400
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE social_brief_clientes SET
               nome=%s, slug=%s, nicho=%s,
               meta_account_id=%s, meta_agency=%s,
               concorrentes=%s, tipos_campanha=%s, ativo=%s
               WHERE id=%s""",
            (
                data.get("nome"), data.get("slug"),
                data.get("nicho", ""),
                data.get("meta_account_id", ""),
                data.get("meta_agency", "piloti"),
                data.get("concorrentes", []),
                json.dumps(data.get("tipos_campanha", {})),
                data.get("ativo", True),
                cid,
            )
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/social-brief/clientes/<int:cid>", methods=["DELETE"])
@login_required
def sb_clientes_delete(cid):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM social_brief_clientes WHERE id=%s", (cid,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/social-brief/ultima-geracao", methods=["GET"])
@login_required
def sb_ultima_geracao():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, semana_inicio, semana_fim, surge_url, publicado, criado_em "
            "FROM social_brief_geracoes ORDER BY criado_em DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"geracao": None})
        g = dict(row)
        g["semana_inicio"] = str(g["semana_inicio"])
        g["semana_fim"] = str(g["semana_fim"])
        g["criado_em"] = str(g["criado_em"])
        return jsonify({"geracao": g})
    finally:
        conn.close()
```

- [ ] **Step 2: Reiniciar Jake OS e testar endpoints**

```bash
cd /root/jake_desktop
fuser -k 5050/tcp 2>/dev/null; sleep 1
nohup venv/bin/python app.py >> /tmp/jake_os.log 2>&1 &
sleep 3

# Testar GET clientes (deve retornar lista vazia)
curl -s -b /tmp/test_session.txt -c /tmp/test_session.txt \
  -X POST http://localhost:5050/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@jakeos.local","password":"Jake@2024!"}' | head -3

curl -s -b /tmp/test_session.txt \
  http://localhost:5050/api/social-brief/clientes | python3 -c "import json,sys; d=json.load(sys.stdin); print('clientes:', len(d['clientes']))"
```
Esperado: `clientes: 0`

- [ ] **Step 3: Testar POST + PUT + DELETE**

```bash
# Criar cliente de teste
curl -s -b /tmp/test_session.txt \
  -X POST http://localhost:5050/api/social-brief/clientes \
  -H "Content-Type: application/json" \
  -d '{"nome":"Teste","slug":"teste","nicho":"academia","meta_account_id":"act_123","concorrentes":["rival1"],"tipos_campanha":{"mensagem":true}}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('id:', d.get('id'), 'ok:', d.get('ok'))"

# Listar novamente
curl -s -b /tmp/test_session.txt \
  http://localhost:5050/api/social-brief/clientes | python3 -c "import json,sys; d=json.load(sys.stdin); print('clientes:', len(d['clientes']), '/ nome:', d['clientes'][0]['nome'] if d['clientes'] else 'none')"

# Deletar (usar o id retornado no POST)
LAST_ID=$(curl -s -b /tmp/test_session.txt http://localhost:5050/api/social-brief/clientes | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['clientes'][0]['id'] if d['clientes'] else '0')")
curl -s -b /tmp/test_session.txt -X DELETE http://localhost:5050/api/social-brief/clientes/$LAST_ID
```
Esperado: `id: 1 ok: True`, `clientes: 1 / nome: Teste`, DELETE retorna `{"ok": true}`

- [ ] **Step 4: Commit**

```bash
cd /root
git add jake_desktop/app.py
git commit -m "feat: CRUD clientes e endpoint última geração para Social Brief"
```

---

## Task 4: Helpers de coleta de dados (Meta Ads, DuckDuckGo, HTML perfil)

**Files:**
- Modify: `jake_desktop/app.py` (adicionar helpers antes das rotas CRUD do Task 3)

- [ ] **Step 1: Adicionar helper `_sb_buscar_meta_ads` em `app.py`**

Inserir imediatamente antes do bloco `# ── Social Brief — CRUD de clientes`:

```python
# ── Social Brief — helpers de coleta ────────────────────────────────────────

def _sb_buscar_meta_ads(meta_account_id, meta_agency="piloti"):
    """
    Busca top 10 criativos por CTR na última semana via Meta Ads API.
    Retorna dict com 'periodo', 'criativos', 'resumo'.
    """
    import re as _re_meta
    if not meta_account_id or not _re_meta.match(r'^act_\d+$', meta_account_id):
        return {"erro": "meta_account_id inválido", "criativos": [], "resumo": {}}

    token_fn = _META_TOKENS.get(meta_agency)
    if not token_fn:
        return {"erro": f"Agência '{meta_agency}' não configurada", "criativos": [], "resumo": {}}
    token = token_fn()
    if not token:
        return {"erro": "Token Meta não configurado", "criativos": [], "resumo": {}}

    try:
        # Busca anúncios com insights dos últimos 7 dias
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{meta_account_id}/ads",
            params={
                "fields": (
                    "id,name,"
                    "creative{id,name,thumbnail_url,body,title,call_to_action_type},"
                    "insights.date_preset(last_7d)"
                    "{impressions,clicks,ctr,spend,cpm,actions,cost_per_action_type}"
                ),
                "limit": 50,
                "access_token": token,
            },
            timeout=20,
        )
        if not r.ok:
            err = r.json().get("error", {})
            return {"erro": err.get("message", f"Meta API {r.status_code}"), "criativos": [], "resumo": {}}

        ads_raw = r.json().get("data", [])
        criativos = []
        for ad in ads_raw:
            insights_data = ad.get("insights", {}).get("data", [])
            if not insights_data:
                continue
            ins = insights_data[0]
            ctr = float(ins.get("ctr") or 0)
            cliques = int(ins.get("clicks") or 0)
            impressoes = int(ins.get("impressions") or 0)
            gasto = float(ins.get("spend") or 0)

            # CPL: custo por lead ou mensagem
            actions = ins.get("actions") or []
            costs = ins.get("cost_per_action_type") or []
            def _find_act(arr, *types):
                for e in arr:
                    if e.get("action_type") in types:
                        try: return float(e.get("value", 0) or 0)
                        except: return 0.0
                return 0.0
            leads = _find_act(actions, "lead", "onsite_conversion.messaging_conversation_started_7d")
            cpl = _find_act(costs, "lead", "onsite_conversion.messaging_conversation_started_7d")

            creative = ad.get("creative") or {}
            criativos.append({
                "id": ad.get("id", ""),
                "nome": ad.get("name", ""),
                "thumbnail_url": creative.get("thumbnail_url", ""),
                "ctr": round(ctr, 2),
                "cliques": cliques,
                "impressoes": impressoes,
                "gasto": round(gasto, 2),
                "cpl": round(cpl, 2),
                "leads": int(leads),
                "tipo_campanha": creative.get("call_to_action_type", ""),
            })

        # Ordena por CTR decrescente, top 10
        criativos.sort(key=lambda x: x["ctr"], reverse=True)
        criativos = criativos[:10]

        total_gasto = sum(c["gasto"] for c in criativos)
        media_ctr = round(sum(c["ctr"] for c in criativos) / len(criativos), 2) if criativos else 0

        # Período: calculado manualmente (last_7d)
        from datetime import date, timedelta
        hoje = date.today()
        inicio = (hoje - timedelta(days=7)).isoformat()
        fim = hoje.isoformat()

        return {
            "periodo": {"inicio": inicio, "fim": fim},
            "criativos": criativos,
            "resumo": {
                "total_gasto": round(total_gasto, 2),
                "media_ctr": media_ctr,
                "melhor_criativo": criativos[0] if criativos else {},
                "pior_criativo": criativos[-1] if criativos else {},
            }
        }
    except Exception as e:
        return {"erro": str(e), "criativos": [], "resumo": {}}


def _sb_buscar_concorrentes(nicho, concorrentes):
    """
    Pesquisa concorrentes via DuckDuckGo.
    Retorna texto consolidado com resultados.
    """
    try:
        from duckduckgo_search import DDGS
        from datetime import date
        ano = date.today().year
        resultados = []
        queries = []
        for conc in (concorrentes or [])[:3]:
            queries.append(f"{conc} Instagram anúncios tráfego pago")
        queries.append(f"{nicho} tráfego pago criativos {ano}")
        queries.append(f"{nicho} hooks copy anúncios Meta Ads")

        with DDGS() as ddg:
            for query in queries:
                try:
                    res = list(ddg.text(query, max_results=3))
                    for r in res:
                        resultados.append(f"[{query}] {r.get('title','')} — {r.get('body','')}")
                except Exception:
                    pass

        return {"conteudo_pesquisa": "\n".join(resultados[:20])}
    except Exception as e:
        return {"conteudo_pesquisa": f"Erro na pesquisa: {e}"}


def _sb_ler_perfil_html(slug):
    """
    Tenta ler arquivo HTML de análise do cliente em static/reports/{slug}_relatorio.html.
    Extrai texto via BeautifulSoup. Retorna string vazia se não encontrar.
    """
    try:
        from bs4 import BeautifulSoup
        caminhos = [
            os.path.join(_basedir, "static", "reports", f"{slug}_relatorio.html"),
            os.path.join(_basedir, "static", "uploads", f"{slug}_relatorio.html"),
            os.path.join(_basedir, "static", f"{slug}_relatorio.html"),
        ]
        for caminho in caminhos:
            if os.path.exists(caminho):
                with open(caminho, "r", encoding="utf-8", errors="ignore") as f:
                    html = f.read()
                soup = BeautifulSoup(html, "html.parser")
                texto = soup.get_text(separator=" ", strip=True)
                return texto[:4000]  # Limita para não explodir o prompt
        return ""
    except Exception:
        return ""
```

- [ ] **Step 2: Testar helpers individualmente**

```bash
cd /root/jake_desktop
venv/bin/python -c "
import os; os.environ.setdefault('DATABASE_URL', open('/root/.env').read().split('DATABASE_URL=')[1].split('\n')[0].strip())
from dotenv import load_dotenv
load_dotenv('/root/.env')
from app import _sb_buscar_concorrentes, _sb_ler_perfil_html

# Testar DuckDuckGo
res = _sb_buscar_concorrentes('academia', ['SmartFit', 'Bodytech'])
print('Pesquisa chars:', len(res['conteudo_pesquisa']))

# Testar HTML perfil (arquivo inexistente — deve retornar vazio)
txt = _sb_ler_perfil_html('cliente-teste')
print('Perfil (deve ser vazio):', repr(txt[:50]))
"
```
Esperado: `Pesquisa chars: >100`, `Perfil (deve ser vazio): ''`

- [ ] **Step 3: Commit**

```bash
cd /root
git add jake_desktop/app.py
git commit -m "feat: helpers Meta Ads, DuckDuckGo e leitura HTML para Social Brief"
```

---

## Task 5: Geração de análise via Claude Sonnet

**Files:**
- Modify: `jake_desktop/app.py` (adicionar `_sb_gerar_analise_claude` após os helpers do Task 4)

- [ ] **Step 1: Adicionar função `_sb_gerar_analise_claude` em `app.py`**

Inserir logo após `_sb_ler_perfil_html` (antes do bloco CRUD):

```python
def _sb_gerar_analise_claude(cliente, dados_meta, perfil_texto, conteudo_pesquisa):
    """
    Chama Claude Sonnet para gerar análise completa do cliente.
    Retorna dict parseado do JSON retornado pelo modelo.
    """
    _ant = _anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    system_prompt = (
        "Você é um estrategista sênior de tráfego pago especializado em performance de "
        "criativos para Meta Ads e social media. Analise os dados e retorne APENAS JSON "
        "válido, sem markdown, sem texto adicional, sem blocos de código.\n\n"
        "Estrutura obrigatória:\n"
        '{"resumo_semana":"análise em 3-4 linhas",'
        '"ranking_criativos":[{"posicao":1,"nome":"...","thumbnail_url":"...",'
        '"destaque":"por que performou em 1 frase","metricas":{"ctr":"2.45%",'
        '"cliques":1203,"cpl":"R$ 12,50","gasto":"R$ 150,00"}}],'
        '"o_que_funcionou":["insight 1","insight 2","insight 3"],'
        '"o_que_nao_funcionou":["ponto 1","ponto 2"],'
        '"perfil_publico":{"genero_predominante":"...","faixa_etaria":"...",'
        '"melhor_posicionamento":"...","cpl_medio":"R$ X,XX"},'
        '"hooks_sugeridos":{"localizacao":["hook 1","hook 2","hook 3"],'
        '"genero":["hook 1","hook 2","hook 3"],"idade":["hook 1","hook 2","hook 3"],'
        '"dor_principal":["hook 1","hook 2","hook 3"]},'
        '"ctas_sugeridos":{"mensagem":["CTA 1","CTA 2"],"visita_perfil":["CTA 1","CTA 2"],'
        '"lead":["CTA 1","CTA 2"]},'
        '"sugestoes_criativos":[{"tipo":"video/imagem/carrossel","conceito":"...",'
        '"hook":"...","referencia":"..."}],'
        '"analise_concorrentes":[{"nome":"...","o_que_fazem":"...","oportunidade":"..."}],'
        '"campanhas_ativas":[{"tipo":"...","objetivo":"...","recomendacao":"..."}]}'
    )
    user_prompt = (
        f"Cliente: {cliente['nome']}\n"
        f"Nicho: {cliente.get('nicho', 'não informado')}\n\n"
        f"=== META ADS — ÚLTIMA SEMANA ===\n{json.dumps(dados_meta, ensure_ascii=False)}\n\n"
        f"=== PERFIL HISTÓRICO DO PÚBLICO ===\n{perfil_texto or 'Não disponível'}\n\n"
        f"=== PESQUISA DE CONCORRENTES ===\n{conteudo_pesquisa}\n\n"
        f"=== CAMPANHAS ATIVAS ===\n{json.dumps(cliente.get('tipos_campanha', {}), ensure_ascii=False)}\n\n"
        f"Hooks e CTAs devem ser específicos para o nicho {cliente.get('nicho', '')}.\n"
        f"Valores monetários em formato brasileiro (R$ X,XX)."
    )
    try:
        resp = _ant.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
        )
        raw = resp.content[0].text.strip()
        # Remove possíveis blocos de código residuais
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except json.JSONDecodeError:
        # Retorna estrutura mínima em caso de erro de parse
        return {
            "resumo_semana": "Análise indisponível (erro de formato).",
            "ranking_criativos": [],
            "o_que_funcionou": [],
            "o_que_nao_funcionou": [],
            "perfil_publico": {},
            "hooks_sugeridos": {},
            "ctas_sugeridos": {},
            "sugestoes_criativos": [],
            "analise_concorrentes": [],
            "campanhas_ativas": [],
        }
    except Exception as e:
        return {
            "resumo_semana": f"Erro na análise: {str(e)}",
            "ranking_criativos": [],
            "o_que_funcionou": [],
            "o_que_nao_funcionou": [],
            "perfil_publico": {},
            "hooks_sugeridos": {},
            "ctas_sugeridos": {},
            "sugestoes_criativos": [],
            "analise_concorrentes": [],
            "campanhas_ativas": [],
        }
```

- [ ] **Step 2: Commit**

```bash
cd /root
git add jake_desktop/app.py
git commit -m "feat: helper Claude Sonnet para análise de criativos Social Brief"
```

---

## Task 6: Gerador de HTML do portal + publicação no Surge

**Files:**
- Modify: `jake_desktop/app.py` (adicionar `_sb_gerar_html_portal` e `_sb_publicar_surge`)

- [ ] **Step 1: Adicionar `_sb_gerar_html_portal` em `app.py`**

Inserir após `_sb_gerar_analise_claude` (antes do bloco CRUD):

```python
def _sb_gerar_html_portal(todos_dados, semana_inicio, semana_fim):
    """
    Gera HTML autocontido único com todos os clientes.
    todos_dados: list de {'cliente': dict, 'analise': dict, 'dados_meta': dict}
    """
    login_user = os.environ.get("SOCIAL_BRIEF_LOGIN", "social")
    login_senha = os.environ.get("SOCIAL_BRIEF_SENHA", "piloti2026")
    primeiro_slug = todos_dados[0]["cliente"]["slug"] if todos_dados else "cliente"

    from datetime import date as _date
    hoje_str = _date.today().strftime("%d/%m/%Y")

    # Monta seções de clientes
    secoes_html = ""
    menu_items_html = ""
    for item in todos_dados:
        cl = item["cliente"]
        an = item["analise"]
        dm = item["dados_meta"]

        slug = cl["slug"]
        menu_items_html += f"""
        <a class="menu-item" data-slug="{slug}" href="#" onclick="mostrarCliente('{slug}'); return false;">
          🟢 {cl['nome']}
        </a>"""

        # KPIs
        resumo = dm.get("resumo", {})
        total_gasto = resumo.get("total_gasto", 0)
        media_ctr = resumo.get("media_ctr", 0)
        perf_pub = an.get("perfil_publico", {})
        cpl_medio = perf_pub.get("cpl_medio", "—")

        # Ranking de criativos
        ranking_html = ""
        medalhas = ["🥇", "🥈", "🥉"]
        for i, cri in enumerate(an.get("ranking_criativos", [])[:5]):
            med = medalhas[i] if i < 3 else f"#{i+1}"
            metricas = cri.get("metricas", {})
            thumb = cri.get("thumbnail_url", "")
            thumb_tag = f'<img src="{thumb}" alt="criativo" style="width:80px;height:80px;object-fit:cover;border-radius:8px;margin-right:16px;">' if thumb else '<div style="width:80px;height:80px;background:#ddd;border-radius:8px;margin-right:16px;flex-shrink:0;"></div>'
            ranking_html += f"""
            <div style="display:flex;align-items:center;background:#fff;border:1px solid #e0e0e0;border-radius:12px;padding:16px;margin-bottom:12px;">
              <div style="font-size:28px;margin-right:16px;flex-shrink:0;">{med}</div>
              {thumb_tag}
              <div style="flex:1;">
                <div style="font-weight:600;margin-bottom:4px;">{cri.get('nome','')}</div>
                <div style="font-size:13px;color:#555;margin-bottom:8px;">{cri.get('destaque','')}</div>
                <div style="display:flex;gap:12px;flex-wrap:wrap;">
                  <span style="background:#e8f5e9;color:#2e7d32;padding:2px 10px;border-radius:20px;font-size:12px;">CTR {metricas.get('ctr','—')}</span>
                  <span style="background:#e3f2fd;color:#1565c0;padding:2px 10px;border-radius:20px;font-size:12px;">Cliques {metricas.get('cliques','—')}</span>
                  <span style="background:#fff3e0;color:#e65100;padding:2px 10px;border-radius:20px;font-size:12px;">CPL {metricas.get('cpl','—')}</span>
                  <span style="background:#f3e5f5;color:#6a1b9a;padding:2px 10px;border-radius:20px;font-size:12px;">Gasto {metricas.get('gasto','—')}</span>
                </div>
              </div>
            </div>"""

        # O que funcionou/não funcionou
        fun_html = "".join(f'<div style="padding:8px 0;border-bottom:1px solid #f0f0f0;">✅ {x}</div>' for x in an.get("o_que_funcionou", []))
        nao_fun_html = "".join(f'<div style="padding:8px 0;border-bottom:1px solid #f0f0f0;">❌ {x}</div>' for x in an.get("o_que_nao_funcionou", []))

        # Hooks — abas simplificadas
        hooks = an.get("hooks_sugeridos", {})
        hook_tabs_html = ""
        for tipo, lista in hooks.items():
            label = {"localizacao": "📍 Localização", "genero": "👤 Gênero", "idade": "🎂 Idade", "dor_principal": "💊 Dor"}.get(tipo, tipo)
            items = "".join(f'<div style="background:#f5f5f5;border-radius:8px;padding:12px;margin-bottom:8px;position:relative;">{h}<button onclick="copiar(\'{h.replace(chr(39), chr(39))}\', this)" style="position:absolute;right:8px;top:8px;background:#1a237e;color:#fff;border:none;border-radius:6px;padding:2px 8px;font-size:11px;cursor:pointer;">📋</button></div>' for h in lista)
            hook_tabs_html += f'<div style="margin-bottom:20px;"><div style="font-weight:600;color:#1a237e;margin-bottom:8px;">{label}</div>{items}</div>'

        # Sugestões de criativos
        sug_html = ""
        for sg in an.get("sugestoes_criativos", [])[:4]:
            sug_html += f"""<div style="background:#fff;border:1px solid #e0e0e0;border-radius:12px;padding:16px;margin-bottom:12px;">
              <div style="font-size:12px;color:#ff6b35;font-weight:600;margin-bottom:4px;">{sg.get('tipo','').upper()}</div>
              <div style="font-weight:600;margin-bottom:4px;">{sg.get('conceito','')}</div>
              <div style="font-size:13px;color:#555;margin-bottom:4px;"><b>Hook:</b> {sg.get('hook','')}</div>
              <div style="font-size:13px;color:#777;"><b>Referência:</b> {sg.get('referencia','')}</div>
            </div>"""

        # Análise de concorrentes
        conc_html = ""
        for cc in an.get("analise_concorrentes", []):
            conc_html += f"""<div style="background:#fff;border:1px solid #e0e0e0;border-radius:12px;padding:16px;margin-bottom:12px;">
              <div style="font-weight:600;margin-bottom:6px;">🏢 {cc.get('nome','')}</div>
              <div style="font-size:13px;margin-bottom:4px;"><b>O que fazem:</b> {cc.get('o_que_fazem','')}</div>
              <div style="font-size:13px;color:#2e7d32;"><b>Oportunidade:</b> {cc.get('oportunidade','')}</div>
            </div>"""

        # Campanhas ativas
        camp_html = ""
        for camp in an.get("campanhas_ativas", []):
            camp_html += f"<tr><td style='padding:10px;border-bottom:1px solid #f0f0f0;'>{camp.get('tipo','')}</td><td style='padding:10px;border-bottom:1px solid #f0f0f0;'>{camp.get('objetivo','')}</td><td style='padding:10px;border-bottom:1px solid #f0f0f0;'>{camp.get('recomendacao','')}</td></tr>"

        secoes_html += f"""
        <div class="cliente-secao" id="cliente-{slug}" style="display:none;">
          <!-- Header -->
          <div style="margin-bottom:32px;">
            <h2 style="font-size:28px;font-weight:700;color:#1a237e;margin:0 0 4px;">{cl['nome']}</h2>
            <div style="color:#666;font-size:14px;">📂 {cl.get('nicho','—')} &nbsp;•&nbsp; 📅 Semana de {semana_inicio} a {semana_fim} &nbsp;•&nbsp; 🔄 Atualizado em {hoje_str}</div>
          </div>

          <!-- KPIs -->
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:32px;">
            <div style="background:#fff;border-radius:16px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.06);text-align:center;">
              <div style="font-size:13px;color:#888;margin-bottom:6px;">💰 Total Gasto</div>
              <div style="font-size:26px;font-weight:700;color:#1a237e;">R$ {total_gasto:,.2f}</div>
            </div>
            <div style="background:#fff;border-radius:16px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.06);text-align:center;">
              <div style="font-size:13px;color:#888;margin-bottom:6px;">📈 CTR Médio</div>
              <div style="font-size:26px;font-weight:700;color:#2e7d32;">{media_ctr}%</div>
            </div>
            <div style="background:#fff;border-radius:16px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.06);text-align:center;">
              <div style="font-size:13px;color:#888;margin-bottom:6px;">🎯 CPL Médio</div>
              <div style="font-size:26px;font-weight:700;color:#ff6b35;">{cpl_medio}</div>
            </div>
          </div>

          <!-- Resumo semana -->
          <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:24px;">
            <h3 style="font-size:16px;font-weight:600;margin:0 0 12px;color:#1a237e;">📝 Resumo da Semana</h3>
            <p style="color:#444;line-height:1.7;margin:0;">{an.get('resumo_semana','')}</p>
          </div>

          <!-- Ranking criativos -->
          <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:24px;">
            <h3 style="font-size:16px;font-weight:600;margin:0 0 16px;color:#1a237e;">🏆 Ranking de Criativos</h3>
            {ranking_html if ranking_html else '<p style="color:#999;">Nenhum dado de criativo disponível.</p>'}
          </div>

          <!-- O que funcionou / não funcionou -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;">
            <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
              <h3 style="font-size:15px;font-weight:600;margin:0 0 16px;color:#2e7d32;">✅ O que funcionou</h3>
              {fun_html if fun_html else '<p style="color:#999;font-size:13px;">—</p>'}
            </div>
            <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
              <h3 style="font-size:15px;font-weight:600;margin:0 0 16px;color:#c62828;">❌ O que não funcionou</h3>
              {nao_fun_html if nao_fun_html else '<p style="color:#999;font-size:13px;">—</p>'}
            </div>
          </div>

          <!-- Perfil do público -->
          <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:24px;">
            <h3 style="font-size:16px;font-weight:600;margin:0 0 16px;color:#1a237e;">👥 Perfil do Público</h3>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">
              <div style="background:#f8f9fa;border-radius:12px;padding:16px;text-align:center;">
                <div style="font-size:20px;margin-bottom:4px;">👤</div>
                <div style="font-size:11px;color:#888;margin-bottom:4px;">Gênero</div>
                <div style="font-weight:600;font-size:13px;">{perf_pub.get('genero_predominante','—')}</div>
              </div>
              <div style="background:#f8f9fa;border-radius:12px;padding:16px;text-align:center;">
                <div style="font-size:20px;margin-bottom:4px;">🎂</div>
                <div style="font-size:11px;color:#888;margin-bottom:4px;">Faixa Etária</div>
                <div style="font-weight:600;font-size:13px;">{perf_pub.get('faixa_etaria','—')}</div>
              </div>
              <div style="background:#f8f9fa;border-radius:12px;padding:16px;text-align:center;">
                <div style="font-size:20px;margin-bottom:4px;">📱</div>
                <div style="font-size:11px;color:#888;margin-bottom:4px;">Posicionamento</div>
                <div style="font-weight:600;font-size:13px;">{perf_pub.get('melhor_posicionamento','—')}</div>
              </div>
              <div style="background:#f8f9fa;border-radius:12px;padding:16px;text-align:center;">
                <div style="font-size:20px;margin-bottom:4px;">💰</div>
                <div style="font-size:11px;color:#888;margin-bottom:4px;">CPL Médio</div>
                <div style="font-weight:600;font-size:13px;">{perf_pub.get('cpl_medio','—')}</div>
              </div>
            </div>
          </div>

          <!-- Hooks sugeridos -->
          <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:24px;">
            <h3 style="font-size:16px;font-weight:600;margin:0 0 16px;color:#1a237e;">💡 Hooks Sugeridos</h3>
            {hook_tabs_html if hook_tabs_html else '<p style="color:#999;font-size:13px;">—</p>'}
          </div>

          <!-- CTAs sugeridos -->
          <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:24px;">
            <h3 style="font-size:16px;font-weight:600;margin:0 0 16px;color:#1a237e;">📣 CTAs Sugeridos</h3>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">
              {''.join(f"""<div><div style="font-weight:600;font-size:13px;color:#ff6b35;margin-bottom:8px;">{'💬 Mensagem' if k=='mensagem' else '👤 Visita' if k=='visita_perfil' else '📋 Lead'}</div>{''.join(f'<div style="background:#f5f5f5;border-radius:8px;padding:10px;margin-bottom:6px;font-size:13px;position:relative;">{cta}<button onclick="copiar(\'{cta.replace(chr(39), chr(34))}\', this)" style="position:absolute;right:6px;top:6px;background:#1a237e;color:#fff;border:none;border-radius:4px;padding:1px 6px;font-size:10px;cursor:pointer;">📋</button></div>' for cta in v)}</div>""" for k,v in an.get('ctas_sugeridos', {}).items())}
            </div>
          </div>

          <!-- Sugestões de criativos -->
          <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:24px;">
            <h3 style="font-size:16px;font-weight:600;margin:0 0 16px;color:#1a237e;">🎨 Sugestões de Criativos</h3>
            {sug_html if sug_html else '<p style="color:#999;font-size:13px;">—</p>'}
          </div>

          <!-- Análise de concorrentes -->
          <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:24px;">
            <h3 style="font-size:16px;font-weight:600;margin:0 0 16px;color:#1a237e;">🏢 Análise de Concorrentes</h3>
            {conc_html if conc_html else '<p style="color:#999;font-size:13px;">—</p>'}
          </div>

          <!-- Campanhas ativas -->
          <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:24px;">
            <h3 style="font-size:16px;font-weight:600;margin:0 0 16px;color:#1a237e;">📊 Campanhas Ativas</h3>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
              <tr style="background:#f8f9fa;"><th style="padding:10px;text-align:left;">Tipo</th><th style="padding:10px;text-align:left;">Objetivo</th><th style="padding:10px;text-align:left;">Recomendação</th></tr>
              {camp_html if camp_html else '<tr><td colspan="3" style="padding:10px;color:#999;">—</td></tr>'}
            </table>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Piloti Agency — Social Media Brief</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Inter',sans-serif;background:#f8f9fa;color:#333;}}
a{{text-decoration:none;color:inherit;}}
/* Login */
#tela-login{{position:fixed;inset:0;background:#1a237e;display:flex;align-items:center;justify-content:center;z-index:9999;}}
.login-box{{background:#fff;border-radius:20px;padding:48px;width:360px;text-align:center;}}
.login-box h1{{color:#1a237e;font-size:22px;margin-bottom:8px;}}
.login-box p{{color:#888;font-size:13px;margin-bottom:28px;}}
.login-input{{width:100%;border:2px solid #e0e0e0;border-radius:10px;padding:12px 16px;font-size:15px;margin-bottom:12px;outline:none;}}
.login-input:focus{{border-color:#1a237e;}}
.login-btn{{width:100%;background:#1a237e;color:#fff;border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:600;cursor:pointer;}}
.login-btn:hover{{background:#283593;}}
#erro-login{{display:none;color:#c62828;font-size:13px;margin-top:8px;}}
/* App */
#app{{display:none;min-height:100vh;}}
.sidebar{{width:240px;background:#1a237e;color:#fff;padding:24px 0;position:fixed;height:100vh;overflow-y:auto;left:0;top:0;}}
.sidebar-logo{{padding:0 20px 24px;border-bottom:1px solid rgba(255,255,255,0.1);}}
.sidebar-logo h2{{font-size:16px;font-weight:700;}}
.sidebar-logo p{{font-size:12px;opacity:0.7;margin-top:4px;}}
.sidebar-semana{{padding:16px 20px;font-size:12px;opacity:0.7;border-bottom:1px solid rgba(255,255,255,0.1);}}
.sidebar-clientes{{padding:16px 0;}}
.sidebar-label{{padding:0 20px 8px;font-size:11px;font-weight:600;opacity:0.5;letter-spacing:1px;}}
.menu-item{{display:block;padding:10px 20px;font-size:14px;cursor:pointer;border-left:3px solid transparent;transition:all .2s;}}
.menu-item:hover,.menu-item.ativo{{background:rgba(255,107,53,0.2);border-left-color:#ff6b35;color:#fff;}}
.sidebar-logout{{padding:16px 20px;border-top:1px solid rgba(255,255,255,0.1);margin-top:auto;}}
.sidebar-logout button{{background:transparent;color:rgba(255,255,255,0.7);border:1px solid rgba(255,255,255,0.3);border-radius:8px;padding:8px 16px;cursor:pointer;font-size:13px;width:100%;}}
.sidebar-logout button:hover{{background:rgba(255,255,255,0.1);color:#fff;}}
.main-content{{margin-left:240px;padding:32px;min-height:100vh;}}
</style>
</head>
<body>

<!-- TELA DE LOGIN -->
<div id="tela-login">
  <div class="login-box">
    <h1>🚀 Piloti Agency</h1>
    <p>Social Media Brief Semanal</p>
    <input id="inp-login" class="login-input" type="text" placeholder="Usuário" />
    <input id="inp-senha" class="login-input" type="password" placeholder="Senha" onkeydown="if(event.key==='Enter')tentarLogin()" />
    <button class="login-btn" onclick="tentarLogin()">Entrar</button>
    <div id="erro-login">Usuário ou senha incorretos.</div>
  </div>
</div>

<!-- APP PRINCIPAL -->
<div id="app">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sidebar-logo">
      <h2>🚀 Piloti Agency</h2>
      <p>Social Media Brief</p>
    </div>
    <div class="sidebar-semana">📅 Semana de {semana_inicio} a {semana_fim}</div>
    <div class="sidebar-clientes">
      <div class="sidebar-label">CLIENTES</div>
      {menu_items_html}
    </div>
    <div class="sidebar-logout"><button onclick="logout()">↩ Sair</button></div>
  </div>

  <!-- Conteúdo principal -->
  <div class="main-content">
    {secoes_html}
  </div>
</div>

<!-- Rodapé (dentro de cada seção seria muito pesado — colocamos no main) -->
<script>
const LOGIN='{login_user}';const SENHA='{login_senha}';
function tentarLogin(){{
  var u=document.getElementById('inp-login').value;
  var s=document.getElementById('inp-senha').value;
  if(u===LOGIN&&s===SENHA){{
    localStorage.setItem('piloti_brief_auth','ok');
    document.getElementById('tela-login').style.display='none';
    document.getElementById('app').style.display='flex';
    mostrarCliente('{primeiro_slug}');
  }}else{{document.getElementById('erro-login').style.display='block';}}
}}
function verificarLogin(){{
  if(localStorage.getItem('piloti_brief_auth')==='ok'){{
    document.getElementById('tela-login').style.display='none';
    document.getElementById('app').style.display='flex';
    mostrarCliente('{primeiro_slug}');
  }}
}}
function logout(){{localStorage.removeItem('piloti_brief_auth');location.reload();}}
function mostrarCliente(slug){{
  document.querySelectorAll('.cliente-secao').forEach(function(s){{s.style.display='none';}});
  var el=document.getElementById('cliente-'+slug);
  if(el)el.style.display='block';
  document.querySelectorAll('.menu-item').forEach(function(m){{m.classList.remove('ativo');}});
  var mi=document.querySelector('[data-slug="'+slug+'"]');
  if(mi)mi.classList.add('ativo');
}}
function copiar(texto,btn){{
  navigator.clipboard.writeText(texto).then(function(){{
    var orig=btn.innerHTML;
    btn.innerHTML='✅';
    setTimeout(function(){{btn.innerHTML=orig;}},2000);
  }});
}}
window.onload=function(){{verificarLogin();}};
</script>
</body>
</html>"""
    return html


def _sb_publicar_surge(html):
    """
    Salva HTML em pasta temporária e publica via surge CLI.
    Retorna URL publicada.
    """
    import subprocess
    import tempfile
    surge_url = os.environ.get("SURGE_URL", "piloti-brief.surge.sh")
    surge_token = os.environ.get("SURGE_TOKEN", "")
    if not surge_token:
        raise ValueError("SURGE_TOKEN não configurado no .env")

    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = os.path.join(tmpdir, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)
        cmd = ["surge", tmpdir, surge_url, "--token", surge_token]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            raise RuntimeError(f"Surge error: {result.stderr or result.stdout}")
    return f"https://{surge_url}"
```

- [ ] **Step 2: Commit**

```bash
cd /root
git add jake_desktop/app.py
git commit -m "feat: gerador HTML portal e publicação Surge para Social Brief"
```

---

## Task 7: Endpoint SSE orquestrador + endpoint download HTML + APScheduler

**Files:**
- Modify: `jake_desktop/app.py` (adicionar rotas e scheduler)

- [ ] **Step 1: Adicionar endpoint SSE `/api/social-brief/gerar` e `/api/social-brief/download-html`**

Adicionar logo após as rotas CRUD (antes de `if __name__ == "__main__":`)

```python
@app.route("/api/social-brief/gerar", methods=["GET"])
@login_required
def sb_gerar_portal():
    """
    Endpoint SSE: gera portal completo com todos os clientes ativos.
    Emite eventos de progresso via text/event-stream.
    """
    from flask import stream_with_context, Response as _Response
    from datetime import date as _date, timedelta as _td

    def _generate():
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM social_brief_clientes WHERE ativo=TRUE ORDER BY nome")
            clientes = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

        if not clientes:
            yield f"data: {json.dumps({'status': 'erro', 'mensagem': 'Nenhum cliente ativo cadastrado'})}\n\n"
            return

        todos_dados = []
        total = len(clientes)

        for i, cliente in enumerate(clientes):
            progresso = int((i / total) * 80)

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'etapa': 'Buscando Meta Ads...', 'progresso': progresso})}\n\n"
            dados_meta = _sb_buscar_meta_ads(
                cliente.get("meta_account_id", ""),
                cliente.get("meta_agency", "piloti")
            )

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'etapa': 'Lendo perfil...', 'progresso': progresso + 2})}\n\n"
            perfil_texto = _sb_ler_perfil_html(cliente["slug"])

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'etapa': 'Pesquisando concorrentes...', 'progresso': progresso + 4})}\n\n"
            pesquisa = _sb_buscar_concorrentes(
                cliente.get("nicho", ""),
                cliente.get("concorrentes") or []
            )

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'etapa': 'Gerando análise com Claude...', 'progresso': progresso + 6})}\n\n"
            analise = _sb_gerar_analise_claude(
                cliente, dados_meta,
                perfil_texto,
                pesquisa.get("conteudo_pesquisa", "")
            )

            todos_dados.append({
                "cliente": cliente,
                "analise": analise,
                "dados_meta": dados_meta,
            })

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'status': 'concluido', 'progresso': int(((i + 1) / total) * 80)})}\n\n"
            time.sleep(1)

        yield f"data: {json.dumps({'etapa': 'Gerando HTML final...', 'progresso': 85})}\n\n"

        hoje = _date.today()
        semana_inicio = (hoje - _td(days=hoje.weekday())).strftime("%d/%m/%Y")
        semana_fim = (hoje - _td(days=hoje.weekday()) + _td(days=6)).strftime("%d/%m/%Y")
        html_portal = _sb_gerar_html_portal(todos_dados, semana_inicio, semana_fim)

        # Salvar geração no banco
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO social_brief_geracoes
                   (semana_inicio, semana_fim, html_completo, publicado, clientes_incluidos)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    (hoje - _td(days=hoje.weekday())).isoformat(),
                    (hoje - _td(days=hoje.weekday()) + _td(days=6)).isoformat(),
                    html_portal,
                    False,
                    json.dumps([{"id": d["cliente"]["id"], "nome": d["cliente"]["nome"]} for d in todos_dados]),
                )
            )
            geracao_id = cur.fetchone()["id"]
            # Salvar dados por cliente
            for item in todos_dados:
                cur.execute(
                    """INSERT INTO social_brief_cliente_dados
                       (geracao_id, cliente_id, analise_json, dados_meta)
                       VALUES (%s, %s, %s, %s)""",
                    (
                        geracao_id,
                        item["cliente"]["id"],
                        json.dumps(item["analise"]),
                        json.dumps(item["dados_meta"]),
                    )
                )
            conn.commit()
        finally:
            conn.close()

        yield f"data: {json.dumps({'etapa': 'Publicando no Surge...', 'progresso': 90})}\n\n"

        try:
            url = _sb_publicar_surge(html_portal)
            # Atualizar surge_url no banco
            conn = _get_db()
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE social_brief_geracoes SET surge_url=%s, publicado=TRUE WHERE id=%s",
                    (url, geracao_id)
                )
                conn.commit()
            finally:
                conn.close()

            yield f"data: {json.dumps({'status': 'finalizado', 'url': url, 'progresso': 100})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'finalizado_sem_surge', 'erro_surge': str(e), 'geracao_id': geracao_id, 'progresso': 100})}\n\n"

    return _Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.route("/api/social-brief/download/<int:geracao_id>", methods=["GET"])
@login_required
def sb_download_html(geracao_id):
    """Permite baixar o HTML gerado de uma geração específica."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT html_completo, criado_em FROM social_brief_geracoes WHERE id=%s", (geracao_id,))
        row = cur.fetchone()
        if not row or not row["html_completo"]:
            return jsonify({"error": "Geração não encontrada"}), 404
        from flask import make_response
        resp = make_response(row["html_completo"])
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        resp.headers["Content-Disposition"] = f'attachment; filename="piloti-brief-{geracao_id}.html"'
        return resp
    finally:
        conn.close()
```

- [ ] **Step 2: Adicionar APScheduler no bloco `__main__`**

Localizar o bloco `if __name__ == "__main__":` e adicionar o seguinte logo após `_init_social_brief_tables()`:

```python
    # APScheduler: Social Brief automático toda segunda às 08h
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from zoneinfo import ZoneInfo as _ZI

        def _job_social_brief():
            """Executa geração do Social Brief de forma síncrona (sem SSE)."""
            with app.app_context():
                from datetime import date as _d, timedelta as _td2
                conn = _get_db()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM social_brief_clientes WHERE ativo=TRUE ORDER BY nome")
                    clientes = [dict(r) for r in cur.fetchall()]
                finally:
                    conn.close()
                if not clientes:
                    print("[Social Brief] Nenhum cliente ativo — abortando")
                    return
                todos_dados = []
                for cliente in clientes:
                    try:
                        dm = _sb_buscar_meta_ads(cliente.get("meta_account_id",""), cliente.get("meta_agency","piloti"))
                        pt = _sb_ler_perfil_html(cliente["slug"])
                        pq = _sb_buscar_concorrentes(cliente.get("nicho",""), cliente.get("concorrentes") or [])
                        an = _sb_gerar_analise_claude(cliente, dm, pt, pq.get("conteudo_pesquisa",""))
                        todos_dados.append({"cliente": cliente, "analise": an, "dados_meta": dm})
                        time.sleep(2)
                    except Exception as e:
                        print(f"[Social Brief] Erro no cliente {cliente['nome']}: {e}")
                if todos_dados:
                    hoje = _d.today()
                    si = (hoje - _td2(days=hoje.weekday())).strftime("%d/%m/%Y")
                    sf = (hoje - _td2(days=hoje.weekday()) + _td2(days=6)).strftime("%d/%m/%Y")
                    html = _sb_gerar_html_portal(todos_dados, si, sf)
                    try:
                        url = _sb_publicar_surge(html)
                        print(f"[Social Brief] Portal publicado: {url}")
                    except Exception as e:
                        print(f"[Social Brief] Erro ao publicar: {e}")

        _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
        _scheduler.add_job(_job_social_brief, "cron", day_of_week="mon", hour=8, minute=0)
        _scheduler.start()
        print("[Social Brief] Agendador ativo — toda segunda às 08h")
    except Exception as _sched_err:
        print(f"[Social Brief] Aviso: agendador não iniciado — {_sched_err}")
```

- [ ] **Step 3: Reiniciar Jake OS e verificar**

```bash
cd /root/jake_desktop
fuser -k 5050/tcp 2>/dev/null; sleep 1
nohup venv/bin/python app.py >> /tmp/jake_os.log 2>&1 &
sleep 4
grep -i "social brief\|agendador\|error\|traceback" /tmp/jake_os.log | head -10
```
Esperado: `[Social Brief] Agendador ativo — toda segunda às 08h` no log, sem tracebacks.

- [ ] **Step 4: Commit**

```bash
cd /root
git add jake_desktop/app.py
git commit -m "feat: SSE orquestrador, download HTML e APScheduler para Social Brief"
```

---

## Task 8: Frontend `social_brief.js`

**Files:**
- Create: `jake_desktop/static/js/social_brief.js`

- [ ] **Step 1: Criar `social_brief.js`**

```javascript
(function () {
  'use strict';

  var SBState = {
    clientes: [],
    ultimaGeracao: null,
    editandoId: null,
    tagsBuffer: [],
    gerando: false,
  };

  // ── Init ───────────────────────────────────────────────────────────────────

  window.initSocialBrief = function () {
    carregarClientes();
    carregarUltimaGeracao();
  };

  // ── Carregar dados ─────────────────────────────────────────────────────────

  function carregarClientes() {
    fetch('/api/social-brief/clientes')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        SBState.clientes = data.clientes || [];
        renderGrid();
      })
      .catch(function (e) { console.error('Erro carregar clientes:', e); });
  }

  function carregarUltimaGeracao() {
    fetch('/api/social-brief/ultima-geracao')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        SBState.ultimaGeracao = data.geracao || null;
        renderStatusPortal();
      });
  }

  // ── Renderização ───────────────────────────────────────────────────────────

  function renderStatusPortal() {
    var url = document.getElementById('sb-portal-url');
    var meta = document.getElementById('sb-portal-meta');
    var g = SBState.ultimaGeracao;
    if (!g) {
      if (url) url.textContent = '— não gerado ainda —';
      if (meta) meta.textContent = '';
      return;
    }
    var linkUrl = g.surge_url || '';
    if (url) {
      url.textContent = linkUrl || '— não publicado —';
      url.href = linkUrl || '#';
    }
    if (meta && g.criado_em) {
      var d = new Date(g.criado_em);
      meta.textContent = 'Gerado em ' + d.toLocaleString('pt-BR') +
        ' • Semana ' + g.semana_inicio + ' a ' + g.semana_fim;
    }
    var btnAbrir = document.getElementById('sb-btn-abrir-portal');
    if (btnAbrir) btnAbrir.style.display = linkUrl ? 'inline-block' : 'none';
  }

  function renderGrid() {
    var grid = document.getElementById('sb-clientes-grid');
    if (!grid) return;
    if (!SBState.clientes.length) {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:rgba(255,255,255,.4);padding:40px;">Nenhum cliente cadastrado. Clique em "+ Novo Cliente" para começar.</div>';
      return;
    }
    grid.innerHTML = SBState.clientes.map(function (c) {
      var concList = (c.concorrentes || []).slice(0, 3).map(function (cc) {
        return '<span class="sb-tag">' + cc + '</span>';
      }).join('');
      var campList = Object.keys(c.tipos_campanha || {}).filter(function (k) { return c.tipos_campanha[k]; }).map(function (k) {
        var icons = { mensagem: '💬', visita_perfil: '👤', lead: '📋', trafego: '🌐', conversao: '🎯' };
        return '<span class="sb-tag sb-tag-camp">' + (icons[k] || '📌') + ' ' + k + '</span>';
      }).join('');
      var metaMasked = c.meta_account_id ? c.meta_account_id.replace(/(\d{3})\d+(\d{3})/, '$1...$2') : '—';
      return '<div class="sb-card">' +
        '<div class="sb-card-header">' +
        '<div class="sb-card-status">' + (c.ativo ? '🟢' : '🔴') + '</div>' +
        '<div class="sb-card-nome">' + c.nome + '</div>' +
        '</div>' +
        '<div class="sb-card-nicho">📂 ' + (c.nicho || '—') + '</div>' +
        '<div class="sb-card-meta">📊 Meta: ' + metaMasked + '</div>' +
        '<div class="sb-tags-row">' + concList + '</div>' +
        '<div class="sb-tags-row">' + campList + '</div>' +
        '<div class="sb-card-acoes">' +
        '<button class="btn-sb-edit" onclick="sbAbrirModalCliente(' + c.id + ')">✏️ Editar</button>' +
        '<button class="btn-sb-del" onclick="sbDeletarCliente(' + c.id + ', \'' + c.nome.replace(/'/g, '') + '\')">🗑️</button>' +
        '</div>' +
        '</div>';
    }).join('');
  }

  // ── Modal cliente ──────────────────────────────────────────────────────────

  window.sbAbrirModalCliente = function (id) {
    SBState.editandoId = id || null;
    SBState.tagsBuffer = [];

    var titulo = document.getElementById('sb-modal-titulo');
    if (titulo) titulo.textContent = id ? 'Editar Cliente' : 'Novo Cliente';

    // Limpar campos
    ['sb-cli-nome', 'sb-cli-slug', 'sb-cli-nicho', 'sb-cli-meta-id'].forEach(function (fId) {
      var el = document.getElementById(fId);
      if (el) el.value = '';
    });
    ['sb-camp-mensagem', 'sb-camp-visita', 'sb-camp-lead', 'sb-camp-trafego', 'sb-camp-conversao'].forEach(function (chk) {
      var el = document.getElementById(chk);
      if (el) el.checked = false;
    });

    if (id) {
      var cliente = SBState.clientes.find(function (c) { return c.id === id; });
      if (cliente) {
        document.getElementById('sb-cli-nome').value = cliente.nome || '';
        document.getElementById('sb-cli-slug').value = cliente.slug || '';
        document.getElementById('sb-cli-nicho').value = cliente.nicho || '';
        document.getElementById('sb-cli-meta-id').value = cliente.meta_account_id || '';
        SBState.tagsBuffer = (cliente.concorrentes || []).slice();
        var tipos = cliente.tipos_campanha || {};
        if (tipos.mensagem) document.getElementById('sb-camp-mensagem').checked = true;
        if (tipos.visita_perfil) document.getElementById('sb-camp-visita').checked = true;
        if (tipos.lead) document.getElementById('sb-camp-lead').checked = true;
        if (tipos.trafego) document.getElementById('sb-camp-trafego').checked = true;
        if (tipos.conversao) document.getElementById('sb-camp-conversao').checked = true;
      }
    }
    renderTagsConcorrentes();

    var modal = document.getElementById('sb-modal-cliente');
    if (modal) modal.classList.remove('sb-hidden');
  };

  function renderTagsConcorrentes() {
    var lista = document.getElementById('sb-tags-lista');
    if (!lista) return;
    lista.innerHTML = SBState.tagsBuffer.map(function (t, i) {
      return '<span class="sb-tag sb-tag-rem">🏢 ' + t + ' <button onclick="sbRemoverTag(' + i + ')">×</button></span>';
    }).join('');
  }

  window.sbAdicionarTagConcorrente = function (event) {
    if (event.key !== 'Enter') return;
    var inp = document.getElementById('sb-tag-input');
    var val = (inp.value || '').trim();
    if (val && !SBState.tagsBuffer.includes(val)) {
      SBState.tagsBuffer.push(val);
      renderTagsConcorrentes();
    }
    inp.value = '';
    event.preventDefault();
  };

  window.sbRemoverTag = function (idx) {
    SBState.tagsBuffer.splice(idx, 1);
    renderTagsConcorrentes();
  };

  window.sbSalvarCliente = function () {
    var nome = (document.getElementById('sb-cli-nome').value || '').trim();
    var slug = (document.getElementById('sb-cli-slug').value || '').trim();
    var nicho = (document.getElementById('sb-cli-nicho').value || '').trim();
    var metaId = (document.getElementById('sb-cli-meta-id').value || '').trim();

    if (!nome || !slug) {
      alert('Nome e slug são obrigatórios.');
      return;
    }
    if (!/^[a-z0-9-]+$/.test(slug)) {
      alert('Slug deve conter apenas letras minúsculas, números e hifens.');
      return;
    }

    var tipos = {
      mensagem: document.getElementById('sb-camp-mensagem').checked,
      visita_perfil: document.getElementById('sb-camp-visita').checked,
      lead: document.getElementById('sb-camp-lead').checked,
      trafego: document.getElementById('sb-camp-trafego').checked,
      conversao: document.getElementById('sb-camp-conversao').checked,
    };

    var payload = {
      nome: nome, slug: slug, nicho: nicho,
      meta_account_id: metaId, meta_agency: 'piloti',
      concorrentes: SBState.tagsBuffer,
      tipos_campanha: tipos, ativo: true,
    };

    var url = SBState.editandoId
      ? '/api/social-brief/clientes/' + SBState.editandoId
      : '/api/social-brief/clientes';
    var method = SBState.editandoId ? 'PUT' : 'POST';

    fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          sbFecharModal('sb-modal-cliente');
          carregarClientes();
        } else {
          alert('Erro: ' + (data.error || 'desconhecido'));
        }
      });
  };

  window.sbDeletarCliente = function (id, nome) {
    if (!confirm('Deletar "' + nome + '"?')) return;
    fetch('/api/social-brief/clientes/' + id, { method: 'DELETE' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) carregarClientes();
      });
  };

  window.sbFecharModal = function (modalId) {
    var modal = document.getElementById(modalId);
    if (modal) modal.classList.add('sb-hidden');
  };

  // ── Geração do portal ──────────────────────────────────────────────────────

  window.sbGerarPortal = function () {
    if (SBState.gerando) return;
    if (!SBState.clientes.length) {
      alert('Cadastre ao menos um cliente antes de gerar o portal.');
      return;
    }
    SBState.gerando = true;

    var modal = document.getElementById('sb-modal-geracao');
    if (modal) modal.classList.remove('sb-hidden');

    // Inicializar lista de progresso
    var lista = document.getElementById('sb-prog-lista');
    if (lista) {
      lista.innerHTML = SBState.clientes.map(function (c) {
        return '<div id="sb-prog-' + c.id + '" class="sb-prog-item">⏳ <b>' + c.nome + '</b> — Aguardando</div>';
      }).join('');
    }
    document.getElementById('sb-prog-fill').style.width = '0%';
    document.getElementById('sb-prog-texto').textContent = 'Iniciando...';
    document.getElementById('sb-modal-resultado').classList.add('sb-hidden');

    var source = new EventSource('/api/social-brief/gerar');

    source.onmessage = function (event) {
      var data;
      try { data = JSON.parse(event.data); } catch (e) { return; }

      // Atualiza progresso na barra
      if (data.progresso !== undefined) {
        document.getElementById('sb-prog-fill').style.width = data.progresso + '%';
      }

      if (data.etapa) {
        document.getElementById('sb-prog-texto').textContent = data.etapa;
      }

      // Atualiza item do cliente específico
      if (data.cliente) {
        var clienteObj = SBState.clientes.find(function (c) { return c.nome === data.cliente; });
        if (clienteObj) {
          var el = document.getElementById('sb-prog-' + clienteObj.id);
          if (el) {
            if (data.status === 'concluido') {
              el.innerHTML = '✅ <b>' + data.cliente + '</b> — Concluído';
            } else {
              el.innerHTML = '🔄 <b>' + data.cliente + '</b> — ' + (data.etapa || 'Processando...');
            }
          }
        }
      }

      if (data.status === 'finalizado' || data.status === 'finalizado_sem_surge') {
        source.close();
        SBState.gerando = false;
        document.getElementById('sb-prog-texto').textContent = 'Concluído!';
        document.getElementById('sb-prog-fill').style.width = '100%';

        var resultado = document.getElementById('sb-modal-resultado');
        resultado.classList.remove('sb-hidden');

        if (data.url) {
          SBState.ultimaUrl = data.url;
          resultado.innerHTML = '<p style="color:#69f0ae;margin-bottom:12px;">✅ Portal publicado com sucesso!</p>' +
            '<a href="' + data.url + '" target="_blank" class="btn-neon" style="display:inline-block;margin-right:8px;">🔗 Abrir Portal</a>' +
            '<button onclick="sbCopiarLink(\'' + data.url + '\')" class="btn-outline">📋 Copiar link</button>';
          carregarUltimaGeracao();
        } else {
          resultado.innerHTML = '<p style="color:#ffd740;margin-bottom:12px;">⚠️ Portal gerado mas não publicado no Surge.</p>' +
            '<p style="color:#888;font-size:13px;">Erro: ' + (data.erro_surge || 'Verifique SURGE_TOKEN no .env') + '</p>';
        }
      }

      if (data.status === 'erro') {
        source.close();
        SBState.gerando = false;
        alert('Erro: ' + (data.mensagem || 'desconhecido'));
        sbFecharModal('sb-modal-geracao');
      }
    };

    source.onerror = function () {
      source.close();
      SBState.gerando = false;
      document.getElementById('sb-prog-texto').textContent = 'Erro na conexão.';
    };
  };

  window.sbCopiarLink = function (url) {
    navigator.clipboard.writeText(url).then(function () {
      alert('Link copiado!');
    });
  };

  window.sbAbrirPortal = function () {
    var g = SBState.ultimaGeracao;
    if (g && g.surge_url) window.open(g.surge_url, '_blank');
    else if (SBState.ultimaUrl) window.open(SBState.ultimaUrl, '_blank');
  };

  window.sbCopiarLinkPortal = function () {
    var g = SBState.ultimaGeracao;
    var url = (g && g.surge_url) || SBState.ultimaUrl;
    if (url) navigator.clipboard.writeText(url).then(function () { alert('Link copiado!'); });
  };

})();
```

- [ ] **Step 2: Verificar sintaxe do JS**

```bash
node --check /root/jake_desktop/static/js/social_brief.js && echo "JS OK"
```
Esperado: `JS OK` (sem erros de sintaxe)

- [ ] **Step 3: Commit**

```bash
cd /root
git add jake_desktop/static/js/social_brief.js
git commit -m "feat: frontend social_brief.js — grid de clientes, modal CRUD, SSE progresso"
```

---

## Task 9: Section no dashboard.html + nav + app.js

**Files:**
- Modify: `jake_desktop/templates/dashboard.html`
- Modify: `jake_desktop/static/js/app.js`

- [ ] **Step 1: Adicionar nav item em `dashboard.html`**

Localizar a linha com `data-page="rotina"` (nav item de Rotina) e inserir logo APÓS ela:

```html
        <a class="nav-item" data-page="social-brief" href="#">
          <span class="nav-icon">📊</span>
          <span class="nav-label">Social Brief</span>
        </a>
```

- [ ] **Step 2: Adicionar CSS da seção em `dashboard.html`**

Localizar o bloco `<style id="rotina-styles">` e adicionar logo APÓS o fechamento `</style>`:

```html
  <style id="social-brief-styles">
    .sb-page { padding: 24px; max-width: 1200px; }
    .sb-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }
    .sb-header h1 { font-family: 'Rajdhani', sans-serif; font-size: 28px; color: #00e5ff; }
    .sb-acoes { display: flex; gap: 10px; }
    .sb-status-card { background: rgba(255,255,255,.05); border: 1px solid rgba(0,229,255,.2); border-radius: 14px; padding: 16px 24px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
    .sb-status-label { color: rgba(255,255,255,.5); font-size: 13px; margin-bottom: 4px; }
    .sb-portal-link { color: #00e5ff; font-weight: 600; }
    .sb-portal-meta { font-size: 13px; color: rgba(255,255,255,.5); }
    .sb-portal-btns { display: flex; gap: 8px; align-items: center; }
    .sb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
    .sb-card { background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1); border-radius: 16px; padding: 20px; transition: border-color .2s; }
    .sb-card:hover { border-color: rgba(0,229,255,.3); }
    .sb-card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
    .sb-card-status { font-size: 16px; }
    .sb-card-nome { font-weight: 700; font-size: 16px; color: #fff; }
    .sb-card-nicho, .sb-card-meta { font-size: 13px; color: rgba(255,255,255,.5); margin-bottom: 6px; }
    .sb-tags-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
    .sb-tag { background: rgba(0,229,255,.1); color: #00e5ff; border-radius: 20px; padding: 2px 10px; font-size: 11px; }
    .sb-tag-camp { background: rgba(255,107,53,.1); color: #ff6b35; }
    .sb-tag-rem { background: rgba(255,255,255,.08); color: rgba(255,255,255,.7); display: flex; align-items: center; gap: 4px; }
    .sb-tag-rem button { background: none; border: none; color: rgba(255,255,255,.5); cursor: pointer; font-size: 14px; padding: 0; }
    .sb-card-acoes { display: flex; gap: 8px; margin-top: 12px; }
    .btn-sb-edit { background: rgba(0,229,255,.1); color: #00e5ff; border: 1px solid rgba(0,229,255,.3); border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 13px; }
    .btn-sb-edit:hover { background: rgba(0,229,255,.2); }
    .btn-sb-del { background: rgba(255,82,82,.1); color: #ff5252; border: 1px solid rgba(255,82,82,.3); border-radius: 8px; padding: 6px 10px; cursor: pointer; font-size: 13px; }
    .btn-sb-del:hover { background: rgba(255,82,82,.2); }
    /* Modal */
    .sb-hidden { display: none !important; }
    .sb-modal { position: fixed; inset: 0; background: rgba(0,0,0,.7); z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 20px; }
    .sb-modal-box { background: #0d1117; border: 1px solid rgba(0,229,255,.2); border-radius: 20px; padding: 32px; width: 100%; max-width: 540px; max-height: 90vh; overflow-y: auto; }
    .sb-modal-box h2 { font-family: 'Rajdhani', sans-serif; color: #00e5ff; font-size: 22px; margin-bottom: 20px; }
    .sb-input { width: 100%; background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.15); border-radius: 10px; padding: 10px 14px; color: #fff; font-size: 14px; margin-bottom: 12px; outline: none; }
    .sb-input:focus { border-color: #00e5ff; }
    .sb-label { color: rgba(255,255,255,.5); font-size: 12px; margin-bottom: 6px; display: block; }
    .sb-checkboxes { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
    .sb-checkboxes label { color: rgba(255,255,255,.7); font-size: 13px; display: flex; align-items: center; gap: 6px; cursor: pointer; }
    .sb-modal-acoes { display: flex; gap: 10px; margin-top: 16px; }
    /* Progresso */
    .sb-prog-item { padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,.05); font-size: 14px; color: rgba(255,255,255,.7); }
    .sb-prog-barra-wrap { margin: 16px 0 8px; }
    .sb-prog-barra { background: rgba(255,255,255,.1); border-radius: 20px; height: 8px; overflow: hidden; }
    .sb-prog-fill { height: 100%; background: linear-gradient(90deg, #00e5ff, #69f0ae); border-radius: 20px; transition: width .4s; }
    .sb-prog-texto { font-size: 13px; color: rgba(255,255,255,.5); text-align: center; }
  </style>
```

- [ ] **Step 3: Adicionar section `page-social-brief` em `dashboard.html`**

Localizar `<!-- ========== ROTINA ==========` e inserir ANTES dela:

```html
      <!-- ========== SOCIAL BRIEF ========== -->
      <section class="page" id="page-social-brief">
        <div class="sb-page">

          <!-- Header -->
          <div class="sb-header">
            <h1>📊 Social Media Brief</h1>
            <div class="sb-acoes">
              <button class="btn-neon" onclick="sbGerarPortal()">⚡ Gerar Portal</button>
              <button class="btn-outline" onclick="sbAbrirModalCliente()">+ Novo Cliente</button>
            </div>
          </div>

          <!-- Status do portal -->
          <div class="sb-status-card">
            <div>
              <div class="sb-status-label">Portal atual</div>
              <a id="sb-portal-url" href="#" target="_blank" class="sb-portal-link">— não gerado ainda —</a>
              <div id="sb-portal-meta" class="sb-portal-meta"></div>
            </div>
            <div class="sb-portal-btns">
              <button onclick="sbCopiarLinkPortal()" class="btn-sb-edit">📋 Copiar link</button>
              <button id="sb-btn-abrir-portal" onclick="sbAbrirPortal()" class="btn-neon" style="display:none;">🔗 Abrir</button>
            </div>
          </div>

          <!-- Grid de clientes -->
          <div id="sb-clientes-grid" class="sb-grid"></div>

          <!-- Modal progresso -->
          <div id="sb-modal-geracao" class="sb-modal sb-hidden">
            <div class="sb-modal-box" style="max-width:620px;">
              <h2>⚡ Gerando Portal</h2>
              <div id="sb-prog-lista"></div>
              <div class="sb-prog-barra-wrap">
                <div class="sb-prog-barra">
                  <div id="sb-prog-fill" class="sb-prog-fill" style="width:0%"></div>
                </div>
              </div>
              <div id="sb-prog-texto" class="sb-prog-texto">Iniciando...</div>
              <div id="sb-modal-resultado" class="sb-hidden" style="margin-top:20px;text-align:center;"></div>
              <div style="text-align:center;margin-top:16px;">
                <button class="btn-outline" onclick="sbFecharModal('sb-modal-geracao')">Fechar</button>
              </div>
            </div>
          </div>

          <!-- Modal cliente -->
          <div id="sb-modal-cliente" class="sb-modal sb-hidden">
            <div class="sb-modal-box">
              <h2 id="sb-modal-titulo">Novo Cliente</h2>
              <label class="sb-label">Nome do cliente *</label>
              <input id="sb-cli-nome" class="sb-input" placeholder="Ex: Academia Saucker" />
              <label class="sb-label">Slug (URL amigável) * — apenas letras minúsculas, números e hifens</label>
              <input id="sb-cli-slug" class="sb-input" placeholder="Ex: saucker" />
              <label class="sb-label">Nicho</label>
              <input id="sb-cli-nicho" class="sb-input" placeholder="Ex: academia, odontologia, estética" />
              <label class="sb-label">ID da conta Meta Ads (act_XXXXXXX)</label>
              <input id="sb-cli-meta-id" class="sb-input" placeholder="act_360347436292903" />
              <label class="sb-label">Concorrentes monitorados</label>
              <div id="sb-tags-lista" class="sb-tags-row" style="margin-bottom:8px;min-height:28px;"></div>
              <input id="sb-tag-input" class="sb-input" placeholder="Digite o nome e pressione Enter..." onkeydown="sbAdicionarTagConcorrente(event)" />
              <label class="sb-label">Tipos de campanha ativos</label>
              <div class="sb-checkboxes">
                <label><input type="checkbox" id="sb-camp-mensagem"> 💬 Mensagem</label>
                <label><input type="checkbox" id="sb-camp-visita"> 👤 Visita ao perfil</label>
                <label><input type="checkbox" id="sb-camp-lead"> 📋 Leads</label>
                <label><input type="checkbox" id="sb-camp-trafego"> 🌐 Tráfego</label>
                <label><input type="checkbox" id="sb-camp-conversao"> 🎯 Conversão</label>
              </div>
              <div class="sb-modal-acoes">
                <button class="btn-neon" onclick="sbSalvarCliente()">Salvar</button>
                <button class="btn-outline" onclick="sbFecharModal('sb-modal-cliente')">Cancelar</button>
              </div>
            </div>
          </div>

        </div>
      </section>

```

- [ ] **Step 4: Adicionar script tag + init hook em `dashboard.html`**

Localizar a linha `<script src="{{ url_for('static', filename='js/rotina.js') }}"></script>` e adicionar ANTES dela:

```html
  <script src="{{ url_for('static', filename='js/social_brief.js') }}"></script>
```

Localizar o bloco de init do rotina (script com `rotinaInit`) e adicionar dentro do mesmo `(function(){...})()`, logo após a lógica do rotina:

```javascript
      document.querySelectorAll('.nav-item').forEach(function(item){
        if(item.dataset.page === 'social-brief'){
          item.addEventListener('click', function(){
            setTimeout(function(){
              if(typeof initSocialBrief === 'function') initSocialBrief();
            }, 50);
          });
        }
      });
      if(location.hash === '#social-brief' && typeof initSocialBrief === 'function'){
        setTimeout(initSocialBrief, 300);
      }
```

**ATENÇÃO:** O bloco acima deve ser inserido dentro do `<script>` existente de init (o último `<script>` antes de `</body>`), não como um novo bloco separado. Abre o arquivo, localiza o `(function(){` do init do rotina e adiciona o código acima logo antes do `})();` final.

- [ ] **Step 5: Adicionar `"social-brief"` ao array `valid` em `app.js`**

No arquivo `jake_desktop/static/js/app.js`, linha 23, localizar:
```javascript
  var valid = ["painel","architect","performance","anuncios","copys","criativos","relatorios","carrossel","prompts","financeiro","agenda","rotina"];
```
E adicionar `"social-brief"` no final do array:
```javascript
  var valid = ["painel","architect","performance","anuncios","copys","criativos","relatorios","carrossel","prompts","financeiro","agenda","rotina","social-brief"];
```

- [ ] **Step 6: Reiniciar Jake OS e testar navegação**

```bash
cd /root/jake_desktop
fuser -k 5050/tcp 2>/dev/null; sleep 1
nohup venv/bin/python app.py >> /tmp/jake_os.log 2>&1 &
sleep 3
grep -i "error\|traceback" /tmp/jake_os.log | head -5
echo "Acessar http://localhost:5050/#social-brief e verificar:"
echo "- Nav item 'Social Brief' aparece no menu"
echo "- Section carrega sem erro JS"
echo "- Grid vazio com mensagem 'Nenhum cliente cadastrado'"
echo "- Botões '+ Novo Cliente' e '⚡ Gerar Portal' visíveis"
```

- [ ] **Step 7: Testar fluxo completo de criação de cliente**

No navegador (`http://localhost:5050/#social-brief`):
1. Clicar em "+ Novo Cliente"
2. Preencher: Nome="Saucker", Slug="saucker", Nicho="academia", Meta ID="act_360347436292903"
3. Adicionar concorrente "SmartFit", marcar "Mensagem" e "Visita ao perfil"
4. Clicar Salvar
5. Verificar que o card aparece no grid

- [ ] **Step 8: Commit**

```bash
cd /root
git add jake_desktop/templates/dashboard.html jake_desktop/static/js/app.js
git commit -m "feat: section Social Brief em dashboard.html + nav item + init hook"
```

---

## Checklist Final de Verificação

Após todos os tasks:

- [ ] Tabelas `social_brief_clientes`, `social_brief_geracoes`, `social_brief_cliente_dados` existem no Neon
- [ ] `.env` tem `SURGE_TOKEN`, `SURGE_URL`, `SOCIAL_BRIEF_LOGIN`, `SOCIAL_BRIEF_SENHA`
- [ ] `apscheduler`, `beautifulsoup4`, `duckduckgo-search` instalados no venv do Jake OS
- [ ] Hash `#social-brief` funciona no router
- [ ] CRUD de clientes funciona (criar, editar, deletar)
- [ ] Botão "Gerar Portal" abre modal com SSE progress
- [ ] Portal HTML gerado é autocontido e tem login funcional
- [ ] Surge publish funciona (requer SURGE_TOKEN válido)
- [ ] APScheduler logado como ativo no startup do Jake OS
- [ ] Nenhum traceback no log após restart
