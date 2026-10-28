@echo off
setlocal
cd /d "%~dp0LearningSupervisor"
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto fail
py -3 -m venv .venv-ai
if errorlevel 1 goto fail
.venv-ai\Scripts\python.exe -c "import assistant.worker; print('V2.29 local assistant ready; language model optional.')"
if errorlevel 1 goto fail
echo Local assistant installed with Python standard library only.
echo Read LOCAL_AI_V224_VI.md before starting. No market model installed.
pause
exit /b 0
:fail
echo Setup failed. Python 3.11 or newer is required. Keep the error text for review.
pause
exit /b 1
