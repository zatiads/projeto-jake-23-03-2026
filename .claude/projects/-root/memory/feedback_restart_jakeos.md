---
name: Reiniciar Jake OS após alterações
description: Sempre matar e reiniciar o localhost:5050 após qualquer modificação no Jake OS
type: feedback
---

Sempre que fizer qualquer alteração no Jake OS (app.py, templates, static/js, static/css), matar o processo e reiniciar o servidor antes de encerrar a resposta.

**Why:** O usuário precisa ver as atualizações imediatamente no localhost:5050. Sem reiniciar, as mudanças de backend não aparecem.

**How to apply:**
```bash
kill $(ps aux | grep 'python.*app\.py' | grep -v grep | awk '{print $2}') 2>/dev/null; sleep 1
cd /root/jake_desktop && nohup ./venv/bin/python app.py >> /tmp/jake_os.log 2>&1 &
sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5050
```
Confirmar com 302 (redirect para login = servidor rodando).
