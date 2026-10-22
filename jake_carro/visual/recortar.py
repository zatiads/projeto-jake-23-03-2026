"""Recorta o carro de cada quadro, alinha pelo chão e salva em webp com transparência."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from rembg import new_session, remove
from scipy import ndimage

ENTRADA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
LARG, ALT, ALTURA_CARRO, CHAO = 900, 420, 250, 400

sessao = new_session("isnet-general-use")
for i, quadro in enumerate(sorted(ENTRADA.glob("*.png"))):
    img = Image.open(quadro).convert("RGB")
    rgba = remove(img, session=sessao)
    alfa = np.array(rgba)[:, :, 3]
    rotulos, n = ndimage.label(alfa > 128)
    if n == 0:
        continue
    tamanhos = ndimage.sum(np.ones_like(rotulos), rotulos, range(1, n + 1))
    principal = int(np.argmax(tamanhos)) + 1
    mascara = rotulos == principal
    # Miolo opaco (vidro escuro às vezes vira "buraco"); borda mantém a suavidade do recorte.
    miolo = ndimage.binary_fill_holes(mascara)
    borda = ndimage.binary_dilation(miolo, iterations=2)
    arr = np.array(rgba)
    alfa = arr[:, :, 3]
    arr[:, :, 3] = np.where(miolo, np.maximum(alfa, 235), np.where(borda, alfa, 0))
    mascara = miolo
    ys, xs = np.where(mascara)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    if x0 <= 3 or x1 >= alfa.shape[1] - 4 or y1 >= alfa.shape[0] - 3:
        print(quadro.name, "cortado na borda, descartado", flush=True)
        continue
    carro = Image.fromarray(arr).crop((x0, y0, x1 + 1, y1 + 1))
    escala = ALTURA_CARRO / carro.height
    carro = carro.resize((max(1, int(carro.width * escala)), ALTURA_CARRO), Image.LANCZOS)
    tela = Image.new("RGBA", (LARG, ALT), (0, 0, 0, 0))
    tela.paste(carro, ((LARG - carro.width) // 2, CHAO - carro.height), carro)
    tela.save(SAIDA / f"{i:03d}.webp", quality=82, method=6)
    print(quadro.name, carro.size, flush=True)
