@echo off
setlocal
cd /d "%~dp0"
echo V2.28 - Install CPU deep-learning research. GPU is not required.
if exist ".venv-learning\Scripts\python.exe" goto install
where py >nul 2>&1
if errorlevel 1 goto plainpython
py -3 -c "import sys,struct; assert sys.version_info >= (3,11) and struct.calcsize('P') == 8, 'Python 3.11+ 64-bit required'"
if errorlevel 1 goto failed
py -3 -m venv .venv-learning
if errorlevel 1 goto failed
goto install
:plainpython
python -c "import sys,struct; assert sys.version_info >= (3,11) and struct.calcsize('P') == 8, 'Python 3.11+ 64-bit required'"
if errorlevel 1 goto failed
python -m venv .venv-learning
if errorlevel 1 goto failed
:install
.venv-learning\Scripts\python.exe -m pip install -r requirements-deep.txt
if errorlevel 1 goto failed
.venv-learning\Scripts\python.exe -c "import torch; x=torch.tensor([1.,2.]); assert float(x.sum()) == 3.; print('CPU PyTorch ready:',torch.__version__)"
if errorlevel 1 goto failed
echo Installation complete. Run Train-Deep-History.cmd with the completed V2.11 cache.
pause
exit /b 0
:failed
echo Installation failed. Preserve this output. Python 3.11+ 64-bit and Internet are required.
pause
exit /b 1
