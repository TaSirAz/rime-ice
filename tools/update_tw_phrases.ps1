param(
    [string]$Source = "https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/TWPhrases.txt",
    [string]$Output = (Join-Path $PSScriptRoot "..\cn_dicts\tw_phrases.dict.yaml")
)

$ErrorActionPreference = "Stop"
# Install the generator dependency once: py -m pip install pypinyin==0.55.0
& py (Join-Path $PSScriptRoot "update_tw_phrases.py") --source $Source --output $Output
if ($LASTEXITCODE -ne 0) {
    throw "Taiwan dictionary generation failed. Install Python and run: py -m pip install pypinyin==0.55.0"
}
