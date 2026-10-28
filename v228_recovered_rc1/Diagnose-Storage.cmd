@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-learning\Scripts\python.exe" goto missing
.venv-learning\Scripts\python.exe -u tools\diagnose_storage.py
set "storage_exit=%errorlevel%"
pause
exit /b %storage_exit%
:missing
echo Run Install-Demo-Learning.cmd once for this V2.28 folder.
pause
exit /b 1
