# Jake IA — Matriz de agentes (roteador)

Referência para evoluir prompts e comandos. Cada agente pode ter o prompt em arquivo separado depois.

| Agente | Gatilho | Prompt (atual) | Ação |
|--------|--------|----------------|------|
| **Analista Sênior** | Mensagem de texto (não comando) | `PROMPT_ANALISTA` em `jake_telegram.py` | Saldo/relatório → Meta; senão → Claude com esse prompt. |
| **Diretor de Copy** | `/copy [tema]` | `PROMPT_COPY` | Se tema vazio → pede tema. Senão → Claude com tema. |
| **Operador de Tráfego** | `/subir [dados]` | `PROMPT_OPERADOR` | Se vazio → pede dados. Senão → Claude com dados. |

## Evoluir os prompts

- **Agora:** os 3 prompts estão como constantes no topo de `jake_telegram.py` (`PROMPT_ANALISTA`, `PROMPT_COPY`, `PROMPT_OPERADOR`). Você pode editar direto lá.
- **Depois:** pode criar um arquivo por agente (ex.: `prompts/analista.txt`, `prompts/copy.txt`, `prompts/operador.txt`) e no `main` carregar com `open(...).read()`. A função `chamar_claude(prompt_sistema, texto_usuario)` continua igual; só muda de onde vem o `prompt_sistema`.

## Comando matriz mais estruturado

Se quiser um “comando matriz” único (ex.: `/agente copy tema aqui`), dá para adicionar um `CommandHandler("agente", cmd_agente)` que lê o primeiro argumento (`copy`, `subir`, `analista`) e roteia para o prompt certo. Por enquanto o desenho com `/copy` e `/subir` separados deixa claro quem responde e é fácil de usar.
