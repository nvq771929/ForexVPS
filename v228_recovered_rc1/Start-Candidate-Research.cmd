@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-learning\Scripts\python.exe" goto missing
.venv-learning\Scripts\python.exe -u tools\candidate_research.py --watch
set "research_exit=%errorlevel%"
pause
exit /b %research_exit%
:missing
echo Run Install-Demo-Learning.cmd once for this V2.28 folder.
pause
exit /b 1
