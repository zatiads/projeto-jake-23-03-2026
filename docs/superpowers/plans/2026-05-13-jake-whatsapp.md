# Jake WhatsApp — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar o Jake ao WhatsApp via Evolution API self-hosted, com chat IA, resumo diário do Gestor às 17h, consultas financeiras e envio de mensagens para grupos.

**Architecture:** Evolution API roda em Docker na porta 8081 e repassa mensagens via webhook para `bot/jake_whatsapp.py` (Flask :5051). Handlers isolados em `bot/whatsapp_handlers.py`. APScheduler interno dispara resumo diário e mensagens agendadas para grupos. Histórico persistido no DB Neon (tabela `conversa`, namespace `whatsapp`).

**Tech Stack:** Python 3, Flask, APScheduler 3.x, Anthropic SDK, psycopg2, requests, Docker Compose.

---

## Context for Implementers

### Estrutura do projeto em /root

```
/root/
  venv/                    # virtualenv Python — usar sempre /root/venv/bin/python
  bot/
    jake_telegram.py       # Referência: padrão de bot existente (755 linhas)
    base_bot.py            # Base comum dos bots
  jake_desktop/
    app.py                 # Jake OS Flask (~7900 linhas) — NÃO modificar
  .env                     # Credenciais — NUNCA commitar
  scripts/
    subir_jake.sh          # Referência: padrão de script de startup
```

### Padrão de DB (copiar de jake_telegram.py)

```python
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

def _get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

# tabela conversa:
# chat_id BIGINT, role TEXT, content TEXT, namespace TEXT, criado_em TIMESTAMP
```

### Evolution API — endpoints relevantes

```
POST /message/sendText/{instance}
  Headers: apikey: {EVOLUTION_API_KEY}
  Body: {"number": "5511999999999@s.whatsapp.net", "text": "mensagem"}

GET /instance/connectionState/{instance}
  Headers: apikey: {EVOLUTION_API_KEY}
  Response: {"instance": {"state": "open"|"close"|"connecting"}}

PUT /webhook/set/{instance}
  Headers: apikey: {EVOLUTION_API_KEY}
  Body: {"url": "http://localhost:5051/webhook", "byEvents": false, "base64": false,
         "headers": {"x-webhook-secret": "SEU_SECRET"}, "events": ["MESSAGES_UPSERT"]}
```

### Webhook payload (Evolution API → /webhook)

```json
{
  "event": "MESSAGES_UPSERT",
  "data": {
    "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": false},
    "message": {"conversation": "texto da mensagem"}
  }
}
```
Ignorar mensagens onde `key.fromMe == true` (enviadas pelo próprio bot).

### Tabelas DB relevantes

```sql
-- Histórico de conversas (já existe)
conversa (chat_id BIGINT, role TEXT, content TEXT, namespace TEXT, criado_em TIMESTAMP)

-- Gestor IA (já existem no Jake OS)
gestor_varreduras (id, executado_em TIMESTAMP, contas_total INT, contas_ok INT,
                   contas_acao INT, contas_erro INT, duracao_seg FLOAT, status TEXT)
gestor_acoes (id, varredura_id, cliente_id, executado_em TIMESTAMP, tipo TEXT,
              entidade_nome TEXT, valor_antes TEXT, valor_depois TEXT, motivo TEXT,
              status TEXT, revertido BOOL)

-- Financeiro pessoal (já existe no Jake OS)
fin_transacoes (id, descricao TEXT, valor NUMERIC, tipo TEXT, categoria TEXT,
                recorrente BOOL, data DATE)
```

### Variáveis .env a adicionar

```bash
EVOLUTION_BASE_URL=http://localhost:8081
EVOLUTION_API_KEY=sua-api-key-aqui
WA_INSTANCE=jake
WA_AUTHORIZED_JID=5511999999999@s.whatsapp.net
EVOLUTION_WEBHOOK_SECRET=seu-secret-opcional
# WA_GRUPOS_JSON é opcional — usar config/wa_grupos.json preferencialmnte
```

### PROMPT_ANALISTA

Copiar literalmente de `/root/bot/jake_telegram.py` linhas 140-170. Não reescrever.

---

## File Structure

