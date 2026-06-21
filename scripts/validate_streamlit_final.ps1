param(
    [int]$Port = 8501,
    [string]$Output = "target/final-validation/streamlit_validation.json",
    [switch]$SkipServer
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $RepoRoot "target/final-validation/logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Push-Location $RepoRoot
try {
    python -m unittest tests.test_demo_data_loader tests.test_demo_service tests.test_demo_app -v
    python scripts/validate_streamlit_final.py --output $Output

    if ($SkipServer) {
        Write-Host "Skipping Streamlit server health check."
        exit 0
    }

    python -c "import streamlit" | Out-Null
    $LogPath = Join-Path $LogDir "streamlit_final.out.log"
    $ErrorLogPath = Join-Path $LogDir "streamlit_final.err.log"
    $Process = Start-Process -FilePath "python" -ArgumentList @(
        "-m", "streamlit", "run", "demo/app.py",
        "--server.headless", "true",
        "--server.port", "$Port",
        "--browser.gatherUsageStats", "false"
    ) -WorkingDirectory $RepoRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $LogPath -RedirectStandardError $ErrorLogPath

    try {
        $Healthy = $false
        for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
            Start-Sleep -Seconds 1
            try {
                $Response = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:$Port/_stcore/health" -TimeoutSec 2
                if ($Response.StatusCode -eq 200) {
                    $Healthy = $true
                    break
                }
            } catch {
                if ($Process.HasExited) {
                    throw "Streamlit process exited before becoming healthy. See $LogPath and $ErrorLogPath"
                }
            }
        }
        if (-not $Healthy) {
            throw "Streamlit health check timed out. See $LogPath and $ErrorLogPath"
        }
        Write-Host "Streamlit final validation passed on port $Port."
    } finally {
        if ($Process -and -not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force
        }
    }
} finally {
    Pop-Location
}
