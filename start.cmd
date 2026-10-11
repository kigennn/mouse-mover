@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto dependencies
echo Preparing Mouse Mover...
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if errorlevel 1 goto setup_failed

:dependencies
".venv\Scripts\python.exe" -c "import importlib.util; raise SystemExit(importlib.util.find_spec('pyautogui') is None)"
if not errorlevel 1 goto run
echo Installing Mouse Mover dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto setup_failed

:run
".venv\Scripts\python.exe" -u mouse_mover.py %*
set "taskExitCode=%errorlevel%"
if not "%taskExitCode%"=="0" pause
exit /b %taskExitCode%

:setup_failed
echo.
echo Setup failed. Install Python 3.9 or newer and check your internet connection.
echo Run start.cmd again when ready.
pause
exit /b 1
