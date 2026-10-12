"""Local, asynchronous candidate scoring prototype. No network during scoring."""
import argparse
import json
import math
import os
import time
from functools import lru_cache
from pathlib import Path


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
        # Condition each candidate on exactly the same committed-text prefix.
        prefix = tokenizer.encode(context[-128:], add_special_tokens=False)
        if not prefix:
            return tuple(0.0 for _ in words)
        prefix = prefix[-192:]
        spans = [tokenizer.encode(w, add_special_tokens=False) for w in words]
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
        return tuple(float(values[i, len(prefix)-1:len(prefix)+len(span)-1].mean().cpu())
                     for i, span in enumerate(spans))


def serve(directory, scorer):
    directory.mkdir(parents=True, exist_ok=True)
    source, target = directory / "request.json", directory / "response.txt"
    last_id = None
    print("Ready. Keep this window open; stop with Ctrl+C. Input text is not logged.", flush=True)
    while True:
        try:
            request = json.loads(source.read_text(encoding="utf-8"))
            request_id, context, words = validate_request(request)
            if request_id != last_id:
                last_id = request_id
                order = stable_order(scorer.score(context, words))
                # Discard obsolete inference results if another keystroke arrived.
                newest = json.loads(source.read_text(encoding="utf-8"))
                if newest.get("id") == request_id:
                    temp = directory / "response.tmp"
                    temp.write_text(request_id + "\n" + ",".join(str(i+1) for i in order) + "\n", encoding="utf-8")
                    os.replace(temp, target)
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
