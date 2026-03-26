# Jake IA — Roadmap passo a passo

Documento para alinhar a visão e a ordem de implementação. **Não é para fazer tudo de uma vez:** cada bloco pode ser feito em uma etapa.

---

## 1. Alertas financeiros (Meta)

**O que você quer**
- Rotina que verifica o saldo da conta de anúncios no Meta.
- Quando o saldo estiver baixo (ex.: faltando R$ 150 para acabar), o Jake manda um alerta no Telegram: “Conta precisa ser recarregada”.

**Como fazer da melhor forma**
- A **Meta Marketing API** expõe o saldo da conta via endpoint (ex.: `act_XXX` → campos de balance/budget).
- Uma **rotina agendada** (cron no servidor ou task periódica dentro do bot) roda a cada X horas, consulta o saldo, compara com um limite (ex.: 150 reais) e, se estiver abaixo, envia uma mensagem para o seu `AUTHORIZED_ID` no Telegram.
- Configuração: limite em reais (ou dólar, conforme a API) e frequência da checagem (ex.: 1x por dia ou a cada 6h).

**Passos sugeridos**
1. Pesquisar na documentação da Meta o endpoint exato de **saldo da conta** (Ad Account balance/budget).
2. Criar um módulo `meta_balance.py` (ou função em `meta_api.py`) que: recebe `act_XXX`, chama a API e retorna o saldo.
3. Criar um script `checar_saldo_meta.py` que: lê conta e limite do `.env`, chama a função de saldo, e, se saldo < limite, envia mensagem via Telegram (usar o mesmo token do Jake e `bot.send_message(chat_id=AUTHORIZED_ID, text="...")`).
4. Agendar no servidor com **cron** (1x por dia; ex. abaixo) ou, no futuro, uma task assíncrona no próprio bot.

**Dependências**
- Nada novo além do que já temos (Meta token, Telegram bot). Só precisamos do endpoint correto de saldo.

