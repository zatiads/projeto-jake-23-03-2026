import copy
import json as _json
import re as _re
from datetime import date, timedelta
from html import escape as _he

from flask import Blueprint, Response, jsonify, request

from .shared import anthropic_client, get_db, login_required

bp = Blueprint('nutricao', __name__)


# ── Helpers de cálculo ───────────────────────────────────────────────────────

def _calcular_imc(peso, altura):
    if not peso or not altura:
        return 0
    return round(float(peso) / ((float(altura) / 100) ** 2), 1)


def _calcular_tmb(sexo, peso, altura, idade):
    if not all([peso, altura, idade]):
        return 0
    base = (10 * float(peso)) + (6.25 * float(altura)) - (5 * int(idade))
    return base + 5 if str(sexo or '').upper() == 'M' else base - 161


def _calcular_get(tmb, nivel_atividade):
    fatores = {'sedentario': 1.2, 'moderado': 1.55, 'intenso': 1.725}
    return float(tmb) * fatores.get(nivel_atividade, 1.55)


def _calcular_macros(objetivo, get, peso):
    if objetivo == 'hipertrofia':
        meta_cal = get + 400
        proteina = float(peso) * 2.0
    elif objetivo == 'emagrecimento':
        meta_cal = get - 400
        proteina = float(peso) * 2.2
    else:
        meta_cal = get
        proteina = float(peso) * 1.8
    gordura = (meta_cal * 0.25) / 9
    carbo = (meta_cal - (proteina * 4) - (gordura * 9)) / 4
    return {
        'calorias': int(meta_cal),
        'proteina': int(proteina),
        'carbo': int(max(carbo, 0)),
        'gordura': int(gordura),
    }


# ── Rotas ────────────────────────────────────────────────────────────────────

@bp.route("/api/nutricao/perfis")
@login_required
def nutricao_get_perfis():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM nutricao_perfis ORDER BY id")
        perfis = [dict(r) for r in cur.fetchall()]
        for p in perfis:
            if p.get('peso') and p.get('altura'):
                p['imc'] = _calcular_imc(p['peso'], p['altura'])
            else:
                p['imc'] = None
            for k in ['peso', 'altura', 'tmb', 'get', 'meta_calorica',
                      'meta_proteina', 'meta_carbo', 'meta_gordura']:
                if p.get(k) is not None:
                    p[k] = float(p[k])
        return jsonify({'perfis': perfis})
    finally:
        conn.close()


@bp.route("/api/nutricao/perfis/<int:perfil_id>", methods=["POST"])
@login_required
def nutricao_update_perfil(perfil_id):
    data = request.get_json() or {}
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM nutricao_perfis WHERE id = %s", (perfil_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'perfil não encontrado'}), 404
        perfil = dict(row)

        campos = ['idade', 'peso', 'altura', 'objetivo', 'nivel_atividade',
                  'preferencias', 'aversoes']
        for campo in campos:
            if campo in data:
                perfil[campo] = data[campo]

        tmb = _calcular_tmb(
            perfil.get('sexo', 'M'),
            perfil.get('peso'), perfil.get('altura'), perfil.get('idade')
        )
        get = _calcular_get(tmb, perfil.get('nivel_atividade', 'intenso'))
        macros = _calcular_macros(
            perfil.get('objetivo', 'hipertrofia'), get, perfil.get('peso', 70)
        )

        if tmb > 0:
            cur.execute("""
                UPDATE nutricao_perfis SET
                    idade=%s, peso=%s, altura=%s, objetivo=%s,
                    nivel_atividade=%s, preferencias=%s, aversoes=%s,
                    tmb=%s, get=%s, meta_calorica=%s, meta_proteina=%s,
                    meta_carbo=%s, meta_gordura=%s, atualizado_em=NOW()
                WHERE id=%s
            """, (
                perfil.get('idade'), perfil.get('peso'), perfil.get('altura'),
                perfil.get('objetivo'), perfil.get('nivel_atividade'),
                perfil.get('preferencias'), perfil.get('aversoes'),
                tmb, get, macros['calorias'], macros['proteina'],
                macros['carbo'], macros['gordura'],
                perfil_id
            ))
        else:
            cur.execute("""
                UPDATE nutricao_perfis SET
                    idade=%s, peso=%s, altura=%s, objetivo=%s,
                    nivel_atividade=%s, preferencias=%s, aversoes=%s,
                    atualizado_em=NOW()
                WHERE id=%s
            """, (
                perfil.get('idade'), perfil.get('peso'), perfil.get('altura'),
                perfil.get('objetivo'), perfil.get('nivel_atividade'),
                perfil.get('preferencias'), perfil.get('aversoes'),
                perfil_id
            ))
        conn.commit()
        return jsonify({'ok': True, 'tmb': tmb, 'get': get, **macros})
    finally:
        conn.close()


