param(
    [string]$InputPath,
    [string]$OutputPath
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
$ImageName = "movie-recommender-hadoop-user-history-validation:latest"

Assert-RelativeDockerPath $InputPath "InputPath"
Assert-RelativeDockerPath $OutputPath "OutputPath"

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Error "Docker command 'docker' was not found."
    exit 1
}

Push-Location $RepoRoot
try {
    & docker build --no-cache -f $Dockerfile -t $ImageName .
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    if (-not $InputPath -and -not $OutputPath) {
        & docker run --rm $ImageName bash -lc "scripts/run_user_history.sh && diff -u tests/fixtures/user-history/expected.txt target/user-history-output/part-r-00000"
        exit $LASTEXITCODE
    }

    $dockerArgs = @("run", "--rm", $ImageName, "bash", "scripts/run_user_history.sh")
    if (-not $InputPath) {
        $InputPath = "tests/fixtures/user-history/ratings.csv"
    }
    $dockerArgs += $InputPath
    if ($OutputPath) {
        $dockerArgs += $OutputPath
    }
    & docker @dockerArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
