# Social Brief — Reativação + Export PDF — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reativar o Social Brief no Jake OS com exportação de PDF gerado no servidor, enviado automaticamente via WhatsApp toda quarta às 8h.

**Architecture:** Adicionar `_sb_gerar_pdf()` no `app.py` usando `weasyprint` para converter o HTML existente em PDF. Novo endpoint `/api/social-brief/exportar-pdf` para download manual. Cron de quarta às 8h gera análise completa, converte para PDF e envia via Evolution API para o Bruno.

**Tech Stack:** Flask, weasyprint, APScheduler, Evolution API (já em uso), psycopg2 (Neon/PostgreSQL)

**Spec:** `docs/superpowers/specs/2026-06-10-social-brief-pdf-design.md`

---

## Mapa de Arquivos

| Arquivo | Ação | O que muda |
|---|---|---|
| `jake_desktop/requirements.txt` | Modificar | Adicionar `weasyprint` |
| `bot/whatsapp_handlers.py` | Modificar | Adicionar `send_document()` |
| `jake_desktop/app.py` | Modificar | + `_sb_gerar_pdf()`, + endpoint `/api/social-brief/exportar-pdf`, modificar cron para quarta + PDF + WhatsApp |
| `jake_desktop/templates/dashboard.html` | Modificar | Descomentar item Social Brief na sidebar (linha 254) |
| `jake_desktop/static/js/social_brief.js` | Modificar | Adicionar botão "Exportar PDF" e handler de download |

---

## Task 1: Instalar weasyprint

**Files:**
- Modify: `jake_desktop/requirements.txt`

- [ ] **Step 1: Adicionar weasyprint ao requirements.txt**

Abrir `jake_desktop/requirements.txt` e adicionar na última linha:
```
weasyprint>=62.0
```

- [ ] **Step 2: Identificar o venv correto e instalar**

```bash
head -5 /root/jake_desktop/run_web.sh
```

Esperado: a linha com `python` aponta para `/root/venv/bin/python` (venv principal).

Instalar:
```bash
/root/venv/bin/pip install weasyprint
```

- [ ] **Step 3: Confirmar instalação**

```bash
/root/venv/bin/python -c "import weasyprint; print(weasyprint.__version__)"
```

Esperado: número de versão impresso sem erro (ex: `62.3`).

- [ ] **Step 4: Commit**

```bash
git add jake_desktop/requirements.txt
git commit -m "chore(social-brief): add weasyprint dependency"
```

---

## Task 2: Adicionar send_document() ao whatsapp_handlers.py

**Files:**
- Modify: `bot/whatsapp_handlers.py`

A função deve enviar um arquivo PDF via Evolution API usando o endpoint `/message/sendMedia/{instance}` com `mediatype: "document"`.

- [ ] **Step 1: Confirmar que `requests` já está importado no arquivo**

```bash
grep -n "^import requests" /root/bot/whatsapp_handlers.py
```

Esperado: `import requests` presente (linha ~10). Se não estiver, adicionar após os outros imports.

- [ ] **Step 2: Adicionar send_document() após send_text()**

Inserir logo após a função `send_text()` (linha ~49):

```python
def send_document(jid: str, pdf_bytes: bytes, filename: str, caption: str = "") -> bool:
    """Envia arquivo PDF para um JID via Evolution API. Retorna True se OK."""
    import base64
    url = f"{_evo_base()}/message/sendMedia/{_wa_instance()}"
    number = jid.split("@")[0] if "@" in jid else jid
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    try:
        resp = requests.post(
            url,
            headers={"apikey": _evo_key(), "Content-Type": "application/json"},
            json={
                "number": number,
                "mediatype": "document",
                "mimetype": "application/pdf",
                "caption": caption,
                "media": pdf_b64,
                "fileName": filename,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"send_document failed to {jid}: {e}")
        return False
```

- [ ] **Step 3: Verificar sintaxe**

