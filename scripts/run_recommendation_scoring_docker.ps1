param(
    [string]$UserHistoryInputPath,
    [string]$SimilarityInputPath,
    [string]$OutputPath,
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

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$Dockerfile = Join-Path $RepoRoot "docker/maven-hadoop/Dockerfile"
$ImageName = "movie-recommender-hadoop-recommendation-scoring-validation:latest"

Assert-RelativeDockerPath $UserHistoryInputPath "UserHistoryInputPath"
Assert-RelativeDockerPath $SimilarityInputPath "SimilarityInputPath"
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

    $expectedFile = "tests/fixtures/recommendation-scoring/expected.txt"
    if (-not $UserHistoryInputPath -and -not $SimilarityInputPath -and -not $OutputPath) {
        & docker run --rm $ImageName bash -lc "scripts/run_recommendation_scoring.sh && diff -u $expectedFile target/recommendation-scoring-output/part-r-00000"
        exit $LASTEXITCODE
    }

    if (-not $UserHistoryInputPath) {
        $UserHistoryInputPath = "tests/fixtures/recommendation-scoring/user-history.txt"
    }
    if (-not $SimilarityInputPath) {
        $SimilarityInputPath = "tests/fixtures/recommendation-scoring/similarity.txt"
    }
    if (-not $OutputPath) {
        $OutputPath = "target/recommendation-scoring-output"
    }

    $dockerArgs = @(
        "run",
        "--rm",
        $ImageName,
        "bash",
        "scripts/run_recommendation_scoring.sh",
        $UserHistoryInputPath,
        $SimilarityInputPath,
        $OutputPath
    )
    & docker @dockerArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
