"""Install a pinned compact Octagram model; keep AI, dictionaries and shortcuts intact."""
import argparse
import hashlib
import os
import time
import urllib.request
from pathlib import Path
from setup import update_yaml

MODEL = "zh-hans-t-essay-bgw-compact"
SIZE = 40925228
SHA256 = "d3cb2438c1fdcd6a855dd6ca8f5c1060a29273c6b64c2c2c69af67cd71b6aa7e"
URL = "https://github.com/lotem/rime-octagram-data/releases/download/20260712/" + MODEL + ".gram"


def verified(path):
    if not path.is_file() or path.stat().st_size != SIZE:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == SHA256


def install(user_dir):
    user_dir = Path(user_dir)
    if not user_dir.is_dir():
        raise ValueError("Select the actual Rime user directory")
    config_path = user_dir / "rime_ice.custom.yaml"
    import yaml
    existing = yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) if config_path.exists() else {}
    patch = (existing or {}).get("patch", {})
    grammar = patch.get("grammar", {})
    language = patch.get("grammar/language", grammar.get("language"))
    if language and language != MODEL:
        raise ValueError("An existing grammar model is configured; preserve it and review manually")
    target = user_dir / (MODEL + ".gram")
    if not verified(target):
        print("Downloading compact native language model (39 MiB)...", flush=True)
        temporary = user_dir / (MODEL + ".gram.part")
        total = 0
        with urllib.request.urlopen(URL, timeout=60) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > SIZE:
                    raise ValueError("Native model download exceeded the pinned size")
                output.write(chunk)
        if not verified(temporary):
            raise ValueError("Native model size/SHA256 check failed; configuration was not changed")
        if target.exists():
            target.rename(target.with_name(target.name + "." + str(time.time_ns()) + ".bak"))
        os.replace(temporary, target)

    def configure(data):
        patch = data.setdefault("patch", {})
        patch["grammar/language"] = MODEL
        # Official Octagram word-model settings; compact data uses the same model format.
        patch["translator/contextual_suggestions"] = True
        patch.setdefault("translator/max_homophones", 7)
        patch.setdefault("translator/max_homographs", 7)
        # librime >= 1.17 supports multiple full-sentence candidates.
        patch.setdefault("translator/max_sentences", 3)

    update_yaml(config_path, configure)
    print("Native grammar configured with backups. AI remains enabled. Redeploy Weasel.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-dir", required=True, type=Path)
    args = parser.parse_args()
    install(args.user_dir)
