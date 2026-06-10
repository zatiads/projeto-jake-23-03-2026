import json
import os

import anthropic as _anthropic
from openai import OpenAI

from flask import Blueprint, jsonify, request

from .shared import get_db, login_required

bp = Blueprint('financeiro', __name__)


# ── API: Financeiro Pessoal — Análise IA ────────────────────────────────────
@bp.route("/api/financeiro/analise", methods=["POST"])
@login_required
def financeiro_analise():
    data = request.get_json(force=True) or {}
    mes        = data.get("mes", "este mês")
    receita    = data.get("receita", 0)
    despesas   = data.get("despesas", 0)
    saldo      = data.get("saldo", 0)
    receita_ant = data.get("receita_ant", 0)
    desp_ant   = data.get("desp_ant", 0)

    var_receita = ""
    if receita_ant > 0:
        pct = ((receita - receita_ant) / receita_ant) * 100
        var_receita = f"As receitas variaram {pct:+.1f}% em relação ao mês anterior."

    prompt = f"""Você é Jake, o assistente financeiro pessoal do Bruno. Analise os dados abaixo e forneça
uma análise direta, honesta e perspicaz sobre a saúde financeira em {mes}.
Use linguagem objetiva e tom de consultor financeiro. Máximo de 3 parágrafos curtos.

Dados de {mes}:
- Receita total: R$ {receita:,.2f}
- Despesas totais: R$ {despesas:,.2f}
- Saldo do mês: R$ {saldo:,.2f}
- Taxa de comprometimento: {(despesas/receita*100) if receita else 0:.1f}% da receita
- Comparativo: receita anterior R$ {receita_ant:,.2f} / despesas anteriores R$ {desp_ant:,.2f}
{var_receita}

CONTEXTO DO PLANO FINANCEIRO 2026 (use para contextualizar a análise):
- Meta principal: juntar R$ 30.000 até dezembro/2026 + vender carro atual por R$ 10k = comprar carro à vista
- Divisão ideal da sobra mensal: R$ 3.333 para reserva do carro (CDB liquidez diária XP) + restante para carteira de investimentos
- Carteira XP recomendada: 30% Tesouro Selic, 25% CDB, 15% LCI/LCA, 20% IVVB11, 10% GOLD11
- Roadmap R$1M: aportar R$ 2.500/mês a partir de jan/2027 (após comprar o carro)
- Regra de ouro: aporte sai no dia 5, antes de qualquer gasto. Não tocar na reserva do carro.

Com base no saldo deste mês, comente se o Bruno está no ritmo para bater a meta do carro.
Seja específico com os números. Dê pelo menos 1 recomendação prática alinhada ao plano."""

    ant_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if ant_key:
        try:
            client = _anthropic.Anthropic(api_key=ant_key)
            msg = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            analise = msg.content[0].text
            brain.salvar(
                modulo="Financeiro",
                titulo=f"Análise financeira {mes}",
                inputs={
                    "mes": mes,
                    "receita": receita,
                    "despesas": despesas,
                    "saldo": saldo,
                    "receita_anterior": receita_ant,
                    "despesas_anteriores": desp_ant,
                },
                output=analise,
                model="claude-sonnet-4-5",
            )
            return jsonify({"analise": analise})
        except Exception as e:
            pass

    if openai_key:
        try:
            client = OpenAI(api_key=openai_key)
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            analise = resp.choices[0].message.content
            brain.salvar(
                modulo="Financeiro",
                titulo=f"Análise financeira {mes}",
                inputs={
                    "mes": mes,
                    "receita": receita,
                    "despesas": despesas,
                    "saldo": saldo,
                    "receita_anterior": receita_ant,
                    "despesas_anteriores": desp_ant,
                },
                output=analise,
                model="gpt-4o",
            )
            return jsonify({"analise": analise})
        except Exception as e:
            pass

    # Fallback local
    saldo_emoji = "✅" if saldo >= 0 else "⚠️"
    taxa = (despesas / receita * 100) if receita else 0
    analise = (
        f"{saldo_emoji} Em <strong>{mes}</strong>, você faturou <strong>R$ {receita:,.2f}</strong> "
        f"e gastou <strong>R$ {despesas:,.2f}</strong>, resultando em saldo de "
        f"<strong>R$ {saldo:,.2f}</strong>. "
        f"Sua taxa de comprometimento foi de <strong>{taxa:.1f}%</strong> da receita."
    )
    return jsonify({"analise": analise})


