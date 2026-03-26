# Jake IA – Rodar na VPS e acessar do seu PC

## 1. Subir o servidor na VPS

No terminal da VPS (SSH ou terminal do Cursor):

```bash
cd jake_desktop
./run_web.sh
```

Se der *Permission denied*, use:
```bash
bash run_web.sh
```
ou antes: `chmod +x run_web.sh` e depois `./run_web.sh`.

Ou manualmente:

```bash
cd jake_desktop
python3 -m venv venv
venv/bin/pip install flask requests
venv/bin/python app.py
```

**Deixe esse terminal aberto** enquanto quiser usar a interface.

## 2. Descobrir o IP da VPS

Na própria VPS:

```bash
curl -s ifconfig.me
```

Ou use o IP que você já usa para SSH (ex.: `123.45.67.89`).

## 3. Acessar do seu Windows

No navegador do seu PC, abra:

```
http://SEU_IP_DA_VPS:5050
```

Exemplo: `http://123.45.67.89:5050`

## 4. Se não abrir (firewall)

Na VPS, libere a porta 5050:

**Ubuntu/Debian (ufw):**
```bash
sudo ufw allow 5050
sudo ufw reload
```

**Firewall do provedor (AWS, DigitalOcean, etc.):** abra a porta **5050** TCP no painel de controle da VPS.

Depois disso, use de novo no navegador: `http://IP_DA_VPS:5050`.
