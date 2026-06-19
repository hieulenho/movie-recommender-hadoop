$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$Dockerfile = Join-Path $RepoRoot "docker/maven-hadoop/Dockerfile"
$ImageName = "movie-recommender-hadoop-maven-validation:latest"

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Error "Docker command 'docker' was not found."
    exit 1
}

Push-Location $RepoRoot
try {
    & docker build -f $Dockerfile -t $ImageName .
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & docker run --rm $ImageName mvn -B test
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
