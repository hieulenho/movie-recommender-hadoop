$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python command 'python' was not found."
    exit 1
}

Push-Location $RepoRoot
try {
    & python -m unittest tests.test_demo_data_loader tests.test_demo_service tests.test_demo_app -v
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

