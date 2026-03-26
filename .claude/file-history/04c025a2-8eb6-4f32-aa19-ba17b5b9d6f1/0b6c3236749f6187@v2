#!/usr/bin/env python3
"""
Inpainting via Replicate: substitui área amarela por parede no estilo da casa.
"""

import os
import io
import base64
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation
import replicate
import requests

from dotenv import load_dotenv
load_dotenv("/root/.env")

INPUT_PATH = "/root/Design sem nome (2).png"
OUTPUT_PATH = "/root/casa_com_parede.png"

# --- 1. Carrega imagem ---
img = Image.open(INPUT_PATH).convert("RGBA")
w, h = img.size
print(f"Imagem: {w}x{h}")

arr = np.array(img)
R, G, B = arr[:,:,0], arr[:,:,1], arr[:,:,2]

# Detecta amarelo
yellow_mask = (R > 180) & (G > 160) & (B < 100)
print(f"Pixels amarelos: {yellow_mask.sum()}")

# Dilata máscara
yellow_mask_dilated = binary_dilation(yellow_mask, iterations=10)

# --- 2. Prepara imagem sem o amarelo (RGB, sem transparência) ---
img_rgb = Image.open(INPUT_PATH).convert("RGB")

# Preenche área amarela com cor da parede da casa (beige ~#c8bfb0)
img_arr_rgb = np.array(img_rgb)
img_arr_rgb[yellow_mask_dilated] = [200, 191, 176]  # bege da casa
img_clean = Image.fromarray(img_arr_rgb)

# --- 3. Cria máscara: branco = inpaint, preto = manter ---
mask_arr = np.zeros((h, w), dtype=np.uint8)
mask_arr[yellow_mask_dilated] = 255
mask_img = Image.fromarray(mask_arr, "L").convert("RGB")

# Redimensiona para 768x768 (melhor resultado com SD inpainting)
size = 768
img_clean_r = img_clean.resize((size, size), Image.LANCZOS)
mask_img_r = mask_img.resize((size, size), Image.NEAREST)

img_clean_r.save("/tmp/rep_image.png")
mask_img_r.save("/tmp/rep_mask.png")
mask_img_r.save("/root/mask_debug.png")
print("Arquivos temporários salvos.")

# --- 4. Converte para data URI ---
def to_data_uri(path):
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{data}"

# --- 5. Chama Replicate SD Inpainting ---
print("Chamando Replicate inpainting...")

output = replicate.run(
    "stability-ai/stable-diffusion-inpainting:95b7223104132402a9ae91cc677285bc5eb997834bd2349fa486f53910fd68b3",
    input={
        "image": to_data_uri("/tmp/rep_image.png"),
        "mask": to_data_uri("/tmp/rep_mask.png"),
        "prompt": (
            "smooth beige stucco wall, modern Brazilian house exterior, "
            "flat solid wall matching the building facade, same color texture as surrounding walls, "
            "architectural photography, no windows no doors, clean wall"
        ),
        "negative_prompt": "window, door, people, text, logo, different color, dirt, graffiti",
        "num_inference_steps": 50,
        "guidance_scale": 7.5,
        "num_outputs": 1,
    }
)

print(f"Output: {output}")

# --- 6. Baixa e salva ---
url = output[0] if isinstance(output, list) else str(output)
print(f"Baixando: {url}")
resp = requests.get(url, timeout=60)
result = Image.open(io.BytesIO(resp.content)).convert("RGB")

# Redimensiona de volta ao original
result = result.resize((w, h), Image.LANCZOS)
result.save(OUTPUT_PATH)
print(f"\nResultado salvo em: {OUTPUT_PATH}")
