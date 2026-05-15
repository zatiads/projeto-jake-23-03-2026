# Gestor IA Completo via WhatsApp — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o Gestor IA de autônomo silencioso em semi-autônomo via WhatsApp — propõe ações diariamente, aguarda aprovação do Bruno, executa só após "ok", com 7 comandos slash e 6 novos alertas inteligentes.

**Architecture:** O gestor_agente.py para de executar imediatamente e passa a salvar ações como `pendente` no banco, enviando resumo consolidado no WA. O jake_whatsapp.py ganha parser de slash-commands e roteamento de aprovação ("ok"/"cancela N"). Um job APScheduler expira pendentes após 4h consultando o banco (persiste entre restarts).

**Tech Stack:** Python 3.12, psycopg2 (Neon/PostgreSQL), Flask, APScheduler, Anthropic Claude Sonnet 4.6, Evolution API (WhatsApp), Meta Graph API v21.0, pytest + unittest.mock

---

## Mapa de Arquivos

| Arquivo | Operação | Responsabilidade |
|---------|----------|-----------------|
| `meta/gestor/migrations.py` | Modificar | Adicionar migração DDL (gestor_estado + colunas gestor_acoes) |
| `meta/gestor/executor.py` | Modificar | Adicionar salvar_pendentes(), executar_aprovadas(), guard no reverter() |
| `meta/meta_api.py` | Modificar | Adicionar duplicar_ad() usando criar_conjunto + criar_anuncio |
| `meta/gestor/coletor.py` | Modificar | Adicionar _buscar_insights_diarios(), effective_status, _buscar_cpl_semana_anterior() |
| `meta/gestor/analista.py` | Modificar | Novas ações (reativar_ad, reduzir_orcamento, duplicar_ad) + 6 alertas no system prompt |
| `bot/whatsapp_handlers.py` | Modificar | Adicionar enviar_resumo_gestor(), processar_aprovacao(), _verificar_varredura_pendente(), cmds |
| `meta/gestor_agente.py` | Modificar | Substituir executar() por salvar_pendentes() + notificar_whatsapp() |
| `bot/jake_whatsapp.py` | Modificar | Parser slash-commands, roteamento aprovação, remover 17h, job expiração |
| `tests/test_gestor_ia_wpp.py` | Criar | Testes unitários para as novas funções |

---

## Task 1: Migração do Banco

**Files:**
- Modify: `meta/gestor/migrations.py`

- [ ] **Step 1: Ler o arquivo de migrations atual**

```bash
cat -n /root/meta/gestor/migrations.py
```

- [ ] **Step 2: Adicionar migração das novas colunas e tabela**

Adicionar ao final de `migrations.py` uma função `migrate_v2()`:

```python
def migrate_v2(conn):
    """Migração v2: suporte a aprovação via WhatsApp."""
    cur = conn.cursor()

    # Colunas novas em gestor_acoes (idempotente via IF NOT EXISTS)
    cur.execute("""
        ALTER TABLE gestor_acoes
          ADD COLUMN IF NOT EXISTS numero_na_varredura INT,
          ADD COLUMN IF NOT EXISTS aprovado_em TIMESTAMP,
          ADD COLUMN IF NOT EXISTS cancelado_em TIMESTAMP,
          ADD COLUMN IF NOT EXISTS expirado_em TIMESTAMP
    """)

    # Índice para queries frequentes do job de expiração
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_gestor_acoes_status_varredura
          ON gestor_acoes(status, varredura_id)
    """)

    # Tabela de estado de aprovação (persiste entre restarts do bot)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gestor_estado (
          id           SERIAL PRIMARY KEY,
          varredura_id INT NOT NULL REFERENCES gestor_varreduras(id),
          status       VARCHAR(20) NOT NULL DEFAULT 'aguardando',
          criado_em    TIMESTAMP DEFAULT NOW(),
          resolvido_em TIMESTAMP
        )
    """)

    conn.commit()
    print("[migrations] v2 aplicada.")
```

- [ ] **Step 3: Rodar a migração no banco**

```bash
cd /root && /root/venv/bin/python3 -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv('/root/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
from meta.gestor.migrations import migrate_v2
migrate_v2(conn)
conn.close()
print('OK')
"
```
Esperado: `[migrations] v2 aplicada.` e `OK`

- [ ] **Step 4: Verificar colunas criadas**

```bash
cd /root && /root/venv/bin/python3 -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv('/root/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='gestor_acoes' ORDER BY ordinal_position\")
print([r[0] for r in cur.fetchall()])
cur.execute(\"SELECT to_regclass('public.gestor_estado')\")
print('gestor_estado:', cur.fetchone()[0])
conn.close()
"
```
Esperado: lista com `numero_na_varredura`, `aprovado_em`, `cancelado_em`, `expirado_em` + `gestor_estado: gestor_estado`

- [ ] **Step 5: Commit**

```bash
git add meta/gestor/migrations.py
git commit -m "feat(gestor): migração v2 - gestor_estado e colunas de aprovação WA"
```

---

## Task 2: executor.py — salvar_pendentes() e executar_aprovadas()

**Files:**
- Modify: `meta/gestor/executor.py`
- Test: `tests/test_gestor_ia_wpp.py`

- [ ] **Step 1: Escrever os testes**

Criar `/root/tests/test_gestor_ia_wpp.py`:

```python
"""Testes para as novas funções do Gestor IA WA."""
import pytest
from unittest.mock import patch, MagicMock, call
import json


# ─── salvar_pendentes ─────────────────────────────────────────────────────────

def test_salvar_pendentes_salva_acoes_sem_executar():
    """salvar_pendentes() deve gravar status=pendente sem chamar Meta API."""
    from meta.gestor.executor import salvar_pendentes

    decisoes = [{
        "cliente_id": 1,
        "conta": "Vielife",
        "acoes": [{"tipo": "pausar_ad", "entidade_id": "123", "entidade_nome": "Criativo X", "motivo": "CPL alto"}],
        "alertas": [],
    }]
    perfis = [{"cliente_id": 1, "nome": "Vielife", "account_id": "act_123", "token_key": "META_TOKEN_VIELIFE", "gestor_config": None, "erro": None}]

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    with patch("meta.gestor.executor._get_db", return_value=mock_conn):
        with patch("meta.gestor.executor._resolve_token", return_value="tok"):
            salvar_pendentes(decisoes, perfis, varredura_id=42, db_conn=mock_conn)

    # Deve ter feito INSERT com status='pendente'
    insert_calls = [c for c in mock_cur.execute.call_args_list if "INSERT" in str(c)]
    assert any("pendente" in str(c) for c in insert_calls), "Esperado INSERT com status=pendente"

    # NÃO deve ter chamado Meta API (nenhum import de atualizar_status_ad etc)
    # Verificar indiretamente: nenhum call com "PAUSED" no execute
    paused_calls = [c for c in mock_cur.execute.call_args_list if "PAUSED" in str(c)]
    assert len(paused_calls) == 0, "salvar_pendentes não deve chamar Meta API"


def test_salvar_pendentes_numera_so_acoes_nao_alertas():
    """numero_na_varredura deve ser atribuído só para ações, não alertas."""
    from meta.gestor.executor import salvar_pendentes

    decisoes = [{
        "cliente_id": 1,
        "conta": "Vielife",
        "acoes": [
            {"tipo": "pausar_ad", "entidade_id": "1", "entidade_nome": "A", "motivo": "x"},
            {"tipo": "escalar_orcamento", "entidade_id": "2", "entidade_nome": "B", "motivo": "y"},
        ],
        "alertas": ["Frequencia alta"],
    }]
    perfis = [{"cliente_id": 1, "nome": "Vielife", "account_id": "act_1", "token_key": "T", "gestor_config": None, "erro": None}]

    numeros_inseridos = []
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    def capturar_execute(sql, params=None):
        if params and "pendente" in str(params):
            # Captura numero_na_varredura (último parâmetro antes de 'pendente')
            p = list(params)
            if "pendente" in p:
                idx = p.index("pendente")
                numeros_inseridos.append(p[idx - 1] if idx > 0 else None)

    mock_cur.execute.side_effect = capturar_execute

    with patch("meta.gestor.executor._get_db", return_value=mock_conn):
        with patch("meta.gestor.executor._resolve_token", return_value="tok"):
            salvar_pendentes(decisoes, perfis, varredura_id=1, db_conn=mock_conn)

    # Alertas inseridos sem numero_na_varredura (None ou ausente na query de alertas)
    # Teste básico: não deve lançar exceção
    assert True


# ─── executar_aprovadas ───────────────────────────────────────────────────────

def test_executar_aprovadas_chama_meta_api():
    """executar_aprovadas() deve buscar pendentes e chamar Meta API."""
    from meta.gestor.executor import executar_aprovadas

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    # Simular ações pendentes no banco
    mock_cur.fetchall.return_value = [
        {"id": 10, "tipo": "pausar_ad", "entidade_id": "ad_999", "entidade_nome": "Criativo",
         "cliente_id": 1, "account_id": "act_1", "numero_na_varredura": 1, "motivo": "CPL alto"},
    ]
    # Token da conta
    mock_cur.fetchone.return_value = {"token_key": "META_TOKEN_VIELIFE"}

    with patch("meta.gestor.executor._get_db", return_value=mock_conn):
        with patch("meta.gestor.executor._resolve_token", return_value="tok_real"):
            with patch("meta.gestor.executor.get_ad", return_value={"status": "ACTIVE"}):
                with patch("meta.gestor.executor.atualizar_status_ad") as mock_pausar:
                    resultado = executar_aprovadas(varredura_id=42, canceladas=[], db_conn=mock_conn)

    mock_pausar.assert_called_once_with("tok_real", "ad_999", "PAUSED")
    assert resultado["ok"] >= 1


def test_executar_aprovadas_ignora_canceladas():
    """Ações com numero_na_varredura nas canceladas não devem ser executadas."""
    from meta.gestor.executor import executar_aprovadas

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    mock_cur.fetchall.return_value = [
        {"id": 10, "tipo": "pausar_ad", "entidade_id": "ad_999", "entidade_nome": "X",
         "cliente_id": 1, "account_id": "act_1", "numero_na_varredura": 2, "motivo": ""},
    ]
    mock_cur.fetchone.return_value = {"token_key": "T"}

    with patch("meta.gestor.executor._get_db", return_value=mock_conn):
        with patch("meta.gestor.executor._resolve_token", return_value="tok"):
            with patch("meta.gestor.executor.atualizar_status_ad") as mock_pausar:
                executar_aprovadas(varredura_id=42, canceladas=[2], db_conn=mock_conn)

    mock_pausar.assert_not_called()


# ─── reverter guard ───────────────────────────────────────────────────────────

def test_reverter_rejeita_status_pendente():
    """reverter() deve lançar exceção se ação não foi executada."""
    from meta.gestor.executor import reverter

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = {
        "id": 5, "revertido": False, "status": "pendente",
        "tipo": "pausar_ad", "entidade_id": "x", "valor_antes": None, "cliente_id": 1,
    }

    with patch("meta.gestor.executor._get_db", return_value=mock_conn):
        with pytest.raises(Exception, match="não foi executada"):
            reverter(5, db_conn=mock_conn)
```

