param(
    [string]$DatasetDir = "data/raw/github-reference",
    [int]$TopL = 10,
    [int]$TopK = 5,
    [int]$MinCommonUsers = 1,
    [int]$RelevanceThreshold = 4,
    [ValidateSet("github-reference-3col", "netflix-raw", "auto")]
    [string]$SourceFormat = "github-reference-3col"
)

$ErrorActionPreference = "Stop"

if ($TopL -lt 1) { throw "TopL must be at least 1." }
if ($TopK -lt 1) { throw "TopK must be at least 1." }
if ($MinCommonUsers -lt 1) { throw "MinCommonUsers must be at least 1." }
if ($RelevanceThreshold -lt 1 -or $RelevanceThreshold -gt 5) {
    throw "RelevanceThreshold must be from 1 through 5."
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$DatasetPath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $DatasetDir))
$Dockerfile = Join-Path $RepoRoot "docker/maven-hadoop/Dockerfile"
$ImageName = "movie-recommender-hadoop-full-reference:latest"

if (-not (Test-Path $DatasetPath -PathType Container)) {
    Write-Error "Dataset directory does not exist: $DatasetDir"
    exit 1
}
if (-not (Test-Path (Join-Path $DatasetPath "movie_titles.txt") -PathType Leaf)) {
    Write-Error "Dataset directory must contain movie_titles.txt: $DatasetDir"
    exit 1
}

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

    $repoMount = "${RepoRoot}:/workspace"
    $dockerArgs = @(
        "run",
        "--rm",
        "-v",
        $repoMount,
        "-w",
        "/workspace",
        $ImageName,
        "bash",
        "scripts/run_full_reference_dataset.sh",
        "--dataset-dir",
        $DatasetDir.Replace("\", "/"),
        "--top-l",
        [string]$TopL,
        "--top-k",
        [string]$TopK,
        "--min-common-users",
        [string]$MinCommonUsers,
        "--relevance-threshold",
        [string]$RelevanceThreshold,
        "--source-format",
        $SourceFormat
    )
    & docker @dockerArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
