# Starts every Aurelius service, each in its own PowerShell window, in dependency order.
# Usage:  .\scripts\start-all.ps1          (backend + web)
#         .\scripts\start-all.ps1 -NoWeb   (backend only)
param([switch]$NoWeb)

$root = Split-Path -Parent $PSScriptRoot

function Start-Service($title, $folder, $command) {
    $dir = Join-Path $root $folder
    $cmd = "`$host.UI.RawUI.WindowTitle = '$title'; Set-Location '$dir'; $command"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $cmd
    Write-Host "Started $title" -ForegroundColor Green
}

function Wait-Port($port, $name) {
    Write-Host "Waiting for $name on port $port..." -NoNewline
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-NetConnection 127.0.0.1 -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue) {
            Write-Host " up" -ForegroundColor Green; return
        }
        Start-Sleep -Seconds 1
    }
    Write-Host " not up after 60 s (check its window)" -ForegroundColor Yellow
}

$py = '.\.venv\Scripts\python.exe src\main.py'

# 1. Data and security first: others depend on them
Start-Service 'MCP server :8500' 'mcp-servers\advisor-tools'      $py
Start-Service 'Sentinel :8004'   'agents\python\compliance-guard' $py
Start-Service 'Liaison :8102'    'agents\node\crm-sync'           'npm run dev'
Wait-Port 8500 'MCP server'
Wait-Port 8004 'Sentinel'
Wait-Port 8102 'Liaison'

# 2. The rest of the agents (any order)
Start-Service 'Librarian :8001'  'agents\python\knowledge-rag'      $py
Start-Service 'Analyst :8002'    'agents\python\portfolio-insights' $py
Start-Service 'Scribe :8003'     'agents\python\meeting-intel'      $py
Start-Service 'Herald :8101'     'agents\node\client-comms'         'npm run dev'
Start-Service 'Notary :8201'     'agents\java\onboarding-kyc'       'mvn spring-boot:run'
Start-Service 'Actuary :8202'    'agents\java\risk-engine'          'mvn spring-boot:run'
Start-Service 'Pulse :8301'      'agents\go\market-pulse'           'go run ./cmd/pulse'
Wait-Port 8201 'Notary'
Wait-Port 8202 'Actuary'

# 3. The Conductor calls everyone, so it goes last
Start-Service 'Conductor :8000'  'agents\python\orchestrator' $py
Wait-Port 8000 'Conductor'

# 4. Web app
if (-not $NoWeb) {
    Start-Service 'Web app :5173' 'frontend\web' 'npm run dev'
    Wait-Port 5173 'Web app'
    Write-Host "`nOpen http://127.0.0.1:5173" -ForegroundColor Cyan
}
Write-Host "All started. Stop everything with .\scripts\stop-all.ps1" -ForegroundColor Cyan