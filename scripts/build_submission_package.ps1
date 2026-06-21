param(
    [string]$Output = "dist/movie-recommender-hadoop-v1.0.0.zip",
    [switch]$IncludeUntracked
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Push-Location $RepoRoot
try {
    $Args = @("scripts/build_submission_package.py", "--output", $Output)
    if ($IncludeUntracked) {
        $Args += "--include-untracked"
    }
    python @Args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
