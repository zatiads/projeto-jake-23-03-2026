"""
Leitor da planilha Google Sheets 'controle_relatorios_semanais'.
Usa gspread e credenciais.json (Service Account).
"""
import os

import gspread


def _get_gc():
    """Cliente gspread autenticado com credenciais.json na raiz do projeto."""
    root = os.path.dirname(os.path.abspath(__file__))
    path_credenciais = os.path.join(root, "credenciais.json")
    return gspread.service_account(filename=path_credenciais)


def _abrir_planilha():
    """Abre a planilha e a primeira aba. Reutilizado por buscar_clientes e buscar_todos_registros."""
    gc = _get_gc()
    planilha = gc.open("controle_relatorios_semanais")
    return planilha.sheet1


def buscar_todos_registros():
    """
    Retorna todos os registros da planilha (sem filtrar por status).
    Útil para sincronizar planilha → banco de dados.
    """
    aba = _abrir_planilha()
    return aba.get_all_records()


def buscar_clientes():
    """
    Abre a planilha 'controle_relatorios_semanais' e retorna uma lista
    com os dados de todos os clientes cujo status seja 'ativo'.
    Cada item da lista é um dicionário (chaves = cabeçalhos da planilha).
    """
    registros = buscar_todos_registros()
    # Planilha usa coluna "status" (minúsculo); valor "ativo"
    return [
        r for r in registros
        if (r.get("status") or r.get("Status") or "").strip().lower() == "ativo"
    ]
