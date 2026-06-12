import json
import os
import re as _re
import time

from flask import Blueprint, jsonify, request

from .shared import get_db, login_required, anthropic_client

bp = Blueprint('prompts', __name__)


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


