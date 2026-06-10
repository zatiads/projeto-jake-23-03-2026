"""
Utilitários compartilhados entre todos os blueprints do Jake OS.
Importar aqui em vez de duplicar em cada módulo.
"""
import os
from functools import wraps

import psycopg2
import psycopg2.extras
from flask import session, redirect, url_for, jsonify


# ── Banco de dados ────────────────────────────────────────────────────────────

def get_db():
    """Abre conexão com Neon usando DATABASE_URL do .env."""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido no .env")
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# ── Clientes AI ──────────────────────────────────────────────────────────────

def anthropic_client():
    """Retorna cliente Anthropic (claude-sonnet-4-5 / 4-6)."""
    import anthropic as _anthropic
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return _anthropic.Anthropic(api_key=key) if key else None


def openai_client():
    """Retorna cliente OpenAI."""
    from openai import OpenAI
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    return OpenAI(api_key=key) if key else None


def get_meta_token(agency="piloti"):
    """Retorna token Meta Ads para a agência especificada."""
    tokens = {
        "piloti": lambda: os.environ.get("META_TOKEN_PILOTI", "").strip(),
    }
    fn = tokens.get(agency)
    if not fn:
        return ""
    return fn() or ""
