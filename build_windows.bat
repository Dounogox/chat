@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv-build\Scripts\python.exe" (
    py -3 -m venv .venv-build
    if errorlevel 1 exit /b %errorlevel%
)

".venv-build\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b %errorlevel%

".venv-build\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b %errorlevel%

".venv-build\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name Brotherhood --icon chat_5962573.ico --collect-submodules socketio --collect-submodules engineio --collect-submodules websocket desktop_app.py
if errorlevel 1 exit /b %errorlevel%

echo.
echo Created dist\Brotherhood.exe