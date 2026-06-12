import base64
import json
import os
import re as _re
import time

import anthropic as _anthropic
import requests

from flask import Blueprint, jsonify, request

from .shared import anthropic_client, get_db, login_required, openai_client

bp = Blueprint('carousel', __name__)


# ── API: Gerador de Carrossel (Claude claude-sonnet-4-5) ───────────────────────────
_CAROUSEL_SYSTEM = """\
Você é um Estrategista de Conteúdo Sênior especializado em carrosséis educativos de alto valor para Instagram.

FILOSOFIA:
Você cria conteúdo que ensina algo genuinamente útil. O leitor deve terminar o carrossel sabendo fazer \
ou entender algo que não sabia antes. Autoridade se constrói pelo mérito do conteúdo, não por hype.

REGRAS DE OURO:
1. Cada slide desenvolve UMA ideia central com profundidade — sem superficialidade.
2. Use dados reais, exemplos concretos, números, estudos ou casos sempre que possível.
3. Evite absolutamente: clichês motivacionais, frases de efeito vazias, "você sabia que...", promessas infladas.
4. A narrativa deve ser progressiva: cada slide avança o entendimento, nunca repete.
5. Prefira verbos de ação e linguagem direta. Português do Brasil natural, sem rebuscamento.
6. Zero emojis.

ESTRUTURA DOS 7 SLIDES:
- Slide 1 | GANCHO: Abre com uma afirmação contraintuitiva, dado surpreendente ou insight que quebra uma crença comum. \
Deve criar tensão cognitiva imediata — o leitor para de rolar porque precisa saber mais.
- Slides 2-3 | PROBLEMA: Diagnóstico profundo. Mostre as causas raiz (não os sintomas). \
Por que o problema persiste? Qual o custo real de ignorá-lo? O leitor deve pensar "é exatamente isso que acontece."
- Slides 4-5 | MÉTODO/FRAMEWORK: Entregue o método, framework ou critério de forma acionável e estruturada. \
Nomeie os princípios. Dê exemplos práticos de como aplicar. Seja específico ao ponto de o leitor conseguir \
implementar sem precisar de mais nada.
- Slide 6 | RESULTADO/VALOR: Mostre o resultado concreto de quem aplica o método. \
Use antes/depois, métricas reais ou transformação mensurável. Torne o ganho tangível.
- Slide 7 | CTA: Um próximo passo imediato, concreto e de baixa fricção que o leitor pode fazer HOJE. \
Não prometa milagres. Ofereça a ação lógica mais próxima.

FORMATO DE SAÍDA:
Retorne SOMENTE JSON válido, sem texto antes ou depois:
{"slides":[{"headline":"...","subheadline":"...","tag":"..."}]}
Exatamente 7 itens. Headline: máx 100 caracteres. Subheadline: 90-200 caracteres com conteúdo rico e específico.\
"""

_CAROUSEL_TONE = {
    "agressivo":    "Tom: direto, urgente, sem rodeios. Contraste forte entre dor e ganho. CTA incisivo e imperativo.",
    "elegante":     "Tom: premium, sofisticado e confiante. Vocabulário refinado sem ser pedante. Autoridade pela precisão.",
    "educacional":  "Tom: didático, claro e estruturado. Priorize explicações passo a passo, analogias e exemplos práticos.",
    "storytelling": "Tom: narrativa com começo, tensão e resolução. Use casos, jornada do personagem ou antes/depois para engajar.",
}

_CAROUSEL_AWARENESS = {
    "frio":     "Público FRIO: a pessoa não sabe que tem o problema ou não te conhece. Gancho por curiosidade, dado surpreendente ou problema latente. Zero venda direta no início.",
    "problema": "Público reconhece o PROBLEMA: já sente a dor. Reforce o diagnóstico e o custo de não agir.",
    "solucao":  "Público busca SOLUÇÃO: está comparando caminhos. Diferencie pelo método e pela clareza.",
    "produto":  "Público em fase PRODUTO: compara ofertas. Reforce prova social, resultado e critério de escolha.",
    "oferta":   "Público consciente da OFERTA: pronto para decidir. Remova objeções, destaque urgência/escassez e facilite a ação.",
}

_CAROUSEL_COMPLEXITY = {
    "simples":  "NÍVEL DE LINGUAGEM: Muito simples. Frases curtas. Palavras do dia a dia. Como se estivesse explicando pra alguém sem formação técnica. Sem jargões, sem palavras difíceis. Se usar um conceito, explique com uma analogia concreta.",
    "medio":    "NÍVEL DE LINGUAGEM: Equilibrado. Direto, claro, sem ser básico demais nem técnico demais.",
    "avancado": "NÍVEL DE LINGUAGEM: Avançado. Público que já domina o assunto. Use termos técnicos, conceitos elaborados, referências de mercado, nuances. Profundidade máxima.",
}

_CAROUSEL_TRIGGER = {
    "prova":       "Gatilho principal: PROVA SOCIAL — números, depoimentos, resultados de quem aplicou.",
    "urgencia":    "Gatilho principal: URGÊNCIA — prazo real, decisão agora ou perde.",
    "autoridade":  "Gatilho principal: AUTORIDADE — credenciais, anos de experiência, cases, certificações.",
    "pertenca":    "Gatilho principal: PERTENCIMENTO — quem já está do outro lado, tribo, exclusividade.",
    "curiosidade": "Gatilho principal: CURIOSIDADE — revelar algo inesperado, tensão cognitiva que o leitor precisa resolver.",
}

def _carousel_fallback(theme, tone):
    suffix = {"agressivo": "Quem age sem método perde para quem age com estratégia.", "elegante": "A diferença está nos critérios, não no esforço.", "educacional": "Entender a causa raiz é o primeiro passo para resolver de forma duradoura."}.get(tone, "")
    return [
        {"headline": f"{theme}: o que separa os 5% que dominam dos 95% que tentam", "subheadline": f"Não é talento nem sorte. É um conjunto de decisões que a maioria nunca aprende a tomar. {suffix}", "tag": "GANCHO"},
        {"headline": "O erro está no diagnóstico, não na execução", "subheadline": "A maioria tenta resolver o sintoma enquanto a causa raiz segue intacta. Resultado: ciclo de tentativas sem evolução real.", "tag": "PROBLEMA"},
        {"headline": "Sem critério claro, qualquer caminho parece certo", "subheadline": "A ausência de um framework de decisão transforma esforço em ruído. Trabalho duro sem direção correta não gera resultado, gera esgotamento.", "tag": "PROBLEMA"},
        {"headline": "O framework em 3 camadas que muda o resultado", "subheadline": "1. Defina o problema real (não o aparente). 2. Identifique a alavanca de maior impacto. 3. Execute em ciclos curtos com medição constante.", "tag": "MÉTODO"},
        {"headline": "A alavanca que 9 em cada 10 ignoram", "subheadline": "Concentrar 80% da energia nos 20% de ações que geram resultado é teoria conhecida — mas aplicar exige rejeitar o que parece urgente mas não é importante.", "tag": "FRAMEWORK"},
        {"headline": "Quem aplica esse método muda o resultado em 30 dias", "subheadline": "Não porque é mágico, mas porque elimina o desperdício de energia em ações de baixo retorno. Foco gera velocidade, velocidade gera resultados mensuráveis.", "tag": "VALOR"},
        {"headline": "Seu próximo passo concreto começa aqui", "subheadline": f"Escolha UMA área onde você quer aplicar esse framework em {theme}. Defina o problema real, a alavanca e o ciclo de medição. Comece esta semana.", "tag": "CTA"},
    ]

