# Nutrição Jake OS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a seção "Nutrição" no Jake OS — sistema completo de cardápio semanal para Bruno e Camila com geração via Claude, revisão, exportação PDF e lista de compras para WhatsApp.

**Architecture:** Backend Flask monolítico em `app.py` com rotas `/api/nutricao/`, seção SPA no `dashboard.html` seguindo o padrão das seções existentes (social-brief, financeiro), módulo JS em `nutricao.js` com IIFE pattern.

**Tech Stack:** Flask, psycopg2 (Neon/PostgreSQL), Anthropic Claude claude-sonnet-4-6, HTML/CSS/JS vanilla (sem frameworks), wkhtmltopdf já instalado na VPS.

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `jake_desktop/app.py` | Modificar | Rotas `/api/nutricao/*`, criação de tabelas, cálculos TMB/GET/macros, integração Claude |
| `jake_desktop/templates/dashboard.html` | Modificar | Adicionar nav item, `<section id="page-nutricao">`, CSS inline da seção |
| `jake_desktop/static/js/nutricao.js` | Criar | Módulo JS completo: estado, renderização, calls de API |
| `jake_desktop/static/js/app.js` | Modificar | Adicionar `'nutricao'` à lista `valid` e chamar `initNutricao()` |

---

## Task 1: Banco de Dados — Tabelas e Dados Iniciais

**Files:**
- Modify: `jake_desktop/app.py` — adicionar função `_init_nutricao_tables()` chamada no startup

- [ ] **Step 1: Localizar onde as outras tabelas são criadas no app.py**

```bash
grep -n "CREATE TABLE\|def _init\|if __name__" /root/jake_desktop/app.py | head -20
```

- [ ] **Step 2: Adicionar função de criação das tabelas em app.py**

Encontre a função de init do banco (ou o bloco `if __name__ == '__main__'`) e adicione antes dela:

```python
def _init_nutricao_tables():
    """Cria tabelas de nutrição se não existirem e insere dados iniciais."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nutricao_perfis (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                sexo VARCHAR(1) DEFAULT 'M',
                idade INTEGER,
                peso DECIMAL(5,2),
                altura INTEGER,
                objetivo VARCHAR(50) DEFAULT 'hipertrofia',
                nivel_atividade VARCHAR(50) DEFAULT 'intenso',
                restricoes TEXT[],
                preferencias TEXT,
                aversoes TEXT,
                tmb DECIMAL(8,2),
                get DECIMAL(8,2),
                meta_calorica INTEGER,
                meta_proteina INTEGER,
                meta_carbo INTEGER,
                meta_gordura INTEGER,
                atualizado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nutricao_cardapios (
                id SERIAL PRIMARY KEY,
                semana_inicio DATE NOT NULL,
                semana_fim DATE NOT NULL,
                status VARCHAR(20) DEFAULT 'rascunho',
                cardapio_json JSONB,
                lista_compras_json JSONB,
                criado_em TIMESTAMP DEFAULT NOW(),
                aprovado_em TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nutricao_alimentos_base (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(200) NOT NULL,
                categoria VARCHAR(50),
                congelavel BOOLEAN DEFAULT FALSE,
                favorito BOOLEAN DEFAULT FALSE,
                notas TEXT
            )
        """)
        # Perfis iniciais
        cur.execute("""
            INSERT INTO nutricao_perfis (nome, sexo, objetivo, nivel_atividade)
            VALUES ('Bruno', 'M', 'hipertrofia', 'intenso'),
                   ('Camila', 'F', 'hipertrofia', 'intenso')
            ON CONFLICT DO NOTHING
        """)
        # Alimentos base favoritos
        alimentos = [
            ('Carne moída', 'proteina', True, True),
            ('Lombo suíno', 'proteina', True, True),
            ('Filé de frango', 'proteina', True, True),
            ('Macarrão', 'carbo', False, True),
            ('Purê de batata', 'carbo', True, True),
            ('Torta de frango', 'lanche', True, True),
            ('Pão de forma', 'lanche', False, True),
            ('Banana', 'fruta', False, True),
            ('Granola', 'lanche', False, True),
            ('Aveia', 'lanche', False, True),
            ('Mel', 'lanche', False, True),
            ('Requeijão', 'lanche', False, True),
            ('Queijo', 'lanche', False, True),
            ('Ovo', 'proteina', False, True),
            ('Bolo de açúcar mascavo', 'lanche', True, True),
            ('Nozes', 'lanche', False, True),
            ('Castanha', 'lanche', False, True),
        ]
        for nome, cat, cong, fav in alimentos:
            cur.execute("""
                INSERT INTO nutricao_alimentos_base (nome, categoria, congelavel, favorito)
                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
            """, (nome, cat, cong, fav))
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 3: Chamar `_init_nutricao_tables()` no startup**

Encontre onde o app inicializa tabelas (procure por `_init` ou `if __name__`) e adicione:

```python
_init_nutricao_tables()
```

- [ ] **Step 4: Verificar criação das tabelas**

```bash
cd /root && /root/venv/bin/python3 -c "
from jake_desktop.app import _init_nutricao_tables
_init_nutricao_tables()
print('OK')
"
```

Ou reiniciar o Jake OS e verificar nos logs.

- [ ] **Step 5: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: criar tabelas nutricao_perfis, nutricao_cardapios, nutricao_alimentos_base"
```

---

## Task 2: Backend — Funções de Cálculo + Rotas de Perfis

**Files:**
- Modify: `jake_desktop/app.py` — funções de cálculo + rotas GET/POST perfis

- [ ] **Step 1: Adicionar funções de cálculo em app.py** (antes das rotas de nutrição)

```python
# ── NUTRIÇÃO: Cálculos ────────────────────────────────────────────────────────

def _calcular_imc(peso, altura):
    """Retorna IMC arredondado para 1 casa."""
    if not peso or not altura:
        return 0
    return round(float(peso) / ((float(altura) / 100) ** 2), 1)

def _calcular_tmb(sexo, peso, altura, idade):
    """Fórmula Mifflin-St Jeor."""
    if not all([peso, altura, idade]):
        return 0
    base = (10 * float(peso)) + (6.25 * float(altura)) - (5 * int(idade))
    return base + 5 if sexo == 'M' else base - 161

def _calcular_get(tmb, nivel_atividade):
    fatores = {'sedentario': 1.2, 'moderado': 1.55, 'intenso': 1.725}
    return float(tmb) * fatores.get(nivel_atividade, 1.55)

def _calcular_macros(objetivo, get, peso):
    """Retorna dict com calorias, proteina, carbo, gordura."""
    if objetivo == 'hipertrofia':
        meta_cal = get + 400
        proteina = float(peso) * 2.0
    elif objetivo == 'emagrecimento':
        meta_cal = get - 400
        proteina = float(peso) * 2.2
    else:  # manutencao
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
```

- [ ] **Step 2: Adicionar rota GET perfis**

```python
@app.route("/api/nutricao/perfis")
@login_required
def nutricao_get_perfis():
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM nutricao_perfis ORDER BY id")
        perfis = [dict(r) for r in cur.fetchall()]
        for p in perfis:
            if p.get('peso') and p.get('altura'):
                p['imc'] = _calcular_imc(p['peso'], p['altura'])
            else:
                p['imc'] = None
            # converter Decimal para float para JSON
            for k in ['peso', 'altura', 'tmb', 'get', 'meta_calorica',
                      'meta_proteina', 'meta_carbo', 'meta_gordura']:
                if p.get(k) is not None:
                    p[k] = float(p[k])
        return jsonify({'perfis': perfis})
    finally:
        conn.close()
```

- [ ] **Step 3: Adicionar rota POST atualizar perfil**

