$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python command 'python' was not found. Install Python 3.10+ and run: python -m pip install -r requirements-demo.txt"
    exit 1
}

Push-Location $RepoRoot
try {
    & python -c "import streamlit" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Streamlit is not installed. Run: python -m pip install -r requirements-demo.txt"
        exit 1
    }
    & python -m streamlit run demo/app.py
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

