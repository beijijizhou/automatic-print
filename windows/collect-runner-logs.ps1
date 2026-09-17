param([string]$Destination = "artifacts/logs")

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$target = Join-Path $root $Destination
New-Item -ItemType Directory -Force $target | Out-Null

$locations = @(
    (Join-Path $env:LOCALAPPDATA "AutomaticPrint\logs"),
    "C:\Windows\ServiceProfiles\NetworkService\AppData\Local\AutomaticPrint\logs"
) | Select-Object -Unique

foreach ($location in $locations) {
    if (-not (Test-Path -LiteralPath $location -PathType Container)) {
        continue
    }
    $owner = if ($location -like "*NetworkService*") { "network-service" } else { "runner-user" }
    $ownerTarget = Join-Path $target $owner
    New-Item -ItemType Directory -Force $ownerTarget | Out-Null
    Get-ChildItem -LiteralPath $location -File -ErrorAction SilentlyContinue |
        Copy-Item -Destination $ownerTarget -Force
}

Get-ComputerInfo -Property WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture |
    Format-List | Out-File -Encoding UTF8 (Join-Path $target "windows-info.txt")
$python = if ($env:PYTHON_EXE) { $env:PYTHON_EXE } else { "python" }
& $python --version 2>&1 | Out-File -Encoding UTF8 (Join-Path $target "python-version.txt")
