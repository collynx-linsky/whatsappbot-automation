# WhatsAppBusinessAI - Create the native PostgreSQL role/database for local dev.
# Prompts for the `postgres` superuser password (not stored anywhere) and
# reads the target role/db name + password from .env at the project root.
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

Write-Host "Creating role '$dbUser' and database '$dbName' on $dbHost`:$dbPort" -ForegroundColor Cyan
$superPassword = Read-Host -Prompt "Enter the postgres superuser password" -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($superPassword)
$env:PGPASSWORD = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

$sql = @"
DO `$`$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$dbUser') THEN
      CREATE ROLE $dbUser WITH LOGIN PASSWORD '$dbPass' CREATEDB;
   END IF;
END
`$`$;
"@

$sql | psql -U postgres -h $dbHost -p $dbPort -v ON_ERROR_STOP=1
psql -U postgres -h $dbHost -p $dbPort -tc "SELECT 1 FROM pg_database WHERE datname = '$dbName'" |
    Select-String "1" | Out-Null
if (-not $?) {
    psql -U postgres -h $dbHost -p $dbPort -c "CREATE DATABASE $dbName OWNER $dbUser;"
}
psql -U postgres -h $dbHost -p $dbPort -c "GRANT ALL PRIVILEGES ON DATABASE $dbName TO $dbUser;"

Remove-Item Env:\PGPASSWORD
Write-Host "Done. Role '$dbUser' and database '$dbName' are ready." -ForegroundColor Green
