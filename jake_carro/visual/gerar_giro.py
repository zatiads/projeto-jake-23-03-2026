"""
Monta o giro 360 do HB20 com vídeo de IA (Kling 2.5 no Replicate).
Os 8 ângulos de estúdio (ia/a0..a7) são pontos de controle: cada trecho de vídeo gira o carro de um ângulo
exatamente até o próximo (start_image → end_image). Emendados, fecham a volta sem costura.

Uso: python gerar_giro.py 1        → só o trecho 1 (teste)
     python gerar_giro.py todos    → os 8 trechos
"""
import base64
import io
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image

AQUI = Path(__file__).resolve().parent
IA = AQUI / "ia"
SAIDA = IA / "giro"
MODELO = "kwaivgi/kling-v2.5-turbo-pro"
H = {"Authorization": f"Bearer {os.environ['REPLICATE_API_TOKEN']}", "Prefer": "wait=1"}

ANGULOS = ["a0_frente", "a1_frente_direita", "a2_lado_direito", "a3_traseira_direita",
           "a4_traseira", "a5_traseira_esquerda", "a6_lado_esquerdo", "a7_frente_esquerda"]

PROMPT = ("Luxury automotive studio turntable shot. The car rotates slowly and smoothly in place on a hidden turntable, "
          "at a constant speed, from the angle in the first frame to the angle in the last frame. The camera is locked: "
          "no camera movement, no zoom, no cuts. The car stays centered and the same size. Same dark navy studio, glossy "
          "reflective black floor, cyan rim light, headlights on. The car's design never changes.")
NEGATIVO = "camera movement, zoom, cut, morphing, deformed car, different car, people, text, flicker"


def data_uri(nome):
    img = Image.open(IA / f"{nome}.png").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def trecho(n):
    """Trecho n gira do ângulo n até o n+1 (o 8º volta pro 0)."""
    ini, fim = ANGULOS[n - 1], ANGULOS[n % 8]
    destino = SAIDA / f"trecho_{n}.mp4"
    if destino.exists():
        return destino
    corpo = {"input": {"prompt": PROMPT, "negative_prompt": NEGATIVO, "duration": 5,
                       "start_image": data_uri(ini), "end_image": data_uri(fim)}}
    for tentativa in range(12):  # conta com pouco crédito: 1 pedido por vez, o 429 manda esperar
        r = requests.post(f"https://api.replicate.com/v1/models/{MODELO}/predictions", headers=H, json=corpo,
                          timeout=120)
        if r.status_code != 429:
            break
        time.sleep(15 * (tentativa + 1))
    r.raise_for_status()
    pred = r.json()
    print(f"trecho {n}: {ini} → {fim} ({pred['id']})", flush=True)
    while pred["status"] not in ("succeeded", "failed", "canceled"):
        time.sleep(10)
        pred = requests.get(pred["urls"]["get"], headers=H, timeout=30).json()
    if pred["status"] != "succeeded":
        print(f"trecho {n} falhou: {pred.get('error')}", flush=True)
        return None
    url = pred["output"] if isinstance(pred["output"], str) else pred["output"][0]
    destino.write_bytes(requests.get(url, timeout=120).content)
    print(f"trecho {n} ok", flush=True)
    return destino


if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == "todos":
        for n in range(1, 9):
            trecho(n)
    else:
        trecho(int(sys.argv[1]))
