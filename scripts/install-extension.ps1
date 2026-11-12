param([string]$DestinationDirectory = (Join-Path $env:APPDATA 'pyRevit/Extensions'))
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $root 'RevitAuto.extension'
$target = [IO.Path]::GetFullPath((Join-Path $DestinationDirectory 'RevitAuto.extension'))
if ($target.StartsWith($source + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or $target -eq $source) {
    throw 'Choose a destination outside the source extension.'
}
$null = New-Item -ItemType Directory -Path $target -Force
Get-ChildItem -LiteralPath $source -Recurse -File | Where-Object { $_.Extension -in @('.py', '.yaml', '.json', '.png') } | ForEach-Object {
    $relative = $_.FullName.Substring($source.Length).TrimStart([char[]]@('\', '/'))
    $destination = Join-Path $target $relative
    $null = New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($destination)) -Force
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
}
Write-Host "Installed: $target"
Write-Host 'Reload pyRevit or restart Revit. If using a custom destination, register its parent in pyRevit Settings.'
