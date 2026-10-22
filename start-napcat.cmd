@echo off
rem Start NapCat. It needs administrator rights and will ask for UAC approval.
setlocal
cd /d "%~dp0"

if not exist "napcat\shell\launcher.bat" (
    echo [ERROR] napcat\shell\launcher.bat not found. Extract NapCat.Shell.zip into napcat\shell first.
    pause
    exit /b 1
)

netstat -ano | findstr ":6099" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo [NapCat] already running on port 6099 - nothing to do.
    exit /b 0
)

set "UNINST="
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQ" /v "UninstallString" 2^>nul') do set "UNINST=%%~b"

if not defined UNINST (
    echo [ERROR] QQ not found in registry. Install QQ 9.9.33 first.
    pause
    exit /b 1
)
echo [NapCat] QQ: %UNINST%
echo [NapCat] launching - approve the UAC prompt, then scan the QR code with your ALT QQ account.
start "" "%~dp0napcat\shell\launcher.bat"

echo [NapCat] window opened. WebUI will be http://127.0.0.1:6099 (token is printed in that window).
exit /b 0
