# Start or restart only this user's Rime model worker in the background.
[CmdletBinding()]
param(
    [string]$RimeUserDir = (Join-Path $env:APPDATA 'Rime'),
    [string]$PythonExe
)
$ErrorActionPreference = 'Stop'
$workerPath = Join-Path $PSScriptRoot 'worker.py'
$setupPath = Join-Path $PSScriptRoot 'setup.py'
$notifyPath = Join-Path $PSScriptRoot 'windows_notify.py'
$rankingPath = Join-Path $PSScriptRoot 'ranking.py'
$tuningPath = Join-Path $PSScriptRoot 'cpu_tuning.py'
foreach ($path in @($workerPath, $setupPath, $notifyPath, $rankingPath, $tuningPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw 'Update all files from the ai-rerank-sync-prototype branch first.'
    }
}
$pythonArgs = @()
if (-not [string]::IsNullOrWhiteSpace($PythonExe)) {
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
        throw 'The specified Python executable does not exist.'
    }
    $pythonCommand = (Get-Item -LiteralPath $PythonExe).FullName
} elseif (Get-Command python -CommandType Application -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command python -CommandType Application | Select-Object -First 1).Source
} elseif (Get-Command py -CommandType Application -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command py -CommandType Application | Select-Object -First 1).Source
    $pythonArgs = @('-3')
} else {
    throw 'Python was not found. Pass -PythonExe or activate Conda.'
}
& $pythonCommand @pythonArgs -m unittest discover -s $PSScriptRoot -p 'test_*.py'
if ($LASTEXITCODE -ne 0) {
    throw 'AI worker compatibility checks failed. The existing worker was not stopped.'
}
& $pythonCommand @pythonArgs -c 'import torch, transformers, yaml'
if ($LASTEXITCODE -ne 0) {
    throw 'Install requirements.txt using the selected Python environment first.'
}
& $pythonCommand @pythonArgs $setupPath --user-dir $RimeUserDir --enable-ai
if ($LASTEXITCODE -ne 0) {
    throw 'AI configuration failed. Review the error above.'
}
# Do not stop other Python jobs, notebooks, or training processes.
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
    Where-Object {
        $_.CommandLine -and $_.ExecutablePath -and
        $_.ExecutablePath.Equals($pythonCommand, [System.StringComparison]::OrdinalIgnoreCase) -and
        $_.CommandLine.IndexOf($workerPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction Stop }
$bridgeDir = Join-Path $RimeUserDir 'ai_bridge'
$prefix = ($pythonArgs -join ' ')
$workerArgs = '{0} -u "{1}" --bridge-dir "{2}"' -f $prefix, $workerPath, $bridgeDir
$process = Start-Process -FilePath $pythonCommand -ArgumentList $workerArgs -WindowStyle Hidden -RedirectStandardOutput (Join-Path $bridgeDir 'worker.log') -RedirectStandardError (Join-Path $bridgeDir 'worker-error.log') -PassThru
Write-Host ('Worker started in background, PID ' + $process.Id)
Write-Host ('Check Ready: Get-Content "' + (Join-Path $bridgeDir 'worker.log') + '" -Tail 5')
Write-Host 'Redeploy Weasel. Candidate ordering will update automatically when the model finishes.'
