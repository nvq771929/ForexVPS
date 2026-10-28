@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install "torch==2.9.0" --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements-learning.txt
if errorlevel 1 goto fail
echo Installation complete. Read HUONG_DAN_VI.md.
pause
exit /b 0
:fail
echo Installation failed. Keep the error text for review.
pause
exit /b 1
