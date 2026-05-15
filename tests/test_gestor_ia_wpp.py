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

    # NÃO deve ter chamado Meta API — verificar que nenhuma call tem "PAUSED"
    paused_calls = [c for c in mock_cur.execute.call_args_list if "PAUSED" in str(c)]
    assert len(paused_calls) == 0, "salvar_pendentes nao deve chamar Meta API"


def test_salvar_pendentes_numera_so_acoes():
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

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    with patch("meta.gestor.executor._get_db", return_value=mock_conn):
        with patch("meta.gestor.executor._resolve_token", return_value="tok"):
            total = salvar_pendentes(decisoes, perfis, varredura_id=1, db_conn=mock_conn)

    assert total == 2  # 2 ações (não conta alertas)


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


# ─── duplicar_ad ──────────────────────────────────────────────────────────────

def test_duplicar_ad_cria_adset_e_anuncio():
    """duplicar_ad() deve criar novo adset e novo ad baseado no original."""
    from meta.meta_api import duplicar_ad
    from unittest.mock import patch

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
                    # Mock da chamada requests para buscar page_id do creative
                    mock_resp = MagicMock()
                    mock_resp.json.return_value = {"object_story_spec": {"page_id": "pg_1"}}
                    with patch("meta.meta_api.requests.get", return_value=mock_resp):
                        novo_id = duplicar_ad("tok", "act_123", "ad_111")

    assert novo_id == "ad_novo_111"
    mock_cs.assert_called_once()
    mock_ca.assert_called_once()


# ─── formatar_resumo_gestor ───────────────────────────────────────────────────

def test_formatar_resumo_gestor_com_acoes_e_alertas():
    """formatar_resumo_gestor() deve formatar ações numeradas + alertas separados."""
    from bot.whatsapp_handlers import formatar_resumo_gestor

    acoes = [
        {"numero_na_varredura": 1, "tipo": "pausar_ad", "entidade_nome": "Criativo X",
         "cliente_nome": "Vielife", "motivo": "CPL R$87 (media R$52)"},
        {"numero_na_varredura": 2, "tipo": "escalar_orcamento", "entidade_nome": "Adset Y",
         "cliente_nome": "Castaldi", "motivo": "CPL R$18 otimo"},
    ]
    alertas = [
        {"tipo": "alerta_saldo", "entidade_nome": "ODC",
         "cliente_nome": "ODC Massaranduba", "motivo": "freq 2.7"},
    ]

    msg = formatar_resumo_gestor(acoes, alertas, total_contas=23, varredura_id=42)

    assert msg is not None
    assert "23 contas" in msg
    assert "1." in msg
    assert "PAUSAR AD" in msg.upper()
    assert "2." in msg
    assert "Alertas" in msg
    assert "freq 2.7" in msg
    assert "ok" in msg.lower()
    assert "cancela" in msg.lower()
    assert "4h" in msg


def test_formatar_resumo_gestor_silencio_sem_acoes_alertas():
    """Se não há ações nem alertas, retorna None."""
    from bot.whatsapp_handlers import formatar_resumo_gestor
    assert formatar_resumo_gestor([], [], total_contas=23, varredura_id=1) is None


def test_formatar_resumo_gestor_so_alertas_sem_bloco_aprovacao():
    """Só alertas: mensagem não pede ok/cancela."""
    from bot.whatsapp_handlers import formatar_resumo_gestor

    alertas = [{"tipo": "alerta_frequencia", "entidade_nome": "X",
                "cliente_nome": "Vielife", "motivo": "freq 2.7"}]
    msg = formatar_resumo_gestor([], alertas, total_contas=23, varredura_id=1)

    assert msg is not None
    assert "freq 2.7" in msg
    assert "cancela" not in msg.lower()


# ─── processar_aprovacao ──────────────────────────────────────────────────────

def test_processar_aprovacao_ok_executa_tudo():
    """'ok' deve chamar executar_aprovadas com canceladas=[]."""
    from bot.whatsapp_handlers import processar_aprovacao

    with patch("bot.whatsapp_handlers._verificar_varredura_pendente",
               return_value={"varredura_id": 42, "id": 1}):
        with patch("bot.whatsapp_handlers.executar_aprovadas",
                   return_value={"ok": 2, "erro": 0, "canceladas": 0}) as mock_exec:
            with patch("bot.whatsapp_handlers.send_text"):
                with patch("bot.whatsapp_handlers._marcar_estado_resolvido"):
                    processar_aprovacao("ok", "5535988550954")

    mock_exec.assert_called_once_with(varredura_id=42, canceladas=[])


def test_processar_aprovacao_cancela_n():
    """'cancela 2' deve chamar executar_aprovadas com canceladas=[2]."""
    from bot.whatsapp_handlers import processar_aprovacao

    with patch("bot.whatsapp_handlers._verificar_varredura_pendente",
               return_value={"varredura_id": 42, "id": 1}):
        with patch("bot.whatsapp_handlers._db") as mock_db:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.side_effect = [
                (1,),   # existe=True
                (3,),   # total=3
            ]
            mock_db.return_value = mock_conn
            with patch("bot.whatsapp_handlers.executar_aprovadas",
                       return_value={"ok": 2, "erro": 0, "canceladas": 1}) as mock_exec:
                with patch("bot.whatsapp_handlers.send_text"):
                    with patch("bot.whatsapp_handlers._marcar_estado_resolvido"):
                        processar_aprovacao("cancela 2", "5535988550954")

    mock_exec.assert_called_once_with(varredura_id=42, canceladas=[2])