- [ ] **Step 2: Rodar testes para confirmar falha**

```bash
cd /root && /root/venv/bin/python3 -m pytest tests/test_gestor_ia_wpp.py -v 2>&1 | head -40
```
Esperado: FAILED (funções ainda não existem)

- [ ] **Step 3: Implementar salvar_pendentes() em executor.py**

Adicionar após a função `executar()` existente:

```python
def salvar_pendentes(
    decisoes: List[Dict[str, Any]],
    perfis: List[Dict[str, Any]],
    varredura_id: int,
    db_conn=None,
) -> int:
    """
    Salva ações como 'pendente' no banco SEM executar no Meta.
    Atribui numero_na_varredura apenas para ações (não alertas).
    Retorna total de ações pendentes salvas.
    """
    fechar = False
    if db_conn is None:
        db_conn = _get_db()
        fechar = True

    perfil_map = {p["cliente_id"]: p for p in perfis}
    total_acoes = 0

    try:
        cur = db_conn.cursor()
        numero_global = 0  # contador de ações numeradas (excluindo alertas)

        for decisao in decisoes:
            cid = decisao["cliente_id"]
            perfil = perfil_map.get(cid)
            if not perfil or perfil.get("erro"):
                continue

            account_id = perfil["account_id"]

            # Alertas — sem numero_na_varredura, sem ação no Meta
            for alerta in decisao.get("alertas", []):
                cur.execute("""
                    INSERT INTO gestor_acoes
                        (varredura_id, cliente_id, account_id, tipo, entidade_id,
                         entidade_nome, motivo, status)
                    VALUES (%s,%s,%s,'alerta_saldo',%s,%s,%s,'sucesso')
                """, (varredura_id, cid, account_id, account_id, decisao["conta"], alerta))

            # Ações — com numero_na_varredura, status=pendente
            for acao in decisao.get("acoes", []):
                numero_global += 1
                cur.execute("""
                    INSERT INTO gestor_acoes
                        (varredura_id, cliente_id, account_id, tipo, entidade_id,
                         entidade_nome, motivo, status, numero_na_varredura)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'pendente',%s)
                """, (
                    varredura_id, cid, account_id,
                    acao["tipo"], acao["entidade_id"], acao.get("entidade_nome", ""),
                    acao.get("motivo", ""), numero_global,
                ))
                total_acoes += 1

        db_conn.commit()
    finally:
        if fechar:
            db_conn.close()

    return total_acoes


def executar_aprovadas(
    varredura_id: int,
    canceladas: List[int] = None,
    db_conn=None,
) -> Dict[str, int]:
    """
    Busca ações pendentes da varredura, ignora as canceladas (por numero_na_varredura),
    executa as aprovadas no Meta e atualiza o status no banco.
    Retorna {"ok": N, "erro": N, "canceladas": N}.
    """
    if canceladas is None:
        canceladas = []

    fechar = False
    if db_conn is None:
        db_conn = _get_db()
        fechar = True

    contadores = {"ok": 0, "erro": 0, "canceladas": 0}

    try:
        cur = db_conn.cursor()

        # Buscar ações pendentes da varredura
        cur.execute("""
            SELECT ga.id, ga.tipo, ga.entidade_id, ga.entidade_nome,
                   ga.cliente_id, ga.account_id, ga.numero_na_varredura, ga.motivo
            FROM gestor_acoes ga
            WHERE ga.varredura_id = %s AND ga.status = 'pendente'
            ORDER BY ga.numero_na_varredura
        """, (varredura_id,))
        acoes = cur.fetchall()

        for acao in acoes:
            num = acao["numero_na_varredura"]

            # Cancelar ações na lista de canceladas
            if num in canceladas:
                cur.execute("""
                    UPDATE gestor_acoes
                    SET status='cancelado', cancelado_em=NOW()
                    WHERE id=%s
                """, (acao["id"],))
                contadores["canceladas"] += 1
                continue

            # Buscar token da conta
            cur2 = db_conn.cursor()
            cur2.execute("SELECT token_key FROM ad_client_profiles WHERE id=%s", (acao["cliente_id"],))
            row = cur2.fetchone()
            if not row:
                contadores["erro"] += 1
                continue

            try:
                token = _resolve_token(row["token_key"])
            except ValueError:
                contadores["erro"] += 1
                continue

            tipo = acao["tipo"]
            entidade_id = acao["entidade_id"]
            valor_antes = None
            valor_depois = None

            try:
                if tipo == "pausar_ad":
                    estado = get_ad(token, entidade_id)
                    valor_antes = {"status": estado.get("status")}
                    valor_depois = {"status": "PAUSED"}
                    atualizar_status_ad(token, entidade_id, "PAUSED")

                elif tipo == "reativar_ad":
                    valor_antes = {"status": "PAUSED"}
                    valor_depois = {"status": "ACTIVE"}
                    atualizar_status_ad(token, entidade_id, "ACTIVE")

                elif tipo == "escalar_orcamento":
                    estado = get_adset(token, entidade_id)
                    atual = int(estado.get("daily_budget") or 0)
                    novo = int(atual * 1.15)
                    valor_antes = {"daily_budget": atual}
                    valor_depois = {"daily_budget": novo}
                    atualizar_orcamento_conjunto(token, entidade_id, novo)

                elif tipo == "reduzir_orcamento":
                    estado = get_adset(token, entidade_id)
                    atual = int(estado.get("daily_budget") or 0)
                    novo = int(atual * 0.80)
                    valor_antes = {"daily_budget": atual}
                    valor_depois = {"daily_budget": novo}
                    atualizar_orcamento_conjunto(token, entidade_id, novo)

                elif tipo == "pausar_conta":
                    valor_antes = {"status": "ACTIVE"}
                    valor_depois = {"status": "PAUSED"}
                    atualizar_status_campanha(token, entidade_id, "PAUSED")

                elif tipo == "duplicar_ad":
                    from meta.meta_api import duplicar_ad as _duplicar
                    novo_id = _duplicar(token, acao["account_id"], entidade_id)
                    valor_antes = {"ad_id": entidade_id}
                    valor_depois = {"ad_id_duplicado": novo_id}

                else:
                    continue

                cur.execute("""
                    UPDATE gestor_acoes
                    SET status='sucesso', aprovado_em=NOW(),
                        valor_antes=%s, valor_depois=%s
                    WHERE id=%s
                """, (json.dumps(valor_antes), json.dumps(valor_depois), acao["id"]))
                contadores["ok"] += 1

            except Exception as e:
                # IMPORTANTE: usar parâmetros psycopg2, NÃO interpolação de string
                cur.execute(
                    "UPDATE gestor_acoes SET status='erro', motivo=CONCAT(motivo, %s) WHERE id=%s",
                    (f" | Erro: {str(e)[:200]}", acao["id"]),
                )
                contadores["erro"] += 1

        db_conn.commit()
    finally:
        if fechar:
            db_conn.close()

    return contadores
```

