"""
Gestor IA — Seed de conhecimento sênior.
Executar uma vez: PYTHONPATH=/root python -m meta.gestor.conhecimento.seed
Idempotente — não duplica se já existir.
"""
import os
import logging

try:
    from dotenv import load_dotenv
    load_dotenv("/root/.env")
except ImportError:
    pass

import psycopg2

_log = logging.getLogger(__name__)

BLOCOS = [
    {
        "titulo": "dental messages cpl benchmarks brasil",
        "nichos": ["dental"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- CPL saudavel: R$8-R$25. Acima de R$40 indica criativo saturado ou publico errado.
- CPL acima de R$50 por mais de 3 dias consecutivos: pausar o ad e testar novo criativo.
- Frequencia maxima antes de trocar criativo: 3.0. Acima disso, CTR cai e CPL sobe.
- Sazonalidade: janeiro e julho sao picos de busca por tratamento dental — thresholds podem subir 20%.
- Publico ideal: lookalike 1-3% de lista de pacientes ou engajamento 60 dias.
- Campanha de mensagem dental: objetivo MESSAGES no Meta, CTA "Agendar consulta pelo WhatsApp".
- Ads com imagem antes/depois performam 2-3x melhor que ads institucionais para dentistas.""",
    },
    {
        "titulo": "dental messages escalada orcamento",
        "nichos": ["dental"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- Escalar quando CPL < R$15 por 3+ dias consecutivos E frequencia < 2.0.
- Limite de escalada segura: +20% do orcamento do conjunto por vez (Meta reinicia aprendizado acima disso).
- Nunca escalar ad individualmente — sempre escalar no nivel do conjunto de anuncios (adset).
- Melhor janela para editar orcamento: entre 0h e 6h horario de Brasilia (menor competicao no leilao).
- Se CPL caiu mas frequencia esta acima de 2.5: escalar publico, nao orcamento.""",
    },
    {
        "titulo": "fitness messages cpl benchmarks brasil",
        "nichos": ["fitness"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- CPL saudavel academia padrao: R$15-R$50. Academias premium aceitam ate R$80.
- Personal trainer e funcional: CPL ate R$60 e aceitavel se ticket medio for alto.
- Sazonalidade forte: janeiro (resolucoes de ano novo) e setembro — thresholds sobem 30%.
- Junho/julho: queda natural de demanda — nao confundir com problema de criativo.
- Criativos de transformacao (antes/depois) performam 2-3x melhor que institucionais.
- Publico com interesse em "academia", "emagrecimento" e "saude" tende a ter CPL 20% menor.""",
    },
    {
        "titulo": "fitness messages fadiga criativa",
        "nichos": ["fitness"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- Frequencia > 2.5 em menos de 14 dias indica publico muito restrito — ampliar audiencia.
- Frequencia > 3.5: pausar o ad. CTR cai abruptamente apos esse ponto.
- Rotacao de criativos: novo ad a cada 3-4 semanas mesmo sem queda de performance (prevencao).
- Testar angulo diferente de copy: dor (nao consigo emagrecer), solucao (academia perto de voce), prova social (aluno transformado).""",
    },
    {
        "titulo": "varejo mensagem whatsapp benchmarks",
        "nichos": ["varejo"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- CPL para varejo via WhatsApp: R$20-R$60. Alta variacao por ticket medio do produto.
- Produto de alto ticket (sofa, movel): CPL ate R$100 e aceitavel se taxa de fechamento for >10%.
- Ads com preco visivel no criativo tendem a ter CTR mais alto mas CPL mais seletivo (lead mais qualificado).
- Urgencia funciona bem em varejo: "Apenas X unidades", "Preco valido ate domingo".
- Frequencia maxima: 2.5. Varejo tem publico geograficamente limitado — satura rapido.""",
    },
    {
        "titulo": "servicos b2b mensagem benchmarks",
        "nichos": ["servicos"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- CPL para servicos B2B via WhatsApp: R$30-R$100. Lead qualificado justifica custo maior.
- Contabilidade e advocacia: CPL ate R$80 e normal. Ciclo de decisao e longo.
- Copy focado em dor especifica do segmento performa melhor que copy generico.
- Campanha de remarketing para visitantes do site costuma ter CPL 40-60% menor.
- Frequencia maxima: 3.0. Publico B2B e menor — monitorar saturacao semanalmente.""",
    },
    {
        "titulo": "engajamento instagram benchmarks brasil",
        "nichos": ["geral"],
        "tipo_campanha": "ENGAGEMENT",
        "fonte": "seed",
        "regras": """- CPM saudavel: R$15-R$35. Acima de R$40 indica publico muito pequeno ou alta competicao.
- CTR abaixo de 0.8% em 7 dias = problema de criativo, nao de publico — trocar o ad.
- CTR acima de 2.5% = criativo excelente — aumentar orcamento desse conjunto.
- Frequencia > 3.0 em campanha de engajamento: ampliar publico ou pausar.
- Visitas ao perfil nao geram conversao direta — usar como topo de funil, nao como metrica primaria de ROI.""",
    },
    {
        "titulo": "engajamento instagram sazonalidade",
        "nichos": ["geral"],
        "tipo_campanha": "ENGAGEMENT",
        "fonte": "seed",
        "regras": """- Semana santa, carnaval e natal: CPM sobe 30-50% — pausar ou reduzir orcamento preventivamente.
- Black Friday: CPM pode dobrar. So manter ativo se o objetivo e venda direta.
- Verao (dez/jan): engajamento de saude e beleza cresce naturalmente — bom momento para escalar.
- Segunda e terca: melhores dias para lancamento de novos criativos (mais atencao do usuario).""",
    },
    {
        "titulo": "regras gerais de escalada meta ads",
        "nichos": ["geral"],
        "tipo_campanha": "geral",
        "fonte": "seed",
        "regras": """- Nunca aumentar mais de 20% do orcamento por dia — acima disso o Meta reinicia a fase de aprendizado.
- Melhor horario para editar orcamento: entre 0h e 6h (menor competicao no leilao).
- Escalar no adset, nao no ad. O adset controla orcamento; o ad e apenas o criativo.
- Antes de escalar: verificar se o ad tem pelo menos 7 dias de dados e 50+ conversoes no adset.
- CBO (Campaign Budget Optimization) distribui orcamento automaticamente entre adsets — usar quando ha 2+ adsets com bom historico.""",
    },
    {
        "titulo": "regras gerais de pausa e reativacao",
        "nichos": ["geral"],
        "tipo_campanha": "geral",
        "fonte": "seed",
        "regras": """- Nunca pausar um ad com menos de 7 dias de dados. Variacao diaria e normal.
- Nunca pausar com menos de R$50 investidos nos ultimos 30 dias — dados insuficientes.
- Antes de pausar por CPL alto: verificar se o ad tem pelo menos 2-3 conversoes no periodo.
- Ad com 1 conversao e CPL aparentemente alto pode ser distorcao — aguardar mais dados.
- Reativar ad pausado: apenas se CPL da conta voltou abaixo do limite historico E o ad nao estava pausado por frequencia alta.""",
    },
    {
        "titulo": "fadiga criativa regras gerais",
        "nichos": ["geral"],
        "tipo_campanha": "geral",
        "fonte": "seed",
        "regras": """- Frequencia > 3.5: sinal forte de fadiga — pausar o ad independente do CPL.
- Frequencia entre 2.5 e 3.5: alerta — preparar novo criativo, mas nao pausar ainda.
- Frequencia < 2.0 com bom CPL: ad saudavel, pode escalar.
- Rotacao preventiva: trocar criativo a cada 30 dias mesmo sem queda, para evitar saturacao gradual.
- Publico restrito (cidade pequena, nicho especializado): frequencia sobe mais rapido — monitorar semanalmente.""",
    },
    {
        "titulo": "analise temporal e sazonalidade meta ads",
        "nichos": ["geral"],
        "tipo_campanha": "geral",
        "fonte": "seed",
        "regras": """- Analise minima: 7 dias de dados para qualquer decisao de pausa.
- Analise ideal: comparar ultimos 7 dias com baseline de 30 dias.
- Variacao de ate 30% no CPL entre dias da semana e normal (segunda tende a ser mais caro).
- Fim de semana: CTR geralmente maior, mas lead tende a ser menos qualificado.
- Evitar mudancas em campanhas na sexta a tarde — Meta leva ate 24h para reestabilizar apos mudancas.""",
    },
    {
        "titulo": "saude e clinicas mensagem benchmarks",
        "nichos": ["saude"],
        "tipo_campanha": "MESSAGES",
        "fonte": "seed",
        "regras": """- Clinicas de saude (hiperbarica, estetica, nutricao): CPL via WhatsApp R$20-R$70.
- Tratamentos de alto ticket: CPL ate R$120 e aceitavel se conversao for boa.
- Copy com prova social (depoimento de paciente) performa 2x melhor que copy tecnico.
- Ads com video curto (15-30s) de depoimento real tendem a ter CPL 20-30% menor.
- Frequencia maxima: 3.0. Publico de saude e geograficamente restrito.""",
    },
    {
        "titulo": "purchase campaigns meta ads benchmarks",
        "nichos": ["geral"],
        "tipo_campanha": "PURCHASE",
        "fonte": "seed",
        "regras": """- ROAS saudavel depende da margem: para 50% de margem, ROAS minimo aceitavel e 2.0.
- CPA (custo por venda) ideal: < 30% do ticket medio do produto.
- Pixel do Meta precisa de pelo menos 50 eventos de compra por semana para sair do aprendizado.
- Retargeting de abandono de carrinho: CPA tipicamente 50-70% menor que prospeccao fria.
- Campanha de prospeccao + retargeting separados: melhor controle de orcamento e otimizacao.""",
    },
    {
        "titulo": "estrutura de campanha meta ads boas praticas",
        "nichos": ["geral"],
        "tipo_campanha": "geral",
        "fonte": "seed",
        "regras": """- Estrutura recomendada: 1 campanha por objetivo, 2-4 adsets por campanha, 2-3 ads por adset.
- Nao criar muitos adsets em 1 campanha — fragmenta orcamento e atrasa aprendizado.
- Testar 1 variavel por vez: ou publico diferente (adset) ou criativo diferente (ad).
- Nomenclatura padrao: [CLIENTE] [OBJETIVO] [PUBLICO/SEGMENTO] [DATA].
- Nunca editar ad ativo — sempre duplicar e pausar o original para manter historico.""",
    },
]


def _get_db():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL não definido")
    return psycopg2.connect(db_url)


def run():
    conn = _get_db()
    cur = conn.cursor()
    inseridos = 0
    pulados = 0

    for bloco in BLOCOS:
        titulo_norm = bloco["titulo"].lower().strip()
        cur.execute(
            "SELECT id FROM gestor_conhecimento WHERE LOWER(TRIM(titulo)) = %s",
            (titulo_norm,),
        )
        if cur.fetchone():
            pulados += 1
            continue

        cur.execute(
            """
            INSERT INTO gestor_conhecimento (titulo, regras, nichos, tipo_campanha, fonte, origem)
            VALUES (%s, %s, %s, %s, %s, 'seed')
            """,
            (
                bloco["titulo"],
                bloco["regras"],
                bloco["nichos"],
                bloco.get("tipo_campanha", "geral"),
                bloco.get("fonte", "seed"),
            ),
        )
        inseridos += 1

    conn.commit()
    conn.close()
    print(f"Seed concluido: {inseridos} inseridos, {pulados} ja existiam.")


if __name__ == "__main__":
    run()
