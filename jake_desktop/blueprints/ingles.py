import base64
import datetime
import json
import os
import tempfile

from flask import Blueprint, jsonify, request

from .shared import anthropic_client, get_db, login_required, openai_client

bp = Blueprint('ingles', __name__)


# ── Dados da trilha ──────────────────────────────────────────────────────────

INGLES_TRILHA = [
  {"id":1,"titulo":"Greetings & Introductions","descricao":"Como se apresentar e quebrar o gelo","icone":"👋","licoes":[
    {"id":1,"titulo":"First Meeting","objetivo":"Introduce yourself professionally","cenario":"You're meeting a new international business contact for the first time at a conference."},
    {"id":2,"titulo":"Small Talk","objetivo":"Keep a light conversation going","cenario":"You're waiting for a business meeting to start and chatting with someone you just met."},
    {"id":3,"titulo":"Video Call Intro","objetivo":"Introduce yourself on a video call","cenario":"You're starting a Zoom call with an international client for the first time."}
  ]},
  {"id":2,"titulo":"Daily Life","descricao":"Cotidiano, rotina e situações do dia a dia","icone":"🏠","licoes":[
    {"id":1,"titulo":"Your Routine","objetivo":"Describe your daily schedule","cenario":"A new English friend asks what your typical workday looks like."},
    {"id":2,"titulo":"Food & Cooking","objetivo":"Talk about food preferences and habits","cenario":"You're having lunch with an international colleague who asks about Brazilian food."},
    {"id":3,"titulo":"Weekend Plans","objetivo":"Make and discuss plans","cenario":"A friend asks what you did last weekend and what you plan to do next."}
  ]},
  {"id":3,"titulo":"Ordering & Service","descricao":"Pedir, reclamar e interagir com serviços","icone":"🍽️","licoes":[
    {"id":1,"titulo":"Restaurant","objetivo":"Order food and handle restaurant situations","cenario":"You're at a restaurant in New York. Order your meal, ask about the menu, and handle a wrong order."},
    {"id":2,"titulo":"Hotel","objetivo":"Check in and request hotel services","cenario":"You're checking into a hotel in Miami. Handle the check-in and request extra towels and a wake-up call."},
    {"id":3,"titulo":"Shopping","objetivo":"Shop, ask prices, handle problems","cenario":"You're shopping at a mall in the US. Find what you need, ask about sizes, and return an item."}
  ]},
  {"id":4,"titulo":"Travel","descricao":"Aeroporto, transporte e navegação","icone":"✈️","licoes":[
    {"id":1,"titulo":"At the Airport","objetivo":"Navigate check-in, security, boarding","cenario":"You're at JFK airport checking in for a flight. Handle check-in, baggage, and boarding questions."},
    {"id":2,"titulo":"Transportation","objetivo":"Use taxis, Uber, subway","cenario":"You just landed in London. Ask for directions to the hotel and use public transportation."},
    {"id":3,"titulo":"Asking Directions","objetivo":"Ask for and understand directions","cenario":"You're lost in downtown Chicago and need to find the nearest subway station."},
    {"id":4,"titulo":"Problem Solving","objetivo":"Handle travel problems (lost luggage, delays)","cenario":"Your luggage did not arrive and your connecting flight was delayed. Talk to airline staff."}
  ]},
  {"id":5,"titulo":"Work & Business","descricao":"Reuniões, apresentações e e-mails","icone":"💼","licoes":[
    {"id":1,"titulo":"Starting a Meeting","objetivo":"Open, manage and close business meetings","cenario":"You're running a video call with international partners. Open the meeting, set the agenda, manage turns."},
    {"id":2,"titulo":"Presenting Ideas","objetivo":"Present a proposal or campaign results","cenario":"You're presenting last month's ad campaign results to an international client."},
    {"id":3,"titulo":"Professional Emails","objetivo":"Discuss email writing and tone","cenario":"Your colleague asks you to help write a follow-up email to a client who did not respond."},
    {"id":4,"titulo":"Conference Calls","objetivo":"Participate actively in calls","cenario":"You're on a call with 3 international team members. Speak up, ask questions, summarize decisions."}
  ]},
  {"id":6,"titulo":"Job Interview","descricao":"Entrevistas e negociação de salário","icone":"🤝","licoes":[
    {"id":1,"titulo":"Tell Me About Yourself","objetivo":"Give a polished professional introduction","cenario":"You're in a job interview for a Senior Digital Marketing Manager role at a US company."},
    {"id":2,"titulo":"Strengths & Experience","objetivo":"Talk about skills and past work","cenario":"The interviewer asks about your biggest achievement and how you handled a difficult campaign."},
    {"id":3,"titulo":"Salary & Closing","objetivo":"Negotiate salary and ask questions","cenario":"The interview is ending. Discuss salary expectations and ask smart questions about the role."}
  ]},
  {"id":7,"titulo":"Health & Emergencies","descricao":"Médico, farmácia e situações de emergência","icone":"🏥","licoes":[
    {"id":1,"titulo":"Doctor Appointment","objetivo":"Describe symptoms and understand diagnosis","cenario":"You're at a clinic in the US with a bad headache and fever. Describe your symptoms to the doctor."},
    {"id":2,"titulo":"Pharmacy","objetivo":"Buy medicine and understand instructions","cenario":"You're at a pharmacy. Ask for medicine for a cold and understand the dosage instructions."},
    {"id":3,"titulo":"Emergency","objetivo":"Handle urgent situations clearly","cenario":"There has been a minor car accident. Call for help, explain the situation, and talk to police."}
  ]},
  {"id":8,"titulo":"Social & Entertainment","descricao":"Lazer, planos e conversas informais","icone":"🎉","licoes":[
    {"id":1,"titulo":"Making Plans","objetivo":"Suggest, accept and decline invitations","cenario":"An English-speaking friend wants to make weekend plans. Suggest activities, negotiate times."},
    {"id":2,"titulo":"Talking About Culture","objetivo":"Discuss movies, music, sports","cenario":"You're at a party and someone asks about your taste in movies, music and sports."},
    {"id":3,"titulo":"Dining Out","objetivo":"Socialize at events and dinners","cenario":"You're at a business dinner with international clients. Keep the conversation fun and professional."}
  ]},
  {"id":9,"titulo":"Digital Marketing in English","descricao":"Vocabulário e situações do marketing digital","icone":"📱","licoes":[
    {"id":1,"titulo":"Client Meeting","objetivo":"Present strategy to an international client","cenario":"You're meeting a US client to present a new paid traffic strategy for their brand."},
    {"id":2,"titulo":"Campaign Results","objetivo":"Report KPIs and metrics in English","cenario":"Present last month's Meta Ads results: CTR, ROAS, CPM. Explain what worked and what did not."},
    {"id":3,"titulo":"Creative Brief","objetivo":"Brief a creative team in English","cenario":"You're briefing a US-based creative team on a new campaign. Describe the audience, tone, and goals."},
    {"id":4,"titulo":"Tech & Tools","objetivo":"Discuss platforms and tools in English","cenario":"A new client asks you to explain how you use Meta Ads Manager and your reporting process."}
  ]},
  {"id":10,"titulo":"Advanced Business","descricao":"Negociação, pitching e situações difíceis","icone":"🚀","licoes":[
    {"id":1,"titulo":"Negotiation","objetivo":"Negotiate prices, terms, and contracts","cenario":"You're negotiating your agency's monthly retainer with a potential US client who wants a lower price."},
    {"id":2,"titulo":"Pitching","objetivo":"Pitch a project or your agency","cenario":"You have 5 minutes to pitch your digital marketing agency to a US investor. Make it compelling."},
    {"id":3,"titulo":"Handling Complaints","objetivo":"Manage difficult client situations","cenario":"A client is unhappy with last month's campaign results and threatens to leave. Handle it professionally."}
  ]},
  {"id":11,"titulo":"Idioms & Phrasal Verbs","descricao":"Expressões naturais do inglês falado","icone":"💡","licoes":[
    {"id":1,"titulo":"Business Idioms","objetivo":"Use common business idioms naturally","cenario":"You're in a casual meeting. Practice idioms: think outside the box, ballpark figure, touch base."},
    {"id":2,"titulo":"Phrasal Verbs","objetivo":"Use phrasal verbs in conversation","cenario":"Chat about work and life using: follow up, bring up, figure out, come up with."},
    {"id":3,"titulo":"Formal vs Informal","objetivo":"Switch between registers","cenario":"Talk casually with a friend, then shift to a formal tone for a client email on the same topic."}
  ]},
  {"id":12,"titulo":"Fluency Polish","descricao":"Storytelling, opinião e humor — nível avançado","icone":"🌟","licoes":[
    {"id":1,"titulo":"Storytelling","objetivo":"Tell engaging stories with detail and flow","cenario":"Tell a story about an interesting experience: a trip, a difficult client, or a funny situation."},
    {"id":2,"titulo":"Expressing Opinions","objetivo":"Argue and discuss confidently","cenario":"Debate: Is remote work better than office work? Give your opinion, support it, respond to counterpoints."},
    {"id":3,"titulo":"Natural & Humorous","objetivo":"Be relaxed and natural in English","cenario":"Have a completely free, casual conversation as if with a friend. No agenda - just be yourself."}
  ]}
]


