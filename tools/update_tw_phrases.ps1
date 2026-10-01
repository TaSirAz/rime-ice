param(
    [string]$Source = "https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/TWPhrases.txt",
    [string]$Output = (Join-Path $PSScriptRoot "..\cn_dicts\tw_phrases.dict.yaml")
)

$ErrorActionPreference = "Stop"

Write-Host "Downloading OpenCC TWPhrases..."
$text = (Invoke-WebRequest -UseBasicParsing -Uri $Source).Content

$seen = [System.Collections.Generic.HashSet[string]]::new()
$phrases = [System.Collections.Generic.List[string]]::new()

foreach ($line in ($text -split "\r?\n")) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
        continue
    }

    $parts = $line -split "`t", 2
    if ($parts.Count -lt 2) {
        continue
    }

    foreach ($phrase in ($parts[1].Trim() -split "\s+")) {
        if ($phrase -and $seen.Add($phrase)) {
            [void]$phrases.Add($phrase)
        }
    }
}

$version = Get-Date -Format "yyyy-MM-dd"

$header = @(
    "# Rime dictionary",
    "# encoding: utf-8",
    "#",
    "# Generated from OpenCC data/dictionary/TWPhrases.txt.",
    "# Source: https://github.com/BYVoid/OpenCC",
    "# Source license: Apache-2.0",
    "#",
    "# These are Taiwan-preferred terms as independent Rime entries.",
    "# The source terms are intentionally NOT removed or rewritten.",
    "",
    "---",
    "name: tw_phrases",
    "version: `"$version`"",
    "sort: by_weight",
    "use_preset_vocabulary: false",
    "...",
    ""
)

$content = ($header + $phrases) -join "`n"
$fullPath = [System.IO.Path]::GetFullPath($Output)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($fullPath, $content + "`n", $utf8NoBom)

Write-Host "Wrote $($phrases.Count) unique Taiwan terms to $fullPath"
