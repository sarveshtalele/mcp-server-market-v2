@echo off
REM ============================================================
REM  Runs the FULL stack, each in its own window:
REM    1) Data API     :8000
REM    2) AG-UI agent  :8001
REM    3) Web frontend :3000   (CopilotKit chatbot)
REM ============================================================
setlocal
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "PY=%BACKEND%\.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo Backend venv missing. Run setup.bat first.
    pause
    exit /b 1
)

echo Starting Data API on http://127.0.0.1:8000 ...
start "SET Data API :8000" /D "%BACKEND%" cmd /k "%PY%" -m uvicorn data_api.main:app --port 8000

timeout /t 4 /nobreak >nul

echo Starting AG-UI agent on http://127.0.0.1:8001 ...
start "SET AG-UI Agent :8001" /D "%BACKEND%" cmd /k "%PY%" -m uvicorn agui_agent.main:app --port 8001

if exist "%FRONTEND%\node_modules" (
    echo Starting web frontend on http://localhost:3000 ...
    start "SET Frontend :3000" /D "%FRONTEND%" cmd /k npm run dev
) else (
    echo.
    echo NOTE: frontend\node_modules missing. Run this once:  cd frontend ^&^& npm install
)

echo.
echo Launched. Open the web chatbot at http://localhost:3000
pause
exit /b 0
