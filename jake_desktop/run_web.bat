@echo off
title Jake IA - Web
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

venv\Scripts\pip install -q flask requests 2>nul
set OPEN_BROWSER=1
echo.
echo Iniciando servidor... Nao feche esta janela.
echo.
venv\Scripts\python.exe app.py
pause
