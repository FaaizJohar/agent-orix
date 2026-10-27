@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

if not exist "%SCRIPT_DIR%\pyproject.toml" (
    echo ======================================================================
    echo                     AGENT ORIX - WINDOWS INSTALLER
    echo        Conversational Terminal AI ^& Local Workspace Assistant
    echo ======================================================================
    set "TARGET_DIR=%USERPROFILE%\.agent-orix"
    echo Setting up Agent Orix in: !TARGET_DIR!...
    where git >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        if exist "!TARGET_DIR!\.git" (
            echo Updating existing repository in !TARGET_DIR!...
            git -C "!TARGET_DIR!" pull --quiet
        ) else (
            echo Cloning repository into !TARGET_DIR!...
            git clone --depth 1 https://github.com/FaaizJohar/agent-orix.git "!TARGET_DIR!"
        )
    ) else (
        echo Downloading Agent Orix release archive...
        curl.exe -sSL "https://github.com/FaaizJohar/agent-orix/archive/refs/heads/main.zip" -o "%TEMP%\agent-orix.zip"
        if not exist "!TARGET_DIR!" mkdir "!TARGET_DIR!"
        tar.exe -xf "%TEMP%\agent-orix.zip" -C "%TEMP%"
        xcopy /s /e /y /q "%TEMP%\agent-orix-main\*" "!TARGET_DIR!\" >nul 2>&1
        del /f /q "%TEMP%\agent-orix.zip" >nul 2>&1
        rmdir /s /q "%TEMP%\agent-orix-main" >nul 2>&1
    )
    if not exist "!TARGET_DIR!\Install-Orix.bat" (
        echo [ERROR] Failed to obtain Agent Orix repository files.
        pause
        exit /b 1
    )
    call "!TARGET_DIR!\Install-Orix.bat" %*
    exit /b !ERRORLEVEL!
)

call "%SCRIPT_DIR%\Install-Orix.bat" %*
