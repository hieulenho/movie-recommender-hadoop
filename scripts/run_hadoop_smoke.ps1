param(
    [string]$InputPath,
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
    param([string]$PathText)
    if ([System.IO.Path]::IsPathRooted($PathText)) {
        return [System.IO.Path]::GetFullPath($PathText)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $PathText))
}

function Assert-SafeOutputPath {
    param([string]$ResolvedOutput)
    $repo = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
    $output = [System.IO.Path]::GetFullPath($ResolvedOutput).TrimEnd('\')
    $protected = @(
        $repo,
        (Join-Path $repo ".git"),
        (Join-Path $repo "src"),
        (Join-Path $repo "scripts"),
        (Join-Path $repo "docs"),
        (Join-Path $repo "data"),
        (Join-Path $repo "tests"),
        (Join-Path $repo "results"),
        (Join-Path $repo "report")
    )

    foreach ($protectedPath in $protected) {
        $normalizedProtected = [System.IO.Path]::GetFullPath($protectedPath).TrimEnd('\')
        if ($normalizedProtected -eq $repo) {
            if ($output -eq $normalizedProtected) {
                throw "Refusing to remove protected repository path: $ResolvedOutput"
            }
        } elseif ($output -eq $normalizedProtected -or $output.StartsWith("$normalizedProtected\")) {
            throw "Refusing to remove protected repository path: $ResolvedOutput"
        }
    }
    if ([System.IO.Path]::GetPathRoot($output).TrimEnd('\') -eq $output) {
        throw "Refusing to remove filesystem root: $ResolvedOutput"
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))

if (-not $InputPath) {
    $InputPath = "tests/fixtures/hadoop-smoke/input.txt"
}
if (-not $OutputPath) {
    $OutputPath = "target/hadoop-smoke-output"
}

$ResolvedInput = Resolve-RepoPath $InputPath
$ResolvedOutput = Resolve-RepoPath $OutputPath
Assert-SafeOutputPath $ResolvedOutput

if (-not (Test-Path -LiteralPath $ResolvedInput -PathType Leaf)) {
    Write-Error "Smoke input file does not exist: $ResolvedInput"
    exit 1
}

$mvn = Get-Command mvn -ErrorAction SilentlyContinue
if (-not $mvn) {
    Write-Error "Maven command 'mvn' was not found."
    exit 1
}

if (Test-Path -LiteralPath $ResolvedOutput) {
    Remove-Item -LiteralPath $ResolvedOutput -Recurse -Force
}

Push-Location $RepoRoot
try {
    & mvn -q -DskipTests package
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $execArgs = "--local `"$ResolvedInput`" `"$ResolvedOutput`""
    & mvn -q exec:java "-Dexec.args=$execArgs"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $PartFile = Join-Path $ResolvedOutput "part-r-00000"
    if (-not (Test-Path -LiteralPath $PartFile -PathType Leaf)) {
        Write-Error "Reducer output was not created: $PartFile"
        exit 1
    }

    Get-Content -LiteralPath $PartFile
} finally {
    Pop-Location
}
