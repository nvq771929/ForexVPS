@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-learning\Scripts\python.exe" goto missing
.venv-learning\Scripts\python.exe tools\run_demo_learning.py --watch
set "learner_exit=%errorlevel%"
echo.
echo The local learner has stopped. No broker order was sent.
pause
exit /b %learner_exit%
:missing
echo Run Install-Demo-Learning.cmd once before starting this V2.28 learner.
pause
exit /b 1
