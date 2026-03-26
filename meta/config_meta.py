"""
Configuração da Meta (Facebook) Marketing API.
Carrega de .env (python-dotenv) ou variáveis de ambiente.
"""
import os

try:
    from dotenv import load_dotenv
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

META_APP_ID = os.environ.get("META_APP_ID", "")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID", "act_360347436292903")

# Mapeamento cliente -> ID da conta de anúncios (Carazinho = OdontoCompany)
CLIENTE_CONTAS = {
    "carazinho": os.environ.get("META_AD_ACCOUNT_CARAZINHO", META_AD_ACCOUNT_ID),
}


def meta_configured():
    if not META_ACCESS_TOKEN or not str(META_ACCESS_TOKEN).strip():
        return False
    if META_AD_ACCOUNT_ID and str(META_AD_ACCOUNT_ID).strip().startswith("act_"):
        return True
    for v in CLIENTE_CONTAS.values():
        if v and str(v).strip().startswith("act_"):
            return True
    return False


def get_conta_for_cliente(nome_cliente):
    nome = (nome_cliente or "").strip().lower()
    if nome and nome in CLIENTE_CONTAS and CLIENTE_CONTAS[nome]:
        return str(CLIENTE_CONTAS[nome]).strip()
    if META_AD_ACCOUNT_ID and str(META_AD_ACCOUNT_ID).strip().startswith("act_"):
        return str(META_AD_ACCOUNT_ID).strip()
    return None
