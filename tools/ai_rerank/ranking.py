"""Conservative candidate promotion; thresholds are heuristics, not calibrated confidence."""
import math
import os


def comparable_indices(words, spans=None):
    """Only compare equal-length text covering the same input as the first candidate."""
    if not words:
        return []
    if spans is not None and (len(spans) != len(words) or
                              any(not isinstance(s, str) or len(s) > 80 for s in spans)):
        raise ValueError("invalid candidate spans")
    return [i for i, word in enumerate(words)
            if len(word) == len(words[0]) and
            (spans is None or spans[i] == spans[0])]


def split_shared_prefix(context, words):
    """Score differing suffixes with the shared, uncommitted sentence prefix as context."""
    common = os.path.commonprefix(words)
    # Identical candidates cannot be meaningfully reranked.
    if any(word == common for word in words):
        common = ""
    return (context + common)[-128:], tuple(word[len(common):] for word in words)


def conservative_order(scores, words, spans=None, margin=0.6, rank_bias=0.25):
    """Promote at most one of the first four entries; preserve every other entry's order."""
    if len(scores) != len(words) or any(not math.isfinite(x) for x in scores):
        raise ValueError("invalid model scores")
    original = list(range(len(words)))
    eligible = [i for i in comparable_indices(words, spans) if i < 4]
    if len(eligible) < 2:
        return original
    adjusted = {i: scores[i] - rank_bias * math.log1p(i) for i in eligible}
    best = max(eligible, key=lambda i: (adjusted[i], -i))
    runner_up = max(adjusted[i] for i in eligible if i != best)
    if best == 0 or adjusted[best] - runner_up < margin:
        return original
    return [best] + [i for i in original if i != best]