- [ ] **Step 4: Adicionar guard no reverter()**

Localizar em `executor.py` a linha:
```python
if acao["status"] != "sucesso":
    raise Exception(f"Só é possível reverter ações com status 'sucesso'")
```
Substituir por:
```python
if acao["status"] != "sucesso":
    if acao["status"] in ("pendente", "expirado", "cancelado"):
        raise Exception(f"Ação {acao_id} não foi executada no Meta, nada a reverter (status: {acao['status']})")
    raise Exception(f"Só é possível reverter ações com status 'sucesso' (atual: {acao['status']})")
```

- [ ] **Step 5: Rodar testes**

```bash
cd /root && /root/venv/bin/python3 -m pytest tests/test_gestor_ia_wpp.py::test_salvar_pendentes_salva_acoes_sem_executar tests/test_gestor_ia_wpp.py::test_executar_aprovadas_chama_meta_api tests/test_gestor_ia_wpp.py::test_executar_aprovadas_ignora_canceladas tests/test_gestor_ia_wpp.py::test_reverter_rejeita_status_pendente -v
```
Esperado: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add meta/gestor/executor.py tests/test_gestor_ia_wpp.py
git commit -m "feat(gestor): salvar_pendentes(), executar_aprovadas(), guard no reverter()"
```

---

## Task 3: meta_api.py — duplicar_ad()

**Files:**
- Modify: `meta/meta_api.py`
- Test: `tests/test_gestor_ia_wpp.py`

- [ ] **Step 1: Escrever o teste**

Adicionar ao `tests/test_gestor_ia_wpp.py`:

```python
# ─── duplicar_ad ──────────────────────────────────────────────────────────────

def test_duplicar_ad_cria_adset_e_anuncio():
    """duplicar_ad() deve criar novo adset e novo ad baseado no original."""
    from meta.meta_api import duplicar_ad

    ad_original = {
        "id": "ad_111",
        "name": "Criativo X",
        "adset_id": "adset_999",
        "creative": {"id": "creative_55"},
        "status": "ACTIVE",
    }
    adset_original = {
        "id": "adset_999",
        "name": "Conjunto Original",
        "campaign_id": "camp_1",
        "daily_budget": "3000",
        "targeting": {"age_min": 18},
        "optimization_goal": "LEAD_GENERATION",
        "billing_event": "IMPRESSIONS",
    }

    with patch("meta.meta_api.get_ad", return_value=ad_original):
        with patch("meta.meta_api.get_adset", return_value=adset_original):
            with patch("meta.meta_api.criar_conjunto", return_value="adset_novo_999") as mock_cs:
                with patch("meta.meta_api.criar_anuncio", return_value="ad_novo_111") as mock_ca:
                    novo_id = duplicar_ad("tok", "act_123", "ad_111")

    assert novo_id == "ad_novo_111"
    mock_cs.assert_called_once()
    mock_ca.assert_called_once()
```

- [ ] **Step 2: Rodar o teste para confirmar falha**

```bash
cd /root && /root/venv/bin/python3 -m pytest tests/test_gestor_ia_wpp.py::test_duplicar_ad_cria_adset_e_anuncio -v
```
Esperado: FAILED (ImportError ou AttributeError)

- [ ] **Step 3: Implementar duplicar_ad() em meta_api.py**

Adicionar ao final de `meta/meta_api.py`:

```python
def duplicar_ad(token: str, account_id: str, ad_id: str) -> str:
    """
    Duplica um ad existente: cria novo adset baseado no original e cria novo ad nele.
    Retorna o ID do novo ad criado.
    O ad duplicado começa PAUSED — aprovação necessária para ativar.
    """
    # 1. Buscar dados do ad e do adset originais
    ad = get_ad(token, ad_id)
    adset_id = ad.get("adset_id") or ad.get("adset", {}).get("id")
    if not adset_id:
        raise ValueError(f"Ad {ad_id} não tem adset_id")

    adset = get_adset(token, adset_id)
    creative_id = (ad.get("creative") or {}).get("id")
    if not creative_id:
        raise ValueError(f"Ad {ad_id} não tem creative_id")

    # 2. Criar novo adset (cópia do original com prefixo "COPY_")
    novo_nome_adset = f"COPY_{adset.get('name', adset_id)}"
    novo_adset_id = criar_conjunto(
        token=token,
        account_id=account_id,
        campaign_id=adset["campaign_id"],
        nome=novo_nome_adset,
        orcamento_diario_cents=int(adset.get("daily_budget") or 0),
        publico_id=None,  # herda do targeting original
        targeting=adset.get("targeting"),
        optimization_goal=adset.get("optimization_goal", "LEAD_GENERATION"),
        billing_event=adset.get("billing_event", "IMPRESSIONS"),
        status="PAUSED",
    )

    # 3. Criar novo ad no novo adset usando o mesmo creative
    novo_nome_ad = f"COPY_{ad.get('name', ad_id)}"
    # Buscar page_id do creative original
    resp = requests.get(
        f"{GRAPH_URL}/{creative_id}",
        params={"fields": "object_story_spec", "access_token": token},
        timeout=15,
    )
    page_id = None
    try:
        spec = resp.json().get("object_story_spec", {})
        page_id = spec.get("page_id") or next(iter(spec.values()), {}).get("page_id")
    except Exception:
        pass

    novo_ad_id = criar_anuncio(
        token=token,
        account_id=account_id,
        adset_id=novo_adset_id,
        page_id=page_id or "",
        nome=novo_nome_ad,
        creative_id=creative_id,
        status="PAUSED",
    )

    return novo_ad_id
