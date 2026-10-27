@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

if not exist "%SCRIPT_DIR%\pyproject.toml" (
    echo ======================================================================
    echo                     AGENT ORIX - WINDOWS INSTALLER
    echo        Conversational Terminal AI ^& Local Workspace Assistant
    echo ======================================================================
    echo Setting up Agent Orix in: %USERPROFILE%\.agent-orix...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/FaaizJohar/agent-orix/main/install.ps1 | iex"
    exit /b %ERRORLEVEL%
)

call "%SCRIPT_DIR%\Install-Orix.bat" %*
