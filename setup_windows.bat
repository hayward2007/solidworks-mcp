@echo off
rem ---------------------------------------------------------------------------
rem  SolidWorks MCP - one-click Windows setup (double-click this file)
rem  Finds Python 3.10+ and runs setup_mcp.py, which creates .venv, installs
rem  requirements.txt, self-tests the server and registers it in Claude Desktop.
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
title SolidWorks MCP setup

set "PYCMD="
set "CHECK=import sys; sys.exit(sys.version_info < (3, 10))"

rem Look for Python: 1) py launcher / Python install manager  2) python on PATH  3) usual install folders
py -3 -c "%CHECK%" <nul >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD python -c "%CHECK%" <nul >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-3.*" "%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do if exist "%%~D\python.exe" "%%~D\python.exe" -c "%CHECK%" <nul >nul 2>&1 && set PYCMD="%%~D\python.exe"

if not defined PYCMD (
    echo Python 3.10 or newer was not found on this PC.
    echo Install it from https://www.python.org/downloads/ and run this file again.
    echo.
    pause
    exit /b 1
)

%PYCMD% "%~dp0setup_mcp.py"
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
