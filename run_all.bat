@echo off
REM ============================================================
REM  Runs the FULL stack, each in its own window:
REM    1) Data API      :8000
REM    2) agentgateway  :3111  (governance + audit log in front of the MCP server)
REM    3) AG-UI agent   :8001
REM    4) Web frontend  :3000  (CopilotKit chatbot)
REM ============================================================
setlocal
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "GATEWAY=%BACKEND%\mcp_server\gateway"
set "PY=%BACKEND%\.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo Backend venv missing. Run setup.bat first.
    pause
    exit /b 1
)

echo Starting Data API on http://127.0.0.1:8000 ...
start "SET Data API :8000" /D "%BACKEND%" cmd /k "%PY%" -m uvicorn data_api.main:app --port 8000

timeout /t 4 /nobreak >nul

if not exist "%GATEWAY%\bin\agentgateway.exe" (
    echo agentgateway.exe missing - run backend\mcp_server\gateway\setup.ps1 once first.
    pause
    exit /b 1
)
echo Starting agentgateway on http://127.0.0.1:3111 ...
start "SET agentgateway :3111" /D "%GATEWAY%" powershell -NoExit -File run.ps1

echo Waiting for agentgateway to be ready...
set "GW_READY="
for /L %%i in (1,1,15) do (
    powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient('127.0.0.1',3111)).Close(); exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "GW_READY=1"
        goto :gw_ready
    )
    timeout /t 1 /nobreak >nul
)
:gw_ready
if not defined GW_READY (
    echo agentgateway did not come up on port 3111 after 15s - check its window for errors.
    pause
    exit /b 1
)

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
