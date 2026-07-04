@echo off
title LoopGenerator
cd /d "%~dp0"

echo [~] Stopping old server (if running)...
:: 1. Kill the process holding the port (and all its children)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

:: 2. Failsafe: kill any hanging uvicorn workers for this project by matching command line
for /f "tokens=2 delims=," %%a in ('wmic process where "name='python.exe' and commandline like '%%uvicorn%%main:app%%'" get processid /format:csv 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

timeout /t 2 /nobreak >nul

echo [*] Starting server at http://localhost:8000
start "" "http://localhost:8000"
poetry run uvicorn main:app --reload > server.log 2>&1
