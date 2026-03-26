#!/bin/bash
cd "$(dirname "$0")" || exit 1

# Mata qualquer servidor Flask do Jake que esteja rodando
pkill -f "python.*jake_desktop.*app.py" 2>/dev/null || true
pkill -f "python app.py" 2>/dev/null || true

# Sobe de novo usando o venv
if [ ! -f "venv/bin/python" ]; then
  python3 -m venv venv
fi
venv/bin/pip install -q flask requests openai python-dotenv >/dev/null 2>&1

echo "Reiniciando servidor Jake IA..."
venv/bin/python app.py
