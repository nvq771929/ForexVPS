@echo off
setlocal
cd /d "%~dp0"
echo V2.29 History Training - separate execution and price research.
echo For T+1 select the completed TESTER folder. For reuse select prepared_history_v211.json.gz (or compatible V210 cache).
if not exist ".venv-learning\Scripts\python.exe" goto missing
.venv-learning\Scripts\python.exe tools\train_history.py
set "history_exit=%errorlevel%"
pause
exit /b %history_exit%
:missing
echo Run Install-Demo-Learning.cmd once before training.
pause
exit /b 1
