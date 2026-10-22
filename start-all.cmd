@echo off
rem Start AstrBot first, wait for it to bind port 6199, then start NapCat.
setlocal
cd /d "%~dp0"

call "%~dp0start-astrbot.cmd"
if errorlevel 1 exit /b 1

echo [start-all] waiting for AstrBot to open port 6199 ...
set /a tries=0
:wait
set /a tries+=1
netstat -ano | findstr ":6199" | findstr "LISTENING" >nul
if not errorlevel 1 goto ready
if %tries% GEQ 30 (
    echo [start-all] AstrBot did not open 6199 after 60s. Check the AstrBot window.
    pause
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait

:ready
echo [start-all] AstrBot is ready on 6199.
call "%~dp0start-napcat.cmd"
echo.
echo [start-all] done. Run status.cmd to verify.
pause
exit /b 0
