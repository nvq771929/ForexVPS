@echo off
setlocal
cd /d "%~dp0LearningSupervisor"
if not exist .venv-ai\Scripts\python.exe (
 echo Run Install-Local-AI-Assistant.cmd first.
 pause
 exit /b 1
)
set /p "V224_AI_SOURCE=Paste LIVE Binary journal directory without quotes: "
set /p "V224_AI_OFFSET=Verified live server UTC offset in minutes; Enter if unknown: "
set /p "V224_AI_CHANNEL=Unique assistant channel matching indicator; e.g. v224_demo: "
if not defined V224_AI_CHANNEL set "V224_AI_CHANNEL=v224_demo"
set /p "V224_AI_COMMON=Optional Terminal Common Files directory for chart display: "
set /p "V224_AI_CONFIG=Optional local_ai JSON path; Enter for facts-only report: "
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
.venv-ai\Scripts\python.exe launch_ai.py
pause
