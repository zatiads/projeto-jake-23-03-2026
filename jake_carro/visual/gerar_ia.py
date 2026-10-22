"""
Gera o visual do cockpit com a IA de imagem da OpenAI (gpt-image-2):
1) render de estúdio do HB20 real do Bruno (a partir das fotos)
2) ângulos em volta do carro no mesmo estúdio (pro giro 360)
3) conceitos das telas do cockpit

Uso: python gerar_ia.py heroi | angulos | telas
"""
import base64
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import OpenAI

AQUI = Path(__file__).resolve().parent
SAIDA = AQUI / "ia"
FOTOS = AQUI / "fotos"
MODELO = os.environ.get("JAKE_CARRO_MODELO_IMAGEM", "gpt-image-2")

cliente = OpenAI(timeout=300, max_retries=1)

CARRO = """The reference photos all show the SAME real car: my own 2013 Hyundai HB20 hatchback (first generation,
Brazilian market), dark metallic graphite grey paint, 5 doors, black grille with chrome Hyundai logo, round fog
lights, silver plastic hubcaps on steel wheels, red/white tail lights, small roof spoiler.
Reproduce EXACTLY this car: same body shape, proportions, headlights, tail lights, hubcaps, bumpers, mirrors, color
and every design detail. Do NOT turn it into a newer HB20, an i20 or any other model. Only improve the condition:
freshly washed and polished paint with deep clean reflections, clean tyres, no dirt, no scratches, no dents.
License plate: clean blank Brazilian Mercosul plate (white with the blue top band), no characters."""

ESTUDIO = """Premium automotive studio photograph, like a luxury car launch: dark seamless studio fading from
near-black (#04070D) to deep navy, glossy black reflective floor with a soft mirror reflection of the car, a thin
electric-cyan (#22D3EE) rim light tracing the roofline, pillars and body contours, cool blue ambient fill, headlights
ON with a soft white glow, a faint cyan light line on the floor under the car. Cinematic, ultra sharp, photorealistic,
high dynamic range. Whole car in frame with comfortable margin, car centered, camera at headlight height.
No text, no watermark, no people, no other objects."""

ANGULOS = {
    "a0_frente": "straight front view",
    "a1_frente_direita": "front three-quarter view from the car's right side (passenger side)",
    "a2_lado_direito": "pure side profile from the car's right side, front of the car pointing to the right of the image",
    "a3_traseira_direita": "rear three-quarter view from the car's right side",
    "a4_traseira": "straight rear view",
    "a5_traseira_esquerda": "rear three-quarter view from the car's left side (driver side)",
    "a6_lado_esquerdo": "pure side profile from the car's left side, front of the car pointing to the left of the image",
    "a7_frente_esquerda": "front three-quarter view from the car's left side (driver side)",
}

VISUAL = """DESIGN DIRECTION (applies to every screen):
- Device: 9-inch landscape Android car head unit, 1024x600, installed in a 2013 Hyundai HB20. Show ONLY the flat
  screen UI, edge to edge, no device frame, no hands, no car interior.
- Product: "JAKE", a voice AI co-pilot (like JARVIS) that runs the car computer. The driver talks to it; it answers
  out loud and calls him "patrão". Interaction is 99% by voice, so the screen is glanceable, never busy.
- Luxury + high-tech + fluid: think Mercedes MBUX Hyperscreen, Porsche Taycan, Lucid Air (inspiration only, original
  design). Near-black navy background (#04070D → #0B1A2B), single accent electric cyan #22D3EE (matches the car's blue
  LED ambient strip), icy white text, secondary text blue-grey #8FB3C6. Layered dark glass, 1px hairlines, soft cyan
  glow only where it means something. NO boxy web-dashboard cards, NO clutter: floating HUD typography with generous
  negative space. One geometric technical sans-serif (Eurostile / Chakra Petch feel) with tabular numerals, big
  confident numbers, small uppercase letter-spaced labels.
- Branding: small chrome Hyundai logo + "HB20" wordmark at the top-left, discreet and elegant.
- JAKE orb: a glowing sphere with thin orbiting rings and a soft halo; its colour shows state — cyan = listening,
  violet = thinking, green = done, amber = offline. A thin live voice waveform next to it when listening.
- The hero car is the user's real graphite-grey 2013 HB20 hatch exactly as in the reference image (studio render,
  cyan rim light, reflection on a glossy floor).
- ALL interface text must be in Brazilian Portuguese, spelled exactly as given below, crisp and legible.
- Touch targets large (>= 48px), high contrast, readable at a glance while driving."""

