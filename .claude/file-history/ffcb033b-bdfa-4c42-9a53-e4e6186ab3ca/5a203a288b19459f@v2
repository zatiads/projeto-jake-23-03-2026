"""
Meta-agente: gera prompts mestres e arquivos de bot prontos.
Uso: python gerar_agente.py
"""
import os, sys, textwrap
import anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

PROMPT_META = """Você é um especialista em engenharia de prompts para agentes de IA. Sua função é criar prompts de sistema (system prompts) extremamente bem estruturados para agentes Telegram.

Dado uma descrição de um agente, você gera um prompt mestre seguindo EXATAMENTE este modelo:

---
PROMPT_[NOME] = \"\"\"Você é o [Nome do Agente] do Jake IA — [descrição curta e direta do papel].

CONTEXTO:
[Uma frase sobre quem é o usuário e o que ele precisa deste agente.]

SUAS COMPETÊNCIAS:
• [competência 1 — específica e acionável]
• [competência 2]
• [competência 3]
• [...]

COMO VOCÊ RESPONDE:
— [regra de comportamento 1]
— [regra de comportamento 2]
— [regra de comportamento 3]
— NUNCA diz "depende" sem explicar de quê depende e qual a sua recomendação.
— NUNCA use a palavra 'automação'.

CAPACIDADES ESPECIAIS DESTE SISTEMA:
— Você TEM ACESSO À INTERNET. Quando a mensagem contiver resultados de busca, use-os como base para responder com dados atuais.
— Você CONSEGUE gerar e enviar arquivos PDF via comando /pdf.
— Você CONSEGUE ler PDFs enviados pelo usuário diretamente no chat.
— NUNCA diga que não tem essas capacidades.

Sempre chame o Bruno de 'Patrão'.\"\"\"
---

REGRAS:
- O prompt deve ser direto, sem floreios
- Competências devem ser específicas (não genéricas como "ajudar com tarefas")
- As regras de resposta devem refletir o estilo e tom do agente
- Inclua sempre as CAPACIDADES ESPECIAIS sem modificar esse bloco
- Sempre inclua "Sempre chame o Bruno de 'Patrão'." no final

Gere APENAS o prompt, sem explicações antes ou depois."""


def gerar_prompt(descricao: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=PROMPT_META,
        messages=[{"role": "user", "content": descricao}],
    )
    return response.content[0].text.strip()


def gerar_arquivo_bot(nome_agente: str, nome_variavel: str, prompt: str, token_env: str, namespace: str) -> str:
    """Gera o conteúdo do arquivo .py do bot."""
    return f'''"""
Jake IA — {nome_agente}
Agente gerado automaticamente por gerar_agente.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from base_bot import rodar_bot

{prompt}

if __name__ == "__main__":
    rodar_bot(
        token_env="{token_env}",
        prompt_sistema={nome_variavel},
        namespace="{namespace}",
        nome="{nome_agente}",
    )
'''


def main():
    print("=" * 60)
    print("  META-AGENTE — Gerador de Bots Jake IA")
    print("=" * 60)
    print()

    nome = input("Nome do agente (ex: Pessoal, Viagem, Fitness): ").strip()
    if not nome:
        print("Nome obrigatório.")
        sys.exit(1)

    print(f"\nDescreva o agente '{nome}' (o que ele faz, para quem, estilo):")
    descricao = input("> ").strip()
    if not descricao:
        print("Descrição obrigatória.")
        sys.exit(1)

    print("\n⏳ Gerando prompt mestre...")
    prompt = gerar_prompt(f"Crie um agente chamado '{nome}'. Descrição: {descricao}")

    print("\n" + "=" * 60)
    print("PROMPT GERADO:")
    print("=" * 60)
    print(prompt)
    print("=" * 60)

    salvar = input("\nSalvar como arquivo de bot? (s/n): ").strip().lower()
    if salvar != "s":
        print("Prompt gerado. Nada foi salvo.")
        return

    nome_var = f"PROMPT_{nome.upper().replace(' ', '_')}"
    token_env = f"TELEGRAM_TOKEN_{nome.upper().replace(' ', '_')}"
    namespace = nome.lower().replace(" ", "_")
    nome_arquivo = f"jake_{nome.lower().replace(' ', '_')}.py"

    # Extrai só o conteúdo da string do prompt (sem PROMPT_X = """...""")
    conteudo = gerar_arquivo_bot(nome, nome_var, prompt, token_env, namespace)
    caminho = os.path.join(os.path.dirname(__file__), nome_arquivo)

    with open(caminho, "w") as f:
        f.write(conteudo)

    print(f"\n✅ Arquivo criado: {caminho}")
    print(f"\nPróximos passos:")
    print(f"  1. Crie o bot no BotFather e pegue o token")
    print(f"  2. Adicione no .env: {token_env}=<seu_token>")
    print(f"  3. Rode: nohup venv/bin/python bot/{nome_arquivo} > /tmp/jake_{namespace}.log 2>&1 &")


if __name__ == "__main__":
    main()
