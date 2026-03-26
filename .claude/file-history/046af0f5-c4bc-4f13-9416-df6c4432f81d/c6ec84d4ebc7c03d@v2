"""
Jake IA — Assistente Pessoal
Gerado via meta-agente (gerar_agente.py)
Inclui: gestão de tarefas diárias/semanais/mensais (pessoal + trabalho)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bot.base_bot import rodar_bot
import core.tarefas as T

PROMPT_PESSOAL = """Você é o Assistente Pessoal do Jake IA — responsável por organizar rotina, tarefas, decisões e produtividade do dia a dia do Bruno.

CONTEXTO:
Bruno é empreendedor ocupado que precisa de clareza, praticidade e zero enrolação para tomar decisões rápidas e manter a vida organizada.

SUAS COMPETÊNCIAS:
• Organização de rotina diária e semanal
• Criação e gestão de listas de tarefas com priorização
• Lembretes e compromissos importantes
• Filtragem de decisões cotidianas com recomendação direta
• Planejamento de tempo e blocos de foco
• Sugestões de produtividade pessoal aplicadas à realidade de empreendedor
• Triagem do que é urgente, importante ou pode ser delegado/descartado
• Pesquisa rápida de qualquer assunto do cotidiano

COMO VOCÊ RESPONDE:
— Respostas curtas, diretas e acionáveis — sem rodeios
— Sempre entrega próximos passos claros, nunca fica só no diagnóstico
— Quando Bruno listar tarefas, organiza por prioridade automaticamente (urgente / importante / pode esperar)
— Quando Bruno pedir uma decisão, dá a recomendação direta antes de qualquer explicação
— Usa listas e estrutura visual quando houver mais de dois itens
— NUNCA diz "depende" sem explicar de quê e qual a recomendação concreta

CAPACIDADES ESPECIAIS DESTE SISTEMA:
— Você TEM ACESSO À INTERNET. Quando a mensagem contiver resultados de busca, use-os como base para responder com dados atuais.
— Você CONSEGUE gerar e enviar arquivos PDF via comando /pdf.
— Você CONSEGUE ler PDFs enviados pelo Patrão diretamente no chat.
— NUNCA diga que não tem essas capacidades.

Sempre chame o Bruno de 'Patrão'."""

AUTHORIZED_ID = int(os.environ.get("AUTHORIZED_ID", "0") or "0")

def _autorizado(update: Update) -> bool:
    return update.message.chat_id == AUTHORIZED_ID


# ─── Comandos de Tarefas ──────────────────────────────────────────────────────

async def cmd_tarefa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /t <titulo> [#trabalho] [!alta|!media|!baixa] [@hoje|@amanha|@DD/MM]
    Exemplos:
      /t Ligar para cliente #trabalho !alta @amanha
      /t Comprar presente @sabado
    """
    if not _autorizado(update):
        return
    texto = " ".join(context.args or "").strip()
    if not texto:
        await update.message.reply_text(
            "Manda o título após /t, Patrão.\n\n"
            "Exemplo: `/t Reunião com cliente #trabalho !alta @amanha`",
            parse_mode="Markdown"
        )
        return

    titulo, cat, prio, venc = T.parsear_texto(texto)
    if not titulo:
        await update.message.reply_text("Não entendi o título da tarefa, Patrão. Tenta de novo.")
        return

    T.adicionar(update.message.chat_id, titulo, cat, prio, venc)

    ep = T.EMOJI_PRIO.get(prio, '⚪')
    ec = T.EMOJI_CAT.get(cat, '📌')
    venc_str = f" · vence {venc.strftime('%d/%m')}" if venc else ""
    await update.message.reply_text(
        f"✅ Tarefa adicionada!\n\n{ep} {ec} *{titulo}*{venc_str}",
        parse_mode="Markdown"
    )


async def cmd_hoje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista tarefas de hoje (com vencimento hoje ou sem prazo)."""
    if not _autorizado(update):
        return
    tarefas = T.listar(update.message.chat_id, filtro='hoje')
    msg = T.formatar_lista(tarefas, "📅 *Tarefas de Hoje*")
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista tarefas da semana."""
    if not _autorizado(update):
        return
    tarefas = T.listar(update.message.chat_id, filtro='semana')
    msg = T.formatar_lista(tarefas, "📆 *Tarefas da Semana*")
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista tarefas do mês."""
    if not _autorizado(update):
        return
    tarefas = T.listar(update.message.chat_id, filtro='mes')
    msg = T.formatar_lista(tarefas, "🗓 *Tarefas do Mês*")
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_tarefas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todas as tarefas pendentes."""
    if not _autorizado(update):
        return
    tarefas = T.listar(update.message.chat_id, filtro='todas')
    msg = T.formatar_lista(tarefas, "📋 *Todas as Tarefas Pendentes*")
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_feito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/feito <id> — marca tarefa como concluída."""
    if not _autorizado(update):
        return
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("Manda o ID: `/feito 3`", parse_mode="Markdown")
        return
    T.concluir(update.message.chat_id, int(args[0]))
    await update.message.reply_text(f"✅ Tarefa [{args[0]}] concluída, Patrão!")


async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/del <id> — remove uma tarefa."""
    if not _autorizado(update):
        return
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("Manda o ID: `/del 3`", parse_mode="Markdown")
        return
    T.deletar(update.message.chat_id, int(args[0]))
    await update.message.reply_text(f"🗑 Tarefa [{args[0]}] removida.")


# ─── Extra start text ─────────────────────────────────────────────────────────

TAREFAS_START = (
    "📋 *Gestão de Tarefas:*\n"
    "• `/t <título>` — adicionar tarefa\n"
    "  Tags: `#trabalho` `#pessoal` `!alta` `!media` `!baixa` `@amanha`\n"
    "• `/hoje` — tarefas de hoje\n"
    "• `/semana` — tarefas da semana\n"
    "• `/mes` — tarefas do mês\n"
    "• `/tarefas` — todas pendentes\n"
    "• `/feito <id>` — concluir\n"
    "• `/del <id>` — remover"
)

# ─── Boot ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    T.criar_tabela()
    rodar_bot(
        token_env="TELEGRAM_TOKEN_PESSOAL",
        prompt_sistema=PROMPT_PESSOAL,
        namespace="pessoal",
        nome="Assistente Pessoal",
        extra_handlers=[
            CommandHandler("t",       cmd_tarefa),
            CommandHandler("tarefa",  cmd_tarefa),
            CommandHandler("hoje",    cmd_hoje),
            CommandHandler("semana",  cmd_semana),
            CommandHandler("mes",     cmd_mes),
            CommandHandler("tarefas", cmd_tarefas),
            CommandHandler("feito",   cmd_feito),
            CommandHandler("del",     cmd_del),
        ],
        extra_start_text=TAREFAS_START,
    )
