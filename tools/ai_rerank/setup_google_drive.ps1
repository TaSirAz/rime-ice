# Select an existing Google Drive RimeSync folder; configure Rime snapshot sync.
# Run in Windows PowerShell. Python 3 and PyYAML are required.
[CmdletBinding()]
param(
    [string]$RimeUserDir = (Join-Path $env:APPDATA 'Rime'),
    [string]$SyncDir
)
$ErrorActionPreference = 'Stop'
$setupPath = Join-Path $PSScriptRoot 'setup.py'
if (-not (Test-Path -LiteralPath $setupPath -PathType Leaf)) {
    throw 'setup.py is missing. Update the ai-rerank-sync-prototype branch first.'
}
if (-not (Test-Path -LiteralPath (Join-Path $RimeUserDir 'installation.yaml') -PathType Leaf)) {
    throw 'Rime installation.yaml was not found. Pass -RimeUserDir with the actual user folder.'
}
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Install Python 3 with the Python launcher (py), then rerun this script.'
}
& py -3 -c 'import yaml'
if ($LASTEXITCODE -ne 0) {
    throw 'Install the sync dependency first: py -3 -m pip install PyYAML'
}
if ([string]::IsNullOrWhiteSpace($SyncDir)) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Choose the existing RimeSync folder inside Google Drive My Drive.'
    $dialog.ShowNewFolderButton = $false
    try {
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
            Write-Host 'Cancelled. Rime settings were not changed.'
            return
        }
        $SyncDir = $dialog.SelectedPath
    } finally {
        $dialog.Dispose()
    }
}
if (-not (Test-Path -LiteralPath $SyncDir -PathType Container)) {
    throw 'Choose an existing folder in Google Drive for desktop.'
}
& py -3 $setupPath --user-dir $RimeUserDir --sync-dir $SyncDir
if ($LASTEXITCODE -ne 0) {
    throw 'Sync setup failed. Review the Python error above.'
}
Write-Host 'Saved. Existing settings were backed up; the device installation_id was preserved.'
Write-Host 'Mark RimeSync Available offline in Google Drive, then run Rime User data sync.'
Write-Host 'On the second computer, wait for Drive to finish downloading, then run Rime User data sync.'
