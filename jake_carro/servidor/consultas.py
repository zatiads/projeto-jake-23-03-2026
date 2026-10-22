"""
Consultas que o Jake faz enquanto o patrão dirige: pesquisa na internet, números do
Meta Ads por cliente e agenda do Google. Cada função devolve TEXTO DE DADOS (não a fala);
quem transforma em fala curta é o app.py.
"""
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

FUSO = ZoneInfo("America/Sao_Paulo")
GRAPH = "https://graph.facebook.com/v21.0"


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


# ── Pesquisa na internet ──────────────────────────────────────────────────────

def pesquisar(cliente_ia, modelo, pergunta):
    """Busca na web pela OpenAI e devolve anotações (quem vira fala curta é o app.py)."""
    hoje = datetime.now(FUSO).strftime("%d/%m/%Y")
    # Pesquisa na web demora mais que o resto: tempo próprio, sem nova tentativa, saída limitada
    # (sem limite o modelo às vezes entra em loop repetindo a lista).
    resp = cliente_ia.with_options(timeout=30, max_retries=0).responses.create(
        model=modelo,
        tools=[{"type": "web_search"}],
        max_output_tokens=500,
        instructions=(f"Hoje é {hoje}. Pesquise na internet e anote, em português, no máximo 5 fatos "
                      "relevantes e recentes que respondam à pergunta, um por linha, sem links."),
        input=pergunta,
    )
    return resp.output_text.strip()[:2500]


# ── Meta Ads ──────────────────────────────────────────────────────────────────

_contas = {"ts": 0, "lista": []}  # [{id, nome, token}]


def contas_meta():
    """Todas as contas de anúncio que os tokens do .env enxergam (cache 6 h)."""
    if time.time() - _contas["ts"] < 6 * 3600 and _contas["lista"]:
        return _contas["lista"]
    vistas = {}
    for chave in ("META_TOKEN_PILOTI", "META_ACCESS_TOKEN"):
        token = os.environ.get(chave, "").strip()
        if not token:
            continue
        try:
            r = requests.get(f"{GRAPH}/me/adaccounts", params={
                "fields": "name,account_status", "limit": 200, "access_token": token}, timeout=10)
            for c in r.json().get("data", []):
                vistas.setdefault(c["id"], {"id": c["id"], "nome": _limpar_nome(c["name"]), "token": token})
        except Exception:
            pass
    if vistas:
        _contas.update(ts=time.time(), lista=list(vistas.values()))
    return _contas["lista"]


def _limpar_nome(nome):
    """'CA01 - RD Contabilidade' → 'RD Contabilidade'; 'BM(24) REALIZE SORRISOS' → 'REALIZE SORRISOS'."""
    limpo = re.sub(r"^\s*(CA\s*\d*|BM\s*\(\d+\))\s*-?\s*", "", nome.strip(), flags=re.I)
    limpo = re.sub(r"\s*-\s*\d+\s*$", "", limpo)
    return limpo.strip() or nome.strip()


def nomes_clientes():
    return [c["nome"] for c in contas_meta()]


def _achar_conta(cliente):
    alvo = _sem_acento(cliente)
    if not alvo:
        return None
    melhor, nota = None, 0
    for c in contas_meta():
        nome = _sem_acento(c["nome"])
        if alvo in nome or nome in alvo:
            n = len(alvo) / max(len(nome), 1) + 1
        else:
            palavras = [p for p in alvo.split() if len(p) > 2]
            n = sum(p in nome for p in palavras) / max(len(palavras), 1)
        if n > nota:
            melhor, nota = c, n
    return melhor if nota >= 0.5 else None


PERIODOS_META = {"hoje": "today", "ontem": "yesterday", "esta_semana": "this_week_mon_today",
                 "ultimos_7_dias": "last_7d", "este_mes": "this_month", "mes_passado": "last_month"}

