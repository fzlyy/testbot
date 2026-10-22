@echo off
rem Show whether the three ports are listening and how big the sticker bank is.
setlocal
cd /d "%~dp0"

echo ==== ports ====
call :check 6185 AstrBot-WebUI
call :check 6199 OneBot-reverse-WS
call :check 6099 NapCat-WebUI

echo.
echo ==== AstrBot HTTP ====
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest http://127.0.0.1:6185 -UseBasicParsing -TimeoutSec 4; 'WebUI: HTTP ' + $r.StatusCode } catch { 'WebUI: DOWN' }"

echo.
echo ==== sticker bank ====
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d = 'data\plugins\astrbot_plugin_sticker_bank\stickers'; if (Test-Path $d) { $f = Get-ChildItem $d -File | Where-Object { $_.Name -ne 'index.json' }; $mb = if ($f) { [math]::Round((($f | Measure-Object Length -Sum).Sum / 1MB), 1) } else { 0 }; 'stickers: ' + $f.Count + ' files, ' + $mb + ' MB' } else { 'stickers: not initialized' }"

echo.
echo ==== persona ====
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c = Get-Content 'data\cmd_config.json' -Raw -Encoding UTF8 | ConvertFrom-Json; 'active persona: ' + $c.agent_runner.config.persona.persona_id } catch { 'config unreadable' }"

echo.
exit /b 0

:check
netstat -ano | findstr ":%1" | findstr "LISTENING" >nul
if errorlevel 1 (echo   %1  %~2  DOWN) else (echo   %1  %~2  LISTENING)
exit /b 0
