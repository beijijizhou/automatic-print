param(
    [string]$RegistrationToken,
    [string]$RepositoryUrl = "https://github.com/beijijizhou/automatic-print",
    [string]$RunnerRoot = "C:\actions-runner",
    [string]$RunnerName = $env:COMPUTERNAME
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not $RegistrationToken) {
    $secureToken = Read-Host "GitHub runner registration token" -AsSecureString
    $tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
    try {
        $RegistrationToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator so the GitHub runner can be installed as a service."
}
if (Test-Path -LiteralPath (Join-Path $RunnerRoot ".runner")) {
    throw "A GitHub Actions runner is already configured at $RunnerRoot."
}

New-Item -ItemType Directory -Force $RunnerRoot | Out-Null
$release = Invoke-RestMethod `
    -Headers @{ "User-Agent" = "AutomaticPrint-Windows-Runner-Setup" } `
    -Uri "https://api.github.com/repos/actions/runner/releases/latest"
$asset = $release.assets |
    Where-Object { $_.name -match '^actions-runner-win-x64-.*\.zip$' } |
    Select-Object -First 1
if (-not $asset) {
    throw "The latest GitHub Actions runner release has no Windows x64 archive."
}

$archive = Join-Path $env:TEMP $asset.name
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archive
Expand-Archive -LiteralPath $archive -DestinationPath $RunnerRoot -Force
Remove-Item -LiteralPath $archive -Force

Push-Location $RunnerRoot
try {
    & .\config.cmd --unattended --replace `
        --url $RepositoryUrl `
        --token $RegistrationToken `
        --name $RunnerName `
        --labels "automatic-print,windows-test" `
        --work "_work" `
        --runasservice
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub Actions runner registration failed."
    }
}
finally {
    Pop-Location
}

$serviceName = Get-Content -LiteralPath (Join-Path $RunnerRoot ".service")
$service = Get-Service -Name $serviceName
if ($service.Status -ne "Running") {
    Start-Service -Name $serviceName
}
Write-Host "Runner installed: $RunnerName ($serviceName)"
