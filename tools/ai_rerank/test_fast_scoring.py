"""Numerical parity against full-prefix scoring; no model download is needed."""
import unittest
from types import SimpleNamespace
from ranking import split_shared_prefix
from worker import TransformerScorer, logits_keep_parameter

try:
    import torch
except ImportError:
    torch = None


class Tokenizer:
    bos_token_id = None
    eos_token_id = 0

    def encode(self, text, add_special_tokens=False):
        return [ord(c) % 10 + 1 for c in text]


class LegacyModel:
    device = "cpu"

    def logits(self, ids):
        positions = torch.arange(ids.shape[1], dtype=torch.float32)[None, :, None]
        vocab = torch.arange(11, dtype=torch.float32)[None, None, :]
        # A causal toy decoder: each position depends on all earlier tokens, never future tokens.
        state = ids.cumsum(dim=1).float()[:, :, None]
        return (positions / 7 + state / 13) * vocab

    def forward(self, input_ids, attention_mask, use_cache=False):
        self.used_cache = use_cache
        self.input_batches = input_ids.shape[0]
        self.output_positions = input_ids.shape[1]
        return SimpleNamespace(logits=self.logits(input_ids))

    def __call__(self, **kwargs):
        return self.forward(**kwargs)


class ModernModel(LegacyModel):
    def forward(self, input_ids, attention_mask, use_cache=False, logits_to_keep=0):
        self.used_cache = use_cache
        self.input_batches = input_ids.shape[0]
        logits = self.logits(input_ids)
        if logits_to_keep:
            logits = logits[:, -logits_to_keep:, :]
        self.output_positions = logits.shape[1]
        return SimpleNamespace(logits=logits)


class TransitionalModel(LegacyModel):
    def forward(self, input_ids, attention_mask, use_cache=False, num_logits_to_keep=0):
        self.used_cache = use_cache
        self.input_batches = input_ids.shape[0]
        logits = self.logits(input_ids)
        if num_logits_to_keep:
            logits = logits[:, -num_logits_to_keep:, :]
        self.output_positions = logits.shape[1]
        return SimpleNamespace(logits=logits)


@unittest.skipIf(torch is None, "PyTorch is required for numerical parity tests")
class FastScoringTests(unittest.TestCase):
    def scorer(self, model):
        scorer = TransformerScorer.__new__(TransformerScorer)
        scorer.torch, scorer.tokenizer, scorer.model = torch, Tokenizer(), model
        scorer.keep_parameter = logits_keep_parameter(model)
        return scorer

    def reference(self, scorer, context, words):
        context, suffixes = split_shared_prefix(context, words)
        prefix = scorer.tokenizer.encode(context)[-192:] or [0]
        spans = [scorer.tokenizer.encode(w) for w in suffixes]
        sequences = [prefix + span for span in spans]
        width = max(map(len, sequences))
        ids = torch.tensor([s + [0] * (width - len(s)) for s in sequences])
        logits = scorer.model.logits(ids)
        values = torch.log_softmax(logits[:, :-1, :], dim=-1).gather(
            2, ids[:, 1:, None]).squeeze(-1)
        return tuple(float(values[i, len(prefix)-1:len(prefix)+len(span)-1].sum()) / len(suffixes[i])
                     for i, span in enumerate(spans))

    def test_suffix_scoring_matches_original_with_empty_long_shared_and_padded_prefixes(self):
        cases = [
            ("", ("共識", "公式")),
            ("", ("共", "公", "式", "司")),
            ("代入這個", ("公式", "公司")),
            ("今天我們準備把新的", ("共識", "公式")),
            ("", ("我們達成公事", "我們達成共識")),
            ("前文" * 80, ("較短", "較長的候選詞")),
        ]
        for model_type in (LegacyModel, ModernModel, TransitionalModel):
            for context, words in cases:
                with self.subTest(model=model_type.__name__, context_length=len(context), words=words):
                    scorer = self.scorer(model_type())
                    expected = self.reference(scorer, context, words)
                    actual = scorer.score(context, words)
                    for a, b in zip(actual, expected):
                        self.assertAlmostEqual(a, b, places=5)
                    self.assertFalse(scorer.model.used_cache)
                    if scorer.keep_parameter:
                        _, suffixes = split_shared_prefix(context, words)
                        expected_positions = 1 if all(len(s) == 1 for s in suffixes) else max(map(len, suffixes)) + 1
                        self.assertEqual(scorer.model.output_positions, expected_positions)
                    _, suffixes = split_shared_prefix(context, words)
                    if all(len(s) == 1 for s in suffixes):
                        self.assertEqual(scorer.model.input_batches, 1)

    def test_compatibility_parameter_detection(self):
        self.assertIsNone(logits_keep_parameter(LegacyModel()))
        self.assertEqual(logits_keep_parameter(ModernModel()), "logits_to_keep")
        self.assertEqual(logits_keep_parameter(TransitionalModel()), "num_logits_to_keep")


if __name__ == "__main__":
    unittest.main()
