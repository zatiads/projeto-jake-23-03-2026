import json
import os

from flask import Blueprint, Response, jsonify, request, send_file

from .shared import get_db, login_required

bp = Blueprint('gestor', __name__)


# ══════════════════════════════════════════════════════════════════════════
#  GESTOR IA — Agente autônomo de tráfego
# ══════════════════════════════════════════════════════════════════════════

def _gestor_db():
    """Retorna conexão ao banco com RealDictCursor (alias local para o gestor)."""
    return get_db()


@bp.route("/api/gestor/varreduras")
@login_required
def gestor_varreduras():
    """Lista execuções do gestor com status e contadores."""
    conn = None
    try:
        conn = _gestor_db(); cur = conn.cursor()
        cur.execute("""
            SELECT id, executado_em, contas_total, contas_ok, contas_acao, contas_erro,
                   duracao_seg, status
            FROM gestor_varreduras
            ORDER BY executado_em DESC
            LIMIT 30
        """)
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get("executado_em"):
                r["executado_em"] = r["executado_em"].isoformat()
        return jsonify({"varreduras": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: conn.close()
        except Exception: pass


@bp.route("/api/gestor/varreduras/<int:varredura_id>/resumo")
@login_required
def gestor_varredura_resumo(varredura_id):
    """Retorna resumo completo de uma varredura: cabeçalho + ações + alertas agrupados por conta."""
    conn = None
    try:
        conn = _gestor_db(); cur = conn.cursor()

        # Cabeçalho da varredura
        cur.execute("""
            SELECT id, executado_em, contas_total, contas_ok, contas_acao, contas_erro, duracao_seg, status
            FROM gestor_varreduras WHERE id = %s
        """, (varredura_id,))
        var = dict(cur.fetchone() or {})
        if not var:
            return jsonify({"error": "Varredura não encontrada"}), 404
        if var.get("executado_em"):
            var["executado_em"] = var["executado_em"].isoformat()

        # Ações (com número na varredura = aprovação pendente ou executada)
        cur.execute("""
            SELECT ga.id, ga.tipo, ga.entidade_nome, ga.motivo, ga.status,
                   ga.numero_na_varredura, ga.valor_antes, ga.valor_depois,
                   ga.aprovado_em, ga.cancelado_em, ga.expirado_em,
                   ga.revertido, ga.revertido_em,
                   acp.nome as cliente_nome, acp.agencia
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE ga.varredura_id = %s AND ga.numero_na_varredura IS NOT NULL
            ORDER BY ga.numero_na_varredura
        """, (varredura_id,))
        acoes = []
        for r in cur.fetchall():
            row = dict(r)
            for k in ("aprovado_em", "cancelado_em", "expirado_em", "revertido_em"):
                if row.get(k): row[k] = row[k].isoformat()
            acoes.append(row)

        # Alertas (sem número — apenas informativos)
        cur.execute("""
            SELECT ga.tipo, ga.entidade_nome, ga.motivo, acp.nome as cliente_nome, acp.agencia
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE ga.varredura_id = %s AND ga.numero_na_varredura IS NULL AND ga.tipo LIKE 'alerta%%'
            ORDER BY acp.agencia, acp.nome
        """, (varredura_id,))
        alertas = [dict(r) for r in cur.fetchall()]

        return jsonify({"varredura": var, "acoes": acoes, "alertas": alertas})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: conn.close()
        except Exception: pass


@bp.route("/api/gestor/acoes")
@login_required
def gestor_acoes():
    """Lista ações com filtros opcionais: ?agencia=piloti&tipo=pausar_ad&cliente_id=5&limit=50"""
    agencia    = request.args.get("agencia")
    tipo       = request.args.get("tipo")
    cliente_id = request.args.get("cliente_id")
    limit      = min(int(request.args.get("limit", 100)), 500)

    conn = None
    try:
        conn = _gestor_db(); cur = conn.cursor()
        where  = ["1=1"]
        params = []
        if agencia:
            where.append("acp.agencia = %s"); params.append(agencia)
        if tipo:
            where.append("ga.tipo = %s"); params.append(tipo)
        if cliente_id:
            where.append("ga.cliente_id = %s"); params.append(int(cliente_id))
        params.append(limit)

        # where list contains only hardcoded literals — no user data in f-string (safe)
        cur.execute(f"""
            SELECT ga.id, ga.varredura_id, ga.cliente_id, ga.account_id,
                   ga.executado_em, ga.tipo, ga.entidade_id, ga.entidade_nome,
                   ga.valor_antes, ga.valor_depois, ga.motivo,
                   ga.revertido, ga.revertido_em, ga.status,
                   acp.nome as cliente_nome, acp.agencia
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE {' AND '.join(where)}
            ORDER BY ga.executado_em DESC
            LIMIT %s
        """, params)

        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            for k in ("executado_em", "revertido_em"):
                if r.get(k):
                    r[k] = r[k].isoformat()
        return jsonify({"acoes": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: conn.close()
        except Exception: pass


@bp.route("/api/gestor/reverter/<int:acao_id>", methods=["POST"])
@login_required
def gestor_reverter(acao_id):
    """Reverte uma ação individual pelo ID."""
    try:
        import sys as _sys
        if "/root" not in _sys.path:
            _sys.path.insert(0, "/root")
        from meta.gestor.executor import reverter
        reverter(acao_id)
        return jsonify({"ok": True, "acao_id": acao_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/gestor/reverter-evento/<int:varredura_id>", methods=["POST"])
@login_required
def gestor_reverter_evento(varredura_id):
    """Reverte todas as ações reversíveis de uma varredura."""
    conn = None
    erros = []
    revertidas = 0
    try:
        conn = _gestor_db(); cur = conn.cursor()
        cur.execute("""
            SELECT id FROM gestor_acoes
            WHERE varredura_id = %s AND revertido = FALSE AND status = 'sucesso'
              AND tipo != 'alerta_saldo'
        """, (varredura_id,))
        ids = [r["id"] for r in cur.fetchall()]
        conn.close(); conn = None

        import sys as _sys
        if "/root" not in _sys.path:
            _sys.path.insert(0, "/root")
        from meta.gestor.executor import reverter

        for aid in ids:
            try:
                reverter(aid)
                revertidas += 1
            except Exception as e:
                erros.append({"acao_id": aid, "erro": str(e)})

        return jsonify({"revertidas": revertidas, "erros": erros})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except Exception: pass


@bp.route("/api/gestor/rodar", methods=["POST"])
@login_required
def gestor_rodar():
    """Dispara varredura manual em background. Retorna 202 imediatamente."""
    import sys as _sys
    if "/root" not in _sys.path:
        _sys.path.insert(0, "/root")

    def _run():
        try:
            from meta.gestor_agente import main
            main()
        except Exception as e:
            print(f"[gestor/rodar] erro: {e}", flush=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"ok": True, "msg": "Varredura iniciada em background"}), 202


@bp.route("/api/gestor/relatorios")
@login_required
def gestor_relatorios():
    """Lista PDFs gerados."""
    conn = None
    try:
        conn = _gestor_db(); cur = conn.cursor()
        cur.execute("""
            SELECT id, gerado_em, agencia, periodo_ini, periodo_fim, arquivo_path, tamanho_kb
            FROM gestor_relatorios
            ORDER BY gerado_em DESC
            LIMIT 50
        """)
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get("gerado_em"):
                r["gerado_em"] = r["gerado_em"].isoformat()
            for k in ("periodo_ini", "periodo_fim"):
                if r.get(k):
                    r[k] = r[k].isoformat()
        return jsonify({"relatorios": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: conn.close()
        except Exception: pass


@bp.route("/api/gestor/relatorios/<int:rel_id>/download")
@login_required
def gestor_relatorio_download(rel_id):
    """Download de um PDF pelo ID."""
    conn = None
    try:
        conn = _gestor_db(); cur = conn.cursor()
        cur.execute("SELECT arquivo_path, agencia, periodo_fim FROM gestor_relatorios WHERE id = %s", (rel_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Relatório não encontrado"}), 404
        caminho_abs = os.path.join(os.path.dirname(__file__), "static", row["arquivo_path"])
        if not os.path.exists(caminho_abs):
            return jsonify({"error": "Arquivo PDF não encontrado no disco"}), 404
        from flask import send_file
        return send_file(caminho_abs, as_attachment=True,
                         download_name=f"gestor_{row['agencia']}_{row['periodo_fim']}.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: conn.close()
        except Exception: pass


@bp.route("/api/gestor/contas")
@login_required
def gestor_contas():
    """Lista contas com saúde atual baseada nas últimas ações."""
    conn = None
    try:
        conn = _gestor_db(); cur = conn.cursor()
        cur.execute("""
            SELECT id, nome, agencia, account_id, token_key, campanha_tipo,
                   gestor_config_json, gestor_ativo
            FROM ad_client_profiles
            ORDER BY agencia, nome
        """)
        contas = [dict(r) for r in cur.fetchall()]

        for c in contas:
            cur.execute("""
                SELECT tipo, status, revertido, executado_em
                FROM gestor_acoes
                WHERE cliente_id = %s
                ORDER BY executado_em DESC LIMIT 1
            """, (c["id"],))
            ultima = cur.fetchone()
            if ultima and ultima["tipo"].startswith("alerta_"):
                c["saude"] = "alerta"
            elif ultima and ultima["status"] == "sucesso" and not ultima.get("revertido"):
                c["saude"] = "otimizada"
            else:
                c["saude"] = "saudavel"
            c["ultima_acao_em"] = ultima["executado_em"].isoformat() if ultima and ultima.get("executado_em") else None

        return jsonify({"contas": contas})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: conn.close()
        except Exception: pass


@bp.route("/api/gestor/contas/<int:cliente_id>", methods=["PATCH"])
@login_required
def gestor_conta_patch(cliente_id):
    """Atualiza gestor_config_json ou gestor_ativo de uma conta."""
    d = request.get_json() or {}
    if "gestor_ativo" not in d and "gestor_config_json" not in d:
        return jsonify({"error": "Nenhum campo reconhecido para atualizar"}), 400
    conn = None
    try:
        conn = _gestor_db(); cur = conn.cursor()
        if "gestor_ativo" in d:
            cur.execute("UPDATE ad_client_profiles SET gestor_ativo = %s WHERE id = %s",
                        (bool(d["gestor_ativo"]), cliente_id))
        if "gestor_config_json" in d:
            import json as _json
            cur.execute("UPDATE ad_client_profiles SET gestor_config_json = %s WHERE id = %s",
                        (_json.dumps(d["gestor_config_json"]), cliente_id))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Conta não encontrada"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: conn.close()
        except Exception: pass


