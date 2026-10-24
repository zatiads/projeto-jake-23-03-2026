"""
Carro em 3/4 traseiro pro modo andando: recorta o render de estúdio (a3) e
alinha igual aos quadros do giro (alinhar_giro.py), só que no dobro da resolução.
Saída: ../servidor/cockpit/carro_pose.webp (1520x800, fundo transparente).
"""
from pathlib import Path

import numpy as np
from PIL import Image
from rembg import new_session, remove
from scipy import ndimage

AQUI = Path(__file__).resolve().parent
X = 2                                   # dobro do quadro do giro (760x400, carro 230, chão 352)
W, H, ALTURA_CARRO, CHAO = 760 * X, 400 * X, 230 * X, 352 * X

img = Image.open(AQUI / "ia" / "a3_traseira_direita.png").convert("RGB")
rgba = np.array(remove(img, session=new_session("isnet-general-use")))
alfa = rgba[:, :, 3]
rot, n = ndimage.label(alfa > 128)
maior = 1 + int(np.argmax(ndimage.sum(np.ones_like(rot), rot, range(1, n + 1))))
miolo = ndimage.binary_fill_holes(rot == maior)
borda = ndimage.binary_dilation(miolo, iterations=2)
rgba[:, :, 3] = np.where(miolo, np.maximum(alfa, 235), np.where(borda, alfa, 0))

# corta o reflexo do piso: abaixo da última linha "larga" (as rodas)
linhas = np.where(miolo.any(axis=1))[0]
largura = miolo.sum(axis=1)
base = next(y for y in range(linhas[-1], linhas[0], -1) if largura[y] > 0.35 * largura.max())
rgba[base + 1:, :, 3] = 0
xs = np.where(miolo[: base + 1].any(axis=0))[0]
carro = Image.fromarray(rgba).crop((xs[0], linhas[0], xs[-1] + 1, base + 1))

esc = min(ALTURA_CARRO / carro.height, (W - 48) / carro.width)
carro = carro.resize((round(carro.width * esc), round(carro.height * esc)), Image.LANCZOS)
tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
tela.paste(carro, ((W - carro.width) // 2, CHAO - carro.height), carro)
destino = AQUI.parent / "servidor" / "cockpit" / "carro_tras34.webp"
tela.save(destino, quality=88, method=6)
print("ok", carro.size, destino.stat().st_size // 1024, "KB")
