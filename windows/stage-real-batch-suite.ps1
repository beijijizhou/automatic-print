param(
    [string]$NasRoot = "Z:\",
    [string]$DestinationRoot = "C:\actions-runner\real-batches\acceptance"
)

$ErrorActionPreference = "Stop"
$entries = @(
    @{ Id="haloo-random-black-2x-609171329038"; Source="0917\HL\单面黑2x-5x\609171329038"; Count=296 },
    @{ Id="haloo-random-multi-609171314019"; Source="0917\HL\多项多件\609171314019"; Count=231 },
    @{ Id="haloo-random-white-2x-609171338053"; Source="0917\HL\单面白2x-5x\609171338053"; Count=36 },
    @{ Id="longfeng-complete-609172109019"; Source="0917\LF\609172109019"; Count=4 },
    @{ Id="putian-complete-609172046008"; Source="0917\PT\609172046008"; Count=4 },
    @{ Id="longfeng-complete-609172110023"; Source="0917\LF\609172110023"; Count=10 },
    @{ Id="putian-complete-609172046009"; Source="0917\PT\609172046009"; Count=4 },
    @{ Id="s2b-complete-CYS2B002"; Destination="s2b\CYS2B002Mr______34_L9IGO772NMBP_20260917_185422_7te7qo5c"; Source="S2B\0917\CYS2B002Mr______34_L9IGO772NMBP_20260917_185422_7te7qo5c"; Count=34 },
    @{ Id="s2b-complete-HS2B011"; Destination="s2b\HS2B011Sg______14_CZ8ZTGIUO6XS_20260917_004608_jfttdkea"; Source="S2B\0916\HS2B011Sg______14_CZ8ZTGIUO6XS_20260917_004608_jfttdkea"; Count=14 },
    @{ Id="longfeng-performance-609172109020"; Source="0917\LF\609172109020"; Count=200 }
)

New-Item -ItemType Directory -Force $DestinationRoot | Out-Null
$records = @()
foreach ($entry in $entries) {
    $source = Join-Path $NasRoot $entry.Source
    $destinationName = if ($entry.Destination) { $entry.Destination } else { $entry.Id }
    $destination = Join-Path $DestinationRoot $destinationName
    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        throw "NAS batch does not exist: $source"
    }
    New-Item -ItemType Directory -Force $destination | Out-Null
    & robocopy $source $destination *.png /S /COPY:DAT /DCOPY:DAT /R:2 /W:2 /NFL /NDL /NP
    if ($LASTEXITCODE -gt 7) {
        throw "Failed to stage $source (robocopy exit $LASTEXITCODE)"
    }
    $files = @(Get-ChildItem $destination -File -Recurse -Filter *.png)
    if ($files.Count -ne $entry.Count) {
        throw "$($entry.Id): expected $($entry.Count) PNG files, staged $($files.Count)"
    }
    $records += [pscustomobject][ordered]@{
        id = $entry.Id
        source = (Resolve-Path -LiteralPath $source).Path
        destination = (Resolve-Path -LiteralPath $destination).Path
        png_files = $files.Count
        bytes = ($files | Measure-Object Length -Sum).Sum
    }
}
$records | ConvertTo-Json -Depth 4 |
    Set-Content -Encoding UTF8 (Join-Path $DestinationRoot "staging-manifest.json")
$records | Format-Table id, png_files, bytes -AutoSize