@bp.route("/api/carousel/copy", methods=["POST"])
@login_required
def api_carousel_copy():
    data  = request.get_json() or {}
    theme = (data.get("theme") or "").strip()
    tone  = data.get("tone", "elegante")
    awareness  = data.get("awareness") or "problema"
    trigger    = data.get("trigger") or "prova"
    num_slides   = max(3, min(10, int(data.get("num_slides") or 7)))
    complexidade = data.get("complexidade") or "medio"
    if len(theme) < 3:
        return jsonify({"error": "Tema muito curto (mínimo 3 caracteres)."}), 400
    tone_hint = _CAROUSEL_TONE.get(tone, _CAROUSEL_TONE["elegante"])
    awareness_hint = _CAROUSEL_AWARENESS.get(awareness, _CAROUSEL_AWARENESS["problema"])
    trigger_hint   = _CAROUSEL_TRIGGER.get(trigger, _CAROUSEL_TRIGGER["prova"])

    client = anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    try:
        ctx = brain.contexto(theme)
        system_prompt = _CAROUSEL_SYSTEM
        if ctx:
            system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": "\n".join([
                    f"Tema: {theme}",
                    f"Tom solicitado: {tone}. {tone_hint}",
                    f"Nível de consciência do público: {awareness_hint}",
                    f"Gatilho mental a priorizar: {trigger_hint}",
                    _CAROUSEL_COMPLEXITY.get(complexidade, _CAROUSEL_COMPLEXITY["medio"]),
                    f"Gere exatamente {num_slides} slides com profundidade real de conteúdo.",
                    "Cada subheadline deve ensinar algo específico, com dados ou exemplos concretos.",
                    f"Retorne SOMENTE o JSON: {{\"slides\":[...{num_slides} itens...]}}",
                ]),
            }],
        )
        raw = (msg.content[0].text or "").strip()
        # Extrai o JSON caso venha com texto extra
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("JSON não encontrado na resposta")
        parsed = json.loads(raw[start:end])
        slides = parsed.get("slides", [])
        if len(slides) != num_slides:
            raise ValueError(f"Esperava {num_slides} slides, recebi {len(slides)}")
        slides_texto = "\n\n".join(
            f"**Slide {i+1}:** {str(s)}" for i, s in enumerate(slides)
        )
        brain.salvar(
            modulo="Carrossel",
            titulo=f"Carrossel {theme}",
            inputs={
                "tema": theme,
                "tom": tone,
                "nivel_consciencia": awareness,
                "gatilho": trigger,
            },
            output=slides_texto,
            model="claude-sonnet-4-5",
            cliente=theme,
        )
        return jsonify({"slides": slides, "theme": theme, "tone": tone})
    except Exception as exc:
        return jsonify({"error": str(exc), "slides": _carousel_fallback(theme, tone)}), 500

# ── API: Máquina de Copys ────────────────────────────────────────────────────
_COPYS_SYSTEM = """\
Você é um Copywriter de Alta Conversão, especializado em anúncios pagos para gestores de tráfego brasileiros.
Seu trabalho é criar textos persuasivos e prontos para veicular em anúncios digitais.

REGRAS ABSOLUTAS:
1. Entregue SOMENTE o texto do anúncio — sem introduções, sem explicações, sem comentários sobre a copy.
2. Use português brasileiro natural, direto e impactante.
3. Respeite rigorosamente o framework, a plataforma, o tom e TODAS as variáveis fornecidas.
4. Adapte o formato à plataforma: Meta Ads aceita textos longos; Google Ads exige títulos curtos (30 chars); TikTok/YouTube focam nos primeiros 3 segundos.
5. Para Roteiro de Vídeo: use tópicos numerados com indicação de cena/visual entre colchetes.
6. O CTA informado deve aparecer EXATAMENTE na última linha, sem nenhuma alteração.

NÍVEL DE CONSCIÊNCIA — muda radicalmente o ângulo de entrada:
- Público Frio (Topo): a pessoa não sabe que tem o problema ou não te conhece. Gancho baseado em curiosidade, dado surpreendente ou problema latente. Zero empurrão de venda direta.
- Público Morno (Meio): sabe que tem o problema, está comparando soluções. Diferencie, apresente autoridade e valide com provas sociais ou resultados.
- Público Quente (Fundo): pronto para comprar, só precisa de um empurrão. Remova objeções, destaque urgência/escassez e facilite a decisão.

GATILHO MENTAL — deve ser o fio condutor do texto inteiro, não apenas uma menção:
- Urgência: prazo real se esgotando, decisão agora ou perde.
- Escassez: vagas/unidades limitadas, exclusividade.
- Prova Social: números, depoimentos, resultados de outros clientes.
- Autoridade: credenciais, anos de experiência, cases, certificações do especialista.
- Curiosidade: revelar algo inesperado, criar tensão cognitiva que o leitor precisa resolver.

TAMANHO — regra inviolável:
- Curta (Stories/Reels): 1 gancho + 1 benefício + CTA. Máximo 3 frases. Copy leve, ritmo acelerado.
- Média (Feed Meta): 3-4 parágrafos com gancho, desenvolvimento, prova e CTA. Tom conversacional.
- Longa (Texto Persuasivo): copy completa com gancho forte, identificação com a dor, apresentação da solução, provas, quebra de objeção e CTA poderoso. 600-1200 caracteres.

EMOJIS:
- Sim: use emojis estrategicamente para destacar benefícios e criar ritmo visual. Não exagere.
- Não: zero emojis. Texto limpo, sem nenhum caractere especial decorativo.

FRAMEWORKS — COMO APLICAR:
- AIDA: Bloco de Atenção → Interesse (contexto/dados) → Desejo (benefício emocional) → Ação (CTA direto).
- PAS: Nomear a dor sem rodeios → Agitar (consequências de ignorar) → Solução com o produto.
- Storytelling Rápido: micro-história em 3 atos (situação → virada → resultado) + CTA.
- Oferta Direta / Varejo: preço / desconto em destaque → benefício principal → urgência + CTA.
- Quebra de Objeção: validar a dúvida do remarketing → rebater com prova/garantia → CTA urgente.
- Roteiro de Vídeo: gancho visual nos 3s → desenvolvimento em tópicos falados → CTA final.
"""

_COPYS_PLATFORM_HINTS = {
    "Meta Ads (Facebook/Instagram)": (
        "Formato Meta Ads: separe o texto em 3 partes com os rótulos exatos: "
        "[TEXTO PRINCIPAL] (copy principal, pode ser longa), "
        "[TÍTULO] (máx 40 chars, impacto imediato), "
        "[DESCRIÇÃO] (máx 30 chars, complemento do título)."
    ),
    "Google Ads (Rede de Pesquisa)": (
        "Formato Google Ads: gere exatamente com os rótulos: "
        "[TÍTULO 1] (máx 30 chars), [TÍTULO 2] (máx 30 chars), [TÍTULO 3] (máx 30 chars), "
        "[DESCRIÇÃO 1] (máx 90 chars), [DESCRIÇÃO 2] (máx 90 chars). "
        "Inclua a palavra-chave principal nos títulos. Conte os caracteres com rigor."
    ),
    "TikTok Ads": (
        "Formato TikTok: gancho nos primeiros 3 segundos é CRÍTICO. "
        "Texto principal curto (máx 100 chars), linguagem jovem e ritmo acelerado. "
        "Separe: [LEGENDA] e [TEXTO NA TELA] (se roteiro)."
    ),
    "YouTube In-Stream": (
        "Formato YouTube In-Stream: os primeiros 5 segundos determinam se o usuário pula. "
        "Use os rótulos de tempo: [0-5s GANCHO], [6-15s DESENVOLVIMENTO], [16-30s OFERTA+CTA]."
    ),
}