**✅ Implementado**
- `meta_api.get_saldo_conta(account_id)` — retorna amount_spent, spend_cap, remaining (em reais).
- `meta/checar_saldo_meta.py` — lê `.env`, consulta saldo e, se `remaining < META_ALERTA_SALDO_LIMITE`, envia alerta no Telegram.
- Variáveis no `.env`: `META_ALERTA_SALDO_LIMITE` (ex.: 150), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALERT_CHAT_ID`.

**Cron (1x por dia, às 9h):**
```bash
# Editar crontab: crontab -e
# Adicionar linha (checagem 1x por dia às 9h):
0 9 * * * cd /root && PYTHONPATH=/root /root/venv/bin/python3 -m meta.checar_saldo_meta >> /root/logs/log_saldo_meta.log 2>&1
```
Teste manual: `cd /root && PYTHONPATH=/root /root/venv/bin/python3 -m meta.checar_saldo_meta`

---

## 2. Ecossistema de arquivos (Google Drive + Sheets)

**O que você quer**
- Conectar **Google Drive** e **Google Sheets**.
- Jake consegue:
  - **Formatar relatórios em PDF** (dados que já temos ou que vêm de planilha).
  - **Ler planilhas de clientes** que são atualizadas em tempo (quase) real.

**Conseguirá ler planilha no Sheets em tempo real?**
- **Sim.** A API do Google Sheets lê o estado atual da planilha no momento da requisição. Toda vez que o Jake “ler” uma planilha, ele vê os dados como estão naquele instante. Os clientes podem editar no navegador; na próxima leitura pelo Jake, entram as alterações.

**Como fazer da melhor forma**
- **Google Cloud:** um projeto com **Drive API** e **Sheets API** ativadas.
- **Credenciais:** Service Account (recomendado para bot/servidor) ou OAuth (se precisar acessar arquivos “do usuário” em nome dele). Para planilhas e pastas que a agência controla, Service Account costuma ser mais simples.
- **Bibliotecas:** `google-auth`, `google-api-python-client` e/ou `gspread` (mais amigável para Sheets).
- **Fluxos no Jake:**
  - “Ler planilha [nome/link]” → API Sheets → resumo ou uso dos dados (ex.: lista de clientes, métricas).
  - “Gerar relatório PDF do Carazinho” → montar conteúdo (ex.: mesmo texto do relatório atual) → gerar PDF (ex.: `reportlab` ou `weasyprint`) → enviar no Telegram ou subir no Drive.

**Passos sugeridos**
1. Criar projeto no Google Cloud, ativar Drive API e Sheets API, criar Service Account e baixar JSON de credenciais.
2. Compartilhar as planilhas/pastas do Drive com o e-mail da Service Account (ex.: `xxx@projeto.iam.gserviceaccount.com`).
3. Adicionar módulo `google_sheets.py`: autenticar, ler célula/intervalo/aba por ID ou link da planilha.
4. Adicionar módulo `google_drive.py`: listar arquivos, baixar, (opcional) upload de PDF.
5. No Jake (Telegram): comando ou intent “ler planilha [X]” → chama `google_sheets`, responde com resumo ou dados relevantes.
6. Geração de PDF: definir template do relatório (ex.: igual ao que já mandamos no Telegram), usar lib de PDF, gerar arquivo e enviar no Telegram (ou salvar no Drive e mandar link). Integrar com “relatório Carazinho” (Meta + PDF).

**Dependências**
- Conta Google Cloud, credenciais, compartilhamento das planilhas/pastas com a service account.

---

## 3. Linha de produção (Publishing) — Drive → Meta

**O que você quer**
- Rotina em que o Jake:
  - Pega **criativos** (imagens/vídeos) no Drive.
  - **Sobe campanhas** direto pela API do Meta (cria campanha, conjuntos de anúncios, anúncios com esses criativos).
- Objetivo: não precisar abrir o Gerenciador de anúncios para publicar.

**Como fazer da melhor forma**
- **Ordem lógica:** primeiro temos Drive (passo 2) e Meta (já temos insights e stub de criação). Depois definimos um “padrão” de como você organiza no Drive (ex.: pasta por campanha, dentro dela: brief.txt ou planilha com nome da campanha, objetivo, orçamento, e pasta “criativos” com imagens/vídeos).
- **Meta API:** criar campanha (`campaigns`), ad set (`adsets`), ad creative (imagem ou vídeo) e anúncio (`ads`). Criativos: upload por URL (o Meta baixa da URL pública) ou upload de arquivo via API.
- **Fluxo possível:** você manda no Telegram “subir campanha Carazinho Black Friday” → Jake lê no Drive a pasta/planilha com esse nome, pega objetivo, orçamento e criativos, e chama a API do Meta em sequência (campaign → ad set → creative → ad).

**Passos sugeridos**
1. Implementar no Meta (em `meta_api.py` ou módulo separado) a criação real de campanha: `campaigns` (name, objective, etc.), depois `adsets` (campaign_id, daily_budget, targeting), depois `adcreatives` (com image_url ou video_id) e `ads` (ad set + creative). Testar com uma campanha de teste.
2. Definir convenção no Drive: estrutura de pastas e/ou planilha com colunas (nome campanha, objetivo, orçamento diário, link da imagem, texto do anúncio, etc.).
3. Módulo `publishing.py`: dado o nome da campanha, (a) lê Drive/Sheets conforme a convenção, (b) baixa ou obtém URL dos criativos, (c) chama Meta para criar campanha + ad set + criativo + anúncio.
4. No Jake: comando `/publicar campanha X` ou “subir campanha X” que chama `publishing` e responde no Telegram com o resultado (sucesso ou erro).

**Dependências**
- Drive + Sheets (passo 2) e permissões Meta (ads_management) já previstas. Ordem: depois dos alertas e do ecossistema de arquivos.

---

## 4. Fase 7 — Sala de comando (front-end visual)

**O que você quer**
- Painel web profissional, com a sua marca.
- Tirar a operação “pesada” do Telegram e centralizar em um **sistema próprio**: dashboard, relatórios, campanhas, alertas, etc.
- Telegram pode continuar como canal de alertas e ações rápidas.

**Como fazer da melhor forma**
- **Backend:** API (FastAPI, Flask ou similar) que reutiliza toda a lógica que o Jake já usa ou virá a usar: Meta (insights, saldo, criação de campanhas), Google (Sheets, Drive), geração de PDF, regras de alerta. Ou seja: os módulos (meta_api, google_sheets, publishing, etc.) viram serviços chamados pela API.
- **Front-end:** SPA (React, Next.js, Vue, etc.) ou até algo mais simples (HTML + JS) que consome essa API: login (você/equipe), dashboard, lista de clientes, relatórios, campanhas, configuração de alertas, “publicar campanha” com dados vindos do painel.
- **Auth:** login/senha ou OAuth para acessar o painel (apenas você ou equipe).
- **Host:** mesmo servidor (por trás de um proxy reverso) ou VPS/cloud; HTTPS obrigatório.

**Passos sugeridos**
1. Definir stack (ex.: FastAPI + React ou Next) e onde hospedar.
2. Desenhar telas principais: Dashboard, Clientes, Relatórios (Meta + PDF), Campanhas (listar + publicar), Alertas (configurar limite de saldo, histórico), Configurações (conta Meta, Google, etc.).
3. Implementar a API que expõe as mesmas ações que o Jake faz (relatório, saldo, ler planilha, publicar campanha) em endpoints REST.
4. Implementar o front-end tela a tela, consumindo a API.
5. Manter o bot do Telegram para: alertas automáticos (ex.: saldo baixo) e, se quiser, comandos rápidos (ex.: “relatório carazinho 7”) que chamam a mesma API.

**Dependências**
- Tudo que vier antes (alertas, Drive/Sheets, publishing) vira “serviço” atrás da API; o front só orquestra e exibe.

---

## Ordem sugerida de implementação

| Ordem | Bloco                    | Motivo |
|-------|--------------------------|--------|
| 1     | Alertas financeiros     | Poucos componentes novos; usa Meta + Telegram que já temos. |
| 2     | Drive + Sheets + PDF     | Base para relatórios melhores e para a linha de produção. |
| 3     | Linha de produção        | Usa Drive/Sheets + Meta; automatiza o que hoje é manual. |
| 4     | Front-end (Sala de comando) | Consome tudo que já estiver pronto em forma de API. |

---

## Resumo

- **Alertas:** rotina (cron) que checa saldo Meta e manda mensagem no Telegram.
- **Drive/Sheets:** API Google + Service Account; Jake lê planilhas “em tempo real” e gera PDF.
- **Publishing:** convenção de pastas/planilhas no Drive + Meta API para criar campanha com criativos do Drive.
- **Front-end:** API que reutiliza a mesma lógica; painel web para operar com a sua marca; Telegram continua para alertas e atalhos.

Quando quiser começar por um bloco (por exemplo, alertas financeiros), diga qual e seguimos passo a passo só naquela parte.
