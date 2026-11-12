param(
    [string]$DestinationDirectory = (Join-Path $env:APPDATA 'Autodesk/Revit/Addins/2026')
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$build = Join-Path $root 'src/RevitAuto.Addin/bin/Release/net8.0-windows'
foreach ($name in @('RevitAuto.Addin.dll', 'RevitAuto.Core.dll')) {
    if (-not (Test-Path -LiteralPath (Join-Path $build $name))) { throw 'Run dotnet build RevitAuto.sln -c Release first.' }
}
$target = Join-Path ([IO.Path]::GetFullPath($DestinationDirectory)) 'Youns.RevitAuto'
$null = New-Item -ItemType Directory -Path $target -Force
foreach ($name in @('RevitAuto.Addin.dll', 'RevitAuto.Core.dll')) {
    Copy-Item -LiteralPath (Join-Path $build $name) -Destination (Join-Path $target $name) -Force
}
$settings = [Xml.XmlWriterSettings]::new()
$settings.Indent = $true
$settings.Encoding = [Text.UTF8Encoding]::new($false)
$manifest = Join-Path $DestinationDirectory 'Youns.RevitAuto.addin'
$writer = [Xml.XmlWriter]::Create($manifest, $settings)
try {
    $writer.WriteStartDocument()
    $writer.WriteStartElement('RevitAddIns')
    $writer.WriteStartElement('AddIn')
    $writer.WriteAttributeString('Type', 'Application')
    $writer.WriteElementString('Name', 'RevitAuto')
    $writer.WriteElementString('Assembly', (Join-Path $target 'RevitAuto.Addin.dll'))
    $writer.WriteElementString('AddInId', '0D65A92A-A9E0-49D8-9DE8-82E8AD5D6D61')
    $writer.WriteElementString('FullClassName', 'RevitAuto.Addin.App')
    $writer.WriteElementString('VendorId', 'YOUN')
    $writer.WriteElementString('VendorDescription', 'Youns Revit sheet automation')
    $writer.WriteEndElement()
    $writer.WriteEndElement()
    $writer.WriteEndDocument()
} finally { $writer.Dispose() }
Write-Host "Installed manifest: $manifest"
