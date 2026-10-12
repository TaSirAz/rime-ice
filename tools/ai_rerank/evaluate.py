"""Report real-model accuracy on fixed examples; never reads user input files."""
import argparse
import time
from worker import TransformerScorer
from ranking import conservative_order

# These examples are diagnostics, not a representative accuracy benchmark.
CASES = (
    ("", ("我們達成公事", "我們達成共識"), 1),
    ("", ("我們達成共識", "我們達成公事"), 0),
    ("我們達成", ("公事", "共識"), 1),
    ("我們達成", ("共識", "公事"), 0),
    ("代入這個", ("公司", "公式"), 1),
    ("代入這個", ("公式", "公司"), 0),
    ("明天去", ("公式", "公司"), 1),
    ("明天去", ("公司", "公式"), 0),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B")
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()
    scorer = TransformerScorer(args.model, args.local_only)
    baseline = corrected = 0
    for context, words, expected in CASES:
        began = time.monotonic()
        scores = scorer.score(context, words)
        order = conservative_order(scores, words)
        baseline += expected == 0
        corrected += order[0] == expected
        print(("PASS" if order[0] == expected else "MISS"),
              repr(context), list(words), "selected=", words[order[0]],
              "scores=", [round(s, 3) for s in scores],
              "seconds=", round(time.monotonic() - began, 2), flush=True)
    print(f"Fixed examples only: Rime input order {baseline}/{len(CASES)}, "
          f"conservative model order {corrected}/{len(CASES)}.")
    print("Passing these examples does not establish general accuracy.")


if __name__ == "__main__":
    main()
