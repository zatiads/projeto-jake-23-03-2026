import json
import os
import re as _re
import requests

from flask import Blueprint, Response, jsonify, make_response, request
from flask import stream_with_context

from .shared import anthropic_client, get_db, login_required

bp = Blueprint('social_brief', __name__)


def _get_meta_token(agency="piloti"):
    """Retorna token Meta Ads para a agência especificada."""
    tokens = {
        "piloti": lambda: os.environ.get("META_TOKEN_PILOTI", "").strip(),
    }
    fn = tokens.get(agency)
    if not fn:
        return ""
    return fn() or ""


# ── Social Brief — helpers de coleta ────────────────────────────────────────

def _sb_buscar_meta_ads(meta_account_id, meta_agency="piloti"):
    """
    Busca top 10 criativos por CTR na última semana via Meta Ads API.
    Retorna dict com 'periodo', 'criativos', 'resumo'.
    """
    import re as _re_meta
    if not meta_account_id or not _re_meta.match(r'^act_\d+$', meta_account_id):
        return {"erro": "meta_account_id inválido", "criativos": [], "resumo": {}}

    token = _get_meta_token(meta_agency)
    if not token:
        return {"erro": f"Token Meta para '{meta_agency}' não configurado", "criativos": [], "resumo": {}}

    try:
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

        def _find_act(arr, *types):
            for e in arr:
                if e.get("action_type") in types:
                    try:
                        return float(e.get("value", 0) or 0)
                    except Exception:
                        return 0.0
            return 0.0

        for ad in ads_raw:
            insights_data = ad.get("insights", {}).get("data", [])
            if not insights_data:
                continue
            ins = insights_data[0]
            ctr = float(ins.get("ctr") or 0)
            cliques = int(ins.get("clicks") or 0)
            impressoes = int(ins.get("impressions") or 0)
            gasto = float(ins.get("spend") or 0)

            actions = ins.get("actions") or []
            costs = ins.get("cost_per_action_type") or []

            leads = _find_act(
                actions,
                "onsite_conversion.messaging_conversation_started_7d",
                "messaging_message_sends",
                "onsite_conversion.total_messaging_connection",
                "lead",
            )
            cpl = _find_act(
                costs,
                "onsite_conversion.messaging_conversation_started_7d",
                "messaging_message_sends",
                "lead",
            )

            creative = ad.get("creative") or {}
            criativo_nome = creative.get("name") or ad.get("name", "")
            criativo_body = creative.get("body") or creative.get("title") or ""
            criativos.append({
                "id": ad.get("id", ""),
                "nome": criativo_nome,
                "body": criativo_body[:120] if criativo_body else "",
                "thumbnail_url": creative.get("thumbnail_url", ""),
                "ctr": round(ctr, 2),
                "cliques": cliques,
                "impressoes": impressoes,
                "gasto": round(gasto, 2),
                "cpl": round(cpl, 2),
                "leads": int(leads),
                "tipo_campanha": creative.get("call_to_action_type", ""),
            })

        criativos.sort(key=lambda x: x["ctr"], reverse=True)
        criativos = criativos[:10]

        total_gasto = sum(c["gasto"] for c in criativos)
        total_leads = int(sum(c["leads"] for c in criativos))
        media_ctr = round(sum(c["ctr"] for c in criativos) / len(criativos), 2) if criativos else 0

        from datetime import date as _date_meta, timedelta as _td_meta
        hoje = _date_meta.today()
        inicio = (hoje - _td_meta(days=7)).isoformat()
        fim = hoje.isoformat()

        return {
            "periodo": {"inicio": inicio, "fim": fim},
            "criativos": criativos,
            "resumo": {
                "total_gasto": round(total_gasto, 2),
                "total_leads": total_leads,
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
    Retorna dict com 'conteudo_pesquisa'.
    """
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        from datetime import date as _dc
        ano = _dc.today().year
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
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "reports", f"{slug}_relatorio.html"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", f"{slug}_relatorio.html"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", f"{slug}_relatorio.html"),
        ]
        for caminho in caminhos:
            if os.path.exists(caminho):
                with open(caminho, "r", encoding="utf-8", errors="ignore") as f:
                    html = f.read()
                soup = BeautifulSoup(html, "html.parser")
                texto = soup.get_text(separator=" ", strip=True)
                return texto[:4000]
        return ""
    except Exception:
        return ""


def _sb_gerar_analise_claude(cliente, dados_meta, perfil_texto, conteudo_pesquisa):
    """
    Chama Claude Sonnet para gerar análise completa do cliente.
    Retorna dict parseado do JSON retornado pelo modelo.
    """
    _ant = anthropic_client()
    if not _ant:
        return {"resumo_semana": "ANTHROPIC_API_KEY não configurada.", "ranking_criativos": [], "o_que_funcionou": [], "o_que_nao_funcionou": [], "perfil_publico": {}, "hooks_sugeridos": {}, "ctas_sugeridos": {}, "sugestoes_criativos": []}
    system_prompt = (
        "Você é um estrategista sênior de tráfego pago especializado em performance de "
        "criativos para Meta Ads e social media. Analise os dados e retorne APENAS JSON "
        "válido, sem markdown, sem texto adicional, sem blocos de código.\n\n"
        "IMPORTANTE sobre perfil_publico: baseie EXCLUSIVAMENTE nos dados reais de "
        "performance da semana (criativos com mais leads/menor CPL). "
        "genero_predominante = gênero que gerou mais leads na semana. "
        "faixa_etaria = faixa com melhor CPL ou mais leads. "
        "melhor_posicionamento = placement (IG Reels, IG Feed, IG Stories, FB Feed) "
        "do criativo #1 do ranking. Se não houver dados suficientes, responda 'A apurar'.\n\n"
        "Estrutura obrigatória:\n"
        "IMPORTANTE: ranking_criativos deve conter os 5 melhores criativos (posições 1 a 5). "
        "Se houver menos de 5 criativos disponíveis, inclua todos os existentes.\n"
        '{"resumo_semana":"análise em 3-4 linhas",'
        '"ranking_criativos":[{"posicao":1,"nome":"...","thumbnail_url":"...",'
        '"destaque":"por que performou em 1 frase","metricas":{"ctr":"2.45%",'
        '"cliques":1203,"cpl":"R$ 12,50","gasto":"R$ 150,00","leads":42}}],'
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
        '"hook":"...","formato":"Reels 9:16 / Feed 1:1 / Stories"}]}'
    )
    user_prompt = (
        f"Cliente: {cliente['nome']}\n"
        f"Nicho: {cliente.get('nicho', 'não informado')}\n\n"
        f"=== META ADS — ÚLTIMA SEMANA ===\n{json.dumps(dados_meta, ensure_ascii=False)}\n\n"
        f"=== PERFIL HISTÓRICO DO PÚBLICO ===\n{perfil_texto or 'Não disponível'}\n\n"
        f"Hooks e CTAs devem ser específicos para o nicho {cliente.get('nicho', '')}.\n"
        f"Valores monetários em formato brasileiro (R$ X,XX).\n"
        f"Lembre: leads = mensagens iniciadas no WhatsApp."
    )
    _fallback = {
        "resumo_semana": "Análise indisponível.",
        "ranking_criativos": [],
        "o_que_funcionou": [],
        "o_que_nao_funcionou": [],
        "perfil_publico": {},
        "hooks_sugeridos": {},
        "ctas_sugeridos": {},
        "sugestoes_criativos": [],
    }
    try:
        resp = _ant.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=8192,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except json.JSONDecodeError:
        _fallback["resumo_semana"] = "Análise indisponível (erro de formato)."
        return _fallback
    except Exception as e:
        _fallback["resumo_semana"] = f"Erro na análise: {str(e)}"
        return _fallback


def _sb_gerar_html_portal(todos_dados, semana_inicio, semana_fim):
    """
    Gera HTML autocontido com todos os clientes. Login screen + sidebar + seções por cliente.
    todos_dados: list de {'cliente': dict, 'analise': dict, 'dados_meta': dict}
    """
    import html as _html_mod
    _e = _html_mod.escape

    def _squad_sort_key(it):
        s = it["cliente"].get("squad")
        return (0 if s else 1, s if s else 0)
    todos_dados = sorted(todos_dados, key=_squad_sort_key)
    primeiro_slug = todos_dados[0]["cliente"]["slug"] if todos_dados else "cliente"

    from datetime import date as _date_html
    hoje_str = _date_html.today().strftime("%d/%m/%Y")

    secoes_html = ""
    menu_items_html = ""
    _cur_sq = object()  # sentinel para detectar mudança de squad

    for item in todos_dados:
        cl = item["cliente"]
        an = item["analise"]
        dm = item["dados_meta"]
        slug = cl["slug"]
        sq = cl.get("squad")

        if sq != _cur_sq:
            _cur_sq = sq
            label = f"Squad {sq}" if sq else "Geral"
            menu_items_html += f'<div class="sidebar-section">{_e(label)}</div>'

        menu_items_html += (
            f'<a class="menu-item" data-slug="{_e(slug)}" href="#" '
            f'onclick="mostrarCliente(\'{_e(slug)}\'); return false;">'
            f'{_e(cl["nome"])}</a>'
        )

        resumo_meta = dm.get("resumo", {})
        total_gasto = resumo_meta.get("total_gasto", 0)
        media_ctr = resumo_meta.get("media_ctr", 0)
        total_leads = resumo_meta.get("total_leads", 0)
        perf_pub = an.get("perfil_publico", {})
        cpl_medio = perf_pub.get("cpl_medio", "—")

        # ── Ranking criativos ──────────────────────────────────────────
        ranking_html = ""
        for i, cri in enumerate(an.get("ranking_criativos", [])[:5]):
            met = cri.get("metricas", {})
            thumb = cri.get("thumbnail_url", "")
            body_text = cri.get("body", "") or ""
            if thumb:
                thumb_tag = (
                    f'<img src="{_e(thumb)}" alt="criativo" '
                    f'style="width:64px;height:64px;object-fit:cover;border-radius:4px;'
                    f'flex-shrink:0;border:1px solid rgba(255,107,0,0.3);">'
                )
            elif body_text:
                thumb_tag = (
                    f'<div style="width:64px;min-height:64px;background:#1a1a1a;border-radius:4px;'
                    f'flex-shrink:0;border:1px solid rgba(255,107,0,0.3);padding:6px;'
                    f'font-size:9px;color:#bbb;line-height:1.4;overflow:hidden;">'
                    f'{_e(body_text[:80])}</div>'
                )
            else:
                thumb_tag = (
                    f'<div style="width:64px;height:64px;background:#1e1e1e;border-radius:4px;'
                    f'flex-shrink:0;border:1px solid #2a2a2a;display:flex;align-items:center;'
                    f'justify-content:center;font-size:18px;color:#333;">📷</div>'
                )
            max_ctr_raw = an.get("ranking_criativos", [{}])[0].get("metricas", {}).get("ctr", 1) or 1
            ctr_raw = met.get("ctr", 0) or 0
            try:
                bar_pct = int(float(str(ctr_raw).replace("%", "").strip() or 0) /
                              float(str(max_ctr_raw).replace("%", "").strip() or 1) * 100)
            except Exception:
                bar_pct = 100 if i == 0 else 60
            ranking_html += (
                f'<div style="display:flex;align-items:center;gap:14px;padding:14px 0;'
                f'border-bottom:1px solid #1e1e1e;">'
                f'<div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:700;'
                f'font-size:22px;color:#FF6B00;width:24px;flex-shrink:0;">#{i+1}</div>'
                f'{thumb_tag}'
                f'<div style="flex:1;min-width:0;">'
                f'<div style="font-size:13px;font-weight:600;color:#F5F5F0;white-space:nowrap;'
                f'overflow:hidden;text-overflow:ellipsis;">{_e(cri.get("nome",""))}</div>'
                f'<div style="font-size:12px;color:#888;margin:2px 0 6px;">{_e(cri.get("destaque",""))}</div>'
                f'<div style="display:flex;gap:10px;flex-wrap:wrap;">'
                f'<span style="font-size:11px;color:#FF6B00;font-weight:600;">CTR {_e(str(met.get("ctr","—")))}</span>'
                f'<span style="font-size:11px;color:#bbb;">Cliques {_e(str(met.get("cliques","—")))}</span>'
                f'<span style="font-size:11px;color:#bbb;">CPL {_e(str(met.get("cpl","—")))}</span>'
                f'<span style="font-size:11px;color:#bbb;">Gasto {_e(str(met.get("gasto","—")))}</span>'
                f'</div>'
                f'<div style="height:3px;background:#1e1e1e;border-radius:1px;margin-top:6px;">'
                f'<div style="height:100%;width:{bar_pct}%;background:#FF6B00;border-radius:1px;"></div></div>'
                f'</div></div>'
            )

        # ── O que funcionou / não ──────────────────────────────────────
        fun_html = "".join(
            f'<div style="padding:10px 0;border-bottom:1px solid #1e1e1e;font-size:13px;color:#bbb;">'
            f'<span style="color:#4caf50;margin-right:8px;">◆</span>{_e(x)}</div>'
            for x in an.get("o_que_funcionou", [])
        )
        nao_fun_html = "".join(
            f'<div style="padding:10px 0;border-bottom:1px solid #1e1e1e;font-size:13px;color:#bbb;">'
            f'<span style="color:#FF6B00;margin-right:8px;">◆</span>{_e(x)}</div>'
            for x in an.get("o_que_nao_funcionou", [])
        )

        # ── Sugestões de criativos ─────────────────────────────────────
        sug_html = "".join(
            f'<div style="background:#141414;border:1px solid rgba(255,107,0,0.2);border-radius:4px;'
            f'padding:20px;margin-bottom:12px;position:relative;overflow:hidden;">'
            f'<div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;"></div>'
            f'<div style="font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#FF6B00;'
            f'font-weight:600;margin-bottom:8px;font-family:\'Barlow Condensed\',sans-serif;">'
            f'{_e(sg.get("tipo","")).upper()}</div>'
            f'<div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:700;font-size:18px;'
            f'color:#F5F5F0;margin-bottom:6px;letter-spacing:-0.5px;">{_e(sg.get("conceito",""))}</div>'
            f'<div style="font-size:13px;color:#888;margin-bottom:4px;">'
            f'<span style="color:#bbb;font-weight:600;">Hook:</span> {_e(sg.get("hook",""))}</div>'
            f'<div style="font-size:12px;color:#666;">'
            f'<span style="color:#888;font-weight:600;">Formato:</span> {_e(sg.get("formato",""))}</div>'
            f'</div>'
            for sg in an.get("sugestoes_criativos", [])[:4]
        )

        _fb = '<div style="font-size:13px;color:#444;padding:8px 0;">—</div>'

        secoes_html += f'''
<div class="cliente-secao" id="cliente-{_e(slug)}" style="display:none;">

  <!-- Header -->
  <div style="position:relative;overflow:hidden;background:#0D0D0D;
              border:1px solid rgba(255,107,0,0.15);border-radius:4px;
              padding:36px 32px;margin-bottom:20px;">
    <div style="position:absolute;inset:0;background-image:
      linear-gradient(rgba(255,107,0,0.04) 1px,transparent 1px),
      linear-gradient(90deg,rgba(255,107,0,0.04) 1px,transparent 1px);
      background-size:50px 50px;pointer-events:none;"></div>
    <div style="position:absolute;top:16px;right:24px;
                font-family:'Barlow Condensed',sans-serif;font-size:80px;font-weight:900;
                color:rgba(255,107,0,0.04);line-height:1;letter-spacing:-4px;pointer-events:none;">
      BRIEF</div>
    <div style="position:relative;z-index:1;">
      <div style="font-size:10px;letter-spacing:5px;text-transform:uppercase;color:#FF6B00;
                  font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:8px;">
        {_e(cl.get("nicho","—"))} &nbsp;·&nbsp; Semana {_e(semana_inicio)} — {_e(semana_fim)}</div>
      <div style="font-family:'Barlow Condensed',sans-serif;font-weight:900;
                  font-size:clamp(32px,4vw,52px);text-transform:uppercase;
                  letter-spacing:-1px;color:#F5F5F0;line-height:1;margin-bottom:20px;">
        {_e(cl["nome"])}</div>
      <div style="display:flex;gap:40px;flex-wrap:wrap;">
        <div>
          <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;
                       font-size:28px;color:#FF6B00;display:block;">R$ {total_gasto:,.2f}</span>
          <span style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#888;">Gasto</span>
        </div>
        <div>
          <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;
                       font-size:28px;color:#F5F5F0;display:block;">{_e(str(media_ctr))}%</span>
          <span style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#888;">CTR Médio</span>
        </div>
        <div>
          <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;
                       font-size:28px;color:#00C2FF;display:block;">{_e(str(total_leads))}</span>
          <span style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#888;">Leads</span>
        </div>
        <div>
          <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;
                       font-size:28px;color:#F5F5F0;display:block;">{_e(str(cpl_medio))}</span>
          <span style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#888;">CPL Médio</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Resumo -->
  <div style="background:#141414;border:1px solid #1e1e1e;border-radius:4px;padding:24px;
              margin-bottom:16px;position:relative;overflow:hidden;">
    <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;opacity:0.4;"></div>
    <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#FF6B00;
                font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:14px;">
      📝 Resumo da Semana</div>
    <p style="font-size:14px;color:#bbb;line-height:1.8;margin:0;">{_e(an.get("resumo_semana",""))}</p>
  </div>

  <!-- Ranking + Funcionou -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
    <div style="background:#141414;border:1px solid #1e1e1e;border-radius:4px;padding:24px;
                position:relative;overflow:hidden;">
      <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;"></div>
      <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#FF6B00;
                  font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:16px;">
        🏆 Ranking de Criativos</div>
      {ranking_html or _fb}
    </div>
    <div style="display:grid;grid-template-rows:1fr 1fr;gap:16px;">
      <div style="background:#141414;border:1px solid #1e1e1e;border-radius:4px;padding:20px;
                  position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#4caf50;opacity:0.7;"></div>
        <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#4caf50;
                    font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:12px;">
          ◆ O que funcionou</div>
        {fun_html or _fb}
      </div>
      <div style="background:#141414;border:1px solid #1e1e1e;border-radius:4px;padding:20px;
                  position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;opacity:0.7;"></div>
        <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#FF6B00;
                    font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:12px;">
          ◆ O que não funcionou</div>
        {nao_fun_html or _fb}
      </div>
    </div>
  </div>

  <!-- Sugestões de criativos -->
  <div style="background:#141414;border:1px solid #1e1e1e;border-radius:4px;padding:24px;
              margin-bottom:16px;position:relative;overflow:hidden;">
    <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;"></div>
    <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#FF6B00;
                font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:20px;">
      🎨 Sugestões de Criativos</div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;">
      {sug_html or _fb}
    </div>
  </div>

  <!-- Referências de Criativos -->
  <div style="background:#141414;border:1px solid rgba(255,107,0,0.2);border-radius:4px;padding:24px;
              margin-bottom:32px;position:relative;overflow:hidden;">
    <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#FF6B00;opacity:0.6;"></div>
    <div style="font-size:10px;letter-spacing:4px;text-transform:uppercase;color:#FF6B00;
                font-family:'Barlow Condensed',sans-serif;font-weight:600;margin-bottom:16px;">
      🎯 Referências de Criativos / Inspiração</div>
    <div style="font-size:13px;color:#444;font-style:italic;padding:20px 0;text-align:center;
                border:1px dashed #2a2a2a;border-radius:4px;">
      Em breve — adicione referências, @ de perfis e links de inspiração aqui.
    </div>
  </div>

</div>'''

    css = (
        '*{box-sizing:border-box;margin:0;padding:0;}'
        'html{scroll-behavior:smooth;}'
        "body{font-family:'Barlow',sans-serif;background:#0D0D0D;color:#F5F5F0;overflow-x:hidden;}"
        'a{text-decoration:none;color:inherit;}'
        '#app{min-height:100vh;}'
        '.sidebar{width:220px;background:#0a0a0a;border-right:1px solid rgba(255,107,0,0.15);'
        'padding:0;position:fixed;height:100vh;overflow-y:auto;left:0;top:0;display:flex;flex-direction:column;}'
        '.sidebar-logo{padding:24px 20px;border-bottom:1px solid #1a1a1a;}'
        ".sidebar-brand{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:18px;"
        'letter-spacing:4px;text-transform:uppercase;color:#FF6B00;}'
        '.sidebar-tagline{font-size:10px;color:#444;letter-spacing:2px;text-transform:uppercase;margin-top:4px;}'
        '.sidebar-week{padding:14px 20px;font-size:11px;color:#555;letter-spacing:1px;'
        'border-bottom:1px solid #1a1a1a;text-transform:uppercase;}'
        '.sidebar-section{padding:16px 20px 8px;font-size:9px;letter-spacing:3px;'
        'text-transform:uppercase;color:#333;font-weight:600;}'
        ".menu-item{display:block;padding:10px 20px;font-size:13px;color:#666;cursor:pointer;"
        "border-left:2px solid transparent;transition:all .15s;font-family:'Barlow',sans-serif;}"
        '.menu-item:hover{color:#F5F5F0;background:rgba(255,107,0,0.06);border-left-color:rgba(255,107,0,0.4);}'
        '.menu-item.ativo{color:#FF6B00;background:rgba(255,107,0,0.08);border-left-color:#FF6B00;}'
        '.sidebar-footer{margin-top:auto;padding:16px 20px;border-top:1px solid #1a1a1a;}'
        '.main-content{margin-left:220px;padding:32px;min-height:100vh;background:#0D0D0D;}'
        '@media(max-width:900px){'
        '.sidebar{display:none;}'
        '.main-content{margin-left:0;padding:20px;}}'
    )

    html = (
        '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'<title>Piloti — Social Brief · {_e(semana_inicio)} a {_e(semana_fim)}</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@300;400;600;700;800;900&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n'
        '</head>\n<body>\n\n'
        '<!-- APP -->\n'
        '<div id="app" style="display:flex;">\n'
        '  <div class="sidebar">\n'
        '    <div class="sidebar-logo">\n'
        '      <div class="sidebar-brand">Piloti</div>\n'
        '      <div class="sidebar-tagline">Social Brief Semanal</div>\n'
        '    </div>\n'
        f'    <div class="sidebar-week">📅 {_e(semana_inicio)} — {_e(semana_fim)}</div>\n'
        f'    {menu_items_html}\n'
        '    <div class="sidebar-footer">\n'
        f'      <div style="font-size:10px;color:#333;letter-spacing:1px;text-transform:uppercase;">Gerado em {hoje_str}</div>\n'
        '    </div>\n'
        '  </div>\n'
        f'  <div class="main-content">{secoes_html}</div>\n'
        '</div>\n\n'
        '<script>\n'
        f'var PRIMEIRO="{_e(primeiro_slug)}";\n'
        'function mostrarCliente(slug){{\n'
        '  document.querySelectorAll(".cliente-secao").forEach(function(s){{s.style.display="none";}});\n'
        '  var el=document.getElementById("cliente-"+slug);if(el)el.style.display="block";\n'
        '  document.querySelectorAll(".menu-item").forEach(function(m){{m.classList.remove("ativo");}});\n'
        "  var mi=document.querySelector(\".menu-item[data-slug='\"+slug+\"']\");if(mi)mi.classList.add(\"ativo\");\n"
        '}}\n'
        'function copiar(btn){{\n'
        '  var t=btn.getAttribute("data-text");\n'
        '  navigator.clipboard.writeText(t).then(function(){{\n'
        '    var o=btn.innerHTML;btn.innerHTML="\u2713";\n'
        '    setTimeout(function(){{btn.innerHTML=o;}},2000);\n'
        '  }});\n'
        '}}\n'
        'window.onload=function(){{mostrarCliente(PRIMEIRO);}};\n'
        '</script>\n</body>\n</html>'
    )
    return html


def _sb_publicar_surge(html):
    """
    Publica HTML no Surge.sh via CLI.
    Retorna URL publicada.
    """
    import subprocess
    import tempfile
    surge_url = os.environ.get("SURGE_URL", "piloti-brief.surge.sh")
    surge_token = os.environ.get("SURGE_TOKEN", "")
    if not surge_token or surge_token == "CONFIGURE_ME":
        raise ValueError("SURGE_TOKEN não configurado no .env. Execute 'surge token' para obtê-lo.")

    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = os.path.join(tmpdir, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)
        cmd = ["surge", tmpdir, surge_url, "--token", surge_token]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            raise RuntimeError(f"Surge error: {result.stderr or result.stdout}")
    return f"https://{surge_url}"


def _sb_gerar_pdf(html: str) -> bytes:
    """Converte HTML do portal em PDF via weasyprint. Retorna bytes do PDF."""
    try:
        from weasyprint import HTML as _WP_HTML, CSS as _WP_CSS
        # Ajuste de CSS para impressão: fundo colorido visível no PDF
        print_css = _WP_CSS(string="@page { size: A4; margin: 10mm; } body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }")
        pdf_bytes = _WP_HTML(string=html).write_pdf(stylesheets=[print_css])
        return pdf_bytes
    except Exception as e:
        raise RuntimeError(f"Erro ao gerar PDF: {e}")


# ── Social Brief — CRUD de clientes ─────────────────────────────────────────

@bp.route("/api/social-brief/clientes", methods=["GET"])
@login_required
def sb_clientes_list():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM social_brief_clientes ORDER BY nome")
        clientes = [dict(r) for r in cur.fetchall()]
        for c in clientes:
            if c.get("concorrentes") is None:
                c["concorrentes"] = []
            if c.get("tipos_campanha") is None:
                c["tipos_campanha"] = {}
        return jsonify({"clientes": clientes})
    finally:
        conn.close()


@bp.route("/api/social-brief/clientes", methods=["POST"])
@login_required
def sb_clientes_create():
    data = request.get_json()
    if not data or not data.get("nome") or not data.get("slug"):
        return jsonify({"error": "nome e slug obrigatórios"}), 400
    import re as _re_slug
    if not _re_slug.match(r'^[a-z0-9-]+$', data["slug"]):
        return jsonify({"error": "slug deve conter apenas letras minúsculas, números e hifens"}), 400
    conn = get_db()
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
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/social-brief/clientes/<int:cid>", methods=["PUT"])
@login_required
def sb_clientes_update(cid):
    data = request.get_json()
    if not data:
        return jsonify({"error": "body obrigatório"}), 400
    if not data.get("nome") or not data.get("slug"):
        return jsonify({"error": "nome e slug obrigatórios"}), 400
    import re as _re_put
    if not _re_put.match(r'^[a-z0-9-]+$', data["slug"]):
        return jsonify({"error": "slug deve conter apenas letras minúsculas, números e hifens"}), 400
    conn = get_db()
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
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/social-brief/clientes/<int:cid>", methods=["DELETE"])
@login_required
def sb_clientes_delete(cid):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM social_brief_clientes WHERE id=%s", (cid,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "cliente não encontrado"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/social-brief/ultima-geracao", methods=["GET"])
@login_required
def sb_ultima_geracao():
    conn = get_db()
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


@bp.route("/api/social-brief/gerar", methods=["GET"])
@login_required
def sb_gerar_portal():
    """Endpoint SSE: gera portal completo com todos os clientes ativos."""
    from flask import stream_with_context, Response as _Response
    from datetime import date as _date_sse, timedelta as _td_sse

    def _generate():
        conn = get_db()
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

            todos_dados.append({"cliente": cliente, "analise": analise, "dados_meta": dados_meta})

            yield f"data: {json.dumps({'cliente': cliente['nome'], 'status': 'concluido', 'progresso': int(((i + 1) / total) * 80)})}\n\n"
            time.sleep(1)

        yield f"data: {json.dumps({'etapa': 'Gerando HTML final...', 'progresso': 85})}\n\n"

        hoje = _date_sse.today()
        dia_seg = hoje - _td_sse(days=hoje.weekday())
        semana_inicio = dia_seg.strftime("%d/%m/%Y")
        semana_fim = (dia_seg + _td_sse(days=6)).strftime("%d/%m/%Y")
        html_portal = _sb_gerar_html_portal(todos_dados, semana_inicio, semana_fim)

        conn = get_db()
        geracao_id = None
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO social_brief_geracoes
                   (semana_inicio, semana_fim, html_completo, publicado, clientes_incluidos)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    dia_seg.isoformat(),
                    (dia_seg + _td_sse(days=6)).isoformat(),
                    html_portal,
                    False,
                    json.dumps([{"id": d["cliente"]["id"], "nome": d["cliente"]["nome"]} for d in todos_dados]),
                )
            )
            geracao_id = cur.fetchone()["id"]
            for item in todos_dados:
                cur.execute(
                    """INSERT INTO social_brief_cliente_dados
                       (geracao_id, cliente_id, analise_json, dados_meta)
                       VALUES (%s, %s, %s, %s)""",
                    (geracao_id, item["cliente"]["id"],
                     json.dumps(item["analise"]), json.dumps(item["dados_meta"]))
                )
            conn.commit()
        finally:
            conn.close()

        yield f"data: {json.dumps({'etapa': 'Publicando no Surge...', 'progresso': 90})}\n\n"

        try:
            url = _sb_publicar_surge(html_portal)
            conn2 = get_db()
            try:
                cur2 = conn2.cursor()
                cur2.execute(
                    "UPDATE social_brief_geracoes SET surge_url=%s, publicado=TRUE WHERE id=%s",
                    (url, geracao_id)
                )
                conn2.commit()
            finally:
                conn2.close()
            yield f"data: {json.dumps({'status': 'finalizado', 'url': url, 'progresso': 100})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'finalizado_sem_surge', 'erro_surge': str(e), 'geracao_id': geracao_id, 'progresso': 100})}\n\n"

    return _Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.route("/api/social-brief/republicar", methods=["POST"])
@login_required
def sb_republicar():
    """Republica o portal usando os dados já salvos da última geração — sem chamar Meta Ads nem Claude."""
    conn = get_db()
    try:
        cur = conn.cursor()
        # Pega a última geração
        cur.execute(
            "SELECT id, semana_inicio, semana_fim FROM social_brief_geracoes ORDER BY criado_em DESC LIMIT 1"
        )
        ger = cur.fetchone()
        if not ger:
            return jsonify({"error": "Nenhuma geração encontrada. Gere o portal primeiro."}), 404

        geracao_id = ger["id"]
        semana_inicio = ger["semana_inicio"].strftime("%d/%m/%Y") if hasattr(ger["semana_inicio"], "strftime") else str(ger["semana_inicio"])
        semana_fim = ger["semana_fim"].strftime("%d/%m/%Y") if hasattr(ger["semana_fim"], "strftime") else str(ger["semana_fim"])

        # Carrega dados dos clientes salvos
        cur.execute(
            """SELECT sbc.*, sbd.analise_json, sbd.dados_meta
               FROM social_brief_cliente_dados sbd
               JOIN social_brief_clientes sbc ON sbc.id = sbd.cliente_id
               WHERE sbd.geracao_id = %s ORDER BY sbc.nome""",
            (geracao_id,)
        )
        rows = cur.fetchall()
        if not rows:
            return jsonify({"error": "Dados da geração não encontrados."}), 404

        todos_dados = [
            {
                "cliente": {k: v for k, v in dict(r).items() if k not in ("analise_json", "dados_meta")},
                "analise": r["analise_json"] if isinstance(r["analise_json"], dict) else json.loads(r["analise_json"] or "{}"),
                "dados_meta": r["dados_meta"] if isinstance(r["dados_meta"], dict) else json.loads(r["dados_meta"] or "{}"),
            }
            for r in rows
        ]
    finally:
        conn.close()

    html_portal = _sb_gerar_html_portal(todos_dados, semana_inicio, semana_fim)
    try:
        url = _sb_publicar_surge(html_portal)
        conn2 = get_db()
        try:
            cur2 = conn2.cursor()
            cur2.execute(
                "UPDATE social_brief_geracoes SET html_completo=%s, surge_url=%s, publicado=TRUE WHERE id=%s",
                (html_portal, url, geracao_id)
            )
            conn2.commit()
        finally:
            conn2.close()
        return jsonify({"ok": True, "url": url, "geracao_id": geracao_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/social-brief/download/<int:geracao_id>", methods=["GET"])
@login_required
def sb_download_html(geracao_id):
    """Permite baixar o HTML de uma geração específica."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT html_completo FROM social_brief_geracoes WHERE id=%s", (geracao_id,)
        )
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


@bp.route("/api/social-brief/exportar-pdf", methods=["GET"])
@login_required
def sb_exportar_pdf():
    """Gera PDF da última geração salva e retorna para download."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, html_completo, semana_inicio, semana_fim FROM social_brief_geracoes ORDER BY criado_em DESC LIMIT 1"
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row or not row["html_completo"]:
        return jsonify({"error": "Nenhuma geração disponível. Gere o portal primeiro."}), 404

    try:
        pdf_bytes = _sb_gerar_pdf(row["html_completo"])
    except Exception as e:
        import traceback as _tb
        print(f"[sb_exportar_pdf] ERRO: {e}\n{_tb.format_exc()}")
        return jsonify({"error": str(e)}), 500

        semana = str(row["semana_inicio"]).replace("/", "-") if row["semana_inicio"] else "semana"
    filename = f"social-brief-{semana}.pdf"
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@bp.route("/api/social-brief/exportar-html", methods=["GET"])
@login_required
def sb_exportar_html():
    """Regenera o HTML da última geração a partir dos dados salvos e retorna para download."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, semana_inicio, semana_fim FROM social_brief_geracoes ORDER BY criado_em DESC LIMIT 1"
        )
        geracao = cur.fetchone()
        if not geracao:
            return jsonify({"error": "Nenhuma geração disponível. Gere o portal primeiro."}), 404

        cur.execute(
            """SELECT sbd.analise_json, sbd.dados_meta, sbc.*
               FROM social_brief_cliente_dados sbd
               JOIN social_brief_clientes sbc ON sbc.id = sbd.cliente_id
               WHERE sbd.geracao_id = %s
               ORDER BY sbc.nome""",
            (geracao["id"],)
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return jsonify({"error": "Dados da última geração não encontrados. Gere o portal novamente."}), 404

    todos_dados = [
        {
            "cliente": {k: v for k, v in dict(r).items() if k not in ("analise_json", "dados_meta")},
            "analise": r["analise_json"] or {},
            "dados_meta": r["dados_meta"] or {},
        }
        for r in rows
    ]

    semana_inicio = geracao["semana_inicio"].strftime("%d/%m/%Y") if geracao["semana_inicio"] else ""
    semana_fim = geracao["semana_fim"].strftime("%d/%m/%Y") if geracao["semana_fim"] else ""
    html = _sb_gerar_html_portal(todos_dados, semana_inicio, semana_fim)

    semana = str(geracao["semana_inicio"]).replace("-", "") if geracao["semana_inicio"] else "semana"
    filename = f"social-brief-{semana}.html"
    response = make_response(html.encode("utf-8"))
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

