param(
    [Parameter(Mandatory = $true)]
    [string]$BatchPaths,
    [string]$ArtifactRoot = "artifacts/real-batches"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactPath = Join-Path $root $ArtifactRoot
$python = if ($env:PYTHON_EXE) { $env:PYTHON_EXE } else { "python" }
New-Item -ItemType Directory -Force $artifactPath | Out-Null

$batches = $BatchPaths.Split(";", [System.StringSplitOptions]::RemoveEmptyEntries) |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ }
if (-not $batches) {
    throw "No real batch folders were supplied."
}

$summary = @()
foreach ($batch in $batches) {
    if (-not (Test-Path -LiteralPath $batch -PathType Container)) {
        throw "Real batch folder does not exist: $batch"
    }
    $source = (Resolve-Path -LiteralPath $batch).Path
    $safeName = (Split-Path -Leaf $source) -replace '[^A-Za-z0-9._-]', '_'
    $runRoot = Join-Path $artifactPath $safeName
    $output = Join-Path $runRoot "output"
    $cache = Join-Path $runRoot "cache"
    New-Item -ItemType Directory -Force $output, $cache | Out-Null

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    & $python (Join-Path $root "scripts\benchmark_header_gap.py") `
        --source $source --output $output --cache $cache --workers 4 --parallel 4 `
        *>&1 | Tee-Object -FilePath (Join-Path $runRoot "run.log")
    $exitCode = $LASTEXITCODE
    $stopwatch.Stop()
    $summary += [ordered]@{
        batch = $source
        exit_code = $exitCode
        elapsed_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
        report = Join-Path $output "独立基准测试.json"
    }
    if ($exitCode -ne 0) {
        $summary | ConvertTo-Json -Depth 4 |
            Set-Content -Encoding UTF8 (Join-Path $artifactPath "summary.json")
        throw "Real batch regression failed: $source"
    }
}

$summary | ConvertTo-Json -Depth 4 |
    Set-Content -Encoding UTF8 (Join-Path $artifactPath "summary.json")