```
Criar:
  docker-compose.evolution.yml        # Evolution API Docker Compose
  bot/jake_whatsapp.py                # Flask :5051 + APScheduler + webhook router
  bot/whatsapp_handlers.py            # Helpers: send_text, DB, resumo, financeiro, grupos
  config/wa_grupos.json               # Config de grupos (exemplo)
  scripts/subir_jake_whatsapp.sh      # Script startup
  /etc/systemd/system/jake-whatsapp.service

Não modificar:
  bot/jake_telegram.py                # Referência apenas
  jake_desktop/app.py                 # Não tocar
```

---

## Task 1: Docker Compose — Evolution API

**Files:**
- Create: `/root/docker-compose.evolution.yml`

- [ ] **Step 1: Criar docker-compose.evolution.yml**

```yaml
version: '3.8'

services:
  evolution-api:
    image: atendai/evolution-api:latest
    container_name: evolution-api
    restart: unless-stopped
    ports:
      - "8081:8080"
    environment:
      - SERVER_URL=http://localhost:8081
      - AUTHENTICATION_TYPE=apikey
      - AUTHENTICATION_API_KEY=${EVOLUTION_API_KEY:-jake-evolution-key}
      - AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true
      - DATABASE_ENABLED=false
      - LOG_LEVEL=ERROR
      - DEL_INSTANCE=false
    volumes:
      - evolution_instances:/evolution/instances
      - evolution_store:/evolution/store

volumes:
  evolution_instances:
  evolution_store:
```

- [ ] **Step 2: Adicionar EVOLUTION_API_KEY no .env se ainda não existir**

```bash
grep -q "EVOLUTION_API_KEY" /root/.env || echo "EVOLUTION_API_KEY=jake-evolution-key" >> /root/.env
grep -q "EVOLUTION_BASE_URL" /root/.env || echo "EVOLUTION_BASE_URL=http://localhost:8081" >> /root/.env
grep -q "WA_INSTANCE" /root/.env || echo "WA_INSTANCE=jake" >> /root/.env
```

- [ ] **Step 3: Subir Evolution API**

```bash
cd /root && docker-compose -f docker-compose.evolution.yml up -d
sleep 8
docker ps | grep evolution
```

Expected: linha com `evolution-api` e status `Up`.

- [ ] **Step 4: Verificar API respondendo**

```bash
EVOLUTION_API_KEY=$(grep EVOLUTION_API_KEY /root/.env | cut -d= -f2)
curl -s -H "apikey: $EVOLUTION_API_KEY" http://localhost:8081/ | head -c 200
```

Expected: JSON com informações da API (não erro de conexão).

- [ ] **Step 5: Criar instância WhatsApp**

```bash
EVOLUTION_API_KEY=$(grep EVOLUTION_API_KEY /root/.env | cut -d= -f2)
curl -s -X POST http://localhost:8081/instance/create \
  -H "apikey: $EVOLUTION_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"instanceName":"jake","qrcode":true}' | python3 -m json.tool | head -20
```

Expected: JSON com `{"instance": {"instanceName": "jake", ...}}`. Sem erro.

- [ ] **Step 6: Commit**

```bash
cd /root
git add docker-compose.evolution.yml
git commit -m "feat(whatsapp): Evolution API Docker Compose"
```

---

## Task 2: `bot/whatsapp_handlers.py` — helpers isolados

**Files:**
- Create: `/root/bot/whatsapp_handlers.py`

- [ ] **Step 1: Criar o arquivo com todos os helpers**

