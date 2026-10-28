@echo off
setlocal
cd /d "%~dp0LearningSupervisor"
if not exist .venv\Scripts\python.exe (
 echo Run Install-Learning-Supervisor.cmd first.
 pause
 exit /b 1
)
set /p "V224_DIALOGUE_SOURCE=Paste LIVE V2.28 journal directory without quotes: "
set /p "V224_DIALOGUE_OFFSET=Verified live server UTC offset in minutes; Enter if unknown: "
set /p "V224_DIALOGUE_MODEL=Optional pre-lock model JSON; Enter for collect/abstain: "
set /p "V224_DIALOGUE_RECEIPT=Optional independent forward validation JSON; Enter for shadow: "
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
.venv\Scripts\python.exe launch_dialogue.py
pause
