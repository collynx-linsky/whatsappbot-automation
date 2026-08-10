# WhatsAppBusinessAI - Run Django migrations
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" manage.py makemigrations
& ".venv\Scripts\python.exe" manage.py migrate
Pop-Location
