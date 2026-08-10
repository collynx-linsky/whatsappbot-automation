# WhatsAppBusinessAI - Create the super admin and load sample dev data
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" manage.py createsuperadmin
& ".venv\Scripts\python.exe" manage.py seed_dev_data
Pop-Location
