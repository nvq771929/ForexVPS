$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$picker = New-Object System.Windows.Forms.FolderBrowserDialog
$picker.Description = 'Select the capture session folder containing metadata.csv'
if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }
$capturePath = $picker.SelectedPath
if (-not (Test-Path -LiteralPath (Join-Path $capturePath 'metadata.csv'))) {
    throw 'Choose a session folder containing metadata.csv, ticks.csv and session.csv.'
}
$sessionRows = Import-Csv -LiteralPath (Join-Path $capturePath 'session.csv')
if (-not ($sessionRows | Where-Object { $_.event -eq 'END' })) {
    throw 'Capture is still open or incomplete. Remove only the recorder from its third chart, then package again.'
}
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$staging = Join-Path $env:TEMP ('EA_Research_' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $staging
try {
    Get-ChildItem -LiteralPath $capturePath -Filter '*.csv' -File | Copy-Item -Destination $staging
    $destination = Join-Path (Split-Path -Parent $capturePath) ('Research_Capture_' + $stamp + '.zip')
    $csvPaths = @(Get-ChildItem -LiteralPath $staging -Filter '*.csv' -File | Select-Object -ExpandProperty FullName)
    Compress-Archive -LiteralPath $csvPaths -DestinationPath $destination
    Write-Host ('Created: ' + $destination)
    Start-Process explorer.exe -ArgumentList ('/select,"' + $destination + '"')
} finally { Remove-Item -LiteralPath $staging -Recurse -Force }