@bp.route("/api/nutricao/gerar-cardapio", methods=["POST"])
@login_required
def nutricao_gerar_cardapio():
    client = anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    conn = get_db()
    try:
        cur = conn.cursor()

        cur.execute("SELECT * FROM nutricao_perfis ORDER BY id LIMIT 2")
        perfis = {p['nome'].lower(): dict(p) for p in cur.fetchall()}
        bruno = perfis.get('bruno', {})
        camila = perfis.get('camila', {})

        cur.execute("SELECT nome, categoria FROM nutricao_alimentos_base WHERE favorito=true ORDER BY categoria")
        alimentos = cur.fetchall()
        proteinas = [a['nome'] for a in alimentos if a['categoria'] == 'proteina']
        carbos = [a['nome'] for a in alimentos if a['categoria'] == 'carbo']
        lanches = [a['nome'] for a in alimentos if a['categoria'] == 'lanche']

        hoje = date.today()
        segunda = hoje - timedelta(days=hoje.weekday())
        domingo = segunda + timedelta(days=6)

        def fmt_perfil(p, nome, sexo_label):
            peso = float(p.get('peso') or 75)
            altura = int(p.get('altura') or 175)
            idade = int(p.get('idade') or 28)
            tmb = float(p.get('tmb') or 0)
            get_val = float(p.get('get') or 0)
            meta_cal = int(p.get('meta_calorica') or 0)
            meta_prot = int(p.get('meta_proteina') or 0)
            meta_carbo = int(p.get('meta_carbo') or 0)
            meta_gord = int(p.get('meta_gordura') or 0)
            imc = _calcular_imc(peso, altura)
            return f"""=== {nome.upper()} ({sexo_label}, academia intensa) ===
Idade: {idade} anos | Peso: {peso}kg | Altura: {altura}cm | IMC: {imc}
TMB: {tmb:.0f} kcal | GET: {get_val:.0f} kcal | Meta: {meta_cal} kcal/dia
Proteína: {meta_prot}g | Carbo: {meta_carbo}g | Gordura: {meta_gord}g
Objetivo: Hipertrofia — ganho de massa muscular"""

        system_prompt = """Você é um nutricionista especializado em hipertrofia e ganho de massa muscular. Crie cardápios práticos, saborosos e com foco em alimentos fáceis de preparar e congelar. Retorne APENAS JSON válido, sem markdown, sem explicações."""

        user_prompt = f"""Crie um cardápio semanal completo (7 dias) para 2 pessoas:

{fmt_perfil(bruno, 'Bruno', 'homem')}

{fmt_perfil(camila, 'Camila', 'mulher')}

=== ALIMENTOS QUE JÁ USAM E GOSTAM ===
Proteínas: {', '.join(proteinas)}
Carbos: {', '.join(carbos)}
Lanches: {', '.join(lanches)}
Sem restrições alimentares.

=== REGRAS OBRIGATÓRIAS ===
1. Priorizar alimentos que já conhecem, misturando com no mínimo 3 refeições novas
2. Café da manhã: rotacionar entre pão com requeijão/queijo, banana com granola/mel/aveia, ovo
3. Almoço e janta: prato principal + acompanhamento + verdura. Indicar se é congelável
4. Café da tarde: lanche nutritivo, congelável quando possível
5. Suco diário: 1 por dia para encher 1 garrafinha (300-500ml), sucos funcionais
6. Fruta do dia: 1 fruta diferente por dia
7. Porções diferentes para Bruno e Camila conforme suas metas calóricas
8. Incluir receitas detalhadas de pratos novos
9. Tempo de preparo realista (pessoas que trabalham)

Semana de {segunda.strftime('%d/%m')} a {domingo.strftime('%d/%m/%Y')}.

Estrutura JSON obrigatória:
{{
  "semana": "{segunda.strftime('%d/%m')} a {domingo.strftime('%d/%m/%Y')}",
  "resumo": {{
    "bruno": {{"calorias_dia": 0, "proteina_dia": "0g", "carbo_dia": "0g", "gordura_dia": "0g"}},
    "camila": {{"calorias_dia": 0, "proteina_dia": "0g", "carbo_dia": "0g", "gordura_dia": "0g"}}
  }},
  "dias": [
    {{
      "dia": "Segunda-feira",
      "refeicoes": {{
        "cafe_manha": {{"descricao": "...", "bruno": {{"porcao": "...", "calorias": 0}}, "camila": {{"porcao": "...", "calorias": 0}}}},
        "almoco": {{"prato_principal": "...", "acompanhamento": "...", "verdura": "...", "congelavel": true, "tempo_preparo": "30min", "bruno": {{"porcao": "...", "calorias": 0, "proteina": "0g"}}, "camila": {{"porcao": "...", "calorias": 0, "proteina": "0g"}}}},
        "cafe_tarde": {{"descricao": "...", "congelavel": true, "bruno": {{"porcao": "...", "calorias": 0}}, "camila": {{"porcao": "...", "calorias": 0}}}},
        "janta": {{"prato_principal": "...", "acompanhamento": "...", "congelavel": true, "tempo_preparo": "25min", "bruno": {{"porcao": "...", "calorias": 0, "proteina": "0g"}}, "camila": {{"porcao": "...", "calorias": 0, "proteina": "0g"}}}},
        "suco_dia": {{"nome": "...", "ingredientes": ["..."], "beneficio": "..."}},
        "fruta_dia": "..."
      }}
    }}
  ],
  "dicas_preparo": ["..."],
  "receitas_detalhadas": [
    {{"nome": "...", "ingredientes": [{{"item": "...", "quantidade": "..."}}], "modo_preparo": ["passo 1"], "rende": "...", "tempo": "...", "congelavel": true, "validade_freezer": "..."}}
  ]
}}"""

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=16000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        texto = msg.content[0].text.strip()
        match = _re.search(r'```(?:json)?\s*([\s\S]*?)```', texto)
        if match:
            texto = match.group(1).strip()
        cardapio_json = _json.loads(texto)

        cur.execute("""
            INSERT INTO nutricao_cardapios
                (semana_inicio, semana_fim, status, cardapio_json)
            VALUES (%s, %s, 'revisao', %s)
            RETURNING id
        """, (segunda, domingo, _json.dumps(cardapio_json)))
        cardapio_id = cur.fetchone()['id']
        conn.commit()

        return jsonify({
            'ok': True,
            'id': cardapio_id,
            'cardapio': cardapio_json,
            'semana_inicio': str(segunda),
            'semana_fim': str(domingo),
        })

    except _json.JSONDecodeError as e:
        return jsonify({'error': f'Claude retornou JSON inválido: {str(e)}'}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/nutricao/cardapios")
@login_required
def nutricao_listar_cardapios():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, semana_inicio, semana_fim, status, criado_em, aprovado_em
            FROM nutricao_cardapios ORDER BY criado_em DESC LIMIT 20
        """)
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            for k in ['semana_inicio', 'semana_fim']:
                if d.get(k):
                    d[k] = str(d[k])
            for k in ['criado_em', 'aprovado_em']:
                if d.get(k):
                    d[k] = d[k].isoformat()
            rows.append(d)
        return jsonify({'cardapios': rows})
    finally:
        conn.close()


@bp.route("/api/nutricao/cardapios/<int:cardapio_id>")
@login_required
def nutricao_get_cardapio(cardapio_id):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM nutricao_cardapios WHERE id = %s", (cardapio_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'não encontrado'}), 404
        d = dict(row)
        for k in ['semana_inicio', 'semana_fim']:
            if d.get(k): d[k] = str(d[k])
        for k in ['criado_em', 'aprovado_em']:
            if d.get(k): d[k] = d[k].isoformat()
        return jsonify(d)
    finally:
        conn.close()


@bp.route("/api/nutricao/cardapios/<int:cardapio_id>/aprovar", methods=["PATCH"])
@login_required
def nutricao_aprovar_cardapio(cardapio_id):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE nutricao_cardapios
            SET status='aprovado', aprovado_em=NOW()
            WHERE id=%s
            RETURNING cardapio_json
        """, (cardapio_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return jsonify({'error': 'não encontrado'}), 404
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@bp.route("/api/nutricao/cardapios/<int:cardapio_id>/editar-refeicao", methods=["PATCH"])
@login_required
def nutricao_editar_refeicao(cardapio_id):
    data = request.get_json() or {}
    dia_nome = data.get('dia')
    tipo = data.get('refeicao')
    novo_conteudo = data.get('novo_conteudo', {})

    if not dia_nome or not tipo:
        return jsonify({'error': 'campos obrigatórios: dia, refeicao, novo_conteudo'}), 400

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT cardapio_json FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'não encontrado'}), 404

        cardapio = copy.deepcopy(row['cardapio_json']) if row['cardapio_json'] else {}
        dia_encontrado = False
        for dia in cardapio.get('dias', []):
            if dia.get('dia') == dia_nome:
                if 'refeicoes' not in dia:
                    dia['refeicoes'] = {}
                dia['refeicoes'][tipo] = novo_conteudo
                dia_encontrado = True
                break

        if not dia_encontrado:
            return jsonify({'error': f'dia não encontrado: {dia_nome}'}), 404

        cur.execute("""
            UPDATE nutricao_cardapios
            SET cardapio_json=%s, status='revisao'
            WHERE id=%s
        """, (_json.dumps(cardapio), cardapio_id))
        conn.commit()
        return jsonify({'ok': True, 'cardapio': cardapio})
    finally:
        conn.close()


