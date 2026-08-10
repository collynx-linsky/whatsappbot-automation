# WhatsAppBusinessAI - First-time environment setup (hybrid dev: native Postgres + Docker Redis)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Backend: creating virtual environment" -ForegroundColor Cyan
Push-Location "$root\backend"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& ".venv\Scripts\python.exe" -m pip install -r requirements\development.txt
Pop-Location

Write-Host "==> Root .env" -ForegroundColor Cyan
if (-not (Test-Path "$root\.env")) {
    Copy-Item "$root\.env.example" "$root\.env"
    Write-Host "Created .env from .env.example - edit it with real values before going further." -ForegroundColor Yellow
} else {
    Write-Host ".env already exists - leaving it as-is." -ForegroundColor DarkGray
}

Write-Host "==> Redis (Docker container)" -ForegroundColor Cyan
try {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        docker compose -f "$root\docker-compose.yml" up -d redis
    } else {
        throw "Docker daemon not reachable"
    }
} catch {
    Write-Host "Docker isn't reachable - skipping Redis container. Start Docker Desktop and re-run this script, or start Redis another way." -ForegroundColor Yellow
}

Write-Host "==> Backend: running migrations" -ForegroundColor Cyan
Write-Host "    (If this fails with a connection/auth error, the Postgres role/db" -ForegroundColor DarkGray
Write-Host "     probably doesn't exist yet - run .\scripts\create-db.ps1 first.)" -ForegroundColor DarkGray
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" manage.py migrate
Pop-Location

Write-Host "==> Frontend: installing dependencies" -ForegroundColor Cyan
Push-Location "$root\frontend"
if (-not (Test-Path ".env.local")) {
    Copy-Item ".env.example" ".env.local"
}
npm install
Pop-Location

Write-Host ""
Write-Host "Setup complete. Next steps:" -ForegroundColor Green
Write-Host "  1. Edit .env with real POSTGRES_* / SUPERADMIN_* values if you haven't."
Write-Host "  2. .\scripts\seed.ps1    (creates super admin + sample businesses)"
Write-Host "  3. .\scripts\start.ps1   (starts backend + frontend)"
