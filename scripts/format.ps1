# WhatsAppBusinessAI - Auto-format backend (isort, black) and frontend (eslint --fix)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Backend: isort" -ForegroundColor Cyan
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" -m isort .
Write-Host "==> Backend: black" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m black .
Pop-Location

Write-Host "==> Frontend: eslint --fix" -ForegroundColor Cyan
Push-Location "$root\frontend"
npx eslint --fix .
Pop-Location

Write-Host ""
Write-Host "Formatting complete." -ForegroundColor Green