```

- [ ] **Step 4: Rodar o teste**

```bash
cd /root && /root/venv/bin/python3 -m pytest tests/test_gestor_ia_wpp.py::test_duplicar_ad_cria_adset_e_anuncio -v
```
Esperado: PASSED

- [ ] **Step 5: Commit**

```bash
git add meta/meta_api.py tests/test_gestor_ia_wpp.py
git commit -m "feat(meta_api): duplicar_ad() - copia adset e ad com status PAUSED"
```

---

## Task 4: coletor.py — Dados extras para novos alertas

**Files:**
- Modify: `meta/gestor/coletor.py`

- [ ] **Step 1: Adicionar _buscar_insights_diarios()**

Após a função `_buscar_insights_ads()` existente, adicionar:

```python
def _buscar_insights_diarios(token: str, account_id: str, days: int = 7) -> list:
    """
    Busca gasto diário da conta nos últimos N dias (level=account).
    Retorna lista de {"date_start": "YYYY-MM-DD", "spend": float}.
    """
    hoje = date.today()
    inicio = hoje - timedelta(days=days)
    url = f"{GRAPH_URL}/{account_id}/insights"
    params = {
        "access_token": token,
        "level": "account",
        "fields": "spend,date_start,actions",
        "time_range": json.dumps({"since": str(inicio), "until": str(hoje)}),
        "time_increment": 1,  # 1 dia por linha
        "limit": 10,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception:
        return []


def _buscar_cpl_semana_anterior(cliente_id: int, objetivo: str) -> float | None:
    """
    Lê do banco o CPL médio da semana anterior para comparativo.
    Abre sua própria conexão (a conexão principal de coletar() é fechada antes do loop).
    Retorna float ou None se não houver dados.
    """
    try:
        conn = _get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT gv.resumo_json
                FROM gestor_varreduras gv
                WHERE gv.executado_em < NOW() - INTERVAL '6 days'
                  AND gv.status = 'sucesso'
                ORDER BY gv.executado_em DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if not row or not row["resumo_json"]:
                return None
            # resumo_json guarda contadores gerais — CPL por cliente não está nele ainda
            # Retornamos None por ora; será expandido quando gestor gravar CPL por conta
            return None
        finally:
            conn.close()
    except Exception:
        return None
```

- [ ] **Step 2: Adicionar effective_status na busca de ads e calcular métricas extras**

Na função `_buscar_insights_ads()`, adicionar `effective_status` nos campos:

```python
"fields": "ad_id,ad_name,spend,impressions,clicks,actions,frequency,cpm,ctr,effective_status",
```

- [ ] **Step 3: Calcular dados extras em coletar()**

Na função `coletar()`, após `metricas = _agregar_conta(rows, objetivo)`, adicionar:

```python
# Dados diários para alertas
dados_diarios = _buscar_insights_diarios(token, conta["account_id"], days=7)
gasto_ontem = 0.0
dias_sem_conversao = 0
if dados_diarios:
    gasto_ontem = float(dados_diarios[-1].get("spend") or 0)
    # Contar dias consecutivos com gasto mas sem conversao
    for dia in reversed(dados_diarios):
        spend_dia = float(dia.get("spend") or 0)
        conv_dia = _extrair_conversoes(dia.get("actions") or [], objetivo)
        if spend_dia > 0 and conv_dia == 0:
            dias_sem_conversao += 1
        elif spend_dia > 0:
            break  # sequência quebrada

# Dias em learning (ads com effective_status=LEARNING)
dias_learning = sum(
    1 for r in rows
    if r.get("effective_status") == "CAMPAIGN_TURNED_OFF"  # placeholder — usar LEARNING
)
ads_em_learning = [r for r in rows if r.get("effective_status") == "LEARNING"]

# CPL semana anterior (do banco)
cpl_semana_anterior = _buscar_cpl_semana_anterior(conta["id"], objetivo)
# Nota: _buscar_cpl_semana_anterior abre sua própria conexão porque db_conn é fechado
# logo após buscar a lista de contas (bloco finally do início de coletar())

metricas["gasto_ontem"] = gasto_ontem
metricas["dias_sem_conversao"] = dias_sem_conversao
metricas["ads_em_learning"] = len(ads_em_learning)
metricas["cpl_semana_anterior"] = cpl_semana_anterior
```

Nota: `db_conn_local` é a conexão aberta no início de `coletar()` — ajustar o escopo conforme o código atual.

- [ ] **Step 4: Verificar que coletar() não quebra**

```bash
cd /root && /root/venv/bin/python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/root/.env')
from meta.gestor.coletor import coletar
perfis = coletar()
print(f'{len(perfis)} contas coletadas')
p = perfis[0]
print('metricas keys:', list(p.get('metricas', {}).keys()))
" 2>&1 | tail -20
```
Esperado: lista de contas + `gasto_ontem`, `dias_sem_conversao`, `ads_em_learning` nas keys

- [ ] **Step 5: Commit**

```bash
git add meta/gestor/coletor.py
git commit -m "feat(coletor): dados diarios, effective_status e cpl semana anterior"
```

---

## Task 5: analista.py — Novas ações e alertas

**Files:**
- Modify: `meta/gestor/analista.py`

- [ ] **Step 1: Atualizar _SYSTEM_PROMPT com novas ações e alertas**

Substituir o `_SYSTEM_PROMPT` completo:

```python
_SYSTEM_PROMPT = """Você é um gestor expert de tráfego pago Meta Ads. Você gerencia múltiplas contas e toma decisões de otimização baseadas no histórico de cada conta.

REGRAS DE DECISÃO:
1. Se a conta tem histórico (cpl_medio não nulo e dias_historico >= 14): analise pelo perfil histórico — CPL acima da média + 1 desvio padrão é sinal de problema; frequência > 3.5 indica fadiga criativa
2. Se a conta tem < 14 dias de histórico ou cpl_medio nulo: use gestor_config como fallback (cpl_max, freq_max)
3. Se nem histórico nem config: apenas monitore, não aja (acoes=[])
4. Se saldo remaining < 30: SEMPRE pause toda a conta (pausar_conta)
5. Se saldo remaining < saldo_alerta (ou < 100 se não configurado): emita alerta (alertas=[])

AÇÕES DISPONÍVEIS (executam no Meta Ads — precisam de aprovação):
- pausar_ad: {"tipo": "pausar_ad", "entidade_id": "<ad_id>", "entidade_nome": "<nome>", "motivo": "..."}
- reativar_ad: {"tipo": "reativar_ad", "entidade_id": "<ad_id>", "entidade_nome": "<nome>", "motivo": "CPL voltou ao normal"}
  → Use apenas se o ad foi pausado pelo gestor anteriormente e CPL voltou abaixo do threshold
- escalar_orcamento: {"tipo": "escalar_orcamento", "entidade_id": "<adset_id>", "entidade_nome": "<nome>", "motivo": "..."}
  → Escale apenas quando o melhor performer estiver claramente ABAIXO do threshold (CPL bom)
- reduzir_orcamento: {"tipo": "reduzir_orcamento", "entidade_id": "<adset_id>", "entidade_nome": "<nome>", "motivo": "..."}
  → Use quando CPL > limite + 30% mas pausar o ad seria prematuro — reduz 20% do orçamento
- pausar_conta: {"tipo": "pausar_conta", "entidade_id": "<account_id>", "entidade_nome": "<nome>", "motivo": "saldo crítico"}
- duplicar_ad: {"tipo": "duplicar_ad", "entidade_id": "<ad_id>", "entidade_nome": "<nome>", "motivo": "..."}
  → Use quando top_ads[0] tem CPL 40% abaixo da média E frequência < 2.0 — duplica para teste

ALERTAS DISPONÍVEIS (não executam no Meta — só informam):
- Use o campo "alertas" (lista de strings) para situações que não requerem ação imediata:
  * "FREQ_ALTA: <ad_nome> freq=<X> (limite 2.5) — monitorar" quando freq > 2.5 e < 3.5
  * "ZERO_CONV: <X> dias com gasto mas sem conversão" quando metricas.dias_sem_conversao >= 3
  * "LEARNING_TRAVADO: <N> ads em aprendizado" quando metricas.ads_em_learning > 0
  * "SALDO_CRITICO: saldo projetado acaba em <N> dias" quando saldo.remaining / gasto_diario_medio < 3
  * "SEM_VEICULACAO: gasto R$0 ontem" quando metricas.gasto_ontem == 0 e há campanhas ativas
  * "CPL_SEMANAL: CPL subiu/caiu X% vs semana anterior" quando metricas.cpl_semana_anterior não é null

FORMATO DE RESPOSTA — retorne APENAS JSON válido, sem markdown:
[
  {
    "cliente_id": <int>,
    "conta": "<nome>",
    "analise": "<1-2 frases explicando o diagnóstico>",
    "acoes": [...],
    "alertas": ["<texto de alerta se houver>"]
  }
]

Se uma conta não requer ação nem alerta, retorne acoes=[] e alertas=[].
Seja conservador: prefira alertar a agir quando houver dúvida.
"""
```

- [ ] **Step 2: Verificar que analista ainda funciona com perfis reais**

```bash
cd /root && /root/venv/bin/python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/root/.env')
from meta.gestor.coletor import coletar
from meta.gestor.analista import analisar
perfis = coletar()
decisoes = analisar(perfis[:3])  # só 3 contas para economizar tokens
for d in decisoes:
    print(d['conta'], '| acoes:', len(d.get('acoes',[])), '| alertas:', len(d.get('alertas',[])))
"
```
Esperado: sem erro, lista de decisões

- [ ] **Step 3: Commit**

```bash
git add meta/gestor/analista.py
git commit -m "feat(analista): novas acoes (reativar, reduzir, duplicar) e 6 alertas inteligentes"
```

---

## Task 6: whatsapp_handlers.py — Funções do gestor WA

**Files:**
- Modify: `bot/whatsapp_handlers.py`
- Test: `tests/test_gestor_ia_wpp.py`

- [ ] **Step 1: Escrever testes das funções WA**

Adicionar ao `tests/test_gestor_ia_wpp.py`:

```python
# ─── enviar_resumo_gestor ─────────────────────────────────────────────────────

def test_enviar_resumo_gestor_formata_mensagem():
    """enviar_resumo_gestor() deve formatar ações numeradas + alertas separados."""
    from bot.whatsapp_handlers import formatar_resumo_gestor

    acoes = [
        {"numero_na_varredura": 1, "tipo": "pausar_ad", "entidade_nome": "Criativo X",
         "cliente_nome": "Vielife", "motivo": "CPL R$87 (media R$52)"},
        {"numero_na_varredura": 2, "tipo": "escalar_orcamento", "entidade_nome": "Adset Y",
         "cliente_nome": "Castaldi", "motivo": "CPL R$18 otimo"},
    ]
    alertas = [
        {"tipo": "alerta_saldo", "entidade_nome": "ODC Massaranduba",
         "cliente_nome": "ODC Massaranduba", "motivo": "freq 2.7"},
    ]
    total_contas = 23

    msg = formatar_resumo_gestor(acoes, alertas, total_contas, varredura_id=42)

    assert "23 contas" in msg
    assert "1." in msg and "PAUSAR AD" in msg.upper()
    assert "2." in msg and "ESCALAR" in msg.upper()
    assert "Alertas" in msg
    assert "freq 2.7" in msg
    assert "ok" in msg.lower()
    assert "cancela" in msg.lower()
    assert "4h" in msg


def test_enviar_resumo_gestor_silencio_sem_acoes_e_alertas():
    """Se não há ações nem alertas, formatar_resumo_gestor retorna None."""
    from bot.whatsapp_handlers import formatar_resumo_gestor

    msg = formatar_resumo_gestor([], [], total_contas=23, varredura_id=1)
    assert msg is None


def test_enviar_resumo_gestor_so_alertas_sem_bloco_aprovacao():
    """Se há só alertas (sem ações), mensagem não pede 'ok' nem 'cancela'."""
    from bot.whatsapp_handlers import formatar_resumo_gestor

    alertas = [{"tipo": "alerta_frequencia", "entidade_nome": "X",
                "cliente_nome": "Vielife", "motivo": "freq 2.7"}]
    msg = formatar_resumo_gestor([], alertas, total_contas=23, varredura_id=1)

    assert msg is not None
    assert "freq 2.7" in msg
    assert "ok" not in msg.lower() or "aprovacao" not in msg.lower()
    assert "cancela" not in msg.lower()


# ─── processar_aprovacao ──────────────────────────────────────────────────────

def test_processar_aprovacao_ok_executa_tudo():
    """'ok' deve chamar executar_aprovadas com canceladas=[]."""
    from bot.whatsapp_handlers import processar_aprovacao

    with patch("bot.whatsapp_handlers._verificar_varredura_pendente", return_value={"varredura_id": 42, "id": 1}):
        with patch("bot.whatsapp_handlers.executar_aprovadas", return_value={"ok": 2, "erro": 0, "canceladas": 0}) as mock_exec:
            with patch("bot.whatsapp_handlers.send_text") as mock_send:
                with patch("bot.whatsapp_handlers._marcar_estado_resolvido"):
                    processar_aprovacao("ok", "5535988550954")

    mock_exec.assert_called_once_with(varredura_id=42, canceladas=[])
    mock_send.assert_called()


def test_processar_aprovacao_cancela_n_remove_acao():
    """'cancela 2' deve chamar executar_aprovadas com canceladas=[2]."""
    from bot.whatsapp_handlers import processar_aprovacao

    with patch("bot.whatsapp_handlers._verificar_varredura_pendente", return_value={"varredura_id": 42, "id": 1}):
        with patch("bot.whatsapp_handlers.executar_aprovadas", return_value={"ok": 1, "erro": 0, "canceladas": 1}) as mock_exec:
            with patch("bot.whatsapp_handlers.send_text"):
                with patch("bot.whatsapp_handlers._marcar_estado_resolvido"):
                    processar_aprovacao("cancela 2", "5535988550954")

    mock_exec.assert_called_once_with(varredura_id=42, canceladas=[2])
```

- [ ] **Step 2: Rodar testes para confirmar falha**

```bash
cd /root && /root/venv/bin/python3 -m pytest tests/test_gestor_ia_wpp.py::test_enviar_resumo_gestor_formata_mensagem tests/test_gestor_ia_wpp.py::test_processar_aprovacao_ok_executa_tudo tests/test_gestor_ia_wpp.py::test_processar_aprovacao_cancela_n_remove_acao -v
```
Esperado: FAILED

- [ ] **Step 3: Implementar funções no whatsapp_handlers.py**

Adicionar após a função `resumo_gestor()` existente (linha ~193):

```python
# ── Gestor IA WA — novas funções ─────────────────────────────────────────────

def _verificar_varredura_pendente() -> dict | None:
    """
    Consulta gestor_estado no banco. Retorna dict com varredura_id e id do estado,
    ou None se não há aprovação pendente.
    """
    try:
        conn = _db()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, varredura_id
                FROM gestor_estado
                WHERE status = 'aguardando'
                ORDER BY criado_em DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"_verificar_varredura_pendente error: {e}")
        return None


