param(
    [ValidateSet("cosine", "cooccurrence")]
    [string]$Method = "cosine",
    [string]$InputPath,
    [string]$OutputPath,
    [int]$MinCommonUsers = 1,
    [int]$TopL = 3
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

if ($MinCommonUsers -lt 1) {
    throw "MinCommonUsers must be at least 1."
}
if ($TopL -lt 1) {
    throw "TopL must be at least 1."
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$Dockerfile = Join-Path $RepoRoot "docker/maven-hadoop/Dockerfile"
$ImageName = "movie-recommender-hadoop-item-similarity-validation:latest"

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

    $expectedFile = if ($Method -eq "cosine") {
        "tests/fixtures/similarity/cosine-expected-top3.txt"
    } else {
        "tests/fixtures/similarity/cooccurrence-expected-top3.txt"
    }

    if (-not $InputPath -and -not $OutputPath -and $MinCommonUsers -eq 1 -and $TopL -eq 3) {
        & docker run --rm $ImageName bash -lc "scripts/run_item_similarity.sh $Method && diff -u $expectedFile target/item-similarity-output/part-r-00000"
        exit $LASTEXITCODE
    }

    $dockerArgs = @("run", "--rm", $ImageName, "bash", "scripts/run_item_similarity.sh", $Method)
    if (-not $InputPath) {
        $InputPath = "tests/fixtures/similarity/pair-stats.txt"
    }
    if (-not $OutputPath) {
        $OutputPath = "target/item-similarity-output"
    }
    $dockerArgs += $InputPath
    $dockerArgs += $OutputPath
    $dockerArgs += [string]$MinCommonUsers
    $dockerArgs += [string]$TopL
    & docker @dockerArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
