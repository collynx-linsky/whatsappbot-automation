# WhatsAppBusinessAI - Run the full test suite (backend pytest + frontend typecheck/build)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Backend: pytest" -ForegroundColor Cyan
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" -m pytest -v
Pop-Location

Write-Host "==> Backend: django checks" -ForegroundColor Cyan
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" manage.py check
Pop-Location

Write-Host "==> Frontend: typecheck" -ForegroundColor Cyan
Push-Location "$root\frontend"
npx tsc --noEmit
Write-Host "==> Frontend: build" -ForegroundColor Cyan
npm run build
Pop-Location

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
