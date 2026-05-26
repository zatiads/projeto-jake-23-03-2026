# Design: Decomposição do jake_whatsapp.py

**Data:** 2026-05-26
**Tipo:** Refatoração pura (sem mudança de comportamento), exceto onde explicitamente marcado como [NOVO]
**Arquivo alvo:** `bot/jake_whatsapp.py` (2319 linhas)

---

## Problema

`jake_whatsapp.py` acumula 6 responsabilidades distintas num único arquivo de 2319 linhas:

1. App Flask + rota `/webhook`
2. Processamento de mensagens e IA
3. Crons (APScheduler) — lembretes, notícias, relatórios
4. Lógica do grupo Casa (lista de compras, menções)
5. Lógica do grupo Viagem Chile [NOVO — ainda não existe no código]
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
  wa_crons.py               # APScheduler + todos os jobs (~220 linhas)
  wa_grupos/
    __init__.py             # expõe JIDs e handlers
    casa.py                 # grupo Casa (~100 linhas)
    viagem_chile.py         # grupo Viagem Chile (~50 linhas) [NOVO]
  whatsapp_handlers.py      # inalterado (helpers puros)
  gestor_whatsapp.py        # inalterado (cliente Jake OS)
```

---

## Componentes

### `jake_whatsapp.py` (mantido, reduzido)

**Responsabilidade:** Ponto de entrada, app Flask, processamento de IA e webhook.

**Conteúdo:**
- Configuração do app Flask e variáveis de ambiente (`AUTHORIZED_JID`, `AUTHORIZED_NUMBER`, `SP_TZ`, etc.)
- `processar_mensagem(sender_jid, texto)` — lógica de intenção e Claude
- `processar_audio(sender_jid, key, message)` — Whisper
- `processar_midia(sender_jid, key, message, tipo)` — imagens/vídeos
- `_cmd_lista_compras()` — **permanece aqui** (chamado por `processar_mensagem` no chat pessoal do Bruno; não é cron nem lógica de grupo)
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

**Globals que re-lê do ambiente** (não recebe de `jake_whatsapp.py`):
```python
AUTHORIZED_NUMBER = os.environ.get("WA_AUTHORIZED_NUMBER", "")
AUTHORIZED_JID    = os.environ.get("WA_AUTHORIZED_JID", "")
SP_TZ             = pytz.timezone("America/Sao_Paulo")
```

**Conteúdo:**
- `configurar_scheduler(app) -> APScheduler` — monta e retorna o scheduler configurado
- `_noticias_diarias()` — resumo IA & Marketing às 07:35
- `_rotina_segunda()`, `_rotina_quarta()`, `_rotina_sexta()` — checks semanais
- `_expirar_pendentes()` — limpa ações/estados expirados no DB
- `_limpar_tmp_midia()` — limpa arquivos temporários
- `_enviar_mensagem_grupo(jid, msg)` — dispatch de lembretes configurados em `wa_grupos.json`
- `_alerta_saldo_baixo()` — verifica saldo Meta Ads e envia alerta se abaixo do limite (atualmente não agendado no scheduler, mas é extraído junto por ser cron-like)
- `_auto_import_recorrentes()` — **promovida de nested para top-level** durante a extração (era função aninhada dentro de `_configurar_scheduler`)

**Dependências:** `whatsapp_handlers.send_text`, `core.db`, `anthropic`, `meta.meta_api`, `os`, `pytz`

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

### `wa_grupos/casa.py` (novo — extração)

**Responsabilidade:** Toda lógica específica do grupo Casa.

**Conteúdo:**
- `CASA_GROUP_JID = "120363310359411409@g.us"`
- `handle_mensagem_casa(texto, key, processar_fn) -> bool`
  - Se mensagem menciona "jake": chama `processar_fn(CASA_GROUP_JID, texto_limpo)` em thread
  - Caso contrário: salva item na tabela `lista_compras` no DB
  - Retorna `True` se processou, `False` se ignorou

**Dependências:** `whatsapp_handlers`, `core.db`

---

### `wa_grupos/viagem_chile.py` (novo — [NOVO, não é extração])

**Responsabilidade:** Toda lógica específica do grupo Viagem Chile.

> **Nota:** Este arquivo NÃO existe no código atual. O webhook hoje não tem branch para este grupo. A criação deste arquivo **adiciona nova lógica** ao webhook (roteamento para `VIAGEM_GROUP_JID`). Isso é intencional e aceito dentro do escopo deste trabalho.

**Conteúdo:**
- `VIAGEM_GROUP_JID = "120363403675290579@g.us"`
- `VIAGEM_DATA = date(2026, 8, 9)`
- `handle_mensagem_viagem(texto, key, processar_fn) -> bool`
  - Por ora retorna `False` (placeholder para lógica futura)

---

## Fluxo do webhook após refatoração

```
POST /webhook
  └── event == "messages.upsert"?
        ├── fromMe? → ignora
        ├── sender_jid == CASA_GROUP_JID?
        │     └── handle_mensagem_casa(texto, key, processar_fn=processar_mensagem) → retorna 200
        ├── sender_jid == VIAGEM_GROUP_JID?  [NOVO]
        │     └── handle_mensagem_viagem(texto, key, processar_fn=processar_mensagem) → retorna 200
        ├── sender_jid == AUTHORIZED_JID?
        │     └── processar_mensagem / processar_audio / processar_midia → retorna 200
        └── outro? → ignora, retorna 200
```

---

## Import circular — solução

`wa_grupos/casa.py` e `wa_grupos/viagem_chile.py` precisam chamar `processar_mensagem()` de `jake_whatsapp.py`. Para evitar import circular, a função é injetada como parâmetro:

```python
# jake_whatsapp.py — na rota /webhook:
from wa_grupos import handle_mensagem_casa, CASA_GROUP_JID

if sender_jid == CASA_GROUP_JID:
    handle_mensagem_casa(texto, key, processar_fn=processar_mensagem)
    return jsonify({"ok": True})
```

```python
# wa_grupos/casa.py:
def handle_mensagem_casa(texto: str, key: dict, processar_fn=None) -> bool:
    if "jake" in texto.lower() and processar_fn:
        # dispara em thread
        ...
```

---

## O que NÃO muda

- Comportamento externo — nenhuma resposta, cron ou lógica alterada (exceto adição do roteamento para Viagem Chile)
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
4. Cron de segunda aparece nos logs no horário agendado
5. Mensagem no número pessoal do Bruno gera resposta normal
6. `/lista` no chat pessoal do Bruno ainda funciona (`_cmd_lista_compras` em `jake_whatsapp.py`)

---

## Resultado esperado

| Arquivo | Antes | Depois |
|---|---|---|
| `jake_whatsapp.py` | 2319 linhas | ~800 linhas |
| `wa_crons.py` | — | ~220 linhas |
| `wa_grupos/casa.py` | — | ~100 linhas |
| `wa_grupos/viagem_chile.py` | — | ~50 linhas [NOVO] |
| **Total** | 2319 | ~1170 linhas |

---

## Notas técnicas

- **`_auto_import_recorrentes`:** era função aninhada em `_configurar_scheduler`. Será promovida a função top-level em `wa_crons.py` durante a extração.
- **`_alerta_saldo_baixo`:** função cron-like existente não agendada no scheduler atual. Extraída para `wa_crons.py` sem alterar seu estado de agendamento.
- **Port inconsistency (pré-existente):** o docstring do arquivo diz `:5051` mas o `main()` roda na porta `5052`. Não será corrigido nesta refatoração para manter o escopo.
