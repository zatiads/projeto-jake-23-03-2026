import json
import os
import re as _re
import time
import requests
import base64

from flask import Blueprint, jsonify, request

from .shared import get_db, login_required, anthropic_client

bp = Blueprint('site_architect', __name__)


# ── API: Site Architect — geração de landing page ─────────────────────────────

_SITE_ARCH_SYSTEM = """\
Você é um Site Architect especialista em landing pages de alta conversão.

OBJETIVO:
- Receber uma URL de referência (layout base) e o contexto de negócio do usuário.
- Entregar UMA landing page completa, em HTML + TailwindCSS, moderna, responsiva e limpa.
- Manter a estrutura de seções da referência (Hero, Benefícios, Prova Social, FAQ, Rodapé),
  mas SEM copiar código ou textos literalmente.

REGRAS:
1. Use SOMENTE TailwindCSS (classes utilitárias) — não use CSS em <style>.
2. Não importe fontes externas; use system fonts (font-sans).
3. Estrutura básica:
   <html lang="pt-BR">
     <head> (meta + título + link Tailwind via CDN)
     <body class="bg-slate-950 text-slate-50 ..."> ... </body>
   </html>
4. Seções mínimas:
   - Hero com headline forte, subheadline e call-to-action.
   - Seção de benefícios / features.
   - Seção de prova social (depoimentos, métricas ou logos).
   - Seção de FAQ.
   - Rodapé simples.
5. Substitua completamente qualquer texto da referência pela copy do usuário (hero_copy, extra_copy, contexto).
6. Nunca use textos genéricos como "Lorem ipsum".
7. Saída: retorne APENAS o HTML final, pronto para ser salvo como index.html.
"""


def _save_data_url_image(kind: str, data_url: str, index: int | None = None) -> str | None:
    """
    Salva uma imagem enviada como data URL em static/uploads/architect
    e retorna a URL pública (/static/...).
    """
    if not data_url or not isinstance(data_url, str) or "," not in data_url:
        return None
    try:
        header, b64 = data_url.split(",", 1)
        mime = "image/png"
        if header.startswith("data:") and ";base64" in header:
            mime = header[5:header.index(";base64")] or "image/png"
        ext = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }.get(mime, "png")

        # Garante diretório
        base_dir = os.path.join(app.static_folder, "uploads", "architect")
        os.makedirs(base_dir, exist_ok=True)

        suffix = f"_{index}" if index is not None else ""
        filename = f"{int(time.time())}_{kind}{suffix}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(base_dir, filename)

        with open(filepath, "wb") as f:
            f.write(base64.b64decode(b64))

        # Caminho público
        return f"/static/uploads/architect/{filename}"
    except Exception:
        return None


def _anthropic_client_46():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return _anthropic.Anthropic(api_key=key) if key else None


