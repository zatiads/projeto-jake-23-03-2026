#!/usr/bin/env python3
"""
Launcher do Jake: redireciona para bot/jake_telegram.py.
Use: python3 /root/jake_telegram.py  (com PYTHONPATH=/root)
Ou prefira: /root/scripts/subir_jake.sh
"""
import os
import sys

# Garante que o projeto está no path (raiz = /root)
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Roda o bot
from bot.jake_telegram import main

if __name__ == "__main__":
    main()
