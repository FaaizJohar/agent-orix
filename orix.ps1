$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$venvPy = Join-Path $scriptDir ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    & $venvPy -m cie.cli.main $args
} else {
    $env:PYTHONPATH = "$scriptDir;$env:PYTHONPATH"
    python -m cie.cli.main $args
}
