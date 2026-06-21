param(
    [string]$DatasetDir = "data/raw/movielens-1m/ml-1m",
    [int]$TopL = 50,
    [int]$TopK = 10,
    [int]$MinCommonUsers = 5,
    [int]$RelevanceThreshold = 4,
    [int]$Reducers = 4,
    [switch]$Resume,
    [switch]$PreflightOnly,
    [switch]$KeepIntermediate,
    [string]$ForceStage = ""
)

$ErrorActionPreference = "Stop"

if ($TopL -lt 1) { throw "TopL must be at least 1." }
if ($TopK -lt 1) { throw "TopK must be at least 1." }
if ($MinCommonUsers -lt 1) { throw "MinCommonUsers must be at least 1." }
if ($Reducers -lt 1) { throw "Reducers must be at least 1." }
if ($RelevanceThreshold -lt 1 -or $RelevanceThreshold -gt 5) {
    throw "RelevanceThreshold must be from 1 through 5."
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$DatasetPath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $DatasetDir))
$Dockerfile = Join-Path $RepoRoot "docker/maven-hadoop/Dockerfile"
$ImageName = "movie-recommender-hadoop-movielens:latest"

if (-not (Test-Path $DatasetPath -PathType Container)) {
    Write-Error "Dataset directory does not exist: $DatasetDir"
    exit 1
}
foreach ($Required in @("ratings.dat", "movies.dat", "users.dat")) {
    if (-not (Test-Path (Join-Path $DatasetPath $Required) -PathType Leaf)) {
        Write-Error "Dataset directory must contain $Required`: $DatasetDir"
        exit 1
    }
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
    $datasetMount = "${DatasetPath}:/movielens-raw:ro"
    $dockerArgs = @(
        "run",
        "--rm",
        "-v",
        $repoMount,
        "-v",
        $datasetMount,
        "-w",
        "/workspace",
        $ImageName,
        "bash",
        "scripts/run_movielens_1m.sh",
        "--dataset-dir",
        "/movielens-raw",
        "--top-l",
        [string]$TopL,
        "--top-k",
        [string]$TopK,
        "--min-common-users",
        [string]$MinCommonUsers,
        "--relevance-threshold",
        [string]$RelevanceThreshold,
        "--reducers",
        [string]$Reducers
    )
    if ($Resume) { $dockerArgs += "--resume" }
    if ($PreflightOnly) { $dockerArgs += "--preflight-only" }
    if ($KeepIntermediate) { $dockerArgs += "--keep-intermediate" }
    if ($ForceStage.Trim() -ne "") {
        $dockerArgs += @("--force-stage", $ForceStage.Trim())
    }
    & docker @dockerArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