```python
"""
whatsapp_handlers.py — Helpers para o bot WhatsApp do Jake.
Sem estado global — todas as funções são puras ou usam conexões efêmeras.
"""
import os
import json
import logging
from datetime import date, datetime

import requests
import psycopg2
import psycopg2.extras
import anthropic

logger = logging.getLogger(__name__)

# ── Config (lida do ambiente em tempo de chamada) ────────────────────────────

def _evo_base() -> str:
    return os.environ.get("EVOLUTION_BASE_URL", "http://localhost:8081").rstrip("/")

def _evo_key() -> str:
    return os.environ.get("EVOLUTION_API_KEY", "")

def _wa_instance() -> str:
    return os.environ.get("WA_INSTANCE", "jake")

def _db():
    url = os.environ.get("DATABASE_URL", "")
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)

# ── Envio de mensagens ────────────────────────────────────────────────────────

def send_text(jid: str, text: str) -> bool:
    """Envia mensagem de texto para um JID via Evolution API. Retorna True se OK."""
    url = f"{_evo_base()}/message/sendText/{_wa_instance()}"
    try:
        resp = requests.post(
            url,
            headers={"apikey": _evo_key(), "Content-Type": "application/json"},
            json={"number": jid, "text": text},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"send_text failed to {jid}: {e}")
        return False

# ── Histórico no DB ───────────────────────────────────────────────────────────

def jid_to_chat_id(jid: str) -> int:
    """Converte JID WhatsApp em chat_id inteiro. Ex: '5511999@s.whatsapp.net' → 5511999"""
    return int(jid.split("@")[0])

def carregar_historico(chat_id: int, limite: int = 40) -> list:
    """Retorna lista [{role, content}] do DB para namespace 'whatsapp'."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content FROM conversa "
            "WHERE chat_id=%s AND namespace='whatsapp' "
            "ORDER BY criado_em DESC LIMIT %s",
            (chat_id, limite),
        )
        rows = cur.fetchall()
        conn.close()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception as e:
        logger.error(f"carregar_historico error: {e}")
        return []

def salvar_mensagem(chat_id: int, role: str, content: str):
    """Persiste mensagem no DB com namespace 'whatsapp'."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO conversa (chat_id, role, content, namespace) VALUES (%s,%s,%s,'whatsapp')",
            (chat_id, role, content),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"salvar_mensagem error: {e}")

# ── Grupos ────────────────────────────────────────────────────────────────────

def get_grupos() -> list:
    """
    Carrega config de grupos. Tenta config/wa_grupos.json primeiro,
    depois WA_GRUPOS_JSON do .env. Retorna lista de dicts.
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "wa_grupos.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao ler wa_grupos.json: {e}")

    raw = os.environ.get("WA_GRUPOS_JSON", "[]")
    try:
        return json.loads(raw)
    except Exception:
        return []

def encontrar_grupo(nome: str) -> dict | None:
    """Busca grupo por nome (case-insensitive). Retorna dict ou None."""
    nome_lower = nome.strip().lower()
    for g in get_grupos():
        if g.get("nome", "").lower() == nome_lower:
            return g
    return None

# ── Resumo Gestor IA ──────────────────────────────────────────────────────────

def resumo_gestor() -> str:
    """
    Consulta gestor_varreduras + gestor_acoes do dia e formata resumo com emojis.
    Retorna string pronta para enviar via WhatsApp.
    """
    hoje = date.today()
    try:
        conn = _db()
        cur = conn.cursor()

        # Varreduras do dia
        cur.execute(
            """
            SELECT contas_total, contas_ok, contas_acao, contas_erro, status
            FROM gestor_varreduras
            WHERE executado_em::date = %s
            ORDER BY executado_em DESC
            LIMIT 5
            """,
            (hoje,),
        )
        varreduras = cur.fetchall()

        # Ações do dia
        cur.execute(
            """
            SELECT ga.tipo, ga.entidade_nome, acp.nome as cliente_nome, ga.status
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE ga.executado_em::date = %s
            ORDER BY ga.executado_em DESC
            LIMIT 20
            """,
            (hoje,),
        )
        acoes = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"resumo_gestor DB error: {e}")
        return "📊 Erro ao consultar o banco de dados."

    if not varreduras and not acoes:
        return "📊 Sem atividades registradas hoje."

    linhas = [f"📊 *Resumo do dia — Jake OS* ({hoje.strftime('%d/%m')})"]

    if varreduras:
        v = varreduras[0]
        linhas.append(
            f"🔍 Varredura: {v['contas_ok']}/{v['contas_total']} contas OK"
            + (f", {v['contas_acao']} ações" if v["contas_acao"] else "")
            + (f", {v['contas_erro']} erros" if v["contas_erro"] else "")
        )

    if acoes:
        sucesso = sum(1 for a in acoes if a["status"] == "sucesso")
        erro = sum(1 for a in acoes if a["status"] != "sucesso")
        linhas.append(f"✅ {sucesso} ações executadas" + (f"  ⚠️ {erro} com erro" if erro else ""))

        # Listar até 3 ações relevantes
        for a in acoes[:3]:
            linhas.append(f"  • {a['tipo']} — {a['entidade_nome']} ({a['cliente_nome']})")

    return "\n".join(linhas)

# ── Contexto financeiro ────────────────────────────────────────────────────────

def financeiro_context() -> str:
    """
    Retorna string com resumo das transações do mês atual para passar ao Claude.
    Formato: lista de transações + totais por tipo.
    """
    hoje = date.today()
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT descricao, valor, tipo, categoria, data::text
            FROM fin_transacoes
            WHERE EXTRACT(YEAR FROM data) = %s AND EXTRACT(MONTH FROM data) = %s
            ORDER BY data DESC
            """,
            (hoje.year, hoje.month),
        )
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"financeiro_context DB error: {e}")
        return "(erro ao consultar transações)"

    if not rows:
        return f"(nenhuma transação registrada em {hoje.strftime('%B/%Y')})"

    receitas = sum(r["valor"] for r in rows if r["tipo"] == "receita")
    despesas = sum(r["valor"] for r in rows if r["tipo"] == "despesa")
    saldo = receitas - despesas

    linhas = [
        f"TRANSAÇÕES DE {hoje.strftime('%B/%Y').upper()}:",
        f"Receitas: R$ {receitas:,.2f} | Despesas: R$ {despesas:,.2f} | Saldo: R$ {saldo:,.2f}",
        "",
    ]
    for r in rows[:20]:  # limitar para não explodir o contexto
        sinal = "+" if r["tipo"] == "receita" else "-"
        linhas.append(f"{r['data']} | {sinal}R${r['valor']:.2f} | {r['categoria']} | {r['descricao']}")

    return "\n".join(linhas)

# ── Verificar conexão WhatsApp ─────────────────────────────────────────────────

def verificar_conexao() -> str:
    """Retorna estado da conexão: 'open', 'close', 'connecting' ou 'unknown'."""
    try:
        resp = requests.get(
            f"{_evo_base()}/instance/connectionState/{_wa_instance()}",
            headers={"apikey": _evo_key()},
            timeout=5,
        )
        data = resp.json()
        return data.get("instance", {}).get("state", "unknown")
    except Exception as e:
        logger.error(f"verificar_conexao error: {e}")
        return "unknown"
```

