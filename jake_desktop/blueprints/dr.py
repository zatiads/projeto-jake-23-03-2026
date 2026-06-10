import json
import os

from flask import Blueprint, jsonify, request

from .shared import anthropic_client, get_db, login_required

bp = Blueprint('dr', __name__)


# ── DR: CRUD OFERTAS ──────────────────────────────────────────────────────────

@bp.route("/api/dr/ofertas", methods=["GET"])
@login_required
def dr_listar_ofertas():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, nicho, tipo_funil, lp_url, quiz_url, "
            "created_at::text, updated_at::text FROM dr_ofertas ORDER BY updated_at DESC"
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/dr/ofertas", methods=["POST"])
@login_required
def dr_criar_oferta():
    d = request.get_json() or {}
    if not d.get("nome"):
        return jsonify({"error": "Campo obrigatório: nome"}), 400
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO dr_ofertas
               (nome, nicho, angulo, hook, promessa, publico, contexto_raw, tipo_funil)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (d["nome"], d.get("nicho"), d.get("angulo"), d.get("hook"),
             d.get("promessa"), d.get("publico"), d.get("contexto_raw"), d.get("tipo_funil", "vsl_direto"))
        )
        novo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/dr/ofertas/<int:oid>", methods=["GET"])
@login_required
def dr_carregar_oferta(oid):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM dr_ofertas WHERE id = %s", (oid,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "Oferta não encontrada"}), 404
        return jsonify(dict(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/dr/ofertas/<int:oid>", methods=["DELETE"])
@login_required
def dr_deletar_oferta(oid):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM dr_ofertas WHERE id = %s", (oid,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/dr/gerar-copy", methods=["POST"])
@login_required
def dr_gerar_copy():
    import json as _json
    d = request.get_json() or {}
    oferta_id = d.get("oferta_id")
    contexto  = d.get("contexto_raw", "")
    produto   = d.get("produto", d.get("nome", ""))
    publico   = d.get("publico", "")
    nicho     = d.get("nicho", "")
    angulo    = d.get("angulo", "")
    hook      = d.get("hook", "")
    promessa  = d.get("promessa", "")
    tipo_funil = d.get("tipo_funil", "vsl_direto")

    prompt = f"""Você é um especialista em Direct Response e copywriting de alta conversão para o mercado brasileiro.

Analise o contexto da oferta vencedora abaixo e gere copy adaptada para o produto do usuário.
Escreva em português do Brasil. Seja direto, persuasivo e use linguagem de conversão real.

CONTEXTO DA OFERTA VENCEDORA:
{contexto}

PRODUTO: {produto}
NICHO: {nicho}
ÂNGULO: {angulo}
HOOK PRINCIPAL: {hook}
PROMESSA CENTRAL: {promessa}
PÚBLICO-ALVO: {publico}
TIPO DE FUNIL: {tipo_funil}

Retorne APENAS um JSON válido com esta estrutura exata (sem texto antes ou depois, sem markdown):
{{
  "copy": {{
    "headline": "headline principal impactante",
    "subheadline": "subheadline de suporte",
    "bullets": ["benefício 1", "benefício 2", "benefício 3", "benefício 4", "benefício 5"],
    "cta": "texto do botão CTA",
    "anuncio_curto": "copy curta para anúncio (até 125 chars)",
    "anuncio_medio": "copy média para anúncio (até 300 chars)",
    "anuncio_longo": "copy longa para anúncio (até 600 chars)"
  }},
  "script_vsl": {{
    "hook": "abertura que para o scroll (15-30 segundos)",
    "problema": "amplificação do problema que o público enfrenta",
    "agitacao": "consequências de não resolver o problema agora",
    "solucao": "apresentação da solução (produto) como saída",
    "prova": "provas sociais, resultados, depoimentos sugeridos",
    "oferta": "detalhes da oferta: preço, bônus, o que está incluso",
    "garantia": "garantia e redução de risco",
    "cta": "chamada para ação final urgente"
  }},
  "angulos": [
    {{"titulo": "Ângulo 1", "descricao": "descrição do ângulo", "hook": "hook para este ângulo"}},
    {{"titulo": "Ângulo 2", "descricao": "descrição do ângulo", "hook": "hook para este ângulo"}},
    {{"titulo": "Ângulo 3", "descricao": "descrição do ângulo", "hook": "hook para este ângulo"}}
  ]
}}"""

    try:
        client = _anthropic_client_46()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        result = _json.loads(raw)

        if oferta_id:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """UPDATE dr_ofertas SET copy_json=%s, script_vsl=%s, angulos_json=%s,
                   updated_at=NOW() WHERE id=%s""",
                (_json.dumps(result.get("copy", {})),
                 _json.dumps(result.get("script_vsl", {})),
                 _json.dumps(result.get("angulos", [])),
                 oferta_id)
            )
            conn.commit()
            conn.close()

        return jsonify(result)
    except _json.JSONDecodeError as e:
        return jsonify({"error": f"Claude retornou JSON inválido: {str(e)}", "raw": raw[:300]}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _dr_fetch_html(url):
    """Faz fetch de uma URL e retorna (html, erro)."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=10
        )
        if resp.status_code != 200:
            return None, f"Status HTTP {resp.status_code}"
        html = resp.text
        import re as _re
        texto_visivel = _re.sub(r'<[^>]+>', ' ', html)
        texto_visivel = _re.sub(r'\s+', ' ', texto_visivel).strip()
        if len(texto_visivel) < 500:
            return None, "Conteúdo insuficiente — página pode usar renderização JS pesada"
        return html, None
    except requests.exceptions.Timeout:
        return None, "Timeout ao carregar URL"
    except Exception as e:
        return None, str(e)


def _dr_prompt_lp(contexto_oferta, hotmart_url, video_url, pixel_id, preco, estrutura_original=None):
    """Monta o prompt para geração de LP HTML completa."""
    ref = f"\nESTRUTURA DA LP ORIGINAL PARA INSPIRAÇÃO:\n{estrutura_original[:3000]}" if estrutura_original else ""
    return f"""Você é um especialista em Direct Response e desenvolvimento web.
Gere uma landing page HTML completa, autocontida e mobile-first para uma oferta de DR.

CONTEXTO DA OFERTA:
{contexto_oferta}

CONFIGURAÇÕES:
- Link do Checkout (Hotmart): {hotmart_url}
- URL do Vídeo VSL: {video_url}
- Pixel ID Meta: {pixel_id}
- Preço: {preco}
{ref}

REQUISITOS OBRIGATÓRIOS:
1. HTML único autocontido (CSS inline + JS inline, sem dependências externas)
2. Mobile-first (breakpoint 768px)
3. Meta Pixel no <head> com o Pixel ID fornecido (fbq('init', '{pixel_id}'); fbq('track', 'PageView');)
4. Player de vídeo: embed do YouTube ou Vimeo com o URL fornecido
5. Seção hero: headline + subheadline impactantes baseadas no contexto
6. Lista de benefícios (bullets) — mínimo 5 itens
7. 3 depoimentos/provas sociais com nome, resultado e texto
8. Timer de escassez: usar localStorage para definir data de expiração fixa (72h da primeira visita). NÃO usar countdown que reseta — é dark pattern.
   JS para timer:
   var KEY='dr_exp'; var stored=localStorage.getItem(KEY);
   var exp=stored?new Date(stored):new Date(Date.now()+72*3600000);
   if(!stored) localStorage.setItem(KEY,exp.toISOString());
9. Bloco de preço com botão CTA → {hotmart_url}?utm_source=meta&utm_medium=cpc&utm_campaign=dr
10. Paleta dark moderna: fundo escuro (#0a0a0a ou similar), destaques em cor vibrante (verde, azul ou laranja)
11. Sem frameworks CSS externos (sem Bootstrap, sem Tailwind)
12. Tag <title> com o nome do produto

Retorne APENAS o código HTML completo, começando com <!DOCTYPE html> e terminando com </html>.
Sem texto antes ou depois, sem markdown, sem explicações."""


@bp.route("/api/dr/clonar-lp", methods=["POST"])
@login_required
def dr_clonar_lp():
    import json as _json
    d = request.get_json() or {}
    url_original = d.get("url_original", "")
    oferta_id    = d.get("oferta_id")
    hotmart_url  = d.get("hotmart_url", "#")
    video_url    = d.get("video_url", "")
    pixel_id     = d.get("pixel_id", "")
    preco        = d.get("preco", "")

    contexto = d.get("contexto_raw") or ""
    if not contexto and oferta_id:
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute("SELECT * FROM dr_ofertas WHERE id=%s", (oferta_id,))
            row = cur.fetchone(); conn.close()
            if row:
                o = dict(row)
                contexto = f"Produto: {o.get('nome')}\nNicho: {o.get('nicho')}\nÂngulo: {o.get('angulo')}\nHook: {o.get('hook')}\nPromessa: {o.get('promessa')}\nPúblico: {o.get('publico')}"
        except Exception:
            pass

    fallback_msg = None
    estrutura_original = None

    if url_original:
        html_orig, erro = _dr_fetch_html(url_original)
        if erro:
            fallback_msg = f"Não foi possível carregar a URL original ({erro}) — LP gerada do zero com base no contexto."
        else:
            estrutura_original = html_orig

    try:
        prompt = _dr_prompt_lp(contexto, hotmart_url, video_url, pixel_id, preco, estrutura_original)
        client = _anthropic_client_46()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )
        lp_html = msg.content[0].text.strip()
        if lp_html.startswith("```"):
            lp_html = lp_html.split("```")[1]
            if lp_html.startswith("html"): lp_html = lp_html[4:]
            lp_html = lp_html.rsplit("```", 1)[0].strip()

        if oferta_id:
            conn = get_db(); cur = conn.cursor()
            cur.execute("UPDATE dr_ofertas SET lp_html=%s, updated_at=NOW() WHERE id=%s", (lp_html, oferta_id))
            conn.commit(); conn.close()

        return jsonify({"html": lp_html, "fallback_msg": fallback_msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/dr/gerar-lp", methods=["POST"])
@login_required
def dr_gerar_lp():
    import json as _json
    d = request.get_json() or {}
    oferta_id   = d.get("oferta_id")
    hotmart_url = d.get("hotmart_url", "#")
    video_url   = d.get("video_url", "")
    pixel_id    = d.get("pixel_id", "")
    preco       = d.get("preco", "")
    contexto    = d.get("contexto_raw", "")

    if not contexto and oferta_id:
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute("SELECT * FROM dr_ofertas WHERE id=%s", (oferta_id,))
            row = cur.fetchone(); conn.close()
            if row:
                o = dict(row)
                contexto = f"Produto: {o.get('nome')}\nNicho: {o.get('nicho')}\nÂngulo: {o.get('angulo')}\nHook: {o.get('hook')}\nPromessa: {o.get('promessa')}\nPúblico: {o.get('publico')}"
                if o.get('copy_json'):
                    try:
                        cp = _json.loads(o['copy_json']) if isinstance(o['copy_json'], str) else o['copy_json']
                        contexto += f"\nHeadline: {cp.get('headline','')}\nBullets: {'; '.join(cp.get('bullets',[]))}"
                    except Exception:
                        pass
        except Exception:
            pass

    try:
        prompt = _dr_prompt_lp(contexto, hotmart_url, video_url, pixel_id, preco)
        client = _anthropic_client_46()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )
        lp_html = msg.content[0].text.strip()
        if lp_html.startswith("```"):
            lp_html = lp_html.split("```")[1]
            if lp_html.startswith("html"): lp_html = lp_html[4:]
            lp_html = lp_html.rsplit("```", 1)[0].strip()

        if oferta_id:
            conn = get_db(); cur = conn.cursor()
            cur.execute("UPDATE dr_ofertas SET lp_html=%s, updated_at=NOW() WHERE id=%s", (lp_html, oferta_id))
            conn.commit(); conn.close()

        return jsonify({"html": lp_html})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/dr/deploy-lp", methods=["POST"])
@login_required
def dr_deploy_lp():
    d = request.get_json() or {}
    html = d.get("html", "")
    oferta_id = d.get("oferta_id")
    if not html:
        return jsonify({"error": "HTML vazio"}), 400
    ok, url, info = _deploy_to_vercel("jake-dr-lp", html)
    if not ok:
        return jsonify({"error": f"Deploy falhou: {info}"}), 500
    if oferta_id:
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute("UPDATE dr_ofertas SET lp_url=%s, updated_at=NOW() WHERE id=%s", (url, oferta_id))
            conn.commit(); conn.close()
        except Exception:
            pass
    return jsonify({"url": url, "ok": True})


def _dr_prompt_quiz(contexto_oferta, redirect_url, estrutura_original=None):
    """Monta prompt para geração de quiz HTML completo."""
    ref = f"\nESTRUTURA DO QUIZ ORIGINAL PARA INSPIRAÇÃO:\n{estrutura_original[:3000]}" if estrutura_original else ""
    return f"""Você é especialista em quiz funnels de alta conversão para Direct Response.
Gere um quiz HTML completo, autocontido e mobile-first.

CONTEXTO DA OFERTA:
{contexto_oferta}

URL DE REDIRECT (após quiz): {redirect_url}
{ref}

REQUISITOS:
1. HTML único autocontido (CSS inline + JS inline)
2. Mobile-first, design atrativo e moderno
3. 4 perguntas com 3-4 opções cada (baseadas no nicho/problema da oferta)
4. Barra de progresso visual (ex: "Pergunta 2 de 4")
5. Campo de email ANTES de revelar o resultado (label: "Para onde enviar sua análise personalizada?")
6. 3 perfis de resultado baseados nas respostas (Perfil A, B, C)
7. Cada perfil tem: título, texto descritivo, e botão CTA → {redirect_url}
8. JS puro para lógica de navegação entre perguntas e cálculo de perfil
9. Animação suave de transição entre perguntas (fade ou slide)
10. Paleta de cores vibrante e moderna, fundo escuro ou claro (escolha o que converter mais)
11. Sem frameworks externos

Retorne APENAS o código HTML completo começando com <!DOCTYPE html>.
Sem texto antes ou depois, sem markdown."""


@bp.route("/api/dr/clonar-quiz", methods=["POST"])
@login_required
def dr_clonar_quiz():
    d = request.get_json() or {}
    url_original = d.get("url_original", "")
    oferta_id    = d.get("oferta_id")
    redirect_url = d.get("redirect_url", "#")

    contexto = d.get("contexto_raw", "")
    if not contexto and oferta_id:
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute("SELECT * FROM dr_ofertas WHERE id=%s", (oferta_id,))
            row = cur.fetchone(); conn.close()
            if row:
                o = dict(row)
                contexto = f"Produto: {o.get('nome')}\nNicho: {o.get('nicho')}\nÂngulo: {o.get('angulo')}\nPromessa: {o.get('promessa')}\nPúblico: {o.get('publico')}"
        except Exception:
            pass

    fallback_msg = None
    estrutura_original = None

    if url_original:
        html_orig, erro = _dr_fetch_html(url_original)
        if erro:
            fallback_msg = f"Não foi possível carregar o quiz original ({erro}) — quiz gerado com estrutura base."
        else:
            estrutura_original = html_orig

    try:
        prompt = _dr_prompt_quiz(contexto, redirect_url, estrutura_original)
        client = _anthropic_client_46()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )
        quiz_html = msg.content[0].text.strip()
        if quiz_html.startswith("```"):
            quiz_html = quiz_html.split("```")[1]
            if quiz_html.startswith("html"): quiz_html = quiz_html[4:]
            quiz_html = quiz_html.rsplit("```", 1)[0].strip()

        if oferta_id:
            conn = get_db(); cur = conn.cursor()
            cur.execute("UPDATE dr_ofertas SET quiz_html=%s, updated_at=NOW() WHERE id=%s", (quiz_html, oferta_id))
            conn.commit(); conn.close()

        return jsonify({"html": quiz_html, "fallback_msg": fallback_msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/dr/deploy-quiz", methods=["POST"])
@login_required
def dr_deploy_quiz():
    d = request.get_json() or {}
    html = d.get("html", "")
    oferta_id = d.get("oferta_id")
    if not html:
        return jsonify({"error": "HTML vazio"}), 400
    ok, url, info = _deploy_to_vercel("jake-dr-quiz", html)
    if not ok:
        return jsonify({"error": f"Deploy falhou: {info}"}), 500
    if oferta_id:
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute("UPDATE dr_ofertas SET quiz_url=%s, updated_at=NOW() WHERE id=%s", (url, oferta_id))
            conn.commit(); conn.close()
        except Exception:
            pass
    return jsonify({"url": url, "ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    ip   = _local_ip()
    print(f"\n  Jake OS")
    print(f"  Local : http://localhost:{port}")
    if ip:
        print(f"  Rede  : http://{ip}:{port}")
    print(f"  Login : {_ADMIN_EMAIL} / {_ADMIN_PASSWORD}")
    print("  Mantenha esta janela aberta.\n")
    if os.environ.get("OPEN_BROWSER", "").lower() in ("1", "true", "yes"):
        threading.Thread(target=_open_browser_delayed, args=(port,), daemon=True).start()
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    _init_rotina_tables()
    _init_social_brief_tables()
    _init_nutricao_tables()
    _init_dr_tables()
    _init_aportes_table()
    _init_ativos_personalizados_table()
    _init_ingles_tables()
    # APScheduler: Social Brief automático toda segunda às 08h