# ── Constantes ───────────────────────────────────────────────────────────────

_INGLES_PALAVRAS_PROMPT = """Gere exatamente 10 palavras em inglês variadas e úteis para um brasileiro de nível intermediário que quer ser fluente.
Misture categorias: cotidiano, emoções, negócios, tecnologia, viagem, comida, natureza, idioms, phrasal verbs, relacionamentos.
Não repita categorias consecutivamente. Escolha palavras realmente úteis, não as mais óbvias.
Retorne SOMENTE um JSON array com 10 objetos (sem markdown):
[{"palavra": "...", "classe_gramatical": "noun|verb|adj|adv|phrase|idiom", "definicao_pt": "Definição clara em 1 frase", "exemplo_en": "Frase completa de exemplo", "fonetica": "/IPA/", "categoria": "..."}]"""

_INGLES_TEMAS_CONVERSA = ['marketing and advertising', 'travel and places', 'business and entrepreneurship', 'daily life and routines', 'technology and innovation']

_INGLES_CONVERSA_SYSTEM = """You are Jake, an English teacher for a Brazilian digital marketer at intermediate level.

Always respond with this EXACT JSON (no markdown, raw JSON only):
{{"en": "Your response in English (2-4 sentences, always end with a follow-up question)", "pt": "Tradução fiel em português do que você disse em 'en'", "versao_en": "If the user spoke Portuguese or mixed languages, show the correct English version of what they said. Format: You could say: '...'. If they spoke full English, return empty string."}}

Rules:
- 'en': natural English at intermediate level. When user makes grammar mistakes, model correct English in your response naturally without pointing out the error.
- 'pt': direct Portuguese translation of 'en' only — no extra text.
- 'versao_en': ONLY when user used Portuguese or Portuñol. Example: You could say: 'I've been working with paid traffic for 3 years.'
Today's topic: {tema}"""