@bp.route("/api/copys/gerar", methods=["POST"])
@login_required
def api_copys_gerar():
    data              = request.get_json() or {}
    plataforma        = (data.get("plataforma")       or "Meta Ads (Facebook/Instagram)").strip()
    framework         = (data.get("framework")        or "AIDA").strip()
    tom               = (data.get("tom")              or "Curto, Seco e Direto ao Ponto").strip()
    nicho             = (data.get("nicho")            or "").strip()
    oferta            = (data.get("oferta")           or "").strip()
    profissao         = (data.get("profissao")        or "").strip()
    nivel_consciencia = (data.get("nivel_consciencia") or "Público Frio (Topo)").strip()
    gatilho           = (data.get("gatilho")          or "Urgência").strip()
    tamanho           = (data.get("tamanho")          or "Média (Feed)").strip()
    cta               = (data.get("cta")              or "").strip()
    usar_emojis       = data.get("usar_emojis", False)
    variacao          = data.get("variacao", False)

    if len(oferta) < 10:
        return jsonify({"error": "Descreva melhor a oferta / produto (mínimo 10 caracteres)."}), 400

    platform_hint = _COPYS_PLATFORM_HINTS.get(plataforma, "")
    emoji_instrucao = "Sim — use emojis estrategicamente" if usar_emojis else "Não — zero emojis, texto 100% limpo"

    linhas = [
        "═══ BRIEFING DA COPY ═══",
        f"Plataforma: {plataforma}",
        platform_hint,
        f"Framework / Estrutura: {framework}",
        f"Tom de Voz: {tom}",
        f"Nível de Consciência do Público: {nivel_consciencia}",
        f"Gatilho Mental Foco: {gatilho}",
        f"Tamanho da Copy: {tamanho}",
        f"Usar Emojis: {emoji_instrucao}",
        f"Especialista / Profissão: {profissao if profissao else 'Não informado'}",
        f"Nicho / Público-Alvo: {nicho if nicho else 'Geral'}",
        f"A Oferta / Produto: {oferta}",
        f"CTA Exato a usar: {cta if cta else 'Crie um CTA adequado ao contexto'}",
        "",
    ]

    if variacao:
        linhas.append(
            "INSTRUÇÃO ESPECIAL — VARIAÇÃO A/B: Crie uma copy com ângulo COMPLETAMENTE DIFERENTE "
            "da geração anterior. Mude o gancho de entrada, a estrutura narrativa, o vocabulário e "
            "a abordagem emocional. O objetivo é gerar uma alternativa para teste A/B que transmita "
            "a mesma oferta por um caminho totalmente diferente. Surpreenda."
        )
    else:
        linhas.append("Gere agora a copy de alta conversão seguindo EXATAMENTE todas as especificações acima.")

    user_msg = "\n".join(filter(None, linhas))

    client = anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada no servidor."}), 500

    try:
        ctx = brain.contexto(nicho)
        system_prompt = _COPYS_SYSTEM
        if ctx:
            system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        copy_text = (msg.content[0].text or "").strip()
        if not copy_text:
            return jsonify({"error": "A IA retornou uma resposta vazia."}), 500
        brain.salvar(
            modulo="Copys",
            titulo=f"Copy {plataforma} {framework}",
            inputs={
                "plataforma": plataforma,
                "framework": framework,
                "tom": tom,
                "nicho": nicho,
                "oferta": oferta,
                "profissao": profissao,
                "nivel_consciencia": nivel_consciencia,
                "gatilho": gatilho,
                "tamanho": tamanho,
            },
            output=copy_text,
            model="claude-sonnet-4-6",
            cliente=nicho,
        )
        return jsonify({"copy": copy_text, "variacao": variacao})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# ── API: Meta Insights para Relatórios ──────────────────────────────────────
import re as _re

_meta_insights_cache: dict = {}   # account_id → {"ts": float, "data": dict}
_META_CACHE_TTL = 1800            # 30 minutos

# Tokens por agência (expansível)
_META_TOKENS = {
    "piloti": lambda: os.environ.get("META_TOKEN_PILOTI", "").strip(),
}

