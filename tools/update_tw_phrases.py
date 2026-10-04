#!/usr/bin/env python3
"""Generate independently encoded Taiwan terms from OpenCC (Apache-2.0)."""
import argparse
import datetime
import re
import urllib.request
from pathlib import Path

from pypinyin import Style, lazy_pinyin

# Taiwan pronunciations and ambiguous technical terms.
OVERRIDES = {
    "滑鼠": "hua shu", "記憶體": "ji yi ti", "函式": "han shi",
    "程式": "cheng shi", "伺服器": "si fu qi", "執行緒": "zhi xing xu",
    "快取": "kuai qu", "硬碟": "ying die", "軟體": "ruan ti",
    "原始碼": "yuan shi ma", "資訊": "zi xun", "連線": "lian xian",
    "載入": "zai ru", "過載": "guo zai", "重灌": "chong guan",
    "重新整理": "chong xin zheng li", "重新命名": "chong xin ming ming",
    "行內函數": "hang nei han shu", "行程": "xing cheng",
    "處理程序": "chu li cheng xu", "調變": "tiao bian",
    "調色盤": "tiao se pan", "核取方塊": "he qu fang kuai",
    "核取按鈕": "he qu an niu", "貼上": "tie shang",
    "矽": "xi", "垃圾": "le se", "繫結": "xi jie",
}
DIGITS = dict(zip("0123456789", "ling yi er san si wu liu qi ba jiu".split()))


def pronunciation(term):
    if term in OVERRIDES:
        return OVERRIDES[term]
    # Punctuation separates name parts; uppercase letters retain Rime Ice codes.
    tokens = []
    for part in re.findall(r"[\u3400-\u9fff]+|[A-Za-z0-9]", term):
        if re.fullmatch(r"[A-Za-z0-9]", part):
            tokens.append(DIGITS.get(part, part))
        else:
            tokens.extend(lazy_pinyin(part, style=Style.NORMAL, strict=False))
    if not tokens or any(not re.fullmatch(r"[a-z]+|[A-Z]", x) for x in tokens):
        raise ValueError(f"Missing pronunciation: {term!r}: {tokens!r}")
    return " ".join(tokens)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/TWPhrases.txt")
    parser.add_argument("--input-dictionary", type=Path, help="Regenerate an existing target-only Rime dictionary offline")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "cn_dicts/tw_phrases.dict.yaml")
    args = parser.parse_args()
    if args.input_dictionary:
        body = args.input_dictionary.read_text(encoding="utf-8-sig").split("...", 1)[1]
        terms = [x.split("\t")[0].strip() for x in body.splitlines() if x.strip() and not x.startswith("#")]
    else:
        if args.source.startswith(("https://", "http://")):
            with urllib.request.urlopen(args.source, timeout=30) as response:
                source = response.read().decode("utf-8-sig")
        else:
            source = Path(args.source).read_text(encoding="utf-8-sig")
        terms = []
        for line in source.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            if "\t" not in line:
                raise ValueError(f"Invalid OpenCC mapping: {line!r}")
            terms.extend(line.split("\t", 1)[1].split())
    terms = list(dict.fromkeys(terms))
    if not terms:
        raise ValueError("The source contains no terms")
    entries = [f"{term}\t{pronunciation(term)}\t100" for term in terms]
    header = f'''# Rime dictionary
# encoding: utf-8
# Generated from OpenCC data/dictionary/TWPhrases.txt (Apache-2.0).
# Source: https://github.com/BYVoid/OpenCC
# Explicit pinyin generated with pypinyin; Taiwan overrides are in the script.
# Original terms are preserved in the upstream dictionaries.

---
name: tw_phrases
version: "{datetime.date.today().isoformat()}"
sort: by_weight
use_preset_vocabulary: false
columns: [text, code, weight]
...

'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(header + "\n".join(entries) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} unique terms with explicit pinyin to {args.output}")


if __name__ == "__main__":
    main()
