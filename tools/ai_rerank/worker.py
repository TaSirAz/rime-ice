"""Local, asynchronous candidate scoring prototype. No network during scoring."""
import argparse
import json
import math
import os
import time
from functools import lru_cache
from pathlib import Path
from windows_notify import WindowsNotifier
from ranking import comparable_indices, conservative_order, split_shared_prefix


def validate_request(data):
    if not isinstance(data, dict):
        raise ValueError("request must be an object")
    if not isinstance(data.get("id"), str) or len(data["id"]) > 200:
        raise ValueError("invalid id")
    if not isinstance(data.get("context"), str) or len(data["context"]) > 256:
        raise ValueError("invalid context")
    words = data.get("candidates")
    if not isinstance(words, list) or not 2 <= len(words) <= 8:
        raise ValueError("expected 2..8 candidates")
    if any(not isinstance(w, str) or not w or len(w) > 64 for w in words):
        raise ValueError("invalid candidate")
    return data["id"], data["context"], tuple(words)


def stable_order(scores):
    if any(not math.isfinite(x) for x in scores):
        raise ValueError("nonfinite score")
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))


class TransformerScorer:
    def __init__(self, model_name, local_only=False):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=local_only)
        self.model = AutoModelForCausalLM.from_pretrained(model_name, local_files_only=local_only)
        self.model.eval()
        if torch.cuda.is_available():
            self.model.to("cuda")

    @lru_cache(maxsize=128)
    def score(self, context, words):
        torch, tokenizer = self.torch, self.tokenizer
        # A shared sentence prefix is context even before Enter.
        context, suffixes = split_shared_prefix(context, words)
        prefix = tokenizer.encode(context, add_special_tokens=False)[-192:]
        if not prefix:
            # Qwen has no BOS; its EOS token supplies the first-token prediction.
            boundary = tokenizer.bos_token_id
            if boundary is None:
                boundary = tokenizer.eos_token_id
            if boundary is None:
                raise ValueError("model has no beginning-of-text token")
            prefix = [boundary]
        spans = [tokenizer.encode(w, add_special_tokens=False) for w in suffixes]
        if any(not s for s in spans):
            raise ValueError("empty candidate tokens")
        sequences = [prefix + span for span in spans]
        width = max(map(len, sequences))
        pad = tokenizer.eos_token_id
        ids = torch.tensor([s + [pad] * (width - len(s)) for s in sequences], device=self.model.device)
        mask = torch.tensor([[1] * len(s) + [0] * (width - len(s)) for s in sequences], device=self.model.device)
        with torch.inference_mode():
            logits = self.model(input_ids=ids, attention_mask=mask).logits
            values = torch.log_softmax(logits[:, :-1, :], dim=-1).gather(2, ids[:, 1:, None]).squeeze(-1)
        # Normalize by characters, not tokenizer-dependent token counts.
        return tuple(float(values[i, len(prefix)-1:len(prefix)+len(span)-1].sum().cpu()) / len(suffixes[i])
                     for i, span in enumerate(spans))


def serve(directory, scorer):
    directory.mkdir(parents=True, exist_ok=True)
    source, target = directory / "request.json", directory / "response.txt"
    last_id = None
    pending_id, pending_since = None, 0.0
    notifier = WindowsNotifier(directory)
    notifier.start()
    print("Automatic refresh: " + ("enabled" if notifier.enabled else "unavailable on this platform"), flush=True)
    print("Ranking: sentence-v6, conservative promotion; no Enter required.", flush=True)
    print("Ready. Keep this window open; stop with Ctrl+C. Input text is not logged.", flush=True)
    while True:
        try:
            request = json.loads(source.read_text(encoding="utf-8"))
            request_id, context, words = validate_request(request)
            if request_id != last_id:
                if request_id != pending_id:
                    pending_id, pending_since = request_id, time.monotonic()
                # Coalesce rapid typing without blocking Rime or delaying notifications.
                if time.monotonic() - pending_since < 0.15:
                    time.sleep(0.025)
                    continue
                last_id = request_id
                spans = request.get("spans")
                eligible = [i for i in comparable_indices(words, spans) if i < 4]
                scores = [0.0] * len(words)
                if len(eligible) >= 2:
                    subset = tuple(words[i] for i in eligible)
                    for i, score in zip(eligible, scorer.score(context, subset)):
                        scores[i] = score
                order = conservative_order(scores, words, spans)
                # Discard obsolete inference results if another keystroke arrived.
                newest = json.loads(source.read_text(encoding="utf-8"))
                if newest.get("id") == request_id:
                    temp = directory / "response.tmp"
                    temp.write_text(request_id + "\n" + ",".join(str(i+1) for i in order) + "\n", encoding="utf-8", newline="\n")
                    os.replace(temp, target)
                    if request.get("auto_refresh") is True:
                        notifier.queue(request_id, request.get("focus"))
        except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
            pass
        time.sleep(0.025)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-dir", type=Path, required=True)
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B")
    parser.add_argument("--local-only", action="store_true", help="Require already downloaded model files")
    args = parser.parse_args()
    serve(args.bridge_dir, TransformerScorer(args.model, args.local_only))
