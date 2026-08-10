# WhatsAppBusinessAI - Stop local development processes started by start.ps1
# Matches on command line (manage.py runserver / celery / next dev) rather
# than killing every python.exe/node.exe on the machine.
$root = Split-Path -Parent $PSScriptRoot
$rootEscaped = [regex]::Escape($root)

$killed = 0
Get-CimInstance Win32_Process | Where-Object {
    $cmd = $_.CommandLine
    if (-not $cmd) { return $false }
    if ($cmd -notmatch $rootEscaped) { return $false }
    return ($cmd -match "manage\.py runserver") -or ($cmd -match "celery") -or ($cmd -match "next dev") -or ($cmd -match "next-server")
} | ForEach-Object {
    Write-Host "Stopping PID $($_.ProcessId): $($_.CommandLine)" -ForegroundColor Yellow
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    $killed++
}

if ($killed -eq 0) {
    Write-Host "No matching WhatsAppBusinessAI dev processes were running." -ForegroundColor DarkGray
} else {
    Write-Host "Stopped $killed process(es)." -ForegroundColor Green
}
