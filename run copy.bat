@echo off
title Suno Prompt Extractor
cd /d "%~dp0\.."

echo.
echo  ===================================
echo    Suno Prompt Extractor
echo  ===================================
echo.

echo  [~] Stopping old server (if running)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5050 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo  [*] Starting server at http://localhost:5050
echo  Press Ctrl+C to stop
echo.
start "" "http://localhost:5050"
poetry run python promptsExtractor/app.py
pause
