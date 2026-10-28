@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-learning\Scripts\python.exe" goto missing
.venv-learning\Scripts\python.exe -u tools\news_calendar.py
set "news_exit=%errorlevel%"
pause
exit /b %news_exit%
:missing
echo Run Install-Demo-Learning.cmd once for this V2.29 folder.
pause
exit /b 1
