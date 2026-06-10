#!/usr/bin/env python3
"""
Piloti — Busca de Criativos de Referência via Apify (Facebook Ad Library)
Usa o actor apify/facebook-ads-scraper para buscar anúncios ativos no Brasil.

Saída: /root/clientes/piloti/criativos_referencia.md
       /root/clientes/piloti/criativos_raw.json
"""

import os, json, time, requests, urllib.parse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("/root/.env")

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
if not APIFY_TOKEN:
    raise SystemExit("APIFY_TOKEN não encontrado no .env")

ACTOR_ID = "apify~facebook-ads-scraper"
BASE_URL = "https://api.apify.com/v2"

CLIENTES = [
    {"nome": "Calixta Films",       "nicho": "Estética automotiva",          "termo": "película automotiva"},
    {"nome": "Queen Poltronas",     "nicho": "Aluguel poltrona pós-cirúrgica","termo": "aluguel poltrona pós cirurgia"},
    {"nome": "Realize Sorrisos",    "nicho": "Odontologia estética",          "termo": "lente de contato dental"},
    {"nome": "Runway",              "nicho": "Academia / Fitness",            "termo": "academia Brasília"},
    {"nome": "Odonto Uberaba",      "nicho": "Odontologia",                   "termo": "dentista Uberaba"},
    {"nome": "Hiperclin",           "nicho": "Câmara hiperbárica",            "termo": "câmara hiperbárica"},
    {"nome": "Maíra Castaldi",      "nicho": "Advocacia",                     "termo": "advogada Brasília"},
    {"nome": "Daniele Taveira",     "nicho": "Advocacia",                     "termo": "consultoria jurídica"},
    {"nome": "RD Contabilidade",    "nicho": "Contabilidade",                 "termo": "contador MEI"},
    {"nome": "Marcus",              "nicho": "Consórcio",                     "termo": "consórcio imóvel"},
    {"nome": "Amanda",              "nicho": "Seguro de vida",                "termo": "seguro de vida"},
    {"nome": "61 Eventos",          "nicho": "Eventos Brasília",              "termo": "espaço para eventos Brasília"},
    {"nome": "IOB Ortopedia",       "nicho": "Ortopedia",                     "termo": "clínica ortopédica"},
    {"nome": "Isac Rocha",          "nicho": "Personal trainer",              "termo": "treinamento funcional"},
    {"nome": "Saucker",             "nicho": "Restaurante sem glúten",        "termo": "restaurante sem glúten"},
    {"nome": "Meu Ritmo",           "nicho": "Assessoria de corrida",         "termo": "assessoria de corrida"},
]


def run_actor(termo: str, max_items: int = 8) -> list:
    url = (
        "https://www.facebook.com/ads/library/"
        f"?active_status=active&ad_type=all&country=BR"
        f"&q={urllib.parse.quote(termo)}&search_type=keyword_unordered"
    )
    payload = {"startUrls": [{"url": url}], "maxResults": max_items}

    r = requests.post(
        f"{BASE_URL}/acts/{ACTOR_ID}/runs",
        params={"token": APIFY_TOKEN},
        json=payload,
        timeout=30,
    )
    if r.status_code not in (200, 201):
        print(f"  [ERRO] {r.status_code} — {r.text[:200]}")
        return []

    run_id = r.json()["data"]["id"]
    print(f"  Run: {run_id} | aguardando...", end="", flush=True)

    for _ in range(36):
        time.sleep(5)
        sr = requests.get(
            f"{BASE_URL}/acts/{ACTOR_ID}/runs/{run_id}",
            params={"token": APIFY_TOKEN},
            timeout=15,
        )
        status = sr.json()["data"]["status"]
        print(".", end="", flush=True)
        if status == "SUCCEEDED":
            print(" OK")
            dataset_id = sr.json()["data"]["defaultDatasetId"]
            items_r = requests.get(
                f"{BASE_URL}/datasets/{dataset_id}/items",
                params={"token": APIFY_TOKEN, "limit": max_items},
                timeout=30,
            )
            return items_r.json() if items_r.status_code == 200 else []
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            print(f" FALHOU ({status})")
            return []

    print(" timeout")
    return []


