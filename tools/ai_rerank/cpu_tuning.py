"""Select CPU thread count using uncached fixed-example inference on this machine."""
import os
import statistics
import time


SAMPLES = (
    ("我們達成", ("共識", "公事", "公式", "公司")),
    ("今天開會討論了新的工作內容最後我們達成", ("共識", "公事", "公式", "公司")),
)


def thread_candidates(original, cores):
    cores = max(1, cores or 1)
    return sorted(set([original] + [n for n in (1, 2, 4, 8) if n <= cores]),
                  key=lambda n: (n != original, n))


def tune_cpu_threads(scorer, clock=time.perf_counter, budget_seconds=8.0):
    torch = scorer.torch
    device = scorer.model.device
    device_type = getattr(device, "type", str(device).split(":")[0])
    original = torch.get_num_threads()
    if device_type != "cpu":
        return {"version": "cpu-tuning-v10", "status": "skipped_non_cpu",
                "threads": original, "measurements": []}
    process_count = getattr(os, "process_cpu_count", os.cpu_count)
    candidates = thread_candidates(original, process_count())
    measurements = []
    started = clock()
    # Bypass lru_cache: otherwise identical examples appear falsely instantaneous.
    uncached = scorer.score.__wrapped__
    try:
        for threads in candidates:
            if len(measurements) >= 2 and clock() - started >= budget_seconds:
                break
            torch.set_num_threads(threads)
            for context, words in SAMPLES:
                uncached(scorer, context, words)
            durations = []
            for _ in range(3):
                began = clock()
                for context, words in SAMPLES:
                    uncached(scorer, context, words)
                durations.append((clock() - began) * 1000 / len(SAMPLES))
            measurements.append({"threads": threads, "median_inference_ms": statistics.median(durations)})
        best = min(measurements, key=lambda row: (row["median_inference_ms"], row["threads"]))
        torch.set_num_threads(best["threads"])
    except Exception:
        torch.set_num_threads(original)
        raise
    return {
        "version": "cpu-tuning-v10", "status": "selected",
        "threads": best["threads"], "previous_threads": original,
        "measurements": [{"threads": row["threads"],
                          "median_inference_ms": round(row["median_inference_ms"], 2)}
                         for row in measurements],
        "duration_ms": round((clock() - started) * 1000, 1),
    }
