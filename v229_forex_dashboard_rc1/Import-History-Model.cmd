@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-learning\Scripts\python.exe" goto missing
echo Stop the Python live learner before importing. Keep the V207 chart attached.
.venv-learning\Scripts\python.exe tools\import_history.py
set "history_exit=%errorlevel%"
pause
exit /b %history_exit%
:missing
echo Run Install-Demo-Learning.cmd once before importing.
pause
exit /b 1
