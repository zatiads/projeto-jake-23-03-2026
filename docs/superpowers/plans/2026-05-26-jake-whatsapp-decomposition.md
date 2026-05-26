# Jake WhatsApp Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompor `bot/jake_whatsapp.py` (2319 linhas) extraindo crons para `wa_crons.py` e lógica de grupos para `wa_grupos/`, sem mudar comportamento externo.

**Architecture:** Extração mínima (Opção A). `jake_whatsapp.py` mantém Flask, webhook e processamento de IA. `wa_crons.py` assume todos os jobs APScheduler. `wa_grupos/casa.py` e `wa_grupos/viagem_chile.py` encapsulam lógica por grupo. Injeção de `processar_fn` como parâmetro evita import circular.

**Tech Stack:** Python 3, Flask, APScheduler, anthropic SDK, psycopg2, pytz

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `bot/wa_grupos/__init__.py` | Criar | Re-exporta JIDs e handlers para o webhook |
| `bot/wa_grupos/casa.py` | Criar | `CASA_GROUP_JID` + `handle_mensagem_casa` |
| `bot/wa_grupos/viagem_chile.py` | Criar | `VIAGEM_GROUP_JID` + `handle_mensagem_viagem` (placeholder) |
| `bot/wa_crons.py` | Criar | Todos os jobs APScheduler + `configurar_scheduler` |
| `bot/jake_whatsapp.py` | Modificar | Remove crons e handlers inline; importa dos novos módulos |

---

## Task 1: Criar `bot/wa_grupos/casa.py`

**Files:**
- Create: `bot/wa_grupos/__init__.py` (arquivo vazio por ora)
- Create: `bot/wa_grupos/casa.py`

- [ ] **Step 1: Criar o diretório e `__init__.py` vazio**

```bash
mkdir -p /root/bot/wa_grupos
touch /root/bot/wa_grupos/__init__.py
```

- [ ] **Step 2: Criar `bot/wa_grupos/casa.py`**

Extrair do webhook (linhas 1708-1748 de `jake_whatsapp.py`):

```python
"""
wa_grupos/casa.py — Lógica específica do grupo Casa.
"""
import os
import logging
import re
import threading

logger = logging.getLogger(__name__)

CASA_GROUP_JID = "120363310359411409@g.us"


def handle_mensagem_casa(texto: str, key: dict, processar_fn=None) -> bool:
    """
    Processa mensagem recebida no grupo Casa.

    - Se menciona 'jake': chama processar_fn(CASA_GROUP_JID, texto_limpo) em thread.
    - Caso contrário: salva item na tabela lista_compras.

    Retorna True se processou, False se ignorou (texto vazio).
    """
    from bot.whatsapp_handlers import send_text

    texto = texto.strip()
    if not texto:
        return False

    if "jake" in texto.lower():
        texto_cmd = re.sub(r"(?i)^@?jake\s*(ia)?\s*[,:]?\s*", "", texto).strip()
        if not texto_cmd:
            texto_cmd = texto
        logger.info(f"Mencao ao Jake no grupo Casa: {texto_cmd!r}")
        if processar_fn:
            def _run():
                try:
                    processar_fn(CASA_GROUP_JID, texto_cmd)
                except Exception as e:
                    logger.error(f"Erro ao processar mencao grupo Casa: {e}", exc_info=True)
            threading.Thread(target=_run, daemon=True).start()
        return True

    # Salvar na lista de compras
    remetente = key.get("participant", key.get("remoteJid", ""))
    try:
        import psycopg2
        conn = psycopg2.connect(os.environ.get("DATABASE_URL", ""))
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO lista_compras (item, adicionado_por) VALUES (%s, %s)",
            (texto, remetente)
        )
        conn.commit()
        conn.close()
        logger.info(f"Item adicionado na lista: {texto!r} por {remetente}")
    except Exception as e:
        logger.error(f"Erro ao salvar item lista_compras: {e}")

    return True
```

- [ ] **Step 3: Verificar que o módulo importa sem erro**

```bash
cd /root && python3 -c "from bot.wa_grupos.casa import CASA_GROUP_JID, handle_mensagem_casa; print('OK', CASA_GROUP_JID)"
```

Expected: `OK 120363310359411409@g.us`

- [ ] **Step 4: Commit**

```bash
cd /root
git add bot/wa_grupos/__init__.py bot/wa_grupos/casa.py
git commit -m "feat(whatsapp): extrai logica do grupo Casa para wa_grupos/casa.py"
```

---

## Task 2: Criar `bot/wa_grupos/viagem_chile.py` e atualizar `__init__.py`

