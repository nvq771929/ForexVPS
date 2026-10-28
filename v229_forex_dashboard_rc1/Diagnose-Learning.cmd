@echo off
setlocal
cd /d "%~dp0"
echo V2.29 - diagnose existing cache and candidate. No retraining or activation.
if not exist ".venv-learning\Scripts\python.exe" goto missing
.venv-learning\Scripts\python.exe tools\diagnose_learning.py
set "diagnose_exit=%errorlevel%"
pause
exit /b %diagnose_exit%
:missing
echo Run Install-Demo-Learning.cmd once.
pause
exit /b 1
