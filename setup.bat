@echo off
REM BizVision AI - Windows bootstrap shim. Delegates to setup.ps1.
where pwsh >nul 2>nul
if %ERRORLEVEL%==0 (
    pwsh -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
) else (
    powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
)
