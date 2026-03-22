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
VAULT_ROOT = "/root/jake-brain"

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


def contexto(cliente: str) -> str:
    """
    Retorna o conteúdo da nota de briefing do cliente no vault Obsidian.
    Faz fuzzy match bidirecional: slug_cliente in slug_arquivo OU slug_arquivo in slug_cliente.
    Arquivos em _Template/ são ignorados.
    Retorna '' se não encontrar match, vault ausente ou qualquer erro.
    Nunca propaga exceção.
    """
    try:
        if not cliente:
            return ""
        if not os.path.isdir(VAULT_ROOT):
            logging.warning(f"brain.contexto: vault {VAULT_ROOT} não encontrado.")
            return ""

        clientes_dir = os.path.join(VAULT_ROOT, "Clientes")
        if not os.path.isdir(clientes_dir):
            return ""

        slug_cliente = _slug(cliente)

        # Coletar e ordenar arquivos .md alfabeticamente, excluindo _Template/
        candidatos = []
        for raiz, dirs, arquivos in os.walk(clientes_dir):
            # Excluir diretórios _Template da busca
            dirs[:] = [d for d in dirs if d != "_Template"]
            for nome in arquivos:
                if nome.endswith(".md"):
                    candidatos.append(os.path.join(raiz, nome))
        candidatos.sort(key=lambda p: os.path.basename(p))

        for caminho in candidatos:
            nome_sem_ext = os.path.splitext(os.path.basename(caminho))[0]
            slug_arquivo = _slug(nome_sem_ext)
            if slug_cliente in slug_arquivo or slug_arquivo in slug_cliente:
                with open(caminho, encoding="utf-8") as f:
                    return f.read()

        return ""

    except Exception as e:
        logging.warning(f"brain.contexto falhou: {e}")
        return ""
