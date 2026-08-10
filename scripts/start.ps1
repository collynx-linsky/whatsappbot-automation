# WhatsAppBusinessAI - Start local development (backend + celery worker + frontend)
# Each service runs in its own PowerShell window so you can watch/stop them
# independently. Redis is expected to already be running (docker compose up
# -d redis, or scripts\setup.ps1). Ctrl+C in each window stops that service,
# or use scripts\stop.ps1 to kill everything at once.
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Starting Django (http://localhost:8000)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; .venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000"

Write-Host "==> Starting Celery worker" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; .venv\Scripts\python.exe -m celery -A config.celery worker --loglevel=info --pool=solo -Q default,high_priority,low_priority"

Write-Host "==> Starting Next.js (http://localhost:3000)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Write-Host ""
Write-Host "All services launching in separate windows:" -ForegroundColor Green
Write-Host "  Backend API:  http://localhost:8000/api/v1/"
Write-Host "  API docs:     http://localhost:8000/api/docs/"
Write-Host "  Django admin: http://localhost:8000/admin/"
Write-Host "  Frontend:     http://localhost:3000/"
