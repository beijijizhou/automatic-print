@echo off
setlocal
cd /d "%~dp0.."

where git >nul 2>nul
if errorlevel 1 (
    echo ERROR: Git is not installed or is not available in PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo The development environment is not ready.
    echo Run windows\setup-dev.bat first.
    pause
    exit /b 1
)

for /f "delims=" %%i in ('git status --porcelain') do (
    echo ERROR: This test computer has local code changes.
    echo Update was stopped to avoid overwriting them.
    git status --short
    pause
    exit /b 1
)

echo Downloading approved code from GitHub...
git pull --ff-only origin main
if errorlevel 1 goto :failed

echo Checking project requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Update finished.
echo If run-dev.bat is open, the app will restart automatically.
pause
exit /b 0

:failed
echo.
echo Update failed. Copy the error above and send it to the developer.
pause
exit /b 1
