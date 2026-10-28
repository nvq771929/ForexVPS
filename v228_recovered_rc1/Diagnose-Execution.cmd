@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-learning\Scripts\python.exe" goto missing
.venv-learning\Scripts\python.exe tools\diagnose_execution.py %*
set "review_exit=%errorlevel%"
pause
exit /b %review_exit%
:missing
echo Run Install-Demo-Learning.cmd or Install-Deep-Learning.cmd once.
pause
exit /b 1
