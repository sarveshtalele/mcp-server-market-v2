@echo off
REM ============================================================================
REM  mcp-server-market - one-shot installer for Windows
REM
REM  Creates the Python virtualenv, installs backend + frontend dependencies,
REM  downloads agentgateway, builds the synthetic dataset, and writes the .env
REM  files. Run it once, then start everything with:  run.bat
REM
REM  Usage:  install.bat
REM
REM  Plain ASCII only, on purpose: Windows PowerShell and cmd read batch files
REM  in the system codepage, and a stray non-ASCII character can break parsing.
REM ============================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   mcp-server-market  -  installing
echo ============================================================
echo.

REM ---------------------------------------------------------------- Python ---
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python was not found on PATH.
    echo         Install Python 3.11 or newer from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" during setup.
    goto :fail
)

for /f "tokens=2 delims= " %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"
echo [1/7] Python found: %PYVER%

for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set "PYMAJOR=%%a"
    set "PYMINOR=%%b"
)
if %PYMAJOR% LSS 3 goto :oldpython
if %PYMAJOR% EQU 3 if %PYMINOR% LSS 11 goto :oldpython
goto :pythonok

:oldpython
echo [ERROR] Python 3.11 or newer is required (found %PYVER%).
echo         This project uses BaseExceptionGroup, a 3.11 builtin.
goto :fail

:pythonok

REM ------------------------------------------------------------------ venv ---
echo [2/7] Creating virtualenv at backend\.venv ...
if exist "backend\.venv\Scripts\python.exe" (
    echo       already present, reusing it
) else (
    %PY% -m venv backend\.venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtualenv.
        goto :fail
    )
)
set "VENV_PY=%CD%\backend\.venv\Scripts\python.exe"

REM ------------------------------------------------------- backend packages ---
echo [3/7] Installing backend dependencies (this takes a minute) ...
"%VENV_PY%" -m pip install --upgrade pip --quiet
"%VENV_PY%" -m pip install -r backend\requirements-dev.txt --quiet
if errorlevel 1 (
    echo [ERROR] Backend dependency installation failed.
    goto :fail
)
echo       done

REM ------------------------------------------------------------ agentgateway ---
echo [4/7] Installing agentgateway ...
"%VENV_PY%" scripts\get_gateway.py
if errorlevel 1 (
    echo [ERROR] agentgateway installation failed.
    echo         Every MCP consumer goes through it, so the audit log stays
    echo         empty without it. Check your network connection, or install it
    echo         manually - see README section 2.3.
    goto :fail
)

REM ------------------------------------------------------------------ seed ---
echo [5/7] Building the synthetic dataset ...
pushd backend
"%VENV_PY%" -m core.seed --reset
if errorlevel 1 (
    popd
    echo [ERROR] Seeding failed.
    goto :fail
)
popd

REM ------------------------------------------------------------------- env ---
echo [6/7] Writing configuration files ...
if exist "backend\.env" (
    echo       backend\.env already exists, leaving it alone
) else (
    copy /y "backend\.env.example" "backend\.env" >nul
    echo       created backend\.env  -  add LLM_API_KEY there to enable the chat
)
if exist "frontend\.env.local" (
    echo       frontend\.env.local already exists, leaving it alone
) else (
    copy /y "frontend\.env.local.example" "frontend\.env.local" >nul
    echo       created frontend\.env.local
)

REM -------------------------------------------------------------- frontend ---
echo [7/7] Installing frontend dependencies ...
where npm >nul 2>&1
if errorlevel 1 (
    echo       [SKIPPED] npm not found on PATH.
    echo       The backend, the MCP server and the audit log all work without it.
    echo       Install Node.js 18+ from https://nodejs.org/ and re-run this
    echo       script if you want the Control Room web UI.
) else (
    pushd frontend
    call npm install --no-audit --no-fund
    if errorlevel 1 (
        popd
        echo [ERROR] npm install failed.
        goto :fail
    )
    popd
    echo       done
)

echo.
echo ============================================================
echo   Installed.
echo ============================================================
echo.
echo   Start everything:        run.bat
echo   Control Room:            http://localhost:3000
echo   API docs:                http://127.0.0.1:8000/docs
echo   Audit log (JSON):        http://127.0.0.1:8000/observability/calls
echo.
echo   Optional: to enable the web chat, put your LLM credentials in
echo   backend\.env  (LLM_API_KEY, and LLM_BASE_URL if you use a proxy).
echo   Everything else works without them.
echo.
echo   To connect Claude Desktop, Claude Code, VS Code Copilot or
echo   Antigravity, see README section 4.
echo.
goto :end

:fail
echo.
echo Installation did not complete. Nothing was started.
echo.
exit /b 1

:end
endlocal
exit /b 0
