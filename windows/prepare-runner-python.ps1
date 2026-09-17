param(
    [string]$RunnerRoot = "C:\actions-runner",
    [string]$PythonRoot = "$env:LOCALAPPDATA\Programs\Python\Python312"
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator."
}
if (-not (Test-Path -LiteralPath (Join-Path $PythonRoot "python.exe"))) {
    throw "Python 3.12 was not found at $PythonRoot."
}

$destination = Join-Path $RunnerRoot "externals\python"
if (Test-Path -LiteralPath $destination) {
    throw "Runner Python already exists at $destination."
}
New-Item -ItemType Directory -Force $destination | Out-Null
Copy-Item -Path (Join-Path $PythonRoot "*") -Destination $destination -Recurse -Force
& (Join-Path $destination "python.exe") --version
