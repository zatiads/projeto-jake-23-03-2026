"""
Módulo de gestão de tarefas — Jake IA Assistente Pessoal
Categorias: pessoal | trabalho
Prioridades: alta | media | baixa
Status: pendente | concluida
"""
import re, os, sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.db import executar

EMOJI_PRIO = {'alta': '🔴', 'media': '🟡', 'baixa': '🟢'}
EMOJI_CAT  = {'trabalho': '💼', 'pessoal': '🏠'}
DIAS_SEMANA = {
    'segunda': 0, 'terca': 1, 'terça': 1,
    'quarta': 2, 'quinta': 3, 'sexta': 4,
    'sabado': 5, 'sábado': 5, 'domingo': 6,
}


def criar_tabela():
    executar("""
        CREATE TABLE IF NOT EXISTS tarefas (
            id           SERIAL PRIMARY KEY,
            chat_id      BIGINT NOT NULL,
            titulo       TEXT NOT NULL,
            categoria    TEXT DEFAULT 'pessoal',
            prioridade   TEXT DEFAULT 'media',
            status       TEXT DEFAULT 'pendente',
            vencimento   DATE,
            criado_em    TIMESTAMP DEFAULT NOW(),
            concluido_em TIMESTAMP
        )
    """)


def _parse_vencimento(token: str):
    """Converte string de vencimento em date ou None."""
    t = token.lower().strip()
    hoje = date.today()
    if t == 'hoje':
        return hoje
    if t in ('amanha', 'amanhã'):
        return hoje + timedelta(days=1)
    for nome, wd in DIAS_SEMANA.items():
        if t == nome:
            diff = (wd - hoje.weekday()) % 7 or 7
            return hoje + timedelta(days=diff)
    try:
        partes = t.split('/')
        if len(partes) == 2:
            return date(hoje.year, int(partes[1]), int(partes[0]))
        if len(partes) == 3:
            return date(int(partes[2]), int(partes[1]), int(partes[0]))
    except Exception:
        pass
    return None


def parsear_texto(texto: str):
    """
    Extrai titulo, categoria, prioridade e vencimento de texto livre.
    Sintaxe: titulo da tarefa #trabalho !alta @amanha
    """
    cat  = 'pessoal'
    prio = 'media'
    venc = None

    m = re.search(r'#(trabalho|pessoal)', texto, re.I)
    if m:
        cat = m.group(1).lower()
        texto = texto[:m.start()] + texto[m.end():]

    m = re.search(r'!(alta|media|média|baixa)', texto, re.I)
    if m:
        prio = m.group(1).lower().replace('média', 'media')
        texto = texto[:m.start()] + texto[m.end():]

    m = re.search(r'@(\S+)', texto)
    if m:
        venc = _parse_vencimento(m.group(1))
        texto = texto[:m.start()] + texto[m.end():]

    titulo = ' '.join(texto.split()).strip()
    return titulo, cat, prio, venc


def adicionar(chat_id: int, titulo: str, categoria='pessoal', prioridade='media', vencimento=None):
    executar(
        "INSERT INTO tarefas (chat_id, titulo, categoria, prioridade, vencimento) VALUES (%s,%s,%s,%s,%s)",
        (chat_id, titulo, categoria, prioridade, vencimento)
    )


def listar(chat_id: int, filtro='todas'):
    hoje = date.today()
    sql = """
        SELECT id, titulo, categoria, prioridade, vencimento
        FROM tarefas
        WHERE chat_id=%s AND status='pendente'
    """
    params = [chat_id]

    if filtro == 'hoje':
        sql += " AND (vencimento = %s OR vencimento IS NULL)"
        params.append(hoje)
    elif filtro == 'semana':
        sql += " AND (vencimento <= %s OR vencimento IS NULL)"
        params.append(hoje + timedelta(days=7))
    elif filtro == 'mes':
        sql += " AND (vencimento <= %s OR vencimento IS NULL)"
        params.append(hoje + timedelta(days=30))

    sql += " ORDER BY CASE prioridade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, criado_em ASC"
    return executar(sql, params) or []


def concluir(chat_id: int, tarefa_id: int):
    executar(
        "UPDATE tarefas SET status='concluida', concluido_em=NOW() WHERE id=%s AND chat_id=%s AND status='pendente'",
        (tarefa_id, chat_id)
    )


def deletar(chat_id: int, tarefa_id: int):
    executar("DELETE FROM tarefas WHERE id=%s AND chat_id=%s", (tarefa_id, chat_id))


def formatar_lista(tarefas: list, titulo: str) -> str:
    if not tarefas:
        return f"{titulo}\n\nNada pendente, Patrão. 👌"
    linhas = [titulo, ""]
    for row in tarefas:
        tid, ttitulo, cat, prio, venc = row
        ep = EMOJI_PRIO.get(prio, '⚪')
        ec = EMOJI_CAT.get(cat, '📌')
        venc_str = f"  · {venc.strftime('%d/%m')}" if venc else ""
        linhas.append(f"{ep} {ec} `[{tid}]` {ttitulo}{venc_str}")
    linhas.append("")
    linhas.append("✅ /feito <id>   🗑 /del <id>")
    return "\n".join(linhas)
