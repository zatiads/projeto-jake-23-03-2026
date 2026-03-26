# Jake IA – Interface web (estilo Jarvis)

Interface que você acessa pelo navegador: **Jake IA** em destaque, esfera de energia grande e cards com hora/data, temperatura e status.

## Acesso como site (recomendado)

1. Na pasta do projeto, execute:
   - **Windows:** dê dois cliques em `run_web.bat` ou no terminal: `run_web.bat`
   - **Linux/Mac:** `chmod +x run_web.sh` e depois `./run_web.sh`
2. Abra no navegador: **http://localhost:5050**

Na primeira execução o script instala Flask e requests no venv (se precisar).

## O que aparece na tela

- **Título:** Jake IA + subtítulo
- **Esfera:** núcleo de energia em tons de cyan/branco (bem maior que a versão desktop), com animação suave
- **Cards ao lado:** Hora e data (atualiza em tempo real), Temperatura (API Open-Meteo, região SP), Status (Online), Saudação (Bom dia / Boa tarde / Boa noite)

## Requisitos

- **Python 3.8+** no PATH.
- Conexão com internet para a temperatura (opcional; se falhar, mostra "— °C").

---

## Versão desktop (janela flutuante)

Se quiser a bolinha solta no Windows: use `run.bat` (precisa de PyQt5 no venv).