_INGLES_TIPOS_ATIVIDADE = {"word_studied", "audio_played", "message_sent"}


# ── Rotas ────────────────────────────────────────────────────────────────────

@bp.route("/api/ingles/palavra-do-dia")
@login_required
def ingles_palavra_do_dia():
    conn = get_db()
    try:
        cur = conn.cursor()
        hoje = datetime.date.today()
        cur.execute("SELECT * FROM ingles_palavras WHERE data_exibicao = %s", (hoje,))
        row = cur.fetchone()
        if row:
            r = dict(row)
            if r.get("data_exibicao"):
                r["data_exibicao"] = str(r["data_exibicao"])
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])
            return jsonify(r)
        client = anthropic_client()
        if not client:
            return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500
        _categorias_legado = ['marketing', 'negocios', 'cotidiano', 'tecnologia']
        day_of_year = hoje.timetuple().tm_yday
        categoria = _categorias_legado[day_of_year % len(_categorias_legado)]
        _palavra_prompt_legado = (
            "Gere UMA palavra em inglês do vocabulário de {categoria} para um profissional de marketing digital "
            "brasileiro de nível intermediário.\nRetorne SOMENTE este JSON (sem markdown):\n"
            '{{\"palavra\": \"...\", \"classe_gramatical\": \"noun|verb|adj|adv|phrase\", '
            '\"definicao_pt\": \"Definição clara em português (1 frase)\", '
            '\"exemplo_en\": \"Exemplo de frase completa em inglês usando a palavra em contexto profissional\", '
            '\"fonetica\": \"/transcrição IPA/\"}}\n'
            "Escolha uma palavra útil mas não óbvia — não use palavras como 'marketing' ou 'business' que qualquer pessoa já conhece."
        )
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": _palavra_prompt_legado.format(categoria=categoria)}]
            )
            raw = msg.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            dados = json.loads(raw)
        except Exception as e:
            return jsonify({"error": f"Erro ao gerar palavra: {e}"}), 503
        cur.execute("""
            INSERT INTO ingles_palavras (palavra, classe_gramatical, definicao_pt, exemplo_en, fonetica, categoria, data_exibicao)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (data_exibicao) DO UPDATE SET palavra = EXCLUDED.palavra
            RETURNING id
        """, (
            dados.get("palavra"), dados.get("classe_gramatical"),
            dados.get("definicao_pt"), dados.get("exemplo_en"),
            dados.get("fonetica"), categoria, hoje
        ))
        novo_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({
            "id": novo_id,
            "palavra": dados.get("palavra"),
            "classe_gramatical": dados.get("classe_gramatical"),
            "definicao_pt": dados.get("definicao_pt"),
            "exemplo_en": dados.get("exemplo_en"),
            "fonetica": dados.get("fonetica"),
            "categoria": categoria,
            "data_exibicao": str(hoje),
            "estudada": False
        })
    finally:
        conn.close()


