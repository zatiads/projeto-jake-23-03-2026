# Automação Live — Design Spec

**Data:** 2026-03-22
**Projeto:** Jake Brain — Cérebro do ecossistema Jake IA
**Sub-projeto:** 3 de 4 — Automação Live (Jake OS salva automaticamente no vault)

---

## Objetivo

Sempre que o Jake OS gerar conteúdo (copy, carrossel, criativo, landing page, análise financeira), salvar automaticamente uma nota `.md` no vault Obsidian (`/root/jake-brain/`), sem intervenção manual.

---

## Arquitetura

### Novo arquivo: `jake_desktop/brain.py`

Módulo utilitário com uma única função pública:

```python
def salvar(modulo: str, titulo: str, inputs: dict, output: str, model: str) -> None
```

Responsabilidades:
1. Montar o caminho de destino: `/root/jake-brain/Jake OS/Outputs/<Modulo>/YYYY-MM-DD-HH-MM-<titulo-slug>.md`
2. Criar diretório se não existir (`os.makedirs(..., exist_ok=True)`)
3. Renderizar o template de nota
4. Escrever o arquivo no disco
5. Logar erros silenciosamente — jamais propagar exceção para a rota

### Modificação: `jake_desktop/app.py`

Importar `brain` e adicionar `brain.salvar(...)` no final de cada rota elegível, antes do `return jsonify(...)`.

### Infraestrutura (sem mudanças)

O cron existente (`*/5 * * * *` → `jake_brain_push.sh`) continua fazendo o git add/commit/push. Nenhuma mudança de infra necessária.

---

## Template da Nota

```markdown
---
modulo: {Modulo}
modelo: {model}
gerado_em: YYYY-MM-DD HH:MM
---

# {titulo}

## Inputs
- **Campo:** valor
- **Campo:** valor

## Output
{conteúdo gerado}

## Modelo
{model}

## Observações
<!-- espaço para anotar no Obsidian depois -->
```

**Regras do template:**
- `modulo` = nome legível (ex: `Copys`, `Carrossel`, `Site Architect`)
- `titulo` = gerado pela rota com contexto (ex: `Copy — Instagram AIDA`)
- `inputs` = somente campos relevantes por módulo (não todo o request body)
- `output` = conteúdo principal em texto limpo (não o JSON completo)
- Para outputs muito longos (HTML de landing page): salvar completo mas indicar no frontmatter `tipo: html`

---

## Rotas Elegíveis

| Módulo | Rota | inputs relevantes | output salvo |
|---|---|---|---|
| Copys | `POST /api/copys/gerar` | plataforma, framework, nicho, oferta, tom | copy gerado |
| Carrossel | `POST /api/carousel/copy` | tema, tom, nível de consciência, gatilho | slides (texto formatado) |
| Criativos v2 | `POST /api/criativos/gerar` | modo, tipo, prompt | prompt expandido + URL resultado |
| Criativos v2 | `POST /api/criativos/expandir-prompt` | prompt, modo, tipo | prompt expandido |
| Anúncios | `POST /api/anuncios/copy` | cliente, tipo campanha, segmento | título + texto + CTA |
| Site Architect | `POST /api/site-architect/generate` | contexto negócio, hero copy, template | HTML completo |
| Site Architect | `POST /api/site-architect/refine` | instrução de refinamento | HTML refinado |
| Financeiro | `POST /api/financeiro/analise` | mês, receita, despesas, saldo | análise completa |

**Fora do escopo** (intermediários/utilitários, não geram conteúdo final):
- `POST /api/criativos/analisar-referencia`
- `GET /api/criativos/pastas`
- `GET /api/criativos/historico`
- `POST /api/carousel/generate-image` (resultado é imagem base64, não texto)

---

## Estrutura do Vault Após Automação Live

```
jake-brain/
└── Jake OS/
    └── Outputs/
        ├── Copys/
        │   └── 2026-03-22-15-43-copy-instagram-aida.md
        ├── Carrossel/
        │   └── 2026-03-22-16-00-carrossel-academia.md
        ├── Criativos/
        │   └── 2026-03-22-16-10-criativo-flux-anuncio.md
        ├── Anuncios/
        │   └── 2026-03-22-16-20-copy-piloti-stories.md
        ├── Site Architect/
        │   └── 2026-03-22-17-00-landing-clinica-aline.md
        └── Financeiro/
            └── 2026-03-22-18-00-analise-marco-2026.md
```

---

## Tratamento de Erros

- `brain.salvar()` nunca lança exceção — usa `try/except` global internamente
- Erros são logados com `app.logger.warning(f"brain.salvar falhou: {e}")`
- A rota continua funcionando normalmente mesmo que o save falhe

---

## Critérios de Sucesso

- [ ] `jake_desktop/brain.py` existe e `salvar()` funciona standalone
- [ ] Ao chamar `/api/copys/gerar`, um `.md` aparece em `Jake OS/Outputs/Copys/`
- [ ] Ao chamar `/api/carousel/copy`, um `.md` aparece em `Jake OS/Outputs/Carrossel/`
- [ ] Todas as 8 rotas elegíveis geram nota no vault
- [ ] Erros em `brain.salvar()` não quebram nenhuma rota
- [ ] Após 5 min, nota aparece no Obsidian Windows via cron