def api_relatorios_insights(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    cache_key = f"{agency}:{account_id}"
    now = time.time()
    if cache_key in _meta_insights_cache:
        cached = _meta_insights_cache[cache_key]
        if now - cached["ts"] < _META_CACHE_TTL:
            return jsonify(cached["data"])

    token_fn = _META_TOKENS.get(agency)
    token = token_fn() if token_fn else ""
    if not token:
        return jsonify({"error": f"Token da agência '{agency}' não configurado"}), 500

    def _find_action(arr, *types):
        """Percorre um array de actions e retorna o value do primeiro type encontrado."""
        for entry in (arr or []):
            if entry.get("action_type") in types:
                try:
                    return float(entry.get("value", 0) or 0)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/insights",
            params={
                "fields": "spend,impressions,clicks,reach,cpm,ctr,frequency,"
                          "actions,cost_per_action_type",
                "date_preset": "last_7d",
                "access_token": token,
            },
            timeout=15,
        )
        if not r.ok:
            err = r.json().get("error", {})
            return jsonify({"error": err.get("message", f"Meta API {r.status_code}")}), 502

        data = r.json().get("data", [])
        if not data:
            result = {
                "spend": 0.0, "impressions": 0, "clicks": 0, "reach": 0,
                "leads": 0,          "lead_cost": 0.0,
                "messaging": 0,      "messaging_cost": 0.0,
                "profile_visits": 0, "profile_visit_cost": 0.0,
                "purchases": 0,
                "ctr": "0.00", "cpm": "0.00", "frequency": "1.00", "empty": True,
            }
            _meta_insights_cache[cache_key] = {"ts": now, "data": result}
            return jsonify(result)

        row      = data[0]
        actions  = row.get("actions") or []
        costs    = row.get("cost_per_action_type") or []

        # ── Extrações com fallback seguro ────────────────────────────
        leads          = int(_find_action(actions, "lead"))
        lead_cost      = _find_action(costs,   "lead")

        profile_visits      = int(_find_action(actions, "instagram_profile_visit"))
        profile_visit_cost  = _find_action(costs,   "instagram_profile_visit")

        # Fallback: campanhas OUTCOME_TRAFFIC (Turbinar/boost) reportam visitas como link_click
        if profile_visits == 0:
            try:
                # Passo 1: pega IDs das campanhas OUTCOME_TRAFFIC
                rc = requests.get(
                    f"https://graph.facebook.com/v21.0/{account_id}/campaigns",
                    params={"fields": "objective", "access_token": token},
                    timeout=10,
                )
                traffic_ids = [
                    c["id"] for c in rc.json().get("data", [])
                    if c.get("objective") == "OUTCOME_TRAFFIC"
                ]
                # Passo 2: query direta de insights por campanha (evita dados incorretos do embed)
                traffic_clicks = 0
                traffic_spend  = 0.0
                for cid in traffic_ids:
                    ri = requests.get(
                        f"https://graph.facebook.com/v21.0/{cid}/insights",
                        params={
                            "fields": "spend,actions",
                            "date_preset": "last_7d",
                            "access_token": token,
                        },
                        timeout=10,
                    )
                    ri_row = (ri.json().get("data") or [{}])[0]
                    traffic_clicks += int(_find_action(ri_row.get("actions") or [], "link_click"))
                    traffic_spend  += float(ri_row.get("spend", 0) or 0)
                print(f"[Jake debug] traffic_ids={traffic_ids} clicks={traffic_clicks} spend={traffic_spend}")
                if traffic_clicks > 0:
                    profile_visits     = traffic_clicks
                    profile_visit_cost = traffic_spend / traffic_clicks
            except Exception as _e:
                print(f"[Jake debug] fallback erro: {_e}")

        messaging      = int(_find_action(
            actions,
            "onsite_conversion.messaging_conversation_started_7d",
            "onsite_conversion.messaging_conversation_started",
        ))
        messaging_cost = _find_action(
            costs,
            "onsite_conversion.messaging_conversation_started_7d",
            "onsite_conversion.messaging_conversation_started",
        )

        purchases = int(_find_action(actions, "purchase", "omni_purchase"))

        # Diagnóstico: todos os action_types retornados
        raw_actions = {a.get("action_type"): a.get("value") for a in actions}

        result = {
            "spend":              float(row.get("spend", 0) or 0),
            "impressions":        int(row.get("impressions", 0) or 0),
            "clicks":             int(row.get("clicks", 0) or 0),
            "reach":              int(row.get("reach", 0) or 0),
            "leads":              leads,
            "lead_cost":          lead_cost,
            "messaging":          messaging,
            "messaging_cost":     messaging_cost,
            "profile_visits":     profile_visits,
            "profile_visit_cost": profile_visit_cost,
            "purchases":          purchases,
            "ctr":                row.get("ctr", "0.00"),
            "cpm":                row.get("cpm", "0.00"),
            "frequency":          row.get("frequency", "1.00"),
            "_actions":           raw_actions,
        }
        _meta_insights_cache[cache_key] = {"ts": now, "data": result}
        return jsonify(result)

    except requests.Timeout:
        return jsonify({"error": "Timeout na Meta API"}), 504
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# ── API: Debug — action_types brutos de uma conta Meta ──────────────────────
def api_relatorios_debug(agency, account_id):
    import re as _re2
    if not _re2.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID inválido"}), 400
    token_fn = _META_TOKENS.get(agency)
    token = token_fn() if token_fn else ""
    if not token:
        return jsonify({"error": f"Token da agência '{agency}' não configurado"}), 500
    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/insights",
            params={
                "fields": "spend,actions,cost_per_action_type",
                "date_preset": "last_7d",
                "access_token": token,
            },
            timeout=15,
        )
        data = r.json().get("data", [])
        if not data:
            return jsonify({"info": "Sem dados nos últimos 7 dias", "raw": r.json()})
        row = data[0]
        account_result = {
            "nivel": "conta",
            "spend": row.get("spend"),
            "actions": row.get("actions", []),
            "cost_per_action_type": row.get("cost_per_action_type", []),
        }

        # Busca também por campanha para encontrar dados de Turbinar/boost
        r2 = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/campaigns",
            params={
                "fields": "name,objective,insights.date_preset(last_7d){spend,actions,cost_per_action_type}",
                "access_token": token,
            },
            timeout=15,
        )
        campaigns = []
        for c in r2.json().get("data", []):
            ins = (c.get("insights") or {}).get("data", [{}])
            ins_row = ins[0] if ins else {}
            if float(ins_row.get("spend", 0) or 0) > 0:
                campaigns.append({
                    "nome": c.get("name"),
                    "objetivo": c.get("objective"),
                    "spend": ins_row.get("spend"),
                    "actions": ins_row.get("actions", []),
                    "cost_per_action_type": ins_row.get("cost_per_action_type", []),
                })

        return jsonify({"account": account_result, "campaigns": campaigns})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# ── Vault Obsidian — helpers ────────────────────────────────────────────────

import unicodedata as _unicodedata

def _slug(name: str) -> str:
    """Normaliza nome para uso como path: lowercase, sem acentos, espaços→hífens."""
    n = _unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if _unicodedata.category(c) != "Mn")
    return _re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")

_VAULT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jake-brain", "Clientes")

