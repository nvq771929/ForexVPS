@echo off
setlocal
cd /d "%~dp0"
echo V2.28 - TCN / Logistic / HGB research. No model activates in MT4.
echo Select prepared_history_v211.json.gz from the completed Train-History output.
if not exist ".venv-learning\Scripts\python.exe" goto missing
.venv-learning\Scripts\python.exe tools\train_deep_history.py %*
set "deep_exit=%errorlevel%"
pause
exit /b %deep_exit%
:missing
echo Run Install-Deep-Learning.cmd once before deep training.
pause
exit /b 1
