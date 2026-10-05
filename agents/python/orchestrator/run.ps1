# Starts the Conductor on http://localhost:8000 (Windows PowerShell).
#   Usage:  .\run.ps1          start the server
#           .\run.ps1 -Test    run the tests instead
#
# What it does for you:
#   1. Creates aurelius\.env with generated secrets if it's missing (scripts\setup_env.ps1)
#   2. Creates this agent's own virtual environment (.venv) and installs requirements.txt
#   3. Runs the tests or starts the server using the .venv's Python

param([switch]$Test)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- 1. .env with secrets (root of the repo: ..\..\..\.env) -------------------
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
& (Join-Path $root "scripts\setup_env.ps1")

# --- 2. Virtual environment ---------------------------------------------------
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Cyan
    # 'py' is the Windows Python launcher; plain 'python' may be a Microsoft Store shortcut
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv .venv
    } else {
        python -m venv .venv
    }
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
}

# --- 3. Run -------------------------------------------------------------------
if ($Test) {
    & $venvPython -m pytest -v
} else {
    Write-Host "Conductor starting: http://localhost:8000/docs" -ForegroundColor Green
    & $venvPython src\main.py
}