@bp.route("/api/nutricao/lista-compras/<int:cardapio_id>", methods=["POST"])
@login_required
def nutricao_gerar_lista_compras(cardapio_id):
    client = anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT cardapio_json FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'cardápio não encontrado'}), 404

        cardapio_json = row['cardapio_json']

        resumo_dias = []
        for dia in (cardapio_json.get("dias") or []):
            ref = dia.get("refeicoes", {})
            resumo_dias.append(
                f"{dia.get('dia','')}: "
                f"café={ref.get('cafe_manha',{}).get('descricao','')} | "
                f"almoço={ref.get('almoco',{}).get('prato_principal','')} + {ref.get('almoco',{}).get('acompanhamento','')} + {ref.get('almoco',{}).get('verdura','')} | "
                f"lanche={ref.get('cafe_tarde',{}).get('descricao','')} | "
                f"janta={ref.get('janta',{}).get('prato_principal','')} + {ref.get('janta',{}).get('acompanhamento','')} | "
                f"suco={ref.get('suco_dia',{}).get('ingredientes',[])} | "
                f"fruta={ref.get('fruta_dia','')}"
            )
        cardapio_resumo = "\n".join(resumo_dias)

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system="Você é um assistente de compras. Analise o cardápio semanal e retorne APENAS JSON com a lista de compras consolidada, agrupada por categoria de supermercado, com quantidades somadas para a semana toda (2 pessoas). Sem markdown, sem texto adicional.",
            messages=[{"role": "user", "content": f"""Cardápio da semana (2 pessoas):
{cardapio_resumo}

Retorne JSON nessa estrutura:
{{
  "categorias": [
    {{"nome": "Proteínas", "emoji": "🥩", "itens": [{{"item": "Filé de frango", "quantidade": "1,5kg", "observacao": "para a semana toda"}}]}},
    {{"nome": "Carboidratos", "emoji": "🌾", "itens": [...]}},
    {{"nome": "Laticínios", "emoji": "🧀", "itens": [...]}},
    {{"nome": "Frutas", "emoji": "🍎", "itens": [...]}},
    {{"nome": "Verduras e Legumes", "emoji": "🥦", "itens": [...]}},
    {{"nome": "Lanches e Extras", "emoji": "🧁", "itens": [...]}},
    {{"nome": "Temperos e Condimentos", "emoji": "🧂", "itens": [...]}}
  ],
  "total_estimado_itens": 0,
  "dica": "dica rápida de organização das compras"
}}"""}]
        )

        texto = msg.content[0].text.strip()
        match = _re.search(r'```(?:json)?\s*([\s\S]*?)```', texto)
        if match:
            texto = match.group(1).strip()
        lista_json = _json.loads(texto)

        cur.execute("""
            UPDATE nutricao_cardapios
            SET lista_compras_json=%s WHERE id=%s
        """, (_json.dumps(lista_json), cardapio_id))
        conn.commit()

        return jsonify({'ok': True, 'lista': lista_json})
    except _json.JSONDecodeError as e:
        conn.rollback()
        return jsonify({'error': f'JSON inválido: {str(e)}'}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/nutricao/exportar-whatsapp/<int:cardapio_id>")
@login_required
def nutricao_exportar_whatsapp(cardapio_id):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT lista_compras_json, semana_inicio, semana_fim FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row or not row['lista_compras_json']:
            return jsonify({'error': 'lista de compras não gerada ainda'}), 404

        lista = row['lista_compras_json']
        sem_ini = str(row['semana_inicio'])[:10] if row['semana_inicio'] else '—'
        sem_fim = str(row['semana_fim'])[:10] if row['semana_fim'] else '—'

        def fmt_data(d):
            if not d or d == '—':
                return d or '—'
            parts = d.split('-')
            return f"{parts[2]}/{parts[1]}" if len(parts) == 3 else d

        linhas = [
            f"🛒 *LISTA DE COMPRAS — Semana {fmt_data(sem_ini)} a {fmt_data(sem_fim)}*",
            "_Cardápio de hipertrofia para 2 pessoas_",
            "",
        ]

        for cat in lista.get('categorias', []):
            if not cat.get('itens'):
                continue
            linhas.append(f"{cat.get('emoji', '•')} *{cat['nome'].upper()}*")
            for item in cat['itens']:
                qtd = f" — {item['quantidade']}" if item.get('quantidade') else ''
                linhas.append(f"☐ {item.get('item', '?')}{qtd}")
            linhas.append("")

        if lista.get('dica'):
            linhas.append(f"💡 _{lista['dica']}_")
            linhas.append("")

        linhas.append("✅ _Gerado pelo Jake OS • Piloti_")

        return jsonify({'texto': '\n'.join(linhas), 'sucesso': True})
    finally:
        conn.close()


@bp.route("/api/nutricao/exportar-pdf/<int:cardapio_id>")
@login_required
def nutricao_exportar_pdf(cardapio_id):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row:
            return "Cardápio não encontrado", 404

        cardapio = row['cardapio_json'] or {}
        sem_ini = str(row['semana_inicio'])[:10] if row['semana_inicio'] else ''
        sem_fim = str(row['semana_fim'])[:10] if row['semana_fim'] else ''

        def fmt_data(d):
            if not d or d == '—':
                return d or '—'
            parts = d.split('-')
            return f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else d

        dias_html = ""
        for dia in cardapio.get('dias', []):
            r = dia.get('refeicoes', {})
            dias_html += f"""
            <div class="dia">
              <h3 class="dia-nome">{_he(str(dia.get('dia', '') or ''))}</h3>
              <table>
                <thead><tr><th>Refeição</th><th>Descrição</th><th>Bruno</th><th>Camila</th></tr></thead>
                <tbody>"""

            for tipo, label in [('cafe_manha', '☀️ Café da Manhã'), ('almoco', '🍽 Almoço'),
                                 ('cafe_tarde', '🫖 Café da Tarde'), ('janta', '🌙 Janta')]:
                ref = r.get(tipo, {})
                if not ref:
                    continue
                if tipo in ('almoco', 'janta'):
                    descricao = f"{_he(str(ref.get('prato_principal', '—') or '—'))}<br><small>{_he(str(ref.get('acompanhamento', '') or ''))} {_he(str(ref.get('verdura', '') or ''))}</small>"
                    congelavel = ' 🧊' if ref.get('congelavel') else ''
                    descricao += f"<br><small>{_he(str(ref.get('tempo_preparo', '') or ''))}{congelavel}</small>"
                    bruno_info = f"{_he(str(ref.get('bruno', {}).get('porcao', '—') or '—'))}<br><small>{_he(str(ref.get('bruno', {}).get('calorias', '—') or '—'))} kcal | {_he(str(ref.get('bruno', {}).get('proteina', '—') or '—'))}</small>"
                    camila_info = f"{_he(str(ref.get('camila', {}).get('porcao', '—') or '—'))}<br><small>{_he(str(ref.get('camila', {}).get('calorias', '—') or '—'))} kcal | {_he(str(ref.get('camila', {}).get('proteina', '—') or '—'))}</small>"
                else:
                    descricao = _he(str(ref.get('descricao', '—') or '—'))
                    congelavel = ' 🧊' if ref.get('congelavel') else ''
                    descricao += congelavel
                    bruno_info = f"{_he(str(ref.get('bruno', {}).get('porcao', '—') or '—'))}<br><small>{_he(str(ref.get('bruno', {}).get('calorias', '—') or '—'))} kcal</small>"
                    camila_info = f"{_he(str(ref.get('camila', {}).get('porcao', '—') or '—'))}<br><small>{_he(str(ref.get('camila', {}).get('calorias', '—') or '—'))} kcal</small>"

                dias_html += f"<tr><td><b>{label}</b></td><td>{descricao}</td><td>{bruno_info}</td><td>{camila_info}</td></tr>"

            suco = r.get('suco_dia', {})
            fruta = r.get('fruta_dia', '')
            if suco:
                ingredientes = ', '.join(_he(str(ing or '')) for ing in suco.get('ingredientes', []))
                dias_html += f"<tr><td>🥤 Suco</td><td>{_he(str(suco.get('nome', '—') or '—'))}<br><small>{ingredientes}</small></td><td colspan='2'>{_he(str(suco.get('beneficio', '') or ''))}</td></tr>"
            if fruta:
                dias_html += f"<tr><td>🍎 Fruta</td><td colspan='3'>{_he(str(fruta or ''))}</td></tr>"

            dias_html += "</tbody></table></div>"

        receitas_html = ""
        for rec in cardapio.get('receitas_detalhadas', []):
            ingredientes_li = ''.join(f"<li>{_he(str(i.get('item', '') or ''))} — {_he(str(i.get('quantidade', '') or ''))}</li>" for i in rec.get('ingredientes', []))
            passos_li = ''.join(f"<li>{_he(str(p or ''))}</li>" for p in rec.get('modo_preparo', []))
            congelavel = ' 🧊 Congelável' if rec.get('congelavel') else ''
            receitas_html += f"""
            <div class="receita">
              <h4>{_he(str(rec.get('nome', '') or ''))}{congelavel}</h4>
              <p><small>⏱ {_he(str(rec.get('tempo', '') or ''))} • Rende: {_he(str(rec.get('rende', '') or ''))} • Freezer: {_he(str(rec.get('validade_freezer', '') or ''))}</small></p>
              <div class="receita-cols">
                <div><strong>Ingredientes</strong><ul>{ingredientes_li}</ul></div>
                <div><strong>Modo de Preparo</strong><ol>{passos_li}</ol></div>
              </div>
            </div>"""

        dicas_html = ''.join(f"<li>{_he(str(d or ''))}</li>" for d in cardapio.get('dicas_preparo', []))

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Cardápio — {_he(fmt_data(sem_ini))} a {_he(fmt_data(sem_fim))}</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12px; color: #1a1a1a; margin: 0; padding: 20px; }}
  h1 {{ color: #2e7d32; font-size: 22px; margin-bottom: 4px; }}
  h2 {{ color: #388e3c; font-size: 16px; border-bottom: 2px solid #81c784; padding-bottom: 4px; margin-top: 24px; }}
  h3.dia-nome {{ background: #e8f5e9; padding: 8px 12px; color: #1b5e20; font-size: 14px; margin: 16px 0 6px; border-left: 4px solid #43a047; }}
  h4 {{ color: #2e7d32; margin: 10px 0 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 11px; }}
  th {{ background: #43a047; color: white; padding: 6px 8px; text-align: left; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }}
  tr:nth-child(even) td {{ background: #f9fbe7; }}
  .receita {{ background: #f1f8e9; border-radius: 6px; padding: 12px; margin-bottom: 12px; }}
  .receita-cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  ul, ol {{ padding-left: 18px; margin: 4px 0; }}
  li {{ margin-bottom: 2px; }}
  .dicas {{ background: #fff8e1; padding: 12px; border-radius: 6px; }}
  footer {{ text-align: center; color: #999; font-size: 10px; margin-top: 24px; border-top: 1px solid #eee; padding-top: 8px; }}
  @media print {{
    body {{ padding: 10px; }}
    h3.dia-nome {{ page-break-before: auto; }}
    .receita {{ page-break-inside: avoid; }}
  }}
</style>
</head>
<body>
  <h1>🥗 Cardápio Semanal</h1>
  <p><strong>Semana:</strong> {_he(fmt_data(sem_ini))} a {_he(fmt_data(sem_fim))} &nbsp;|&nbsp; <strong>Bruno &amp; Camila</strong> &nbsp;|&nbsp; Foco: Hipertrofia</p>
  <h2>📅 Cardápio Dia a Dia</h2>
  {dias_html}
  <h2>👨‍🍳 Receitas Detalhadas</h2>
  {receitas_html}
  <h2>💡 Dicas de Preparo e Congelamento</h2>
  <div class="dicas"><ul>{dicas_html}</ul></div>
  <footer>Gerado pelo Jake OS &nbsp;•&nbsp; Piloti &nbsp;•&nbsp; {_he(fmt_data(sem_ini))} a {_he(fmt_data(sem_fim))}</footer>
</body>
</html>"""

        return Response(
            html,
            mimetype='text/html',
            headers={'Content-Disposition': f'inline; filename=cardapio_{sem_ini}.html'}
        )
    finally:
        conn.close()
