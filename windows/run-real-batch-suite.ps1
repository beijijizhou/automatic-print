param(
    [string]$ManifestPath = "windows/real-batch-suite.json",
    [string]$ArtifactRoot = "artifacts/acceptance",
    [string]$OutputRoot = "",
    [string]$CacheRoot = "C:\actions-runner\real-batch-cache",
    [string]$BatchIds = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$manifestFile = if ([IO.Path]::IsPathRooted($ManifestPath)) {
    $ManifestPath
} else { Join-Path $root $ManifestPath }
$artifactPath = if ([IO.Path]::IsPathRooted($ArtifactRoot)) {
    $ArtifactRoot
} else { Join-Path $root $ArtifactRoot }
$runToken = if ($env:GITHUB_RUN_ID) { $env:GITHUB_RUN_ID } else {
    Get-Date -Format "yyyyMMdd-HHmmss"
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path "C:\actions-runner\acceptance-runs" $runToken
}
$python = if ($env:PYTHON_EXE) { $env:PYTHON_EXE } else { "python" }
$testedCommit = (& git -C $root rev-parse HEAD).Trim()
$manifest = Get-Content -Raw -Encoding UTF8 $manifestFile | ConvertFrom-Json
$selectedIds = @($BatchIds.Split(';', [StringSplitOptions]::RemoveEmptyEntries) |
    ForEach-Object { $_.Trim() } | Where-Object { $_ })
$batches = @($manifest.batches | Where-Object {
    -not $selectedIds -or $selectedIds -contains $_.id
})
if (-not $batches) { throw "No manifest batches matched BatchIds: $BatchIds" }
New-Item -ItemType Directory -Force $artifactPath, $OutputRoot, $CacheRoot | Out-Null
Set-Content -Encoding UTF8 (Join-Path $artifactPath "tested-commit.txt") $testedCommit

$summary = @()
$failed = 0
foreach ($batch in $batches) {
    foreach ($cacheState in $batch.passes) {
        $reportRoot = Join-Path (Join-Path $artifactPath $batch.id) $cacheState
        $output = Join-Path (Join-Path $OutputRoot $batch.id) $cacheState
        $cache = Join-Path $CacheRoot $batch.id
        $reportDestination = Join-Path $reportRoot "report.json"
        New-Item -ItemType Directory -Force $reportRoot | Out-Null
        try {
            if (-not (Test-Path -LiteralPath $batch.path -PathType Container)) {
                throw "Staged batch does not exist: $($batch.path)"
            }
            if ($cacheState -eq "cold" -and (Test-Path -LiteralPath $cache)) {
                Remove-Item -LiteralPath $cache -Recurse -Force
            }
            if (Test-Path -LiteralPath $output) {
                Remove-Item -LiteralPath $output -Recurse -Force
            }
            New-Item -ItemType Directory -Force $output, $cache | Out-Null
            $arguments = @(
                (Join-Path $root "scripts\benchmark_header_gap.py"),
                "--source", $batch.path,
                "--output", $output,
                "--cache", $cache,
                "--workers", "4",
                "--parallel", [string]$(if ($batch.save_parallelism) { $batch.save_parallelism } else { 4 }),
                "--parts", [string]$(if ($batch.output_parts) { $batch.output_parts } else { 1 }),
                "--platform", $batch.platform,
                "--expected-images", [string]$batch.expected_images,
                "--tested-commit", $testedCommit,
                "--cache-state", $cacheState,
                "--report-name", "real-batch-report.json"
            )
            if ($null -ne $batch.max_generation_seconds) {
                $arguments += @("--max-seconds", [string]$batch.max_generation_seconds)
            }
            $stopwatch = [Diagnostics.Stopwatch]::StartNew()
            & $python @arguments *>&1 |
                Tee-Object -FilePath (Join-Path $reportRoot "run.log")
            $exitCode = $LASTEXITCODE
            $stopwatch.Stop()
            $reportFile = Join-Path $output "real-batch-report.json"
            if (Test-Path -LiteralPath $reportFile) {
                Copy-Item -LiteralPath $reportFile -Destination $reportDestination -Force
            }
            if ($exitCode -ne 0) {
                throw "Benchmark process exited with $exitCode"
            }
            $summary += [ordered]@{
                id=$batch.id; platform=$batch.platform; cache=$cacheState
                status="passed"; elapsed_seconds=[Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
                output=$output; report=$reportDestination
            }
        } catch {
            $failed += 1
            $_ | Out-String | Set-Content -Encoding UTF8 (Join-Path $reportRoot "failure.txt")
            $summary += [ordered]@{
                id=$batch.id; platform=$batch.platform; cache=$cacheState
                status="failed"; error=$_.Exception.Message; output=$output
                report=$(if (Test-Path -LiteralPath $reportDestination) { $reportDestination } else { "" })
            }
        }
    }
}

[ordered]@{
    tested_commit=$testedCommit
    manifest=(Resolve-Path -LiteralPath $manifestFile).Path
    output_root=$OutputRoot
    total=$summary.Count
    passed=@($summary | Where-Object status -eq "passed").Count
    failed=$failed
    results=$summary
} | ConvertTo-Json -Depth 8 |
    Set-Content -Encoding UTF8 (Join-Path $artifactPath "suite-summary.json")
if ($failed) {
    throw "$failed real-batch acceptance run(s) failed; remaining batches were still executed."
}
