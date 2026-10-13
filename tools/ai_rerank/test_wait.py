import unittest
from windows_notify import WaitDeadline


class WaitDeadlineTests(unittest.TestCase):
    def request(self, request_id="a", **changes):
        data = {"id": request_id, "wait_for_ai": True, "auto_refresh": True, "focus": "control"}
        data.update(changes)
        return data

    def test_timeout_without_any_response(self):
        timer = WaitDeadline()
        self.assertIsNone(timer.expired_id(self.request(), None, 10))
        self.assertIsNone(timer.expired_id(self.request(), None, 11.99))
        self.assertEqual(timer.expired_id(self.request(), None, 12), "a")
        self.assertIsNone(timer.expired_id(self.request(), None, 13))

    def test_result_ready_cancels_timeout(self):
        timer = WaitDeadline()
        timer.expired_id(self.request(), None, 10)
        self.assertIsNone(timer.expired_id(self.request(), "a", 11))
        self.assertIsNone(timer.expired_id(self.request(), None, 15))

    def test_typing_restarts_wait_and_old_result_is_ignored(self):
        timer = WaitDeadline()
        timer.expired_id(self.request(), None, 10)
        self.assertIsNone(timer.expired_id(self.request("b"), "a", 11.8))
        self.assertIsNone(timer.expired_id(self.request("b"), "a", 12))
        self.assertEqual(timer.expired_id(self.request("b"), "a", 14), "b")

    def test_manual_mode_missing_focus_or_wait_disabled_never_hide(self):
        for changes in ({"auto_refresh": False}, {"focus": ""}, {"wait_for_ai": False}):
            timer = WaitDeadline()
            timer.expired_id(self.request(**changes), None, 10)
            self.assertIsNone(timer.expired_id(self.request(**changes), None, 20))


if __name__ == "__main__":
    unittest.main()
