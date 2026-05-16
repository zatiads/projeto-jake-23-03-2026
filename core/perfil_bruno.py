"""
Perfil persistente do Bruno — carregado pelo Jake em toda interação.
Atualizado em: 2026-05-16
"""

PERFIL = {
    # ── Identidade ──────────────────────────────────────────────────────────
    "nome": "Bruno",
    "apelido_bot": "Patrao",
    "cidade": "Varginha, MG",

    # ── Metas 2026 ──────────────────────────────────────────────────────────
    "metas": [
        "Atingir R$1.000.000 de faturamento anual",
        "Comprar carro novo entre R$40k e R$60k",
        "Viagem ao Chile em agosto (já marcada)",
        "Pelo menos 1 viagem de avião maior no ano",
        "Várias viagens menores a lugares próximos de Varginha",
        "Conhecer Baependi (MG) e outros destinos próximos",
        "Comprar Meta Quest (Oculus) para gravar POV videos",
        "Comprar drone DJI Neo 2 para produção de conteúdo",
    ],

    # ── Agência e clientes ──────────────────────────────────────────────────
    "agencia": {
        "foco": "Manter base atual de clientes — não expandir tráfego",
        "prioridade_maxima": "Clientes da Dentto (ficaram sem atenção, precisam de resultado)",
        "outras_plataformas": ["Meta Ads", "Google Ads"],
        "google_ads": {
            "status": "pendente integração no Jake OS",
            "prioridade": "relatórios e otimização",
        },
    },

    # ── Rotina ──────────────────────────────────────────────────────────────
    "rotina": {
        "horario_inicio_atual": "07:30–08:00",
        "horario_meta": "07:00–07:30",
        "trabalha_sabado": True,
        "trabalha_domingo": False,
        "monitoramento": "diário (inclusive fins de semana)",
        "preferencia_relatorio": "detalhado mas essencial — só o que importa",
    },

    # ── Alertas ─────────────────────────────────────────────────────────────
    "alertas": {
        "saldo_minimo_meta": 300.0,
        "sem_conversao_dias": 1,
        "sem_conversao_ignorar_objetivos": ["ENGAGEMENT", "REACH", "BRAND_AWARENESS"],
        # Contas com objetivo de visita ao perfil/engagement não têm conversão de mensagem
        "bom_dia_todos_os_dias": True,
    },

    # ── Financeiro ──────────────────────────────────────────────────────────
    "financeiro": {
        "meta_anual": 1_000_000.0,
        "ano_base": 2026,
        "mes_inicio_contagem": 1,  # janeiro
        "inclui_renda_variavel": True,
    },

    # ── Criativos / testes ──────────────────────────────────────────────────
    "criativos": {
        "metodo_upload": "manual ou Drive",
        "sugerir_copy_queda_ctr": True,
        "ctr_queda_threshold_pct": 20,  # alerta se CTR caiu >20%
    },

    # ── Personalidade do Jake ────────────────────────────────────────────────
    "jake": {
        "tom": "descontraído, direto ao ponto",
        "usar_emojis": True,
        "lembrar_tarefas": True,
        "idioma": "português",
    },
}


def get_contexto_sistema() -> str:
    """
    Retorna string de contexto para injetar no system prompt do Jake.
    """
    return (
        "Voce e Jake, assistente pessoal do Bruno (Patrao), gestor de trafego de Varginha/MG.\n"
        "Perfil do Bruno:\n"
        "- Meta 2026: R$1M de faturamento, carro novo R$40-60k, viagem ao Chile em agosto\n"
        "- Prioridade maxima: melhorar resultados dos clientes da Dentto\n"
        "- NAO quer expandir base de clientes de trafego — foco em qualidade\n"
        "- Trabalha de seg a sab, comeca por volta das 7h30\n"
        "- Quer relatórios essenciais mas detalhados\n"
        "- Tom: descontraido, direto, pode usar emojis\n"
        "- Plataformas: Meta Ads (principal) + Google Ads (integracao pendente)\n"
        "- Quer ser lembrado de tarefas importantes\n"
    )
