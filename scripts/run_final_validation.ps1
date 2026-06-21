param(
    [switch]$SkipDocker,
    [switch]$SkipStreamlitServer
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ValidationDir = Join-Path $RepoRoot "target/final-validation"
$LogDir = Join-Path $ValidationDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Invoke-FinalCommand {
    param(
        [string]$Name,
        [string]$Command,
        [string]$LogName
    )

    $LogPath = Join-Path $LogDir $LogName
    $Started = Get-Date
    Write-Host "Running $Name"
    Push-Location $RepoRoot
    try {
        powershell -NoProfile -ExecutionPolicy Bypass -Command $Command *> $LogPath
        $ExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $Ended = Get-Date
    return [ordered]@{
        name = $Name
        command = $Command
        exit_code = $ExitCode
        log_path = (Resolve-Path $LogPath).Path.Replace($RepoRoot.Path + "\", "").Replace("\", "/")
        elapsed_seconds = [math]::Round(($Ended - $Started).TotalSeconds, 3)
    }
}

$Results = @()
$Results += Invoke-FinalCommand "python-unittest" 'python -m unittest discover -s tests -p "test_*.py" -v' "python_unittest.log"
$Results += Invoke-FinalCommand "python-compileall" 'python -m compileall scripts demo tests' "python_compileall.log"
$Results += Invoke-FinalCommand "maven-package" 'mvn package' "maven_package.log"
if (-not $SkipDocker) {
    $Results += Invoke-FinalCommand "docker-hadoop-maven" 'powershell -ExecutionPolicy Bypass -File scripts/test_hadoop_maven_docker.ps1' "docker_hadoop_maven.log"
}
$Results += Invoke-FinalCommand "demo-tests" 'powershell -ExecutionPolicy Bypass -File scripts/test_demo.ps1' "demo_tests.log"
$StreamlitCommand = 'powershell -ExecutionPolicy Bypass -File scripts/validate_streamlit_final.ps1'
if ($SkipStreamlitServer) {
    $StreamlitCommand += ' -SkipServer'
}
$Results += Invoke-FinalCommand "streamlit-final-validation" $StreamlitCommand "streamlit_final_validation.log"
$Results += Invoke-FinalCommand "final-report-data" 'python scripts/build_final_report_data.py --output-dir target/final-report-data' "final_report_data.log"

$CommandManifest = [ordered]@{
    generated_by = "scripts/run_final_validation.ps1"
    commands = $Results
}
$CommandManifest | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $ValidationDir "command_results.json")

python scripts/run_final_validation.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$Failures = @($Results | Where-Object { $_.exit_code -ne 0 })
if ($Failures.Count -gt 0) {
    Write-Error "One or more final validation commands failed. See target/final-validation/logs."
    exit 1
}

Write-Host "Final validation completed successfully."
