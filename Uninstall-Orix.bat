@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Agent Orix - Uninstaller

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
cd /d "%SCRIPT_DIR%"

echo ======================================================================
echo                     AGENT ORIX - UNINSTALLER
echo ======================================================================
echo.
echo This will remove the local virtual environment (.venv), build artifacts,
echo and desktop shortcuts.
echo Your source code, git repository, and model files will NOT be deleted.
echo.

set "CONFIRM=N"
set /p "CONFIRM=Are you sure you want to uninstall Agent Orix? (y/N): "
if /i not "!CONFIRM!"=="y" (
    echo [INFO] Uninstallation cancelled. No changes were made.
    pause
    exit /b 0
)

echo.
echo [1/3] Removing virtual environment (.venv)...
if exist "%SCRIPT_DIR%\.venv" (
    rmdir /s /q "%SCRIPT_DIR%\.venv" >nul 2>&1
    echo [OK] Removed .venv directory.
) else (
    echo [INFO] No .venv directory found.
)

echo.
echo [2/3] Cleaning build and cache artifacts...
if exist "%SCRIPT_DIR%\build" rmdir /s /q "%SCRIPT_DIR%\build" >nul 2>&1
if exist "%SCRIPT_DIR%\dist" rmdir /s /q "%SCRIPT_DIR%\dist" >nul 2>&1
for /d %%d in ("%SCRIPT_DIR%\*.egg-info") do (
    rmdir /s /q "%%d" >nul 2>&1
)
if exist "%SCRIPT_DIR%\.pytest_cache" rmdir /s /q "%SCRIPT_DIR%\.pytest_cache" >nul 2>&1
echo [OK] Temporary build caches removed.

echo.
echo [3/3] Removing desktop shortcut and run scripts...
powershell -NoProfile -Command "$path = [System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Agent Orix.lnk'); if (Test-Path $path) { Remove-Item $path -Force }" >nul 2>&1
if exist "%SCRIPT_DIR%\run-orix.bat" del "%SCRIPT_DIR%\run-orix.bat" >nul 2>&1
echo [OK] Launcher shortcuts removed.

echo.
echo ======================================================================
echo                     UNINSTALLATION COMPLETE
echo ======================================================================
echo.
echo Agent Orix environment has been cleanly removed from your system.
echo To reinstall in the future, simply run:
echo   Install-Orix.bat
echo.
pause
exit /b 0