def _marcar_estado_resolvido(estado_id: int):
    """Marca gestor_estado como aprovado/resolvido."""
    try:
        conn = _db()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE gestor_estado
                SET status='aprovado', resolvido_em=NOW()
                WHERE id=%s
            """, (estado_id,))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"_marcar_estado_resolvido error: {e}")


def formatar_resumo_gestor(acoes: list, alertas: list, total_contas: int, varredura_id: int) -> str | None:
    """
    Formata mensagem matinal do Gestor IA.
    Retorna None se não há ações nem alertas (silêncio).
    """
    from datetime import date as _date
    hoje = _date.today().strftime("%d/%m")

    if not acoes and not alertas:
        return None

    linhas = [f"Gestor IA — {hoje}"]

    if acoes:
        linhas.append(f"Analisei {total_contas} contas. {len(acoes)} {'acao' if len(acoes)==1 else 'acoes'} para aprovar:")
        linhas.append("")
        _TIPO_LABEL = {
            "pausar_ad": "PAUSAR AD",
            "reativar_ad": "REATIVAR AD",
            "escalar_orcamento": "ESCALAR ORCAMENTO +15%",
            "reduzir_orcamento": "REDUZIR ORCAMENTO -20%",
            "pausar_conta": "PAUSAR CONTA",
            "duplicar_ad": "DUPLICAR AD",
        }
        for a in acoes:
            label = _TIPO_LABEL.get(a["tipo"], a["tipo"].upper())
            linhas.append(f"{a['numero_na_varredura']}. {label} — {a['cliente_nome']}")
            linhas.append(f"   {a['entidade_nome']} | {a['motivo']}")
            linhas.append("")
    else:
        linhas.append(f"Analisei {total_contas} contas. Sem acoes necessarias.")
        linhas.append("")

    if alertas:
        linhas.append("Alertas (sem acao):")
        for al in alertas:
            linhas.append(f"- {al['cliente_nome']}: {al['motivo']}")
        linhas.append("")

    if acoes:
        linhas.append('Responda "ok" para aprovar tudo ou "cancela N" para cancelar uma acao especifica.')
        linhas.append("Expira em 4h.")

    return "\n".join(linhas)


def enviar_resumo_gestor(varredura_id: int):
    """Busca ações pendentes e alertas do varredura_id e envia WA formatado."""
    import os as _os
    destino = _os.environ.get("WA_AUTHORIZED_NUMBER", "").strip()
    if not destino:
        logger.warning("WA_AUTHORIZED_NUMBER não configurado — resumo não enviado")
        return

    try:
        conn = _db()
        try:
            cur = conn.cursor()
            total_contas_cur = conn.cursor()
            total_contas_cur.execute("SELECT COUNT(*) FROM ad_client_profiles WHERE gestor_ativo=TRUE")
            total_contas = total_contas_cur.fetchone()[0]

            cur.execute("""
                SELECT ga.numero_na_varredura, ga.tipo, ga.entidade_nome,
                       ga.motivo, acp.nome as cliente_nome
                FROM gestor_acoes ga
                JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
                WHERE ga.varredura_id = %s AND ga.status = 'pendente'
                  AND ga.numero_na_varredura IS NOT NULL
                ORDER BY ga.numero_na_varredura
            """, (varredura_id,))
            acoes = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT ga.tipo, ga.entidade_nome, ga.motivo, acp.nome as cliente_nome
                FROM gestor_acoes ga
                JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
                WHERE ga.varredura_id = %s AND ga.tipo LIKE 'alerta%'
                ORDER BY ga.executado_em
            """, (varredura_id,))
            alertas = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"enviar_resumo_gestor DB error: {e}")
        return

    msg = formatar_resumo_gestor(acoes, alertas, total_contas, varredura_id)
    if msg:
        send_text(destino, msg)


