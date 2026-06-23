@echo off
title LoopGenerator
cd /d "%~dp0"

echo [~] Stopping old server (if running)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [*] Starting server at http://localhost:8000
start "" "http://localhost:8000"
poetry run uvicorn main:app --reload > server.log 2>&1
