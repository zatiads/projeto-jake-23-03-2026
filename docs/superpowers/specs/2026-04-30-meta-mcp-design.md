# Meta Ads MCP Server — Design Spec

**Data:** 2026-04-30
**Autor:** Jake IA / Bruno
**Status:** Aprovado

---

## Objetivo

Criar um servidor MCP (Model Context Protocol) para Meta Ads que:
1. Serve como backend para o assistente IA do Jake OS (HTTP, porta 5051)
2. Serve como MCP server para Claude Code (stdio)

Ambos os casos reutilizam o código existente em `meta/meta_api.py` sem modificações.

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
│                               │  (sem alterações)   │   │
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
- `tools/list` — retorna lista de tools disponíveis com schemas
- `tools/call` — executa uma tool e retorna resultado

### 2. `jake_desktop/app.py` (modificado)

Adiciona:
- Função `_chamar_mcp_tool(tool_name: str, args: dict) -> dict` — cliente HTTP para localhost:5051
- Injeção das tools Meta no array `tools=[]` do OpenAI function calling quando o chat de relatórios/tráfego está ativo
- Degradação graciosa: se o servidor MCP não estiver disponível, chat funciona sem tools

### 3. `scripts/subir_jake.sh` (modificado)

Adiciona linha para subir `mcp_server.py` em background antes do Jake OS.

### 4. `.claude/settings.json` (modificado)

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

| Tool | Parâmetros principais | Função em meta_api.py |
|------|-----------------------|----------------------|
| `meta_listar_campanhas` | `token_key`, `account_id` | `listar_campanhas()` |
| `meta_get_insights` | `token_key`, `account_id`, `days` | `_get_insights()` |
| `meta_get_saldo` | `token_key`, `account_id` | `get_saldo_conta()` |
| `meta_criar_campanha` | `token_key`, `account_id`, `nome`, `tipo`, `orcamento`, `cbo` | `criar_campanha()` |
| `meta_criar_conjunto` | `token_key`, `account_id`, `campaign_id`, `tipo`, `publico`, `localizacao`, `orcamento` | `criar_conjunto()` |
| `meta_criar_anuncio` | `token_key`, `account_id`, `adset_id`, `page_id`, `creative_ref`, `titulo`, `texto`, `cta` | `criar_anuncio()` |
| `meta_upload_imagem` | `token_key`, `account_id`, `imagem_base64`, `filename` | `upload_imagem()` |
| `meta_upload_video` | `token_key`, `account_id`, `video_base64`, `filename` | `upload_video()` |
| `meta_deletar_objeto` | `token_key`, `objeto_id` | `deletar_objeto_meta()` |

**Segurança:** `token_key` é validado contra `VALID_TOKEN_KEYS` no `meta_api.py` — impede acesso a tokens arbitrários. Todas as criações ficam em `PAUSED` por padrão.

---

## Fluxo Jake OS

```
Usuário digita: "relatório da semana da Piloti"
  → GPT-4o recebe tools no system prompt
  → decide: tool=meta_get_insights, args={token_key: "META_TOKEN_PILOTI", days: 7}
  → app.py chama POST http://localhost:5051/call {tool, args}
  → mcp_server executa meta_api._get_insights(...)
  → retorna JSON com métricas
  → GPT-4o formata e exibe ao usuário
```

---

## Fluxo Claude Code

```
Usuário: "lista campanhas da Piloti"
  → Claude Code invoca tool meta_listar_campanhas
  → spawna processo: python3 mcp_server.py --stdio
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

- Python stdlib: `json`, `sys`, `argparse`, `threading`
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
