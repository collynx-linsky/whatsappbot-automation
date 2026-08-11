# WhatsAppBusinessAI - Restore the PostgreSQL database from a backup-db.ps1
# dump (Priority 9: backup/DR). DESTRUCTIVE: drops and recreates every
# object in the target database before restoring. Requires -Force to
# actually run, on top of the interactive confirmation prompt — two
# deliberate hurdles for an operation that overwrites live data.
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,

    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path $BackupFile)) {
    Write-Host "Backup file not found: $BackupFile" -ForegroundColor Red
    exit 1
}

$envFile = "$root\.env"
if (-not (Test-Path $envFile)) {
    Write-Host "No .env found - run scripts\setup.ps1 first (or copy .env.example to .env)." -ForegroundColor Red
    exit 1
}

$envVars = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.*)\s*$') {
        $envVars[$matches[1]] = $matches[2]
    }
}

$dbName = $envVars["POSTGRES_DB"]
$dbUser = $envVars["POSTGRES_USER"]
$dbPass = $envVars["POSTGRES_PASSWORD"]
$dbHost = $envVars["POSTGRES_HOST"]
$dbPort = $envVars["POSTGRES_PORT"]

Write-Host "This will DROP and RECREATE every object in database '$dbName' on $dbHost`:$dbPort," -ForegroundColor Red
Write-Host "then restore it from: $BackupFile" -ForegroundColor Red
if (-not $Force) {
    Write-Host "Re-run with -Force to actually proceed." -ForegroundColor Yellow
    exit 1
}
$confirm = Read-Host "Type the database name ('$dbName') to confirm"
if ($confirm -ne $dbName) {
    Write-Host "Confirmation did not match - aborting, nothing was touched." -ForegroundColor Yellow
    exit 1
}

$env:PGPASSWORD = $dbPass
try {
    & pg_restore -U $dbUser -h $dbHost -p $dbPort -d $dbName --clean --if-exists --no-owner $BackupFile
} finally {
    Remove-Item Env:\PGPASSWORD
}

Write-Host "Restore complete from $BackupFile" -ForegroundColor Green
Write-Host "Run scripts\migrate.ps1 next if the backup predates a since-applied migration." -ForegroundColor Cyan
