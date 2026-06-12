import base64
import json
import os
import re as _re
import time

import requests

from flask import Blueprint, jsonify, request

from .shared import anthropic_client, get_db, login_required

bp = Blueprint('anuncios', __name__)


# ══════════════════════════════════════════════════════════════════════════
#  ABA SUBIR ANÚNCIOS — CRUD de perfis de clientes
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/api/anuncios/clientes", methods=["GET"])
@login_required
def anuncios_listar_clientes():
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, nome, agencia, account_id, token_key, page_id, business_id, link_url, whatsapp,
                   segmento, campanha_tipo, localizacao_json, publico_json,
                   orcamento_diario, campanha_id_existente, optimization_goal, pixel_id,
                   publico_salvo_id, publico_salvo_nome
            FROM ad_client_profiles ORDER BY agencia, nome
        """)
        rows = cur.fetchall()
        conn.close()
        return jsonify({"clientes": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/clientes", methods=["POST"])
@login_required
def anuncios_criar_cliente():
    d = request.get_json() or {}
    obrigatorios = ["nome", "agencia", "account_id", "token_key", "localizacao_json"]
    faltando = [f for f in obrigatorios if not d.get(f)]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios: {faltando}"}), 400
    if d["token_key"] not in _VALID_TOKEN_KEYS:
        return jsonify({"error": f"token_key inválido. Válidos: {list(_VALID_TOKEN_KEYS)}"}), 400
    if d["agencia"] not in ("piloti", "freelance"):
        return jsonify({"error": "agencia deve ser piloti ou freelance"}), 400

    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO ad_client_profiles
                (nome, agencia, account_id, token_key, page_id, business_id, link_url, whatsapp, segmento,
                 campanha_tipo, localizacao_json, publico_json, orcamento_diario,
                 campanha_id_existente, optimization_goal, pixel_id, publico_salvo_id, publico_salvo_nome)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            d["nome"], d["agencia"], d["account_id"], d["token_key"],
            d.get("page_id"), d.get("business_id"), d.get("link_url"), d.get("whatsapp"), d.get("segmento"),
            d.get("campanha_tipo", "MESSAGES"),
            json.dumps(d["localizacao_json"]),
            json.dumps(d.get("publico_json") or {}),
            d.get("orcamento_diario"), d.get("campanha_id_existente"),
            d.get("optimization_goal", "LINK_CLICKS"), d.get("pixel_id"),
            d.get("publico_salvo_id"), d.get("publico_salvo_nome")
        ))
        novo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/clientes/<int:cid>", methods=["PUT"])
@login_required
def anuncios_atualizar_cliente(cid):
    d = request.get_json() or {}
    if "token_key" in d and d["token_key"] not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400

    campos, valores = [], []
    mapa = {
        "nome": "nome", "agencia": "agencia", "account_id": "account_id",
        "token_key": "token_key", "page_id": "page_id", "business_id": "business_id",
        "link_url": "link_url", "whatsapp": "whatsapp", "segmento": "segmento", "campanha_tipo": "campanha_tipo",
        "orcamento_diario": "orcamento_diario", "campanha_id_existente": "campanha_id_existente",
        "optimization_goal": "optimization_goal", "pixel_id": "pixel_id",
        "publico_salvo_id": "publico_salvo_id", "publico_salvo_nome": "publico_salvo_nome"
    }
    for k, col in mapa.items():
        if k in d:
            campos.append(f"{col} = %s")
            valores.append(d[k])
    for jk in ("localizacao_json", "publico_json"):
        if jk in d:
            campos.append(f"{jk} = %s")
            valores.append(json.dumps(d[jk]))
    if not campos:
        return jsonify({"error": "Nenhum campo para atualizar"}), 400

    campos.append("atualizado_em = NOW()")
    valores.append(cid)
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute(f"UPDATE ad_client_profiles SET {', '.join(campos)} WHERE id = %s", valores)
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/clientes/<int:cid>/publicos-salvos", methods=["GET"])
@login_required
def anuncios_clientes_publicos_salvos(cid):
    """Lista públicos salvos da conta Meta do cliente."""
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT account_id, token_key FROM ad_client_profiles WHERE id=%s", (cid,))
        row = cur.fetchone()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if not row:
        return jsonify({"error": "Cliente não encontrado"}), 404
    account_id = row["account_id"]
    token_key  = row["token_key"]
    token      = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"Token {token_key} não configurado"}), 500
    try:
        resp = requests.get(
            f"{_meta_api.GRAPH_URL}/{account_id}/saved_audiences",
            params={"fields": "id,name", "access_token": token, "limit": 100},
            timeout=10,
        )
        data = resp.json()
        if "error" in data:
            return jsonify({"error": data["error"].get("message", "Erro Meta API")}), 400
        publicos = [{"id": p["id"], "nome": p["name"]} for p in data.get("data", [])]
        return jsonify({"publicos": publicos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/clientes/<int:cid>", methods=["DELETE"])
@login_required
def anuncios_deletar_cliente(cid):
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("DELETE FROM ad_client_profiles WHERE id = %s", (cid,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
#  ABA SUBIR ANÚNCIOS — CRUD de públicos salvos
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/api/anuncios/audiences")
@login_required
def audiences_listar():
    account_id = request.args.get("account_id", "").strip() or None
    try:
        conn = get_db(); cur = conn.cursor()
        if account_id:
            cur.execute("SELECT * FROM ad_audiences WHERE account_id=%s ORDER BY tipo, nome", (account_id,))
        else:
            cur.execute("SELECT * FROM ad_audiences ORDER BY account_id, tipo, nome")
        rows = cur.fetchall(); conn.close()
        return jsonify({"audiences": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/audiences", methods=["POST"])
@login_required
def audiences_criar():
    d = request.get_json() or {}
    for f in ("nome", "account_id", "token_key", "targeting_json"):
        if not d.get(f):
            return jsonify({"error": f"Campo obrigatório: {f}"}), 400
    if d.get("token_key") not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    tipo = d.get("tipo", "manual")
    if tipo not in ("manual", "salvo_meta", "custom_meta"):
        return jsonify({"error": "tipo inválido"}), 400
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO ad_audiences (nome, account_id, token_key, tipo, targeting_json, meta_audience_id)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
        """, (d["nome"], d["account_id"], d["token_key"], tipo,
              json.dumps(d["targeting_json"]), d.get("meta_audience_id")))
        novo_id = cur.fetchone()["id"]; conn.commit(); conn.close()
        return jsonify({"ok": True, "id": novo_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/audiences/<int:aid>", methods=["PUT"])
@login_required
def audiences_atualizar(aid):
    d = request.get_json() or {}
    campos, valores = [], []
    if "nome" in d:
        campos.append("nome = %s"); valores.append(d["nome"])
    if "targeting_json" in d:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT tipo FROM ad_audiences WHERE id=%s", (aid,))
        row = cur.fetchone(); conn.close()
        if row and row["tipo"] == "custom_meta":
            return jsonify({"error": "custom_meta: apenas nome pode ser editado"}), 400
        campos.append("targeting_json = %s"); valores.append(json.dumps(d["targeting_json"]))
    if not campos:
        return jsonify({"error": "Nenhum campo para atualizar"}), 400
    valores.append(aid)
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(f"UPDATE ad_audiences SET {', '.join(campos)} WHERE id=%s", valores)
        conn.commit(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/audiences/<int:aid>", methods=["DELETE"])
@login_required
def audiences_deletar(aid):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM ad_audiences WHERE id=%s", (aid,))
        conn.commit(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/audiences/importar", methods=["POST"])
@login_required
def audiences_importar():
    d = request.get_json() or {}
    account_id = d.get("account_id", "").strip()
    token_key  = d.get("token_key", "").strip()
    if not account_id or not token_key:
        return jsonify({"error": "account_id e token_key obrigatórios"}), 400
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    importados = atualizados = 0
    erros = []

    def _upsert(nome, tipo, targeting_j, meta_id):
        nonlocal importados, atualizados
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute("SELECT id FROM ad_audiences WHERE account_id=%s AND meta_audience_id=%s",
                        (account_id, meta_id))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE ad_audiences SET nome=%s, targeting_json=%s WHERE id=%s",
                            (nome, json.dumps(targeting_j), row["id"]))
                atualizados += 1
            else:
                cur.execute("""
                    INSERT INTO ad_audiences (nome, account_id, token_key, tipo, targeting_json, meta_audience_id)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (nome, account_id, token_key, tipo, json.dumps(targeting_j), meta_id))
                importados += 1
            conn.commit(); conn.close()
        except Exception as e:
            erros.append(f"{nome}: {e}")

    try:
        salvos = _meta_api.listar_publicos_salvos(token, account_id)
        for s in salvos:
            t = s.get("targeting") or {}
            geo = t.get("geo_locations") or {}
            targeting_j = {
                "age_min":   t.get("age_min", 18),
                "age_max":   t.get("age_max", 65),
                "genders":   t.get("genders", []),
                "countries": geo.get("countries", []),
                "cities":    [c.get("name", "") for c in geo.get("cities", [])],
            }
            _upsert(s["name"], "salvo_meta", targeting_j, s["id"])
    except Exception as e:
        erros.append(f"saved_audiences: {e}")

    try:
        customs = _meta_api.listar_custom_audiences(token, account_id)
        for c in customs:
            targeting_j = {"custom_audience_id": c["id"]}
            _upsert(f"{c['name']} ({c.get('subtype','?')})", "custom_meta", targeting_j, c["id"])
    except Exception as e:
        erros.append(f"custom_audiences: {e}")

    return jsonify({"ok": True, "importados": importados, "atualizados": atualizados, "erros": erros})


#  ABA SUBIR ANÚNCIOS — Meta API (campanhas, upload, copy, publicar)
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/api/anuncios/pages")
@login_required
def anuncios_listar_pages():
    token_key = request.args.get("token_key", "META_ACCESS_TOKEN")
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500
    business_id = request.args.get("business_id", "").strip() or None
    try:
        pages = _meta_api.listar_paginas(token, business_id=business_id)
        return jsonify({"pages": pages})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/campanhas/<account_id>")
@login_required
def anuncios_listar_campanhas(account_id):
    token_key = request.args.get("token_key", "META_ACCESS_TOKEN")
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500
    try:
        campanhas = _meta_api.listar_campanhas(token, account_id)
        return jsonify({"campanhas": campanhas})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/campanha/<campaign_id>/status", methods=["PATCH"])
@login_required
def anuncios_campanha_status(campaign_id):
    """Pausa ou ativa uma campanha Meta. Body: {status: 'PAUSED'|'ACTIVE', token_key: '...'}"""
    d         = request.get_json() or {}
    status    = (d.get("status") or "").strip().upper()
    token_key = (d.get("token_key") or "META_ACCESS_TOKEN").strip()

    if status not in ("PAUSED", "ACTIVE"):
        return jsonify({"error": "status deve ser PAUSED ou ACTIVE"}), 400
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    import re as _re_camp
    if not _re_camp.fullmatch(r'\d{10,20}', campaign_id):
        return jsonify({"error": "campaign_id inválido"}), 400

    try:
        resp = requests.post(
            f"https://graph.facebook.com/v21.0/{campaign_id}",
            params={"access_token": token},
            data={"status": status},
            timeout=15,
        )
        data = resp.json()
        if data.get("success"):
            return jsonify({"ok": True, "campaign_id": campaign_id, "status": status})
        return jsonify({"error": data.get("error", {}).get("message", "Erro desconhecido")}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/lote/drive-download", methods=["POST"])
@login_required
def anuncios_lote_drive_download():
    """Baixa arquivo de link público do Drive, faz upload para Meta e retorna creative_ref."""
    import re as _re
    from urllib.parse import urlparse, parse_qs
    d = request.get_json() or {}
    url        = (d.get("url") or "").strip()
    account_id = (d.get("account_id") or "").strip()
    token_key  = (d.get("token_key") or "META_ACCESS_TOKEN").strip()

    if not url:
        return jsonify({"error": "URL obrigatória"}), 400
    if not account_id:
        return jsonify({"error": "account_id obrigatório"}), 400
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    # Extrair file_id do link do Drive
    file_id = None
    m = _re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if m:
        file_id = m.group(1)
    elif "id=" in url:
        file_id = parse_qs(urlparse(url).query).get("id", [None])[0]
    if not file_id:
        return jsonify({"error": "URL inválida. Use um link no formato drive.google.com/file/d/ID/view"}), 400

    # Baixar arquivo diretamente do Drive (stream para detectar Content-Type antes de ler body)
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        resp = requests.get(download_url, stream=True, allow_redirects=True, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"error": f"Erro ao baixar arquivo: {e}"}), 400

    # Detectar arquivo não público (Drive retorna HTML com página de confirmação)
    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type:
        return jsonify({"error": "Arquivo não público ou requer confirmação. Compartilhe com 'qualquer pessoa com o link'"}), 400

    # Detectar tipo suportado via Content-Type
    _MIME_EXT = {
        "image/jpeg": ".jpg",
        "image/png":  ".png",
        "image/gif":  ".gif",
        "video/mp4":  ".mp4",
    }
    mime_base = content_type.split(";")[0].strip()
    ext = _MIME_EXT.get(mime_base)
    if not ext:
        return jsonify({"error": f"Tipo de arquivo não suportado: {mime_base}. Use JPG, PNG, GIF ou MP4."}), 400

    # Verificar tamanho antes de carregar (limite: 100 MB)
    _MAX_BYTES = 100 * 1024 * 1024
    content_length = resp.headers.get("Content-Length")
    if content_length and int(content_length) > _MAX_BYTES:
        return jsonify({"error": "Arquivo muito grande. Limite: 100 MB"}), 400

    content = b""
    for chunk in resp.iter_content(chunk_size=65536):
        content += chunk
        if len(content) > _MAX_BYTES:
            return jsonify({"error": "Arquivo muito grande. Limite: 100 MB"}), 400

    # Fazer upload direto para Meta (sem salvar em disco)
    try:
        if mime_base == "video/mp4":
            video_id = _meta_api.upload_video(token, account_id, content, f"lote_drive{ext}")
            creative_ref = {"tipo": "video", "video_id": video_id}
        else:
            resultado = _meta_api.upload_imagem(token, account_id, content, f"lote_drive{ext}")
            creative_ref = {"tipo": "imagem", "hash": resultado["hash"]}
    except Exception as e:
        return jsonify({"error": f"Erro ao enviar para Meta: {e}"}), 500

    return jsonify({"creative_ref": creative_ref, "mime": mime_base, "file_id": file_id, "ok": True})


@bp.route("/api/anuncios/wa/subir", methods=["POST"])
@login_required
def anuncios_wa_subir():
    """Endpoint para Jake WhatsApp: baixa Drive, salva tmp, prepara mc_token para stream."""
    import re as _re_wa
    from urllib.parse import urlparse as _urlparse_wa, parse_qs as _parse_qs_wa
    d              = request.get_json() or {}
    drive_url      = (d.get("drive_url") or "").strip()
    arquivo_local  = (d.get("arquivo_local") or "").strip()
    arquivos_locais = [a for a in (d.get("arquivos_locais") or []) if a]
    cliente_ids    = d.get("cliente_ids") or []
    orcamento_raw  = d.get("orcamento")
    campanha_nome  = (d.get("campanha_nome") or "").strip()
    campanha_tipo  = (d.get("campanha_tipo") or "MESSAGES").strip().upper()
    orcamento_por_conjunto_raw = d.get("orcamento_por_conjunto")
    publicos_salvos_por_cliente = d.get("publicos_salvos_por_cliente") or {}

    # Normalizar: arquivo_local avulso vai para a lista
    if arquivo_local and arquivo_local not in arquivos_locais:
        arquivos_locais.insert(0, arquivo_local)

    if not drive_url and not arquivos_locais:
        return jsonify({"error": "drive_url ou arquivo_local obrigatório"}), 400
    if not cliente_ids:
        return jsonify({"error": "cliente_ids obrigatório"}), 400
    if not campanha_nome:
        return jsonify({"error": "campanha_nome obrigatório"}), 400
    if campanha_tipo not in ("MESSAGES", "ENGAGEMENT", "PURCHASE"):
        return jsonify({"error": "campanha_tipo inválido"}), 400
    try:
        orcamento = float(orcamento_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "orcamento deve ser número"}), 400
    orcamento_por_conjunto = None
    if orcamento_por_conjunto_raw is not None:
        try:
            orcamento_por_conjunto = float(orcamento_por_conjunto_raw)
        except (TypeError, ValueError):
            pass

    _MIME_EXT_WA = {"image/jpeg": ".jpg", "image/png": ".png", "video/mp4": ".mp4"}

    if arquivos_locais:
        # Um ou mais arquivos já salvos localmente (enviados via WhatsApp)
        import re as _re_loc
        _EXT_MIME = {".jpg": "image/jpeg", ".png": "image/png", ".mp4": "video/mp4"}
        for arq in arquivos_locais:
            if not _re_loc.match(r'^/tmp/wa_media_[a-f0-9\-]+\.(jpg|png|mp4)$', arq):
                return jsonify({"error": f"arquivo_local inválido: {arq}"}), 400
            if not os.path.exists(arq):
                return jsonify({"error": f"Arquivo não encontrado. Reenvia: {arq}"}), 400
        ext_loc = os.path.splitext(arquivos_locais[0])[1].lower()
        mime_base = _EXT_MIME.get(ext_loc, "image/jpeg")
        ext = ext_loc
        tmp_uuid_val = str(uuid.uuid4())
        tmp_path = arquivos_locais[0]
    else:
        # Download do Google Drive
        file_id = None
        m = _re_wa.search(r'/file/d/([a-zA-Z0-9_-]+)', drive_url)
        if m:
            file_id = m.group(1)
        elif "id=" in drive_url:
            file_id = _parse_qs_wa(_urlparse_wa(drive_url).query).get("id", [None])[0]
        if not file_id:
            return jsonify({"error": "URL do Drive inválida. Use drive.google.com/file/d/ID/view"}), 400

        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        try:
            resp = requests.get(download_url, stream=True, allow_redirects=True, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            return jsonify({"error": f"Erro ao baixar do Drive: {e}"}), 400

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" in content_type:
            return jsonify({"error": "Arquivo não público. Compartilhe com 'qualquer pessoa com o link'"}), 400

        mime_base = content_type.split(";")[0].strip()
        ext = _MIME_EXT_WA.get(mime_base)
        if not ext:
            return jsonify({"error": f"Tipo não suportado: {mime_base}. Use JPG, PNG ou MP4"}), 400

        _MAX_WA = 100 * 1024 * 1024
        content = b""
        for chunk in resp.iter_content(chunk_size=65536):
            content += chunk
            if len(content) > _MAX_WA:
                return jsonify({"error": "Arquivo muito grande. Limite: 100 MB"}), 400

        tmp_uuid_val = str(uuid.uuid4())
        tmp_path = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{ext}")
        with open(tmp_path, "wb") as fh:
            fh.write(content)
        def _del_tmp():
            try: os.remove(tmp_path)
            except Exception: pass
        threading.Timer(3600, _del_tmp).start()

    # Buscar clientes no banco
    conn = None
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, agencia, account_id, token_key, page_id, link_url, whatsapp, "
            "campanha_tipo, optimization_goal, pixel_id, localizacao_json, publico_json, "
            "publico_salvo_id, publico_salvo_nome "
            "FROM ad_client_profiles WHERE id = ANY(%s)",
            (cliente_ids,)
        )
        clientes = [dict(c) for c in cur.fetchall()]
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar clientes: {e}"}), 500
    finally:
        try: conn.close()
        except Exception: pass

    if not clientes:
        return jsonify({"error": "Nenhum cliente encontrado"}), 404

    # Validar campos obrigatórios
    erros = []
    for c in clientes:
        if not c.get("page_id"):
            erros.append(f"{c['nome']}: page_id não configurado")
        if not c.get("account_id"):
            erros.append(f"{c['nome']}: account_id não configurado")
        if c.get("token_key") not in _VALID_TOKEN_KEYS:
            erros.append(f"{c['nome']}: token_key inválido")
    if erros:
        return jsonify({"error": "Clientes com configuração incompleta", "detalhes": erros}), 400

    # Armazenar payload para stream
    mc_token = str(uuid.uuid4())
    _lote_payloads[mc_token] = {
        "clientes":       clientes,
        "tmp_uuid":       tmp_uuid_val,
        "tmp_ext":        ext,
        "tmp_path":       tmp_path,
        "tmp_paths":      arquivos_locais if arquivos_locais else [tmp_path],
        "copy":              d.get("copy") or {},
        "copies_list":       d.get("copies_list") or [],
        "campanha_nome":     campanha_nome,
        "orcamento":         orcamento,
        "campanha_tipo":     campanha_tipo,
        "num_conjuntos":               d.get("num_conjuntos") or 1,
        "cri_por_conjunto":            d.get("cri_por_conjunto") or len(arquivos_locais if arquivos_locais else [tmp_path]),
        "orcamento_por_conjunto":      orcamento_por_conjunto,
        "publicos_salvos_por_cliente": publicos_salvos_por_cliente,
    }
    threading.Timer(1800, lambda: _lote_payloads.pop(mc_token, None)).start()

    return jsonify({"mc_token": mc_token, "clientes": len(clientes), "tipo": mime_base})


@bp.route("/api/anuncios/upload-criativo", methods=["POST"])
@login_required
def anuncios_upload_criativo():
    import re as _re
    tmp_uuid_val = request.form.get("tmp_uuid", "").strip()
    account_id   = request.form.get("account_id", "")
    token_key    = request.form.get("token_key", "META_ACCESS_TOKEN")
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    if not account_id:
        return jsonify({"error": "account_id obrigatório"}), 400
    token = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    # Caminho via tmp_uuid (criativo importado por URL)
    if tmp_uuid_val:
        if not _re.match(r'^[a-f0-9\-]{36}$', tmp_uuid_val):
            return jsonify({"error": "tmp_uuid inválido"}), 400
        matches = _glob.glob(os.path.join(_TMP_DIR, f"{tmp_uuid_val}.*"))
        if not matches:
            return jsonify({"error": "Arquivo temporário não encontrado ou expirado"}), 404
        tmp_path = matches[0]
        ext = os.path.splitext(tmp_path)[1].lower()
        filename = f"url_import{ext}"
        with open(tmp_path, "rb") as f:
            file_bytes = f.read()
        mime = "video/mp4" if ext == ".mp4" else "image/jpeg"
        try:
            if "video" in mime:
                video_id = _meta_api.upload_video(token, account_id, file_bytes, filename)
                os.remove(tmp_path)
                return jsonify({"tipo": "video", "video_id": video_id, "ok": True})
            else:
                resultado = _meta_api.upload_imagem(token, account_id, file_bytes, filename)
                os.remove(tmp_path)
                return jsonify({"tipo": "imagem", "hash": resultado["hash"], "ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Caminho normal via upload de arquivo
    if "arquivo" not in request.files:
        return jsonify({"error": "Campo 'arquivo' ou 'tmp_uuid' ausente"}), 400
    arquivo    = request.files["arquivo"]
    filename   = arquivo.filename or "criativo"
    file_bytes = arquivo.read()
    mime       = arquivo.content_type or ""
    try:
        if "video" in mime or filename.lower().endswith(".mp4"):
            video_id = _meta_api.upload_video(token, account_id, file_bytes, filename)
            return jsonify({"tipo": "video", "video_id": video_id, "ok": True})
        else:
            resultado = _meta_api.upload_imagem(token, account_id, file_bytes, filename)
            return jsonify({"tipo": "imagem", "hash": resultado["hash"], "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/copy", methods=["POST"])
@login_required
def anuncios_gerar_copy():
    d            = request.get_json() or {}
    imagem_b64   = d.get("imagem_base64", "")
    mime_type    = d.get("mime_type", "image/jpeg")
    cliente_nome = d.get("cliente_nome", "cliente")
    camp_tipo    = d.get("campanha_tipo", "MESSAGES")
    segmento     = d.get("segmento", "")

    cta_sugerido = "WHATSAPP_MESSAGE" if camp_tipo == "MESSAGES" else "LEARN_MORE"
    objetivo_txt = "gerar mensagens no WhatsApp" if camp_tipo == "MESSAGES" else "gerar engajamento"

    system = (
        "Você é especialista em copywriting para anúncios do Facebook/Instagram. "
        "Crie copies curtas, diretas e persuasivas em português brasileiro. "
        "Retorne APENAS um JSON válido, sem markdown ou texto adicional."
    )
    prompt = (
        f"Analise este criativo de anúncio para '{cliente_nome}'"
        + (f" (segmento: {segmento})" if segmento else "")
        + f". Objetivo: {objetivo_txt}.\n"
        "Crie:\n"
        "- titulo: até 40 caracteres, chamativo\n"
        "- texto: até 125 caracteres, copy persuasiva\n"
        f"- cta: use exatamente '{cta_sugerido}'\n\n"
        'Responda APENAS com JSON: {"titulo":"...","texto":"...","cta":"..."}'
    )

    client = anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    try:
        ctx = brain.contexto(cliente_nome)
        if ctx:
            system = system + f"\n\n## Briefing do Cliente\n{ctx}"
        content = []
        if imagem_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime_type, "data": imagem_b64}
            })
        content.append({"type": "text", "text": prompt})

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": content}]
        )
        raw = msg.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json\n"):
                raw = raw[5:]
        resultado = json.loads(raw)
        brain.salvar(
            modulo="Anuncios",
            titulo=f"Copy {cliente_nome} — {camp_tipo}",
            inputs={"cliente_nome": cliente_nome, "camp_tipo": camp_tipo, "segmento": segmento},
            output=f"Título: {resultado.get('titulo')}\n\nTexto: {resultado.get('texto')}\n\nCTA: {resultado.get('cta')}",
            model="claude-sonnet-4-6",
            cliente=cliente_nome,
        )
        return jsonify(resultado)
    except json.JSONDecodeError:
        return jsonify({"error": "IA retornou formato inválido"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/anuncios/publicar", methods=["POST"])
@login_required
def anuncios_publicar():
    d                 = request.get_json() or {}
    cliente_id        = d.get("cliente_id")
    campanha_exist_id = d.get("campanha_existente_id")
    campanha_nome     = d.get("campanha_nome", "Campanha Jake OS")
    orcamento         = float(d.get("orcamento_diario", 0))
    creative_ref      = d.get("creative_ref", {})
    copy_data         = d.get("copy", {})

    if not cliente_id:
        return jsonify({"error": "cliente_id obrigatório"}), 400
    if not creative_ref:
        return jsonify({"error": "creative_ref obrigatório"}), 400
    if not copy_data.get("titulo") or not copy_data.get("texto"):
        return jsonify({"error": "copy.titulo e copy.texto obrigatórios"}), 400

    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT * FROM ad_client_profiles WHERE id = %s", (cliente_id,))
        cliente = cur.fetchone()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar cliente: {e}"}), 500

    if not cliente:
        return jsonify({"error": "Cliente não encontrado"}), 404

    localizacao = cliente.get("localizacao_json") or {}
    tem_loc = localizacao and (localizacao.get("paises") or localizacao.get("cidades"))
    if not tem_loc:
        return jsonify({"error": "Localização não configurada — publicação bloqueada"}), 400

    page_id = cliente.get("page_id", "")
    if not page_id:
        return jsonify({"error": "page_id não configurado no perfil do cliente"}), 400

    token_key  = cliente["token_key"]
    if token_key not in _VALID_TOKEN_KEYS:
        return jsonify({"error": "token_key inválido"}), 400
    token      = os.getenv(token_key, "")
    account_id = cliente["account_id"]
    camp_tipo  = cliente.get("campanha_tipo", "MESSAGES")
    audience_id      = d.get("audience_id")
    saved_audience_id = d.get("saved_audience_id") or cliente.get("publico_salvo_id") or None
    publico          = cliente.get("publico_json") or {}
    if audience_id and not saved_audience_id:
        try:
            conn2 = get_db(); cur2 = conn2.cursor()
            cur2.execute("SELECT targeting_json, tipo FROM ad_audiences WHERE id=%s", (audience_id,))
            aud_row = cur2.fetchone(); conn2.close()
            if aud_row:
                publico = aud_row["targeting_json"] or {}
        except Exception:
            pass

    if not token:
        return jsonify({"error": f"{token_key} não configurado"}), 500

    campaign_id = adset_id = ad_id = None
    try:
        if campanha_exist_id:
            campaign_id = campanha_exist_id
        else:
            cbo = camp_tipo not in ("ENGAGEMENT", "PURCHASE")
            campaign_id = _meta_api.criar_campanha(
                token, account_id, camp_tipo, campanha_nome, orcamento, cbo=cbo
            )

        try:
            adset_id = _meta_api.criar_conjunto(
                token, account_id, campaign_id, camp_tipo, publico, localizacao,
                orcamento=(orcamento if camp_tipo in ("ENGAGEMENT", "PURCHASE") else None),
                optimization_goal=cliente.get("optimization_goal") or None,
                pixel_id=cliente.get("pixel_id") or None,
                saved_audience_id=saved_audience_id,
                page_id=page_id or None,
            )
        except Exception as e2:
            if not campanha_exist_id:
                _meta_api.deletar_objeto_meta(token, campaign_id)
            raise Exception(f"Falha no conjunto (campanha removida): {e2}")

        try:
            link_url = cliente.get("link_url") or ""
            ad_id = _meta_api.criar_anuncio(
                token, account_id, adset_id, page_id, creative_ref,
                copy_data["titulo"], copy_data["texto"],
                copy_data.get("cta", "WHATSAPP_MESSAGE"),
                link_url=link_url
            )
        except Exception as e3:
            _meta_api.deletar_objeto_meta(token, adset_id)
            if not campanha_exist_id:
                _meta_api.deletar_objeto_meta(token, campaign_id)
            raise Exception(f"Falha no anúncio (conjunto e campanha removidos): {e3}")

        try:
            conn = get_db()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO ad_publish_log
                    (cliente_id, account_id, campaign_id, adset_id, ad_id, status, audience_id, payload_json)
                VALUES (%s,%s,%s,%s,%s,'sucesso',%s,%s)
            """, (cliente_id, account_id, campaign_id, adset_id, ad_id,
                  audience_id if audience_id else None, json.dumps(d)))
            conn.commit()
            conn.close()
        except Exception:
            pass

        return jsonify({
            "ok": True,
            "campaign_id": campaign_id,
            "adset_id": adset_id,
            "ad_id": ad_id,
            "msg": "Anúncio criado com status PAUSADO. Ative no Gerenciador da Meta para publicar."
        })

    except Exception as e:
        try:
            conn = get_db()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO ad_publish_log
                    (cliente_id, account_id, campaign_id, adset_id, ad_id, status, erro_msg, payload_json)
                VALUES (%s,%s,%s,%s,%s,'erro',%s,%s)
            """, (cliente_id, account_id, campaign_id, adset_id, ad_id, str(e), json.dumps(d)))
            conn.commit()
            conn.close()
        except Exception:
            pass
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
#  ABA SUBIR ANÚNCIOS — Multi-Cliente
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/api/anuncios/multi-cliente/upload-temp", methods=["POST"])
@login_required
def anuncios_multi_cliente_upload_temp():
    """Salva o criativo em /tmp e retorna tmp_uuid. Upload real para cada conta ocorre na stream."""
    if "criativo" not in request.files:
        return jsonify({"error": "Campo 'criativo' ausente"}), 400
    arq  = request.files["criativo"]
    # Limite de 10 MB
    file_bytes = arq.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        return jsonify({"error": "Arquivo muito grande (máx 10 MB)"}), 400
    _ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4"}
    raw_ext = os.path.splitext(arq.filename or "img")[1].lower()
    ext  = raw_ext if raw_ext in _ALLOWED_EXTS else ".jpg"
    mime = arq.content_type or "image/jpeg"
    tmp_uuid_val = str(uuid.uuid4())
    tmp_path = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{ext}")
    try:
        with open(tmp_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        return jsonify({"error": f"Erro ao salvar arquivo: {e}"}), 500
    # Limpeza automática após 30 min
    def _cleanup():
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
    threading.Timer(1800, _cleanup).start()
    return jsonify({"tmp_uuid": tmp_uuid_val, "ext": ext, "mime": mime, "ok": True})


@bp.route("/api/anuncios/multi-cliente/preparar", methods=["POST"])
@login_required
def anuncios_multi_cliente_preparar():
    """Valida payload, busca perfis dos clientes, armazena em memória, retorna token + dados para revisão."""
    d = request.get_json() or {}
    cliente_ids = d.get("cliente_ids") or []
    if not cliente_ids:
        return jsonify({"error": "Selecione ao menos um cliente"}), 400
    if not d.get("tmp_uuid"):
        return jsonify({"error": "Criativo obrigatório — faça upload primeiro"}), 400
    if not d.get("campanha_nome"):
        return jsonify({"error": "Nome da campanha obrigatório"}), 400
    if not d.get("orcamento"):
        return jsonify({"error": "Orçamento obrigatório"}), 400
    try:
        orcamento_float = float(d["orcamento"])
    except (TypeError, ValueError):
        return jsonify({"error": "Orçamento deve ser um número"}), 400

    conn = None
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, agencia, account_id, token_key, page_id, link_url, "
            "campanha_tipo, optimization_goal, pixel_id, localizacao_json, publico_json, "
            "publico_salvo_id, publico_salvo_nome "
            "FROM ad_client_profiles WHERE id = ANY(%s)",
            (cliente_ids,)
        )
        clientes = [dict(c) for c in cur.fetchall()]
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar clientes: {e}"}), 500
    finally:
        try: conn.close()
        except Exception: pass

    if not clientes:
        return jsonify({"error": "Nenhum cliente encontrado"}), 404

    tmp_matches = _glob.glob(os.path.join(_TMP_DIR, f"{d['tmp_uuid']}.*"))
    if not tmp_matches:
        return jsonify({"error": "Criativo temporário não encontrado — faça o upload novamente"}), 400

    erros = []
    for c in clientes:
        loc = c.get("localizacao_json") or {}
        if not (loc.get("paises") or loc.get("cidades")):
            erros.append(f"{c['nome']}: localização não configurada")
        if not c.get("page_id"):
            erros.append(f"{c['nome']}: page_id não configurado")
        if not c.get("account_id"):
            erros.append(f"{c['nome']}: account_id não configurado")
        if c.get("token_key") not in _VALID_TOKEN_KEYS:
            erros.append(f"{c['nome']}: token_key inválido")
    if erros:
        return jsonify({"error": "Clientes com configuração incompleta", "detalhes": erros}), 400

    mc_token = str(uuid.uuid4())
    _lote_payloads[mc_token] = {
        "clientes":      clientes,
        "tmp_uuid":      d["tmp_uuid"],
        "tmp_ext":       d.get("tmp_ext", ".jpg"),
        "copy":          d.get("copy") or {},
        "campanha_nome": d["campanha_nome"],
        "orcamento":     orcamento_float,
    }
    def _cleanup_token():
        _lote_payloads.pop(mc_token, None)
    threading.Timer(1800, _cleanup_token).start()

    clientes_revisao = []
    for c in clientes:
        pub = c.get("publico_json") or {}
        loc = c.get("localizacao_json") or {}
        cidades_raw = loc.get("cidades") or []
        cidades = [ci.get("name", ci) if isinstance(ci, dict) else ci for ci in cidades_raw]
        clientes_revisao.append({
            "id":       c["id"],
            "nome":     c["nome"],
            "agencia":  c["agencia"],
            "publico": {
                "idade_min": pub.get("idade_min", 18),
                "idade_max": pub.get("idade_max", 65),
                "genero":    pub.get("genders", []),
                "cidades":   cidades,
                "paises":    loc.get("paises") or [],
            },
            "orcamento": orcamento_float,
        })

    return jsonify({"token": mc_token, "clientes": clientes_revisao})


@bp.route("/api/anuncios/multi-cliente/stream/<mc_token>")
@login_required
def anuncios_multi_cliente_stream(mc_token):
    """Para cada cliente: faz upload da imagem na conta dele, cria campanha+conjunto+anúncio via SSE."""
    payload = _lote_payloads.pop(mc_token, None)

    def _sse(data: dict) -> str:
        return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

    def _gerar():
        if not payload:
            yield _sse({"status": "erro", "cliente": "", "erro": "Token inválido ou expirado", "idx": 0, "total": 0})
            return

        clientes              = payload["clientes"]
        tmp_uuid_val          = payload["tmp_uuid"]
        tmp_ext               = payload.get("tmp_ext", ".jpg")
        copy_data             = payload.get("copy") or {}
        copies_list           = payload.get("copies_list") or []
        campanha_nome         = payload["campanha_nome"]
        orcamento             = payload["orcamento"]
        orcamento_por_conj    = payload.get("orcamento_por_conjunto") or None
        total                 = len(clientes)
        num_conjuntos         = int(payload.get("num_conjuntos") or 1)
        cri_por_conjunto      = int(payload.get("cri_por_conjunto") or 1)
        tmp_paths             = payload.get("tmp_paths") or [payload.get("tmp_path") or os.path.join(_TMP_DIR, f"{tmp_uuid_val}{tmp_ext}")]

        _EXT_MIME = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}

        # Carregar todos os arquivos de mídia
        arquivos_bytes = []
        for tp in tmp_paths:
            try:
                ext_i = os.path.splitext(tp)[1].lower()
                with open(tp, "rb") as f:
                    arquivos_bytes.append({"bytes": f.read(), "ext": ext_i, "mime": _EXT_MIME.get(ext_i, "image/jpeg")})
            except Exception as e:
                yield _sse({"status": "erro", "cliente": "upload", "erro": f"Arquivo não encontrado: {tp}: {e}", "idx": 0, "total": total})
                return

        for idx, cliente in enumerate(clientes):
            nome       = cliente["nome"]
            account_id = cliente["account_id"]
            token_key  = cliente["token_key"]
            token_val  = os.getenv(token_key, "")
            page_id    = cliente.get("page_id", "")
            camp_tipo  = payload.get("campanha_tipo") or cliente.get("campanha_tipo") or "MESSAGES"
            localizacao = cliente.get("localizacao_json") or {}
            publico    = cliente.get("publico_json") or {}
            link_url   = cliente.get("link_url") or ""
            opt_goal   = cliente.get("optimization_goal") or None
            pixel_id   = cliente.get("pixel_id") or None
            saved_aud_id = (
                payload.get("publicos_salvos_por_cliente", {}).get(str(cliente["id"]))
                or payload.get("publico_salvo_id")
                or cliente.get("publico_salvo_id")
            )

            yield _sse({"status": "publicando", "cliente": nome, "idx": idx + 1, "total": total})

            if token_key not in _VALID_TOKEN_KEYS or not token_val:
                yield _sse({"status": "erro", "cliente": nome, "erro": "token_key inválido ou token ausente", "idx": idx + 1, "total": total})
                continue

            campaign_id = adset_id = None
            ad_ids = []
            try:
                # 1. Upload de todos os criativos para a conta deste cliente
                creative_refs = []
                for arq in arquivos_bytes:
                    if "video" in arq["mime"]:
                        video_id = _meta_api.upload_video(token_val, account_id, arq["bytes"], f"criativo{arq['ext']}")
                        creative_refs.append({"tipo": "video", "video_id": video_id})
                    else:
                        resultado = _meta_api.upload_imagem(token_val, account_id, arq["bytes"], f"criativo{arq['ext']}")
                        creative_refs.append({"tipo": "imagem", "hash": resultado["hash"]})

                # 2. Campanha (uma por cliente)
                cbo = camp_tipo not in ("ENGAGEMENT", "PURCHASE")
                campaign_id = _meta_api.criar_campanha(
                    token_val, account_id, camp_tipo, campanha_nome, orcamento, cbo=cbo
                )

                # 3. N conjuntos, cada um com cri_por_conjunto criativos
                _CAMP_CTA = {"MESSAGES": "WHATSAPP_MESSAGE", "PURCHASE": "SHOP_NOW", "ENGAGEMENT": "LEARN_MORE"}
                cta = _CAMP_CTA.get(camp_tipo, "SEND_MESSAGE")

                for i_conj in range(num_conjuntos):
                    # Fatia os criativos para este conjunto
                    inicio = i_conj * cri_por_conjunto
                    fim    = inicio + cri_por_conjunto
                    refs_conj = creative_refs[inicio:fim]
                    if not refs_conj:
                        break

                    try:
                        _adset_orc = orcamento_por_conj or (orcamento if camp_tipo in ("ENGAGEMENT", "PURCHASE") else None)
                        _conj_nome = f"{nome} | Conjunto {i_conj + 1}" if num_conjuntos > 1 else f"{nome} | Conjunto"
                        print(f"[STREAM] saved_aud_id={saved_aud_id!r} publico={publico!r} loc={localizacao!r}", flush=True)
                        adset_id = _meta_api.criar_conjunto(
                            token_val, account_id, campaign_id, camp_tipo, publico, localizacao,
                            orcamento=_adset_orc,
                            optimization_goal=opt_goal, pixel_id=pixel_id,
                            saved_audience_id=saved_aud_id or None,
                            page_id=page_id or None,
                            nome=_conj_nome,
                        )
                    except Exception as e2:
                        if i_conj == 0:
                            _meta_api.deletar_objeto_meta(token_val, campaign_id)
                            raise Exception(f"Falha no conjunto {i_conj+1}: {e2}")
                        continue

                    for i_cr, creative_ref in enumerate(refs_conj):
                        try:
                            # Copy específica para este criativo, ou fallback para a copy global
                            _idx_global = i_conj * cri_por_conjunto + i_cr
                            _copy_cr = (copies_list[_idx_global] if _idx_global < len(copies_list) else None) or copy_data
                            _titulo_ad = _copy_cr.get("titulo") or f"Criativo {_idx_global + 1}"
                            _texto_ad  = _copy_cr.get("texto") or ""
                            ad_id = _meta_api.criar_anuncio(
                                token_val, account_id, adset_id, page_id, creative_ref,
                                _titulo_ad, _texto_ad,
                                cta, link_url=link_url
                            )
                            ad_ids.append(ad_id)
                        except Exception as e3:
                            if i_cr == 0 and i_conj == 0:
                                _meta_api.deletar_objeto_meta(token_val, adset_id)
                                _meta_api.deletar_objeto_meta(token_val, campaign_id)
                                raise Exception(f"Falha no anúncio {i_conj+1}/{i_cr+1}: {e3}")
                        # Erros em criativos adicionais: registra mas não desfaz

                # 5. Log (um registro por anúncio criado)
                for ad_id_log in (ad_ids or [None]):
                    try:
                        conn = get_db(); cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO ad_publish_log
                                (cliente_id, account_id, campaign_id, adset_id, ad_id,
                                 status, audience_id, payload_json)
                            VALUES (%s,%s,%s,%s,%s,'sucesso',NULL,%s)
                        """, (cliente["id"], account_id, campaign_id, adset_id, ad_id_log,
                              json.dumps(copy_data)))
                        conn.commit()
                    except Exception:
                        pass
                    finally:
                        try: conn.close()
                        except Exception: pass

                yield _sse({"status": "ok", "cliente": nome, "campanha_id": campaign_id,
                            "ads": len(ad_ids), "idx": idx + 1, "total": total})

            except Exception as e:
                try:
                    conn = get_db(); cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO ad_publish_log
                            (cliente_id, account_id, campaign_id, adset_id, ad_id,
                             status, audience_id, erro_msg, payload_json)
                        VALUES (%s,%s,%s,%s,%s,'erro',NULL,%s,%s)
                    """, (cliente["id"], account_id, campaign_id, adset_id, None,
                          str(e), json.dumps(copy_data)))
                    conn.commit()
                except Exception:
                    pass
                finally:
                    try: conn.close()
                    except Exception: pass
                yield _sse({"status": "erro", "cliente": nome, "erro": str(e), "idx": idx + 1, "total": total})

        # Limpar arquivos temp
        for tp in tmp_paths:
            try: os.remove(tp)
            except Exception: pass

        yield _sse({"status": "concluido", "total": total})

    return app.response_class(
        _gerar(),
        mimetype="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )


# ══════════════════════════════════════════════════════════════════════════
#  GESTOR IA — Agente autônomo de tráfego
# ══════════════════════════════════════════════════════════════════════════

def _gestor_db():
    """Retorna conexão ao banco com RealDictCursor (alias local para o gestor)."""
    return get_db()


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


# ══════════════════════════════════════════════════════════════════════════
#  ABA DRIVE BATCH — Publicar lote via Google Drive
# ══════════════════════════════════════════════════════════════════════════

_DRIVE_MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/png":  ".png",
    "image/webp": ".webp",
    "image/gif":  ".gif",
}


def _drive_download(file_id: str, timeout: int = 30) -> bytes:
    """Baixa conteúdo de um arquivo do Drive sem autenticação OAuth.

    Usa a URL de export pública que funciona para arquivos com
    permissão 'qualquer pessoa com o link' (sem precisar de API key).
    """
    resp = requests.get(
        "https://drive.google.com/uc",
        params={"export": "download", "id": file_id},
        timeout=timeout,
        allow_redirects=True,
    )
    resp.raise_for_status()
    # Google redireciona para uma página HTML de confirmação para arquivos grandes
    if "text/html" in resp.headers.get("Content-Type", ""):
        raise Exception(
            "Arquivo muito grande — o Drive exige confirmação. "
            "Tente reduzir o tamanho das imagens (< 25 MB) ou tornar a pasta pública."
        )
    return resp.content


@bp.route("/api/anuncios/drive/listar", methods=["POST"])
@login_required
def drive_listar():
    """Lista arquivos de imagem de uma pasta pública do Google Drive."""
    d = request.get_json() or {}
    url = (d.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL obrigatória"}), 400

    # Extrair folder_id da URL
    folder_id = None
    if "/folders/" in url:
        folder_id = url.split("/folders/")[1].split("?")[0].split("/")[0]
    elif "id=" in url:
        from urllib.parse import urlparse, parse_qs
        folder_id = parse_qs(urlparse(url).query).get("id", [None])[0]
    if not folder_id:
        return jsonify({"error": "Não foi possível extrair o ID da pasta. Use um link no formato drive.google.com/drive/folders/..."}), 400

    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return jsonify({"error": "GOOGLE_API_KEY não configurada no servidor"}), 500

    try:
        resp = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            params={
                "q": f"'{folder_id}' in parents",
                "fields": "files(id,name,mimeType,thumbnailLink)",
                "key": api_key,
                "pageSize": 100,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return jsonify({"error": f"Erro ao acessar Google Drive: {e}"}), 500

    files = [
        {"id": f["id"], "name": f["name"],
         "thumbnailLink": f"https://drive.google.com/thumbnail?id={f['id']}&sz=w100",
         "ext": _DRIVE_MIME_EXT.get(f["mimeType"], ".jpg"), "mimeType": f["mimeType"]}
        for f in data.get("files", [])
        if f.get("mimeType") in _DRIVE_MIME_EXT
    ]
    if not files:
        return jsonify({"error": "Nenhuma imagem encontrada na pasta (suporta JPG, PNG, WebP, GIF)"}), 400

    return jsonify({"files": files, "total": len(files)})


@bp.route("/api/anuncios/drive/thumb/<file_id>")
@login_required
def drive_thumb(file_id):
    """Proxy de thumbnail — baixa via API key e repassa ao browser com cache."""
    try:
        data = _drive_download(file_id, timeout=15)
        return Response(data, content_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=7200"})
    except Exception as e:
        app.logger.error(f"drive_thumb error for {file_id}: {e}")
        return str(e), 404


@bp.route("/api/anuncios/drive/publicos")
@login_required
def drive_publicos():
    """Lista públicos salvos + custom audiences de um cliente para seleção no wizard."""
    cliente_id = request.args.get("cliente_id")
    if not cliente_id:
        return jsonify({"error": "cliente_id obrigatório"}), 400

    conn = None
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT account_id, token_key FROM ad_client_profiles WHERE id = %s", (cliente_id,))
        row = cur.fetchone()
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar cliente: {e}"}), 500
    finally:
        try: conn.close()
        except Exception: pass

    if not row:
        return jsonify({"error": "Cliente não encontrado"}), 404

    token = os.getenv(row["token_key"], "")
    if not token:
        return jsonify({"error": f"{row['token_key']} não configurado"}), 400

    account_id = row["account_id"]
    result = []

    try:
        for s in _meta_api.listar_publicos_salvos(token, account_id):
            t   = s.get("targeting") or {}
            geo = t.get("geo_locations") or {}
            result.append({
                "id":   s["id"],
                "nome": s["name"],
                "tipo": "salvo",
                "data": {
                    "idade_min": t.get("age_min", 18),
                    "idade_max": t.get("age_max", 65),
                    "genders":   t.get("genders", [1, 2]),
                },
            })
    except Exception:
        pass

    try:
        for c in _meta_api.listar_custom_audiences(token, account_id):
            result.append({
                "id":   c["id"],
                "nome": f"{c['name']} ({c.get('subtype', '?')})",
                "tipo": "custom",
                "data": {"custom_audience_id": c["id"]},
            })
    except Exception:
        pass

    return jsonify({"publicos": result})


@bp.route("/api/anuncios/drive/campanhas")
@login_required
def drive_campanhas():
    """Busca campanhas ativas/pausadas de um cliente para seleção na UI."""
    cliente_id = request.args.get("cliente_id")
    if not cliente_id:
        return jsonify({"error": "cliente_id obrigatório"}), 400

    conn = None
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT account_id, token_key FROM ad_client_profiles WHERE id = %s",
            (cliente_id,)
        )
        row = cur.fetchone()
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar cliente: {e}"}), 500
    finally:
        try: conn.close()
        except Exception: pass

    if not row:
        return jsonify({"error": "Cliente não encontrado"}), 404

    account_id = row["account_id"]
    token_key  = row["token_key"]
    token      = os.getenv(token_key, "")
    if not token:
        return jsonify({"error": f"Token '{token_key}' não configurado"}), 500

    try:
        resp = requests.get(
            f"https://graph.facebook.com/v21.0/{account_id}/campaigns",
            params={
                "fields": "id,name,effective_status",
                "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED"]}]',
                "access_token": token,
                "limit": 50,
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            return jsonify({"error": data["error"].get("message", "Erro Meta API")}), 400
        campanhas = [{"id": c["id"], "name": c["name"], "status": c.get("effective_status", "")}
                     for c in data.get("data", [])]
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar campanhas: {e}"}), 500

    return jsonify({"campanhas": campanhas})


@bp.route("/api/anuncios/drive/iniciar-copies", methods=["POST"])
@login_required
def drive_iniciar_copies():
    """Armazena lista de arquivos em memória e retorna token para o stream de geração de copies."""
    d = request.get_json() or {}
    files = d.get("files") or []
    campanha_tipo = d.get("campanha_tipo", "MESSAGES")
    cliente_id    = d.get("cliente_id")

    if not files:
        return jsonify({"error": "Lista de arquivos vazia"}), 400
    if campanha_tipo not in ("MESSAGES", "PURCHASE", "ENGAGEMENT"):
        return jsonify({"error": "campanha_tipo inválido"}), 400

    # Buscar nome do cliente para usar no prompt (opcional, melhora copy)
    cliente_nome = ""
    if cliente_id:
        conn = None
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute("SELECT nome FROM ad_client_profiles WHERE id = %s", (cliente_id,))
            row = cur.fetchone()
            if row:
                cliente_nome = row["nome"]
        except Exception:
            pass
        finally:
            try: conn.close()
            except Exception: pass

    copies_token = str(uuid.uuid4())
    _lote_payloads[copies_token] = {
        "files":          files,
        "campanha_tipo":  campanha_tipo,
        "cliente_nome":   cliente_nome,
    }
    def _cleanup():
        _lote_payloads.pop(copies_token, None)
    threading.Timer(1800, _cleanup).start()

    return jsonify({"copies_token": copies_token})


_COPY_PROMPTS = {
    "MESSAGES": (
        "Você é especialista em copywriting para anúncios de WhatsApp. "
        "Analise a imagem e crie uma copy persuasiva focada em gerar mensagens no WhatsApp. "
        "Retorne APENAS JSON válido, sem markdown: "
        '{"titulo": "string máx 40 chars", "texto": "string máx 125 chars"}'
    ),
    "PURCHASE": (
        "Você é especialista em copywriting de conversão. "
        "Analise a imagem e crie uma copy focada em venda direta com urgência. "
        "Retorne APENAS JSON válido, sem markdown: "
        '{"titulo": "string máx 40 chars", "texto": "string máx 125 chars"}'
    ),
    "ENGAGEMENT": (
        "Você é especialista em copywriting de engajamento. "
        "Analise a imagem e crie uma copy instigante que gere curtidas e comentários. "
        "Retorne APENAS JSON válido, sem markdown: "
        '{"titulo": "string máx 40 chars", "texto": "string máx 125 chars"}'
    ),
}


@bp.route("/api/anuncios/drive/gerar-copies/stream/<copies_token>")
@login_required
def drive_gerar_copies_stream(copies_token):
    """SSE: para cada arquivo do Drive, baixa, gera copy com Claude Vision, emite evento."""
    payload = _lote_payloads.pop(copies_token, None)

    def _sse(data: dict) -> str:
        return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

    def _sse_ev(event: str, data: dict) -> str:
        return f"event: {event}\ndata: " + json.dumps(data, ensure_ascii=False) + "\n\n"

    def _gerar():
        if not payload:
            yield _sse_ev("erro", {"index": 0, "msg": "Token inválido ou expirado"})
            return

        files         = payload["files"]
        camp_tipo     = payload["campanha_tipo"]
        cliente_nome  = payload.get("cliente_nome", "")
        total         = len(files)
        system_prompt = _COPY_PROMPTS.get(camp_tipo, _COPY_PROMPTS["MESSAGES"])
        if cliente_nome:
            system_prompt += f"\n\nCliente: {cliente_nome}"

        client  = anthropic_client()

        for idx, f in enumerate(files):
            file_id   = f["id"]
            file_name = f["name"]
            mime_type = f.get("mimeType", "image/jpeg")
            ext       = _DRIVE_MIME_EXT.get(mime_type, ".jpg")

            # 1. Baixar imagem do Drive
            try:
                file_bytes = _drive_download(file_id)
            except Exception as e:
                yield _sse_ev("erro", {"index": idx, "file_id": file_id, "msg": f"Download falhou: {e}"})
                continue

            # 2. Salvar em /tmp com TTL de 30 min
            tmp_uuid_val = str(uuid.uuid4())
            tmp_path     = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{ext}")
            try:
                with open(tmp_path, "wb") as fp:
                    fp.write(file_bytes)
            except Exception as e:
                yield _sse_ev("erro", {"index": idx, "file_id": file_id, "msg": f"Erro ao salvar tmp: {e}"})
                continue

            def _cleanup_tmp(path=tmp_path):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
            threading.Timer(1800, _cleanup_tmp).start()

            # 3. Gerar copy com Claude Vision
            if not client:
                yield _sse_ev("erro", {"index": idx, "file_id": file_id, "msg": "ANTHROPIC_API_KEY não configurada"})
                continue
            try:
                import time as _time
                b64 = base64.b64encode(file_bytes).decode("utf-8")
                raw = None
                for _attempt in range(3):
                    try:
                        msg = client.messages.create(
                            model="claude-sonnet-4-6",
                            max_tokens=300,
                            system=system_prompt,
                            messages=[{"role": "user", "content": [
                                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}},
                                {"type": "text", "text": "Gere a copy para este criativo."},
                            ]}]
                        )
                        raw = msg.content[0].text.strip()
                        break
                    except Exception as _e:
                        if _attempt < 2 and ("529" in str(_e) or "overloaded" in str(_e).lower()):
                            _time.sleep(2 ** _attempt)
                        else:
                            raise
                if "```" in raw:
                    raw = raw.split("```")[1]
                    if raw.startswith("json\n"):
                        raw = raw[5:]
                resultado = json.loads(raw)
                titulo = resultado.get("titulo", "")
                texto  = resultado.get("texto", "")
            except Exception as e:
                yield _sse_ev("erro", {"index": idx, "file_id": file_id,
                                       "tmp_uuid": tmp_uuid_val, "ext": ext, "msg": f"Erro IA: {e}"})
                continue

            yield _sse_ev("copy", {
                "index":    idx,
                "file_id":  file_id,
                "file_name": file_name,
                "tmp_uuid": tmp_uuid_val,
                "ext":      ext,
                "titulo":   titulo,
                "texto":    texto,
            })

        yield _sse_ev("concluido", {"total": total})

    return app.response_class(
        _gerar(),
        mimetype="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@bp.route("/api/anuncios/drive/preparar", methods=["POST"])
@login_required
def drive_preparar():
    """Valida payload completo, verifica arquivos tmp, armazena em memória, retorna token."""
    d             = request.get_json() or {}
    cliente_ids   = d.get("cliente_ids") or []
    mode          = d.get("mode", "single")
    campanha_cfg  = d.get("campanha") or {}
    conjuntos_cfg = d.get("conjuntos") or {}
    camp_tipo     = d.get("campanha_tipo", "MESSAGES")
    copies        = d.get("copies") or []

    # Validação básica
    if not cliente_ids:
        return jsonify({"error": "Selecione ao menos um cliente"}), 400
    if not copies:
        return jsonify({"error": "Lista de copies vazia"}), 400

    try:
        num_conj   = int(conjuntos_cfg.get("num", 0))
        criat_por  = int(conjuntos_cfg.get("criativos_por", 0))
        orcamento  = float(conjuntos_cfg.get("orcamento", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Configuração de conjuntos inválida"}), 400

    if num_conj < 1 or criat_por < 1:
        return jsonify({"error": "Número de conjuntos e criativos por conjunto devem ser >= 1"}), 400
    if num_conj * criat_por != len(copies):
        return jsonify({
            "error": f"{num_conj} conjuntos × {criat_por} criativos = {num_conj * criat_por}, mas há {len(copies)} copies"
        }), 400

    # Buscar clientes no banco
    conn = None
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, agencia, account_id, token_key, page_id, link_url, "
            "campanha_tipo, optimization_goal, pixel_id, localizacao_json, publico_json, "
            "campanha_id_existente "
            "FROM ad_client_profiles WHERE id = ANY(%s)",
            (cliente_ids,)
        )
        clientes = [dict(c) for c in cur.fetchall()]
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar clientes: {e}"}), 500
    finally:
        try: conn.close()
        except Exception: pass

    if len(clientes) != len(cliente_ids):
        return jsonify({"error": "Um ou mais clientes não encontrados"}), 404

    # Validar campanha salva para modo multi com tipo=salva
    if mode == "multi" and campanha_cfg.get("tipo") == "salva":
        sem_campanha = [c["nome"] for c in clientes if not c.get("campanha_id_existente")]
        if sem_campanha:
            return jsonify({"error": f"Clientes sem campanha salva: {', '.join(sem_campanha)}"}), 400

    # Validar campos obrigatórios por cliente
    erros = []
    for c in clientes:
        if not c.get("account_id"):
            erros.append(f"{c['nome']}: account_id não configurado")
        if not c.get("page_id"):
            erros.append(f"{c['nome']}: page_id não configurado")
        if c.get("token_key") not in _VALID_TOKEN_KEYS:
            erros.append(f"{c['nome']}: token_key inválido")
        loc = c.get("localizacao_json") or {}
        if not (loc.get("paises") or loc.get("cidades")):
            erros.append(f"{c['nome']}: localização não configurada")
    if erros:
        return jsonify({"error": "Clientes com configuração incompleta", "detalhes": erros}), 400

    # Verificar arquivos tmp no disco
    for cp in copies:
        tmp_uuid_val = cp.get("tmp_uuid", "")
        ext          = cp.get("ext", ".jpg")
        tmp_path     = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{ext}")
        if not os.path.exists(tmp_path):
            return jsonify({"error": "Arquivos expirados — regere as copies antes de publicar", "expired": True}), 400

    publicos_conj = d.get("publicos_conj") or []

    # Armazenar payload
    db_token = str(uuid.uuid4())
    _lote_payloads[db_token] = {
        "clientes":      clientes,
        "mode":          mode,
        "campanha_cfg":  campanha_cfg,
        "conjuntos":     {"num": num_conj, "orcamento": orcamento, "criativos_por": criat_por},
        "camp_tipo":     camp_tipo,
        "copies":        copies,
        "publicos_conj": publicos_conj,
    }
    def _cleanup_token():
        _lote_payloads.pop(db_token, None)
    threading.Timer(1800, _cleanup_token).start()

    return jsonify({
        "token": db_token,
        "resumo": {
            "clientes":   len(clientes),
            "conjuntos":  num_conj,
            "total_ads":  len(clientes) * num_conj * criat_por,
        }
    })


@bp.route("/api/anuncios/drive/stream/<db_token>")
@login_required
def drive_stream(db_token):
    """SSE: para cada cliente, cria campanha+conjuntos+anúncios no Meta Ads."""
    payload = _lote_payloads.pop(db_token, None)

    def _sse(data: dict) -> str:
        return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

    _CAMP_CTA = {"MESSAGES": "WHATSAPP_MESSAGE", "PURCHASE": "SHOP_NOW", "ENGAGEMENT": "LEARN_MORE"}

    def _gerar():
        if not payload:
            yield _sse({"status": "erro", "msg": "Token inválido ou expirado"})
            return

        clientes      = payload["clientes"]
        campanha_cfg  = payload["campanha_cfg"]
        conjuntos     = payload["conjuntos"]
        camp_tipo     = payload["camp_tipo"]
        copies        = payload["copies"]
        publicos_conj = payload.get("publicos_conj") or []
        num_conj      = conjuntos["num"]
        criat_por     = conjuntos["criativos_por"]
        orcamento     = conjuntos["orcamento"]
        camp_nome    = campanha_cfg.get("nome", "Campanha Drive Batch")
        cta          = _CAMP_CTA.get(camp_tipo, "SEND_MESSAGE")
        cbo          = (camp_tipo == "MESSAGES")

        all_tmp_paths = set()

        for idx_c, cliente in enumerate(clientes):
            nome         = cliente["nome"]
            account_id   = cliente["account_id"]
            token_key    = cliente["token_key"]
            token_val    = os.getenv(token_key, "")
            page_id      = cliente.get("page_id", "")
            localizacao  = cliente.get("localizacao_json") or {}
            publico      = cliente.get("publico_json") or {}
            opt_goal     = cliente.get("optimization_goal") or None
            pixel_id     = cliente.get("pixel_id") or None
            link_url     = cliente.get("link_url") or ""

            if not token_val:
                yield _sse({"status": "erro", "msg": f"{nome}: token não encontrado", "cliente": nome})
                continue

            yield _sse({"status": "publicando", "msg": f"Iniciando {nome}...", "cliente": nome})

            # Resolver campaign_id
            newly_created_campaign = False
            campaign_id = None
            try:
                tipo_camp = campanha_cfg.get("tipo", "nova")
                if tipo_camp == "existente":
                    campaign_id = campanha_cfg["id"]
                elif tipo_camp == "salva":
                    campaign_id = cliente.get("campanha_id_existente")
                    if not campaign_id:
                        yield _sse({"status": "erro", "msg": f"{nome}: campanha_id_existente não definida", "cliente": nome})
                        continue
                else:  # nova
                    camp_budget = (num_conj * orcamento) if cbo else orcamento
                    campaign_id = _meta_api.criar_campanha(
                        token_val, account_id, camp_tipo, camp_nome, camp_budget, cbo=cbo
                    )
                    newly_created_campaign = True
            except Exception as e:
                yield _sse({"status": "erro", "msg": f"{nome}: erro ao criar campanha: {e}", "cliente": nome})
                continue

            # Criar conjuntos e anúncios
            created_adset_ids = []
            client_error = False

            for i in range(num_conj):
                slice_start = i * criat_por
                adset_copies = copies[slice_start: slice_start + criat_por]

                yield _sse({
                    "status": "publicando",
                    "msg":    f"{nome} — Conjunto {i+1}/{num_conj}",
                    "cliente": nome,
                })

                try:
                    # Resolver público para este conjunto
                    pub_cfg = publicos_conj[i] if i < len(publicos_conj) else {}
                    tipo_pub = pub_cfg.get("tipo", "padrao")
                    if tipo_pub == "salvo":
                        d = pub_cfg.get("data") or {}
                        publico_conj = {
                            "idade_min": d.get("idade_min", 18),
                            "idade_max": d.get("idade_max", 65),
                            "genders":   d.get("genders", [1, 2]),
                        }
                    elif tipo_pub == "custom":
                        d = pub_cfg.get("data") or {}
                        publico_conj = {
                            "idade_min": 18, "idade_max": 65, "genders": [1, 2],
                            "custom_audience_id": d.get("custom_audience_id", pub_cfg.get("id", "")),
                        }
                    else:
                        publico_conj = publico  # padrão do cliente

                    adset_orcamento = orcamento if not cbo else None
                    adset_id = _meta_api.criar_conjunto(
                        token_val, account_id, campaign_id, camp_tipo,
                        publico_conj, localizacao,
                        orcamento=adset_orcamento,
                        optimization_goal=opt_goal,
                        pixel_id=pixel_id,
                        nome=f"Conjunto {i+1} — {camp_nome}",
                        page_id=page_id or None,
                    )
                    created_adset_ids.append(adset_id)
                except Exception as e:
                    for aid in created_adset_ids:
                        try: _meta_api.deletar_objeto_meta(token_val, aid)
                        except Exception: pass
                    if newly_created_campaign:
                        try: _meta_api.deletar_objeto_meta(token_val, campaign_id)
                        except Exception: pass
                    yield _sse({"status": "erro", "msg": f"{nome} — Conjunto {i+1} falhou: {e}", "cliente": nome})
                    client_error = True
                    break

                for cp in adset_copies:
                    tmp_uuid_val = cp.get("tmp_uuid", "")
                    ext          = cp.get("ext", ".jpg")
                    titulo       = cp.get("titulo", "")
                    texto        = cp.get("texto", "")
                    tmp_path     = os.path.join(_TMP_DIR, f"{tmp_uuid_val}{ext}")
                    all_tmp_paths.add(tmp_path)

                    try:
                        with open(tmp_path, "rb") as fp:
                            file_bytes = fp.read()
                        filename = f"drive_batch_{tmp_uuid_val}{ext}"

                        upload_result = _meta_api.upload_imagem(token_val, account_id, file_bytes, filename)
                        creative_ref  = {"tipo": "imagem", "hash": upload_result["hash"]}

                        ad_id = _meta_api.criar_anuncio(
                            token_val, account_id, adset_id, page_id,
                            creative_ref, titulo, texto, cta, link_url=link_url,
                        )

                        try:
                            conn = get_db(); cur = conn.cursor()
                            cur.execute("""
                                INSERT INTO ad_publish_log
                                    (cliente_id, account_id, campaign_id, adset_id, ad_id,
                                     status, audience_id, payload_json)
                                VALUES (%s,%s,%s,%s,%s,'sucesso',NULL,%s)
                            """, (cliente["id"], account_id, campaign_id, adset_id, ad_id,
                                  json.dumps({"titulo": titulo, "texto": texto})))
                            conn.commit()
                        except Exception:
                            pass
                        finally:
                            try: conn.close()
                            except Exception: pass

                        yield _sse({"status": "ok", "msg": f"Ad criado: {titulo[:30]}", "cliente": nome})

                    except Exception as e:
                        try:
                            conn = get_db(); cur = conn.cursor()
                            cur.execute("""
                                INSERT INTO ad_publish_log
                                    (cliente_id, account_id, campaign_id, adset_id, ad_id,
                                     status, audience_id, erro_msg, payload_json)
                                VALUES (%s,%s,%s,%s,NULL,'erro',NULL,%s,%s)
                            """, (cliente["id"], account_id, campaign_id, adset_id, str(e),
                                  json.dumps({"titulo": titulo, "texto": texto})))
                            conn.commit()
                        except Exception:
                            pass
                        finally:
                            try: conn.close()
                            except Exception: pass
                        yield _sse({"status": "erro", "msg": f"Ad '{titulo[:20]}' falhou: {e}", "cliente": nome})

            if not client_error:
                yield _sse({"status": "ok", "msg": f"{nome} concluído ✓", "cliente": nome})

        for tmp_path in all_tmp_paths:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

        yield _sse({"status": "concluido"})

    return app.response_class(
        _gerar(),
        mimetype="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ══════════════════════════════════════════════════════════════════════════
#  ABA SUBIR ANÚNCIOS — Builder de Lote
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/api/anuncios/publicar-lote", methods=["POST"])
@login_required
def anuncios_publicar_lote():
    """Etapa 1: valida payload, armazena em memória, retorna lote_token."""
    d = request.get_json() or {}
    if not d.get("cliente_id") and not d.get("cliente_ids"):
        return jsonify({"error": "cliente_id ou cliente_ids obrigatório"}), 400
    if not d.get("conjuntos"):
        return jsonify({"error": "conjuntos não podem ser vazios"}), 400
    lote_token = str(uuid.uuid4())
    _lote_payloads[lote_token] = d
    return jsonify({"lote_token": lote_token})


@bp.route("/api/anuncios/publicar-lote/stream/<lote_token>")
@login_required
def anuncios_publicar_lote_stream(lote_token):
    """Etapa 2: processa lote sequencialmente via SSE."""
    payload = _lote_payloads.pop(lote_token, None)

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    def gerar():
        if payload is None:
            yield _sse({"tipo": "erro_fatal", "erro": "Lote não encontrado ou já processado"})
            return

        camp_nome             = payload.get("campanha_nome", "Campanha Jake OS")
        camp_tipo             = payload.get("campanha_tipo", "MESSAGES")
        orcamento_total       = float(payload.get("orcamento_diario_total", 0))
        modo_camp             = payload.get("modo_campanha", "nova")
        campaign_id_existente = payload.get("campaign_id_existente", "").strip()
        conjuntos             = payload["conjuntos"]
        lote_id               = payload.get("lote_id", lote_token)
        n_conjuntos           = len(conjuntos)
        # Suporta cliente_ids (multi) ou cliente_id (single)
        cliente_ids_lista = payload.get("cliente_ids") or [payload.get("cliente_id")]

        total_geral = sum(len(c.get("criativos", [])) for c in conjuntos) * len(cliente_ids_lista)
        sucesso_geral = 0; falha_geral = 0

        for cliente_id in cliente_ids_lista:
            try:
                conn = get_db(); cur = conn.cursor()
                cur.execute("SELECT * FROM ad_client_profiles WHERE id = %s", (cliente_id,))
                cliente = cur.fetchone(); conn.close()
            except Exception as e:
                yield _sse({"tipo": "erro_fatal", "erro": f"Erro ao buscar cliente {cliente_id}: {e}"})
                continue
            if not cliente:
                yield _sse({"tipo": "erro_fatal", "erro": f"Cliente {cliente_id} não encontrado"})
                continue

            token_key = cliente["token_key"]
            if token_key not in _VALID_TOKEN_KEYS:
                yield _sse({"tipo": "erro_fatal", "erro": f"token_key inválido para {cliente['nome']}", "cliente": cliente["nome"]})
                continue
            token       = os.getenv(token_key, "")
            account_id  = cliente["account_id"]
            page_id     = cliente.get("page_id", "")
            link_url    = cliente.get("link_url") or ""
            localizacao = cliente.get("localizacao_json") or {}
            opt_goal    = cliente.get("optimization_goal") or None
            pixel_id    = cliente.get("pixel_id") or None
            nome_cliente = cliente["nome"]

            yield _sse({"tipo": "cliente_inicio", "cliente": nome_cliente})

            cbo = camp_tipo not in ("ENGAGEMENT", "PURCHASE")
            if modo_camp == "existente" and campaign_id_existente:
                if not campaign_id_existente.isdigit():
                    yield _sse({"tipo": "erro_fatal", "erro": "campaign_id_existente inválido", "cliente": nome_cliente}); continue
                try:
                    r_check = requests.get(
                        f"https://graph.facebook.com/v21.0/{campaign_id_existente}",
                        params={"fields": "account_id", "access_token": token},
                        timeout=10,
                    )
                    r_check.raise_for_status()
                    resp_data = r_check.json()
                except requests.exceptions.RequestException as e:
                    yield _sse({"tipo": "erro_fatal", "erro": f"Erro ao validar campanha: {e}", "cliente": nome_cliente}); continue
                if "error" in resp_data:
                    yield _sse({"tipo": "erro_fatal", "erro": f"Meta API: {resp_data['error'].get('message', str(resp_data['error']))}", "cliente": nome_cliente}); continue
                expected_account = account_id.replace("act_", "")
                if str(resp_data.get("account_id", "")) != expected_account:
                    yield _sse({"tipo": "erro_fatal", "erro": "Campanha não pertence à conta do cliente", "cliente": nome_cliente}); continue
                campaign_id = campaign_id_existente
                yield _sse({"tipo": "campanha_ok", "campaign_id": campaign_id, "existente": True, "cliente": nome_cliente})
            else:
                try:
                    campaign_id = _meta_api.criar_campanha(
                        token, account_id, camp_tipo, camp_nome, orcamento_total, cbo=cbo
                    )
                    yield _sse({"tipo": "campanha_ok", "campaign_id": campaign_id, "cliente": nome_cliente})
                except Exception as e:
                    yield _sse({"tipo": "erro_fatal", "erro": str(e), "cliente": nome_cliente}); continue

            sucesso = 0; falha = 0

            for ci, conjunto in enumerate(conjuntos):
                audience_id = conjunto.get("audience_id")
                publico = cliente.get("publico_json") or {}
                saved_aud = cliente.get("publico_salvo_id") or None
                if audience_id:
                    try:
                        conn2 = get_db(); cur2 = conn2.cursor()
                        cur2.execute("SELECT targeting_json FROM ad_audiences WHERE id=%s", (audience_id,))
                        row = cur2.fetchone(); conn2.close()
                        if row and row["targeting_json"]:
                            publico = row["targeting_json"]
                            saved_aud = None
                    except Exception:
                        pass

                orcamento_conj = (orcamento_total / n_conjuntos) if camp_tipo in ("ENGAGEMENT", "PURCHASE") else None
                try:
                    adset_id = _meta_api.criar_conjunto(
                        token, account_id, campaign_id, camp_tipo, publico, localizacao,
                        orcamento=orcamento_conj, optimization_goal=opt_goal,
                        pixel_id=pixel_id, nome=conjunto.get("nome"),
                        page_id=page_id or None,
                        saved_audience_id=saved_aud,
                    )
                    yield _sse({"tipo": "conjunto_ok", "conjunto_idx": ci, "adset_id": adset_id, "cliente": nome_cliente})
                except Exception as e:
                    yield _sse({"tipo": "conjunto_erro", "conjunto_idx": ci, "erro": str(e), "cliente": nome_cliente})
                    falha += len(conjunto.get("criativos", []))
                    continue

                for ri, criativo in enumerate(conjunto.get("criativos", [])):
                    copy = criativo.get("copy", {})
                    try:
                        # Resolve creative_ref: se tmp_uuid (multi-cliente), re-faz upload para esta conta
                        cr = dict(criativo.get("creative_ref") or {})
                        if cr.get("tmp_uuid") and not cr.get("hash") and not cr.get("video_id"):
                            tmp_uuid_cr = cr["tmp_uuid"]
                            ext_cr = cr.get("ext", ".jpg")
                            tmp_path_cr = os.path.join(_TMP_DIR, f"{tmp_uuid_cr}{ext_cr}")
                            with open(tmp_path_cr, "rb") as _f:
                                cr_bytes = _f.read()
                            if cr.get("tipo") == "video":
                                video_id = _meta_api.upload_video(token, account_id, cr_bytes, f"criativo{ext_cr}")
                                cr = {"tipo": "video", "video_id": video_id}
                            else:
                                res = _meta_api.upload_imagem(token, account_id, cr_bytes, f"criativo{ext_cr}")
                                cr = {"tipo": "imagem", "hash": res["hash"]}
                        ad_id = _meta_api.criar_anuncio(
                            token, account_id, adset_id, page_id, cr,
                            copy.get("titulo", ""), copy.get("texto", ""),
                            copy.get("cta", "WHATSAPP_MESSAGE"),
                            link_url=link_url
                        )
                        try:
                            conn3 = get_db(); cur3 = conn3.cursor()
                            cur3.execute("""
                                INSERT INTO ad_publish_log
                                    (cliente_id, account_id, campaign_id, adset_id, ad_id,
                                     status, audience_id, lote_id, payload_json)
                                VALUES (%s,%s,%s,%s,%s,'sucesso',%s,%s,%s)
                            """, (cliente_id, account_id, campaign_id, adset_id, ad_id,
                                  audience_id, lote_id, json.dumps(criativo)))
                            conn3.commit(); conn3.close()
                        except Exception:
                            pass
                        sucesso += 1
                        sucesso_geral += 1
                        yield _sse({"tipo": "anuncio_ok", "conjunto_idx": ci,
                                    "criativo_idx": ri, "ad_id": ad_id, "cliente": nome_cliente})
                    except Exception as e:
                        falha += 1
                        falha_geral += 1
                        yield _sse({"tipo": "anuncio_erro", "conjunto_idx": ci,
                                    "criativo_idx": ri, "erro": str(e), "cliente": nome_cliente})
        # fim do loop de clientes
        yield _sse({"tipo": "fim", "total": total_geral, "sucesso": sucesso_geral, "falha": falha_geral})

    return app.response_class(
        gerar(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@bp.route("/api/anuncios/preview-url", methods=["POST"])
@login_required
def anuncios_preview_url():
    """Baixa URL externa, detecta tipo, salva em /tmp, retorna tmp_uuid."""
    d = request.get_json() or {}
    url = (d.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url obrigatória"}), 400

    MAX_SIZE = 50 * 1024 * 1024  # 50MB
    try:
        resp = requests.get(url, timeout=30, stream=True)
        content_type = resp.headers.get("Content-Type", "")
        content_length = int(resp.headers.get("Content-Length", 0) or 0)
        if content_length > MAX_SIZE:
            return jsonify({"error": "Arquivo muito grande (máx 50MB)"}), 400

        if content_type.startswith("image/"):
            tipo = "imagem"
            ext  = content_type.split("/")[1].split(";")[0].strip() or "jpg"
        elif content_type.startswith("video/"):
            tipo = "video"
            ext  = content_type.split("/")[1].split(";")[0].strip() or "mp4"
        else:
            return jsonify({"error": "Formato não suportado. Use imagem ou vídeo."}), 400

        tmp_uuid_val = str(uuid.uuid4())
        tmp_path = os.path.join(_TMP_DIR, f"{tmp_uuid_val}.{ext}")
        size = 0
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                size += len(chunk)
                if size > MAX_SIZE:
                    f.close()
                    os.remove(tmp_path)
                    return jsonify({"error": "Arquivo muito grande (máx 50MB)"}), 400
                f.write(chunk)

        threading.Timer(1800, lambda p=tmp_path: os.path.exists(p) and os.remove(p)).start()
        return jsonify({"tmp_uuid": tmp_uuid_val, "tipo": tipo, "ok": True})
    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout ao acessar a URL (30s)"}), 400
    except Exception as e:
        return jsonify({"error": f"Não foi possível acessar a URL: {e}"}), 400


@bp.route("/api/anuncios/tmp-preview/<tmp_uuid_val>")
@login_required
def anuncios_tmp_preview(tmp_uuid_val):
    """Serve arquivo temporário de preview."""
    import re
    if not re.match(r'^[a-f0-9\-]{36}$', tmp_uuid_val):
        return jsonify({"error": "uuid inválido"}), 400
    matches = _glob.glob(os.path.join(_TMP_DIR, f"{tmp_uuid_val}.*"))
    if not matches:
        return jsonify({"error": "Preview não encontrado ou expirado"}), 404
    from flask import send_file
    return send_file(matches[0])


@bp.route("/api/anuncios/copy-lote", methods=["POST"])
@login_required
def anuncios_copy_lote():
    """Gera N copies via Claude para o lote."""
    import re
    d = request.get_json() or {}
    cliente_id = d.get("cliente_id")
    camp_tipo  = d.get("campanha_tipo", "MESSAGES")
    criativos  = d.get("criativos", [])
    if not cliente_id or not criativos:
        return jsonify({"error": "cliente_id e criativos obrigatórios"}), 400

    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT nome, segmento FROM ad_client_profiles WHERE id=%s", (cliente_id,))
        cliente = cur.fetchone(); conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    nome_cliente = (cliente or {}).get("nome", "cliente")
    segmento     = (cliente or {}).get("segmento", "")
    objetivo_txt = {
        "MESSAGES":   "gerar mensagens no WhatsApp",
        "ENGAGEMENT": "gerar engajamento no post",
        "PURCHASE":   "gerar conversões/vendas na landing page",
    }.get(camp_tipo, "gerar conversões")
    cta_sugerido = "WHATSAPP_MESSAGE" if camp_tipo == "MESSAGES" else "LEARN_MORE"

    lista_txt = "\n".join(
        f"- indice: {c['indice']}, tipo: {c['tipo']}, descricao: {c.get('descricao','(sem descricao)')}"
        for c in criativos
    )
    prompt = (
        f"Cliente: {nome_cliente} | Segmento: {segmento} | Objetivo: {objetivo_txt}\n\n"
        f"Gere {len(criativos)} copies distintas para anuncios Meta Ads. Uma copy por criativo listado abaixo.\n"
        f"Cada copy deve ter:\n"
        f"- titulo: max 40 caracteres, impactante\n"
        f"- texto: max 125 caracteres, direto ao ponto com CTA implicito ({cta_sugerido})\n\n"
        f"Criativos:\n{lista_txt}\n\n"
        f'Responda SOMENTE com JSON valido, no formato:\n[{{"indice": "X-X", "titulo": "...", "texto": "..."}}]'
    )

    try:
        resp = anthropic_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        copies = json.loads(match.group(0) if match else raw)
        return jsonify({"copies": copies})
    except Exception as e:
        return jsonify({"error": f"Erro ao gerar copies: {e}"}), 500
