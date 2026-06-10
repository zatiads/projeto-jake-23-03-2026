import base64
import json
import math as _math
import os
import time

import requests

from flask import Blueprint, jsonify, request

from .shared import anthropic_client, get_db, login_required

bp = Blueprint('criativos', __name__)


# ══════════════════════════════════════════════════════════════════════════
import math as _math

_CRIATIVOS_MODOS = {"anuncios", "criativo", "psicodelico", "pessoas", "cena"}

_CRIATIVOS_MODELOS_IMAGEM = {
    "flux-1.1-pro":     "black-forest-labs/flux-1.1-pro",
    "flux-dev":         "black-forest-labs/flux-dev",
    "recraft-v3":       "recraft-ai/recraft-v3",
    "ideogram-v3-turbo":"ideogram-ai/ideogram-v3-turbo",
    "imagen-4":         "google/imagen-4",
}

_CRIATIVOS_MODELOS_VIDEO = {
    "wan-t2v-fast":  ("wavespeedai/wan-2.2-t2v-480p", "t2v"),
    "wan-5b-fast":   ("wavespeedai/wan-2.2-t2v-720p", "t2v"),
    "hailuo-02":     ("minimax/hailuo-02",             "t2v"),
    "seedance-lite": ("bytedance/seedance-1-lite",     "t2v"),
    "runway-gen4":   ("runwayml/gen4-turbo",           "t2v"),
    "wan-i2v-fast":  ("wavespeedai/wan-2.2-i2v-480p", "i2v"),
}

# Taxa estimada em USD por segundo de GPU por modelo
_CUSTO_POR_SEGUNDO = {
    "wan-t2v-fast":  0.0030,
    "wan-5b-fast":   0.0050,
    "hailuo-02":     0.0080,
    "seedance-lite": 0.0035,
    "runway-gen4":   0.0200,
    "wan-i2v-fast":  0.0030,
}

