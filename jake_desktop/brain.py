"""
brain.py — Salva automaticamente outputs do Jake OS no vault Obsidian.
Uso: import brain; brain.salvar(modulo, titulo, inputs, output, model)
"""
import os
import re
import logging
import unicodedata
from datetime import datetime

VAULT = "/root/jake-brain/Jake OS/Outputs"

TEMPLATE = """\
---
modulo: {modulo}
modelo: {model}
gerado_em: {gerado_em}
---

# {titulo}

## Inputs
{inputs_md}

## Output
{output}

## Modelo
{model}

## Observações
<!-- espaço para anotar no Obsidian depois -->
"""


def _slug(texto: str) -> str:
    """'Copy — Instagram AIDA' → 'copy-instagram-aida' (max 60 chars)"""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    texto = re.sub(r"[\s_-]+", "-", texto)
    return texto[:60].strip("-")


def _inputs_md(inputs: dict) -> str:
    """Converte dict de inputs em lista markdown. Ignora vazios, trunca longos."""
    if not inputs:
        return "- (sem inputs registrados)"
    linhas = []
    for k, v in inputs.items():
        if v is None or v == "":
            continue
        v_str = str(v)
        if len(v_str) > 300:
            v_str = v_str[:300] + "..."
        linhas.append(f"- **{k}:** {v_str}")
    return "\n".join(linhas) if linhas else "- (sem inputs registrados)"


def salvar(modulo: str, titulo: str, inputs: dict, output: str, model: str) -> None:
    """
    Salva um output gerado pelo Jake OS como nota .md no vault Obsidian.
    Silencioso em caso de erro — nunca propaga exceção.
    """
    try:
        if not titulo:
            logging.warning("brain.salvar: titulo vazio, ignorando.")
            return
        if not os.path.isdir("/root/jake-brain"):
            logging.warning("brain.salvar: vault /root/jake-brain não encontrado.")
            return

        agora = datetime.now()
        ts = agora.strftime("%Y-%m-%d-%H-%M")
        gerado_em = agora.strftime("%Y-%m-%d %H:%M")

        destino_dir = os.path.join(VAULT, modulo)
        os.makedirs(destino_dir, exist_ok=True)

        slug = _slug(titulo)
        nome_base = f"{ts}-{slug}"
        destino = os.path.join(destino_dir, f"{nome_base}.md")

        # Colisão: append -2, -3, etc.
        contador = 2
        while os.path.exists(destino):
            destino = os.path.join(destino_dir, f"{nome_base}-{contador}.md")
            contador += 1

        conteudo = TEMPLATE.format(
            modulo=modulo,
            model=model,
            gerado_em=gerado_em,
            titulo=titulo,
            inputs_md=_inputs_md(inputs or {}),
            output=output or "(sem output)",
        )

        with open(destino, "w", encoding="utf-8") as f:
            f.write(conteudo)

    except Exception as e:
        logging.warning(f"brain.salvar falhou: {e}")
