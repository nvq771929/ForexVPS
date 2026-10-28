@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto plainpython
py -3 -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11 or newer is required'"
if errorlevel 1 goto failed
py -3 -m venv .venv-learning
if errorlevel 1 goto failed
goto install
:plainpython
python -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11 or newer is required'"
if errorlevel 1 goto failed
python -m venv .venv-learning
:install
if errorlevel 1 goto failed
.venv-learning\Scripts\python.exe -m pip install -r requirements-learning.txt
if errorlevel 1 goto failed
.venv-learning\Scripts\python.exe tools\run_demo_learning.py --help
if errorlevel 1 goto failed
echo.
echo Installation complete. For existing Tester data, run Train-History.cmd.
echo For new live demo signals, attach V2.29 in MT4 and run Start-Demo-Learning.cmd.
pause
exit /b 0
:failed
echo.
echo Installation failed. Preserve this output. Python 3.11+ and Internet are required for installation.
pause
exit /b 1