_CRIATIVOS_SYSTEM_PROMPTS = {
    "anuncios": (
        "You are an expert commercial photographer and ad creative director specializing in Meta Ads and Google Ads. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: studio lighting, commercial photography style, trust-inspiring composition, clean backgrounds, "
        "specific camera/lens (Canon EOS R5, 85mm f/1.4), warm color grading. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "criativo": (
        "You are an expert creative director and editorial photographer. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: conceptual art, bold composition, editorial/National Geographic style, dynamic lighting, "
        "color contrast, visual narrative, storytelling. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "psicodelico": (
        "You are an expert AI artist specializing in psychedelic and surrealist visual art. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: fractal geometry, neon/vibrant colors, DMT-inspired visuals, kaleidoscope patterns, "
        "liquid geometry, cosmic themes, ultra-detailed, 8K resolution, surrealist dreamscape. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "pessoas": (
        "You are an expert portrait and fashion photographer. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: hyperrealistic skin texture, subsurface scattering, Rembrandt or natural window lighting, "
        "Canon EOS R5 85mm f/1.2, shallow depth of field, authentic candid expressions, photojournalism style. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
    "cena": (
        "You are an expert landscape and architectural photographer. "
        "Expand simple Portuguese prompts into professional English image/video generation prompts. "
        "Focus on: cinematic wide angle (16mm), leading lines, volumetric light, golden hour, atmospheric haze, "
        "rule of thirds, long exposure, National Geographic / award-winning landscape style. "
        "Return ONLY the expanded prompt, no explanation, no quotes, 50-120 words."
    ),
}

_REPLICATE_BASE = "https://api.replicate.com/v1"


def _replicate_headers():
    token = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN não configurado no .env")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@bp.route("/api/criativos/upload-imagem", methods=["POST"])
@login_required
def criativos_upload_imagem():
    if "arquivo" not in request.files:
        return jsonify({"error": "Campo 'arquivo' ausente"}), 400
    arquivo = request.files["arquivo"]
    file_bytes = arquivo.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        return jsonify({"error": "Arquivo muito grande. Limite: 10 MB"}), 413
    mime = arquivo.content_type or "image/jpeg"
    if mime not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        return jsonify({"error": "Tipo de arquivo não suportado. Use JPEG, PNG, WebP ou GIF"}), 415
    # base64 para análise via Claude
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    # Upload para Replicate Files API para uso como URL em I2V
    try:
        headers = _replicate_headers()
        headers.pop("Content-Type")  # multipart não usa Content-Type JSON
        resp = requests.post(
            f"{_REPLICATE_BASE}/files",
            headers={"Authorization": headers["Authorization"]},
            files={"content": (arquivo.filename or "upload", file_bytes, mime)},
            timeout=30,
        )
        if not resp.ok:
            return jsonify({"error": f"Replicate upload: {resp.text[:200]}"}), 500
        url = resp.json().get("urls", {}).get("get") or resp.json().get("url", "")
        return jsonify({"url": url, "base64": b64, "mime_type": mime, "ok": True})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


_CRIATIVOS_SYSTEM_PROMPT_KONTEXT = (
    "You are an expert in AI image editing. "
    "The user has a reference image and wants to modify it. "
    "Transform the user's simple request into a clear EDITING INSTRUCTION. "
    "Format: describe ONLY what should change, never the whole image. "
    "Use direct action verbs: 'Change', 'Replace', 'Remove', 'Add', 'Keep'. "
    "Always add: 'Keep the [unchanged elements] exactly the same.' "
    "Example output: 'Change the product label text to focus on postpartum women. "
    "Keep the product, lighting, background and composition exactly the same.' "
    "Maximum 2 sentences. Always in English."
)


@bp.route("/api/criativos/expandir-prompt", methods=["POST"])
@login_required
def criativos_expandir_prompt():
    d = request.get_json() or {}
    prompt         = (d.get("prompt") or "").strip()
    modo           = d.get("modo", "criativo")
    tipo           = d.get("tipo", "imagem")
    tem_referencia = bool(d.get("tem_referencia", False))
    if not prompt:
        return jsonify({"error": "Campo 'prompt' obrigatório"}), 400
    if modo not in _CRIATIVOS_MODOS:
        return jsonify({"error": f"modo inválido. Válidos: {list(_CRIATIVOS_MODOS)}"}), 400

    client = anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    if tem_referencia:
        system = _CRIATIVOS_SYSTEM_PROMPT_KONTEXT
        user_msg = f"Transform this editing request into a Kontext instruction: {prompt}"
    else:
        tipo_hint = " Optimize for motion, camera movement, and temporal consistency." if tipo == "video" else ""
        system = _CRIATIVOS_SYSTEM_PROMPTS[modo] + tipo_hint
        user_msg = f"Expand this prompt: {prompt}"

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        prompt_expandido = msg.content[0].text.strip()
        brain.salvar(
            modulo="Criativos",
            titulo=f"Prompt expandido {modo} {tipo}" + (" [kontext]" if tem_referencia else ""),
            inputs={"prompt": prompt, "modo": modo, "tipo": tipo, "tem_referencia": tem_referencia},
            output=prompt_expandido,
            model="claude-sonnet-4-6",
        )
        return jsonify({"prompt_expandido": prompt_expandido})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/criativos/analisar-referencia", methods=["POST"])
@login_required
def criativos_analisar_referencia():
    d = request.get_json() or {}
    b64  = d.get("imagem_base64", "")
    mime = d.get("mime_type", "image/jpeg")
    if not b64:
        return jsonify({"error": "imagem_base64 obrigatório"}), 400

    client = anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    system = (
        "You are an expert visual analyst and prompt engineer. "
        "Analyze the image and return ONLY valid JSON with two fields: "
        "'prompt_sugerido' (English prompt 50-120 words to recreate this visual style) and "
        "'modo_sugerido' (one of: anuncios, criativo, psicodelico, pessoas, cena). "
        "No markdown, no explanation, just the JSON object."
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text",  "text": "Analyze this image and return the JSON."},
            ]}],
        )
        raw = msg.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json\n"):
                raw = raw[5:]
        result = json.loads(raw)
        # Validar modo_sugerido
        if result.get("modo_sugerido") not in _CRIATIVOS_MODOS:
            result["modo_sugerido"] = "criativo"
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({"error": "IA retornou formato inválido"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/criativos/gerar-imagem", methods=["POST"])
@login_required
def criativos_gerar_imagem():
    d = request.get_json() or {}
    prompt         = (d.get("prompt_expandido") or "").strip()
    modelo         = d.get("modelo", "flux-1.1-pro")
    imagem_url     = (d.get("imagem_url") or "").strip()
    tem_referencia = bool(d.get("tem_referencia", False))

    if not prompt:
        return jsonify({"error": "prompt_expandido obrigatório"}), 400

    # Modo Kontext: ignora o modelo enviado e usa flux-kontext-pro
    if tem_referencia and imagem_url:
        try:
            url = _generate_kontext(prompt, imagem_url, os.environ.get("REPLICATE_API_TOKEN", "").strip())
            brain.salvar(
                modulo="Criativos",
                titulo="Imagem editada flux-kontext-pro",
                inputs={"modelo": "flux-kontext-pro", "prompt": prompt, "input_image": imagem_url},
                output=url,
                model="flux-kontext-pro",
            )
            return jsonify({"url": url, "ok": True})
        except Exception as e:
            return jsonify({"error": f"Kontext Pro: {e}"}), 500

    if modelo not in _CRIATIVOS_MODELOS_IMAGEM:
        return jsonify({"error": f"modelo inválido. Válidos: {list(_CRIATIVOS_MODELOS_IMAGEM)}"}), 400

    slug = _CRIATIVOS_MODELOS_IMAGEM[modelo]
    try:
        headers = _replicate_headers()
        headers["Prefer"] = "wait=60"
        resp = requests.post(
            f"{_REPLICATE_BASE}/models/{slug}/predictions",
            headers=headers,
            json={"input": {"prompt": prompt, "aspect_ratio": "4:5",
                            "output_format": "webp", "output_quality": 90}},
            timeout=90,
        )
        if not resp.ok:
            return jsonify({"error": f"Replicate {resp.status_code}: {resp.text[:300]}"}), 500
        pred = resp.json()
        # Caminho síncrono (Prefer: wait)
        if pred.get("status") == "succeeded":
            out = pred.get("output")
            url = out[0] if isinstance(out, list) else out
            brain.salvar(
                modulo="Criativos",
                titulo=f"Imagem gerada {modelo}",
                inputs={"modelo": modelo, "prompt": prompt},
                output=url,
                model=modelo,
            )
            return jsonify({"url": url, "ok": True})
        # Fallback polling (raro)
        get_url = (pred.get("urls") or {}).get("get", "")
        hdrs = {"Authorization": headers["Authorization"]}
        for _ in range(20):
            time.sleep(3)
            p = requests.get(get_url, headers=hdrs, timeout=15).json()
            if p.get("status") == "succeeded":
                out = p.get("output")
                url = out[0] if isinstance(out, list) else out
                brain.salvar(
                    modulo="Criativos",
                    titulo=f"Imagem gerada {modelo}",
                    inputs={"modelo": modelo, "prompt": prompt},
                    output=url,
                    model=modelo,
                )
                return jsonify({"url": url, "ok": True})
            if p.get("status") == "failed":
                return jsonify({"error": p.get("error", "Geração falhou")}), 500
        return jsonify({"error": "Timeout na geração de imagem"}), 500
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/criativos/gerar-video", methods=["POST"])
@login_required
def criativos_gerar_video():
    d = request.get_json() or {}
    prompt     = (d.get("prompt_expandido") or "").strip()
    modelo     = d.get("modelo", "wan-t2v-fast")
    imagem_url = d.get("imagem_url")
    if not prompt:
        return jsonify({"error": "prompt_expandido obrigatório"}), 400
    if modelo not in _CRIATIVOS_MODELOS_VIDEO:
        return jsonify({"error": f"modelo inválido. Válidos: {list(_CRIATIVOS_MODELOS_VIDEO)}"}), 400

    slug, tipo = _CRIATIVOS_MODELOS_VIDEO[modelo]
    if tipo == "i2v" and not imagem_url:
        return jsonify({"error": "imagem_url obrigatório para modelos I2V"}), 400

    input_payload = {"prompt": prompt}
    if tipo == "i2v":
        input_payload["image"] = imagem_url

    try:
        headers = _replicate_headers()
        resp = requests.post(
            f"{_REPLICATE_BASE}/models/{slug}/predictions",
            headers=headers,
            json={"input": input_payload},
            timeout=30,
        )
        if not resp.ok:
            return jsonify({"error": f"Replicate {resp.status_code}: {resp.text[:300]}"}), 500
        pred = resp.json()
        prediction_id = pred.get("id")
        brain.salvar(
            modulo="Criativos",
            titulo=f"Vídeo iniciado {modelo}",
            inputs={"modelo": modelo, "prompt": prompt},
            output=f"prediction_id: {prediction_id}",
            model=modelo,
        )
        return jsonify({"prediction_id": prediction_id, "ok": True})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/criativos/status/<prediction_id>")
@login_required
def criativos_status(prediction_id):
    import re as _re
    if not _re.fullmatch(r'[a-zA-Z0-9]+', prediction_id or ''):
        return jsonify({"status": "failed", "error": "prediction_id inválido"}), 400
    try:
        headers = _replicate_headers()
        resp = requests.get(
            f"{_REPLICATE_BASE}/predictions/{prediction_id}",
            headers={"Authorization": headers["Authorization"]},
            timeout=15,
        )
        if not resp.ok:
            return jsonify({"status": "failed", "error": resp.text[:200]}), 500
        pred = resp.json()
        status = pred.get("status", "starting")
        url = None
        predict_time = None
        custo_usd = None
        if status == "succeeded":
            out = pred.get("output")
            url = out[0] if isinstance(out, list) else out
            metrics = pred.get("metrics") or {}
            predict_time = metrics.get("predict_time")
        return jsonify({
            "status": status,
            "url": url,
            "error": pred.get("error"),
            "predict_time": predict_time,
        })
    except RuntimeError as e:
        return jsonify({"status": "failed", "error": str(e)}), 500
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 500


@bp.route("/api/criativos/pastas", methods=["GET"])
@login_required
def criativos_listar_pastas():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome, criado_em FROM creative_folders ORDER BY nome")
        rows = cur.fetchall()
        return jsonify({"pastas": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/criativos/pastas", methods=["POST"])
@login_required
def criativos_criar_pasta():
    d = request.get_json() or {}
    nome = (d.get("nome") or "").strip()
    if not nome:
        return jsonify({"error": "nome obrigatório"}), 400
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO creative_folders (nome) VALUES (%s) RETURNING id", (nome,))
        novo_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/criativos/pastas/<int:pid>", methods=["DELETE"])
@login_required
def criativos_deletar_pasta(pid):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as n FROM creative_history WHERE folder_id = %s", (pid,))
        count = cur.fetchone()["n"]
        cur.execute("DELETE FROM creative_folders WHERE id = %s", (pid,))
        conn.commit()
        return jsonify({"ok": True, "criativos_desvinculados": count})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/criativos/historico", methods=["GET"])
@login_required
def criativos_listar_historico():
    folder_id = request.args.get("folder_id")
    tipo      = request.args.get("tipo")
    try:
        page  = max(1, int(request.args.get("page", 1)))
        limit = min(50, max(1, int(request.args.get("limit", 20))))
        if folder_id:
            folder_id = int(folder_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Parâmetros de paginação inválidos"}), 400
    offset    = (page - 1) * limit
    where, params = [], []
    if folder_id:
        where.append("folder_id = %s"); params.append(folder_id)
    if tipo in ("imagem", "video"):
        where.append("tipo = %s"); params.append(tipo)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as total FROM creative_history {where_sql}", params)
        total = cur.fetchone()["total"]
        cur.execute(
            f"SELECT id, tipo, modo, modelo, prompt_original, prompt_expandido, url_resultado, folder_id, criado_em "
            f"FROM creative_history {where_sql} ORDER BY criado_em DESC LIMIT %s OFFSET %s",
            params + [limit, offset]
        )
        items = [dict(r) for r in cur.fetchall()]
        return jsonify({"items": items, "total": total, "page": page, "pages": _math.ceil(total/limit) if total else 1})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/criativos/historico", methods=["POST"])
@login_required
def criativos_salvar_historico():
    d = request.get_json() or {}
    required = ["tipo", "modo", "modelo", "prompt_original", "prompt_expandido", "url_resultado"]
    missing = [f for f in required if not d.get(f)]
    if missing:
        return jsonify({"error": f"Campos obrigatórios: {missing}"}), 400
    conn = get_db()
    try:
        cur = conn.cursor()
        predict_time = d.get("predict_time_s")
        custo_usd = None
        if predict_time and d.get("modelo") in _CUSTO_POR_SEGUNDO:
            custo_usd = round(predict_time * _CUSTO_POR_SEGUNDO[d["modelo"]], 4)
        cur.execute(
            "INSERT INTO creative_history (tipo,modo,modelo,prompt_original,prompt_expandido,url_resultado,folder_id,predict_time_s,custo_usd) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (d["tipo"], d["modo"], d["modelo"], d["prompt_original"],
             d["prompt_expandido"], d["url_resultado"], d.get("folder_id"),
             predict_time, custo_usd)
        )
        novo_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"id": novo_id, "ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/criativos/custos")
@login_required
def criativos_custos():
    conn = get_db()
    try:
        cur = conn.cursor()
        # Gasto total do mês atual
        cur.execute(
            "SELECT COALESCE(SUM(custo_usd),0) as total, COUNT(*) as geracoes "
            "FROM creative_history "
            "WHERE custo_usd IS NOT NULL "
            "AND DATE_TRUNC('month', criado_em) = DATE_TRUNC('month', NOW())"
        )
        mes = cur.fetchone()
        # Últimas 20 gerações com custo registrado
        cur.execute(
            "SELECT modelo, prompt_original, predict_time_s, custo_usd, criado_em::text "
            "FROM creative_history "
            "WHERE custo_usd IS NOT NULL "
            "ORDER BY criado_em DESC LIMIT 20"
        )
        historico = [dict(r) for r in cur.fetchall()]
        return jsonify({
            "mes_total_usd": float(mes["total"]),
            "mes_geracoes": int(mes["geracoes"]),
            "historico": historico,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/criativos/historico/<int:hid>", methods=["DELETE"])
@login_required
def criativos_deletar_historico(hid):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM creative_history WHERE id = %s", (hid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/criativos/historico/<int:hid>/pasta", methods=["PATCH"])
@login_required
def criativos_mover_pasta(hid):
    d = request.get_json() or {}
    folder_id = d.get("folder_id")  # pode ser None para "sem pasta"
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE creative_history SET folder_id = %s WHERE id = %s", (folder_id, hid))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


def _open_browser_delayed(port, delay=2):
    time.sleep(delay)
    webbrowser.open(f"http://localhost:{port}")

