# WhatsAppBusinessAI - Automated security scan (Priority 10)
#   - bandit: static analysis for common Python security issues
#   - pip-audit: known-CVE scan of installed dependencies (base + dev requirements)
#   - audit_permissions: custom check that every view is tenant-scoped and
#     declares explicit permission_classes (see apps/common/management/commands/audit_permissions.py)
#
# Exits non-zero on any finding so it can be wired into CI as-is (see .github/workflows/security.yml).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$failed = $false

Push-Location "$root\backend"

Write-Host "==> bandit (static analysis)" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m bandit -r apps core config -x "*/migrations/*,*/tests/*"
if ($LASTEXITCODE -ne 0) { $failed = $true }

Write-Host ""
Write-Host "==> pip-audit (base requirements)" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m pip_audit -r requirements\base.txt
if ($LASTEXITCODE -ne 0) { $failed = $true }

Write-Host ""
Write-Host "==> pip-audit (development requirements)" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m pip_audit -r requirements\development.txt
if ($LASTEXITCODE -ne 0) { $failed = $true }

Write-Host ""
Write-Host "==> audit_permissions (tenant isolation + RBAC static audit)" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" manage.py audit_permissions
if ($LASTEXITCODE -ne 0) { $failed = $true }

Pop-Location

Write-Host ""
if ($failed) {
    Write-Host "Security scan FAILED - see findings above." -ForegroundColor Red
    exit 1
}
Write-Host "Security scan clean." -ForegroundColor Green
