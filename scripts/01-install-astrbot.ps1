# Step 1: create an isolated venv in this project and install AstrBot from PyPI.
# ASCII-only on purpose: Windows PowerShell 5.1 misreads UTF-8 .ps1 files without a BOM.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:PIP_CACHE_DIR = Join-Path $root '.pip-cache'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'

$py = 'C:\Users\54126\AppData\Local\Programs\Python\Python313\python.exe'
if (-not (Test-Path $py)) { $py = (Get-Command python).Source }

Write-Host "[1/4] base python: $py"
& $py --version

if (-not (Test-Path (Join-Path $root '.venv\Scripts\python.exe'))) {
    Write-Host '[2/4] creating .venv ...'
    & $py -m venv (Join-Path $root '.venv')
}
else {
    Write-Host '[2/4] .venv already exists, reuse it'
}

$vpy = Join-Path $root '.venv\Scripts\python.exe'
Write-Host '[3/4] upgrading pip ...'
& $vpy -m pip install --upgrade pip -q

Write-Host '[4/4] installing astrbot (this takes a few minutes) ...'
& $vpy -m pip install astrbot

& $vpy -c "import astrbot, sys; print('OK astrbot', getattr(astrbot,'__version__','?'), '|', sys.version.split()[0])"
Write-Host 'DONE'
