#!/usr/bin/env python3
"""
Lista contas de anúncios da Meta (ad accounts) para preencher a planilha.
Usa o Token de Usuário do Sistema da Meta.
"""
import requests

GRAPH_URL = "https://graph.facebook.com/v20.0"


def main():
    print("Cole seu Token da Meta (Token de Usuário do Sistema) e pressione Enter:")
    token = input().strip()
    if not token:
        print("Token vazio. Saindo.")
        return

    url = f"{GRAPH_URL}/me/adaccounts"
    params = {"access_token": token, "fields": "name,id"}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição: {e}")
        if hasattr(e, "response") and e.response is not None and hasattr(e.response, "text"):
            print("Resposta:", e.response.text[:500])
        return
    except ValueError as e:
        print(f"Resposta inválida da API: {e}")
        return

    contas = data.get("data") or []
    if not contas:
        print("Nenhuma conta de anúncios encontrada (ou token sem permissão ads_management).")
        return

    print()
    print("Contas de anúncios (NOME | ID):")
    print("-" * 60)
    for c in contas:
        nome = (c.get("name") or "").strip() or "—"
        id_conta = (c.get("id") or "").strip() or "—"
        print(f"{nome} | {id_conta}")
    print("-" * 60)
    print(f"Total: {len(contas)} conta(s)")


if __name__ == "__main__":
    main()
