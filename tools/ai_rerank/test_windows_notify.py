import ctypes
import os
import unittest
from windows_notify import INPUT, KEYBDINPUT, WindowsNotifier, may_notify

class NotificationTests(unittest.TestCase):
    def test_abi_input_layout(self):
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(INPUT), expected)
        events = (INPUT * 2)()
        events[0].type = events[1].type = 1
        events[0].data.ki = KEYBDINPUT(0x87, 0, 0, 0, 0x52494D45)
        events[1].data.ki = KEYBDINPUT(0x87, 0, 2, 0, 0x52494D45)
        self.assertEqual(events[0].data.ki.wVk, 0x87)
        self.assertEqual(events[1].data.ki.dwFlags, 2)

    def test_valid_matching_request(self):
        self.assertTrue(may_notify("one", "focus", "focus", "one", "one"))

    def test_other_window_or_control_is_rejected(self):
        self.assertFalse(may_notify("one", "focus-a", "focus-b", "one", "one"))

    def test_stale_request_or_response_is_rejected(self):
        self.assertFalse(may_notify("one", "focus", "focus", "two", "one"))
        self.assertFalse(may_notify("one", "focus", "focus", "one", "two"))

    def test_missing_focus_modifier_keys_and_expiry(self):
        self.assertFalse(may_notify("one", "", "", "one", "one"))
        self.assertFalse(may_notify("one", "focus", "focus", "one", "one", modifiers_down=True))
        self.assertFalse(may_notify("one", "focus", "focus", "one", "one", expired=True))

    @unittest.skipIf(os.name == "nt", "Windows native initialization is tested on the target PC")
    def test_non_windows_does_not_inject_input(self):
        notifier = WindowsNotifier(".")
        self.assertFalse(notifier.enabled)
        notifier.start()
        notifier.queue("one", "focus")
        self.assertIsNone(notifier.pending)
        notifier.close()

if __name__ == "__main__":
    unittest.main()
