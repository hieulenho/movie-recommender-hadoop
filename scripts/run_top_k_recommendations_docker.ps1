param(
    [string]$UserHistoryInputPath,
    [string]$RawPredictionInputPath,
    [string]$OutputPath,
    [int]$TopK = 2,
    [switch]$NoCache
)

$ErrorActionPreference = "Stop"

function Assert-RelativeDockerPath {
    param(
        [string]$PathText,
        [string]$Name
    )
    if ($PathText -and [System.IO.Path]::IsPathRooted($PathText)) {
        throw "$Name must be relative to the repository when passed to the Docker wrapper."
    }
}

if ($TopK -lt 1) {
    throw "TopK must be at least 1."
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$Dockerfile = Join-Path $RepoRoot "docker/maven-hadoop/Dockerfile"
$ImageName = "movie-recommender-hadoop-top-k-recommendation-validation:latest"

Assert-RelativeDockerPath $UserHistoryInputPath "UserHistoryInputPath"
Assert-RelativeDockerPath $RawPredictionInputPath "RawPredictionInputPath"
Assert-RelativeDockerPath $OutputPath "OutputPath"

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Error "Docker command 'docker' was not found."
    exit 1
}

Push-Location $RepoRoot
try {
    $buildArgs = @("build", "-f", $Dockerfile, "-t", $ImageName)
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }
    $buildArgs += "."
    & docker @buildArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $expectedFile = "tests/fixtures/top-k-recommendation/expected-top2.txt"
    if (-not $UserHistoryInputPath -and -not $RawPredictionInputPath -and -not $OutputPath -and $TopK -eq 2) {
        & docker run --rm $ImageName bash -lc "scripts/run_top_k_recommendations.sh && diff -u $expectedFile target/top-k-recommendation-output/part-r-00000"
        exit $LASTEXITCODE
    }

    if (-not $UserHistoryInputPath) {
        $UserHistoryInputPath = "tests/fixtures/top-k-recommendation/user-history.txt"
    }
    if (-not $RawPredictionInputPath) {
        $RawPredictionInputPath = "tests/fixtures/top-k-recommendation/raw-predictions.txt"
    }
    if (-not $OutputPath) {
        $OutputPath = "target/top-k-recommendation-output"
    }

    $dockerArgs = @(
        "run",
        "--rm",
        $ImageName,
        "bash",
        "scripts/run_top_k_recommendations.sh",
        $UserHistoryInputPath,
        $RawPredictionInputPath,
        $OutputPath,
        [string]$TopK
    )
    & docker @dockerArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