TELAS = {
    "t1_parado": """SCREEN 1 — "PARADO" (car parked / just started; morning welcome).
Layout: the hero car large in the center, slightly 3/4, floating over a glossy floor with a cyan light ring under it.
Top bar: left = Hyundai logo + "HB20"; center = time "08:12" big and "qui, 23 out" small; right = "4G" signal icon and
"18° Varginha".
Left side, floating text: label "BOM DIA, PATRÃO" and below "Varginha · 18°C · máx 27° · chuva 10%".
Right side, floating list: label "HOJE" then "10:00  Call Gestor" and "Dia todo  Lançar gastos da casa".
Bottom center: the JAKE orb in CYAN (listening) with caption "Ouvindo…" and the live transcript
"“Jake, coloca no mapa São Tomé das Letras”".
Bottom corners: two pill buttons "Modo viagem" (left) and "Resumo do dia" (right).
Very subtle: thin perspective road lines on the floor.""",
    "t2_andando": """SCREEN 2 — "ANDANDO" (driving; minimal, glanceable).
Huge speed number "62" with small "km/h" on the left third, a thin cyan arc gauge around it.
Center: the hero car small and seen from behind/above at a slight angle on an abstract road made of glowing cyan
perspective lines that suggest motion (speed lines).
Right third: next navigation step "Em 400 m vire à direita" with a big arrow, and below "Chegada 16:31 · 87 km".
Bottom strip: now playing "Froid" with "Spotify", play/pause and next icons; the JAKE orb small in VIOLET (thinking)
with caption "Pensando…".
Top bar same as screen 1 (Hyundai logo + "HB20", time "14:52", "27° Varginha").
Nothing else on screen.""",
    "t3_viagem": """SCREEN 3 — "MODO VIAGEM" (road trip + automatic arrival message).
Title at top-left under the logo: small label "MODO VIAGEM" in cyan and large "São Tomé das Letras".
Top right: "Chegada 16:31" and "Faltam 5 min".
Left 60%: a dark stylised map with a glowing cyan route line from "Varginha" to "São Tomé das Letras", the car position
as a pulsing dot near the end.
Right 40%, floating: a highlighted green-accent element "Aviso de chegada enviado" with a WhatsApp-style check and the
message preview "Chegando em 5 minutinhos!"; below it "Trilha sonora: Estrada" and "Próxima parada: Posto em 12 km".
Bottom: the JAKE orb in GREEN (done) with caption "Feito" and the line
"“Avisei que você chega em 5 minutos, patrão.”".""",
    "t4_resumo": """SCREEN 4 — "RESUMO DO DIA" (end of day, car parked at night; darker, calmer).
Top-left: small cyan label "RESUMO DO DIA" and large "Quinta, 22 de outubro".
A row of four big floating stats with tiny labels: "RODADOS 128 km", "AO VOLANTE 2h41", "CONSUMO 11,8 km/l",
"COMBUSTÍVEL R$ 74".
Below left: "ANÚNCIOS HOJE" with a minimal elegant horizontal bar chart (thin cyan bars) for "Runway", "Saucker",
"mrrunners", "RD Contabilidade".
Below right: "AMANHÃ" with "10:00  Call Gestor" and "Dia todo  Lançar gastos da casa".
A small hero car silhouette at the bottom-right with the headlights off and a faint cyan outline.
Bottom: the JAKE orb in CYAN, calm, with the line "“Fechou o dia, patrão. Descansa aí.”".""",
}


def salvar(nome, resp):
    caminho = SAIDA / f"{nome}.png"
    caminho.write_bytes(base64.b64decode(resp.data[0].b64_json))
    print("ok", caminho.name, flush=True)
    return caminho


def editar(nome, prompt, imagens, tamanho="1536x1024"):
    arquivos = [open(p, "rb") for p in imagens]
    try:
        resp = cliente.images.edit(model=MODELO, image=arquivos, prompt=prompt, size=tamanho, quality="high")
        return salvar(nome, resp)
    except Exception as e:
        print("ERRO", nome, e, flush=True)
    finally:
        for f in arquivos:
            f.close()


def fotos_ref():
    return [FOTOS / n for n in ("frente_direita.jpg", "frente_esquerda.jpg", "traseira_esquerda.jpg")]


def heroi():
    prompt = (f"{CARRO}\n\n{ESTUDIO}\n\nCamera angle: front three-quarter view from the car's right side, "
              "slightly low camera, the car looking powerful and premium.")
    editar("heroi", prompt, fotos_ref())


def angulos():
    heroi_img = SAIDA / "heroi.png"
    refs = [heroi_img, *fotos_ref()]
    def um(item):
        nome, angulo = item
        prompt = (f"The FIRST reference image is the approved studio render of the car; match its studio set, lighting, "
                  f"floor, paint finish and colour EXACTLY so all angles look like one continuous photo shoot. "
                  f"The other references are real photos of the same car for shape details.\n\n{CARRO}\n\n{ESTUDIO}\n\n"
                  f"Camera angle for this image: {angulo}. Same camera distance and height as the first reference, "
                  f"car centered, same scale.")
        editar(nome, prompt, refs)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(um, ANGULOS.items()))


def telas():
    heroi_img = SAIDA / "heroi.png"
    def uma(item):
        nome, tela = item
        prompt = (f"Design a top-of-the-line in-car infotainment screen (UI concept, flat screen render). "
                  f"The reference image is the hero car to use in the UI.\n\n{VISUAL}\n\n{tela}")
        editar(nome, prompt, [heroi_img])
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(uma, TELAS.items()))


if __name__ == "__main__":
    SAIDA.mkdir(exist_ok=True)
    {"heroi": heroi, "angulos": angulos, "telas": telas}[sys.argv[1]]()
