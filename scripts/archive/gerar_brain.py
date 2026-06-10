#!/usr/bin/env python3
"""
gerar_brain.py — Gera estrutura de notas no vault jake-brain para cada componente do Jake.
Uso: cd /root && python3 scripts/gerar_brain.py
Regra: se o arquivo já existe, pula (não sobrescreve nunca).
"""
import os
from datetime import date

VAULT = "/root/jake-brain"
TODAY = date.today().isoformat()

COMPONENTES = [
    {
        "arquivo": "Jake OS/Bots/jake-principal.md",
        "nome": "Bot Principal",
        "tipo": "bot",
        "caminho": "/root/jake_telegram.py + /root/bot/base_bot.py",
        "arquivos": ["/root/jake_telegram.py", "/root/bot/base_bot.py"],
        "tags": ["jake", "bot", "telegram"],
    },
    {
        "arquivo": "Jake OS/Bots/jake-pessoal.md",
        "nome": "Bot Pessoal",
        "tipo": "bot",
        "caminho": "/root/bot/jake_pessoal.py",
        "arquivos": ["/root/bot/jake_pessoal.py", "/root/bot/prompt_pessoal.txt"],
        "tags": ["jake", "bot", "telegram", "pessoal"],
    },
    {
        "arquivo": "Jake OS/Bots/jake-viagem.md",
        "nome": "Bot Viagem",
        "tipo": "bot",
        "caminho": "/root/bot/jake_viagem.py",
        "arquivos": ["/root/bot/jake_viagem.py", "/root/bot/prompt_viagem.txt"],
        "tags": ["jake", "bot", "telegram", "viagem"],
    },
    {
        "arquivo": "Jake OS/Bots/jake-whatsapp.md",
        "nome": "Jake WhatsApp",
        "tipo": "bot",
        "caminho": "/root/bot/jake_whatsapp.py + /root/bot/gestor_whatsapp.py",
        "arquivos": ["/root/bot/jake_whatsapp.py", "/root/bot/gestor_whatsapp.py"],
        "tags": ["jake", "bot", "whatsapp", "meta-ads", "anuncios"],
    },
    {
        "arquivo": "Jake OS/Bots/gerar-agente.md",
        "nome": "Gerador de Agentes",
        "tipo": "bot",
        "caminho": "/root/bot/gerar_agente.py",
        "arquivos": ["/root/bot/gerar_agente.py"],
        "tags": ["jake", "bot", "meta-agente"],
    },
    {
        "arquivo": "Jake OS/Core/banco-de-dados.md",
        "nome": "Banco de Dados",
        "tipo": "core",
        "caminho": "/root/core/db.py",
        "arquivos": ["/root/core/db.py"],
        "tags": ["jake", "core", "database", "neon", "postgresql"],
    },
    {
        "arquivo": "Jake OS/Core/sync-planilha.md",
        "nome": "Sync Planilha",
        "tipo": "core",
        "caminho": "/root/core/sync_planilha.py",
        "arquivos": ["/root/core/sync_planilha.py"],
        "tags": ["jake", "core", "google-sheets"],
    },
    {
        "arquivo": "Jake OS/Core/tarefas.md",
        "nome": "Tarefas",
        "tipo": "core",
        "caminho": "/root/core/tarefas.py",
        "arquivos": ["/root/core/tarefas.py"],
        "tags": ["jake", "core"],
    },
    {
        "arquivo": "Jake OS/Core/utilitarios.md",
        "nome": "Utilitários",
        "tipo": "script",
        "caminho": "/root/",
        "arquivos": ["/root/leitor_planilha.py", "/root/listar_ids.py"],
        "tags": ["jake", "utilitarios"],
    },
    {
        "arquivo": "Jake OS/Meta Ads/overview.md",
        "nome": "Meta Ads",
        "tipo": "integração",
        "caminho": "/root/meta/",
        "arquivos": ["/root/meta/meta_api.py", "/root/meta/checar_saldo_meta.py", "/root/meta/config_meta.py"],
        "tags": ["jake", "meta-ads", "facebook"],
    },
    {
        "arquivo": "Jake OS/App-Rotas.md",
        "nome": "Jake OS App (Rotas)",
        "tipo": "flask",
        "caminho": "/root/jake_desktop/app.py",
        "arquivos": ["/root/jake_desktop/app.py"],
        "tags": ["jake", "flask", "backend"],
    },
    {
        "arquivo": "Jake OS/Frontend.md",
        "nome": "Jake OS Frontend",
        "tipo": "frontend",
        "caminho": "/root/jake_desktop/static/js/",
        "arquivos": [],
        "tags": ["jake", "frontend", "javascript"],
    },
    {
        "arquivo": "Jake OS/Infraestrutura/vps-scripts.md",
        "nome": "Scripts e Infraestrutura",
        "tipo": "script",
        "caminho": "/root/scripts/",
        "arquivos": [],
        "tags": ["jake", "infraestrutura", "scripts"],
    },
    {
        "arquivo": "Jake OS/Infraestrutura/migrations.md",
        "nome": "Migrations",
        "tipo": "script",
        "caminho": "/root/scripts/",
        "arquivos": ["/root/scripts/migrar_anuncios.py", "/root/scripts/migrar_criativos.py"],
        "tags": ["jake", "database", "migration"],
    },
    {
        "arquivo": "Jake OS/Infraestrutura/docs-existentes.md",
        "nome": "Documentação Existente",
        "tipo": "docs",
        "caminho": "/root/docs/",
        "arquivos": [],
        "tags": ["jake", "docs"],
    },
    {
        "arquivo": "Projetos/carousel-engine.md",
        "nome": "Carousel Engine",
        "tipo": "projeto",
        "caminho": "/root/carousel-engine/",
        "arquivos": [],
        "tags": ["jake", "projeto", "nextjs"],
    },
    {
        "arquivo": "Clientes/clinica-cliente.md",
        "nome": "Clínica Cliente",
        "tipo": "site",
        "caminho": "/root/clinica-cliente/",
        "arquivos": ["/root/clinica-cliente/index.html", "/root/clinica-cliente/sitealine.html"],
        "tags": ["jake", "cliente", "site"],
    },
    {
        "arquivo": "Clientes/camila-piercer.md",
        "nome": "Camila Piercer",
        "tipo": "site",
        "caminho": "/root/camila_piercerr_2.html",
        "arquivos": ["/root/camila_piercerr_2.html"],
        "tags": ["jake", "cliente", "site"],
    },
]