# ── Financeiro: CRUD Transações ──────────────────────────────────────────────

@bp.route("/api/financeiro/transacoes", methods=["GET"])
@login_required
def financeiro_listar_transacoes():
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "SELECT id, descricao, valor, tipo, categoria, recorrente, data::text "
            "FROM fin_transacoes ORDER BY data DESC"
        )
        rows = cur.fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/financeiro/transacoes", methods=["POST"])
@login_required
def financeiro_criar_transacao():
    d = request.get_json() or {}
    for campo in ["descricao", "valor", "tipo", "categoria", "data"]:
        if not d.get(campo):
            return jsonify({"error": f"Campo obrigatório: {campo}"}), 400
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO fin_transacoes (descricao,valor,tipo,categoria,recorrente,data) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (d["descricao"], d["valor"], d["tipo"], d["categoria"],
             d.get("recorrente", False), d["data"])
        )
        novo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/financeiro/transacoes/<int:tid>", methods=["PUT"])
@login_required
def financeiro_atualizar_transacao(tid):
    d = request.get_json() or {}
    campos_validos = ["descricao", "valor", "tipo", "categoria", "recorrente", "data"]
    campos = {k: v for k, v in d.items() if k in campos_validos}
    if not campos:
        return jsonify({"error": "Nenhum campo válido"}), 400
    try:
        conn = get_db()
        cur  = conn.cursor()
        sets   = ", ".join(f"{k} = %s" for k in campos)
        valores = list(campos.values()) + [tid]
        cur.execute(f"UPDATE fin_transacoes SET {sets} WHERE id = %s", valores)
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/financeiro/transacoes/<int:tid>", methods=["DELETE"])
@login_required
def financeiro_deletar_transacao(tid):
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("DELETE FROM fin_transacoes WHERE id = %s", (tid,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Financeiro: CRUD Raio-X ──────────────────────────────────────────────────

@bp.route("/api/financeiro/raiox", methods=["GET"])
@login_required
def financeiro_get_raiox():
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT id, nome, grupo, valores FROM fin_raiox ORDER BY grupo, id")
        rows = cur.fetchall()
        conn.close()
        resultado = {"entradas": [], "fixas": [], "variaveis": []}
        for r in rows:
            resultado[r["grupo"]].append({
                "id": r["id"], "nome": r["nome"], "valores": r["valores"]
            })
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/financeiro/raiox", methods=["PUT"])
@login_required
def financeiro_salvar_raiox():
    d = request.get_json() or {}
    try:
        conn = get_db()
        cur  = conn.cursor()
        if not d:
            return jsonify({"error": "Payload vazio"}), 400
        cur.execute("DELETE FROM fin_raiox")
        for grupo in ["entradas", "fixas", "variaveis"]:
            for item in d.get(grupo, []):
                cur.execute(
                    "INSERT INTO fin_raiox (nome, grupo, valores) VALUES (%s, %s, %s)",
                    (item["nome"], grupo, json.dumps(item["valores"]))
                )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Financeiro: Aportes de Investimento ──────────────────────────────────────

_ATIVOS_VALIDOS = {"tesouro_selic", "cdb", "lci_lca", "ivvb11", "gold11"}


@bp.route("/api/financeiro/aportes", methods=["GET"])
@login_required
def financeiro_listar_aportes():
    try:
        conn = get_db()
        try:
            cur  = conn.cursor()
            cur.execute("""
                SELECT id, mes_ano::text, ativo, valor
                FROM aportes_investimento
                ORDER BY mes_ano DESC, id DESC
            """)
            rows = cur.fetchall()
        finally:
            conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/financeiro/aportes", methods=["POST"])
@login_required
def financeiro_criar_aporte():
    d = request.get_json(force=True) or {}
    mes_ano = d.get("mes_ano")
    ativo   = d.get("ativo")
    valor   = d.get("valor")
    if not mes_ano:
        return jsonify({"error": "mes_ano obrigatório"}), 400
    if not ativo:
        return jsonify({"error": "ativo obrigatório"}), 400
    if ativo not in _ATIVOS_VALIDOS and not ativo.startswith('custom_'):
        return jsonify({"error": f"ativo inválido: {ativo}"}), 400
    if ativo.startswith('custom_'):
        try:
            _conn = get_db()
            try:
                _cur = _conn.cursor()
                _cur.execute("SELECT key FROM ativos_personalizados WHERE key = %s", (ativo,))
                if not _cur.fetchone():
                    return jsonify({"error": f"ativo inválido: {ativo}"}), 400
            finally:
                _conn.close()
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    try:
        valor = float(valor)
        if valor <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "valor deve ser > 0"}), 400
    try:
        conn = get_db()
        try:
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO aportes_investimento (mes_ano, ativo, valor)
                VALUES (DATE_TRUNC('month', %s::date), %s, %s)
                RETURNING id
            """, (mes_ano, ativo, valor))
            novo_id = cur.fetchone()["id"]
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True, "id": novo_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/financeiro/aportes/<int:aid>", methods=["DELETE"])
@login_required
def financeiro_deletar_aporte(aid):
    try:
        conn = get_db()
        try:
            cur  = conn.cursor()
            cur.execute("DELETE FROM aportes_investimento WHERE id = %s", (aid,))
            conn.commit()
            rowcount = cur.rowcount
        finally:
            conn.close()
        if rowcount == 0:
            return jsonify({"error": "not found"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Financeiro: Ativos Personalizados ────────────────────────────────────────

_ATIVOS_FIXOS = [
    {"key": "tesouro_selic", "label": "Tesouro Selic", "cor": "#00e5ff", "meta": 30},
    {"key": "cdb",           "label": "CDB",           "cor": "#ffd740", "meta": 25},
    {"key": "lci_lca",       "label": "LCI/LCA",       "cor": "#69f0ae", "meta": 15},
    {"key": "ivvb11",        "label": "IVVB11",         "cor": "#ff5252", "meta": 20},
    {"key": "gold11",        "label": "GOLD11",         "cor": "#7c4dff", "meta": 10},
]
_KEYS_FIXAS   = {a["key"] for a in _ATIVOS_FIXOS}
_PALETA_CUSTOM = ['#ff8a65', '#ce93d8', '#80deea', '#a5d6a7', '#ffcc02', '#ef9a9a']


def _gerar_key_ativo(label):
    import re
    slug = re.sub(r'[^a-z0-9 ]', '', label.lower().strip())
    slug = re.sub(r'\s+', '_', slug).strip('_')
    return ('custom_' + slug)[:50]


@bp.route("/api/financeiro/ativos", methods=["GET"])
@login_required
def financeiro_listar_ativos():
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT key, label, cor, meta FROM ativos_personalizados ORDER BY id ASC")
            rows = cur.fetchall()
        finally:
            conn.close()
        result = [{**a, "fixo": True} for a in _ATIVOS_FIXOS]
        result += [{"key": r["key"], "label": r["label"], "cor": r["cor"],
                    "meta": float(r["meta"]), "fixo": False} for r in rows]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/financeiro/ativos", methods=["POST"])
@login_required
def financeiro_criar_ativo():
    d     = request.get_json(force=True) or {}
    label = (d.get("label") or "").strip()
    if not label:
        return jsonify({"error": "label obrigatório"}), 400
    if len(label) > 100:
        return jsonify({"error": "label muito longo (máx 100)"}), 400
    try:
        meta = float(d.get("meta") or 0)
        if not (0 <= meta <= 100):
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "meta deve ser entre 0 e 100"}), 400
    key = _gerar_key_ativo(label)
    if key in _KEYS_FIXAS:
        return jsonify({"error": f"Ativo com nome similar já existe (key: {key})"}), 400
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS n FROM ativos_personalizados")
            n = cur.fetchone()["n"]
            cor = _PALETA_CUSTOM[int(n) % len(_PALETA_CUSTOM)]
            cur.execute("""
                INSERT INTO ativos_personalizados (key, label, cor, meta)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (key) DO NOTHING
                RETURNING id
            """, (key, label, cor, meta))
            row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()
        if not row:
            return jsonify({"error": f"Ativo com nome similar já existe (key: {key})"}), 400
        ativo = {"key": key, "label": label, "cor": cor, "meta": meta, "fixo": False}
        return jsonify({"ok": True, "ativo": ativo})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/financeiro/ativos/<string:key>", methods=["DELETE"])
@login_required
def financeiro_deletar_ativo(key):
    if key in _KEYS_FIXAS:
        return jsonify({"error": "ativo fixo não pode ser removido"}), 400
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM ativos_personalizados WHERE key = %s", (key,))
            conn.commit()
            rowcount = cur.rowcount
        finally:
            conn.close()
        if rowcount == 0:
            return jsonify({"error": "not found"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: Site Architect — geração de landing page ─────────────────────────────