**Files:**
- Create: `bot/wa_grupos/viagem_chile.py`
- Modify: `bot/wa_grupos/__init__.py`

- [ ] **Step 1: Criar `bot/wa_grupos/viagem_chile.py`**

```python
"""
wa_grupos/viagem_chile.py — Lógica específica do grupo Viagem Chile.
[NOVO] Este arquivo não existia antes — adiciona roteamento novo ao webhook.
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)

VIAGEM_GROUP_JID = "120363403675290579@g.us"
VIAGEM_DATA = date(2026, 8, 9)


def handle_mensagem_viagem(texto: str, key: dict, processar_fn=None) -> bool:
    """
    Processa mensagem recebida no grupo Viagem Chile.
    Por ora retorna False (placeholder para lógica futura).
    """
    return False
```

- [ ] **Step 2: Atualizar `bot/wa_grupos/__init__.py`**

```python
from .casa import CASA_GROUP_JID, handle_mensagem_casa
from .viagem_chile import VIAGEM_GROUP_JID, handle_mensagem_viagem

__all__ = [
    "CASA_GROUP_JID", "handle_mensagem_casa",
    "VIAGEM_GROUP_JID", "handle_mensagem_viagem",
]
```

- [ ] **Step 3: Verificar importação do pacote completo**

```bash
cd /root && python3 -c "
from bot.wa_grupos import (
    CASA_GROUP_JID, handle_mensagem_casa,
    VIAGEM_GROUP_JID, handle_mensagem_viagem,
)
print('Casa JID:', CASA_GROUP_JID)
print('Viagem JID:', VIAGEM_GROUP_JID)
print('OK')
"
```

Expected: ambos JIDs impressos, `OK`.

- [ ] **Step 4: Commit**

```bash
cd /root
git add bot/wa_grupos/viagem_chile.py bot/wa_grupos/__init__.py
git commit -m "feat(whatsapp): adiciona wa_grupos/viagem_chile.py e init do pacote"
```

---

## Task 3: Criar `bot/wa_crons.py`

Extrair de `jake_whatsapp.py` as funções:
- `_rotina_segunda` (linhas 1300–1413)
- `_enviar_resumo_gestor` (linhas 1807–1815)
- `_enviar_mensagem_grupo` (linhas 1817–1820)
- `_limpar_tmp_midia` (linhas 1850–1863)
- `_expirar_pendentes` (linhas 1866–1892)
- `_alerta_saldo_baixo` (linhas 1895–1993)
- `_rotina_sexta` (linhas 1996–2036)
- `_rotina_quarta` (linhas 2039–2099)
- `_noticias_diarias` (linhas 2102–2168)
- `_configurar_scheduler` → `configurar_scheduler` (linhas 2171–2291)
- `_auto_import_recorrentes` — promover de nested para top-level (estava dentro de `_configurar_scheduler` nas linhas 2200–2207)

**Files:**
- Create: `bot/wa_crons.py`

- [ ] **Step 1: Criar `bot/wa_crons.py`**

