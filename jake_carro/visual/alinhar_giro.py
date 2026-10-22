"""
Recorta o carro de cada quadro do giro (sem o fundo do vídeo) e alinha todos pelas rodas:
mesmo ponto de apoio no chão e mesma altura. Assim ele gira certinho em cima do anel do cockpit,
e o piso/reflexo/neon passam a ser desenhados pelo painel.
Entrada: ia/giro/volta.mp4  →  Saída: ia/giro/hb20_giro_alfa.webp (folha 8 colunas, fundo transparente)
"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from rembg import new_session, remove
from scipy import ndimage

AQUI = Path(__file__).resolve().parent
GIRO = AQUI / "ia" / "giro"
N = 72
W, H, COLS = 640, 400, 8       # quadro final
ALTURA_CARRO = 250            # todo carro fica com essa altura (sem o reflexo)
CHAO = 352                    # linha onde as rodas tocam o chão

volta = GIRO / "volta.mp4"
total = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(volta)],
                           capture_output=True, text=True).stdout.strip())
sessao = new_session("isnet-general-use")

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    passo = total / N
    selecao = "+".join(f"eq(n\\,{int(i * passo)})" for i in range(N))
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(volta), "-vf", f"select='{selecao}'",
                    "-vsync", "0", str(tmp / "%03d.png")], check=True)
    quadros = sorted(tmp.glob("*.png"))[:N]

    folha = Image.new("RGBA", (W * COLS, H * ((len(quadros) + COLS - 1) // COLS)), (0, 0, 0, 0))
    for k, q in enumerate(quadros):
        img = Image.open(q).convert("RGB")
        rgba = np.array(remove(img, session=sessao))
        alfa = rgba[:, :, 3]
        rot, n = ndimage.label(alfa > 128)
        if n == 0:
            print("sem carro no quadro", k); continue
        maior = 1 + int(np.argmax(ndimage.sum(np.ones_like(rot), rot, range(1, n + 1))))
        miolo = ndimage.binary_fill_holes(rot == maior)
        borda = ndimage.binary_dilation(miolo, iterations=2)
        rgba[:, :, 3] = np.where(miolo, np.maximum(alfa, 235), np.where(borda, alfa, 0))

        # o reflexo no piso preto às vezes vem junto: corta tudo abaixo da base das rodas
        linhas = np.where(miolo.any(axis=1))[0]
        larg_linha = miolo.sum(axis=1)
        topo = linhas[0]
        # base = última linha "larga" (rodas); abaixo disso a largura despenca (reflexo fino) ou some
        base = linhas[-1]
        pico = larg_linha.max()
        for y in range(linhas[-1], topo, -1):
            if larg_linha[y] > 0.35 * pico:
                base = y
                break
        rgba[base + 1:, :, 3] = 0
        xs = np.where(miolo[: base + 1].any(axis=0))[0]
        carro = Image.fromarray(rgba).crop((xs[0], topo, xs[-1] + 1, base + 1))

        esc = ALTURA_CARRO / carro.height
        carro = carro.resize((max(1, round(carro.width * esc)), ALTURA_CARRO), Image.LANCZOS)
        x = (W - carro.width) // 2
        folha.paste(carro, ((k % COLS) * W + x, (k // COLS) * H + CHAO - ALTURA_CARRO), carro)
        print(k, carro.size, flush=True)

    destino = GIRO / "hb20_giro_alfa.webp"
    folha.save(destino, quality=82, method=6)
    print("ok", folha.size, destino.stat().st_size // 1024, "KB")
