#!/bin/bash
cd "$(dirname "$0")"

if [ ! -f "venv/bin/python" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
fi

if [ ! -f "venv/pyqt5_ok" ] || ! venv/bin/python -c "import PyQt5" 2>/dev/null; then
    echo "Instalando PyQt5..."
    venv/bin/pip install PyQt5
    touch venv/pyqt5_ok
fi

venv/bin/python jake_sphere.py