```python
"""
wa_crons.py — Todos os jobs APScheduler do Jake WhatsApp.
Chamado por jake_whatsapp.py: configurar_scheduler() no main().
"""
import os
import logging
import time as _time

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.whatsapp_handlers import send_text, get_grupos

logger = logging.getLogger(__name__)

AUTHORIZED_NUMBER = os.environ.get("WA_AUTHORIZED_NUMBER", "").strip()
AUTHORIZED_JID    = os.environ.get("WA_AUTHORIZED_JID", "").strip()
SP_TZ             = pytz.timezone("America/Sao_Paulo")


# ── Helper interno ─────────────────────────────────────────────────────────────

def _chamar_claude(prompt_sistema: str, mensagem: str) -> str:
    """Chamada simples ao Claude — uso exclusivo dos crons."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=prompt_sistema,
        messages=[{"role": "user", "content": mensagem}],
    )
    return resp.content[0].text.strip()


# ── Cron jobs ──────────────────────────────────────────────────────────────────

def _rotina_segunda():
    """Toda segunda às 7h30: briefing semanal Meta + notícias IA + financeiro."""
    if not AUTHORIZED_NUMBER:
        return

    import urllib.request
    import xml.etree.ElementTree as ET

    destino = AUTHORIZED_NUMBER

    # 1. Performance Meta da semana anterior
    try:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"],
                                cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute("""
            SELECT acp.nome, ga.tipo, COUNT(*) as n
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE ga.executado_em >= NOW() - INTERVAL '7 days'
              AND ga.status = 'sucesso'
              AND ga.tipo NOT LIKE 'alerta%%'
            GROUP BY acp.nome, ga.tipo
            ORDER BY acp.nome
        """)
        acoes_semana = cur.fetchall()

        cur.execute("""
            SELECT contas_total, contas_ok, contas_acao, contas_erro
            FROM gestor_varreduras
            WHERE executado_em >= NOW() - INTERVAL '7 days'
              AND status = 'sucesso'
            ORDER BY executado_em DESC LIMIT 1
        """)
        ultima_varredura = cur.fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"_rotina_segunda: erro ao buscar Meta: {e}")
        acoes_semana = []
        ultima_varredura = None

    linhas_meta = ["*Resumo Meta — semana anterior:*"]
    if ultima_varredura:
        linhas_meta.append(
            f"{ultima_varredura['contas_ok']}/{ultima_varredura['contas_total']} contas OK | "
            f"{ultima_varredura['contas_acao']} acoes tomadas"
        )
    if acoes_semana:
        por_cliente: dict = {}
        for a in acoes_semana:
            por_cliente.setdefault(a["nome"], []).append(f"{a['tipo']}({a['n']})")
        for nome, tipos in list(por_cliente.items())[:5]:
            linhas_meta.append(f"  • {nome}: {', '.join(tipos)}")
    else:
        linhas_meta.append("Nenhuma acao executada na semana.")

    # 2. Notícias de IA (RSS)
    noticias = []
    feeds = [
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "https://www.artificialintelligence-news.com/feed/",
    ]
    for feed_url in feeds:
        try:
            req = urllib.request.Request(feed_url, headers={"User-Agent": "Jake-IA/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall(".//item")[:3]:
                titulo = item.findtext("title", "").strip()
                if titulo:
                    noticias.append(titulo)
        except Exception:
            pass
        if len(noticias) >= 5:
            break

    if noticias:
        prompt_noticias = (
            "Você é Jake, assistente de tráfego pago do Bruno.\n"
            "Filtre e resuma em 3-4 frases curtas (português) as notícias de IA abaixo "
            "focando no que é relevante para um gestor de tráfego Meta Ads:\n\n"
            + "\n".join(f"- {n}" for n in noticias)
        )
        try:
            resumo_ia = _chamar_claude(prompt_noticias, "Resumo para gestor de tráfego:")
        except Exception:
            resumo_ia = "\n".join(f"• {n}" for n in noticias[:3])
    else:
        resumo_ia = "Nao consegui buscar noticias desta semana."

    # 3. Financeiro
    try:
        from bot.whatsapp_handlers import resumo_financeiro_wa
        fin_linha = resumo_financeiro_wa()
    except Exception as e:
        fin_linha = f"(erro ao carregar financeiro: {e})"

    from datetime import date as _date
    hoje = _date.today().strftime("%d/%m")
    msg = (
        f"Bom dia, Patrao! Segunda-feira {hoje} — aqui esta o seu briefing:\n\n"
        + "\n".join(linhas_meta)
        + f"\n\n*IA & Trafego — novidades:*\n{resumo_ia}"
        + f"\n\n{fin_linha}"
        + "\n\nBoa semana!"
    )
    send_text(destino, msg)
    logger.info("_rotina_segunda: briefing enviado")


def _noticias_diarias():
    """Todo dia às 7h35: resumo de IA & Marketing via RSS."""
    if not AUTHORIZED_NUMBER:
        return
    try:
        import urllib.request
        import xml.etree.ElementTree as ET
        from datetime import date as _date

        feeds = [
            "https://techcrunch.com/tag/artificial-intelligence/feed/",
            "https://feeds.feedburner.com/socialmediaexaminer",
            "https://www.searchenginejournal.com/feed/",
            "https://www.jonloomer.com/feed/",
            "https://www.artificialintelligence-news.com/feed/",
        ]

        noticias = []
        for feed_url in feeds:
            try:
                req = urllib.request.Request(feed_url, headers={"User-Agent": "Jake-IA/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    xml_data = resp.read()
                root = ET.fromstring(xml_data)
                for item in root.findall(".//item")[:3]:
                    titulo = item.findtext("title", "").strip()
                    if titulo:
                        noticias.append(titulo)
            except Exception:
                pass
            if len(noticias) >= 8:
                break

        hoje = _date.today()
        dias = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
        dia_semana = dias[hoje.weekday()]

        if noticias:
            prompt = (
                f"Você é Jake, assistente do Bruno — gestor de tráfego Meta Ads.\n"
                f"Hoje é {dia_semana}, {hoje.strftime('%d/%m/%Y')}.\n"
                "Com base nas notícias abaixo, selecione as 3 mais relevantes para quem "
                "gerencia campanhas Meta Ads e agências de marketing digital no Brasil. "
                "Para cada uma escreva: título adaptado ao contexto + 1 frase de impacto prático. "
                "Formato: bullet point. Tom direto, sem enrolação, português.\n\n"
                "Notícias disponíveis:\n"
                + "\n".join(f"- {n}" for n in noticias)
            )
            try:
                resumo = _chamar_claude(prompt, "Resumo IA & Marketing:")
            except Exception:
                resumo = "\n".join(f"• {n}" for n in noticias[:3])
        else:
            resumo = "Não consegui acessar os feeds hoje. Tente verificar manualmente."

        msg = (
            f"*IA & Marketing — {dia_semana} {hoje.strftime('%d/%m')}*\n\n"
            f"{resumo}"
        )
        send_text(AUTHORIZED_NUMBER, msg)
        logger.info("_noticias_diarias: resumo enviado")
    except Exception as e:
        logger.error(f"_noticias_diarias error: {e}")


def _rotina_quarta():
    """Toda quarta às 7h30: check de meio de semana."""
    if not AUTHORIZED_NUMBER:
        return
    try:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"],
                                cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute("""
            SELECT acp.nome, ga.tipo, ga.motivo, ga.status
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE ga.executado_em >= NOW() - INTERVAL '3 days'
              AND ga.tipo LIKE 'alerta%%'
            ORDER BY ga.executado_em DESC
            LIMIT 10
        """)
        alertas = cur.fetchall()
        cur.execute("""
            SELECT MAX(executado_em) as ultima FROM gestor_varreduras
            WHERE status = 'sucesso'
        """)
        ultima_var = cur.fetchone()
        conn.close()

        from datetime import date as _date
        hoje = _date.today()
        linhas = [f"*Check de quarta — {hoje.strftime('%d/%m')}*\n"]

        if ultima_var and ultima_var["ultima"]:
            dias_sem = (hoje - ultima_var["ultima"].date()).days
            if dias_sem > 1:
                linhas.append(f"Gestor sem varredura ha {dias_sem} dias — verificar cron.")
            else:
                linhas.append("Gestor IA: varredura em dia.")
        else:
            linhas.append("Gestor IA: sem varreduras recentes.")

        if alertas:
            linhas.append(f"\nAlertas dos ultimos 3 dias ({len(alertas)}):")
            por_conta: dict = {}
            for a in alertas:
                por_conta.setdefault(a["nome"], []).append(a["motivo"].split(":")[0])
            for nome, tipos in list(por_conta.items())[:6]:
                linhas.append(f"  • {nome}: {', '.join(set(tipos))}")
        else:
            linhas.append("\nNenhum alerta nos ultimos 3 dias. Tudo tranquilo.")

        linhas.append("\nSe precisar de ajuste em alguma conta antes do fim de semana, e so mandar.")
        send_text(AUTHORIZED_NUMBER, "\n".join(linhas))
        logger.info("_rotina_quarta: check enviado")
    except Exception as e:
        logger.error(f"_rotina_quarta error: {e}")


def _rotina_sexta():
    """Toda sexta às 17h: relatório financeiro vs meta R$1M."""
    if not AUTHORIZED_NUMBER:
        return
    try:
        from core.sync_financeiro import resumo_mes
        from datetime import date as _date
        r = resumo_mes()
        hoje = _date.today()
        dia = hoje.day
        proj_mensal = (r["receitas"] / dia * 30) if dia > 0 else r["receitas"]
        proj_anual  = proj_mensal * 12
        meta_anual  = 1_000_000.0
        pct         = proj_anual / meta_anual * 100
        bar_filled  = int(pct / 10)
        bar         = "X" * bar_filled + "." * (10 - bar_filled)

        msg = (
            f"*Relatorio Financeiro — {hoje.strftime('%d/%m/%Y')}*\n\n"
            f"Receitas {hoje.strftime('%b')}: R${r['receitas']:,.2f}\n"
            f"Despesas {hoje.strftime('%b')}: R${r['despesas']:,.2f}\n"
            f"Saldo {hoje.strftime('%b')}:    R${r['saldo']:,.2f}\n\n"
            f"Projecao anual: R${proj_anual:,.0f}\n"
            f"Meta R$1M:      [{bar}] {pct:.1f}%\n\n"
        )
        if pct >= 100:
            msg += "Meta atingida, Patrao!"
        elif pct >= 70:
            msg += "No caminho certo. Segura o ritmo!"
        elif pct >= 40:
            msg += "Metade do caminho. Vamos acelerar?"
        else:
            msg += "Abaixo da meta. Hora de revisar as entradas."

        send_text(AUTHORIZED_NUMBER, msg)
        logger.info("_rotina_sexta: relatorio financeiro enviado")
    except Exception as e:
        logger.error(f"_rotina_sexta error: {e}")


def _alerta_saldo_baixo():
    """Todo dia às 8h: verifica saldo das contas Meta."""
    if not AUTHORIZED_NUMBER:
        return
    try:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"],
                                cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute("""
            SELECT nome, account_id, token_key, agencia FROM ad_client_profiles
            WHERE gestor_ativo = TRUE
        """)
        contas = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"_alerta_saldo_baixo: erro ao buscar contas: {e}")
        return

    try:
        from meta.meta_api import _resolve_token
    except Exception:
        _resolve_token = lambda k: os.getenv(k, "")

    import requests as _req

    LIMITES = {
        "Calixta Films":  100.0,
        "Amanda Cunha":    50.0,
        "Marcos Couto":    50.0,
    }
    LIMITE_PADRAO = 300.0
    CARTAO = {"Maíra Castaldi", "RD Contabilidade"}

    alertas_piloti = []
    alertas_dentto = []

    for conta in contas:
        try:
            token = _resolve_token(conta["token_key"])
        except Exception:
            token = os.getenv(conta["token_key"], "")
        if not token:
            continue
        try:
            resp = _req.get(
                f"https://graph.facebook.com/v21.0/{conta['account_id']}",
                params={"fields": "amount_spent,spend_cap,balance,account_status", "access_token": token},
                timeout=10,
            )
            data = resp.json()
            nome    = conta["nome"]
            agencia = (conta.get("agencia") or "piloti").lower()
            status  = int(data.get("account_status", 1))

            if nome in CARTAO:
                if status in (2, 3, 9):
                    linha = f"  • {nome}: Falta de pagamento"
                else:
                    continue
            else:
                amount_spent = float(data.get("amount_spent", 0) or 0) / 100
                spend_cap    = float(data.get("spend_cap",    0) or 0) / 100
                balance      = float(data.get("balance",      0) or 0) / 100
                remaining    = max(0.0, spend_cap - amount_spent) if spend_cap else balance
                limite       = LIMITES.get(nome, LIMITE_PADRAO)
                if remaining >= limite:
                    continue
                linha = f"  • {nome}: R${remaining:.2f} restante"

            if agencia == "dentto":
                alertas_dentto.append(linha)
            else:
                alertas_piloti.append(linha)
        except Exception:
            pass

    partes = []
    if alertas_piloti:
        partes.append("*Piloti:*\n" + "\n".join(alertas_piloti))
    if alertas_dentto:
        partes.append("*Dentto:*\n" + "\n".join(alertas_dentto))

    if partes:
        msg = "*Saldo baixo — Contas Meta:*\n\n" + "\n\n".join(partes)
        send_text(AUTHORIZED_NUMBER, msg)
        logger.info(f"_alerta_saldo_baixo: Piloti={len(alertas_piloti)} Dentto={len(alertas_dentto)}")


def _enviar_resumo_gestor():
    """Envia resumo do Gestor IA para o Bruno (não agendado por padrão)."""
    if not AUTHORIZED_JID:
        logger.warning("WA_AUTHORIZED_JID nao configurado - resumo nao enviado")
        return
    from bot.whatsapp_handlers import resumo_gestor
    logger.info("Enviando resumo diario do Gestor IA...")
    resumo = resumo_gestor()
    destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else AUTHORIZED_JID
    send_text(destino, resumo)


def _enviar_mensagem_grupo(grupo: dict):
    """Cron agendado: envia mensagem para um grupo configurado."""
    logger.info(f"Enviando mensagem agendada para grupo {grupo['nome']}")
    send_text(grupo["jid"], grupo["msg"])


def _limpar_tmp_midia():
    """A cada hora: remove arquivos wa_media_* do /tmp com mais de 1h."""
    import glob as _glob_tmp
    agora = _time.time()
    removidos = 0
    for f in _glob_tmp.glob("/tmp/wa_media_*"):
        try:
            if agora - os.path.getmtime(f) > 3600:
                os.remove(f)
                removidos += 1
        except Exception:
            pass
    if removidos:
        logger.info(f"_limpar_tmp_midia: {removidos} arquivo(s) removido(s)")


def _expirar_pendentes():
    """A cada 30min: expira ações pendentes com mais de 4h sem aprovação."""
    try:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"],
                                cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute("""
            UPDATE gestor_acoes
            SET status='expirado', expirado_em=NOW()
            WHERE status='pendente'
              AND executado_em < NOW() - INTERVAL '4 hours'
        """)
        n_acoes = cur.rowcount
        cur.execute("""
            UPDATE gestor_estado
            SET status='expirado', resolvido_em=NOW()
            WHERE status='aguardando'
              AND criado_em < NOW() - INTERVAL '4 hours'
        """)
        n_estados = cur.rowcount
        conn.commit()
        conn.close()
        if n_acoes or n_estados:
            logger.info(f"_expirar_pendentes: {n_acoes} acoes e {n_estados} estados expirados")
    except Exception as e:
        logger.error(f"_expirar_pendentes error: {e}")


def _auto_import_recorrentes():
    """Dia 1 de cada mês às 6h: importa transações recorrentes do financeiro."""
    try:
        from core.sync_financeiro import auto_importar_recorrentes
        n = auto_importar_recorrentes()
        if n:
            logger.info(f"auto_import_recorrentes: {n} transacoes importadas")
    except Exception as e:
        logger.error(f"auto_import_recorrentes error: {e}")


# ── Scheduler ─────────────────────────────────────────────────────────────────

def configurar_scheduler() -> BackgroundScheduler:
    """Monta e retorna o BackgroundScheduler configurado com todos os jobs."""
    scheduler = BackgroundScheduler(timezone=SP_TZ)

    scheduler.add_job(
        _limpar_tmp_midia,
        "interval", hours=1,
        id="limpar_tmp_midia",
        replace_existing=True,
    )

    scheduler.add_job(
        _expirar_pendentes,
        "interval", minutes=30,
        id="expirar_pendentes",
        replace_existing=True,
    )

    scheduler.add_job(
        _rotina_segunda,
        CronTrigger(day_of_week="mon", hour=7, minute=30, timezone=SP_TZ),
        id="rotina_segunda",
        replace_existing=True,
    )
    logger.info("Agendado: briefing de segunda as 07:30")

    scheduler.add_job(
        _auto_import_recorrentes,
        CronTrigger(day=1, hour=6, minute=0, timezone=SP_TZ),
        id="auto_import_recorrentes",
        replace_existing=True,
    )
    logger.info("Agendado: auto-import financeiro no dia 1 de cada mes")

    scheduler.add_job(
        _noticias_diarias,
        CronTrigger(hour=7, minute=35, timezone=SP_TZ),
        id="noticias_diarias",
        replace_existing=True,
    )
    logger.info("Agendado: noticias diarias IA & Marketing as 07:35")

    scheduler.add_job(
        _rotina_sexta,
        CronTrigger(day_of_week="fri", hour=17, minute=0, timezone=SP_TZ),
        id="rotina_sexta",
        replace_existing=True,
    )
    logger.info("Agendado: relatorio financeiro sexta as 17:00")

    scheduler.add_job(
        _rotina_quarta,
        CronTrigger(day_of_week="wed", hour=7, minute=30, timezone=SP_TZ),
        id="rotina_quarta",
        replace_existing=True,
    )
    logger.info("Agendado: check de quarta as 07:30")

    # [NOVO] _alerta_saldo_baixo existia no código mas NÃO estava agendada no
    # scheduler original. Adicioná-la aqui é uma mudança intencional de comportamento:
    # o alerta passará a disparar todo dia às 8h, conforme descrito em ROTINAS_CONFIGURADAS.
    scheduler.add_job(
        _alerta_saldo_baixo,
        CronTrigger(hour=8, minute=0, timezone=SP_TZ),
        id="alerta_saldo_baixo",
        replace_existing=True,
    )
    logger.info("Agendado: alerta saldo baixo as 08:00")  # [NOVO]

    # Mensagens agendadas para grupos (lê wa_grupos.json via whatsapp_handlers)
    grupos = get_grupos()
    for grupo in grupos:
        jid  = grupo.get("jid", "")
        nome = grupo.get("nome", "")
        lembretes = grupo.get("lembretes") or []
        if not lembretes and grupo.get("msg") and grupo.get("cron"):
            lembretes = [{"id": nome, "msg": grupo["msg"], "cron": grupo["cron"], "dias": grupo.get("dias", [])}]
        for lembrete in lembretes:
            lid  = lembrete.get("id", lembrete.get("msg", "")[:20])
            msg  = lembrete.get("msg", "")
            cron = lembrete.get("cron", "")
            if not cron or not msg:
                continue
            try:
                partes = cron.strip().split()
                if len(partes) == 5:
                    minuto, hora, dia, mes, dia_sem = partes
                    scheduler.add_job(
                        _enviar_mensagem_grupo,
                        CronTrigger(
                            minute=minuto, hour=hora, day=dia,
                            month=mes, day_of_week=dia_sem, timezone=SP_TZ
                        ),
                        args=[{"jid": jid, "nome": nome, "msg": msg}],
                        id=f"grupo_{nome}_{lid}",
                        replace_existing=True,
                    )
                else:
                    hora_m, minuto_m = cron.split(":")
                    dias = lembrete.get("dias", [])
                    dia_semana = ",".join(dias) if dias else "*"
                    scheduler.add_job(
                        _enviar_mensagem_grupo,
                        CronTrigger(day_of_week=dia_semana, hour=int(hora_m), minute=int(minuto_m), timezone=SP_TZ),
                        args=[{"jid": jid, "nome": nome, "msg": msg}],
                        id=f"grupo_{nome}_{lid}",
                        replace_existing=True,
                    )
                logger.info(f"Agendado: lembrete '{lid}' para grupo '{nome}' | cron={cron}")
            except Exception as e:
                logger.error(f"Erro ao agendar lembrete '{lid}' do grupo '{nome}': {e}")

    return scheduler
```

