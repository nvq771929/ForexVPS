@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-learning\Scripts\python.exe" goto missing
echo V2.29 Forex News - paste MT4 Data Folder, FX_V222, or its LIVE_* folder.
echo Calendar output: MQL4\Files\FX_V222\news_calendar.csv
.venv-learning\Scripts\python.exe -u tools\forex_news.py
set "news_exit=%errorlevel%"
pause
exit /b %news_exit%
:missing
echo Run Install-Demo-Learning.cmd once for this V2.29 folder.
pause
exit /b 1
