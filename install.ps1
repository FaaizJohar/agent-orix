# Agent Orix - PowerShell One-Click & One-Line Installer for Windows
# Supports both local execution and web one-line execution without cloning:
#   irm https://raw.githubusercontent.com/FaaizJohar/agent-orix/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
if (-not $scriptDir -or -not (Test-Path (Join-Path $scriptDir "pyproject.toml"))) {
    $installDir = Join-Path $env:USERPROFILE ".agent-orix"
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "               AGENT ORIX - ONE-LINE WINDOWS INSTALLER" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "Setting up Agent Orix in: $installDir..."
    if (Get-Command git -ErrorAction SilentlyContinue) {
        if (Test-Path "$installDir\.git") {
            git -C $installDir pull --quiet
        } else {
            git clone --depth 1 https://github.com/FaaizJohar/agent-orix.git $installDir
        }
    } else {
        $zipUrl = "https://github.com/FaaizJohar/agent-orix/archive/refs/heads/main.zip"
        $tempZip = Join-Path $env:TEMP "agent-orix-main.zip"
        Invoke-WebRequest -Uri $zipUrl -OutFile $tempZip
        Expand-Archive -Path $tempZip -DestinationPath $env:TEMP -Force
        Remove-Item -Force $tempZip
        if (Test-Path $installDir) { Remove-Item -Recurse -Force $installDir }
        Move-Item -Path (Join-Path $env:TEMP "agent-orix-main") -Destination $installDir -Force
    }
    $scriptDir = $installDir
}

Set-Location $scriptDir
& "$scriptDir\Install-Orix.bat"