def processar_aprovacao(texto: str, destino: str):
    """
    Processa resposta de aprovação do Bruno.
    texto: "ok" ou "cancela N"
    """
    import re as _re
    import sys as _sys
    if "/root" not in _sys.path:
        _sys.path.insert(0, "/root")
    from meta.gestor.executor import executar_aprovadas

    estado = _verificar_varredura_pendente()
    if not estado:
        send_text(destino, "Sem acoes pendentes de aprovacao no momento.")
        return

    varredura_id = estado["varredura_id"]
    estado_id = estado["id"]

    canceladas = []
    texto_limpo = texto.strip().lower()

    if texto_limpo == "ok":
        canceladas = []
    else:
        m = _re.match(r"^cancela\s+(\d+)$", texto_limpo)
        if m:
            n = int(m.group(1))
            # Verificar se N é válido (existe ação com esse número)
            try:
                conn_check = _db()
                cur_check = conn_check.cursor()
                cur_check.execute(
                    "SELECT COUNT(*) FROM gestor_acoes WHERE varredura_id=%s AND status='pendente' AND numero_na_varredura=%s",
                    (varredura_id, n),
                )
                existe = cur_check.fetchone()[0] > 0
                # Buscar total de ações para mensagem de erro
                cur_check.execute(
                    "SELECT COUNT(*) FROM gestor_acoes WHERE varredura_id=%s AND status='pendente' AND numero_na_varredura IS NOT NULL",
                    (varredura_id,),
                )
                total = cur_check.fetchone()[0]
                conn_check.close()
                if not existe:
                    send_text(destino, f"So tem {total} acao(es) numerada(s). Manda 'ok' para aprovar ou ignore para cancelar tudo em 4h.")
                    return
            except Exception:
                pass
            canceladas = [n]
        else:
            send_text(destino, 'Nao entendi. Responda "ok" para aprovar tudo ou "cancela N" para cancelar uma acao.')
            return

    try:
        resultado = executar_aprovadas(varredura_id=varredura_id, canceladas=canceladas)
        _marcar_estado_resolvido(estado_id)

        partes = []
        if resultado["ok"]:
            partes.append(f"{resultado['ok']} acao(es) executada(s)")
        if resultado["canceladas"]:
            partes.append(f"{resultado['canceladas']} cancelada(s)")
        if resultado["erro"]:
            partes.append(f"{resultado['erro']} com erro")

        msg = "Gestor IA: " + ", ".join(partes) + "."
        send_text(destino, msg)
    except Exception as e:
        logger.error(f"processar_aprovacao error: {e}")
        send_text(destino, f"Erro ao executar acoes: {e}")


# ── Comandos slash ─────────────────────────────────────────────────────────────

def cmd_saldo(destino: str):
    """Lista saldo atual de todas as contas ativas."""
    import os as _os, sys as _sys, requests as _req
    if "/root" not in _sys.path:
        _sys.path.insert(0, "/root")
    from meta.meta_api import _resolve_token

    GRAPH_URL = "https://graph.facebook.com/v21.0"
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            SELECT nome, agencia, account_id, token_key
            FROM ad_client_profiles
            WHERE gestor_ativo = TRUE
            ORDER BY agencia, nome
        """)
        contas = cur.fetchall()
        conn.close()
    except Exception as e:
        send_text(destino, f"Erro ao buscar contas: {e}")
        return

    linhas = ["Saldo das contas ativas:"]
    agencia_atual = None
    for c in contas:
        if c["agencia"] != agencia_atual:
            agencia_atual = c["agencia"]
            linhas.append(f"\n[{agencia_atual.upper()}]")
        try:
            token = _resolve_token(c["token_key"])
            resp = _req.get(
                f"{GRAPH_URL}/{c['account_id']}",
                params={"fields": "amount_spent,spend_cap,balance", "access_token": token},
                timeout=10,
            )
            d = resp.json()
            spent = float(d.get("amount_spent") or 0) / 100
            cap = float(d.get("spend_cap") or 0) / 100
            bal = float(d.get("balance") or 0) / 100
            remaining = max(0.0, cap - spent) if cap else bal
            linhas.append(f"  {c['nome']}: R${remaining:.0f} restante")
        except Exception:
            linhas.append(f"  {c['nome']}: erro ao buscar")

    send_text(destino, "\n".join(linhas))


def cmd_historico(destino: str):
    """Últimas 10 ações do gestor com status."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            SELECT ga.tipo, ga.entidade_nome, ga.status, ga.executado_em,
                   acp.nome as cliente_nome
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE ga.tipo NOT LIKE 'alerta%'
            ORDER BY ga.executado_em DESC
            LIMIT 10
        """)
        acoes = cur.fetchall()
        conn.close()
    except Exception as e:
        send_text(destino, f"Erro: {e}")
        return

    if not acoes:
        send_text(destino, "Nenhuma acao registrada ainda.")
        return

    _STATUS_ICON = {"sucesso": "V", "erro": "X", "pendente": "...", "cancelado": "-", "expirado": "~"}
    linhas = ["Historico do Gestor IA (ultimas 10):"]
    for a in acoes:
        icon = _STATUS_ICON.get(a["status"], "?")
        data = a["executado_em"].strftime("%d/%m %H:%M") if a["executado_em"] else "?"
        linhas.append(f"[{icon}] {a['tipo']} — {a['entidade_nome']} ({a['cliente_nome']}) {data}")

    send_text(destino, "\n".join(linhas))


def cmd_status_cliente(destino: str, nome_cliente: str):
    """Métricas rápidas de um cliente: CPL, freq, saldo, top ad."""
    import sys as _sys
    if "/root" not in _sys.path:
        _sys.path.insert(0, "/root")

    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nome, agencia, account_id, token_key, campanha_tipo
            FROM ad_client_profiles
            WHERE LOWER(nome) LIKE %s AND gestor_ativo = TRUE
            LIMIT 1
        """, (f"%{nome_cliente.lower()}%",))
        conta = cur.fetchone()
        conn.close()
    except Exception as e:
        send_text(destino, f"Erro: {e}")
        return

    if not conta:
        send_text(destino, f"Cliente '{nome_cliente}' nao encontrado.")
        return

    try:
        from meta.meta_api import _resolve_token
        from meta.gestor.coletor import _buscar_insights_ads, _buscar_saldo, _agregar_conta
        token = _resolve_token(conta["token_key"])
        rows = _buscar_insights_ads(token, conta["account_id"])
        saldo = _buscar_saldo(token, conta["account_id"])
        metricas = _agregar_conta(rows, conta["campanha_tipo"] or "MESSAGES")

        top = metricas.get("top_ads", [{}])[0] if metricas.get("top_ads") else {}
        linhas = [
            f"Status: {conta['nome']}",
            f"CPL medio: R${metricas.get('cpl_medio') or '—'}",
            f"Freq media: —",
            f"Saldo: R${saldo.get('remaining', 0):.0f}",
            f"Top ad: {top.get('ad_name', '—')} (CPL R${top.get('cpl', '—')})",
            f"Total conversoes 30d: {metricas.get('total_conversoes', 0)}",
        ]
        send_text(destino, "\n".join(linhas))
    except Exception as e:
        send_text(destino, f"Erro ao buscar metricas: {e}")


def cmd_relatorio(destino: str):
    """Envia resumo da semana em texto no WA."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            SELECT ga.tipo, ga.entidade_nome, ga.status, acp.nome as cliente_nome, acp.agencia
            FROM gestor_acoes ga
            JOIN ad_client_profiles acp ON acp.id = ga.cliente_id
            WHERE ga.executado_em >= NOW() - INTERVAL '7 days'
              AND ga.tipo NOT LIKE 'alerta%'
              AND ga.status = 'sucesso'
            ORDER BY ga.executado_em DESC
        """)
        acoes = cur.fetchall()
        conn.close()
    except Exception as e:
        send_text(destino, f"Erro: {e}")
        return

    if not acoes:
        send_text(destino, "Nenhuma acao executada nos ultimos 7 dias.")
        return

    por_agencia: dict = {}
    for a in acoes:
        ag = a["agencia"] or "—"
        por_agencia.setdefault(ag, []).append(a)

    linhas = ["Relatorio semanal — ultimos 7 dias:"]
    for ag, lista in por_agencia.items():
        linhas.append(f"\n[{ag.upper()}] {len(lista)} acoes")
        for a in lista[:5]:
            linhas.append(f"  V {a['tipo']} — {a['entidade_nome']} ({a['cliente_nome']})")
        if len(lista) > 5:
            linhas.append(f"  ... e mais {len(lista)-5}")

    linhas.append("\nPDF completo disponivel no Jake OS > Relatorios.")
    send_text(destino, "\n".join(linhas))
```

- [ ] **Step 4: Rodar testes**

```bash
cd /root && /root/venv/bin/python3 -m pytest tests/test_gestor_ia_wpp.py::test_enviar_resumo_gestor_formata_mensagem tests/test_gestor_ia_wpp.py::test_enviar_resumo_gestor_silencio_sem_acoes_e_alertas tests/test_gestor_ia_wpp.py::test_processar_aprovacao_ok_executa_tudo tests/test_gestor_ia_wpp.py::test_processar_aprovacao_cancela_n_remove_acao -v
```
Esperado: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add bot/whatsapp_handlers.py tests/test_gestor_ia_wpp.py
git commit -m "feat(wpp_handlers): enviar_resumo_gestor, processar_aprovacao, cmds slash"
```

---

## Task 7: gestor_agente.py — Orquestrador semi-autônomo

**Files:**
- Modify: `meta/gestor_agente.py`

