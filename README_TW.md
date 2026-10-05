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
   bash rime-install TaSirAz/rime-ice@taiwan-phrases
   ```

5. Run Weasel **重新部署**.

The installed defaults use 9 candidates per page and start in Traditional
Chinese mode.

## Update Taiwan vocabulary

Install Python, then run from the repository root in PowerShell:

```powershell
py -m pip install pypinyin==0.55.0
```

```powershell
.\tools\update_tw_phrases.ps1
```

The script downloads OpenCC's `TWPhrases.txt`, keeps every unique target-side
Taiwan term, assigns explicit pinyin (with Taiwan pronunciation overrides), and regenerates `cn_dicts/tw_phrases.dict.yaml`.

Source: OpenCC `TWPhrases.txt` (Apache-2.0).

## Repair an installation of the earlier branch

Run `bash rime-install TaSirAz/rime-ice@taiwan-phrases` from your Plum directory,
then run Weasel **重新部署**. The recipe reinstalls `rime_ice.custom.yaml`,
including `translator/dictionary: rime_ice_tw`; no manual patch is needed.
If a stale compiled table persists, exit Weasel, remove only
`build/rime_ice_tw.table.bin`, `build/rime_ice_tw.prism.bin`, and
`build/rime_ice_tw.reverse.bin` from the user folder, then redeploy.
Keep the user dictionaries intact.

The extended root imports each upstream table directly because Rime does not
recursively import the tables listed inside an imported dictionary. The
Taiwan entries carry explicit codes so Traditional characters and mixed
Latin/Chinese entries do not depend on Simplified single-character lookup.
When upstream changes its import list or inline entries, update
`rime_ice_tw.dict.yaml` to match, retaining the Taiwan table.

The static dictionary keeps all 810 original target terms. Pronunciations are
automatically generated except for explicit overrides in the Python script;
rare names and other polyphonic terms may need additional overrides.
