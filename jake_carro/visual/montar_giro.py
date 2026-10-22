"""
Emenda os 8 trechos (ia/giro/trecho_1..8.mp4) numa volta completa e gera:
- ia/giro/volta.mp4        → a volta inteira (pra ver)
- ia/giro/hb20_giro.webp   → folha com N quadros (o cockpit "rola" por ela com o dedo)
Uso: python montar_giro.py [N=72]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
GIRO = AQUI / "ia" / "giro"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 72
W, H, COLS = 640, 426, 8

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    # cada trecho termina no quadro em que o próximo começa: tira o último quadro pra não repetir
    lista = tmp / "lista.txt"
    partes = []
    # O ângulo a7 saiu espelhado da IA: o trecho 7 passa da frente e o 8 volta. Corta o 7 no quadro que
    # bate com a frente (75, achado comparando com o 1º quadro do trecho 1) e descarta o 8.
    cortes = {1: 120, 2: 120, 3: 120, 4: 120, 5: 120, 6: 120, 7: 75}
    for n, fim in cortes.items():
        parte = tmp / f"p{n}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(GIRO / f"trecho_{n}.mp4"),
                        "-vf", f"scale={W}:{H},fps=24,trim=end_frame={fim},setpts=PTS-STARTPTS", "-an",
                        "-c:v", "libx264", "-crf", "16", str(parte)], check=True)
        partes.append(parte)
    lista.write_text("".join(f"file '{p}'\n" for p in partes))
    volta = GIRO / "volta.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(volta)], check=True)

    total = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(volta)],
                               capture_output=True, text=True).stdout.strip())
    quadros = tmp / "q"
    quadros.mkdir()
    passo = total / N
    selecao = "+".join(f"eq(n\\,{int(i * passo)})" for i in range(N))
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(volta), "-vf", f"select='{selecao}'", "-vsync", "0",
                    str(quadros / "%03d.png")], check=True)
    arquivos = sorted(quadros.glob("*.png"))[:N]
    linhas = (len(arquivos) + COLS - 1) // COLS
    folha = Image.new("RGB", (W * COLS, H * linhas))
    for k, f in enumerate(arquivos):
        folha.paste(Image.open(f).convert("RGB"), ((k % COLS) * W, (k // COLS) * H))
    destino = GIRO / "hb20_giro.webp"
    folha.save(destino, quality=78, method=6)
    print(f"{total} quadros na volta → {len(arquivos)} na folha {folha.size}, "
          f"{destino.stat().st_size // 1024} KB")