```bash
python3 -c "import sys; sys.path.insert(0, '/root'); from bot.whatsapp_handlers import send_document; print('OK')"
```

Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git add bot/whatsapp_handlers.py
git commit -m "feat(whatsapp): adicionar send_document para envio de PDF"
```

---

## Task 3: Adicionar _sb_gerar_pdf() e endpoint de exportação no app.py

**Files:**
- Modify: `jake_desktop/app.py` (inserção após linha 7383 e após endpoint existente de download)

### 3a — Função _sb_gerar_pdf()

- [ ] **Step 1: Inserir _sb_gerar_pdf() após _sb_publicar_surge() (linha ~7383)**

Adicionar após a função `_sb_publicar_surge` (que termina na linha 7383):

```python
def _sb_gerar_pdf(html: str) -> bytes:
    """Converte HTML do portal em PDF via weasyprint. Retorna bytes do PDF."""
    try:
        from weasyprint import HTML as _WP_HTML, CSS as _WP_CSS
        # Ajuste de CSS para impressão: fundo colorido visível no PDF
        print_css = _WP_CSS(string="@page { size: A4; margin: 10mm; } body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }")
        pdf_bytes = _WP_HTML(string=html).write_pdf(stylesheets=[print_css])
        return pdf_bytes
    except Exception as e:
        raise RuntimeError(f"Erro ao gerar PDF: {e}")
```

- [ ] **Step 2: Verificar sintaxe do app.py**

```bash
python3 -c "import ast; ast.parse(open('/root/jake_desktop/app.py').read()); print('syntax OK')"
```

Esperado: `syntax OK`

### 3b — Endpoint /api/social-brief/exportar-pdf

**Nota:** A coluna `html_completo TEXT` existe na tabela `social_brief_geracoes` (confirmado em `app.py` linha ~158). O endpoint lê o HTML salvo da última geração — não precisa rerodar Meta Ads nem Claude.

- [ ] **Step 3: Confirmar coluna html_completo no schema**

```bash
grep -n "html_completo" /root/jake_desktop/app.py | head -5
```

Esperado: linha com `html_completo TEXT` no CREATE TABLE e linhas de INSERT/SELECT.

- [ ] **Step 4: Inserir endpoint após o endpoint de download existente (~linha 7715)**

Primeiro, localizar onde termina o endpoint `sb_download`:
```bash
grep -n "def sb_download\|def sb_" /root/jake_desktop/app.py | head -20
```

Inserir após o endpoint `sb_download` (use `grep -n "def sb_download\|def sb_" /root/jake_desktop/app.py | head -20` para localizar o fim):

```python
@app.route("/api/social-brief/exportar-pdf", methods=["GET"])
@login_required
def sb_exportar_pdf():
    """Gera PDF da última geração salva e retorna para download."""
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, html_completo, semana_inicio, semana_fim FROM social_brief_geracoes ORDER BY criado_em DESC LIMIT 1"
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row or not row["html_completo"]:
        return jsonify({"error": "Nenhuma geração disponível. Gere o portal primeiro."}), 404

    try:
        pdf_bytes = _sb_gerar_pdf(row["html_completo"])
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    semana = str(row["semana_inicio"]).replace("/", "-") if row["semana_inicio"] else "semana"
    filename = f"social-brief-{semana}.pdf"
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
```

- [ ] **Step 5: Verificar sintaxe**

```bash
python3 -c "import ast; ast.parse(open('/root/jake_desktop/app.py').read()); print('syntax OK')"
```

- [ ] **Step 6: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(social-brief): adicionar _sb_gerar_pdf e endpoint exportar-pdf"
```

---

## Task 4: Modificar cron — trocar segunda por quarta + adicionar PDF + WhatsApp

**Files:**
- Modify: `jake_desktop/app.py` (bloco do cron, ~linhas 9396-9481)

O cron atual roda toda segunda. Precisamos:
1. Trocar `day_of_week="mon"` por `day_of_week="wed"`
2. Após salvar a geração no banco, gerar PDF e enviar via WhatsApp

