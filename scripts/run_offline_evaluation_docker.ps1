param(
    [ValidateSet("cosine", "cooccurrence")]
    [string]$Method = "cosine",
    [int]$TopK = 10,
    [int]$TopL = 50,
    [int]$MinCommonUsers = 1,
    [int]$RelevanceThreshold = 4
)

$ErrorActionPreference = "Stop"

if ($TopK -lt 1) {
    throw "TopK must be at least 1."
}
if ($TopL -lt 1) {
    throw "TopL must be at least 1."
}
if ($MinCommonUsers -lt 1) {
    throw "MinCommonUsers must be at least 1."
}
if ($RelevanceThreshold -lt 1 -or $RelevanceThreshold -gt 5) {
    throw "RelevanceThreshold must be from 1 through 5."
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$Dockerfile = Join-Path $RepoRoot "docker/maven-hadoop/Dockerfile"
$ImageName = "movie-recommender-hadoop-offline-evaluation:latest"

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

    $dockerArgs = @(
        "run",
        "--rm",
        $ImageName,
        "bash",
        "scripts/run_offline_evaluation.sh",
        "--method",
        $Method,
        "--top-k",
        [string]$TopK,
        "--top-l",
        [string]$TopL,
        "--min-common-users",
        [string]$MinCommonUsers,
        "--relevance-threshold",
        [string]$RelevanceThreshold
    )
    & docker @dockerArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
