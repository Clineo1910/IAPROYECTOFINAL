@echo off
title SIGE-360 Launcher
cd /d "%~dp0"

set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

echo Iniciando SIGE-360...
start "SIGE-360 MCP (:8000)" cmd /k ""%PY%" agente\servidor_mcp.py"
start "SIGE-360 n8n (:5678)" /D "%USERPROFILE%" cmd /k "set N8N_DIAGNOSTICS_ENABLED=false && npx.cmd --yes n8n"
start "SIGE-360 Web (:3060)" cmd /k ""%PY%" -m uvicorn app:app --port 3060"

timeout /t 4 /nobreak >nul
start "" "http://localhost:3060/login.html"
start "" "http://localhost:3060/semaforo.html"
echo Listo. Las 3 ventanas de SIGE-360 estan corriendo.
