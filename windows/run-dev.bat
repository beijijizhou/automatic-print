@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo The development environment is not ready.
    echo Run windows\setup-dev.bat first.
    pause
    exit /b 1
)

echo Starting Automatic Print in auto-reload mode...
echo Keep this window open while testing.
".venv\Scripts\python.exe" dev.py

if errorlevel 1 (
    echo.
    echo Automatic Print stopped with an error.
    pause
)