> **Notas técnicas:**
> - **`configurar_scheduler()` sem parâmetro `app`:** A spec menciona `configurar_scheduler(app)` mas o código original `_configurar_scheduler()` nunca recebeu `app`. O plano mantém a assinatura sem parâmetro, que é correta.
> - **Imports com `bot.` prefix:** O app roda com `PYTHONPATH=/root` (ver systemd service). Por isso os imports usam `from bot.wa_crons import ...` e `from bot.wa_grupos import ...`. Isso é consistente com o resto do projeto (ex: `from bot.whatsapp_handlers import ...` no próprio `jake_whatsapp.py`).
> - **`_alerta_saldo_baixo` agendada [NOVO]:** A spec diz que a função não estava agendada. O plano adiciona o agendamento explicitamente como melhoria — comportamento novo intencional.

- [ ] **Step 2: Verificar que o módulo importa sem erro**

```bash
cd /root && python3 -c "from bot.wa_crons import configurar_scheduler; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Verificar que o scheduler inicializa**

```bash
cd /root && python3 -c "
from bot.wa_crons import configurar_scheduler
s = configurar_scheduler()
jobs = s.get_jobs()
print(f'Jobs agendados: {len(jobs)}')
for j in jobs: print(' -', j.id)
"
```

Expected: 8+ jobs listados (limpar_tmp_midia, expirar_pendentes, rotina_segunda, auto_import_recorrentes, noticias_diarias, rotina_sexta, rotina_quarta, alerta_saldo_baixo, + lembretes de grupos).

- [ ] **Step 4: Commit**

```bash
cd /root
git add bot/wa_crons.py
git commit -m "feat(whatsapp): extrai todos os crons para wa_crons.py"
```

---

## Task 4: Atualizar `bot/jake_whatsapp.py`

Remover o código extraído e conectar os novos módulos.

**Files:**
- Modify: `bot/jake_whatsapp.py`

### 4a — Remover definição inline de `CASA_GROUP_JID` e adicionar imports

- [ ] **Step 1: Substituir linha 49 (`CASA_GROUP_JID = "..."`) pelos novos imports**

Localizar o bloco de config no topo do arquivo (linhas 43-49):

```python
# ANTES (linha 49):
CASA_GROUP_JID     = "120363310359411409@g.us"

