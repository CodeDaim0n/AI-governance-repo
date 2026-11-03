@echo off
setlocal
cd /d "%~dp0"
echo Starting Fabric Studio...
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 or newer is required. Install Python and add it to PATH.
  pause
  exit /b 1
)
if not exist ".venv-studio\Scripts\python.exe" (
  python -m venv .venv-studio
  if errorlevel 1 goto setup_failed
)
if not exist ".venv-studio\studio-installed.txt" (
  echo Installing the project. First-time setup requires internet access.
  ".venv-studio\Scripts\python.exe" -m pip install -e .
  if errorlevel 1 goto setup_failed
  echo Installed>".venv-studio\studio-installed.txt"
)
echo Keep this window open. Press Ctrl+C to stop Studio.
".venv-studio\Scripts\python.exe" -m fabric.studio --open
if errorlevel 1 (
  echo Studio could not start. Check the message above.
  pause
  exit /b 1
)
exit /b 0

:setup_failed
echo Setup failed. Check your Python installation and internet connection, then try again.
pause
exit /b 1