def extrair_ad(ad: dict) -> dict:
    snap = ad.get("snapshot") or {}
    ad_id = ad.get("adArchiveID") or ad.get("adArchiveId") or ad.get("adId", "")

    resultado = {
        "pagina": snap.get("pageName") or ad.get("pageName", "—"),
        "pagina_url": snap.get("pageProfileUri", ""),
        "ad_id": ad_id,
        "link_ad": f"https://www.facebook.com/ads/library/?id={ad_id}" if ad_id else "",
        "texto": (snap.get("body", {}) or {}).get("text", "") or snap.get("caption", ""),
        "cta": snap.get("ctaText", ""),
        "tipo": ad.get("gatedType", ""),
        "inicio": ad.get("startDateFormatted", "")[:10] if ad.get("startDateFormatted") else "",
        "imagens": [],
        "videos": [],
        "cards": [],
    }

    # Imagem principal
    for key in ("resizedImageUrl", "originalImageUrl"):
        val = snap.get(key)
        if val:
            resultado["imagens"].append(val)
            break

    # Cards (carrossel)
    for card in (snap.get("cards") or []):
        card_info = {}
        for key in ("resizedImageUrl", "originalImageUrl"):
            if card.get(key):
                card_info["imagem"] = card[key]
                break
        if card.get("videoHdUrl") or card.get("videoSdUrl"):
            card_info["video"] = card.get("videoHdUrl") or card.get("videoSdUrl")
        if card.get("title"):
            card_info["titulo"] = card["title"]
        if card_info:
            resultado["cards"].append(card_info)

    # Vídeo principal
    for key in ("videoHdUrl", "videoSdUrl"):
        val = snap.get(key)
        if val:
            resultado["videos"].append(val)
            break

    return resultado


def gerar_markdown(resultados: list) -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")
    linhas = [
        "# Piloti — Criativos de Referência (Ad Library)",
        f"> Gerado em {hoje} via Apify · Facebook Ad Library Brasil · Anúncios ativos\n",
    ]

    for item in resultados:
        linhas.append(f"---\n## {item['cliente']}")
        linhas.append(f"**Nicho:** {item['nicho']}  |  **Termo:** `{item['termo']}`\n")

        if not item["ads"]:
            linhas.append("_Nenhum anúncio encontrado._\n")
            continue

        for i, ad in enumerate(item["ads"], 1):
            linhas.append(f"### {i}. {ad['pagina']}")
            if ad["pagina_url"]:
                linhas.append(f"Página: {ad['pagina_url']}")
            if ad["link_ad"]:
                linhas.append(f"**Ad Library:** {ad['link_ad']}")
            if ad["texto"]:
                texto = ad["texto"][:200].replace("\n", " ")
                linhas.append(f"Texto: _{texto}_")
            if ad["cta"]:
                linhas.append(f"CTA: `{ad['cta']}`")
            if ad["inicio"]:
                linhas.append(f"Ativo desde: {ad['inicio']}")
            if ad["imagens"]:
                linhas.append(f"Imagem: {ad['imagens'][0]}")
            if ad["videos"]:
                linhas.append(f"Vídeo: {ad['videos'][0]}")
            if ad["cards"]:
                linhas.append(f"Cards: {len(ad['cards'])} itens no carrossel")
                for c in ad["cards"][:3]:
                    if c.get("imagem"):
                        linhas.append(f"  - img: {c['imagem']}")
                    if c.get("video"):
                        linhas.append(f"  - video: {c['video']}")
            linhas.append("")

    return "\n".join(linhas)


def main():
    resultados = []
    total = len(CLIENTES)
    os.makedirs("/root/clientes/piloti", exist_ok=True)

    for i, cliente in enumerate(CLIENTES, 1):
        print(f"\n[{i}/{total}] {cliente['nome']} → '{cliente['termo']}'")
        ads_raw = run_actor(cliente["termo"], max_items=8)

        ads = [extrair_ad(a) for a in ads_raw if a.get("adArchiveID") or a.get("adId")]
        print(f"  ✓ {len(ads)} criativos")

        resultados.append({
            "cliente": cliente["nome"],
            "nicho": cliente["nicho"],
            "termo": cliente["termo"],
            "ads": ads,
        })

        # Salva JSON parcial
        with open("/root/clientes/piloti/criativos_raw.json", "w") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)

        time.sleep(2)

    # Markdown final
    md = gerar_markdown(resultados)
    out_path = "/root/clientes/piloti/criativos_referencia.md"
    with open(out_path, "w") as f:
        f.write(md)

    print(f"\n✅ Salvo em: {out_path}")


if __name__ == "__main__":
    main()