```python
@app.route("/api/nutricao/perfis/<int:perfil_id>", methods=["POST"])
@login_required
def nutricao_update_perfil(perfil_id):
    data = request.get_json() or {}
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM nutricao_perfis WHERE id = %s", (perfil_id,))
        perfil = dict(cur.fetchone())

        # Atualiza campos enviados
        campos = ['idade', 'peso', 'altura', 'objetivo', 'nivel_atividade',
                  'preferencias', 'aversoes']
        for campo in campos:
            if campo in data:
                perfil[campo] = data[campo]

        # Recalcula TMB/GET/macros
        tmb = _calcular_tmb(
            perfil.get('sexo', 'M'),
            perfil.get('peso'), perfil.get('altura'), perfil.get('idade')
        )
        get = _calcular_get(tmb, perfil.get('nivel_atividade', 'intenso'))
        macros = _calcular_macros(
            perfil.get('objetivo', 'hipertrofia'), get, perfil.get('peso', 70)
        )

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
        conn.commit()
        return jsonify({'ok': True, 'tmb': tmb, 'get': get, **macros})
    finally:
        conn.close()
```

- [ ] **Step 4: Testar rotas de perfis**

```bash
curl -s -b "session=..." http://localhost:5050/api/nutricao/perfis | python3 -m json.tool
```

(Ajuste a sessão conforme necessário — ou testar via browser logado no Jake OS)

- [ ] **Step 5: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: nutricao — calculos TMB/GET/macros + rotas GET/POST perfis"
```

---

## Task 3: Backend — Geração do Cardápio via Claude

**Files:**
- Modify: `jake_desktop/app.py` — rota `POST /api/nutricao/gerar-cardapio`

- [ ] **Step 1: Adicionar rota de geração do cardápio**

```python
@app.route("/api/nutricao/gerar-cardapio", methods=["POST"])
@login_required
def nutricao_gerar_cardapio():
    import json as _json
    from datetime import date, timedelta

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    conn = _get_db()
    try:
        cur = conn.cursor()

        # Buscar perfis
        cur.execute("SELECT * FROM nutricao_perfis ORDER BY id LIMIT 2")
        perfis = {p['nome'].lower(): dict(p) for p in cur.fetchall()}
        bruno = perfis.get('bruno', {})
        camila = perfis.get('camila', {})

        # Buscar alimentos favoritos
        cur.execute("SELECT nome, categoria FROM nutricao_alimentos_base WHERE favorito=true ORDER BY categoria")
        alimentos = cur.fetchall()
        proteinas = [a['nome'] for a in alimentos if a['categoria'] == 'proteina']
        carbos = [a['nome'] for a in alimentos if a['categoria'] == 'carbo']
        lanches = [a['nome'] for a in alimentos if a['categoria'] == 'lanche']

        # Semana atual
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
            max_tokens=8000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        texto = msg.content[0].text.strip()
        # Limpar possível markdown do Claude
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        cardapio_json = _json.loads(texto)

        # Salvar no banco com status 'revisao'
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
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
```

- [ ] **Step 2: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: nutricao — rota gerar-cardapio via Claude"
```

---

## Task 4: Backend — Aprovar, Editar Refeição, Lista de Compras

**Files:**
- Modify: `jake_desktop/app.py` — rotas PATCH aprovar, PATCH editar-refeicao, POST lista-compras, GET cardapios

- [ ] **Step 1: Rota GET listar cardápios + GET cardápio por ID**

```python
@app.route("/api/nutricao/cardapios")
@login_required
def nutricao_listar_cardapios():
    conn = _get_db()
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

@app.route("/api/nutricao/cardapios/<int:cardapio_id>")
@login_required
def nutricao_get_cardapio(cardapio_id):
    import json as _json
    conn = _get_db()
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
```

- [ ] **Step 2: Rota PATCH aprovar cardápio**

```python
@app.route("/api/nutricao/cardapios/<int:cardapio_id>/aprovar", methods=["PATCH"])
@login_required
def nutricao_aprovar_cardapio(cardapio_id):
    conn = _get_db()
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
            return jsonify({'error': 'não encontrado'}), 404
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()
```

- [ ] **Step 3: Rota PATCH editar refeição individual**

```python
@app.route("/api/nutricao/cardapios/<int:cardapio_id>/editar-refeicao", methods=["PATCH"])
@login_required
def nutricao_editar_refeicao(cardapio_id):
    import json as _json
    data = request.get_json() or {}
    dia_nome = data.get('dia')           # ex: 'Segunda-feira'
    tipo = data.get('refeicao')          # ex: 'almoco'
    novo_conteudo = data.get('novo_conteudo', {})

    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT cardapio_json FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'não encontrado'}), 404

        cardapio = dict(row['cardapio_json']) if row['cardapio_json'] else {}
        for dia in cardapio.get('dias', []):
            if dia.get('dia') == dia_nome:
                if 'refeicoes' not in dia:
                    dia['refeicoes'] = {}
                dia['refeicoes'][tipo] = novo_conteudo
                break

        cur.execute("""
            UPDATE nutricao_cardapios
            SET cardapio_json=%s, status='revisao'
            WHERE id=%s
        """, (_json.dumps(cardapio), cardapio_id))
        conn.commit()
        return jsonify({'ok': True, 'cardapio': cardapio})
    finally:
        conn.close()
```

- [ ] **Step 4: Rota POST gerar lista de compras**

```python
@app.route("/api/nutricao/lista-compras/<int:cardapio_id>", methods=["POST"])
@login_required
def nutricao_gerar_lista_compras(cardapio_id):
    import json as _json

    client = _anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT cardapio_json FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'cardápio não encontrado'}), 404

        cardapio_json = row['cardapio_json']

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            system="Você é um assistente de compras. Analise o cardápio e retorne APENAS JSON com a lista de compras consolidada, agrupada por categoria de supermercado, com quantidades somadas para a semana toda (2 pessoas). Sem markdown, sem texto adicional.",
            messages=[{"role": "user", "content": f"""Cardápio: {_json.dumps(cardapio_json, ensure_ascii=False)}

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
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        lista_json = _json.loads(texto)

        cur.execute("""
            UPDATE nutricao_cardapios
            SET lista_compras_json=%s WHERE id=%s
        """, (_json.dumps(lista_json), cardapio_id))
        conn.commit()

        return jsonify({'ok': True, 'lista': lista_json})
    except _json.JSONDecodeError as e:
        return jsonify({'error': f'JSON inválido: {str(e)}'}), 500
    finally:
        conn.close()
```

- [ ] **Step 5: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: nutricao — rotas aprovar, editar-refeicao, lista-compras, listar-cardapios"
```

---

## Task 5: Backend — Exportações WhatsApp e PDF

**Files:**
- Modify: `jake_desktop/app.py` — rotas de exportação

- [ ] **Step 1: Rota exportar para WhatsApp**

```python
@app.route("/api/nutricao/exportar-whatsapp/<int:cardapio_id>")
@login_required
def nutricao_exportar_whatsapp(cardapio_id):
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT lista_compras_json, semana_inicio, semana_fim FROM nutricao_cardapios WHERE id=%s", (cardapio_id,))
        row = cur.fetchone()
        if not row or not row['lista_compras_json']:
            return jsonify({'error': 'lista de compras não gerada ainda'}), 404

        lista = row['lista_compras_json']
        sem_ini = str(row['semana_inicio'])[:10] if row['semana_inicio'] else '—'
        sem_fim = str(row['semana_fim'])[:10] if row['semana_fim'] else '—'

        # Formatar datas dd/mm
        def fmt_data(d):
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
                linhas.append(f"☐ {item['item']}{qtd}")
            linhas.append("")

        if lista.get('dica'):
            linhas.append(f"💡 _{lista['dica']}_")
            linhas.append("")

        linhas.append("✅ _Gerado pelo Jake OS • Piloti_")

        return jsonify({'texto': '\n'.join(linhas), 'sucesso': True})
    finally:
        conn.close()
