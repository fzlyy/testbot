# Run AstrBot in the foreground, mirroring output to logs\astrbot-console.log.
# ASCII only: Windows PowerShell 5.1 mishandles UTF-8 .ps1 files without a BOM.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir "astrbot-console.log"

$exe = Join-Path $root ".venv\Scripts\astrbot.exe"
if (-not (Test-Path $exe)) {
    Write-Host "[ERROR] astrbot.exe not found at $exe" -ForegroundColor Red
    exit 1
}

Write-Host "[AstrBot] starting ... log: $log" -ForegroundColor Cyan
& $exe run 2>&1 | Tee-Object -FilePath $log
