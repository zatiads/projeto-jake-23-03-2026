@echo off
title Jake Desktop
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 (
        echo Erro: instale Python 3.8+ e adicione ao PATH.
        pause
        exit /b 1
    )
)

if not exist "venv\pyqt5_ok" (
    echo Instalando PyQt5...
    venv\Scripts\pip install PyQt5
    if errorlevel 1 (
        echo Erro ao instalar PyQt5.
        pause
        exit /b 1
    )
    echo. > venv\pyqt5_ok
)

venv\Scripts\python.exe jake_sphere.py
if errorlevel 1 pause
