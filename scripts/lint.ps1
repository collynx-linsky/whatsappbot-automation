# WhatsAppBusinessAI - Lint backend (ruff, black --check, isort --check) and frontend (eslint)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Backend: ruff" -ForegroundColor Cyan
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" -m ruff check .
Write-Host "==> Backend: black --check" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m black --check .
Write-Host "==> Backend: isort --check" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m isort --check .
Pop-Location

Write-Host "==> Frontend: eslint" -ForegroundColor Cyan
Push-Location "$root\frontend"
npm run lint
Pop-Location

Write-Host ""
Write-Host "Lint clean." -ForegroundColor Green
