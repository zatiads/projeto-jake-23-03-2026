"""
Testes unitários para brain.py.
Uso: cd /root/jake_desktop && /root/venv/bin/python -m pytest tests/test_brain.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import brain


# --- _slug ---

def test_slug_basico():
    assert brain._slug("Copy Instagram AIDA") == "copy-instagram-aida"


def test_slug_acentos():
    resultado = brain._slug("Análise Março 2026")
    assert "analise" in resultado
    assert "marco" in resultado
    assert "2026" in resultado


def test_slug_max_60_chars():
    assert len(brain._slug("a" * 100)) <= 60


def test_slug_chars_especiais():
    resultado = brain._slug("Copy — Dashboard v2")
    assert "copy" in resultado
    assert "dashboard" in resultado
    assert len(resultado) <= 60


# --- _inputs_md ---

def test_inputs_md_basico():
    md = brain._inputs_md({"plataforma": "Instagram", "framework": "AIDA"})
    assert "**plataforma:** Instagram" in md
    assert "**framework:** AIDA" in md


def test_inputs_md_ignora_vazios():
    md = brain._inputs_md({"a": "valor", "b": "", "c": None, "d": "ok"})
    assert "**b:**" not in md
    assert "**c:**" not in md
    assert "valor" in md
    assert "ok" in md


def test_inputs_md_trunca_longos():
    md = brain._inputs_md({"prompt": "x" * 400})
    assert "..." in md
    for linha in md.splitlines():
        if "prompt" in linha:
            assert len(linha) < 400


def test_inputs_md_dict_vazio():
    md = brain._inputs_md({})
    assert "sem inputs" in md


# --- salvar ---

def test_salvar_cria_arquivo(tmp_path):
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar(
                "Copys",
                "Copy Instagram AIDA academia",
                {"plataforma": "Instagram", "framework": "AIDA"},
                "Conteúdo gerado aqui",
                "claude-sonnet-4-6",
            )

    arquivos = list((vault_outputs / "Copys").glob("*.md"))
    assert len(arquivos) == 1

    conteudo = arquivos[0].read_text(encoding="utf-8")
    assert "Copy Instagram AIDA academia" in conteudo
    assert "Conteúdo gerado aqui" in conteudo
    assert "claude-sonnet-4-6" in conteudo
    assert "Instagram" in conteudo
    assert "modulo: Copys" in conteudo
    assert "gerado_em:" in conteudo
    assert "## Observações" in conteudo


def test_salvar_titulo_vazio_nao_cria_arquivo(tmp_path):
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Copys", "", {"p": "v"}, "output", "model")
    assert not (vault_outputs / "Copys").exists()


def test_salvar_titulo_none_nao_cria_arquivo(tmp_path):
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Copys", None, {}, "output", "model")
    assert not (vault_outputs / "Copys").exists()


def test_salvar_vault_inexistente_nao_propaga():
    with patch("brain.os.path.isdir", return_value=False):
        brain.salvar("Copys", "titulo", {}, "output", "model")  # não deve lançar


def test_salvar_erro_interno_nao_propaga():
    with patch("brain.VAULT", "/dev/null/impossivel"):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Copys", "titulo", {}, "output", "model")  # não deve lançar


def test_salvar_colisao_gera_sufixo(tmp_path):
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    dt_fixo = datetime(2026, 3, 22, 15, 43, 0)

    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            with patch("brain.datetime") as mock_dt:
                mock_dt.now.return_value = dt_fixo
                brain.salvar("Copys", "Copy teste", {}, "output 1", "model")
                brain.salvar("Copys", "Copy teste", {}, "output 2", "model")

    arquivos = sorted((vault_outputs / "Copys").glob("*.md"))
    assert len(arquivos) == 2
    assert any("-2.md" in f.name for f in arquivos)


def test_salvar_frontmatter_completo(tmp_path):
    vault_outputs = tmp_path / "Jake OS" / "Outputs"
    with patch("brain.VAULT", str(vault_outputs)):
        with patch("brain.os.path.isdir", return_value=True):
            brain.salvar("Financeiro", "Análise março", {}, "texto da análise", "claude-sonnet-4-5")

    arquivo = list((vault_outputs / "Financeiro").glob("*.md"))[0]
    conteudo = arquivo.read_text(encoding="utf-8")
    assert conteudo.startswith("---\n")
    assert "modulo: Financeiro" in conteudo
    assert "modelo: claude-sonnet-4-5" in conteudo
    assert "## Inputs\n" in conteudo
    assert "## Output\n" in conteudo
    assert "## Observações" in conteudo