- [ ] **Step 1: Localizar linha exata do add_job**

```bash
grep -n 'add_job.*_job_social_brief\|day_of_week.*mon' /root/jake_desktop/app.py
```

- [ ] **Step 2: Trocar day_of_week de "mon" para "wed"**

Na linha com `_sched.add_job(_job_social_brief, "cron", day_of_week="mon", hour=8, minute=0)`:

Trocar `day_of_week="mon"` por `day_of_week="wed"`.

- [ ] **Step 3: Verificar variáveis em escopo no ponto de inserção**

```bash
sed -n '9420,9480p' /root/jake_desktop/app.py
```

Confirmar que:
- A variável com o HTML gerado se chama `html` (linha ~9426: `html = _sb_gerar_html_portal(...)`)
- A variável da data de início da semana se chama `seg` (linha ~9424: `seg = hoje - _tdj(days=hoje.weekday())`)

Se os nomes forem diferentes, ajustar o snippet abaixo conforme encontrado.

- [ ] **Step 4: Adicionar envio de PDF após o bloco de salvar no banco**

Localizar o trecho dentro de `_job_social_brief` onde o HTML é salvo no banco (após `conn2.commit()`). Após o bloco `try/except` de publicação no Surge (linhas ~9459-9475), adicionar:

**Nota:** `WA_AUTHORIZED_NUMBER` é o número puro (ex: `5535988550954`), não um JID. `send_document` aceita número puro diretamente — a lógica `split("@")[0]` dentro da função apenas trata o caso de JID com sufixo, mas número puro passa direto.

```python
                    # Gera PDF e envia via WhatsApp
                    try:
                        import sys as _sys
                        _sys.path.insert(0, '/root')
                        from bot.whatsapp_handlers import send_document as _send_doc
                        pdf_bytes = _sb_gerar_pdf(html)
                        authorized_number = os.environ.get("WA_AUTHORIZED_NUMBER", "")
                        if authorized_number and pdf_bytes:
                            semana_label = seg.strftime("%d/%m") + " a " + (seg + _tdj(days=6)).strftime("%d/%m/%Y")
                            _send_doc(
                                jid=authorized_number,
                                pdf_bytes=pdf_bytes,
                                filename=f"social-brief-{seg.strftime('%Y-%m-%d')}.pdf",
                                caption=f"📊 Social Brief — semana {semana_label}",
                            )
                            print(f"[Social Brief] PDF enviado via WhatsApp")
                    except Exception as e:
                        print(f"[Social Brief] Erro ao enviar PDF: {e}")
```

- [ ] **Step 5: Atualizar o print do agendador**

Trocar a linha:
```python
print("[Social Brief] Agendador ativo — toda segunda às 08h")
```
por:
```python
print("[Social Brief] Agendador ativo — toda quarta às 08h")
```

- [ ] **Step 6: Verificar sintaxe**

```bash
python3 -c "import ast; ast.parse(open('/root/jake_desktop/app.py').read()); print('syntax OK')"
```

- [ ] **Step 7: Commit**

```bash
git add jake_desktop/app.py
git commit -m "feat(social-brief): cron para quarta 8h + gerar PDF + enviar WhatsApp"
```

---

## Task 5: Reativar Social Brief na sidebar

**Files:**
- Modify: `jake_desktop/templates/dashboard.html` (linha 254)

- [ ] **Step 1: Confirmar que o comentário exato existe no arquivo**

```bash
grep -n "Rotina e Social Brief desativados" /root/jake_desktop/templates/dashboard.html
```

Esperado: `254:        <!-- Rotina e Social Brief desativados -->`. Se a linha não aparecer, procurar o comentário com `grep -n "Social Brief" /root/jake_desktop/templates/dashboard.html` e usar o texto exato encontrado.

- [ ] **Step 2: Substituir o comentário pelo item de nav**

