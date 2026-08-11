# WhatsAppBusinessAI - Backup the PostgreSQL database (Priority 9: backup/DR).
# Reads connection details from .env, dumps to backups/ in pg_dump's
# custom compressed format (-Fc — supports selective/parallel restore,
# unlike a plain .sql text dump), and prunes dumps older than
# -RetentionDays (default 14). Safe to run repeatedly / on a schedule
# (Windows Task Scheduler locally, cron on a real server — see
# docs/backup-recovery.md).
param(
    [int]$RetentionDays = 14
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

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

$backupDir = "$root\backups"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupFile = "$backupDir\waba_$dbName`_$timestamp.dump"

Write-Host "Backing up '$dbName' from $dbHost`:$dbPort to $backupFile" -ForegroundColor Cyan
$env:PGPASSWORD = $dbPass
try {
    & pg_dump -U $dbUser -h $dbHost -p $dbPort -Fc -f $backupFile $dbName
} finally {
    Remove-Item Env:\PGPASSWORD
}

if (-not (Test-Path $backupFile)) {
    Write-Host "Backup failed - no output file was created." -ForegroundColor Red
    exit 1
}
$sizeMb = [math]::Round((Get-Item $backupFile).Length / 1MB, 2)
Write-Host "Backup complete: $backupFile ($sizeMb MB)" -ForegroundColor Green

# Retention: delete dumps older than $RetentionDays, this database only
# (the glob is scoped to this $dbName so backups of any other local
# project sharing this backups/ directory convention are never touched).
$cutoff = (Get-Date).AddDays(-$RetentionDays)
$old = Get-ChildItem "$backupDir\waba_$dbName`_*.dump" | Where-Object { $_.LastWriteTime -lt $cutoff }
if ($old) {
    Write-Host "Pruning $($old.Count) backup(s) older than $RetentionDays days:" -ForegroundColor Yellow
    $old | ForEach-Object {
        Write-Host "  - $($_.Name)"
        Remove-Item $_.FullName -Force
    }
}
