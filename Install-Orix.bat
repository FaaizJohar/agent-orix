@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Agent Orix - Windows Installer

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
cd /d "%SCRIPT_DIR%"

echo ======================================================================
echo                     AGENT ORIX - WINDOWS INSTALLER
echo        Conversational Terminal AI ^& Local Workspace Assistant
echo ======================================================================
echo.

:: -----------------------------------------------------------------------
:: Step 1: Detect Supported Python Version (>= 3.10)
:: -----------------------------------------------------------------------
echo [1/5] Checking Python installation...

set "PYTHON_EXE="

:: Test python command
python -c "import sys; sys.exit(0 if sys.version_info.major == 3 and sys.version_info.minor >= 10 else 1)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%i"
)

:: If not found, test py launcher
if "!PYTHON_EXE!"=="" (
    py -3 -c "import sys; sys.exit(0 if sys.version_info.major == 3 and sys.version_info.minor >= 10 else 1)" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%i"
    )
)

if "!PYTHON_EXE!"=="" (
    echo [ERROR] Python 3.10 or newer was not detected on your system.
    echo.
    echo Please install Python 3.10+ 64-bit from the official website:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Make sure to check the box "Add python.exe to PATH"
    echo during Python installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python -V 2^>nul') do set "PY_VER=%%v"
if "!PY_VER!"=="" (
    for /f "tokens=2 delims= " %%v in ('py -3 -V 2^>nul') do set "PY_VER=%%v"
)
echo [OK] Detected Python !PY_VER! at !PYTHON_EXE!

:: -----------------------------------------------------------------------
:: Step 2: Create Isolated Virtual Environment (.venv)
:: -----------------------------------------------------------------------
echo.
echo [2/5] Setting up isolated Python environment .venv...

set "VENV_DIR=%SCRIPT_DIR%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if exist "%VENV_PY%" (
    echo [OK] Existing virtual environment found at: %VENV_DIR%
) else (
    echo Creating virtual environment in: %VENV_DIR%
    "!PYTHON_EXE!" -m venv "%VENV_DIR%"
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        echo Please ensure you have write permissions in this directory.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
)

:: -----------------------------------------------------------------------
:: Step 3: Install Agent Orix and Dependencies
:: -----------------------------------------------------------------------
echo.
echo [3/5] Installing Agent Orix packages and dependencies...

"%VENV_PY%" -m pip install -e "%SCRIPT_DIR%"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install Agent Orix dependencies.
    echo Please check your internet connection or package cache and try again.
    pause
    exit /b 1
)
echo [OK] Agent Orix installed in editable mode.

:: -----------------------------------------------------------------------
:: Step 4: Detect Local AI Runtime ^& Configured Model (Ollama)
:: -----------------------------------------------------------------------
echo.
echo [4/5] Checking local AI runtime Ollama...

set "OLLAMA_DETECTED=0"
set "MODEL_DETECTED=0"

where curl.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    curl.exe -s --connect-timeout 2 http://127.0.0.1:11434/api/tags > "%TEMP%\ollama_tags.json" 2>nul
    if %ERRORLEVEL% EQU 0 (
        set "OLLAMA_DETECTED=1"
        findstr /i "cavrix-code" "%TEMP%\ollama_tags.json" >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            set "MODEL_DETECTED=1"
        )
    )
    if exist "%TEMP%\ollama_tags.json" del "%TEMP%\ollama_tags.json" >nul 2>&1
)

if "!OLLAMA_DETECTED!"=="1" (
    echo [OK] Ollama service detected running on http://127.0.0.1:11434
    if "!MODEL_DETECTED!"=="1" (
        echo [OK] Target AI model 'cavrix-code:latest' is available in Ollama.
    ) else (
        echo [NOTE] Ollama is running, but model 'cavrix-code:latest' was not found in tags.
        echo        Orix can still run tools and workflows offline, or you can point
        echo        to another model by setting: set CIE_MODEL_NAME=your-model-name
    )
) else (
    echo [INFO] Ollama local service was not detected on localhost:11434.
    echo        Orix can run in standalone tool/scripting mode right away.
    echo        For full conversational AI chat, install and run Ollama from:
    echo          https://ollama.com/
)

:: -----------------------------------------------------------------------
:: Step 5: Setup Launchers ^& Desktop Shortcut
:: -----------------------------------------------------------------------
echo.
echo [5/5] Creating launcher scripts...

:: Create run-orix.bat in root
(
    echo @echo off
    echo setlocal
    echo chcp 65001 ^>nul 2^>^&1
    echo set "SCRIPT_DIR=%%~dp0"
    echo if "%%SCRIPT_DIR:~-1%%"=="\" set "SCRIPT_DIR=%%SCRIPT_DIR:~0,-1%%"
    echo if exist "%%SCRIPT_DIR%%\.venv\Scripts\python.exe" ^(
    echo     "%%SCRIPT_DIR%%\.venv\Scripts\python.exe" -m cie.cli.main %%*
    echo ^) else ^(
    echo     python -m cie.cli.main %%*
    echo ^)
) > "%SCRIPT_DIR%\run-orix.bat"

echo [OK] Created launcher: %SCRIPT_DIR%\run-orix.bat

:: Check if non-interactive
if "%NON_INTERACTIVE%"=="1" (
    echo.
    echo [OK] Non-interactive installation complete.
    exit /b 0
)

:: Optional Desktop Shortcut creation via PowerShell
set "CREATE_SHORTCUT=N"
set /p "CREATE_SHORTCUT=Would you like to create a Desktop shortcut? (Y/n): "
if /i "!CREATE_SHORTCUT!"=="Y" (
    powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Agent Orix.lnk')); $s.TargetPath = '%SCRIPT_DIR%\run-orix.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Save()" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo [OK] Desktop shortcut 'Agent Orix' created.
    ) else (
        echo [INFO] Could not create desktop shortcut. You can launch Orix using run-orix.bat.
    )
)

echo.
echo ======================================================================
echo                     INSTALLATION COMPLETE!
echo ======================================================================
echo.
echo You can start Agent Orix anytime by running:
echo   .\run-orix.bat
echo or:
echo   .\orix.bat
echo.

set "LAUNCH_NOW=N"
set /p "LAUNCH_NOW=Would you like to launch Agent Orix now? (y/N): "
if /i "!LAUNCH_NOW!"=="y" (
    echo Launching Agent Orix...
    call "%SCRIPT_DIR%\run-orix.bat"
)

exit /b 0
