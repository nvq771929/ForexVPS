@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Run INSTALL_LEARNING.cmd first.
 pause
 exit /b 1
)
set /p "V224_JOURNAL=Paste LIVE V2.23 journal directory, without quotation marks: "
set /p "V224_COMMON=Optional Terminal\Common\Files directory, or Enter to skip MT4 panel: "
set /p "V224_OFFSET=Verified live server UTC offset in MINUTES, or Enter for unknown: "
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
rem Values are passed as argv; no CALL, eval or shell expression expansion.
.venv\Scripts\python.exe launch_watch.py
pause