```

- [ ] **Step 2: Rota exportar PDF (HTML otimizado para impressão)**

```python
@app.route("/api/nutricao/exportar-pdf/<int:cardapio_id>")
@login_required
def nutricao_exportar_pdf(cardapio_id):
    import json as _json
    conn = _get_db()
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
            parts = d.split('-')
            return f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else d

        # Montar HTML das refeições por dia
        dias_html = ""
        for dia in cardapio.get('dias', []):
            r = dia.get('refeicoes', {})
            dias_html += f"""
            <div class="dia">
              <h3 class="dia-nome">{dia.get('dia', '')}</h3>
              <table>
                <thead><tr><th>Refeição</th><th>Descrição</th><th>Bruno</th><th>Camila</th></tr></thead>
                <tbody>"""

            for tipo, label in [('cafe_manha','☀️ Café da Manhã'), ('almoco','🍽 Almoço'),
                                 ('cafe_tarde','🫖 Café da Tarde'), ('janta','🌙 Janta')]:
                ref = r.get(tipo, {})
                if not ref: continue
                if tipo in ('almoco', 'janta'):
                    descricao = f"{ref.get('prato_principal','—')}<br><small>{ref.get('acompanhamento','')} {ref.get('verdura','')}</small>"
                    congelavel = ' 🧊' if ref.get('congelavel') else ''
                    descricao += f"<br><small>{ref.get('tempo_preparo','')}{congelavel}</small>"
                    bruno_info = f"{ref.get('bruno',{}).get('porcao','—')}<br><small>{ref.get('bruno',{}).get('calorias','—')} kcal | {ref.get('bruno',{}).get('proteina','—')}</small>"
                    camila_info = f"{ref.get('camila',{}).get('porcao','—')}<br><small>{ref.get('camila',{}).get('calorias','—')} kcal | {ref.get('camila',{}).get('proteina','—')}</small>"
                else:
                    descricao = ref.get('descricao', '—')
                    congelavel = ' 🧊' if ref.get('congelavel') else ''
                    descricao += congelavel
                    bruno_info = f"{ref.get('bruno',{}).get('porcao','—')}<br><small>{ref.get('bruno',{}).get('calorias','—')} kcal</small>"
                    camila_info = f"{ref.get('camila',{}).get('porcao','—')}<br><small>{ref.get('camila',{}).get('calorias','—')} kcal</small>"

                dias_html += f"<tr><td><b>{label}</b></td><td>{descricao}</td><td>{bruno_info}</td><td>{camila_info}</td></tr>"

            suco = r.get('suco_dia', {})
            fruta = r.get('fruta_dia', '')
            if suco:
                ingredientes = ', '.join(suco.get('ingredientes', []))
                dias_html += f"<tr><td>🥤 Suco</td><td>{suco.get('nome','—')}<br><small>{ingredientes}</small></td><td colspan='2'>{suco.get('beneficio','')}</td></tr>"
            if fruta:
                dias_html += f"<tr><td>🍎 Fruta</td><td colspan='3'>{fruta}</td></tr>"

            dias_html += "</tbody></table></div>"

        # Receitas detalhadas
        receitas_html = ""
        for rec in cardapio.get('receitas_detalhadas', []):
            ingredientes_li = ''.join(f"<li>{i.get('item','')} — {i.get('quantidade','')}</li>" for i in rec.get('ingredientes', []))
            passos_li = ''.join(f"<li>{p}</li>" for p in rec.get('modo_preparo', []))
            congelavel = ' 🧊 Congelável' if rec.get('congelavel') else ''
            receitas_html += f"""
            <div class="receita">
              <h4>{rec.get('nome','')}{congelavel}</h4>
              <p><small>⏱ {rec.get('tempo','')} • Rende: {rec.get('rende','')} • Freezer: {rec.get('validade_freezer','')}</small></p>
              <div class="receita-cols">
                <div><strong>Ingredientes</strong><ul>{ingredientes_li}</ul></div>
                <div><strong>Modo de Preparo</strong><ol>{passos_li}</ol></div>
              </div>
            </div>"""

        # Dicas
        dicas_html = ''.join(f"<li>{d}</li>" for d in cardapio.get('dicas_preparo', []))

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Cardápio — {fmt_data(sem_ini)} a {fmt_data(sem_fim)}</title>
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
  <p><strong>Semana:</strong> {fmt_data(sem_ini)} a {fmt_data(sem_fim)} &nbsp;|&nbsp; <strong>Bruno &amp; Camila</strong> &nbsp;|&nbsp; Foco: Hipertrofia</p>
  <h2>📅 Cardápio Dia a Dia</h2>
  {dias_html}
  <h2>👨‍🍳 Receitas Detalhadas</h2>
  {receitas_html}
  <h2>💡 Dicas de Preparo e Congelamento</h2>
  <div class="dicas"><ul>{dicas_html}</ul></div>
  <footer>Gerado pelo Jake OS &nbsp;•&nbsp; Piloti &nbsp;•&nbsp; {fmt_data(sem_ini)} a {fmt_data(sem_fim)}</footer>
