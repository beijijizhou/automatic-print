@echo off
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0.."

echo Automatic Print - Windows development setup
echo.

where git >nul 2>nul
if errorlevel 1 (
    echo ERROR: Git is not installed or is not available in PATH.
    echo Install Git for Windows, then run this file again.
    pause
    exit /b 1
)

py -3.12 --version >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python 3.12 is not installed.
    echo Install Python 3.12 with "Add Python to PATH" enabled.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating the project environment...
    py -3.12 -m venv .venv
    if errorlevel 1 goto :failed
)

echo Installing project requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Setup finished. Double-click run-dev.bat to start the app.
pause
exit /b 0

:failed
echo.
echo Setup failed. Copy the error above and send it to the developer.
pause
exit /b 1