@bp.route("/api/site-architect/generate", methods=["POST"])
@login_required
def api_site_arch_generate():
    """
    Gera uma landing page completa (HTML+Tailwind) a partir de:
    - URL de referência (para entender seções)
    - contexto de negócio e copy
    - metadados de assets (logo/hero/gallery) em data URLs (opcionais)
    """
    data = request.get_json(force=True) or {}
    ref_url = (data.get("reference_url") or "").strip()
    contexto = (data.get("business_context") or "").strip()
    hero_copy = (data.get("hero_copy") or "").strip()
    extra_copy = (data.get("extra_copy") or "").strip()
    template_kind = (data.get("template_kind") or "").strip() or "lead"
    assets = data.get("assets") or {}

    if not any((ref_url, contexto, hero_copy)):
        return jsonify({"error": "Preencha pelo menos URL de referência, contexto ou hero copy."}), 400

    client = _anthropic_client_46()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada para o Site Architect."}), 500

    template_hints = {
        "lead": (
            "Tipo de página: CAPTURA DE LEADS.\n"
            "Foque em formulário ou botão de WhatsApp como ação principal, promessa forte no hero, "
            "seção de benefícios enxuta e prova social objetiva.\n"
        ),
        "lancamento": (
            "Tipo de página: LANÇAMENTO / FUNIL.\n"
            "Inclua seções claras de promessa, prova social forte, módulo para detalhes do evento/curso, "
            "bônus e garantia. Crie sensação de urgência real e estrutura pensando em tráfego frio/morno.\n"
        ),
        "servico-local": (
            "Tipo de página: SERVIÇO LOCAL.\n"
            "Destaque endereço/região atendida, fotos do espaço, depoimentos locais, mapa ou instruções de "
            "como chegar e foco em agendamento (botão de WhatsApp ou telefone visível o tempo todo).\n"
        ),
        "saas": (
            "Tipo de página: SOFTWARE / SAAS.\n"
            "Use blocos de features claros, captura de e-mail para teste grátis, comparativo rápido com "
            "a forma antiga de fazer, seção de pricing simples e prova social com logos/métricas.\n"
        ),
        "ecommerce": (
            "Tipo de página: E‑COMMERCE SIMPLES (1 PRODUTO).\n"
            "Hero com foto forte do produto, benefícios em bullets, seção de detalhes/tabela, prova social "
            "com reviews e um bloco de perguntas frequentes focado em objeções de compra.\n"
        ),
    }
    template_hint = template_hints.get(template_kind, template_hints["lead"])

    # resumo textual + URLs dos assets
    logo_present = bool(assets.get("logo"))
    hero_present = bool(assets.get("hero"))
    gallery_list = assets.get("gallery") or []
    benefits_list = assets.get("benefits") or []
    social_list = assets.get("social") or []
    gallery_len = len(gallery_list)
    benefits_len = len(benefits_list)
    social_len = len(social_list)

    logo_url = _save_data_url_image("logo", assets.get("logo")) if logo_present else None
    hero_url = _save_data_url_image("hero", assets.get("hero")) if hero_present else None
    gallery_urls: list[str] = []
    for idx, item in enumerate(gallery_list[:6]):
        url = _save_data_url_image("gallery", item, index=idx + 1)
        if url:
            gallery_urls.append(url)

    benefits_urls: list[str] = []
    for idx, item in enumerate(benefits_list[:6]):
        url = _save_data_url_image("benefits", item, index=idx + 1)
        if url:
            benefits_urls.append(url)

    social_urls: list[str] = []
    for idx, item in enumerate(social_list[:6]):
        url = _save_data_url_image("social", item, index=idx + 1)
        if url:
            social_urls.append(url)

    assets_summary_lines = [
        "Resumo dos assets visuais disponíveis:",
        f"- Logotipo enviado: {'sim' if logo_present else 'não'}",
        f"- Banner principal enviado: {'sim' if hero_present else 'não'}",
        f"- Imagens de produto/serviço na galeria: {gallery_len}",
        f"- Imagens específicas para BENEFÍCIOS: {benefits_len}",
        f"- Imagens específicas para PROVA SOCIAL / RESULTADOS: {social_len}",
        "",
        "URLs de imagem já hospedadas (use-as diretamente nos elementos <img src=\"...\"> do HTML gerado, sem buscar imagens novas):",
        f"- LOGO_URL: {logo_url or '[nenhum logotipo enviado]'}",
        f"- HERO_URL: {hero_url or '[nenhum banner principal enviado]'}",
        "- GALLERY_URLS (use em cards/seção de produtos/serviços):",
    ]
    for u in gallery_urls:
        assets_summary_lines.append(f"  - {u}")
    assets_summary_lines.append("- BENEFITS_URLS (use como ícones/fotos na seção de Benefícios):")
    for u in benefits_urls:
        assets_summary_lines.append(f"  - {u}")
    assets_summary_lines.append("- SOCIAL_PROOF_URLS (use em depoimentos, prints de resultado, logos de clientes na seção de Prova Social):")
    for u in social_urls:
        assets_summary_lines.append(f"  - {u}")
    assets_summary_lines.append(
        "Orientação: se LOGO_URL existir, use-o no cabeçalho/nav da página. "
        "Se HERO_URL existir, use como imagem principal na seção Hero (banner do topo). "
        "Use GALLERY_URLS em cards ou grades na seção de produtos/serviços, BENEFITS_URLS na seção de benefícios "
        "e SOCIAL_PROOF_URLS na seção de prova social/resultados, sem inventar URLs adicionais."
    )
    assets_summary = "\n".join(assets_summary_lines)

    # Se tiver URL de referência, tentamos trazer o HTML bruto só para dar contexto estrutural ao modelo.
    reference_snippet = ""
    if ref_url:
        try:
            r = requests.get(ref_url, timeout=8)
            if r.ok:
                txt = r.text
                # Limitamos o HTML para não estourar contexto.
                reference_snippet = txt[:6000]
        except Exception:
            reference_snippet = ""

    user_instructions = "\n".join(
        [
            f"URL de referência (se disponível): {ref_url or 'não fornecida'}",
            "",
            template_hint,
            "",
            assets_summary,
            "",
            "HTML bruto (trecho) da referência, se carregado com sucesso:",
            reference_snippet or "[não carregado ou indisponível]",
            "",
            "Contexto do negócio:",
            contexto or "[não informado]",
            "",
            "Copy principal (Hero):",
            hero_copy or "[não informado]",
            "",
            "Outras informações relevantes (benefícios, provas, objeções etc.):",
            extra_copy or "[não informado]",
            "",
            "Gere agora o HTML completo seguindo as regras do sistema.",
        ]
    )

    try:
        ctx = brain.contexto(contexto[:80])
        system_prompt = _SITE_ARCH_SYSTEM
        if ctx:
            system_prompt = system_prompt + f"\n\n## Briefing do Cliente\n{ctx}"
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_instructions}],
        )
        html = (msg.content[0].text or "").strip()
        brain.salvar(
            modulo="Site Architect",
            titulo=f"Landing Page — {template_kind or 'custom'}",
            inputs={"business_context": contexto, "hero_copy": hero_copy, "template_kind": template_kind},
            output=html,
            model="claude-sonnet-4-6",
            cliente=contexto[:80],
        )
        return jsonify({"html": html})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/site-architect/refine", methods=["POST"])
