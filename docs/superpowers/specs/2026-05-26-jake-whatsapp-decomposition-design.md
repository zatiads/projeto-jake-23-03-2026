# Design: Decomposição do jake_whatsapp.py

**Data:** 2026-05-26
**Tipo:** Refatoração pura (sem mudança de comportamento)
**Arquivo alvo:** `bot/jake_whatsapp.py` (2319 linhas)

---

## Problema

`jake_whatsapp.py` acumula 6 responsabilidades distintas num único arquivo de 2319 linhas:

1. App Flask + rota `/webhook`
2. Processamento de mensagens e IA
3. Crons (APScheduler) — lembretes, notícias, relatórios
4. Lógica do grupo Casa (lista de compras, menções)
5. Lógica do grupo Viagem Chile
6. Integração com Jake OS via `GestorJakeOS`

Isso dificulta navegar, manter e testar cada parte de forma isolada.

---

## Abordagem escolhida: Extração mínima (Opção A)

Extrair apenas os pedaços com fronteiras naturais (crons e grupos), mantendo `jake_whatsapp.py` como ponto de entrada principal. O systemd e os scripts existentes não precisam mudar.

---

## Estrutura resultante

```
bot/
  jake_whatsapp.py          # Flask, webhook, processamento IA (~800 linhas)
  wa_crons.py               # APScheduler + todos os jobs (~200 linhas)
  wa_grupos/
    __init__.py             # expõe JIDs e handlers
    casa.py                 # grupo Casa (~100 linhas)
    viagem_chile.py         # grupo Viagem Chile (~50 linhas)
  whatsapp_handlers.py      # inalterado (helpers puros)
  gestor_whatsapp.py        # inalterado (cliente Jake OS)
```

---

## Componentes

### `jake_whatsapp.py` (mantido, reduzido)

**Responsabilidade:** Ponto de entrada, app Flask, processamento de IA e webhook.

**Conteúdo:**
- Configuração do app Flask e variáveis de ambiente
- `processar_mensagem(sender_jid, texto)` — lógica de intenção e Claude
- `processar_audio(sender_jid, key, message)` — Whisper
- `processar_midia(sender_jid, key, message, tipo)` — imagens/vídeos
- Rota `POST /webhook` — delega para handlers de grupo quando JID bate
- Rota `GET /health`
- `if __name__ == "__main__"` — inicia Flask + chama `configurar_scheduler(app)`

**Interface com os novos módulos:**
```python
from wa_crons import configurar_scheduler
from wa_grupos import handle_mensagem_casa, handle_mensagem_viagem, CASA_GROUP_JID, VIAGEM_GROUP_JID
```

---

### `wa_crons.py` (novo)

**Responsabilidade:** Toda a lógica de agendamento — nada mais.

**Conteúdo:**
- `configurar_scheduler(app) -> APScheduler` — monta e retorna o scheduler configurado
- `_noticias_diarias()` — resumo IA & Marketing às 07:35
- `_rotina_segunda()`, `_rotina_quarta()`, `_rotina_sexta()` — checks semanais
- `_expirar_pendentes()` — limpa ações/estados expirados no DB
- `_limpar_tmp_midia()` — limpa arquivos temporários
- `_enviar_mensagem_grupo(jid, msg)` — dispatch de lembretes configurados em `wa_grupos.json`
- `_auto_import_recorrentes()` — importação financeira mensal

**Dependências:** `whatsapp_handlers.send_text`, `core.db`, `anthropic`

---

### `wa_grupos/__init__.py`

**Responsabilidade:** Re-exportar o que o webhook precisa.

```python
from .casa import CASA_GROUP_JID, handle_mensagem_casa
from .viagem_chile import VIAGEM_GROUP_JID, handle_mensagem_viagem

__all__ = [
    "CASA_GROUP_JID", "handle_mensagem_casa",
    "VIAGEM_GROUP_JID", "handle_mensagem_viagem",
]
```

---

### `wa_grupos/casa.py` (novo)

**Responsabilidade:** Toda lógica específica do grupo Casa.

**Conteúdo:**
- `CASA_GROUP_JID = "120363310359411409@g.us"`
- `handle_mensagem_casa(texto, key) -> bool`
  - Se mensagem menciona "jake": dispara `processar_mensagem(CASA_GROUP_JID, texto_limpo)` em thread
  - Caso contrário: salva item na tabela `lista_compras` no DB
  - Retorna `True` se processou, `False` se ignorou

**Dependências:** `whatsapp_handlers`, `core.db`, referência circular evitada via import tardio de `processar_mensagem`

---

### `wa_grupos/viagem_chile.py` (novo)

**Responsabilidade:** Toda lógica específica do grupo Viagem Chile.

**Conteúdo:**
- `VIAGEM_GROUP_JID = "120363403675290579@g.us"`
- `VIAGEM_DATA = date(2026, 8, 9)`
- `handle_mensagem_viagem(texto, key) -> bool`
  - Placeholder para lógica futura (pesquisa de restaurantes, passeios, contagem regressiva interativa)
  - Por ora retorna `False` (não processa nada)

---

## Fluxo do webhook após refatoração

```
POST /webhook
  └── event == "messages.upsert"?
        ├── fromMe? → ignora
        ├── sender_jid == CASA_GROUP_JID?
        │     └── handle_mensagem_casa(texto, key) → retorna 200
        ├── sender_jid == VIAGEM_GROUP_JID?
        │     └── handle_mensagem_viagem(texto, key) → retorna 200
        ├── sender_jid == AUTHORIZED_JID?
        │     └── processar_mensagem / processar_audio / processar_midia → retorna 200
        └── outro? → ignora, retorna 200
```

---

## Import circular — solução

`wa_grupos/casa.py` precisa chamar `processar_mensagem()` que vive em `jake_whatsapp.py`. Para evitar import circular:

- `handle_mensagem_casa` recebe `processar_fn` como parâmetro injetado pelo webhook:

```python
# jake_whatsapp.py
from wa_grupos import handle_mensagem_casa

# na rota /webhook:
if sender_jid == CASA_GROUP_JID:
    handle_mensagem_casa(texto, key, processar_fn=processar_mensagem)
    return jsonify({"ok": True})
```

---

## O que NÃO muda

- Comportamento externo — nenhuma resposta, cron ou lógica alterada
- `whatsapp_handlers.py` — inalterado
- `gestor_whatsapp.py` — inalterado
- Configuração systemd (`jake-whatsapp.service`) — inalterada
- `config/wa_grupos.json` — inalterado

---

## Testes

Após refatoração, verificar manualmente:
1. Bot reinicia sem erros (`systemctl restart jake-whatsapp`)
2. Mensagem no grupo Casa é salva na lista de compras
3. `@Jake` no grupo Casa gera resposta de IA
4. Cron de segunda aparece nos logs no horário
5. Mensagem no número pessoal do Bruno gera resposta normal

Não há testes automatizados para o webhook no momento — manter o comportamento atual é suficiente.

---

## Resultado esperado

| Arquivo | Antes | Depois |
|---|---|---|
| `jake_whatsapp.py` | 2319 linhas | ~800 linhas |
| `wa_crons.py` | — | ~200 linhas |
| `wa_grupos/casa.py` | — | ~100 linhas |
| `wa_grupos/viagem_chile.py` | — | ~50 linhas |
| **Total** | 2319 | ~1150 linhas |
