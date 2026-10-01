# Taiwan customization

This branch adds Taiwan-preferred vocabulary to Rime Ice without replacing the
original terms.

Examples:

- `shubiao` can still produce **鼠標**
- `huashu` can produce **滑鼠**
- `neicun` can still produce **內存**
- `jiyiti` can produce **記憶體**

The OpenCC filter uses `s2tw.json`, so it only handles Taiwan Traditional
character forms. Taiwan regional vocabulary is provided by
`cn_dicts/tw_phrases.dict.yaml` as real Rime dictionary entries.

## New Windows PC

1. Install Weasel.
2. Install Git for Windows.
3. Install Plum:

   ```bash
   cd ~
   git clone https://github.com/rime/plum.git plum
   cd plum
   ```

4. Install this fork:

   ```bash
   bash rime-install TaSirAz/rime-ice
   ```

5. Run Weasel **重新部署**.

The installed defaults use 9 candidates per page and start in Traditional
Chinese mode.

## Update Taiwan vocabulary

Run from the repository root in PowerShell:

```powershell
.\tools\update_tw_phrases.ps1
```

The script downloads OpenCC's `TWPhrases.txt`, keeps every unique target-side
Taiwan term, and regenerates `cn_dicts/tw_phrases.dict.yaml`.

Source: OpenCC `TWPhrases.txt` (Apache-2.0).
