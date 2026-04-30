# Meta Ads MCP Server — Design Spec

**Data:** 2026-04-30
**Autor:** Jake IA / Bruno
**Status:** Aprovado

---

## Objetivo

Criar um servidor MCP (Model Context Protocol) para Meta Ads que:
1. Serve como backend para o assistente IA do Jake OS (HTTP, porta 5051)
2. Serve como MCP server para Claude Code (stdio)

Ambos os casos reutilizam o código existente em `meta/meta_api.py`. Funções de leitura
(`_get_insights`, `get_saldo_conta`) leem `META_ACCESS_TOKEN` diretamente do módulo —
não aceitam token explícito — portanto `token_key` não se aplica a elas (detalhe abaixo).

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                        VPS /root                         │
│                                                          │
│  ┌──────────────┐    HTTP     ┌─────────────────────┐   │
│  │  Jake OS     │ ──────────► │  Meta MCP Server    │   │
│  │  :5050       │             │  meta/mcp_server.py │   │
│  │  (Flask SPA) │             │  :5051              │   │
│  └──────────────┘             └────────┬────────────┘   │
│                                        │                  │
│  ┌──────────────┐    stdio             │ importa          │
│  │  Claude Code │ ──────────►         │                  │
│  │  (terminal)  │             ┌────────▼────────────┐   │
│  └──────────────┘             │  meta/meta_api.py   │   │
│                               └─────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Componentes

### 1. `meta/mcp_server.py` (novo)

Servidor MCP com dois modos de transporte:
- `--stdio`: modo Claude Code — lê JSON-RPC do stdin, escreve no stdout
- padrão (sem flag): modo HTTP — Flask simples na porta 5051

Implementa o protocolo MCP mínimo:
- `tools/list` — retorna lista de tools disponíveis com schemas JSON
- `tools/call` — executa uma tool e retorna resultado

### 2. `jake_desktop/app.py` (modificado)

Adiciona:
- Função `_chamar_mcp_tool(tool_name: str, args: dict) -> dict` — cliente HTTP para `localhost:5051`
- Injeção das tools Meta no array `tools=[]` do OpenAI function calling quando o chat de relatórios/tráfego está ativo
- Degradação graciosa: se o servidor MCP não estiver disponível, chat funciona sem tools

### 3. `scripts/subir_jake.sh` (modificado)

Adiciona linha para subir `mcp_server.py` em background (nohup, porta 5051) antes do Jake OS.

### 4. `/root/.claude/settings.json` (modificado)

Registra o servidor MCP para Claude Code:
```json
{
  "mcpServers": {
    "meta-ads": {
      "command": "/root/venv/bin/python3",
      "args": ["/root/meta/mcp_server.py", "--stdio"],
      "env": {}
    }
  }
}
```

---

## Tools MCP

### Ferramentas de leitura (sem token_key)

Estas funções leem `META_ACCESS_TOKEN` diretamente do módulo `config_meta.py`.

| Tool | Parâmetros | Função em meta_api.py |
|------|------------|----------------------|
| `meta_get_insights` | `account_id`, `days` (int, default 7) | `_get_insights()` |
| `meta_get_saldo` | `account_id` | `get_saldo_conta()` |

### Ferramentas de escrita (com token_key)

Aceitam `token_key` que é resolvido via `_resolve_token()` antes de chamar a função.
`token_key` deve ser um de: `META_TOKEN_PILOTI`, `META_TOKEN_DENTTO`, `META_ACCESS_TOKEN`.

| Tool | Parâmetros | Função em meta_api.py |
|------|------------|----------------------|
| `meta_listar_campanhas` | `token_key`, `account_id` | `listar_campanhas()` |
| `meta_criar_campanha` | `token_key`, `account_id`, `nome`, `campanha_tipo`, `orcamento`, `cbo` | `criar_campanha()` |
| `meta_criar_conjunto` | `token_key`, `account_id`, `campaign_id`, `campanha_tipo`, `publico`, `localizacao`, `orcamento` | `criar_conjunto()` |
| `meta_criar_anuncio` | `token_key`, `account_id`, `adset_id`, `page_id`, `creative_ref`, `titulo`, `texto`, `cta` | `criar_anuncio()` |
| `meta_upload_imagem` | `token_key`, `account_id`, `imagem_base64`, `filename` | `upload_imagem()` |
| `meta_upload_video` | `token_key`, `account_id`, `video_base64`, `filename` | `upload_video()` |
| `meta_deletar_objeto` | `token_key`, `objeto_id` | `deletar_objeto_meta()` |

### Schemas de parâmetros complexos

**`creative_ref`** (objeto JSON):
```json
{ "tipo": "imagem", "hash": "<image_hash>" }
{ "tipo": "video",  "video_id": "<video_id>" }
```

**`publico`** (objeto JSON):
```json
{ "idade_min": 18, "idade_max": 65, "genero": [1, 2] }
```
(`genero`: 1=masculino, 2=feminino; omitir para ambos)

**`localizacao`** (objeto JSON):
```json
{
  "paises": ["BR"],
  "cidades": [{ "key": "<city_key>", "radius": 15, "distance_unit": "kilometer" }]
}
```

### Conversões no mcp_server

- `imagem_base64` / `video_base64`: o servidor decodifica (`base64.b64decode`) para `bytes` antes de chamar `upload_imagem` / `upload_video`

**Segurança:** `token_key` é validado contra `VALID_TOKEN_KEYS` no `meta_api.py`. Todas as criações ficam em `PAUSED` por padrão.

---

## Tratamento de erros

Todas as chamadas a `meta_api.py` são envolvidas em `try/except`. Em caso de exceção:

- **Modo stdio (JSON-RPC):** retorna `{"jsonrpc": "2.0", "id": <id>, "error": {"code": -32000, "message": "<str(e)>"}}`
- **Modo HTTP:** retorna HTTP 200 com `{"ok": false, "error": "<str(e)>"}`

Funções que retornam `None` (ex: `_get_insights` em falha de rede) são tratadas como erro com mensagem `"Sem dados retornados pela Meta API"`.

---

## Fluxo Jake OS

```
Usuário digita: "relatório da semana da Piloti"
  → GPT-4o recebe tools no system prompt
  → decide: tool=meta_get_insights, args={account_id: "act_...", days: 7}
  → app.py chama POST http://localhost:5051/call {tool, args}
  → mcp_server executa meta_api._get_insights(account_id, days=7)
  → retorna JSON com métricas
  → GPT-4o formata e exibe ao usuário
```

---

## Fluxo Claude Code

```
Usuário: "lista campanhas da Piloti"
  → Claude Code invoca tool meta_listar_campanhas
  → spawna processo: python3 /root/meta/mcp_server.py --stdio
  → envia JSON-RPC via stdin
  → recebe resultado via stdout
  → apresenta ao usuário
```

---

## Startup e Processo

- `mcp_server.py` sobe via `subir_jake.sh` com `nohup` na porta 5051
- PID gravado em `/tmp/meta_mcp.pid` para controle
- Se cair, Jake OS degrada sem tools (não quebra)
- Logs em `/root/logs/meta_mcp.log`

---

## Dependências

- Python stdlib: `json`, `sys`, `argparse`, `base64`
- Flask (já instalado no venv do projeto)
- `meta/meta_api.py` (sem modificações)
- Variáveis de ambiente existentes no `.env`

Sem novas dependências externas.

---

## O que NÃO está no escopo

- UI no Jake OS para listar tools disponíveis
- Autenticação no endpoint HTTP do MCP (roda só em localhost)
- Suporte a streaming de resultados
- Cache de resultados