Na linha 254, substituir:
```html
        <!-- Rotina e Social Brief desativados -->
```
por:
```html
        <a class="nav-item" data-page="social-brief" href="#">
          <span class="nav-icon">📊</span>
          <span class="nav-label">Social Brief</span>
        </a>
```

- [ ] **Step 3: Confirmar que o item foi inserido e a seção existe**

```bash
grep -n "social-brief" /root/jake_desktop/templates/dashboard.html
```

Esperado: linha com `data-page="social-brief"` na sidebar (~254) e linha com `id="page-social-brief"` (~2083).

- [ ] **Step 4: Commit**

```bash
git add jake_desktop/templates/dashboard.html
git commit -m "feat(social-brief): reativar na sidebar do Jake OS"
```

---

## Task 6: Adicionar botão "Exportar PDF" no frontend

**Files:**
- Modify: `jake_desktop/templates/dashboard.html` (botão HTML na div `.sb-acoes`)
- Modify: `jake_desktop/static/js/social_brief.js` (função JS de download)

- [ ] **Step 1: Confirmar localização do div .sb-acoes no dashboard.html**

```bash
grep -n "sb-acoes\|Republicar\|Gerar Portal" /root/jake_desktop/templates/dashboard.html
```

Esperado: linhas próximas a 2088 com os botões existentes.

- [ ] **Step 2: Adicionar botão "Exportar PDF" no dashboard.html**

Localizar a div `.sb-acoes` (~linha 2088) e adicionar o botão após o botão "Republicar":

```html
<button class="btn-outline" onclick="sbExportarPDF()" title="Baixar PDF da última geração">📄 Exportar PDF</button>
```

- [ ] **Step 3: Adicionar função sbExportarPDF() no social_brief.js**

No final do IIFE (antes do `})();`), adicionar:

```javascript
  window.sbExportarPDF = function () {
    var btn = document.querySelector('[onclick="sbExportarPDF()"]');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Gerando...'; }
    fetch('/api/social-brief/exportar-pdf')
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Erro'); });
        return r.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'social-brief.pdf';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(function (e) { alert('Erro ao exportar PDF: ' + e.message); })
      .finally(function () {
        if (btn) { btn.disabled = false; btn.textContent = '📄 Exportar PDF'; }
      });
  };
```

- [ ] **Step 4: Verificar sintaxe do JS**

```bash
node --check /root/jake_desktop/static/js/social_brief.js && echo "JS OK"
```

- [ ] **Step 5: Commit**

```bash
git add jake_desktop/templates/dashboard.html jake_desktop/static/js/social_brief.js
git commit -m "feat(social-brief): botao Exportar PDF no frontend"
```

---

## Task 7: Verificação final e restart

- [ ] **Step 1: Checar se Jake OS está rodando**

```bash
curl -s http://localhost:5050/login | grep -c "Jake" || echo "Jake OS offline"
```

- [ ] **Step 2: Reiniciar Jake OS**

```bash
pkill -f "python.*app.py" 2>/dev/null; sleep 2
cd /root/jake_desktop && nohup /root/venv/bin/python app.py >> /root/logs/jakeos.log 2>&1 &
sleep 3 && curl -s http://localhost:5050/login | grep -c "Jake"
```

- [ ] **Step 3: Testar endpoint de exportação (precisa de cookie de sessão logada)**

Verificar no navegador acessando `http://localhost:5050/#social-brief` que:
1. Item "Social Brief" aparece na sidebar
2. Botão "Exportar PDF" está visível
3. Clicar em "Exportar PDF" inicia download (se já houver geração salva)

- [ ] **Step 4: Verificar cron configurado**

```bash
grep -n "day_of_week\|social_brief\|quarta" /root/jake_desktop/app.py | tail -10
```

Esperado: `day_of_week="wed"` presente.

- [ ] **Step 5: Confirmar todos os arquivos estão commitados**

```bash
git status
```

Esperado: `nothing to commit, working tree clean`. Se houver arquivos pendentes, commitá-los individualmente antes de prosseguir.
