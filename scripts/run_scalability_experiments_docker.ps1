param(
    [ValidateSet("smoke", "standard", "extended")]
    [string]$Profile = "smoke",
    [string]$OutputDir = "target/scalability-benchmark",
    [string]$ExperimentFilter,
    [switch]$Resume,
    [switch]$FailFast,
    [switch]$KeepStageOutput
)

$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
    param([string]$PathText)
    if ([System.IO.Path]::IsPathRooted($PathText)) {
        return [System.IO.Path]::GetFullPath($PathText)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $PathText))
}

function Assert-SafeHostOutputPath {
    param([string]$ResolvedOutput)
    $repo = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
    $output = [System.IO.Path]::GetFullPath($ResolvedOutput).TrimEnd('\')
    $root = [System.IO.Path]::GetPathRoot($output).TrimEnd('\')
    if ($output -eq $root) {
        throw "Refusing to use a filesystem root as benchmark output: $ResolvedOutput"
    }

    $protected = @(
        $repo,
        (Join-Path $repo ".git"),
        (Join-Path $repo "src"),
        (Join-Path $repo "scripts"),
        (Join-Path $repo "docs"),
        (Join-Path $repo "data"),
        (Join-Path $repo "tests"),
        (Join-Path $repo "report"),
        (Join-Path $repo "config"),
        (Join-Path $repo "docker")
    )
    foreach ($protectedPath in $protected) {
        $normalizedProtected = [System.IO.Path]::GetFullPath($protectedPath).TrimEnd('\')
        if ($normalizedProtected -eq $repo) {
            if ($output -eq $normalizedProtected) {
                throw "Refusing to use protected repository path as benchmark output: $ResolvedOutput"
            }
        } elseif ($output -eq $normalizedProtected -or $output.StartsWith("$normalizedProtected\")) {
            throw "Refusing to use protected repository path as benchmark output: $ResolvedOutput"
        }
    }
}

function Invoke-GitText {
    param([string[]]$GitArgs)
    try {
        $text = (& git @GitArgs 2>$null) -join "`n"
        if ($LASTEXITCODE -ne 0) {
            return ""
        }
        return $text.Trim()
    } catch {
        return ""
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$Dockerfile = Join-Path $RepoRoot "docker/maven-hadoop/Dockerfile"
$ImageName = "movie-recommender-hadoop-scalability-benchmark:latest"
$ResolvedOutput = Resolve-RepoPath $OutputDir
Assert-SafeHostOutputPath $ResolvedOutput

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Error "Docker command 'docker' was not found."
    exit 1
}

New-Item -ItemType Directory -Force -Path $ResolvedOutput | Out-Null

Push-Location $RepoRoot
try {
    $GitCommit = Invoke-GitText @("rev-parse", "HEAD")
    $GitBranch = Invoke-GitText @("branch", "--show-current")
    $GitStatus = Invoke-GitText @("status", "--porcelain")
    $GitDirty = if ($GitStatus) { "true" } else { "false" }

    & docker build -f $Dockerfile -t $ImageName .
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $mountSpec = "${ResolvedOutput}:/benchmark-output"
    $dockerArgs = @(
        "run",
        "--rm",
        "-v",
        $mountSpec,
        "-e",
        "BENCHMARK_DOCKER_IMAGE=$ImageName",
        "-e",
        "BENCHMARK_GIT_COMMIT=$GitCommit",
        "-e",
        "BENCHMARK_GIT_BRANCH=$GitBranch",
        "-e",
        "BENCHMARK_GIT_DIRTY=$GitDirty",
        $ImageName,
        "python3",
        "scripts/run_scalability_experiments.py",
        "--profile",
        $Profile,
        "--profiles-file",
        "config/scalability_profiles.json",
        "--output-dir",
        "/benchmark-output",
        "--execution-mode",
        "docker"
    )

    if ($ExperimentFilter) {
        $dockerArgs += "--experiment-filter"
        $dockerArgs += $ExperimentFilter
    }
    if ($Resume) {
        $dockerArgs += "--resume"
    }
    if ($FailFast) {
        $dockerArgs += "--fail-fast"
    }
    if ($KeepStageOutput) {
        $dockerArgs += "--keep-stage-output"
    }

    & docker @dockerArgs
    $exitCode = $LASTEXITCODE
    Write-Host "Benchmark artifacts: $ResolvedOutput"
    exit $exitCode
} finally {
    Pop-Location
}