</body>
</html>"""

        from flask import Response
        return Response(
            html,
            mimetype='text/html',
            headers={'Content-Disposition': f'inline; filename=cardapio_{sem_ini}.html'}
        )
    finally:
        conn.close()
```

- [ ] **Step 3: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat: nutricao — rotas exportar-whatsapp e exportar-pdf"
```

---

## Task 6: Frontend HTML + CSS no dashboard.html

**Files:**
- Modify: `jake_desktop/templates/dashboard.html` — nav item, CSS inline, `<section>` da página

- [ ] **Step 1: Adicionar nav item no sidebar**

Encontre o último item do menu lateral e adicione depois:

```html
<a class="nav-item" data-page="nutricao" href="#">
  <span class="nav-icon">🥗</span>
  <span class="nav-label">Nutrição</span>
</a>
```

- [ ] **Step 2: Adicionar CSS inline da seção Nutrição**

Encontre onde termina o último bloco `<style>` interno e adicione antes de `</style>` (ou crie novo bloco):

```html
<style id="nutricao-styles">
/* ===== NUTRIÇÃO ===== */
.nutr-page { padding: 24px; max-width: 1200px; }
.nutr-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.nutr-header h2 { font-family: 'Rajdhani', sans-serif; font-size: 28px; font-weight: 700; color: #eceff1; margin: 0; }
.nutr-header h2 span { color: #00e5ff; }

/* Perfis */
.nutr-perfis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
.nutr-perfil-card { background: rgba(10,18,32,.85); border: 1px solid rgba(0,229,255,0.15); border-radius: 12px; padding: 20px; }
.nutr-perfil-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.nutr-perfil-avatar { font-size: 32px; }
.nutr-perfil-nome { font-family: 'Rajdhani', sans-serif; font-size: 20px; font-weight: 700; color: #00e5ff; }
.nutr-perfil-obj { font-size: 12px; color: #90a4ae; }
.nutr-perfil-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid rgba(0,229,255,0.1); }
.nutr-stat { text-align: center; }
.nutr-stat-label { font-size: 10px; color: #546e7a; display: block; text-transform: uppercase; letter-spacing: 0.5px; }
.nutr-stat-val { font-family: 'Rajdhani', sans-serif; font-size: 16px; font-weight: 700; color: #eceff1; }
.nutr-macros { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.nutr-macro { text-align: center; padding: 8px 4px; border-radius: 8px; font-family: 'Rajdhani', sans-serif; }
.nutr-macro span { display: block; font-size: 18px; font-weight: 700; }
.nutr-macro small { font-size: 10px; opacity: 0.7; }
.nutr-macro-cal { background: rgba(0,229,255,0.1); color: #00e5ff; }
.nutr-macro-prot { background: rgba(105,240,174,0.1); color: #69f0ae; }
.nutr-macro-carbo { background: rgba(255,215,64,0.1); color: #ffd740; }
.nutr-macro-gord { background: rgba(255,82,82,0.1); color: #ff5252; }

/* Cardápio */
.nutr-cardapio-area { margin-bottom: 24px; }
.nutr-status-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.nutr-semana-label { font-family: 'Rajdhani', sans-serif; font-size: 16px; color: #90a4ae; flex: 1; }
.nutr-badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.nutr-badge-revisao { background: rgba(0,229,255,0.15); color: #00e5ff; }
.nutr-badge-aprovado { background: rgba(105,240,174,0.15); color: #69f0ae; }
.nutr-badge-rascunho { background: rgba(255,215,64,0.15); color: #ffd740; }

/* Navegação de dias */
.nutr-dias-nav { display: flex; gap: 4px; margin-bottom: 16px; background: rgba(0,229,255,0.05); border: 1px solid rgba(0,229,255,0.15); border-radius: 10px; padding: 4px; }
.nutr-dia-tab { flex: 1; text-align: center; padding: 8px 4px; border-radius: 7px; cursor: pointer; font-family: 'Rajdhani', sans-serif; font-size: 13px; color: #90a4ae; border: none; background: none; transition: all 0.2s; }
.nutr-dia-tab.ativo { background: rgba(0,229,255,0.15); color: #00e5ff; font-weight: 700; }

/* Cards de refeição */
.nutr-refeicoes-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.nutr-refeicao-card { background: rgba(10,18,32,.85); border: 1px solid rgba(0,229,255,0.1); border-radius: 10px; padding: 16px; position: relative; transition: border-color 0.2s; }
.nutr-refeicao-card:hover { border-color: rgba(0,229,255,0.3); }
.nutr-ref-tipo { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #00e5ff; margin-bottom: 6px; font-family: 'Rajdhani', sans-serif; }
.nutr-ref-prato { font-size: 14px; font-weight: 600; color: #eceff1; margin-bottom: 8px; line-height: 1.4; }
.nutr-ref-pessoas { font-size: 12px; color: #90a4ae; display: flex; gap: 8px; flex-wrap: wrap; }
.nutr-ref-congelavel { position: absolute; top: 10px; right: 36px; font-size: 14px; }
.nutr-btn-editar { position: absolute; top: 8px; right: 10px; background: none; border: none; color: #546e7a; cursor: pointer; font-size: 14px; opacity: 0; transition: opacity 0.2s; }
.nutr-refeicao-card:hover .nutr-btn-editar { opacity: 1; }
.nutr-extras-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.nutr-extra-card { background: rgba(105,240,174,0.05); border: 1px solid rgba(105,240,174,0.15); border-radius: 10px; padding: 14px; }
.nutr-extra-tipo { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #69f0ae; margin-bottom: 6px; font-family: 'Rajdhani', sans-serif; }
.nutr-extra-desc { font-size: 13px; color: #eceff1; }
.nutr-extra-sub { font-size: 11px; color: #90a4ae; margin-top: 4px; }

/* Lista de compras */
.nutr-lista-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
.nutr-lista-header h3 { font-family: 'Rajdhani', sans-serif; font-size: 22px; color: #eceff1; margin: 0; }
.nutr-lista-acoes { display: flex; gap: 8px; }
.nutr-lista-cat { background: rgba(10,18,32,.85); border: 1px solid rgba(0,229,255,0.1); border-radius: 10px; padding: 16px; margin-bottom: 12px; }
.nutr-lista-cat-header { font-family: 'Rajdhani', sans-serif; font-size: 16px; color: #00e5ff; margin-bottom: 10px; }
.nutr-lista-item { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid rgba(0,229,255,0.05); font-size: 13px; color: #cfd8dc; cursor: pointer; }
.nutr-lista-item input[type="checkbox"] { cursor: pointer; width: 15px; height: 15px; accent-color: #00e5ff; }
.nutr-lista-item.marcado { opacity: 0.4; text-decoration: line-through; }
.nutr-lista-item-qtd { margin-left: auto; color: #ffd740; font-size: 12px; font-family: 'Rajdhani', sans-serif; white-space: nowrap; }

/* Loading overlay */
.nutr-loading { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px; gap: 16px; }
.nutr-loading-msg { font-family: 'Rajdhani', sans-serif; font-size: 18px; color: #00e5ff; }
.nutr-spinner { width: 40px; height: 40px; border: 3px solid rgba(0,229,255,0.2); border-top-color: #00e5ff; border-radius: 50%; animation: nutr-spin 0.8s linear infinite; }
@keyframes nutr-spin { to { transform: rotate(360deg); } }

/* Modais */
.nutr-modal { position: fixed; inset: 0; background: rgba(0,0,0,.75); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.nutr-modal-box { background: #0a1220; border: 1px solid rgba(0,229,255,0.25); border-radius: 14px; padding: 28px; width: 480px; max-width: 95vw; max-height: 85vh; overflow-y: auto; }
.nutr-modal-box h2 { font-family: 'Rajdhani', sans-serif; font-size: 22px; color: #00e5ff; margin-bottom: 20px; }
.nutr-form-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 14px; }
.nutr-modal-acoes { display: flex; gap: 10px; margin-top: 20px; justify-content: flex-end; }

/* Histórico */
.nutr-hist-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px; background: rgba(10,18,32,.85); border: 1px solid rgba(0,229,255,0.1); border-radius: 8px; margin-bottom: 8px; cursor: pointer; transition: border-color 0.2s; }
.nutr-hist-item:hover { border-color: rgba(0,229,255,0.3); }
.nutr-hist-semana { font-family: 'Rajdhani', sans-serif; font-size: 15px; color: #eceff1; flex: 1; }
.nutr-hist-data { font-size: 11px; color: #546e7a; }

.nutr-hidden { display: none !important; }
</style>
```

- [ ] **Step 3: Adicionar a `<section>` da página Nutrição**

Encontre onde termina a última `<section class="page">` e adicione:

```html
<!-- ========== NUTRIÇÃO ========== -->
<section class="page" id="page-nutricao">
  <div class="nutr-page">

    <!-- Header -->
    <div class="nutr-header">
      <h2>🥗 Nutri<span>ção</span></h2>
      <button class="btn-neon" onclick="nutricaoGerarCardapio()" id="nutr-btn-gerar">
        ✨ Gerar Cardápio da Semana
      </button>
    </div>

    <!-- Cards de perfil -->
    <div class="nutr-perfis-grid" id="nutr-perfis-grid">
      <!-- Injetado por nutricao.js -->
    </div>

    <!-- Área do cardápio (aparece após gerar) -->
    <div id="nutr-cardapio-area" class="nutr-hidden">
      <div class="nutr-status-bar">
        <span class="nutr-semana-label" id="nutr-semana-label">—</span>
        <span id="nutr-status-badge" class="nutr-badge nutr-badge-revisao">Revisão</span>
        <button class="btn-outline btn-sm" onclick="nutricaoGerarCardapio()" style="font-size:12px;">🔄 Gerar novo</button>
        <button class="btn-neon btn-sm" onclick="nutricaoAprovarCardapio()" id="nutr-btn-aprovar" style="font-size:12px;">✅ Aprovar cardápio</button>
      </div>

      <!-- Navegação por dia -->
      <div class="nutr-dias-nav" id="nutr-dias-nav">
        <!-- Injetado por nutricao.js -->
      </div>

      <!-- Conteúdo do dia selecionado -->
      <div id="nutr-dia-content">
        <!-- Injetado por nutricao.js -->
      </div>
    </div>

    <!-- Lista de compras (aparece após aprovar) -->
    <div id="nutr-lista-area" class="nutr-hidden">
      <div class="nutr-lista-header">
        <h3>🛒 Lista de Compras</h3>
        <div class="nutr-lista-acoes">
          <button class="btn-neon" onclick="nutricaoCopiarWhatsapp()">📱 Enviar pro WhatsApp</button>
          <button class="btn-outline" onclick="nutricaoBaixarPDF()">📄 Baixar PDF</button>
        </div>
      </div>
      <div id="nutr-lista-container">
        <!-- Injetado por nutricao.js -->
      </div>
    </div>

    <!-- Histórico -->
    <div id="nutr-historico-area" style="margin-top:24px;">
      <div style="font-family:'Rajdhani',sans-serif;font-size:14px;color:#546e7a;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">Cardápios Anteriores</div>
      <div id="nutr-historico-lista"></div>
    </div>

  </div>

  <!-- Modal Perfil -->
  <div id="nutr-modal-perfil" class="nutr-modal nutr-hidden">
    <div class="nutr-modal-box">
      <h2 id="nutr-modal-perfil-titulo">Editar Perfil</h2>
      <div class="nutr-form-row">
        <div>
          <label class="config-label">Idade</label>
          <input type="number" id="nutr-perf-idade" class="input-dark" placeholder="anos">
        </div>
        <div>
          <label class="config-label">Peso (kg)</label>
          <input type="number" id="nutr-perf-peso" class="input-dark" step="0.1" placeholder="ex: 80.5">
        </div>
        <div>
          <label class="config-label">Altura (cm)</label>
          <input type="number" id="nutr-perf-altura" class="input-dark" placeholder="ex: 178">
        </div>
      </div>
      <label class="config-label">Objetivo</label>
      <select id="nutr-perf-objetivo" class="input-dark" style="width:100%;margin-bottom:12px;">
        <option value="hipertrofia">💪 Hipertrofia / Ganho de massa</option>
        <option value="emagrecimento">🔥 Emagrecimento</option>
        <option value="manutencao">⚖️ Manutenção</option>
      </select>
      <label class="config-label">Nível de atividade</label>
      <select id="nutr-perf-atividade" class="input-dark" style="width:100%;margin-bottom:12px;">
        <option value="sedentario">😴 Sedentário</option>
        <option value="moderado">🚶 Moderado (3-5x/semana)</option>
        <option value="intenso">🏋️ Intenso (6-7x/semana)</option>
      </select>
      <label class="config-label">Alimentos que gosta (opcional)</label>
      <textarea id="nutr-perf-preferencias" class="input-dark" rows="2" style="width:100%;box-sizing:border-box;" placeholder="Ex: frango, batata doce, ovos..."></textarea>
      <div class="nutr-modal-acoes">
        <button class="btn-outline" onclick="nutricaoFecharModal('nutr-modal-perfil')">Cancelar</button>
        <button class="btn-neon" onclick="nutricaoSalvarPerfil()">Salvar e Recalcular</button>
      </div>
    </div>
  </div>

  <!-- Modal Editar Refeição -->
  <div id="nutr-modal-refeicao" class="nutr-modal nutr-hidden">
    <div class="nutr-modal-box">
      <h2 id="nutr-modal-ref-titulo">Editar Refeição</h2>
      <p style="color:#90a4ae;font-size:13px;margin-bottom:12px;">Descreva o que quer nessa refeição — será atualizado no cardápio.</p>
      <textarea id="nutr-modal-ref-input" class="input-dark" rows="5" style="width:100%;box-sizing:border-box;" placeholder="Ex: trocar o almoço por frango grelhado com arroz integral e brócolis"></textarea>
      <div class="nutr-modal-acoes">
        <button class="btn-outline" onclick="nutricaoFecharModal('nutr-modal-refeicao')">Cancelar</button>
        <button class="btn-neon" onclick="nutricaoSalvarEdicaoRefeicao()">Atualizar</button>
      </div>
    </div>
  </div>

</section>
```

- [ ] **Step 4: Incluir o script nutricao.js no final do dashboard.html**

Encontre onde os outros scripts são incluídos (próximo ao `</body>`) e adicione:

```html
<script src="{{ url_for('static', filename='js/nutricao.js') }}"></script>
```

- [ ] **Step 5: Commit**

```bash
git add jake_desktop/templates/dashboard.html
git commit -m "feat: nutricao — nav item, section HTML e CSS no dashboard.html"
```

---

## Task 7: Frontend JS — nutricao.js (Estado, Perfis, Geração)

**Files:**
- Create: `jake_desktop/static/js/nutricao.js`

- [ ] **Step 1: Criar nutricao.js com estado, init e perfis**

```javascript
// jake_desktop/static/js/nutricao.js
(function () {
  'use strict';

  var NState = {
    perfis: [],
    cardapioAtual: null,
    cardapioId: null,
    status: null,
    diaSelecionado: 0,
    gerando: false,
    editandoDia: null,
    editandoRefeicao: null,
    perfilEditandoId: null,
  };

  var DIAS_CURTOS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // ── INIT ────────────────────────────────────────────────────────────────────
  window.initNutricao = function () {
    carregarPerfis();
    carregarUltimoCardapio();
  };

  // ── PERFIS ──────────────────────────────────────────────────────────────────
  function carregarPerfis() {
    fetch('/api/nutricao/perfis')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        NState.perfis = data.perfis || [];
        renderPerfis();
      })
      .catch(function (e) { console.error('Erro perfis:', e); });
  }

  function renderPerfis() {
    var grid = document.getElementById('nutr-perfis-grid');
    if (!grid) return;
    grid.innerHTML = NState.perfis.map(function (p) {
      var avatar = p.nome === 'Bruno' ? '👨' : '👩';
      var imc = p.imc ? p.imc.toFixed(1) : '—';
      var tmb = p.tmb ? Math.round(p.tmb) : '—';
      var getVal = p.get ? Math.round(p.get) : '—';
      var peso = p.peso ? p.peso + 'kg' : '—';
      var altura = p.altura ? p.altura + 'cm' : '—';
      var kcal = p.meta_calorica || '—';
      var prot = p.meta_proteina ? p.meta_proteina + 'g' : '—';
      var carbo = p.meta_carbo ? p.meta_carbo + 'g' : '—';
      var gord = p.meta_gordura ? p.meta_gordura + 'g' : '—';
      var obj = p.objetivo === 'hipertrofia' ? '💪 Hipertrofia' :
               p.objetivo === 'emagrecimento' ? '🔥 Emagrecimento' : '⚖️ Manutenção';
      return '<div class="nutr-perfil-card">' +
        '<div class="nutr-perfil-header">' +
          '<span class="nutr-perfil-avatar">' + avatar + '</span>' +
          '<div style="flex:1">' +
            '<div class="nutr-perfil-nome">' + esc(p.nome) + '</div>' +
            '<div class="nutr-perfil-obj">' + obj + '</div>' +
          '</div>' +
          '<button class="btn-mini" onclick="nutricaoAbrirModalPerfil(' + p.id + ')">✏️</button>' +
        '</div>' +
        '<div class="nutr-perfil-stats">' +
          '<div class="nutr-stat"><span class="nutr-stat-label">Peso</span><span class="nutr-stat-val">' + peso + '</span></div>' +
          '<div class="nutr-stat"><span class="nutr-stat-label">Altura</span><span class="nutr-stat-val">' + altura + '</span></div>' +
          '<div class="nutr-stat"><span class="nutr-stat-label">IMC</span><span class="nutr-stat-val">' + imc + '</span></div>' +
          '<div class="nutr-stat"><span class="nutr-stat-label">TMB</span><span class="nutr-stat-val">' + tmb + '</span></div>' +
        '</div>' +
        '<div class="nutr-macros">' +
          '<div class="nutr-macro nutr-macro-cal"><span>' + kcal + '</span><small>kcal/dia</small></div>' +
          '<div class="nutr-macro nutr-macro-prot"><span>' + prot + '</span><small>proteína</small></div>' +
          '<div class="nutr-macro nutr-macro-carbo"><span>' + carbo + '</span><small>carbo</small></div>' +
          '<div class="nutr-macro nutr-macro-gord"><span>' + gord + '</span><small>gordura</small></div>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  // ── MODAL PERFIL ────────────────────────────────────────────────────────────
  window.nutricaoAbrirModalPerfil = function (id) {
    NState.perfilEditandoId = id;
    var p = NState.perfis.find(function (x) { return x.id === id; }) || {};
    var titulo = document.getElementById('nutr-modal-perfil-titulo');
    if (titulo) titulo.textContent = 'Editar Perfil — ' + (p.nome || '');

    document.getElementById('nutr-perf-idade').value = p.idade || '';
    document.getElementById('nutr-perf-peso').value = p.peso || '';
    document.getElementById('nutr-perf-altura').value = p.altura || '';
    document.getElementById('nutr-perf-objetivo').value = p.objetivo || 'hipertrofia';
    document.getElementById('nutr-perf-atividade').value = p.nivel_atividade || 'intenso';
    document.getElementById('nutr-perf-preferencias').value = p.preferencias || '';

    document.getElementById('nutr-modal-perfil').classList.remove('nutr-hidden');
  };

  window.nutricaoSalvarPerfil = function () {
    var id = NState.perfilEditandoId;
    if (!id) return;
    var payload = {
      idade: parseInt(document.getElementById('nutr-perf-idade').value) || null,
      peso: parseFloat(document.getElementById('nutr-perf-peso').value) || null,
      altura: parseInt(document.getElementById('nutr-perf-altura').value) || null,
      objetivo: document.getElementById('nutr-perf-objetivo').value,
      nivel_atividade: document.getElementById('nutr-perf-atividade').value,
      preferencias: document.getElementById('nutr-perf-preferencias').value,
    };
    fetch('/api/nutricao/perfis/' + id, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.ok || data.calorias) {
        nutricaoFecharModal('nutr-modal-perfil');
        carregarPerfis();
      } else {
        alert('Erro: ' + (data.error || 'desconhecido'));
      }
    });
  };

  window.nutricaoFecharModal = function (modalId) {
    var modal = document.getElementById(modalId);
    if (modal) modal.classList.add('nutr-hidden');
  };

  // ── GERAR CARDÁPIO ──────────────────────────────────────────────────────────
  window.nutricaoGerarCardapio = function () {
    if (NState.gerando) return;
    NState.gerando = true;

    var area = document.getElementById('nutr-cardapio-area');
    var listaArea = document.getElementById('nutr-lista-area');
    if (area) area.classList.add('nutr-hidden');
    if (listaArea) listaArea.classList.add('nutr-hidden');

    // Mostrar loading na área do cardápio
    var histArea = document.getElementById('nutr-historico-area');
    if (histArea) histArea.innerHTML = '<div class="nutr-loading">' +
      '<div class="nutr-spinner"></div>' +
      '<div class="nutr-loading-msg" id="nutr-loading-msg">Calculando macros...</div>' +
    '</div>';

    var mensagens = [
      'Calculando macros...',
      'Consultando alimentos favoritos...',
      'Claude está criando seu cardápio...',
      'Montando as refeições da semana...',
      'Quase pronto...',
    ];
    var msgIdx = 0;
    var msgInterval = setInterval(function () {
      msgIdx = (msgIdx + 1) % mensagens.length;
      var el = document.getElementById('nutr-loading-msg');
      if (el) el.textContent = mensagens[msgIdx];
    }, 2500);

    fetch('/api/nutricao/gerar-cardapio', {method: 'POST'})
      .then(function (r) { return r.json(); })
      .then(function (data) {
        clearInterval(msgInterval);
        NState.gerando = false;
        if (data.error) {
          alert('Erro ao gerar cardápio: ' + data.error);
          if (histArea) histArea.innerHTML = '';
          return;
        }
        NState.cardapioAtual = data.cardapio;
        NState.cardapioId = data.id;
        NState.status = 'revisao';
        NState.diaSelecionado = 0;
        if (histArea) histArea.innerHTML = '';
        renderCardapio();
        carregarHistorico();
      })
      .catch(function (e) {
        clearInterval(msgInterval);
        NState.gerando = false;
        alert('Erro de conexão: ' + e.message);
        if (histArea) histArea.innerHTML = '';
      });
  };
})();
```

- [ ] **Step 2: Commit parcial**

```bash
git add jake_desktop/static/js/nutricao.js
git commit -m "feat: nutricao.js — estado, init, perfis, modal perfil, gerar cardápio"
```

---

## Task 8: Frontend JS — Renderização do Cardápio e Lista de Compras

**Files:**
- Modify: `jake_desktop/static/js/nutricao.js` — adicionar funções de render (dentro do IIFE)

- [ ] **Step 1: Adicionar funções de renderização do cardápio**

Dentro do IIFE do `nutricao.js`, antes do último `})();`, adicione:

```javascript
  // ── RENDER CARDÁPIO ─────────────────────────────────────────────────────────
  function renderCardapio() {
    var cardapio = NState.cardapioAtual;
    if (!cardapio) return;

    var area = document.getElementById('nutr-cardapio-area');
    if (area) area.classList.remove('nutr-hidden');

    // Semana label
    var semLabel = document.getElementById('nutr-semana-label');
    if (semLabel) semLabel.textContent = 'Semana ' + (cardapio.semana || '—');

    // Status badge
    var badge = document.getElementById('nutr-status-badge');
    if (badge) {
      badge.textContent = NState.status === 'aprovado' ? 'Aprovado' :
                          NState.status === 'revisao' ? 'Em Revisão' : 'Rascunho';
      badge.className = 'nutr-badge nutr-badge-' + (NState.status || 'rascunho');
    }

    // Botão aprovar — esconder se já aprovado
    var btnAprovar = document.getElementById('nutr-btn-aprovar');
    if (btnAprovar) btnAprovar.style.display = NState.status === 'aprovado' ? 'none' : '';

    // Nav de dias
    renderDiasNav();
    renderDia(NState.diaSelecionado);
  }

  function renderDiasNav() {
    var nav = document.getElementById('nutr-dias-nav');
    if (!nav || !NState.cardapioAtual) return;
    var dias = NState.cardapioAtual.dias || [];
    nav.innerHTML = dias.map(function (d, i) {
      var nome = d.dia || DIAS_CURTOS[i] || ('Dia ' + (i + 1));
      var curto = nome.substring(0, 3);
      return '<button class="nutr-dia-tab' + (i === NState.diaSelecionado ? ' ativo' : '') +
        '" onclick="nutricaoSelecionarDia(' + i + ')">' + esc(curto) + '</button>';
    }).join('');
  }

  window.nutricaoSelecionarDia = function (idx) {
    NState.diaSelecionado = idx;
    renderDiasNav();
    renderDia(idx);
  };

  function renderDia(idx) {
    var content = document.getElementById('nutr-dia-content');
    if (!content || !NState.cardapioAtual) return;
    var dia = (NState.cardapioAtual.dias || [])[idx];
    if (!dia) { content.innerHTML = ''; return; }

    var r = dia.refeicoes || {};

    function cardRefeicao(tipo, label, emoji) {
      var ref = r[tipo] || {};
      var congelavel = ref.congelavel ? '<span class="nutr-ref-congelavel" title="Pode congelar">🧊</span>' : '';
      var prato = '';
      if (tipo === 'almoco' || tipo === 'janta') {
        var partes = [ref.prato_principal, ref.acompanhamento, ref.verdura].filter(Boolean);
        prato = partes.join(' · ') || '—';
      } else {
        prato = ref.descricao || '—';
      }
      var brunoInfo = '';
      var camilaInfo = '';
      if (ref.bruno) {
        brunoInfo = '<span>👨 ' + esc(ref.bruno.porcao || '') + (ref.bruno.calorias ? ' · ' + ref.bruno.calorias + ' kcal' : '') + '</span>';
      }
      if (ref.camila) {
        camilaInfo = '<span>👩 ' + esc(ref.camila.porcao || '') + (ref.camila.calorias ? ' · ' + ref.camila.calorias + ' kcal' : '') + '</span>';
      }
      var tempo = (tipo === 'almoco' || tipo === 'janta') && ref.tempo_preparo ?
        '<span style="font-size:11px;color:#546e7a">⏱ ' + esc(ref.tempo_preparo) + '</span>' : '';
      var btnEditar = '<button class="nutr-btn-editar" onclick="nutricaoAbrirModalRefeicao(\'' + dia.dia + '\',\'' + tipo + '\')">✏️</button>';

      return '<div class="nutr-refeicao-card">' +
        congelavel +
        btnEditar +
        '<div class="nutr-ref-tipo">' + emoji + ' ' + label + '</div>' +
        '<div class="nutr-ref-prato">' + esc(prato) + '</div>' +
        tempo +
        '<div class="nutr-ref-pessoas">' + brunoInfo + camilaInfo + '</div>' +
      '</div>';
    }

    var suco = r.suco_dia || {};
    var fruta = r.fruta_dia || '';
    var sucoDesc = suco.nome ? esc(suco.nome) + (suco.beneficio ? ' · <small>' + esc(suco.beneficio) + '</small>' : '') : '—';
    var ingredientesStr = (suco.ingredientes || []).join(', ');

    content.innerHTML =
      '<div class="nutr-refeicoes-grid">' +
        cardRefeicao('cafe_manha', 'Café da Manhã', '☀️') +
        cardRefeicao('almoco', 'Almoço', '🍽') +
        cardRefeicao('cafe_tarde', 'Café da Tarde', '🫖') +
        cardRefeicao('janta', 'Janta', '🌙') +
      '</div>' +
      '<div class="nutr-extras-grid">' +
        '<div class="nutr-extra-card">' +
          '<div class="nutr-extra-tipo">🥤 Suco do Dia</div>' +
          '<div class="nutr-extra-desc">' + sucoDesc + '</div>' +
          (ingredientesStr ? '<div class="nutr-extra-sub">' + esc(ingredientesStr) + '</div>' : '') +
        '</div>' +
        '<div class="nutr-extra-card">' +
          '<div class="nutr-extra-tipo">🍎 Fruta do Dia</div>' +
          '<div class="nutr-extra-desc">' + esc(fruta || '—') + '</div>' +
        '</div>' +
      '</div>';
  }

  // ── APROVAR CARDÁPIO ─────────────────────────────────────────────────────────
  window.nutricaoAprovarCardapio = function () {
    if (!NState.cardapioId) return;
    if (!confirm('Aprovar este cardápio e gerar a lista de compras?')) return;

    fetch('/api/nutricao/cardapios/' + NState.cardapioId + '/aprovar', {method: 'PATCH'})
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { alert('Erro: ' + (data.error || '?')); return; }
        NState.status = 'aprovado';
        renderCardapio();
        // Gerar lista de compras
        return fetch('/api/nutricao/lista-compras/' + NState.cardapioId, {method: 'POST'});
      })
      .then(function (r) { if (r) return r.json(); })
      .then(function (data) {
        if (data && data.lista) {
          renderListaCompras(data.lista);
        }
      })
      .catch(function (e) { alert('Erro: ' + e.message); });
  };

  // ── EDITAR REFEIÇÃO ──────────────────────────────────────────────────────────
  window.nutricaoAbrirModalRefeicao = function (dia, tipo) {
    NState.editandoDia = dia;
    NState.editandoRefeicao = tipo;
    var labels = {cafe_manha: 'Café da Manhã', almoco: 'Almoço', cafe_tarde: 'Café da Tarde', janta: 'Janta'};
    var titulo = document.getElementById('nutr-modal-ref-titulo');
    if (titulo) titulo.textContent = 'Editar ' + (labels[tipo] || tipo) + ' — ' + dia;
    document.getElementById('nutr-modal-ref-input').value = '';
    document.getElementById('nutr-modal-refeicao').classList.remove('nutr-hidden');
  };

  window.nutricaoSalvarEdicaoRefeicao = function () {
    var input = document.getElementById('nutr-modal-ref-input').value.trim();
    if (!input) return;
    if (!NState.cardapioId) return;

    // Monta novo conteúdo simples com a descrição do usuário
    var novoConteudo = {descricao: input};

    fetch('/api/nutricao/cardapios/' + NState.cardapioId + '/editar-refeicao', {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        dia: NState.editandoDia,
        refeicao: NState.editandoRefeicao,
        novo_conteudo: novoConteudo,
      }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.ok && data.cardapio) {
        NState.cardapioAtual = data.cardapio;
        nutricaoFecharModal('nutr-modal-refeicao');
        renderDia(NState.diaSelecionado);
      }
    });
  };

  // ── LISTA DE COMPRAS ─────────────────────────────────────────────────────────
  function renderListaCompras(lista) {
    var area = document.getElementById('nutr-lista-area');
    var container = document.getElementById('nutr-lista-container');
    if (!area || !container) return;
    area.classList.remove('nutr-hidden');

    if (lista.dica) {
      container.innerHTML = '<p style="color:#90a4ae;font-size:13px;margin-bottom:12px;">💡 ' + esc(lista.dica) + '</p>';
    } else {
      container.innerHTML = '';
    }

    (lista.categorias || []).forEach(function (cat) {
      if (!cat.itens || !cat.itens.length) return;
      var itensHtml = cat.itens.map(function (item) {
        var obs = item.observacao ? ' <span style="color:#546e7a;font-size:11px;">(' + esc(item.observacao) + ')</span>' : '';
        return '<div class="nutr-lista-item" onclick="this.classList.toggle(\'marcado\')">' +
          '<input type="checkbox" onclick="event.stopPropagation();this.closest(\'.nutr-lista-item\').classList.toggle(\'marcado\')">' +
          '<span>' + esc(item.item) + obs + '</span>' +
          '<span class="nutr-lista-item-qtd">' + esc(item.quantidade || '') + '</span>' +
        '</div>';
      }).join('');
      container.innerHTML += '<div class="nutr-lista-cat">' +
        '<div class="nutr-lista-cat-header">' + (cat.emoji || '') + ' ' + esc(cat.nome) + '</div>' +
        itensHtml +
      '</div>';
    });
  }

  // ── EXPORTAR WHATSAPP ────────────────────────────────────────────────────────
  window.nutricaoCopiarWhatsapp = function () {
    if (!NState.cardapioId) return;
    fetch('/api/nutricao/exportar-whatsapp/' + NState.cardapioId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.sucesso || !data.texto) {
          alert('Erro ao gerar texto: ' + (data.error || '?'));
          return;
        }
        if (navigator.clipboard) {
          navigator.clipboard.writeText(data.texto).then(function () {
            alert('Lista copiada! Abrindo WhatsApp Web...');
            window.open('https://wa.me/?text=' + encodeURIComponent(data.texto), '_blank');
          });
        } else {
          window.open('https://wa.me/?text=' + encodeURIComponent(data.texto), '_blank');
        }
      });
  };

  // ── EXPORTAR PDF ─────────────────────────────────────────────────────────────
  window.nutricaoBaixarPDF = function () {
    if (!NState.cardapioId) return;
    window.open('/api/nutricao/exportar-pdf/' + NState.cardapioId, '_blank');
  };

  // ── HISTÓRICO ────────────────────────────────────────────────────────────────
  function carregarHistorico() {
    fetch('/api/nutricao/cardapios')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderHistorico(data.cardapios || []);
      });
  }

  function carregarUltimoCardapio() {
    fetch('/api/nutricao/cardapios')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var lista = data.cardapios || [];
        renderHistorico(lista);
        if (lista.length > 0 && !NState.cardapioAtual) {
          // Carregar o mais recente
          var ultimo = lista[0];
          carregarCardapioById(ultimo.id);
        }
      });
  }

  function carregarCardapioById(id) {
    fetch('/api/nutricao/cardapios/' + id)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.cardapio_json) {
          NState.cardapioAtual = data.cardapio_json;
          NState.cardapioId = data.id;
          NState.status = data.status;
          NState.diaSelecionado = 0;
          renderCardapio();
          if (data.status === 'aprovado' && data.lista_compras_json) {
            renderListaCompras(data.lista_compras_json);
          }
        }
      });
  }

  function renderHistorico(lista) {
    var el = document.getElementById('nutr-historico-lista');
    if (!el) return;
    if (!lista.length) { el.innerHTML = '<p style="color:#546e7a;font-size:13px;">Nenhum cardápio anterior.</p>'; return; }
    el.innerHTML = lista.slice(0, 5).map(function (c) {
      var statusBadge = '<span class="nutr-badge nutr-badge-' + esc(c.status) + '" style="font-size:10px;">' +
        (c.status === 'aprovado' ? 'Aprovado' : c.status === 'revisao' ? 'Em Revisão' : 'Rascunho') + '</span>';
      var data = c.criado_em ? new Date(c.criado_em).toLocaleDateString('pt-BR') : '—';
      return '<div class="nutr-hist-item" onclick="nutricaoCarregarCardapio(' + c.id + ')">' +
        '<span class="nutr-hist-semana">Semana ' + esc(c.semana_inicio || '—') + ' a ' + esc(c.semana_fim || '—') + '</span>' +
        statusBadge +
        '<span class="nutr-hist-data">' + data + '</span>' +
      '</div>';
    }).join('');
  }

  window.nutricaoCarregarCardapio = function (id) {
    carregarCardapioById(id);
  };
```

- [ ] **Step 2: Commit**

```bash
git add jake_desktop/static/js/nutricao.js
git commit -m "feat: nutricao.js — render cardápio, dias, aprovar, lista compras, WhatsApp, PDF, histórico"
```

---

## Task 9: Atualizar app.js — Routing e initNutricao

**Files:**
- Modify: `jake_desktop/static/js/app.js`

- [ ] **Step 1: Ler app.js atual**

```bash
cat /root/jake_desktop/static/js/app.js
```

- [ ] **Step 2: Adicionar 'nutricao' à lista valid e chamar initNutricao**

Editar o array `valid` para incluir `"nutricao"`:

```javascript
var valid = ["painel","architect","performance","anuncios","copys","criativos","relatorios","carrossel","prompts","financeiro","agenda","rotina","social-brief","nutricao"];
```

Editar a função `showPage` para chamar `initNutricao()` quando a página nutrição for acessada:

```javascript
function showPage(id) {
  document.querySelectorAll(".page").forEach(function (p) {
    p.classList.toggle("active", p.id === "page-" + id);
  });
  document.querySelectorAll(".nav-item").forEach(function (n) {
    n.classList.toggle("active", n.dataset.page === id);
  });
  history.replaceState(null, "", "#" + id);
  // Inicializar módulos quando a página é acessada
  if (id === "nutricao" && typeof window.initNutricao === "function") {
    window.initNutricao();
  }
  if (id === "social-brief" && typeof window.initSocialBrief === "function") {
    window.initSocialBrief();
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add jake_desktop/static/js/app.js
git commit -m "feat: app.js — adicionar nutricao ao router SPA"
```

---

## Task 10: Teste End-to-End e Restart

- [ ] **Step 1: Reiniciar Jake OS**

```bash
pkill -f "jake_desktop" 2>/dev/null || true
sleep 1
cd /root && nohup /root/venv/bin/python3 jake_desktop/app.py >> /root/logs/jake_desktop.log 2>&1 &
sleep 2
```

- [ ] **Step 2: Verificar se subiu sem erros**

```bash
tail -20 /root/logs/jake_desktop.log
```

- [ ] **Step 3: Verificar tabelas criadas no banco**

```bash
/root/venv/bin/python3 -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv('/root/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute(\"SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'nutricao%'\")
print([r[0] for r in cur.fetchall()])
conn.close()
"
```

Esperado: `['nutricao_perfis', 'nutricao_cardapios', 'nutricao_alimentos_base']`

- [ ] **Step 4: Verificar perfis iniciais**

```bash
/root/venv/bin/python3 -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv('/root/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute('SELECT nome, objetivo, nivel_atividade FROM nutricao_perfis')
print(cur.fetchall())
conn.close()
"
```

Esperado: `[('Bruno', 'hipertrofia', 'intenso'), ('Camila', 'hipertrofia', 'intenso')]`

- [ ] **Step 5: Testar navegação no browser**

Abrir `http://localhost:5050/#nutricao` e verificar:
- Cards de Bruno e Camila aparecem (com "—" nos dados se não preenchidos ainda)
- Nav item "🥗 Nutrição" aparece no sidebar e fica ativo
- Modal de editar perfil abre ao clicar ✏️

- [ ] **Step 6: Testar fluxo completo**

1. Editar perfil de Bruno: peso 85kg, altura 178cm, idade 28 → Salvar
2. Verificar que TMB/GET/macros foram calculados e aparecem no card
3. Clicar "✨ Gerar Cardápio da Semana" → aguardar loading
4. Verificar que cardápio aparece com 7 abas de dias
5. Navegar entre os dias
6. Clicar ✏️ em uma refeição → editar → Atualizar
7. Clicar "✅ Aprovar cardápio"
8. Verificar que lista de compras aparece com checkboxes
9. Clicar "📱 Enviar pro WhatsApp" → verificar que copia texto e abre wa.me
10. Clicar "📄 Baixar PDF" → verificar que abre HTML em nova aba

- [ ] **Step 7: Commit final**

```bash
git add -A
git commit -m "feat: seção Nutrição completa — cardápio semanal, perfis, Claude, lista de compras, PDF, WhatsApp"
```

---

## Checklist Final

- [ ] Tabelas `nutricao_perfis`, `nutricao_cardapios`, `nutricao_alimentos_base` criadas no Neon
- [ ] Perfis Bruno e Camila inseridos com objetivo hipertrofia + atividade intensa
- [ ] 17 alimentos base favoritos inseridos
- [ ] Cálculos TMB/GET/macros (Mifflin-St Jeor + superávit 400kcal) funcionando
- [ ] Modal de perfil salva e recalcula macros automaticamente
- [ ] Nav item "🥗 Nutrição" no sidebar
- [ ] Hash `#nutricao` roteado em `app.js`
- [ ] `initNutricao()` chamado ao navegar para a seção
- [ ] Geração do cardápio retorna JSON válido do Claude
- [ ] Loading animado com mensagens durante geração
- [ ] Navegação por dia (7 abas) funcionando
- [ ] Ícone 🧊 em refeições que podem ser congeladas
- [ ] Edição de refeição individual via modal
- [ ] Botão aprovar muda status e gera lista de compras automaticamente
- [ ] Checkboxes na lista de compras funcionam localmente
- [ ] Exportação para WhatsApp copia texto formatado e abre wa.me
- [ ] Exportação PDF gera HTML otimizado para impressão
- [ ] Histórico de cardápios anteriores carrega ao abrir a seção
- [ ] Jake OS reiniciado após implementação
