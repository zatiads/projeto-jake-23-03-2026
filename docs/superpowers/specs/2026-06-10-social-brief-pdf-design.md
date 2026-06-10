# Social Brief — Reativação + Export PDF

**Data:** 2026-06-10
**Status:** Aprovado pelo usuário

---

## Contexto

O módulo Social Brief já existe completamente no Jake OS (rotas, banco, JS, HTML). Foi desativado apenas na sidebar. O portal anterior gerava um HTML autocontido e publicava via Surge.sh.

Novo objetivo: reativar na sidebar + substituir Surge por exportação de PDF gerado no servidor, enviado automaticamente via WhatsApp para o Bruno toda quarta às 8h.

---

## Escopo

1. **Reativar Social Brief na sidebar** do Jake OS
2. **Adicionar botão "Exportar PDF"** na interface
3. **Geração de PDF no servidor** via `weasyprint`
4. **Cron toda quarta às 8h**: gera análise + PDF + envia via jake-whatsapp
5. **Endpoint de download**: `/api/social-brief/exportar-pdf`

---

## Arquitetura

### Backend (`jake_desktop/app.py`)

**Nova função** `_sb_gerar_pdf(todos_dados, semana_inicio, semana_fim) -> bytes`
- Chama `_sb_gerar_html_portal()` (já existe) para obter o HTML
- Converte para PDF via `weasyprint.HTML(string=html).write_pdf()`
- Retorna bytes do PDF

**Novo endpoint** `GET /api/social-brief/exportar-pdf`
- Busca dados da última geração salva no banco (`social_brief_geracoes` + `social_brief_cliente_dados`)
- Regera o HTML com os dados salvos
- Gera PDF via `_sb_gerar_pdf()`
- Retorna `application/pdf` com header `Content-Disposition: attachment; filename=social-brief-SEMANA.pdf`

**Cron quarta às 8h** (em `_init_scheduler()`)
- Executa fluxo completo: busca Meta Ads + Claude + HTML + PDF
- Salva geração no banco
- Envia PDF via Evolution API para Bruno (mesmo mecanismo do jake-whatsapp)

### Frontend

**`dashboard.html`**: descomentar item Social Brief na sidebar

**`social_brief.js`**: adicionar botão "Exportar PDF" que chama `/api/social-brief/exportar-pdf` e faz download

### Dependência nova

```
weasyprint
```

Instalar via: `pip install weasyprint` no venv do Jake OS

---

## Conteudo do PDF

Mesmo conteudo do HTML portal atual (funcao `_sb_gerar_html_portal` ja existente):
- Capa com semana e data de geracao
- Por cliente: resumo da semana, ranking top 5 criativos, o que funcionou/nao funcionou, perfil do publico, hooks e CTAs sugeridos
- Metricas: CTR, cliques, CPL, gasto total, leads

---

## Fluxo do cron (quarta 8h)

```
1. Busca clientes ativos do banco
2. Para cada cliente: Meta Ads + Claude (mesma logica do SSE)
3. Gera HTML via _sb_gerar_html_portal()
4. Converte HTML -> PDF via weasyprint
5. Salva geracao no banco
6. Envia PDF via Evolution API para Bruno (WA_AUTHORIZED_NUMBER)
7. Mensagem: "Social Brief da semana X a Y gerado."
```

---

## Arquivos modificados

| Arquivo | Mudanca |
|---|---|
| `jake_desktop/app.py` | + funcao `_sb_gerar_pdf`, + endpoint exportar-pdf, + cron quarta 8h |
| `jake_desktop/templates/dashboard.html` | descomentar Social Brief na sidebar |
| `jake_desktop/static/js/social_brief.js` | + botao Exportar PDF |
| `jake_desktop/requirements.txt` ou venv | + weasyprint |

---

## Fora do escopo

- Envio direto ao grupo (Bruno repassa manualmente)
- Alterar layout/conteudo do HTML existente
- Remover Surge (mantém como fallback se configurado)
