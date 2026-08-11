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
Write-Host "==> Frontend: component/unit tests (Vitest)" -ForegroundColor Cyan
npm run test
Write-Host "==> Frontend: build" -ForegroundColor Cyan
npm run build
Pop-Location

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
Write-Host "(Playwright e2e tests are not run here — they need the backend" -ForegroundColor DarkGray
Write-Host " and frontend dev servers both running live. See docs/testing.md." -ForegroundColor DarkGray
