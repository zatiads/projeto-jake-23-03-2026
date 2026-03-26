#!/usr/bin/env python3
"""
Inpainting: substitui a área amarela por uma parede no estilo da casa.
"""

import os
import sys
import io
import numpy as np
from PIL import Image
import openai

# Carrega .env
from dotenv import load_dotenv
load_dotenv("/root/.env")

INPUT_PATH = "/root/Design sem nome (2).png"
OUTPUT_PATH = "/root/casa_com_parede.png"

# --- 1. Carrega imagem ---
img = Image.open(INPUT_PATH).convert("RGBA")
w, h = img.size
print(f"Imagem: {w}x{h}")

# --- 2. Detecta pixels amarelos e cria máscara ---
arr = np.array(img)
R, G, B = arr[:,:,0], arr[:,:,1], arr[:,:,2]

# Amarelo: R alto, G alto, B baixo
yellow_mask = (R > 180) & (G > 160) & (B < 100)
print(f"Pixels amarelos encontrados: {yellow_mask.sum()}")

# Dilata um pouco a máscara para cobrir bordas suavizadas
from scipy.ndimage import binary_dilation
yellow_mask_dilated = binary_dilation(yellow_mask, iterations=8)

# Cria máscara RGBA: branco=área a preencher, preto=manter
mask_arr = np.zeros((h, w, 4), dtype=np.uint8)
mask_arr[yellow_mask_dilated] = [255, 255, 255, 255]  # branco = inpaint aqui
mask_arr[~yellow_mask_dilated] = [0, 0, 0, 255]        # preto = manter

# Remove o amarelo da imagem original (deixa transparente) para o inpainting
img_clean = arr.copy()
img_clean[yellow_mask_dilated, 3] = 0  # transparente na área da máscara

# --- 3. Redimensiona para 1024x1024 (requisito DALL-E 2) ---
size = 1024

img_pil = Image.fromarray(img_clean, "RGBA").resize((size, size), Image.LANCZOS)
mask_pil = Image.fromarray(mask_arr, "RGBA").resize((size, size), Image.NEAREST)

# Salva temporários como PNG em disco (OpenAI precisa de arquivo real)
img_pil.save("/tmp/inpaint_image.png", format="PNG")
mask_pil.save("/tmp/inpaint_mask.png", format="PNG")

# Debug: salva máscara para conferir
mask_pil.save("/root/mask_debug.png")
print("Máscara salva em /root/mask_debug.png")

# --- 4. Chama DALL-E 2 inpainting ---
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("Chamando DALL-E 2 inpainting...")
response = client.images.edit(
    model="dall-e-2",
    image=open("/tmp/inpaint_image.png", "rb"),
    mask=open("/tmp/inpaint_mask.png", "rb"),
    prompt=(
        "smooth beige stucco wall matching the house exterior, "
        "modern Brazilian house facade, flat architectural wall, "
        "same color and texture as the rest of the building, "
        "no windows no doors, clean solid wall"
    ),
    n=1,
    size="1024x1024",
    response_format="b64_json"
)

# --- 5. Salva resultado ---
import base64
img_data = base64.b64decode(response.data[0].b64_json)
result_img = Image.open(io.BytesIO(img_data))

# Redimensiona de volta ao tamanho original
result_img = result_img.resize((w, h), Image.LANCZOS)
result_img.save(OUTPUT_PATH)
print(f"Resultado salvo em: {OUTPUT_PATH}")
