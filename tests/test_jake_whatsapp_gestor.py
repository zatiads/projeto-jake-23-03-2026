"""Testes para interpretar_comando e resolver_clientes em jake_whatsapp.py"""
import pytest
from unittest.mock import patch, MagicMock


# ── interpretar_comando ────────────────────────────────────────────────────────

def test_interpretar_subir_anuncio():
    from bot.jake_whatsapp import interpretar_comando
    mock_claude = MagicMock()
    mock_claude.return_value = '{"intencao":"subir_anuncio","drive_link":"https://drive.google.com/file/d/ABC/view","clientes":["cordeirópolis"],"orcamento":30,"campanha_tipo":"MESSAGES"}'

    with patch("bot.jake_whatsapp.chamar_claude", mock_claude):
        result = interpretar_comando("Sobe esse vídeo https://drive.google.com/file/d/ABC/view para cordeirópolis, R$30")

    assert result["intencao"] == "subir_anuncio"
    assert result["orcamento"] == 30
    assert "cordeirópolis" in result["clientes"]


def test_interpretar_pausar_campanha():
    from bot.jake_whatsapp import interpretar_comando
    mock_claude = MagicMock()
    mock_claude.return_value = '{"intencao":"pausar_campanha","clientes":["schroeder"],"orcamento":null,"campanha_tipo":null,"drive_link":null}'

    with patch("bot.jake_whatsapp.chamar_claude", mock_claude):
        result = interpretar_comando("Pausa as campanhas do Schroeder")

    assert result["intencao"] == "pausar_campanha"
    assert "schroeder" in result["clientes"]


def test_interpretar_json_invalido_retorna_desconhecida():
    from bot.jake_whatsapp import interpretar_comando
    mock_claude = MagicMock()
    mock_claude.return_value = "Não entendi o comando."

    with patch("bot.jake_whatsapp.chamar_claude", mock_claude):
        result = interpretar_comando("blablabla")

    assert result["intencao"] == "desconhecida"


# ── resolver_clientes ──────────────────────────────────────────────────────────

def test_resolver_match_exato():
    from bot.jake_whatsapp import resolver_clientes
    clientes_db = [
        {"id": 1, "nome": "Odontocompany Cordeiropolis"},
        {"id": 2, "nome": "ODC Tijucas"},
    ]
    with patch("bot.jake_whatsapp._buscar_clientes_db", return_value=clientes_db):
        resultado = resolver_clientes(["cordeiropolis"])
    assert len(resultado["confirmados"]) == 1
    assert resultado["confirmados"][0]["id"] == 1
    assert resultado["ambiguos"] == []


def test_resolver_sem_match():
    from bot.jake_whatsapp import resolver_clientes
    clientes_db = [{"id": 1, "nome": "Odontocompany Cordeiropolis"}]
    with patch("bot.jake_whatsapp._buscar_clientes_db", return_value=clientes_db):
        resultado = resolver_clientes(["xyz123"])
    assert resultado["confirmados"] == []
    assert len(resultado["nao_encontrados"]) == 1


def test_resolver_multiplos():
    from bot.jake_whatsapp import resolver_clientes
    clientes_db = [
        {"id": 1, "nome": "Odontocompany Cordeiropolis"},
        {"id": 2, "nome": "ODC Tijucas"},
        {"id": 3, "nome": "ODC Schroeder"},
    ]
    with patch("bot.jake_whatsapp._buscar_clientes_db", return_value=clientes_db):
        resultado = resolver_clientes(["cordeiropolis", "tijucas"])
    assert len(resultado["confirmados"]) == 2