- [ ] **Step 2: Verificar sintaxe**

```bash
cd /root && venv/bin/python -c "import bot.whatsapp_handlers; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Testar get_grupos com arquivo exemplo**

```bash
mkdir -p /root/config
echo '[{"nome":"Teste","jid":"120363@g.us","msg":"Oi","cron":"08:00","dias":["mon"]}]' > /root/config/wa_grupos.json
cd /root && venv/bin/python -c "
from bot.whatsapp_handlers import get_grupos, encontrar_grupo
gs = get_grupos()
print('grupos:', len(gs))
g = encontrar_grupo('Teste')
print('encontrou:', g['nome'] if g else None)
"
```

Expected:
```
grupos: 1
encontrou: Teste
```

- [ ] **Step 4: Commit**

```bash
cd /root
git add bot/whatsapp_handlers.py config/wa_grupos.json
git commit -m "feat(whatsapp): handlers — send_text, DB, resumo_gestor, financeiro, grupos"
```

---

## Task 3: `bot/jake_whatsapp.py` — servidor Flask + APScheduler

**Files:**
- Create: `/root/bot/jake_whatsapp.py`

- [ ] **Step 1: Criar o arquivo**

```python
"""
jake_whatsapp.py — Bot Jake no WhatsApp via Evolution API.
Flask :5051 recebe webhooks. APScheduler dispara crons internos.
"""
import os
import sys
import json
import time
import logging

# Garantir que /root está no path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

from flask import Flask, request, jsonify
import anthropic
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from bot.whatsapp_handlers import (
    send_text, jid_to_chat_id,
    carregar_historico, salvar_mensagem,
    get_grupos, encontrar_grupo,
    resumo_gestor, financeiro_context,
    verificar_conexao,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
AUTHORIZED_JID     = os.environ.get("WA_AUTHORIZED_JID", "").strip()
WEBHOOK_SECRET     = os.environ.get("EVOLUTION_WEBHOOK_SECRET", "").strip()
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "").strip()
SP_TZ              = pytz.timezone("America/Sao_Paulo")

