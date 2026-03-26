#!/bin/bash
cd "$(dirname "$0")"
[ -f venv/bin/python ] || python3 -m venv venv
venv/bin/pip install -q flask requests 2>/dev/null
venv/bin/python app.py