CONVERSAS = ("onsite_conversion.messaging_conversation_started_7d", "messaging_conversation_started_7d")
LEADS = ("lead", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead")


def _acao(acoes, tipos):
    valores = {a["action_type"]: float(a.get("value", 0)) for a in acoes or []}
    for t in tipos:  # pega o primeiro tipo que existir (não soma variantes da mesma métrica)
        if t in valores:
            return int(valores[t])
    return 0


def meta(cliente, periodo):
    conta = _achar_conta(cliente)
    if not conta:
        return f"Não achei conta de anúncio pro cliente '{cliente}'. Contas que eu vejo: {', '.join(nomes_clientes())}."
    preset = PERIODOS_META.get(periodo or "", "yesterday")
    r = requests.get(f"{GRAPH}/{conta['id']}/insights", params={
        "level": "campaign", "date_preset": preset, "limit": 50,
        "fields": "campaign_name,spend,actions,inline_link_clicks",
        "access_token": conta["token"]}, timeout=15)
    dados = r.json()
    if "error" in dados:
        return f"A Meta deu erro ao consultar {conta['nome']}: {dados['error'].get('message', '')[:150]}"
    linhas = dados.get("data", [])
    if not linhas:
        return f"{conta['nome']}: nenhum gasto nem resultado no período ({periodo or 'ontem'})."
    total_gasto = total_conv = total_leads = 0
    campanhas = []
    for l in linhas:
        gasto = float(l.get("spend") or 0)
        conv = _acao(l.get("actions"), CONVERSAS)
        leads = _acao(l.get("actions"), LEADS)
        total_gasto += gasto; total_conv += conv; total_leads += leads
        campanhas.append((gasto, l.get("campaign_name", ""), conv, leads))
    campanhas.sort(reverse=True)
    resultados = total_conv + total_leads
    txt = (f"Conta {conta['nome']}, período {periodo or 'ontem'}: gasto R$ {total_gasto:.2f}, "
           f"{total_conv} conversas iniciadas no WhatsApp/Direct (é o lead das campanhas de mensagem), "
           f"{total_leads} leads de formulário")
    if resultados:
        txt += f", custo por resultado R$ {total_gasto / resultados:.2f}"
    txt += ". Campanhas: " + "; ".join(
        f"{n} (R$ {g:.2f}, {c} conversas, {ld} leads)" for g, n, c, ld in campanhas[:4])
    return txt


# ── Agenda Google ─────────────────────────────────────────────────────────────

def _sessao_google():
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    cred = service_account.Credentials.from_service_account_file(
        os.environ.get("JAKE_CARRO_GOOGLE_CRED", "/root/credenciais.json"),
        scopes=["https://www.googleapis.com/auth/calendar.readonly"])
    return AuthorizedSession(cred)


def agendas():
    return [a.strip() for a in os.environ.get("JAKE_CARRO_AGENDAS", "").split(",") if a.strip()]


def _intervalo(periodo):
    agora = datetime.now(FUSO)
    hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    if periodo == "amanha":
        return hoje + timedelta(days=1), hoje + timedelta(days=2)
    if periodo in ("esta_semana", "ultimos_7_dias"):
        return agora, hoje + timedelta(days=7 - hoje.weekday())  # até domingo
    if periodo == "proxima_semana":
        seg = hoje + timedelta(days=7 - hoje.weekday())
        return seg, seg + timedelta(days=7)
    if periodo == "este_mes":
        prox = (hoje.replace(day=1) + timedelta(days=32)).replace(day=1)
        return agora, prox
    return hoje, hoje + timedelta(days=1)  # hoje


def agenda_itens(periodo):
    """Itens da agenda em lista [{hora, titulo}] (pro cockpit)."""
    ids = agendas()
    inicio, fim = _intervalo(periodo)
    s = _sessao_google()
    itens = []
    for cal in ids:
        r = s.get(f"https://www.googleapis.com/calendar/v3/calendars/{cal}/events", params={
            "timeMin": inicio.isoformat(), "timeMax": fim.isoformat(), "singleEvents": "true",
            "orderBy": "startTime", "maxResults": 20, "timeZone": "America/Sao_Paulo"}, timeout=10)
        if r.status_code != 200:
            continue
        for e in r.json().get("items", []):
            ini = e.get("start", {})
            if "dateTime" in ini:
                quando = datetime.fromisoformat(ini["dateTime"]).astimezone(FUSO)
                itens.append({"ordem": quando.isoformat(), "hora": quando.strftime("%H:%M"),
                              "titulo": e.get("summary", "sem título")})
            else:
                itens.append({"ordem": ini.get("date", ""), "hora": "Dia todo",
                              "titulo": e.get("summary", "sem título")})
    itens.sort(key=lambda i: (i["hora"] != "Dia todo", i["ordem"]))
    return [{"hora": i["hora"], "titulo": i["titulo"]} for i in itens[:6]]


def agenda(periodo):
    ids = agendas()
    if not ids:
        return "A agenda ainda não foi configurada no Jake."
    inicio, fim = _intervalo(periodo)
    s = _sessao_google()
    eventos, falhas = [], []
    for cal in ids:
        r = s.get(f"https://www.googleapis.com/calendar/v3/calendars/{cal}/events", params={
            "timeMin": inicio.isoformat(), "timeMax": fim.isoformat(), "singleEvents": "true",
            "orderBy": "startTime", "maxResults": 50, "timeZone": "America/Sao_Paulo"}, timeout=10)
        if r.status_code != 200:
            falhas.append(cal)
            continue
        for e in r.json().get("items", []):
            ini = e.get("start", {})
            if "dateTime" in ini:
                quando = datetime.fromisoformat(ini["dateTime"]).astimezone(FUSO)
                rotulo = quando.strftime("%a %d/%m %H:%M")
            else:
                quando = datetime.fromisoformat(ini.get("date", inicio.date().isoformat())).replace(tzinfo=FUSO)
                rotulo = quando.strftime("%a %d/%m (dia todo)")
            eventos.append((quando, f"{rotulo} — {e.get('summary', 'sem título')}"))
    if falhas and not eventos and len(falhas) == len(ids):
        return ("SEM ACESSO: a agenda ainda não foi compartilhada com o Jake. Diga isso em uma frase e que é só "
                "compartilhar com o e-mail do Jake no Google Agenda.")
    eventos.sort(key=lambda x: x[0])
    dias = {"Mon": "seg", "Tue": "ter", "Wed": "qua", "Thu": "qui", "Fri": "sex", "Sat": "sáb", "Sun": "dom"}
    linhas = [t for _, t in eventos]
    for en, pt in dias.items():
        linhas = [l.replace(en, pt) for l in linhas]
    periodo_txt = periodo or "hoje"
    if not linhas:
        return f"Agenda ({periodo_txt}): nada marcado."
    return f"Agenda ({periodo_txt}), {len(linhas)} itens:\n" + "\n".join(linhas[:25])


# ── Lugar (cidade) ────────────────────────────────────────────────────────────

VARGINHA = (-21.5513, -45.4303)


def cidade(lat, lon):
    try:
        r = requests.get("https://nominatim.openstreetmap.org/reverse", params={
            "lat": lat, "lon": lon, "format": "json", "zoom": 10, "accept-language": "pt-BR"},
            headers={"User-Agent": "jake-carro/1.0"}, timeout=4)
        end = r.json().get("address", {})
        return end.get("city") or end.get("town") or end.get("village") or end.get("municipality") or ""
    except Exception:
        return ""
