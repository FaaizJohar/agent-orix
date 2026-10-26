$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$env:PYTHONPATH = "$scriptDir;$env:PYTHONPATH"
python -m cie.cli.main $args
