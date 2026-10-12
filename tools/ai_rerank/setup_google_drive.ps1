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
$pythonArgs = @()
if (Get-Command python -CommandType Application -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command python -CommandType Application).Source
} elseif (Get-Command py -CommandType Application -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command py -CommandType Application).Source
    $pythonArgs = @('-3')
} else {
    throw 'Python was not found. Activate your Conda environment or install Python 3.'
}
& $pythonCommand @pythonArgs -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.10 or newer is required. Activate a suitable Conda environment and retry.'
}
& $pythonCommand @pythonArgs -c 'import yaml'
if ($LASTEXITCODE -ne 0) {
    if ($pythonArgs.Count -eq 0) {
        throw 'Install the sync dependency first: python -m pip install PyYAML'
    }
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
& $pythonCommand @pythonArgs $setupPath --user-dir $RimeUserDir --sync-dir $SyncDir
if ($LASTEXITCODE -ne 0) {
    throw 'Sync setup failed. Review the Python error above.'
}
Write-Host 'Saved. Existing settings were backed up; the device installation_id was preserved.'
Write-Host 'Mark RimeSync Available offline in Google Drive, then run Rime User data sync.'
Write-Host 'On the second computer, wait for Drive to finish downloading, then run Rime User data sync.'
