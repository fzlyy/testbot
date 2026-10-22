@echo off
rem Stop AstrBot and NapCat by the ports they listen on.
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo This will stop:
echo   - AstrBot on ports 6185 and 6199
echo   - NapCat on port 6099, which also closes the QQ instance NapCat runs in
echo.
choice /c YN /n /m "Continue? [Y/N] "
if errorlevel 2 exit /b 0
echo.

call :kill 6185 AstrBot
call :kill 6199 AstrBot
call :kill 6099 NapCat

echo.
echo Done. Run status.cmd to verify.
pause
exit /b 0

:kill
set "FOUND="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%~1" ^| findstr "LISTENING"') do (
    echo   stopping %~2 port %~1 PID %%p
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Stop-Process -Id %%p -Force -ErrorAction SilentlyContinue"
    set "FOUND=1"
)
if not defined FOUND echo   port %~1 nothing listening
exit /b 0