# ── Prompt (copiado literalmente de bot/jake_telegram.py) ─────────────────────
PROMPT_ANALISTA = """Você é Jake — a inteligência artificial mais avançada em marketing digital do Brasil. Você é o parceiro estratégico do Bruno, gestor de tráfego com carteira de clientes em educação, saúde e serviços.

SUAS COMPETÊNCIAS (domínio absoluto):
• Tráfego pago: Meta Ads, Google Ads, TikTok Ads — estrutura, otimização, escala
• Análise de métricas: ROI, ROAS, CPA, CPL, CTR, frequência, saturação de público
• Funis de vendas: topo, meio e fundo — diagnóstico e correção
• Copywriting de alta conversão: anúncios, páginas, WhatsApp, e-mail
• Lançamentos digitais: PLs, perpétuos, eventos online, simpósios, webinários
• Estratégia de conteúdo: Instagram, YouTube, TikTok, WhatsApp
• CRO (otimização de conversão): landing pages, criativos, ofertas
• Posicionamento de marca e diferenciação competitiva
• Psicologia do consumidor e gatilhos mentais
• Gestão de agência: precificação, processos, retenção de clientes

COMO VOCÊ RESPONDE:
— Direto ao ponto. Sem enrolação, sem resposta genérica.
— Quando receber métricas, diagnóstica o problema real e dá o próximo passo concreto.
— Quando receber contexto de cliente, pensa como dono do negócio, não como executor.
— Usa dados e referências reais quando possível.
— Fala como um sócio inteligente, não como um assistente.
— Quando a pergunta for estratégica, pensa em 3 camadas: o que fazer HOJE, essa SEMANA e esse MÊS.
— NUNCA diz "depende" sem explicar de quê depende e qual a sua recomendação.
— NUNCA use a palavra 'automação'.

Sempre chame o Bruno de 'Patrão'."""

# ── Claude ────────────────────────────────────────────────────────────────────
_anthropic_client = None

def get_claude():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client

def chamar_claude(prompt_sistema: str, mensagem: str, historico: list = None) -> str:
    """Chama Claude com retry para 529 (overloaded). Retorna texto da resposta."""
    messages = list(historico or []) + [{"role": "user", "content": mensagem}]
    for attempt in range(3):
        try:
            resp = get_claude().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=prompt_sistema,
                messages=messages,
            )
            return resp.content[0].text
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    return "Deu ruim no cérebro, Patrão. Tenta de novo daqui a pouco."

# ── Roteamento de intenção ─────────────────────────────────────────────────────

_KEYWORDS_FINANCEIRO = [
    "gastei", "gasto", "receita", "despesa", "saldo", "financeiro",
    "dinheiro", "transação", "quanto entrou", "quanto saiu", "mês",
]

_KEYWORDS_GRUPO = ["manda", "envia", "grupo", "bom dia", "boa semana", "boa tarde", "boa noite"]

def _eh_financeiro(texto: str) -> bool:
    t = texto.lower()
    return any(k in t for k in _KEYWORDS_FINANCEIRO)

def _eh_grupo(texto: str) -> bool:
    t = texto.lower()
    return sum(1 for k in _KEYWORDS_GRUPO if k in t) >= 2

# ── Handler de mensagem ────────────────────────────────────────────────────────

