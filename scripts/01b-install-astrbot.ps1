# Step 1b: complete the AstrBot install inside the project venv.
# ASCII-only on purpose (PowerShell 5.1 + UTF-8 without BOM breaks parsing).
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$tmp = Join-Path $root '.tmp'
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$env:TEMP = $tmp
$env:TMP = $tmp
$env:PIP_CACHE_DIR = Join-Path $root '.pip-cache'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'

$base = 'C:\Users\54126\AppData\Local\Programs\Python\Python313\python.exe'
if (-not (Test-Path $base)) { $base = (Get-Command python).Source }
$venvDir = Join-Path $root '.venv'
$vpy = Join-Path $venvDir 'Scripts\python.exe'

if (-not (Test-Path $vpy)) {
    Write-Host '[1/4] creating venv ...'
    & $base -m venv --without-pip $venvDir
}

Write-Host '[2/4] checking pip inside venv ...'
& $vpy -m pip --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '      bootstrapping pip into venv ...'
    & $base -m pip install --no-cache-dir --target (Join-Path $venvDir 'Lib\site-packages') pip
}

& $vpy -m pip --version
if ($LASTEXITCODE -ne 0) { Write-Host 'FATAL: pip unavailable in venv'; exit 1 }

Write-Host '[3/4] installing astrbot (several minutes) ...'
& $vpy -m pip install astrbot
if ($LASTEXITCODE -ne 0) { Write-Host 'FATAL: pip install astrbot failed'; exit 1 }

Write-Host '[4/4] verifying ...'
& $vpy -c "import astrbot, sys; print('OK astrbot', getattr(astrbot, '__version__', '?'), '| python', sys.version.split()[0])"
& $vpy -m pip show astrbot | Select-String -Pattern 'Name|Version|Location'
Write-Host 'DONE'
