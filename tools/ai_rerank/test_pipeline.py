import tempfile
import contextlib
import io
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from worker import serve
import threading
import time
import unittest
from windows_notify import PipelineTiming, WindowsNotifier


class PipelineTimingTests(unittest.TestCase):
    def test_stages_are_relative_to_observed_request(self):
        timing = PipelineTiming()
        self.assertTrue(timing.observe("a", None, None, None, 10))
        self.assertTrue(timing.observe("a", "a", None, None, 10.05))
        timing.notified("a", 10.055)
        self.assertTrue(timing.observe("a", "a", "a", "ai", 10.08))
        data = timing.snapshot()
        self.assertEqual(data["response_ms"], 50)
        self.assertEqual(data["notification_ms"], 55)
        self.assertEqual(data["applied_ms"], 80)
        self.assertEqual(data["notification_to_applied_ms"], 25)
        self.assertEqual(data["mode"], "ai")

    def test_stale_response_ack_and_notification_do_not_count(self):
        timing = PipelineTiming()
        timing.observe("a", None, None, None, 10)
        timing.notified("old", 11)
        timing.observe("a", "old", "old", "ai", 12)
        self.assertIsNone(timing.snapshot()["applied_ms"])
        self.assertIsNone(timing.snapshot()["response_ms"])
        self.assertIsNone(timing.snapshot()["notification_ms"])
        timing.observe("b", "a", "a", "ai", 13)
        self.assertEqual(timing.snapshot()["request_id"], "b")
        self.assertIsNone(timing.snapshot()["applied_ms"])

    def test_original_order_ack_is_distinct_from_ai(self):
        timing = PipelineTiming()
        timing.observe("a", None, None, None, 10)
        timing.observe("a", None, "a", "original", 12)
        self.assertEqual(timing.snapshot()["mode"], "original")
        self.assertIsNone(timing.snapshot()["response_ms"])

    def test_invalid_id_and_duplicate_observations_are_ignored(self):
        timing = PipelineTiming()
        self.assertFalse(timing.observe(None, None, None, None, 1))
        timing.observe("a", "a", "a", "ai", 10)
        self.assertFalse(timing.observe("a", "a", "a", "ai", 12))
        self.assertEqual(timing.snapshot()["applied_ms"], 0)

    def test_queue_wakes_notifier_instead_of_waiting_for_next_poll(self):
        with tempfile.TemporaryDirectory() as directory:
            notifier = WindowsNotifier.__new__(WindowsNotifier)
            notifier.directory = directory
            notifier.enabled = True
            notifier.pending = None
            notifier.lock = threading.Lock()
            notifier.wake = threading.Event()
            notifier.queue("a", "control")
            self.assertTrue(notifier.wake.is_set())
            self.assertEqual(notifier.pending[:2], ("a", "control"))
            self.assertGreater(notifier.pending[2], time.monotonic())


class ImmediateWorkerTests(unittest.TestCase):
    def test_first_request_is_scored_without_advancing_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = {"id": "a", "context": "", "candidates": ["共識", "公事"],
                       "focus": "control", "auto_refresh": True}
            (root / "request.json").write_text(json.dumps(request), encoding="utf-8")
            scorer = MagicMock()
            scorer.score.return_value = (-1.0, -4.0)
            notifier = MagicMock()
            notifier.enabled = True
            with patch("worker.WindowsNotifier", return_value=notifier), \
                    patch("worker.time.monotonic", return_value=10.0), \
                    patch("worker.time.sleep", side_effect=StopIteration), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(StopIteration):
                    serve(root, scorer)
            scorer.score.assert_called_once_with("", ("共識", "公事"))
            self.assertEqual((root / "response.txt").read_text().splitlines(), ["a", "1,2"])
            notifier.queue.assert_called_once_with("a", "control")
            self.assertEqual(json.loads((root / "timing.json").read_text())["worker_ms"], 0)


if __name__ == "__main__":
    unittest.main()
