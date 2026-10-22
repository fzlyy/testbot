@echo off
rem Wrapper so the check script runs even when the PowerShell execution policy is Restricted.
rem Usage: scripts\check-stack.cmd [ -ApiKey sk-xxx ] [ -Model deepseek-flash ] [ -SkipApi ]
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check-stack.ps1" %*
exit /b %ERRORLEVEL%