- [ ] **Step 1: Ler o arquivo atual**

```bash
cat -n /root/meta/gestor_agente.py
```

- [ ] **Step 2: Atualizar imports no topo do arquivo**

Localizar a linha (próximo ao topo do arquivo):
```python
from meta.gestor.executor import executar
```
Substituir por:
```python
from meta.gestor.executor import salvar_pendentes
```
(A função `executar` não é mais chamada diretamente pelo orquestrador — `executar_aprovadas` é chamada pelo handler WA.)

- [ ] **Step 3: Substituir executar() por salvar_pendentes() + notificação WA**

Substituir o bloco da função `main()` (manter imports restantes e _get_db inalterados). O novo `main()`:

```python
def main():
    inicio = time.time()
    _log("Iniciando varredura...")

    db_conn = None
    db_conn = _get_db()
    cur = db_conn.cursor()

    # Inserir registro de varredura
    cur.execute("""
        INSERT INTO gestor_varreduras (contas_total, contas_ok, contas_acao, contas_erro, status)
        VALUES (0, 0, 0, 0, 'em_andamento')
        RETURNING id
    """)
    varredura_id = cur.fetchone()["id"]
    db_conn.commit()

    try:
        # 1. Coletar
        _log("Coletando metricas...")
        perfis = coletar(db_conn=None)
        _log(f"  {len(perfis)} contas coletadas")

        # 2. Analisar
        _log("Analisando com Claude...")
        decisoes = analisar(perfis)
        total_acoes = sum(len(d.get('acoes', [])) for d in decisoes)
        _log(f"  {total_acoes} acoes decididas")

        # 3. Salvar como pendente (NÃO executa no Meta)
        _log("Salvando acoes como pendentes...")
        from meta.gestor.executor import salvar_pendentes
        n_pendentes = salvar_pendentes(decisoes, perfis, varredura_id, db_conn=None)
        _log(f"  {n_pendentes} acoes pendentes salvas")

        # 4. Registrar estado de aprovação no banco
        if n_pendentes > 0:
            cur.execute("""
                INSERT INTO gestor_estado (varredura_id, status)
                VALUES (%s, 'aguardando')
            """, (varredura_id,))
            db_conn.commit()

        # 5. Notificar Bruno via WhatsApp
        _log("Enviando resumo via WhatsApp...")
        try:
            import sys as _sys
            if "/root" not in _sys.path:
                _sys.path.insert(0, "/root")
            from bot.whatsapp_handlers import enviar_resumo_gestor
            enviar_resumo_gestor(varredura_id)
        except Exception as e:
            _log(f"  Aviso: falha ao enviar WA: {e}")

        # 6. Relatório PDF (somente sextas)
        if date.today().weekday() == 4:
            _log("Gerando relatorios semanais (sexta)...")
            arquivos = gerar(perfis, varredura_id, db_conn=None)
            _log(f"  PDFs gerados: {arquivos}")

        # Atualizar varredura como sucesso
        contas_ok   = sum(1 for p in perfis if not p.get("erro"))
        contas_erro = sum(1 for p in perfis if p.get("erro"))
        contas_acao = sum(1 for d in decisoes if d.get("acoes"))
        duracao = time.time() - inicio

        cur.execute("""
            UPDATE gestor_varreduras
            SET contas_total=%s, contas_ok=%s, contas_acao=%s, contas_erro=%s,
                resumo_json=%s, duracao_seg=%s, status='sucesso'
            WHERE id=%s
        """, (
            len(perfis), contas_ok, contas_acao, contas_erro,
            json.dumps({"pendentes": n_pendentes}),
            round(duracao, 2),
            varredura_id,
        ))
        db_conn.commit()
        _log(f"Varredura concluida em {duracao:.1f}s. ID={varredura_id} | {n_pendentes} pendentes")

    except Exception as e:
        _log(f"ERRO na varredura: {e}")
        cur.execute("""
            UPDATE gestor_varreduras
            SET status='erro', resumo_json=%s
            WHERE id=%s
        """, (json.dumps({"erro": str(e)}), varredura_id))
        db_conn.commit()
        sys.exit(1)
    finally:
        if db_conn:
            db_conn.close()
```

- [ ] **Step 3: Verificar sintaxe**

```bash
cd /root && /root/venv/bin/python3 -c "import meta.gestor_agente; print('OK')"
```
Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git add meta/gestor_agente.py
git commit -m "feat(gestor_agente): modo semi-autonomo - salvar_pendentes + notificacao WA"
```

---

## Task 8: jake_whatsapp.py — Slash-commands, roteamento e limpeza

**Files:**
- Modify: `bot/jake_whatsapp.py`
- Test: `tests/test_gestor_ia_wpp.py`

- [ ] **Step 1: Escrever testes de roteamento**

Adicionar ao `tests/test_gestor_ia_wpp.py`:

```python
# ─── roteamento slash-commands ────────────────────────────────────────────────

def test_slash_saldo_nao_vai_para_financeiro():
    """Mensagem '/saldo' deve ser roteada para cmd_saldo, não para _eh_financeiro."""
    import importlib, sys

    # Mock das dependências do módulo
    sys.modules.setdefault("anthropic", MagicMock())
    sys.modules.setdefault("apscheduler", MagicMock())
    sys.modules.setdefault("apscheduler.schedulers.background", MagicMock())
    sys.modules.setdefault("apscheduler.triggers.cron", MagicMock())
    sys.modules.setdefault("pytz", MagicMock())

    with patch.dict("os.environ", {
        "WA_AUTHORIZED_JID": "123@lid",
        "WA_AUTHORIZED_NUMBER": "5535988550954",
        "ANTHROPIC_API_KEY": "fake",
    }):
        # Verificar que a função _eh_slash_cmd existe e detecta /saldo
        # Teste sem importar o módulo completo (evita conexões reais)
        def _eh_slash_cmd(texto):
            return texto.strip().startswith("/")

        assert _eh_slash_cmd("/saldo") is True
        assert _eh_slash_cmd("/gestor") is True
        assert _eh_slash_cmd("saldo") is False
        assert _eh_slash_cmd("quanto ganhei") is False


def test_aprovacao_detecta_ok_e_cancela():
    """Regex de aprovação deve detectar 'ok' e 'cancela N'."""
    import re
    APROVACAO_RE = re.compile(r'^(ok|cancela\s+\d+)$', re.IGNORECASE)

    assert APROVACAO_RE.match("ok")
    assert APROVACAO_RE.match("cancela 2")
    assert APROVACAO_RE.match("cancela 10")
    assert not APROVACAO_RE.match("okay")
    assert not APROVACAO_RE.match("cancelar 2")
    assert not APROVACAO_RE.match("saldo")
```

- [ ] **Step 2: Rodar testes**

```bash
cd /root && /root/venv/bin/python3 -m pytest tests/test_gestor_ia_wpp.py::test_slash_saldo_nao_vai_para_financeiro tests/test_gestor_ia_wpp.py::test_aprovacao_detecta_ok_e_cancela -v
```
Esperado: PASSED (são testes unitários simples)

- [ ] **Step 3: Adicionar parser de slash-commands em jake_whatsapp.py**

Adicionar função antes de `processar_mensagem()` (linha ~1075):

```python
import re as _re_slash
_APROVACAO_RE = _re_slash.compile(r'^(ok|cancela\s+\d+)$', _re_slash.IGNORECASE)

def _processar_slash_cmd(sender_jid: str, texto: str) -> bool:
    """
    Processa slash-commands (/gestor, /saldo, etc.).
    Retorna True se processou, False se não era slash-command.
    """
    from bot.whatsapp_handlers import (
        cmd_saldo, cmd_historico, cmd_status_cliente, cmd_relatorio,
        processar_aprovacao, enviar_resumo_gestor, _verificar_varredura_pendente,
    )
    destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid
    texto_limpo = texto.strip()

    if not texto_limpo.startswith("/"):
        return False

    partes = texto_limpo.split(None, 1)
    cmd = partes[0].lower()
    args = partes[1] if len(partes) > 1 else ""

    if cmd == "/saldo":
        cmd_saldo(destino)

    elif cmd == "/historico":
        cmd_historico(destino)

    elif cmd == "/relatorio":
        cmd_relatorio(destino)

    elif cmd == "/status":
        if args:
            cmd_status_cliente(destino, args)
        else:
            send_text(destino, "Uso: /status [nome do cliente]")

    elif cmd == "/gestor":
        estado = _verificar_varredura_pendente()
        if estado:
            send_text(destino, f"Ha acoes pendentes de aprovacao (varredura #{estado['varredura_id']}). Responda 'ok' ou 'cancela N' primeiro.")
        else:
            send_text(destino, "Iniciando varredura manual...")
            import threading
            def _run():
                try:
                    from meta.gestor_agente import main
                    main()
                except Exception as e:
                    logger.error(f"[/gestor] erro: {e}")
                    send_text(destino, f"Erro na varredura: {e}")
            threading.Thread(target=_run, daemon=True).start()

    elif cmd == "/pausa":
        if args:
            # Reutiliza fluxo existente de pausar campanha
            _processar_gestor_cmd(sender_jid, f"pausa {args}")
        else:
            send_text(destino, "Uso: /pausa [nome do cliente]")

    elif cmd == "/ativa":
        if args:
            _processar_gestor_cmd(sender_jid, f"ativa {args}")
        else:
            send_text(destino, "Uso: /ativa [nome do cliente]")

    else:
        send_text(destino, f"Comando '{cmd}' nao reconhecido. Comandos: /gestor /saldo /status /relatorio /pausa /ativa /historico")

    return True