def _vault_ler_contexto(nome: str) -> str:
    """Lê o .md mais recente de jake-brain/Clientes/<slug>/Performance/"""
    slug = _slug(nome)
    pasta = os.path.join(_VAULT_ROOT, slug, "Performance")
    if not os.path.isdir(pasta):
        return ""
    arquivos = sorted([f for f in os.listdir(pasta) if f.endswith(".md")], reverse=True)
    if not arquivos:
        return ""
    try:
        with open(os.path.join(pasta, arquivos[0]), encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def _vault_salvar_snapshot(nome: str, metricas: dict, metricas_anterior: dict, delta: dict, analise: str):
    """Salva snapshot semanal em jake-brain/Clientes/<slug>/Performance/YYYY-WXX.md"""
    from datetime import date
    slug  = _slug(nome)
    pasta = os.path.join(_VAULT_ROOT, slug, "Performance")
    os.makedirs(pasta, exist_ok=True)
    hoje   = date.today()
    semana = hoje.strftime("%Y-W%W")
    path   = os.path.join(pasta, f"{semana}.md")
    linhas_met = "\n".join(
        f"| {k} | {v} | {metricas_anterior.get(k,'--')} | {delta.get(k,'--')} |"
        for k, v in metricas.items()
    )
    conteudo = f"""# Performance — {nome} — {semana}

**Data de análise:** {hoje.isoformat()}

## Métricas
| Métrica | Atual | Anterior | Delta |
|---|---|---|---|
{linhas_met}

## Análise IA
{analise}
"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(conteudo)
    except Exception as e:
        print(f"[Jake vault] erro ao salvar snapshot: {e}")

# ── API: Análise IA para Relatórios ──────────────────────────────────────────
def api_relatorios_analise():
    data              = request.get_json() or {}
    nome              = (data.get("nome") or "").strip()
    metricas          = data.get("metricas") or {}
    metricas_anterior = data.get("metricas_anterior") or {}
    delta             = data.get("delta") or {}

    client = anthropic_client()
    if not client:
        return jsonify({"analise": ""})

    metricas_str = "\n".join(f"- {k}: {v}" for k, v in metricas.items())

    # Contexto histórico do vault Obsidian
    contexto_vault = _vault_ler_contexto(nome)
    bloco_vault = (
        f"\n\nContexto histórico do cliente (semanas anteriores):\n{contexto_vault[:800]}"
        if contexto_vault else ""
    )

    # Comparação com semana anterior
    bloco_anterior = ""
    if metricas_anterior:
        ant_str   = "\n".join(f"- {k}: {v}" for k, v in metricas_anterior.items())
        delta_str = "\n".join(f"- {k}: {v}" for k, v in delta.items()) if delta else ""
        bloco_anterior = (
            f"\n\nSemana anterior:\n{ant_str}"
            + (f"\n\nVariação (atual vs anterior):\n{delta_str}" if delta_str else "")
        )

    prompt = (
        f"Você é analista de tráfego pago. Gere uma análise BREVE (2-3 frases, máximo 140 palavras) "
        f"sobre os resultados das campanhas Meta Ads de '{nome}' nos últimos 7 dias.\n\n"
        f"Dados atuais:\n{metricas_str}"
        f"{bloco_anterior}"
        f"{bloco_vault}\n\n"
        f"Seja direto, profissional, em português brasileiro. "
        f"Destaque o principal resultado, compare com semana anterior se disponível, e dê UMA recomendação prática. "
        f"NÃO use markdown, asteriscos, negrito ou formatação. Apenas texto corrido simples."
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        analise = (msg.content[0].text or "").strip()
        if metricas:
            _vault_salvar_snapshot(nome, metricas, metricas_anterior, delta, analise)
        return jsonify({"analise": analise})
    except Exception as exc:
        return jsonify({"analise": "", "error": str(exc)})


# ── API: Performance — Saldo ────────────────────────────────────────────────

_perf_saldo_cache: dict = {}
_PERF_SALDO_TTL = 1800  # 30 min

def api_performance_saldo(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    token_fn = _META_TOKENS.get(agency)
    if not token_fn:
        return jsonify({"error": "Agência não encontrada"}), 404

    cache_key = f"saldo:{agency}:{account_id}"
    now = time.time()
    if cache_key in _perf_saldo_cache:
        cached = _perf_saldo_cache[cache_key]
        if now - cached["ts"] < _PERF_SALDO_TTL:
            return jsonify(cached["data"])

    token = token_fn()
    if not token:
        return jsonify({"error": "Token da agência não configurado"}), 500

    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}",
            params={"fields": "amount_spent,balance,spend_cap,currency", "access_token": token},
            timeout=15,
        )
        if not r.ok:
            err = r.json().get("error", {})
            return jsonify({"error": err.get("message", f"Meta API {r.status_code}")}), 502
        data = r.json()
        amount_spent = float(data.get("amount_spent", 0) or 0) / 100
        balance      = float(data.get("balance", 0) or 0) / 100
        spend_cap    = float(data.get("spend_cap", 0) or 0) / 100
        remaining    = max(0.0, spend_cap - amount_spent) if spend_cap else balance
        result = {
            "amount_spent": round(amount_spent, 2),
            "balance":      round(balance, 2),
            "spend_cap":    round(spend_cap, 2),
            "remaining":    round(remaining, 2),
            "currency":     data.get("currency", "BRL"),
            "alerta":       remaining < 200.0,
        }
        _perf_saldo_cache[cache_key] = {"ts": now, "data": result}
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── API: Performance — Alerta de Saldo ─────────────────────────────────────

_alerta_sent_cache: dict = {}  # account_id -> timestamp último envio
_ALERTA_TTL = 3600  # 1 hora

def api_performance_alerta_saldo():
    data       = request.get_json() or {}
    account_id = (data.get("account_id") or "").strip()
    nome       = (data.get("nome") or "conta").strip()
    agency     = (data.get("agency") or "").strip()
    saldo      = data.get("saldo", 0)

    now = time.time()
    last = _alerta_sent_cache.get(account_id, 0)
    if now - last < _ALERTA_TTL:
        return jsonify({"ok": True, "dedup": True})

    msg = f"⚠️ Patrão, saldo baixo em {nome} ({agency}): R$ {float(saldo):,.2f}"
    ok, detail = _send_telegram(msg)
    _alerta_sent_cache[account_id] = now
    return jsonify({"ok": ok, "detail": detail})


# ── API: Performance — Semana Anterior ─────────────────────────────────────

def _extract_insights_row(row: dict) -> dict:
    """Extrai métricas de uma linha de insights da Meta API."""
    actions = row.get("actions") or []
    costs   = row.get("cost_per_action_type") or []

    def _fa(arr, *types):
        for entry in (arr or []):
            if entry.get("action_type") in types:
                try:
                    return float(entry.get("value", 0) or 0)
                except Exception:
                    return 0.0
        return 0.0

    leads     = int(_fa(actions, "lead"))
    messaging = int(_fa(actions,
        "onsite_conversion.messaging_conversation_started_7d",
        "onsite_conversion.messaging_conversation_started"))
    purchases = int(_fa(actions, "purchase", "omni_purchase"))
    profile_visits = int(_fa(actions, "instagram_profile_visit"))
    spend     = float(row.get("spend", 0) or 0)

    return {
        "spend":          round(spend, 2),
        "impressions":    int(row.get("impressions", 0) or 0),
        "clicks":         int(row.get("clicks", 0) or 0),
        "reach":          int(row.get("reach", 0) or 0),
        "cpm":            row.get("cpm", "0.00"),
        "ctr":            row.get("ctr", "0.00"),
        "frequency":      row.get("frequency", "1.00"),
        "leads":          leads,
        "messaging":      messaging,
        "purchases":      purchases,
        "profile_visits": profile_visits,
    }


def _fetch_meta_period(account_id: str, token: str, since: str, until: str) -> dict:
    """Busca insights de um período específico (since/until em YYYY-MM-DD)."""
    r = requests.get(
        f"https://graph.facebook.com/v21.0/{account_id}/insights",
        params={
            "fields": "spend,impressions,clicks,reach,cpm,ctr,frequency,actions,cost_per_action_type",
            "time_range": '{"since":"' + since + '","until":"' + until + '"}',
            "access_token": token,
        },
        timeout=15,
    )
    if not r.ok:
        return {}
    data = r.json().get("data", [])
    if not data:
        return {"spend": 0, "impressions": 0, "clicks": 0, "reach": 0,
                "leads": 0, "messaging": 0, "purchases": 0, "profile_visits": 0,
                "cpm": "0.00", "ctr": "0.00", "frequency": "1.00"}
    return _extract_insights_row(data[0])


def api_performance_semana_anterior(agency, account_id):
    if not _re.match(r'^act_\d+$', account_id):
        return jsonify({"error": "ID de conta inválido"}), 400

    token_fn = _META_TOKENS.get(agency)
    if not token_fn:
        return jsonify({"error": "Agência não encontrada"}), 404
    token = token_fn()
    if not token:
        return jsonify({"error": "Token da agência não configurado"}), 500

    from datetime import date, timedelta
    today          = date.today()
    since_atual    = (today - timedelta(days=6)).isoformat()
    until_atual    = today.isoformat()
    since_anterior = (today - timedelta(days=13)).isoformat()
    until_anterior = (today - timedelta(days=7)).isoformat()

    try:
        atual    = _fetch_meta_period(account_id, token, since_atual, until_atual)
        anterior = _fetch_meta_period(account_id, token, since_anterior, until_anterior)
        return jsonify({"atual": atual, "anterior": anterior})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── API: Fábrica de Criativos (Texto + Imagem) ─────────────────────────────────

def _parse_creative_variants(raw: str) -> list[dict]:
    """
    Tenta extrair uma lista de {headline, subheadline} a partir de um JSON retornado pela IA.
    """
    try:
        raw = raw.strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("JSON não encontrado na resposta")
        slice_ = raw[start:end]
        parsed = json.loads(slice_)
        if not isinstance(parsed, list):
            raise ValueError("JSON não é uma lista")
        variants: list[dict] = []
        for item in parsed[:5]:
            hl = str(item.get("headline", "")).strip()
            sh = str(item.get("subheadline", "")).strip()
            if hl:
                variants.append({"headline": hl, "subheadline": sh})
        if not variants:
            raise ValueError("Nenhuma variação válida encontrada")
        while len(variants) < 5:
            variants.append(variants[-1])
        return variants
    except Exception as exc:  # pragma: no cover - diagnóstico
        print("[Jake] Erro ao parsear variantes de criativos:", exc, raw[:400])
        raise


def _generate_creative_texts(niche: str, campaign_focus: str, engine: str) -> list[dict]:
    focus_label = {
        "whatsapp": "campanhas de mensagem no WhatsApp (objetivo leads/contato)",
        "conversion": "conversões diretas (vendas/checkout)",
        "awareness": "reconhecimento de marca e lembrança",
    }.get(campaign_focus, "campanhas de mensagem no WhatsApp (objetivo leads/contato)")

    system_prompt = (
        "Você é um copywriter especialista em anúncios para Meta Ads focados em campanhas de mensagem.\n\n"
        "Gere EXATAMENTE 5 variações, cada uma com:\n"
        '- \"headline\": promessa curta, agressiva e clara (máx. 55 caracteres).\n'
        '- \"subheadline\": texto de apoio de 1 a 2 frases, focado em benefício e próximo da linguagem do público.\n\n'
        "Contexto:\n"
        f"- Público/nicho: {niche}\n"
        f"- Foco da campanha: {focus_label}\n\n"
        "Responda APENAS em JSON, no formato:\n\n"
        '[\n  { "headline": "...", "subheadline": "..." },\n  ... (total 5 itens)\n]\n'
    )

    if engine == "claude":
        client = anthropic_client()
        if not client:
            raise RuntimeError("ANTHROPIC_API_KEY não configurada para o motor de texto.")
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=900,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": "Gere as 5 variações em português brasileiro conforme instruções, respondendo apenas com o JSON.",
            }],
        )
        raw = (msg.content[0].text or "").strip()
        return _parse_creative_variants(raw)
    else:
        client = openai_client()
        if not client:
            raise RuntimeError("OPENAI_API_KEY não configurada para o motor de texto.")
        resp = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.8,
            max_tokens=900,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Gere as 5 variações em português brasileiro conforme instruções, em JSON."},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
        return _parse_creative_variants(raw)


def _file_to_data_url(f) -> str:
    """Converte um arquivo enviado via formulário em data URL."""
    content = f.read()
    mime = f.mimetype or "image/jpeg"
    b64 = base64.b64encode(content).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _generate_kontext(instruction: str, input_image_data_url: str, token: str) -> str:
    """Edita uma imagem com Flux Kontext Pro. Retorna URL da imagem editada."""
    headers = {**_replicate_headers(), "Prefer": "wait=120"}
    resp = requests.post(
        f"{_REPLICATE_BASE}/models/black-forest-labs/flux-kontext-pro/predictions",
        headers=headers,
        json={"input": {
            "prompt": instruction,
            "input_image": input_image_data_url,
            "output_format": "webp",
            "output_quality": 90,
        }},
        timeout=120,
    )
    if not resp.ok:
        raise ValueError(f"Replicate Kontext {resp.status_code}: {resp.text[:300]}")
    pred = resp.json()
    if pred.get("status") == "succeeded":
        out = pred.get("output")
        return out[0] if isinstance(out, list) else out
    get_url = (pred.get("urls") or {}).get("get", "")
    hdrs = {"Authorization": headers["Authorization"]}
    for _ in range(30):
        time.sleep(4)
        p = requests.get(get_url, headers=hdrs, timeout=15).json()
        if p.get("status") == "succeeded":
            out = p.get("output")
            return out[0] if isinstance(out, list) else out
        if p.get("status") == "failed":
            raise ValueError("Kontext: geração falhou")
    raise ValueError("Kontext: timeout")


def _generate_creative_images(mode: str, image_engine: str, prompt: str, image_file):
    """
    Gera até 5 imagens (ou reutiliza a mesma) dependendo do modo.
    Retorna lista de data URLs.
    """
    images: list[str] = []

    # Kontext: upload + instrução → edição consistente da imagem de referência
    if mode == "upload" and image_file and prompt:
        replicate_token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
        if replicate_token:
            try:
                image_file.seek(0)
                input_data_url = _file_to_data_url(image_file)
                edited_url = _generate_kontext(prompt, input_data_url, replicate_token)
                edited_data_url = _url_to_data_url(edited_url)
                return [edited_data_url] * 5
            except Exception as exc:
                print("[Jake] Kontext falhou, usando imagem original:", exc)
                image_file.seek(0)
        # fallback: devolve imagem original
        try:
            image_file.seek(0)
            data_url = _file_to_data_url(image_file)
            return [data_url] * 5
        except Exception as exc:
            print("[Jake] Erro ao converter imagem de upload:", exc)
            return []

    # Upload sem instrução: devolve a foto base em todos os criativos
    if mode == "upload" and image_file:
        try:
            data_url = _file_to_data_url(image_file)
            images = [data_url] * 5
            return images
        except Exception as exc:
            print("[Jake] Erro ao converter imagem de upload:", exc)
            return []

    # Prompt: gera uma imagem sintética e replica para os 5 cards.
    if mode == "prompt" and prompt:
        # 1️⃣ Flux 1.1 Pro via Replicate
        replicate_token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
        if replicate_token and image_engine == "flux":
            try:
                image_url = _generate_flux(prompt, replicate_token)
                data_url = _url_to_data_url(image_url)
                images = [data_url] * 5
                return images
            except Exception as flux_err:  # pragma: no cover - diagnóstico
                print("[Jake] Flux (Fábrica de Criativos) falhou, tentando fallback:", flux_err)

        # 2️⃣ Fallback com DALL-E 3 (ou uso como pseudo-Imagen 4)
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_key:
            try:
                client = OpenAI(api_key=openai_key)
                final_prompt = f"{prompt}. {_IMG_MASTER_STYLE}"
                resp = client.images.generate(
                    model="dall-e-3",
                    prompt=final_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                image_url = resp.data[0].url
                data_url = _url_to_data_url(image_url)
                images = [data_url] * 5
                return images
            except Exception as e:  # pragma: no cover - diagnóstico
                print("[Jake] DALL-E fallback (Fábrica de Criativos) falhou:", e)

    return images


@bp.route("/api/generate-creative", methods=["POST"])
@login_required
def api_generate_creative():
    """
    Endpoint da Fábrica de Criativos.

    Recebe multipart/form-data com:
    - mode: 'prompt' ou 'upload'
    - image_engine: 'flux' ou 'imagen4'
    - text_engine: 'claude' ou 'gpt4o'
    - campaign_focus: 'whatsapp' | 'conversion' | 'awareness'
    - niche: string
    - prompt: (se mode = prompt)
    - image: arquivo (se mode = upload)
    """
    mode = (request.form.get("mode") or "prompt").strip()
    image_engine = (request.form.get("image_engine") or "flux").strip()
    text_engine = (request.form.get("text_engine") or "claude").strip()
    campaign_focus = (request.form.get("campaign_focus") or "whatsapp").strip()
    niche = (request.form.get("niche") or "").strip()
    prompt = (request.form.get("prompt") or "").strip()
    image_file = request.files.get("image")

    if not niche:
        return jsonify({"error": "Preencha o público/nicho antes de gerar."}), 400

    if mode == "prompt" and not prompt:
        return jsonify({"error": "Descreva a cena do criativo (prompt)."}), 400

    if mode == "upload" and (not image_file or not image_file.filename):
        return jsonify({"error": "Envie uma imagem base no modo Upload."}), 400

    try:
        texts = _generate_creative_texts(niche, campaign_focus, text_engine)
    except Exception as exc:
        return jsonify({"error": f"Falha ao gerar textos: {exc}"}), 500

    try:
        images = _generate_creative_images(mode, image_engine, prompt, image_file)
    except Exception as exc:
        print("[Jake] Erro ao gerar imagens (Fábrica de Criativos):", exc)
        images = []

    creatives = []
    for i in range(5):
        t = texts[i] if i < len(texts) else texts[-1]
        img = images[i] if i < len(images) else (images[0] if images else None)
        creatives.append({
            "id": i + 1,
            "headline": t.get("headline", ""),
            "subheadline": t.get("subheadline", ""),
            "image": img,
        })

    # Detecta se o caminho Kontext foi usado
    effective_image_engine = image_engine
    if mode == "upload" and prompt:
        effective_image_engine = "kontext"

    return jsonify({
        "creatives": creatives,
        "meta": {
            "mode": mode,
            "image_engine": effective_image_engine,
            "text_engine": text_engine,
            "campaign_focus": campaign_focus,
        },
    })

# ── Engenheiro de Prompts ─────────────────────────────────────────────────────

_PROMPT_ENGINEER_SYSTEM = """Você é um Engenheiro de Prompts Sênior com mais de 20 anos de experiência criando prompts estruturados de alta performance para os mais diversos contextos: marketing, tecnologia, educação, jurídico, criativo, negócios e muito mais.

Seu fluxo de trabalho tem DUAS ETAPAS obrigatórias:

---

**ETAPA 1 — PERGUNTAS ESTRATÉGICAS**

Quando o usuário apresentar uma ideia ou projeto, você NUNCA gera o prompt direto. Primeiro, você faz de 5 a 7 perguntas estratégicas e objetivas para entender:
- O objetivo principal do prompt
- O público-alvo ou destinatário
- O contexto de uso (plataforma, ferramenta, situação)
- Tom e linguagem desejados
- Restrições ou requisitos específicos
- Exemplos de resultados esperados (se houver)

Formate as perguntas assim (JSON obrigatório):
{"type":"questions","questions":["Pergunta 1?","Pergunta 2?","Pergunta 3?","Pergunta 4?","Pergunta 5?"]}

---

**ETAPA 2 — GERAÇÃO DO PROMPT ESTRUTURADO**

Após o usuário responder, gere o prompt final:

{"type":"prompt","title":"Título descritivo curto (máx 50 chars)","prompt":"O prompt completo e estruturado aqui, rico em detalhes, com persona se aplicável, contexto, formato de saída esperado, restrições e exemplos relevantes."}

---

**REGRAS:**
- Responda SEMPRE em português brasileiro
- Nunca gere o prompt sem fazer as perguntas primeiro
- Se a resposta for insuficiente, faça perguntas de refinamento (mesma estrutura JSON)
- Fora dos JSONs, pode conversar normalmente — o texto será exibido como mensagem normal"""


@bp.route("/api/prompts/sessoes", methods=["GET"])
@login_required
def prompts_listar_sessoes():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, titulo, criado_em, atualizado_em FROM prompt_sessions "
            "ORDER BY atualizado_em DESC LIMIT 100"
        )
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify({"sessoes": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/prompts/sessoes", methods=["POST"])
@login_required
def prompts_criar_sessao():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO prompt_sessions (titulo) VALUES (NULL) RETURNING id, criado_em, atualizado_em"
        )
        row = dict(cur.fetchone())
        conn.commit()
        return jsonify(row)
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/prompts/sessoes/<int:sid>/mensagens", methods=["GET"])
@login_required
def prompts_listar_mensagens(sid):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, role, content, criado_em FROM prompt_messages "
            "WHERE session_id = %s ORDER BY criado_em ASC",
            (sid,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify({"mensagens": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/prompts/sessoes/<int:sid>/chat", methods=["POST"])
@login_required
def prompts_chat(sid):
    d = request.get_json() or {}
    user_msg = (d.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Mensagem vazia"}), 400

    conn = get_db()
    try:
        cur = conn.cursor()

        # Verifica que a sessão existe
        cur.execute("SELECT id FROM prompt_sessions WHERE id = %s", (sid,))
        if not cur.fetchone():
            return jsonify({"error": "Sessão não encontrada"}), 404

        # Carrega histórico
        cur.execute(
            "SELECT role, content FROM prompt_messages "
            "WHERE session_id = %s ORDER BY criado_em ASC",
            (sid,)
        )
        history = [{"role": r["role"], "content": r["content"]} for r in cur.fetchall()]

        # Adiciona nova mensagem do usuário ao histórico
        history.append({"role": "user", "content": user_msg})

        # Chama Claude
        client = _anthropic_client_46()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_PROMPT_ENGINEER_SYSTEM,
            messages=history
        )
        reply = response.content[0].text

        # Salva par user + assistant
        cur.execute(
            "INSERT INTO prompt_messages (session_id, role, content) VALUES (%s, %s, %s)",
            (sid, "user", user_msg)
        )
        cur.execute(
            "INSERT INTO prompt_messages (session_id, role, content) VALUES (%s, %s, %s)",
            (sid, "assistant", reply)
        )

        # Atualiza atualizado_em da sessão
        cur.execute(
            "UPDATE prompt_sessions SET atualizado_em = NOW() WHERE id = %s", (sid,)
        )
        conn.commit()
        return jsonify({"reply": reply})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/prompts/sessoes/<int:sid>/titulo", methods=["PATCH"])
@login_required
def prompts_atualizar_titulo(sid):
    d = request.get_json() or {}
    titulo = (d.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"error": "Título vazio"}), 400
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prompt_sessions SET titulo = %s, atualizado_em = NOW() WHERE id = %s",
            (titulo, sid)
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/prompts/sessoes/<int:sid>", methods=["DELETE"])
@login_required
def prompts_deletar_sessao(sid):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM prompt_sessions WHERE id = %s", (sid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ── Inicialização ────────────────────────────────────────────────────────────
def _local_ip():
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

# ── Prompt mestre cinematográfico ────────────────────────────────────────────
_IMG_MASTER_STYLE = (
    "Cinematic ultra-realistic editorial photograph, 8K. "
    "Hyperdetailed textures, dramatic chiaroscuro lighting — deep rich shadows contrasted with luminous practicals. "
    "Shot on Hasselblad medium format, 50mm f/1.4, shallow depth of field with smooth bokeh. "
    "Award-winning commercial photography, magazine cover quality. "
    "No text, no watermarks, no logos, no UI mockups."
)

def _carousel_image_style_suffix(style_visual: str, mix_reality: str, palette: str) -> str:
    """Monta sufixo de estilo para geração de imagem do carrossel."""
    style_map = {
        "editorial": "Editorial realista, revista de negócios, luz natural e composição limpa.",
        "luxo": "High fashion, moda e luxo, estética de campanha premium, tecidos e ambientes refinados.",
        "cyberpunk": "Futurista cyberpunk, neon, tecnologia e humano fundidos, cenários distópicos.",
        "documental": "Documentário, fotografia crua, realismo sem retoque excessivo.",
        "retrato": "Retrato editorial, foco no rosto e expressão, fundo suave.",
        "produto": "Fotografia de produto, foco no objeto, fundo neutro ou lifestyle.",
    }
    mix_map = {
        "leve": "Leve toque digital: reflexos ou partículas sutis, mantendo o real dominante.",
        "medio": "Mistura equilibrada: elementos digitais/holográficos integrados à cena real — dados, luzes volumétricas, UI flutuante.",
        "forte": "Mistura forte real × IA: cenário real com personagens ou objetos claramente digitais, hologramas, circuitos visíveis.",
    }
    palette_map = {
        "neutro": "Paleta neutra, tons de cinza e bege, destaque sutil em uma cor.",
        "quente": "Paleta quente: âmbar, dourado, laranja suave, sensação acolhedora.",
        "frio": "Paleta fria: azul, teal, prata, sensação tecnológica.",
        "neon": "Neon: roxo, rosa elétrico, ciano, alto contraste.",
        "pb": "Preto e branco, alto contraste, cinematográfico.",
    }
    a = style_map.get(style_visual or "", style_map["editorial"])
    b = mix_map.get(mix_reality or "", mix_map["medio"])
    c = palette_map.get(palette or "", palette_map["neutro"])
    return f"{a} {b} Colorização: {c}"

def _url_to_data_url(url: str) -> str:
    resp = requests.get(url, timeout=60)
    mime = resp.headers.get("content-type", "image/webp")
    b64  = base64.b64encode(resp.content).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def _generate_flux(prompt: str, token: str, style_suffix: str | None = None) -> str:
    """Generate image with Flux 1.1 Pro via Replicate. Returns image URL."""
    import time as _time
    final_prompt = f"{prompt}. {_IMG_MASTER_STYLE}"
    if style_suffix:
        final_prompt = f"{final_prompt}. {style_suffix}"
    resp = requests.post(
        "https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro/predictions",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "wait=60",
        },
        json={
            "input": {
                "prompt": final_prompt,
                "aspect_ratio": "4:5",
                "output_format": "webp",
                "output_quality": 92,
                "safety_tolerance": 2,
                "prompt_upsampling": True,
            }
        },
        timeout=75,
    )
    if not resp.ok:
        detail = ""
        try:
            data = resp.json()
            detail = str(data.get("detail") or data.get("error") or "")[:200]
        except Exception:
            detail = resp.text[:200]
        lower_detail = detail.lower()
        if resp.status_code == 429 or "throttled" in lower_detail or "rate limit" in lower_detail:
            raise RuntimeError(
                "Replicate: limite de velocidade atingido. "
                "Com saldo baixo (< US$5), o limite é de 6 requisições por minuto com burst de 1. "
                "Gere menos slides por vez (ex.: 1–3) ou espere alguns segundos antes de tentar novamente."
            )
        raise RuntimeError(f"Replicate {resp.status_code}: {detail}")

    pred = resp.json()
    # Synchronous path
    if pred.get("status") == "succeeded":
        out = pred.get("output")
        return (out[0] if isinstance(out, list) else out)

    # Async polling fallback
    get_url = (pred.get("urls") or {}).get("get")
    if get_url:
        for _ in range(25):
            _time.sleep(3)
            p = requests.get(get_url, headers={"Authorization": f"Bearer {token}"}, timeout=10).json()
            if p.get("status") == "succeeded":
                out = p.get("output")
                return (out[0] if isinstance(out, list) else out)
            if p.get("status") in ("failed", "canceled"):
                raise RuntimeError(f"Flux falhou: {p.get('error', 'desconhecido')}")
    raise RuntimeError("Flux: timeout após polling.")

# ── Geração de imagens (apenas Replicate / Flux 1.1 Pro) ─────────────────────
@bp.route("/api/carousel/generate-image", methods=["POST"])
@login_required
def api_carousel_generate_image():
    data         = request.get_json() or {}
    prompt       = (data.get("prompt") or "").strip()
    headline     = (data.get("headline") or "").strip()
    subheadline  = (data.get("subheadline") or "").strip()
    tag          = (data.get("tag") or "").strip()
    style_visual = (data.get("style_visual") or "").strip() or None
    mix_reality  = (data.get("mix_reality") or "").strip() or None
    palette      = (data.get("palette") or "").strip() or None
    modelo       = (data.get("modelo") or "flux-1.1-pro").strip()

    replicate_token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not replicate_token:
        return jsonify({"error": "Configure REPLICATE_API_TOKEN no .env para gerar imagens."}), 500

    # Gerar prompt via Claude se tiver contexto do slide
    if headline and not prompt:
        client = anthropic_client()
        if client:
            try:
                ctx = f"Headline: {headline}"
                if subheadline: ctx += f"\nSubheadline: {subheadline}"
                if tag:         ctx += f"\nTag/seção: {tag}"
                style_hint = style_visual or "editorial realista"
                msg = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=150,
                    messages=[{"role": "user", "content":
                        f"Crie um prompt de imagem em inglês para um slide de carrossel do Instagram com este conteúdo:\n{ctx}\n\n"
                        f"Estilo visual: {style_hint}. Paleta: {palette or 'neutro'}.\n"
                        f"Regras: sem texto na imagem, foco em composição visual impactante, "
                        f"fotorrealista ou semi-realista, formato quadrado (1:1). "
                        f"Retorne APENAS o prompt em inglês, sem explicações."
                    }],
                )
                prompt = (msg.content[0].text or "").strip()
            except Exception:
                pass

    if not prompt and headline:
        prompt = headline + (". " + subheadline if subheadline else "")

    if len(prompt) < 5:
        return jsonify({"error": "Prompt muito curto."}), 400

    style_suffix = _carousel_image_style_suffix(style_visual, mix_reality, palette)
    full_prompt  = (prompt + " " + style_suffix).strip()

    try:
        if modelo in _CRIATIVOS_MODELOS_IMAGEM:
            slug    = _CRIATIVOS_MODELOS_IMAGEM[modelo]
            headers = _replicate_headers()
            headers["Prefer"] = "wait=60"
            resp = requests.post(
                f"{_REPLICATE_BASE}/models/{slug}/predictions",
                headers=headers,
                json={"input": {"prompt": full_prompt, "aspect_ratio": "1:1",
                                "output_format": "png"}},
                timeout=90,
            )
            if not resp.ok:
                return jsonify({"error": f"Replicate {resp.status_code}: {resp.text[:300]}"}), 500
            pred = resp.json()
            if pred.get("status") == "succeeded":
                out = pred.get("output")
                image_url = out[0] if isinstance(out, list) else out
            else:
                # polling
                get_url = (pred.get("urls") or {}).get("get", "")
                hdrs = {"Authorization": headers["Authorization"]}
                image_url = None
                for _ in range(20):
                    time.sleep(3)
                    p = requests.get(get_url, headers=hdrs, timeout=15).json()
                    if p.get("status") == "succeeded":
                        out = p.get("output")
                        image_url = out[0] if isinstance(out, list) else out
                        break
                    if p.get("status") == "failed":
                        return jsonify({"error": "Replicate: geração falhou"}), 500
                if not image_url:
                    return jsonify({"error": "Timeout na geração da imagem"}), 500
        else:
            image_url = _generate_flux(full_prompt, replicate_token)

        data_url = _url_to_data_url(image_url)
        return jsonify({"dataUrl": data_url, "prompt": prompt, "model": modelo})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: Financeiro Pessoal — Análise IA ────────────────────────────────────