# DEPOIS — remover linha 49 e adicionar imports após os imports existentes (após linha 34):
from bot.wa_crons import configurar_scheduler
from bot.wa_grupos import (
    CASA_GROUP_JID, handle_mensagem_casa,
    VIAGEM_GROUP_JID, handle_mensagem_viagem,
)
```

A constante `CASA_GROUP_JID` agora vem de `wa_grupos`. Remover a definição local na linha 49.

- [ ] **Step 2: Verificar que o arquivo ainda importa**

```bash
cd /root && python3 -c "import bot.jake_whatsapp; print('OK')"
```

Expected: `OK` (ou warnings de variáveis não usadas, mas sem erro).

### 4b — Atualizar o webhook para usar os handlers de grupo

- [ ] **Step 3: Substituir o bloco Casa inline no webhook pelo handler**

Localizar as linhas 1708-1748 (bloco `if sender_jid == CASA_GROUP_JID:`):

```python
# REMOVER este bloco completo (linhas 1708-1748):
if sender_jid == CASA_GROUP_JID:
    message_grp = msg_data.get("message", {})
    texto_grp = (
        message_grp.get("conversation")
        or message_grp.get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()
    if texto_grp:
        if "jake" in texto_grp.lower():
            ...  # (todo o bloco inline)
        ...
    return jsonify({"ok": True})

# SUBSTITUIR POR:
if sender_jid == CASA_GROUP_JID:
    message_grp = msg_data.get("message", {})
    texto_grp = (
        message_grp.get("conversation")
        or message_grp.get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()
    handle_mensagem_casa(texto_grp, key, processar_fn=processar_mensagem)
    return jsonify({"ok": True})

if sender_jid == VIAGEM_GROUP_JID:
    message_grp = msg_data.get("message", {})
    texto_grp = (
        message_grp.get("conversation")
        or message_grp.get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()
    handle_mensagem_viagem(texto_grp, key, processar_fn=processar_mensagem)
    return jsonify({"ok": True})
```

### 4c — Atualizar `main()` para usar `configurar_scheduler`

- [ ] **Step 4: Substituir chamada na `main()`**

Localizar linha 2310:

```python
# ANTES:
scheduler = _configurar_scheduler()

# DEPOIS:
scheduler = configurar_scheduler()
```

### 4d — Remover funções cron do arquivo

- [ ] **Step 5: Remover as funções cron extraídas**

Remover as seguintes funções (agora em `wa_crons.py`):
- `_rotina_segunda` (linhas ~1300-1413)
- `_enviar_resumo_gestor` (linhas ~1807-1815)
- `_enviar_mensagem_grupo` (linhas ~1817-1820)
- `_limpar_tmp_midia` (linhas ~1850-1863)
- `_expirar_pendentes` (linhas ~1866-1892)
- `_alerta_saldo_baixo` (linhas ~1895-1993)
- `_rotina_sexta` (linhas ~1996-2036)
- `_rotina_quarta` (linhas ~2039-2099)
- `_noticias_diarias` (linhas ~2102-2168)
- `_configurar_scheduler` (linhas ~2171-2291, incluindo a nested `_auto_import_recorrentes`)

Manter: `ROTINAS_CONFIGURADAS`, `_cmd_tarefas`, `_contexto_rotinas`, `_KEYWORDS_ROTINAS`, `_eh_sobre_rotinas`, `_processar_slash_cmd`, `_cmd_lista_compras`.

- [ ] **Step 6: Verificar que o arquivo importa após remoções**

```bash
cd /root && python3 -c "import bot.jake_whatsapp; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit parcial**

```bash
cd /root
git add bot/jake_whatsapp.py
git commit -m "refactor(whatsapp): remove crons e handlers inline; delega para wa_crons e wa_grupos"
```

---

## Task 5: Smoke test e commit final

- [ ] **Step 1: Reiniciar o serviço**

```bash
sudo systemctl restart jake-whatsapp
sleep 3
sudo systemctl status jake-whatsapp
```

Expected: `Active: active (running)` e nos logs `APScheduler iniciado com N job(s)`.

- [ ] **Step 2: Verificar logs de inicialização**

```bash
sudo journalctl -u jake-whatsapp -n 50 --no-pager
```

Expected:
- `Agendado: briefing de segunda as 07:30`
- `Agendado: noticias diarias IA & Marketing as 07:35`
- `Agendado: alerta saldo baixo as 08:00`
- `Agendado: check de quarta as 07:30`
- `Agendado: relatorio financeiro sexta as 17:00`
- `APScheduler iniciado com N job(s)` (N >= 8)
- Sem `ERROR` ou `ImportError`

- [ ] **Step 3: Testar health check**

```bash
curl -s http://localhost:5052/health | python3 -m json.tool
```

Expected: `{"ok": true, "wa_status": "open"}`

- [ ] **Step 4: Contar linhas resultantes**

```bash
wc -l /root/bot/jake_whatsapp.py /root/bot/wa_crons.py /root/bot/wa_grupos/casa.py /root/bot/wa_grupos/viagem_chile.py
```

Expected: `jake_whatsapp.py` ~850-950 linhas, total geral ~1200 linhas.

- [ ] **Step 5: Commit de encerramento**

```bash
cd /root
git add -A
git commit -m "refactor(whatsapp): decomposicao completa jake_whatsapp.py -> wa_crons + wa_grupos"
```

---

## Testes manuais pos-deploy

Verificar no WhatsApp real:

1. **Mensagem pessoal** ao número do Bruno → Jake responde normalmente
2. **`/lista`** no chat pessoal → lista de compras enviada (confirma `_cmd_lista_compras` intacto)
3. **Mensagem comum** no grupo Casa → salva na `lista_compras` (sem resposta)
4. **`@Jake quais contas temos pra pagar?`** no grupo Casa → Jake responde no grupo
5. **Aguardar próximo cron** ou forçar via Python para confirmar scheduler ativo:
   ```bash
   python3 -c "from bot.wa_crons import _expirar_pendentes; _expirar_pendentes(); print('OK')"
   ```