TEMPLATE = """---
tipo: {tipo}
caminho: {caminho}
tags: {tags}
gerado_em: {hoje}
---

# {nome}

## Arquivos
{arquivos_lista}

## O que faz
[TODO]

## Como funciona
[TODO]

## Variáveis de Ambiente
[TODO]

## Dependências
[TODO]

## Decisões Tomadas
[TODO]

## Próximos Passos
[TODO]

## Links Relacionados
[TODO]
"""

IGNORAR = {"venv", ".venv", "node_modules", "__pycache__", ".git", ".local", ".npm", ".cache", "jake-brain"}


def listar_arquivos_dir(caminho):
    resultado = []
    if os.path.isdir(caminho):
        for f in sorted(os.listdir(caminho)):
            if f in IGNORAR or f.startswith("."):
                continue
            fp = os.path.join(caminho, f)
            if os.path.isfile(fp):
                resultado.append(fp)
    return resultado


def gerar_nota(comp):
    arquivos = comp["arquivos"]
    if not arquivos:
        arquivos = listar_arquivos_dir(comp["caminho"])
    arquivos_lista = "\n".join(f"- `{a}`" for a in arquivos) if arquivos else "- (nenhum arquivo detectado)"
    tags_str = "[" + ", ".join(comp["tags"]) + "]"
    return TEMPLATE.format(
        tipo=comp["tipo"],
        caminho=comp["caminho"],
        tags=tags_str,
        hoje=TODAY,
        nome=comp["nome"],
        arquivos_lista=arquivos_lista,
    )


def main():
    criados = 0
    pulados = 0
    for comp in COMPONENTES:
        destino = os.path.join(VAULT, comp["arquivo"])
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        if os.path.exists(destino):
            print(f"[PULADO]  {comp['arquivo']}")
            pulados += 1
            continue
        conteudo = gerar_nota(comp)
        with open(destino, "w", encoding="utf-8") as f:
            f.write(conteudo)
        print(f"[CRIADO]  {comp['arquivo']}")
        criados += 1
    print(f"\nConcluído: {criados} criados, {pulados} pulados.")


if __name__ == "__main__":
    main()
