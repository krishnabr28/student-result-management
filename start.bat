@echo off
setlocal
cd /d "%~dp0"
title Student Result Management System
if not exist ".venv\Scripts\python.exe" (
  echo The app is not set up yet. Double-click setup.bat first.
  pause
  exit /b 1
)
set "PORT=5000"
for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"APP_PORT=" .env 2^>nul') do set "PORT=%%~b"
echo Opening http://localhost:%PORT% in your browser in a few seconds.
echo Keep this window open while you use the app. Close it (or press Ctrl+C) to stop the app.
echo.
start "" /min cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:%PORT%"
".venv\Scripts\python.exe" run.py
echo.
echo The app has stopped.
pause
