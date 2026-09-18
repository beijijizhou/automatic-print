$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repositoryUrl = "https://github.com/beijijizhou/automatic-print.git"
$installRoot = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "AutomaticPrint"

function Find-CommandPath {
    param(
        [string]$CommandName,
        [string[]]$Candidates
    )

    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    foreach ($candidate in $Candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

function Test-Python312 {
    param(
        [string]$Executable,
        [string[]]$PrefixArguments = @()
    )

    if (-not $Executable -or -not (Test-Path $Executable)) {
        return $false
    }
    try {
        $version = & $Executable @PrefixArguments -c `
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" `
            2>$null
        return $LASTEXITCODE -eq 0 -and "$version".Trim() -eq "3.12"
    }
    catch {
        return $false
    }
}

function Find-Python312 {
    $launcher = Find-CommandPath "py" @(
        "$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe",
        "$env:SystemRoot\py.exe"
    )
    if (Test-Python312 $launcher @("-3.12")) {
        return @{ Executable = $launcher; PrefixArguments = @("-3.12") }
    }

    $command = Get-Command python -ErrorAction SilentlyContinue
    $candidates = @(
        $(if ($command) { $command.Source }),
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "${env:ProgramFiles(x86)}\Python312\python.exe"
    ) | Where-Object { $_ } | Select-Object -Unique
    foreach ($candidate in $candidates) {
        if (Test-Python312 $candidate) {
            return @{ Executable = $candidate; PrefixArguments = @() }
        }
    }
    return $null
}

function Install-WithWinget {
    param(
        [string]$PackageId,
        [string]$DisplayName
    )

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Cannot install $DisplayName automatically because winget is unavailable."
    }
    Write-Host "Installing $DisplayName..."
    & $winget.Source install --id $PackageId --exact --silent `
        --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "$DisplayName installation failed."
    }
}

Write-Host ""
Write-Host "Automatic Print - test computer setup/update"
Write-Host "Install folder: $installRoot"
Write-Host ""

$git = Find-CommandPath "git" @(
    "$env:ProgramFiles\Git\cmd\git.exe",
    "${env:ProgramFiles(x86)}\Git\cmd\git.exe",
    "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
)
if (-not $git) {
    Install-WithWinget "Git.Git" "Git for Windows"
    $git = Find-CommandPath "git" @(
        "$env:ProgramFiles\Git\cmd\git.exe",
        "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
    )
}
if (-not $git) {
    throw "Git was installed but could not be located. Restart Windows and run this script again."
}

$python312 = Find-Python312
if (-not $python312) {
    Install-WithWinget "Python.Python.3.12" "Python 3.12"
    $python312 = Find-Python312
}
if (-not $python312) {
    throw "Python was installed but could not be located. Restart Windows and run this script again."
}
Write-Host "Using Python 3.12: $($python312.Executable)"

$chrome = Find-CommandPath "chrome" @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
if (-not $chrome) {
    Install-WithWinget "Google.Chrome" "Google Chrome"
}

$projectEnvironment = Join-Path $installRoot ".venv"
$runningProjectProcesses = Get-CimInstance Win32_Process |
    Where-Object {
        $_.ExecutablePath -and
        $_.ExecutablePath.StartsWith(
            $projectEnvironment,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    }
if ($runningProjectProcesses) {
    Write-Host "Closing the previous Automatic Print development process..."
    $runningProjectProcesses |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    Start-Sleep -Milliseconds 800
}

if (Test-Path (Join-Path $installRoot ".git")) {
    Push-Location $installRoot
    try {
        $changes = & $git status --porcelain --untracked-files=no
        if ($changes) {
            throw "Local code changes were found. Update stopped to avoid overwriting them."
        }
        Write-Host "Downloading the latest code..."
        & $git pull --ff-only origin main
        if ($LASTEXITCODE -ne 0) {
            throw "Git update failed."
        }
    }
    finally {
        Pop-Location
    }
}
elseif (Test-Path $installRoot) {
    throw "$installRoot already exists but is not a Git repository."
}
else {
    Write-Host "Downloading Automatic Print..."
    & $git clone $repositoryUrl $installRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Git clone failed."
    }
}

$venvPython = Join-Path $installRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating the project Python environment..."
    $pythonArguments = @($python312.PrefixArguments)
    & $python312.Executable @pythonArguments -m venv (Join-Path $installRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Python environment creation failed."
    }
}

Write-Host "Installing and updating project requirements..."
& $venvPython -m pip install --disable-pip-version-check -r `
    (Join-Path $installRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Dependency installation failed."
}

Write-Host ""
Write-Host "Creating the Haloo Automatic desktop shortcut..."
$runScript = Join-Path $installRoot "windows\run-dev.bat"
$iconPath = Join-Path $installRoot "assets\ha-icon.ico"
$desktop = [Environment]::GetFolderPath(
    [Environment+SpecialFolder]::Desktop
)
$shortcutPath = Join-Path $desktop "Haloo Automatic.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $runScript
$shortcut.WorkingDirectory = $installRoot
$shortcut.Description = "Haloo Automatic - POD production center"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Save()
Write-Host "Desktop entry: $shortcutPath"

Write-Host ""
Write-Host "Setup/update finished. Starting Haloo Automatic..."
Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" `
    -ArgumentList "/k", "`"$runScript`"" `
    -WorkingDirectory $installRoot