@bp.route("/api/ingles/palavras-do-dia")
@login_required
def ingles_palavras_do_dia():
    conn = get_db()
    try:
        cur = conn.cursor()
        hoje = datetime.date.today()
        cur.execute("SELECT COUNT(*) as count FROM ingles_palavras WHERE data_exibicao = %s", (hoje,))
        row = cur.fetchone()
        count = row["count"] if row else 0
        if count >= 10:
            cur.execute(
                "SELECT * FROM ingles_palavras WHERE data_exibicao = %s ORDER BY posicao",
                (hoje,)
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["data_exibicao"] = str(d["data_exibicao"])
                d["created_at"] = str(d["created_at"])
                rows.append(d)
            return jsonify(rows)
        client = anthropic_client()
        if not client:
            return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                messages=[{"role": "user", "content": _INGLES_PALAVRAS_PROMPT}]
            )
            raw = msg.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            palavras = json.loads(raw)
            if not isinstance(palavras, list):
                raise ValueError("Resposta não é array")
        except Exception as e:
            return jsonify({"error": f"Erro ao gerar palavras: {e}"}), 503
        try:
            cur.execute("DELETE FROM ingles_palavras WHERE data_exibicao = %s", (hoje,))
            for i, p in enumerate(palavras[:10], start=1):
                cur.execute("""
                    INSERT INTO ingles_palavras
                      (palavra, classe_gramatical, definicao_pt, exemplo_en, fonetica, categoria, data_exibicao, posicao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    p.get("palavra"), p.get("classe_gramatical"),
                    p.get("definicao_pt"), p.get("exemplo_en"),
                    p.get("fonetica"), p.get("categoria"),
                    hoje, i
                ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"error": f"Erro ao salvar palavras: {e}"}), 500
        cur.execute(
            "SELECT * FROM ingles_palavras WHERE data_exibicao = %s ORDER BY posicao",
            (hoje,)
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["data_exibicao"] = str(d["data_exibicao"])
            d["created_at"] = str(d["created_at"])
            rows.append(d)
        return jsonify(rows)
    finally:
        conn.close()


@bp.route("/api/ingles/palavra/audio")
@login_required
def ingles_palavra_audio():
    palavra = (request.args.get("palavra") or "").strip()
    if not palavra:
        return jsonify({"error": "Parâmetro 'palavra' obrigatório"}), 400
    client = openai_client()
    if not client:
        return jsonify({"error": "OPENAI_API_KEY não configurada"}), 500
    try:
        tts = client.audio.speech.create(model="tts-1", voice="onyx", input=palavra)
        audio_bytes = (getattr(tts, "content", None)
                       or (b"".join(tts.iter_bytes()) if hasattr(tts, "iter_bytes") else b""))
        return jsonify({"audio": base64.b64encode(audio_bytes).decode()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/ingles/sessoes")
@login_required
def ingles_listar_sessoes():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, tema, mensagens, created_at FROM ingles_sessoes ORDER BY created_at DESC LIMIT 10")
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["created_at"] = str(r["created_at"])
        return jsonify(rows)
    finally:
        conn.close()


@bp.route("/api/ingles/sessoes", methods=["POST"])
@login_required
def ingles_criar_sessao():
    day_of_year = datetime.date.today().timetuple().tm_yday
    tema = _INGLES_TEMAS_CONVERSA[day_of_year % len(_INGLES_TEMAS_CONVERSA)]
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ingles_sessoes (tema, mensagens) VALUES (%s, %s) RETURNING id",
            (tema, json.dumps([]))
        )
        novo_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"id": novo_id, "tema": tema, "mensagens": []})
    finally:
        conn.close()


@bp.route("/api/ingles/conversar/voz", methods=["POST"])
@login_required
def ingles_conversar_voz():
    audio_file = request.files.get("audio")
    sessao_id = request.form.get("sessao_id")
    if not audio_file:
        return jsonify({"error": "Campo 'audio' obrigatório"}), 400
    if not sessao_id:
        return jsonify({"error": "Campo 'sessao_id' obrigatório"}), 400

    oai = openai_client()
    if not oai:
        return jsonify({"error": "OPENAI_API_KEY não configurada"}), 500
    ant = anthropic_client()
    if not ant:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    suffix = ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        audio_file.save(tmp)
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as f:
            transcricao_obj = oai.audio.transcriptions.create(
                model="whisper-1", file=f, language="pt"
            )
        transcricao = transcricao_obj.text.strip()
    except Exception as e:
        return jsonify({"error": f"Erro Whisper: {e}"}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, tema, mensagens FROM ingles_sessoes WHERE id = %s", (int(sessao_id),))
        sessao = cur.fetchone()
        if not sessao:
            return jsonify({"error": "Sessão não encontrada"}), 404
        tema = sessao["tema"] or "daily life"
        mensagens_raw = sessao["mensagens"]
        if isinstance(mensagens_raw, list):
            mensagens = mensagens_raw
        else:
            mensagens = json.loads(mensagens_raw or "[]")

        mensagens.append({"role": "user", "content": transcricao})
        licao_context = request.form.get("licao_context", "").strip()
        if licao_context:
            system = (
                "You are Jake, an English teacher for a Brazilian at intermediate level.\n"
                "Lesson context: " + licao_context + "\n\n"
                "Always respond with this EXACT JSON (no markdown, raw JSON only):\n"
                "{\"en\": \"Your response in English (2-4 sentences + follow-up question)\", "
                "\"pt\": \"Tradução fiel em português do que você disse em 'en'\", "
                "\"versao_en\": \"If user spoke Portuguese or mixed, the correct English version. Format: You could say: '...'. Otherwise empty string.\"}\n\n"
                "Rules: 'en' = natural English, model correct grammar without pointing out errors. "
                "'pt' = direct translation of 'en'. 'versao_en' = only when user used Portuguese/Portuñol. "
                "You understand Portuguese but always respond in the JSON format above."
            )
        else:
            system = _INGLES_CONVERSA_SYSTEM.format(tema=tema)
        try:
            resp = ant.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=system,
                messages=mensagens
            )
            raw_resp = resp.content[0].text.strip()
            try:
                if raw_resp.startswith("```"):
                    raw_resp = raw_resp.split("```")[1]
                    if raw_resp.startswith("json"):
                        raw_resp = raw_resp[4:]
                parsed = json.loads(raw_resp)
                resposta_en = parsed.get("en", raw_resp)
                resposta_pt = parsed.get("pt", "")
                versao_en = parsed.get("versao_en", "")
            except Exception:
                resposta_en = raw_resp
                resposta_pt = ""
                versao_en = ""
        except Exception as e:
            return jsonify({"error": f"Erro Claude: {e}"}), 500

        mensagens.append({"role": "assistant", "content": resposta_en})

        cur.execute(
            "UPDATE ingles_sessoes SET mensagens = %s WHERE id = %s",
            (json.dumps(mensagens), int(sessao_id))
        )
        cur.execute(
            "INSERT INTO ingles_atividades (tipo, data_atividade) VALUES (%s, %s)",
            ("message_sent", datetime.date.today())
        )
        conn.commit()
    finally:
        conn.close()

    try:
        tts = oai.audio.speech.create(model="tts-1", voice="onyx", input=resposta_en)
        audio_bytes = (getattr(tts, "content", None)
                       or (b"".join(tts.iter_bytes()) if hasattr(tts, "iter_bytes") else b""))
    except Exception as e:
        return jsonify({"error": f"Erro TTS: {e}"}), 500

    return jsonify({
        "transcricao": transcricao,
        "resposta_en": resposta_en,
        "resposta_pt": resposta_pt,
        "versao_en": versao_en,
        "audio_base64": base64.b64encode(audio_bytes).decode()
    })


@bp.route("/api/ingles/sessoes/<int:sid>/chat", methods=["POST"])
@login_required
def ingles_chat(sid):
    data = request.get_json() or {}
    mensagem = (data.get("mensagem") or "").strip()
    if not mensagem:
        return jsonify({"error": "mensagem obrigatória"}), 400
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ingles_sessoes WHERE id = %s", (sid,))
        sessao = cur.fetchone()
        if not sessao:
            return jsonify({"error": "sessão não encontrada"}), 404
        sessao = dict(sessao)
        historico = sessao.get("mensagens") or []
        if isinstance(historico, str):
            historico = json.loads(historico)
        client = anthropic_client()
        if not client:
            return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500
        system = _INGLES_CONVERSA_SYSTEM.format(tema=sessao.get("tema", "general conversation"))
        msgs_api = [{"role": m["role"], "content": m["content"]} for m in historico]
        msgs_api.append({"role": "user", "content": mensagem})
        resp_claude = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=system,
            messages=msgs_api
        )
        resposta = resp_claude.content[0].text.strip()
        historico.append({"role": "user", "content": mensagem})
        historico.append({"role": "assistant", "content": resposta})
        cur.execute(
            "UPDATE ingles_sessoes SET mensagens = %s WHERE id = %s",
            (json.dumps(historico), sid)
        )
        cur.execute(
            "INSERT INTO ingles_atividades (tipo, data_atividade) VALUES (%s, %s)",
            ("message_sent", datetime.date.today())
        )
        conn.commit()
        return jsonify({"resposta": resposta, "mensagens": historico})
    finally:
        conn.close()


@bp.route("/api/ingles/atividade", methods=["POST"])
@login_required
def ingles_registrar_atividade():
    data = request.get_json() or {}
    tipo = data.get("tipo", "")
    if tipo not in _INGLES_TIPOS_ATIVIDADE:
        return jsonify({"error": f"tipo inválido. Use: {', '.join(_INGLES_TIPOS_ATIVIDADE)}"}), 400
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ingles_atividades (tipo, data_atividade) VALUES (%s, %s)",
            (tipo, datetime.date.today())
        )
        if tipo == "word_studied":
            cur.execute(
                "UPDATE ingles_palavras SET estudada = TRUE WHERE data_exibicao = %s",
                (datetime.date.today(),)
            )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.route("/api/ingles/progresso")
@login_required
def ingles_progresso():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM ingles_atividades WHERE tipo = 'word_studied'")
        total_palavras = (cur.fetchone() or {}).get("total", 0)
        cur.execute("""
            SELECT DISTINCT data_atividade
            FROM ingles_atividades
            ORDER BY data_atividade DESC
            LIMIT 60
        """)
        dias_ativos = [r["data_atividade"] for r in cur.fetchall()]
        streak = 0
        hoje = datetime.date.today()
        data_check = hoje
        for d in dias_ativos:
            if d == data_check:
                streak += 1
                data_check = data_check - datetime.timedelta(days=1)
            elif d < data_check:
                break
        mes_atual = hoje.month
        ano_atual = hoje.year
        calendario = [str(d) for d in dias_ativos if d.month == mes_atual and d.year == ano_atual]
        cur.execute("SELECT id, tema, created_at FROM ingles_sessoes ORDER BY created_at DESC LIMIT 5")
        sessoes = [{"id": r["id"], "tema": r["tema"], "created_at": str(r["created_at"])} for r in cur.fetchall()]
        return jsonify({
            "streak": streak,
            "total_palavras": total_palavras,
            "calendario": calendario,
            "ultimas_sessoes": sessoes
        })
    finally:
        conn.close()


@bp.route("/api/ingles/trilha")
@login_required
def ingles_get_trilha():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT modulo_id, licao_id, status FROM ingles_trilha_progresso")
        progresso = {(r["modulo_id"], r["licao_id"]): r["status"] for r in cur.fetchall()}
    finally:
        conn.close()
    resultado = []
    for modulo in INGLES_TRILHA:
        m = dict(modulo)
        licoes = []
        for l in modulo["licoes"]:
            li = dict(l)
            li["status"] = progresso.get((modulo["id"], l["id"]), "pending")
            licoes.append(li)
        m["licoes"] = licoes
        total = len(licoes)
        concluidas = sum(1 for li in licoes if li["status"] == "completed")
        m["progresso"] = {"total": total, "concluidas": concluidas}
        resultado.append(m)
    return jsonify(resultado)


@bp.route("/api/ingles/trilha/completar", methods=["POST"])
@login_required
def ingles_completar_licao():
    data = request.get_json() or {}
    modulo_id = data.get("modulo_id")
    licao_id = data.get("licao_id")
    if not modulo_id or not licao_id:
        return jsonify({"error": "modulo_id e licao_id obrigatorios"}), 400
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ingles_trilha_progresso (modulo_id, licao_id, status)
            VALUES (%s, %s, 'completed')
            ON CONFLICT (modulo_id, licao_id) DO UPDATE SET status = 'completed', completed_at = NOW()
        """, (int(modulo_id), int(licao_id)))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()
