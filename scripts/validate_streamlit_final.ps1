param(
    [int]$Port = 8501,
    [string]$Output = "target/final-validation/streamlit_movielens_1m_validation.json",
    [ValidateSet("cosine", "cooccurrence")]
    [string]$Method = "cosine",
    [switch]$SkipServer
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $RepoRoot "target/final-validation/logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Invoke-Checked {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

Push-Location $RepoRoot
try {
    Invoke-Checked "Streamlit demo unit tests" {
        python -m unittest tests.test_demo_data_loader tests.test_demo_service tests.test_demo_app -v
    }
    Invoke-Checked "Streamlit artifact validation" {
        python scripts/validate_streamlit_final.py --output $Output --method $Method --app-test-passed
    }

    if ($SkipServer) {
        Write-Host "Skipping Streamlit server health check."
        exit 0
    }

    Invoke-Checked "Streamlit import check" {
        python -c "import streamlit"
    }
    $LogPath = Join-Path $LogDir "streamlit_final.out.log"
    $ErrorLogPath = Join-Path $LogDir "streamlit_final.err.log"
    $Process = Start-Process -FilePath "python" -ArgumentList @(
        "-m", "streamlit", "run", "demo/app.py",
        "--server.headless", "true",
        "--server.port", "$Port",
        "--server.address", "127.0.0.1",
        "--browser.gatherUsageStats", "false"
    ) -WorkingDirectory $RepoRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $LogPath -RedirectStandardError $ErrorLogPath

    try {
        $Healthy = $false
        $HealthUris = @(
            "http://127.0.0.1:$Port/_stcore/health",
            "http://localhost:$Port/_stcore/health",
            "http://127.0.0.1:$Port/healthz",
            "http://localhost:$Port/healthz"
        )
        for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
            Start-Sleep -Seconds 1
            foreach ($HealthUri in $HealthUris) {
                try {
                    $Response = Invoke-WebRequest -UseBasicParsing -Uri $HealthUri -TimeoutSec 2
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
            if ($Healthy) {
                break
            }
        }
        if (-not $Healthy) {
            throw "Streamlit health check timed out. See $LogPath and $ErrorLogPath"
        }
        Invoke-Checked "Streamlit final validation" {
            python scripts/validate_streamlit_final.py --output $Output --method $Method --app-test-passed --health-check-passed
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
