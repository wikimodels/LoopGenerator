@echo off
title LoopGenerator
cd /d "%~dp0"

echo [~] Stopping old server (if running)...
:: 1. Kill the process holding port 8000 (regardless of connection state)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 "') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

:: 2. Failsafe: kill any remaining process holding port 8000 via PowerShell
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Stop-Process -Force -ErrorAction SilentlyContinue" >nul 2>&1

timeout /t 2 /nobreak >nul

echo [*] Starting server at http://localhost:8000
start "" "http://localhost:8000"
poetry run uvicorn main:app --reload > server.log 2>&1
