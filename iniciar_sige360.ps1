# iniciar_sige360.ps1 - Inicia los 3 servicios de SIGE-360 en ventanas separadas
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "Iniciando SIGE-360 (MCP :8000, n8n :5678, Web :3060)..." -ForegroundColor Cyan

Start-Process powershell -WorkingDirectory $raiz -ArgumentList "-NoExit", "-Command", "& '$py' agente/servidor_mcp.py"
Start-Process powershell -WorkingDirectory $raiz -ArgumentList "-NoExit", "-Command", "npx --yes n8n"
Start-Process powershell -WorkingDirectory $raiz -ArgumentList "-NoExit", "-Command", "& '$py' -m uvicorn app:app --port 3060"

Start-Sleep -Seconds 3
Start-Process "http://localhost:3060/login.html"
Start-Process "http://localhost:3060/semaforo.html"
Write-Host "Listo. Si n8n tarda unos segundos, recarga http://localhost:5678." -ForegroundColor Green
