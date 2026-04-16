@echo off
setlocal

set "ROOT=%~dp0"
set "FOCUS_API_BASE=http://120.77.145.202:9000"
cd /d "%ROOT%"

where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH.
    pause
    exit /b 1
)

if not exist "%ROOT%electron-dist\node_modules" (
    echo [ERROR] Missing electron-dist\node_modules
    echo Please run:
    echo   cd electron-dist
    echo   npm.cmd install
    pause
    exit /b 1
)

echo [INFO] Starting Electron app...
start "Focus App" cmd /k "cd /d ""%ROOT%electron-dist"" && set FOCUS_API_BASE=%FOCUS_API_BASE% && npm.cmd start"

echo [INFO] Launch commands sent.
echo [INFO] Backend check: http://120.77.145.202:9000/docs
exit /b 0
