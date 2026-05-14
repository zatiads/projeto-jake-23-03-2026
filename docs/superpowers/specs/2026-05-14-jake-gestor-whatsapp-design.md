# Jake Gestor via WhatsApp — Fase 1

**Data:** 2026-05-14
**Status:** aprovado pelo usuário

## Objetivo

Permitir que Bruno execute comandos de gestão de tráfego via WhatsApp usando linguagem natural. Fase 1 cobre: subir anúncios a partir de link do Google Drive e pausar/ativar campanhas em múltiplos clientes.

## Arquitetura

```
WhatsApp (Bruno)
      |
Evolution API → jake_whatsapp.py (porta 5052)
      |
  Claude interpreta mensagem
  extrai: intenção + parâmetros
      |
  gestor_whatsapp.py
  (orquestra chamadas ao Jake OS)
      |
  Jake OS (localhost:5050)
  endpoints de anúncios existentes
      |
  Resposta via WhatsApp
```

Jake WhatsApp atua como frontend de voz. Jake OS executa toda a lógica de negócio — nenhuma lógica de Meta API é duplicada.

## Intenções Suportadas

| Intenção | Exemplo de mensagem |
|---|---|
| `subir_anuncio` | "Sobe esse vídeo [link] para Cordeirópolis e Tijucas, R$30" |
| `pausar_campanha` | "Pausa todas as campanhas do Schroeder" |
| `ativar_campanha` | "Ativa campanhas do Tijucas" |

## Componentes

### 1. `jake_whatsapp.py` — modificações

- Nova função `interpretar_comando(texto) -> dict` — chama Claude com prompt estruturado, retorna JSON:
  ```json
  {
    "intencao": "subir_anuncio",
    "drive_link": "https://drive.google.com/...",
    "clientes": ["cordeirópolis", "tijucas"],
    "orcamento": 30,
    "campanha_tipo": "MESSAGES"
  }
  ```
- Nova função `resolver_clientes(nomes) -> list` — fuzzy match contra `ad_client_profiles` no banco
- Dicionário `_sessoes` em memória — gerencia estado de conversa por JID com TTL de 10 minutos
- Handler de mensagens ganha roteamento por intenção

### 2. `bot/gestor_whatsapp.py` — módulo novo

Responsabilidades:
- `subir_anuncio(clientes, drive_link, orcamento, campanha_tipo)` — orquestra chamadas ao Jake OS
- `pausar_campanha(cliente_id, campanha_id)` — chama Meta via Jake OS
- `ativar_campanha(cliente_id, campanha_id)` — chama Meta via Jake OS
- `listar_campanhas(cliente_id)` — busca campanhas ativas para confirmação antes de pausar/ativar
- Autenticação Jake OS: login único com cookie de sessão reutilizado

### 3. Autenticação Jake OS

Jake OS usa `@login_required` (sessão Flask). `gestor_whatsapp.py` faz login em `POST /auth/login` na inicialização e reutiliza o cookie. Se cookie expirar, faz re-login automático.

## Fluxo Detalhado — Subir Anúncio

```
1. Bruno: "Sobe esse vídeo [link] para Cordeirópolis e Tijucas, R$30"

2. interpretar_comando() → extrai intenção + parâmetros

3. resolver_clientes(["cordeirópolis", "tijucas"]):
   - match > 80%: usa direto
   - match 50-80%: pergunta "Encontrei Odontocompany Cordeirópolis, é esse?"
   - nenhum match: "Não encontrei esse cliente. Quer listar os disponíveis?"

4. Jake: "Vou subir para:
   • Odontocompany Cordeirópolis (act_2152...)
   • ODC Tijucas (act_1497...)
   Orcamento: R$30/dia cada | Tipo: MESSAGES
   Confirma? (sim/nao)"

5. Bruno: "sim"

6. Jake chama Jake OS em sequência:
   POST /api/anuncios/lote/drive-download → {meta_handle}
   POST /api/anuncios/multi-cliente/preparar → {mc_token}
   GET  /api/anuncios/multi-cliente/stream/<mc_token> → consome SSE

7. Jake reporta resultado:
   "Anuncio subido!
   • Cordeiropolis: OK (camp. 123)
   • Tijucas: OK (camp. 456)
   2/2 concluidos"
```

## Fluxo Detalhado — Pausar/Ativar

```
1. Bruno: "Pausa todas as campanhas do Schroeder"

2. Jake busca campanhas ativas de ODC Schroeder via Jake OS

3. Jake: "Vou pausar 3 campanhas ativas em ODC Schroeder:
   - [nome campanha 1]
   - [nome campanha 2]
   - [nome campanha 3]
   Confirma? (sim/nao)"

4. Bruno: "sim"

5. Jake pausa via Meta API (Jake OS) e reporta:
   "3/3 campanhas pausadas em ODC Schroeder"
```

## Gerenciamento de Estado

```python
_sessoes = {
  "5535988550954@lid": {
    "estado": "aguardando_confirmacao_subida",
    "payload": { ... },
    "expira_em": timestamp
  }
}
```

Estados possíveis:
- `aguardando_confirmacao_clientes` — resolvendo ambiguidade de cliente
- `aguardando_confirmacao_subida` — resumo montado, esperando sim/não
- `executando` — em progresso, bloqueia novo comando

TTL: 10 minutos. Mensagem fora de contexto reinicia o fluxo.

## Tratamento de Erros

| Cenário | Mensagem para Bruno |
|---|---|
| Jake OS fora do ar | "Jake OS nao esta respondendo. Verifica se esta rodando (porta 5050)" |
| Erro Meta API | Mensagem de erro traduzida, sem stacktrace |
| Drive inacessivel | "Nao consegui acessar o arquivo. O link esta publico?" |
| Timeout > 2min | "Ta demorando mais que o normal. Te aviso quando terminar" |
| Nenhum cliente encontrado | "Nao encontrei esse cliente. Quer listar os disponiveis?" |
| Já executando | "Ainda processando o lote anterior, aguarda..." |

## Defaults

- `campanha_tipo`: `MESSAGES` se não informado
- `orcamento`: valor do cadastro do cliente (`orcamento_diario`) se não informado; se não tiver cadastrado, pergunta

## Arquivos

| Arquivo | Acao |
|---|---|
| `/root/bot/jake_whatsapp.py` | Modificar — adicionar interpretar_comando, resolver_clientes, _sessoes, roteamento |
| `/root/bot/gestor_whatsapp.py` | Criar — módulo de orquestração com Jake OS |

Sem novas tabelas. Sem novo banco. Usa `ad_client_profiles` existente.

## Fora de Escopo (Fase 1)

- Relatórios de performance
- Geração de copies/criativos
- Agendamento de publicações
- Gestão de grupos WhatsApp (Fase 2)
