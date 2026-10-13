import unittest
from functools import lru_cache
from types import SimpleNamespace
from unittest.mock import patch
from cpu_tuning import thread_candidates, tune_cpu_threads


class FakeTorch:
    def __init__(self):
        self.threads = 6

    def get_num_threads(self):
        return self.threads

    def set_num_threads(self, threads):
        self.threads = threads


class Scorer:
    def __init__(self, device="cpu"):
        self.torch = FakeTorch()
        self.model = SimpleNamespace(device=SimpleNamespace(type=device))
        self.now, self.calls = 0.0, 0
        self.speeds = {1: .04, 2: .015, 4: .025, 6: .1, 8: .03}

    @lru_cache(maxsize=128)
    def score(self, context, words):
        self.calls += 1
        self.now += self.speeds[self.torch.threads]
        return (-1, -2, -3, -4)


class CPUTuningTests(unittest.TestCase):
    def test_measured_fastest_threads_selected_and_cache_bypassed(self):
        scorer = Scorer()
        with patch("cpu_tuning.os.cpu_count", return_value=8):
            with patch("cpu_tuning.os.process_cpu_count", return_value=8, create=True):
                result = tune_cpu_threads(scorer, clock=lambda: scorer.now)
        self.assertEqual(result["threads"], 2)
        self.assertEqual(scorer.torch.threads, 2)
        self.assertEqual(len(result["measurements"]), 5)
        self.assertEqual(scorer.calls, 40)
        self.assertEqual(scorer.score.cache_info().currsize, 0)

    def test_gpu_does_not_run_cpu_benchmark(self):
        scorer = Scorer("cuda")
        result = tune_cpu_threads(scorer)
        self.assertEqual(result["status"], "skipped_non_cpu")
        self.assertEqual(scorer.calls, 0)
        self.assertEqual(scorer.torch.threads, 6)

    def test_benchmark_failure_restores_original_threads(self):
        scorer = Scorer()
        scorer.speeds = {}
        with self.assertRaises(KeyError):
            tune_cpu_threads(scorer)
        self.assertEqual(scorer.torch.threads, 6)

    def test_thread_grid_respects_available_cores_and_keeps_original(self):
        self.assertEqual(thread_candidates(12, 2), [12, 1, 2])
        self.assertEqual(thread_candidates(1, 1), [1])

    def test_budget_keeps_at_least_baseline_and_one_alternative(self):
        scorer = Scorer()
        with patch("cpu_tuning.os.process_cpu_count", return_value=8, create=True):
            result = tune_cpu_threads(scorer, clock=lambda: scorer.now, budget_seconds=0)
        self.assertEqual(len(result["measurements"]), 2)
        self.assertEqual(scorer.torch.threads, 1)


if __name__ == "__main__":
    unittest.main()