@login_required
def api_site_arch_refine():
    """
    Recebe o HTML atual + uma instrução de chat e devolve
    uma nova versão do HTML com o ajuste aplicado.
    Ex.: "mude a cor dos botões para verde".
    """
    data = request.get_json(force=True) or {}
    instruction = (data.get("instruction") or "").strip()
    html = (data.get("html") or "").strip()
    if not html or not instruction:
        return jsonify({"error": "Envie 'html' e 'instruction'."}), 400

    client = _anthropic_client_46()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada para o Site Architect."}), 500

    refine_prompt = (
        "Você receberá o HTML atual de uma landing page e uma instrução de edição.\n"
        "Ajuste SOMENTE o necessário no HTML para cumprir a instrução, mantendo o resto intacto.\n"
        "Retorne apenas o novo HTML completo, sem explicações.\n\n"
        f"Instrução do usuário: {instruction}\n\n"
        "HTML atual:\n"
        f"{html}\n"
    )

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=_SITE_ARCH_SYSTEM,
            messages=[{"role": "user", "content": refine_prompt}],
        )
        new_html = (msg.content[0].text or "").strip()
        brain.salvar(
            modulo="Site Architect",
            titulo=f"Refinamento — {instruction[:50]}",
            inputs={"instrucao": instruction[:300] if instruction else ""},
            output=new_html,
            model="claude-sonnet-4-6",
        )
        return jsonify(
            {
                "html": new_html,
                "summary": f"Ajuste aplicado: {instruction}",
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/site-architect/export", methods=["POST"])
@login_required
def api_site_arch_export():
    """
    Exporta o HTML atual como um index.html pronto para deploy.

    A lógica de download é feita no front-end (Blob + link temporário),
    então aqui retornamos apenas JSON com o conteúdo.
    """
    data = request.get_json(force=True) or {}
    html = (data.get("html") or "").strip()
    if not html:
        return jsonify({"error": "Envie o HTML para exportação."}), 400
    return jsonify({"filename": "index.html", "html": html})


@bp.route("/api/site-architect/export-react", methods=["POST"])
@login_required
def api_site_arch_export_react():
    """
    Converte o HTML em um componente React simples (TSX) usando dangerouslySetInnerHTML.
    É a forma mais segura de preservar a estrutura Tailwind sem tentar "reactificar" tudo.
    """
    data = request.get_json(force=True) or {}
    html = (data.get("html") or "").strip()
    component_name_raw = (data.get("component_name") or "LandingGenerated").strip()
    if not html:
        return jsonify({"error": "Envie o HTML para exportação React."}), 400

    # Sanitiza nome do componente para PascalCase
    safe_name = "".join(ch if ch.isalnum() else " " for ch in component_name_raw).title().replace(" ", "")
    if not safe_name:
        safe_name = "LandingGenerated"

    # Escapa caracteres problemáticos dentro do template string
    esc_html = html.replace("`", "\\`").replace("${", "\\${")

    code = f"""import React from "react";

type Props = {{
  // Você pode passar props aqui no futuro se quiser tornar a landing dinâmica
}};

const {safe_name}: React.FC<Props> = () => {{
  return (
    <div
      dangerouslySetInnerHTML={{{{{ __html: `{esc_html}` }}}}}
    />
  );
}};

export default {safe_name};
"""
    filename = f"{safe_name}.tsx"
    return jsonify({"filename": filename, "code": code})


def _deploy_to_vercel(project_name: str, index_html: str) -> tuple[bool, str, dict]:
    """
    Esqueleto de integração com a API da Vercel.

    Fluxo esperado:
    1. Criar um deployment com 1 arquivo (index.html) via API REST:
       POST https://api.vercel.com/v13/deployments
       Headers:
         - Authorization: Bearer VERCEL_TOKEN
         - Content-Type: application/json
       Body (simplificado):
         {
           "name": "<project_name>",
           "files": [{ "file": "index.html", "data": "<conteúdo do HTML>" }],
           "projectSettings": { "framework": "static" }
         }
    2. A Vercel devolve a URL do preview e, se o projeto estiver conectado a um domínio,
       também o domínio final.
    """
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token:
        return (
            False,
            "Configure VERCEL_TOKEN no .env para publicar automaticamente.",
            {},
        )
    payload = {
        "name": project_name or "jake-architect-site",
        "files": [
            {
                "file": "index.html",
                "data": index_html,
            }
        ],
        "projectSettings": {
            "framework": "static",
        },
    }
    try:
        r = requests.post(
            "https://api.vercel.com/v13/deployments",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=40,
        )
        if not r.ok:
            try:
                err = r.json()
            except Exception:
                err = {"error": r.text}
            return False, f"Vercel API {r.status_code}: {err.get('error') or err}", err
        data = r.json()
        url = data.get("url")
        inspector = data.get("inspectorUrl") or f"https://vercel.com/{url}" if url else ""
        return True, url or inspector or "Deploy criado.", data
    except Exception as exc:
        return False, f"Falha na chamada para a Vercel: {exc}", {}


@bp.route("/api/site-architect/deploy", methods=["POST"])
@login_required
def api_site_arch_deploy():
    """
    Cria um deploy estático na Vercel com base em um index.html.

    - Requer VERCEL_TOKEN no .env.
    - project_name é opcional (usa um nome padrão quando vazio).
    """
    data = request.get_json(force=True) or {}
    html = (data.get("html") or "").strip()
    project_name = (data.get("project_name") or "jake-architect-site").strip()
    if not html:
        return jsonify({"error": "Envie o HTML para publicar."}), 400

    ok, msg, extra = _deploy_to_vercel(project_name, html)
    if not ok:
        hint = (
            "Você pode exportar o index.html e subir manualmente na Vercel "
            "caso prefira configurar o projeto pelo painel web."
        )
        return jsonify({"error": msg, "hint": hint}), 502

    return jsonify(
        {
            "message": "Deploy criado com sucesso.",
            "url": extra.get("url"),
            "inspectorUrl": extra.get("inspectorUrl"),
            "project": project_name,
        }
    )



# ══════════════════════════════════════════════════════════════════════════
#  ABA SUBIR ANÚNCIOS — CRUD de perfis de clientes
# ══════════════════════════════════════════════════════════════════════════

