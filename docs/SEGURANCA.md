# Segurança — Jake IA e VPS

## O que foi feito

1. **Credenciais só no `.env`**  
   Token do Telegram, Anthropic, Meta, OpenAI e `AUTHORIZED_ID` vêm do `.env`. O código não tem mais chaves gravadas em texto.

2. **`.gitignore`**  
   O arquivo `.env` e variantes (`.env.*`) estão no `.gitignore`. Se você usar `git` no projeto, o `.env` não será commitado.

3. **Permissão do `.env`**  
   Só o dono (root) pode ler/escrever:  
   `chmod 600 /root/.env`  
   (recomendado; confira com `ls -la /root/.env` — deve mostrar `-rw-------`.)

## Checklist rápido

- [ ] **.env com permissão 600** — `chmod 600 /root/.env`
- [ ] **Nunca fazer commit do .env** — já está no .gitignore
- [ ] **SSH na VPS** — use chave SSH, desative login por senha se possível (`PasswordAuthentication no` no sshd_config)
- [ ] **Acesso root** — evite usar root no dia a dia; crie um usuário e use sudo
- [ ] **Firewall** — só as portas necessárias abertas (ex.: 22 SSH); o bot não precisa de porta aberta (ele faz polling)
- [ ] **Rotação de chaves** — se achar que alguma chave vazou, troque no painel (Meta, Telegram, Anthropic, OpenAI) e atualize o .env

## Se o .env vazou (Git, cópia, etc.)

1. Troque **todas** as chaves nos painéis (Telegram BotFather, Meta, Anthropic, OpenAI).
2. Atualize o `.env` na VPS com as novas chaves.
3. Reinicie o bot e o cron de saldo.

## VPS e Cursor

- Você usa Cursor na VPS: quem tem acesso ao Cursor (ou ao servidor) pode ver arquivos abertos e o `.env`.
- Recomendação: acesso à VPS só por você (ou equipe mínima), SSH com chave e, se puder, desativar login root por senha.

## SSH na VPS

- **Situação atual:** login root permitido, autenticação por **senha** ativa. Não há chaves em `/root/.ssh/authorized_keys`.
- **Recomendação:** usar **chave SSH** e depois desativar senha, para evitar força bruta.

**Passo 1 — Gerar e usar chave (no seu PC):**
```bash
# No seu computador (não na VPS):
ssh-keygen -t ed25519 -C "seu@email" -f ~/.ssh/id_ed25519_jake
# Copiar a chave para a VPS (troque IP pelo IP da VPS):
ssh-copy-id -i ~/.ssh/id_ed25519_jake.pub root@IP_DA_VPS
```
Depois teste: `ssh -i ~/.ssh/id_ed25519_jake root@IP_DA_VPS` e confirme que entra sem senha.

**Passo 2 — Só depois de testar a chave**, desativar login por senha na VPS:
```bash
sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload sshd
```
(Deixe outra sessão SSH aberta até confirmar que ainda entra.)

## Firewall (UFW)

- **Situação atual:** UFW **inativo** (todas as portas abertas).
- **Recomendação:** ativar UFW, liberar só SSH (22) e deixar o resto bloqueado. O Jake não precisa de porta aberta (usa polling).

**Comandos (rode na VPS):**
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw --force enable
sudo ufw status
```
Assim só a porta 22 fica aberta para entrada. Mantenha a sessão SSH aberta até confirmar que `ufw status` mostra 22 allow e que você ainda consegue conectar em outra aba.

## Resumo

| Onde estava o risco              | O que foi feito                          |
|----------------------------------|------------------------------------------|
| Tokens no código (jake_telegram)  | Removidos; leitura só de variáveis de ambiente (.env) |
| .env commitado no Git            | .env adicionado ao .gitignore            |
| .env legível por outros usuários | Recomendado chmod 600 no .env            |
| Histórico do Cursor com código   | .cursor-server/.../History/ no .gitignore |
| SSH por senha                    | Documentado: usar chave e depois desativar senha |
| Firewall desligado               | Documentado: ativar UFW, liberar só 22   |