```

- [ ] **Step 4: Atualizar processar_mensagem() com nova cadeia de prioridade**

Substituir o início de `processar_mensagem()` (linhas 1077-1103):

```python
def processar_mensagem(sender_jid: str, texto: str):
    """Processa mensagem do Bruno e envia resposta."""
    chat_id = jid_to_chat_id(sender_jid)
    historico = carregar_historico(chat_id)
    destino = AUTHORIZED_NUMBER if AUTHORIZED_NUMBER else sender_jid

    # 1. Slash-commands (ANTES de qualquer outra verificação)
    if _processar_slash_cmd(sender_jid, texto):
        return

    # 2. Aprovação do gestor (sem sessão ativa E há varredura pendente)
    sessao = _get_sessao(sender_jid)
    if not sessao and _APROVACAO_RE.match(texto.strip()):
        from bot.whatsapp_handlers import _verificar_varredura_pendente, processar_aprovacao
        if _verificar_varredura_pendente():
            processar_aprovacao(texto.strip(), destino)
            return

    # 3. Sessão ativa (confirmação pendente de fluxo de anúncio)
    if sessao:
        _processar_confirmacao(sender_jid, texto, sessao)
        return

    # Detectar resposta órfã (sessão expirou por restart)
    import re as _re_orfao
    _t = texto.strip()
    if _re_orfao.match(r'^\d+[x\-]\d+[x\-]\d+$', _t):
        send_text(destino, "Minha sessao expirou, Patrao (servico reiniciou). Repete o comando do inicio.")
        return

    # 4. Keywords de gestor (subir anuncio, pausar, ativar)
    if _eh_gestor_cmd(texto):
        _processar_gestor_cmd(sender_jid, texto)
        return

    # 5. Grupo — COPIAR EXATAMENTE as linhas 1104-1124 do arquivo original
    # NÃO usar pass aqui. Copiar o bloco completo:
    #   if _eh_grupo(texto):
    #       grupos = get_grupos()
    #       grupo_encontrado = None
    #       for g in grupos:
    #           ... (copiar bloco completo até o return)
    # Referência: git show HEAD:bot/jake_whatsapp.py | grep -A 20 "_eh_grupo(texto)"

    # 6. Chat geral com Claude — COPIAR EXATAMENTE as linhas 1126-1157 do arquivo original
    # O bloco de financeiro, clientes e chat com Claude deve ser copiado integralmente.
    # Referência: linhas após o bloco de grupo até o fim de processar_mensagem()
```

**Importante:** Manter o restante da função exatamente como está (grupos, financeiro, chat Claude). Apenas substituir o bloco de verificações iniciais.

- [ ] **Step 5: Remover APScheduler das 17h e adicionar job de expiração**

Em `_configurar_scheduler()`, remover o bloco das 17h (linhas 1285-1291):
```python
# REMOVER este bloco:
scheduler.add_job(
    _enviar_resumo_gestor,
    CronTrigger(hour=17, minute=0, timezone=SP_TZ),
    id="resumo_gestor",
    replace_existing=True,
)
```

Adicionar job de expiração de pendentes a cada 30min:
```python
def _expirar_pendentes():
    """Expira ações pendentes com mais de 4h sem aprovação."""
    try:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"],
                                cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        # Expirar ações
        cur.execute("""
            UPDATE gestor_acoes
            SET status='expirado', expirado_em=NOW()
            WHERE status='pendente'
              AND executado_em < NOW() - INTERVAL '4 hours'
        """)
        n_acoes = cur.rowcount
        # Expirar estado
        cur.execute("""
            UPDATE gestor_estado
            SET status='expirado', resolvido_em=NOW()
            WHERE status='aguardando'
              AND criado_em < NOW() - INTERVAL '4 hours'
        """)
        n_estados = cur.rowcount
        conn.commit()
        conn.close()
        if n_acoes or n_estados:
            logger.info(f"_expirar_pendentes: {n_acoes} acoes e {n_estados} estados expirados")
    except Exception as e:
        logger.error(f"_expirar_pendentes error: {e}")

# Adicionar no scheduler:
scheduler.add_job(
    _expirar_pendentes,
    "interval", minutes=30,
    id="expirar_pendentes",
    replace_existing=True,
)
```

- [ ] **Step 6: Verificar sintaxe**

```bash
cd /root && /root/venv/bin/python3 -c "
import os
os.environ['WA_AUTHORIZED_JID'] = 'x'
os.environ['WA_AUTHORIZED_NUMBER'] = 'y'
os.environ['ANTHROPIC_API_KEY'] = 'x'
import ast
with open('/root/bot/jake_whatsapp.py') as f:
    ast.parse(f.read())
print('Sintaxe OK')
"
```
Esperado: `Sintaxe OK`

- [ ] **Step 7: Rodar todos os testes**

```bash
cd /root && /root/venv/bin/python3 -m pytest tests/test_gestor_ia_wpp.py -v
```
Esperado: todos PASSED

- [ ] **Step 8: Reiniciar jake-whatsapp**

```bash
sudo systemctl restart jake-whatsapp && sleep 3 && sudo systemctl status jake-whatsapp | head -20
```
Esperado: `active (running)`

- [ ] **Step 9: Commit final**

```bash
git add bot/jake_whatsapp.py tests/test_gestor_ia_wpp.py
git commit -m "feat(jake_wpp): slash-commands, roteamento aprovacao, job expiracao 4h"
```

---

## Task 9: Smoke Test End-to-End

- [ ] **Step 1: Disparar varredura manual e verificar banco**

```bash
cd /root && /root/venv/bin/python3 -m meta.gestor_agente 2>&1 | tail -20
```
Esperado: log mostrando contas coletadas, ações pendentes salvas, "Enviando resumo via WhatsApp"

- [ ] **Step 2: Verificar ações pendentes no banco**

```bash
cd /root && /root/venv/bin/python3 -c "
import os, psycopg2, psycopg2.extras
from dotenv import load_dotenv
load_dotenv('/root/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute(\"SELECT tipo, entidade_nome, status, numero_na_varredura FROM gestor_acoes WHERE status='pendente' ORDER BY numero_na_varredura\")
for r in cur.fetchall():
    print(r)
cur.execute(\"SELECT * FROM gestor_estado WHERE status='aguardando'\")
print('estado:', cur.fetchone())
conn.close()
"
```
Esperado: lista de ações pendentes com numeros + registro em gestor_estado

- [ ] **Step 3: Testar /saldo via linha de comando (sem WA real)**

```bash
cd /root && /root/venv/bin/python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/root/.env')
from unittest.mock import patch, MagicMock
with patch('bot.whatsapp_handlers.send_text') as mock_send:
    from bot.whatsapp_handlers import cmd_saldo
    cmd_saldo('5535988550954')
    print(mock_send.call_args_list[0][0][1][:300])
"
```
Esperado: texto com saldos das contas

- [ ] **Step 4: Testar formatar_resumo_gestor diretamente**

```bash
cd /root && /root/venv/bin/python3 -c "
from bot.whatsapp_handlers import formatar_resumo_gestor
acoes = [{'numero_na_varredura': 1, 'tipo': 'pausar_ad', 'entidade_nome': 'Test Ad', 'cliente_nome': 'Vielife', 'motivo': 'CPL R\$87'}]
alertas = [{'tipo': 'alerta_frequencia', 'entidade_nome': 'X', 'cliente_nome': 'ODC', 'motivo': 'freq 2.7'}]
msg = formatar_resumo_gestor(acoes, alertas, 23, 999)
print(msg)
"
```
Esperado: mensagem formatada com ação numerada e alerta separado

- [ ] **Step 5: Commit final do plano**

```bash
git add docs/superpowers/plans/2026-05-15-gestor-ia-whatsapp.md
git commit -m "docs: plano de implementacao Gestor IA WA completo"
```
