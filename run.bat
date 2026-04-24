@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON_CMD=python"

if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%ROOT%.venv\Scripts\python.exe"
)

echo Starting PacMan backend and frontend...
echo Backend terminal: Flask API on http://127.0.0.1:5000
echo Frontend terminal: Vite dev server on http://127.0.0.1:5173

start "PacMan Backend" cmd /k "cd /d "%ROOT%" && "%PYTHON_CMD%" -m pip install -r requirements.txt && "%PYTHON_CMD%" game.py --api --host 127.0.0.1 --port 5000"
start "PacMan Frontend" cmd /k "cd /d "%ROOT%frontend" && npm install && npm run dev"

echo.
echo Both terminals were launched.
echo Close this window or keep it open.

endlocal
