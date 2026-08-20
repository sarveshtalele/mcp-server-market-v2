@echo off
REM ============================================================================
REM  mcp-server-market - start the whole stack on Windows
REM
REM  Starts agentgateway (:3111), the backend (:8000) and the Control Room
REM  UI (:3000), in that order. Run install.bat first.
REM
REM  Usage:  run.bat            start everything
REM          run.bat backend    just the backend
REM          run.bat gateway    just the gateway
REM          run.bat frontend   just the web UI
REM          run.bat seed       rebuild the synthetic dataset
REM
REM  Plain ASCII only - see the note in install.bat.
REM ============================================================================

setlocal
cd /d "%~dp0"

set "VENV_PY=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [ERROR] No virtualenv at backend\.venv
    echo         Run install.bat first.
    exit /b 1
)

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=all"

"%VENV_PY%" scripts\dev.py %TARGET%
exit /b %errorlevel%