def processar_mensagem(sender_jid: str, texto: str):
    """Processa mensagem do Bruno e envia resposta."""
    chat_id = jid_to_chat_id(sender_jid)
    historico = carregar_historico(chat_id)

    # Intenção: enviar para grupo
    if _eh_grupo(texto):
        # Tentar identificar nome do grupo no texto
        grupos = get_grupos()
        grupo_encontrado = None
        for g in grupos:
            if g["nome"].lower() in texto.lower():
                grupo_encontrado = g
                break

        if grupo_encontrado:
            ok = send_text(grupo_encontrado["jid"], grupo_encontrado["msg"])
            resposta = (
                f"✅ Mensagem enviada para o grupo {grupo_encontrado['nome']}, Patrão!"
                if ok else
                f"❌ Falha ao enviar para {grupo_encontrado['nome']}. Evolution API offline?"
            )
            send_text(sender_jid, resposta)
            salvar_mensagem(chat_id, "user", texto)
            salvar_mensagem(chat_id, "assistant", resposta)
            return
        else:
            # Deixa Claude responder que não encontrou
            pass

    # Intenção: financeiro — injeta contexto no prompt
    prompt = PROMPT_ANALISTA
    mensagem_claude = texto
    if _eh_financeiro(texto):
        ctx = financeiro_context()
        mensagem_claude = f"DADOS FINANCEIROS DO SISTEMA:\n{ctx}\n\nPERGUNTA DO PATRÃO: {texto}"

    resposta = chamar_claude(prompt, mensagem_claude, historico)

    # Verificar se Claude quer enviar para grupo (fallback textual)
    if _eh_grupo(texto) and "não está configurado" not in resposta.lower():
        # Tenta extrair nome de grupo da resposta ou do texto original
        grupos = get_grupos()
        for g in grupos:
            if g["nome"].lower() in texto.lower():
                send_text(g["jid"], g["msg"])
                break
        else:
            resposta = "Patrão, esse grupo não tá configurado ainda. Adiciona no config/wa_grupos.json."

    salvar_mensagem(chat_id, "user", texto)
    salvar_mensagem(chat_id, "assistant", resposta)
    send_text(sender_jid, resposta)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    # Verificar secret se configurado
    if WEBHOOK_SECRET:
        incoming = request.headers.get("x-webhook-secret", "")
        if incoming != WEBHOOK_SECRET:
            return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}

    # Apenas processar MESSAGES_UPSERT
    if data.get("event") != "MESSAGES_UPSERT":
        return jsonify({"ok": True})

    msg_data = data.get("data", {})
    key = msg_data.get("key", {})

    # Ignorar mensagens enviadas pelo próprio bot
    if key.get("fromMe"):
        return jsonify({"ok": True})

    sender_jid = key.get("remoteJid", "")

    # Apenas responder ao usuário autorizado
    if sender_jid != AUTHORIZED_JID:
        return jsonify({"ok": True})

    message = msg_data.get("message", {})
    texto = (
        message.get("conversation")
        or message.get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()

    if not texto:
        return jsonify({"ok": True})

    # Processar em background para não bloquear o webhook
    import threading
    threading.Thread(target=processar_mensagem, args=(sender_jid, texto), daemon=True).start()

    return jsonify({"ok": True})

@app.route("/health")
def health():
    return jsonify({"ok": True, "wa_status": verificar_conexao()})

# ── APScheduler — crons ───────────────────────────────────────────────────────

def _enviar_resumo_gestor():
    """Cron das 17h: envia resumo do Gestor IA para o Bruno."""
    if not AUTHORIZED_JID:
        logger.warning("WA_AUTHORIZED_JID não configurado — resumo não enviado")
        return
    logger.info("Enviando resumo diário do Gestor IA...")
    resumo = resumo_gestor()
    send_text(AUTHORIZED_JID, resumo)

def _enviar_mensagem_grupo(grupo: dict):
    """Cron agendado: envia mensagem para um grupo configurado."""
    logger.info(f"Enviando mensagem agendada para grupo {grupo['nome']}")
    send_text(grupo["jid"], grupo["msg"])

def _configurar_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=SP_TZ)

    # Resumo Gestor às 17h todos os dias
    scheduler.add_job(
        _enviar_resumo_gestor,
        CronTrigger(hour=17, minute=0, timezone=SP_TZ),
        id="resumo_gestor",
        replace_existing=True,
    )

    # Mensagens agendadas para grupos
    grupos = get_grupos()
    DIAS_MAP = {
        "mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu",
        "fri": "fri", "sat": "sat", "sun": "sun",
    }
    for i, grupo in enumerate(grupos):
        cron_time = grupo.get("cron", "")
        dias = grupo.get("dias", [])
        if not cron_time or not dias:
            continue
        try:
            hora, minuto = cron_time.split(":")
            dia_semana = ",".join(DIAS_MAP.get(d, d) for d in dias)
            scheduler.add_job(
                _enviar_mensagem_grupo,
                CronTrigger(day_of_week=dia_semana, hour=int(hora), minute=int(minuto), timezone=SP_TZ),
                args=[grupo],
                id=f"grupo_{i}_{grupo['nome']}",
                replace_existing=True,
            )
            logger.info(f"Agendado: grupo '{grupo['nome']}' às {cron_time} nos dias {dias}")
        except Exception as e:
            logger.error(f"Erro ao agendar grupo {grupo.get('nome')}: {e}")

    return scheduler

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY não configurada — encerrando")
        sys.exit(1)

    # Verificar conexão WhatsApp
    estado = verificar_conexao()
    if estado == "open":
        logger.info("✅ WhatsApp conectado")
    elif estado == "close":
        logger.warning("⚠️  WhatsApp desconectado. Reconecte via QR em http://localhost:8081")
    else:
        logger.warning(f"WhatsApp status: {estado} (Evolution API pode estar inicializando)")

    # Iniciar scheduler
    scheduler = _configurar_scheduler()
    scheduler.start()
    logger.info(f"APScheduler iniciado com {len(scheduler.get_jobs())} job(s)")

    # Iniciar Flask
    logger.info("Jake WhatsApp iniciando na porta 5051...")
    app.run(host="0.0.0.0", port=5051, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Instalar APScheduler e pytz**

```bash
/root/venv/bin/pip install apscheduler pytz -q
```

Expected: sem erros, pacotes instalados.

- [ ] **Step 3: Verificar sintaxe**

```bash
cd /root && venv/bin/python -c "import bot.jake_whatsapp; print('OK')"
```

Expected: `OK` (sem erros de import)

- [ ] **Step 4: Testar endpoint /health em background**

```bash
cd /root
PYTHONPATH=/root venv/bin/python bot/jake_whatsapp.py &
BOT_PID=$!
sleep 4
curl -s http://localhost:5051/health | python3 -m json.tool
kill $BOT_PID 2>/dev/null
```

Expected:
```json
{"ok": true, "wa_status": "close"}
```
(ou `"open"` se WhatsApp já conectado)

- [ ] **Step 5: Testar webhook com payload simulado**

```bash
cd /root
PYTHONPATH=/root venv/bin/python bot/jake_whatsapp.py &
BOT_PID=$!
sleep 3

# Mensagem de sender não autorizado — deve ser ignorada
curl -s -X POST http://localhost:5051/webhook \
  -H "Content-Type: application/json" \
  -d '{"event":"MESSAGES_UPSERT","data":{"key":{"remoteJid":"9999@s.whatsapp.net","fromMe":false},"message":{"conversation":"oi"}}}' \
  | python3 -m json.tool

kill $BOT_PID 2>/dev/null
```

Expected: `{"ok": true}` sem erros no log do bot.

- [ ] **Step 6: Commit**

```bash
cd /root
git add bot/jake_whatsapp.py
git commit -m "feat(whatsapp): bot Flask + APScheduler + webhook handler"
```

---

## Task 4: Scripts de startup + systemd

**Files:**
- Create: `/root/scripts/subir_jake_whatsapp.sh`
- Create: `/etc/systemd/system/jake-whatsapp.service`

- [ ] **Step 1: Criar script de startup**

```bash
cat > /root/scripts/subir_jake_whatsapp.sh << 'EOF'
#!/bin/bash
# Sobe o Jake WhatsApp bot na porta 5051.
cd /root
mkdir -p /root/logs

pkill -f "jake_whatsapp.py" 2>/dev/null; sleep 2

PYTHONPATH=/root nohup /root/venv/bin/python3 /root/bot/jake_whatsapp.py \
  >> /root/logs/jake_whatsapp.log 2>&1 &

echo "Jake WhatsApp iniciado. PID: $!"
echo "Log: tail -f /root/logs/jake_whatsapp.log"
EOF
chmod +x /root/scripts/subir_jake_whatsapp.sh
```

- [ ] **Step 2: Criar systemd service**

```bash
cat > /etc/systemd/system/jake-whatsapp.service << 'EOF'
[Unit]
Description=Jake WhatsApp Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root
Environment=PYTHONPATH=/root
ExecStart=/root/venv/bin/python /root/bot/jake_whatsapp.py
Restart=always
RestartSec=5
StandardOutput=append:/root/logs/jake_whatsapp.log
StandardError=append:/root/logs/jake_whatsapp.log

[Install]
WantedBy=multi-user.target
EOF
```

- [ ] **Step 3: Habilitar e iniciar serviço**

```bash
mkdir -p /root/logs
systemctl daemon-reload
systemctl enable jake-whatsapp
systemctl start jake-whatsapp
sleep 3
systemctl is-active jake-whatsapp
```

Expected: `active`

- [ ] **Step 4: Verificar health via systemd**

```bash
curl -s http://localhost:5051/health | python3 -m json.tool
```

Expected: `{"ok": true, ...}`

- [ ] **Step 5: Commit**

```bash
cd /root
git add scripts/subir_jake_whatsapp.sh
git commit -m "feat(whatsapp): script startup + systemd service"
```

---

## Task 5: Configurar webhook na Evolution API + conectar WhatsApp

**Files:** nenhum (configuração via API)

- [ ] **Step 0: Garantir variáveis no .env antes de continuar**

```bash
grep -q "EVOLUTION_WEBHOOK_SECRET" /root/.env || echo "EVOLUTION_WEBHOOK_SECRET=jake-webhook-secret" >> /root/.env
grep -q "WA_AUTHORIZED_JID" /root/.env || echo "WA_AUTHORIZED_JID=" >> /root/.env
```

- [ ] **Step 1: Configurar webhook na instância**

```bash
EVOLUTION_API_KEY=$(grep EVOLUTION_API_KEY /root/.env | cut -d= -f2 | tr -d '"')
WA_INSTANCE=$(grep WA_INSTANCE /root/.env | cut -d= -f2 | tr -d '"')
WEBHOOK_SECRET=$(grep EVOLUTION_WEBHOOK_SECRET /root/.env | cut -d= -f2 | tr -d '"')

curl -s -X PUT "http://localhost:8081/webhook/set/$WA_INSTANCE" \
  -H "apikey: $EVOLUTION_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"url\": \"http://localhost:5051/webhook\",
    \"byEvents\": false,
    \"base64\": false,
    \"headers\": {\"x-webhook-secret\": \"$WEBHOOK_SECRET\"},
    \"events\": [\"MESSAGES_UPSERT\"]
  }" | python3 -m json.tool
```

Expected: JSON com confirmação, sem erro.

- [ ] **Step 2: Obter QR code para conectar WhatsApp**

```bash
EVOLUTION_API_KEY=$(grep EVOLUTION_API_KEY /root/.env | cut -d= -f2 | tr -d '"')
WA_INSTANCE=$(grep WA_INSTANCE /root/.env | cut -d= -f2 | tr -d '"')

curl -s "http://localhost:8081/instance/connect/$WA_INSTANCE" \
  -H "apikey: $EVOLUTION_API_KEY" | python3 -m json.tool | head -5
```

Acesse `http://SEU_IP_VPS:8081` no browser para escanear o QR code com o WhatsApp do número dedicado do Jake.

> **Importante:** Porta 8081 precisa estar liberada temporariamente no firewall para acessar o dashboard. Após conectar, pode fechar novamente.

```bash
# Liberar temporariamente (reverter após scan)
ufw allow 8081/tcp 2>/dev/null || true
```

- [ ] **Step 3: Verificar conexão após scan do QR**

```bash
sleep 10
curl -s http://localhost:5051/health | python3 -m json.tool
```

Expected: `{"ok": true, "wa_status": "open"}`

- [ ] **Step 4: Adicionar WA_AUTHORIZED_JID no .env**

Descubra seu JID:
```bash
# O JID é: DDDnúmero@s.whatsapp.net
# Ex: 5511999998888@s.whatsapp.net
# Adicionar no .env:
echo "WA_AUTHORIZED_JID=55XXXXXXXXXXX@s.whatsapp.net" >> /root/.env
```

- [ ] **Step 5: Reiniciar bot para carregar o JID**

```bash
systemctl restart jake-whatsapp
sleep 3
systemctl is-active jake-whatsapp
```

- [ ] **Step 6: Teste end-to-end**

Envie uma mensagem do WhatsApp do Bruno para o número do Jake. Verifique no log:

```bash
tail -f /root/logs/jake_whatsapp.log
```

Expected: linhas mostrando recebimento do webhook e envio de resposta.

- [ ] **Step 7: Fechar porta 8081 no firewall**

```bash
ufw delete allow 8081/tcp 2>/dev/null || true
```

- [ ] **Step 8: Commit final**

```bash
cd /root
git log --oneline -6
```

Verificar que todos os commits do whatsapp estão presentes.
