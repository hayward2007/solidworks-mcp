@echo off
rem ---------------------------------------------------------------------------
rem  SolidWorks MCP - one-click Windows setup (double-click this file)
rem  In a downloaded copy of the repository it runs install.ps1 from this folder.
rem  On its own (for example saved by Claude into Downloads) it runs the latest
rem  installer from GitHub, which puts the code into %USERPROFILE%\solidworks-mcp.
rem  Options are passed on, for example:  setup_windows.bat -InstallPython
rem ---------------------------------------------------------------------------
setlocal
title SolidWorks MCP setup
set "PS=powershell -NoProfile -ExecutionPolicy Bypass"
set "URL=https://raw.githubusercontent.com/hayward2007/solidworks-mcp/main/install.ps1"
set "MODE=remote"
if exist "%~dp0install.ps1" if exist "%~dp0setup_mcp.py" set "MODE=local"
if "%MODE%"=="local" %PS% -File "%~dp0install.ps1" %*
if "%MODE%"=="remote" %PS% -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072; & ([scriptblock]::Create((irm '%URL%'))) %*"
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
