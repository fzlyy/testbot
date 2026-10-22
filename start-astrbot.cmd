@echo off
rem Start AstrBot in its own window. Output is mirrored to logs\astrbot-console.log.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\astrbot.exe" (
    echo [ERROR] .venv not found. Run: powershell -ExecutionPolicy Bypass -File scripts\01b-install-astrbot.ps1
    pause
    exit /b 1
)

netstat -ano | findstr ":6185" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo [AstrBot] already running on port 6185 - nothing to do.
    exit /b 0
)

if not exist "logs" mkdir "logs"
echo [AstrBot] starting, WebUI will be http://127.0.0.1:6185
echo [AstrBot] log: logs\astrbot-console.log
start "AstrBot" powershell -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-astrbot.ps1"

echo [AstrBot] window opened. Wait about 20 seconds, then run status.cmd
exit /b 0
