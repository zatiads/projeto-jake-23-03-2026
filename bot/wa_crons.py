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

from bot.whatsapp_handlers import send_text, get_grupos, resumo_gestor

logger = logging.getLogger(__name__)

AUTHORIZED_NUMBER = os.environ.get("WA_AUTHORIZED_NUMBER", "").strip()
AUTHORIZED_JID    = os.environ.get("WA_AUTHORIZED_JID", "").strip()
SP_TZ             = pytz.timezone("America/Sao_Paulo")


def _chamar_claude(prompt_sistema: str, mensagem: str) -> str:
    """Chamada simples ao Claude — uso exclusivo dos crons. Usa Haiku por eficiência de custo."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=prompt_sistema,
        messages=[{"role": "user", "content": mensagem}],
    )
    return resp.content[0].text.strip()


def _rotina_segunda():
    """
    Rotina automática toda segunda às 7h30.
    Envia: resumo Meta da semana anterior + notícias de IA + situação financeira.
    """
    if not AUTHORIZED_NUMBER:
        return

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

    # 2. Financeiro
    try:
        from bot.whatsapp_handlers import resumo_financeiro_wa
        fin_linha = resumo_financeiro_wa()
    except Exception as e:
        fin_linha = f"(erro ao carregar financeiro: {e})"

    # Montar mensagem final
    from datetime import date as _date
    hoje = _date.today().strftime("%d/%m")
    msg = (
        f"Bom dia, Patrao! Segunda-feira {hoje} — aqui esta o seu briefing:\n\n"
        + "\n".join(linhas_meta)
        + f"\n\n{fin_linha}"
        + "\n\nBoa semana!"
    )
    send_text(destino, msg)
    logger.info("_rotina_segunda: briefing enviado")


def _rotina_quarta():
    """
    Roda toda quarta às 7h30.
    Check de meio de semana: contas com gasto travado ou sem conversão.
    """
    if not AUTHORIZED_NUMBER:
        return
    try:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"],
                                cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()

        # Últimas ações do Gestor dos últimos 3 dias
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

        # Contas sem varredura nos últimos 2 dias (possível problema)
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
    """
    Roda toda sexta às 17h.
    Envia relatório financeiro pessoal vs meta R$1M anual.
    """
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
    """
    Roda todo dia às 8h.
    Verifica saldo das contas Meta, separando por agência (Piloti / Dentto).
    Limites personalizados por conta. Contas de cartão de crédito pausadas
    exibem "Falta de pagamento" ao invés de saldo restante.
    """
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

    # Limites de alerta personalizados (default R$300)
    LIMITES = {
        "Calixta Films":  100.0,
        "Amanda Cunha":    50.0,
        "Marcos Couto":    50.0,
    }
    LIMITE_PADRAO = 300.0

    # Clientes ignorados no alerta de saldo baixo (substring, case-insensitive)
    IGNORAR = {"massaranduba", "tijucas", "ilhota", "vielife", "odontouberaba", "barra velha"}

    # Contas de cartão de crédito: não têm saldo pré-pago.
    # Se estiverem pausadas, o motivo é falta de pagamento — exibir isso.
    CARTAO = {"Maíra Castaldi", "RD Contabilidade"}

    alertas_piloti = []

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
            nome     = conta["nome"]
            if any(ig in nome.lower() for ig in IGNORAR):
                continue
            agencia  = (conta.get("agencia") or "piloti").lower()
            # account_status: 1=ativa, 2=desativada, 3=não paga (unsettled), 9=período de graça
            status   = int(data.get("account_status", 1))

            if nome in CARTAO:
                # Cartão de crédito — só alerta se conta pausada por não pagamento
                if status in (2, 3, 9):
                    linha = f"  • {nome}: ⚠️ Falta de pagamento"
                else:
                    continue  # ativa no cartão, sem alerta
            else:
                amount_spent = float(data.get("amount_spent", 0) or 0) / 100
                spend_cap    = float(data.get("spend_cap",    0) or 0) / 100
                balance      = float(data.get("balance",      0) or 0) / 100
                remaining    = max(0.0, spend_cap - amount_spent) if spend_cap else balance
                limite       = LIMITES.get(nome, LIMITE_PADRAO)
                if remaining >= limite:
                    continue
                linha = f"  • {nome}: R${remaining:.2f} restante"

            alertas_piloti.append(linha)

        except Exception:
            pass

    partes = []
    if alertas_piloti:
        partes.append("🟠🟣 *Piloti:*\n" + "\n".join(alertas_piloti))

    if partes:
        msg = "⚠️ *Saldo baixo — Contas Meta:*\n\n" + "\n\n".join(partes)
        send_text(AUTHORIZED_NUMBER, msg)
        logger.info(f"_alerta_saldo_baixo: Piloti={len(alertas_piloti)}")


def _enviar_resumo_gestor():
    """Envia resumo do Gestor IA para o Bruno (não agendado automaticamente)."""
    if not AUTHORIZED_JID:
        logger.warning("WA_AUTHORIZED_JID nao configurado - resumo nao enviado")
        return
    logger.info("Enviando resumo diario do Gestor IA...")
    resumo = resumo_gestor()
    destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else AUTHORIZED_JID
    send_text(destino, resumo)


def _enviar_mensagem_grupo(grupo: dict):
    """Cron agendado: envia mensagem para um grupo configurado."""
    logger.info(f"Enviando mensagem agendada para grupo {grupo['nome']}")
    send_text(grupo["jid"], grupo["msg"])


def _limpar_tmp_midia():
    """Remove arquivos wa_media_* do /tmp com mais de 1 hora."""
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
    """Expira ações pendentes com mais de 4h sem aprovação."""
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
    """Importa automaticamente as transações recorrentes no dia 1 de cada mês às 6h."""
    try:
        from core.sync_financeiro import auto_importar_recorrentes
        n = auto_importar_recorrentes()
        if n:
            logger.info(f"auto_import_recorrentes: {n} transacoes importadas")
    except Exception as e:
        logger.error(f"auto_import_recorrentes error: {e}")


def configurar_scheduler() -> BackgroundScheduler:
    """Cria e configura o BackgroundScheduler com todos os jobs do Jake WhatsApp."""
    scheduler = BackgroundScheduler(timezone=SP_TZ)

    # Limpeza de arquivos temporários de mídia a cada hora
    scheduler.add_job(
        _limpar_tmp_midia,
        "interval", hours=1,
        id="limpar_tmp_midia",
        replace_existing=True,
    )

    # Expirar pendentes a cada 30min
    scheduler.add_job(
        _expirar_pendentes,
        "interval", minutes=30,
        id="expirar_pendentes",
        replace_existing=True,
    )

    # Rotina de segunda-feira: briefing semanal às 7h30
    scheduler.add_job(
        _rotina_segunda,
        CronTrigger(day_of_week="mon", hour=7, minute=30, timezone=SP_TZ),
        id="rotina_segunda",
        replace_existing=True,
    )
    logger.info("Agendado: briefing de segunda as 07:30")

    # Auto-importar recorrentes no dia 1 de cada mês às 6h
    scheduler.add_job(
        _auto_import_recorrentes,
        CronTrigger(day=1, hour=6, minute=0, timezone=SP_TZ),
        id="auto_import_recorrentes",
        replace_existing=True,
    )
    logger.info("Agendado: auto-import financeiro no dia 1 de cada mes")

    # Check de quarta-feira às 7h30
    scheduler.add_job(
        _rotina_quarta,
        CronTrigger(day_of_week="wed", hour=7, minute=30, timezone=SP_TZ),
        id="rotina_quarta",
        replace_existing=True,
    )
    logger.info("Agendado: check de quarta as 07:30")

    # [NOVO] Alerta de saldo baixo Meta todo dia às 8h
    scheduler.add_job(
        _alerta_saldo_baixo,
        CronTrigger(hour=8, minute=0, timezone=SP_TZ),
        id="alerta_saldo_baixo",
        replace_existing=True,
    )
    logger.info("Agendado: alerta saldo baixo Meta as 08:00")

    # Mensagens agendadas para grupos
    grupos = get_grupos()
    for grupo in grupos:
        jid  = grupo.get("jid", "")
        nome = grupo.get("nome", "")
        # Suporta formato novo: lembretes=[{id, msg, cron}]
        # e formato legado: {msg, cron: "HH:MM", dias: [...]}
        lembretes = grupo.get("lembretes") or []
        if not lembretes and grupo.get("msg") and grupo.get("cron"):
            lembretes = [{"id": nome, "msg": grupo["msg"], "cron": grupo["cron"], "dias": grupo.get("dias", [])}]
        for lembrete in lembretes:
            lid = lembrete.get("id", lembrete.get("msg", "")[:20])
            msg = lembrete.get("msg", "")
            cron = lembrete.get("cron", "")
            if not cron or not msg:
                continue
            try:
                partes = cron.strip().split()
                if len(partes) == 5:
                    # Cron padrão 5 campos: minuto hora dia mes dia_semana
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
                    # Formato legado HH:MM + dias
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
