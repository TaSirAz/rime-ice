"""Windows foreground-checked automatic refresh notification for the Rime prototype."""
import ctypes
import json
import os
import threading
import time
from pathlib import Path

WORD, DWORD, LONG = ctypes.c_uint16, ctypes.c_uint32, ctypes.c_int32
ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", WORD), ("wScan", WORD), ("dwFlags", DWORD),
                ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", LONG), ("dy", LONG), ("mouseData", DWORD),
                ("dwFlags", DWORD), ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", DWORD), ("wParamL", WORD), ("wParamH", WORD)]

class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", DWORD), ("data", INPUTUNION)]

class RECT(ctypes.Structure):
    _fields_ = [("left", LONG), ("top", LONG), ("right", LONG), ("bottom", LONG)]

class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", DWORD), ("flags", DWORD),
                ("hwndActive", ctypes.c_void_p), ("hwndFocus", ctypes.c_void_p),
                ("hwndCapture", ctypes.c_void_p), ("hwndMenuOwner", ctypes.c_void_p),
                ("hwndMoveSize", ctypes.c_void_p), ("hwndCaret", ctypes.c_void_p),
                ("rcCaret", RECT)]

def may_notify(request_id, expected_focus, actual_focus, latest_id, response_id,
               modifiers_down=False, expired=False):
    return bool(request_id and expected_focus and expected_focus == actual_focus
                and request_id == latest_id == response_id
                and not modifiers_down and not expired)

class WaitDeadline:
    """Independent watchdog: inference may be busy while this thread reveals fallback."""
    def __init__(self):
        self.request_id = None
        self.started = 0.0
        self.finished = False

    def expired_id(self, request, response_id, now):
        request_id = request.get("id")
        if not isinstance(request_id, str) or not request_id:
            return None
        if request_id != self.request_id:
            self.request_id, self.started, self.finished = request_id, now, False
        if response_id == request_id:
            self.finished = True
        if (self.finished or request.get("wait_for_ai") is not True
                or request.get("auto_refresh") is not True or not request.get("focus")):
            return None
        if now - self.started < 2.0:
            return None
        self.finished = True
        return request_id

class PipelineTiming:
    """Observe bridge stages, not UI paint; stores only IDs and elapsed times."""
    def __init__(self):
        self.request_id = None
        self.started = 0.0
        self.ready = self.sent = self.applied = None
        self.mode = None

    def observe(self, request_id, response_id, applied_id, mode, now):
        if not isinstance(request_id, str) or not request_id:
            return False
        changed = False
        if request_id != self.request_id:
            self.request_id, self.started = request_id, now
            self.ready = self.sent = self.applied = None
            self.mode = None
            changed = True
        if response_id == request_id and self.ready is None:
            self.ready = now
            changed = True
        if applied_id == request_id and self.applied is None:
            self.applied, self.mode = now, mode
            changed = True
        return changed

    def notified(self, request_id, now):
        if request_id == self.request_id:
            self.sent = now

    def snapshot(self):
        def elapsed(value):
            return round((value - self.started) * 1000, 1) if value is not None else None
        return {
            "version": "pipeline-v9", "request_id": self.request_id,
            "response_ms": elapsed(self.ready), "notification_ms": elapsed(self.sent),
            "applied_ms": elapsed(self.applied), "mode": self.mode,
            "notification_to_applied_ms": round((self.applied - self.sent) * 1000, 1)
                if self.applied is not None and self.sent is not None and self.applied >= self.sent else None,
        }

class WindowsNotifier:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.enabled = os.name == "nt"
        self.pending = None
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.thread = None
        if not self.enabled:
            return
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        self.api.GetForegroundWindow.restype = ctypes.c_void_p
        self.api.GetForegroundWindow.argtypes = []
        self.api.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(DWORD)]
        self.api.GetWindowThreadProcessId.restype = DWORD
        self.api.GetGUIThreadInfo.argtypes = [DWORD, ctypes.POINTER(GUITHREADINFO)]
        self.api.GetGUIThreadInfo.restype = ctypes.c_int
        self.api.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.api.GetAsyncKeyState.restype = ctypes.c_int16
        self.api.SendInput.argtypes = [DWORD, ctypes.POINTER(INPUT), ctypes.c_int]
        self.api.SendInput.restype = DWORD

    def focus(self):
        hwnd = self.api.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = DWORD()
        thread_id = self.api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(info)
        if not self.api.GetGUIThreadInfo(thread_id, ctypes.byref(info)) or not info.hwndFocus:
            return ""
        return f"{int(hwnd)}:{pid.value}:{int(info.hwndFocus)}"

    def queue(self, request_id, focus):
        if self.enabled and isinstance(focus, str) and focus:
            with self.lock:
                self.pending = (request_id, focus, time.monotonic() + 1.0)
            self.wake.set()

    def log(self, event, request_id=""):
        try:
            with (self.directory / "notify_status.log").open("a", encoding="utf-8") as output:
                output.write(event + "\t" + request_id + "\n")
        except OSError:
            pass

    def start(self):
        if self.enabled:
            self.thread = threading.Thread(target=self.run, daemon=True, name="rime-auto-refresh")
            self.thread.start()

    def close(self):
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=1)

    def write_timing(self, tracker):
        try:
            temp = self.directory / "pipeline_timing.tmp"
            temp.write_text(json.dumps(tracker.snapshot()), encoding="utf-8")
            os.replace(temp, self.directory / "pipeline_timing.json")
        except OSError:
            pass

    def run(self):
        previous, last_publish = None, 0.0
        watchdog = WaitDeadline()
        tracker = PipelineTiming()
        while not self.stop.is_set():
            self.wake.wait(timeout=0.01)
            self.wake.clear()
            if self.stop.is_set():
                break
            try:
                focus = self.focus()
                now = time.monotonic()
                if focus != previous or now - last_publish >= 0.25:
                    temp = self.directory / "focus.tmp"
                    temp.write_text(focus + "\n" + str(time.time()) + "\n",
                                    encoding="utf-8", newline="\n")
                    os.replace(temp, self.directory / "focus.txt")
                    previous, last_publish = focus, now
                request = json.loads((self.directory / "request.json").read_text(encoding="utf-8"))
                try:
                    response = (self.directory / "response.txt").read_text(encoding="utf-8").splitlines()
                except FileNotFoundError:
                    response = []
                response_id = response[0] if response else None
                try:
                    ack = (self.directory / "applied.txt").read_text(encoding="utf-8").splitlines()
                except FileNotFoundError:
                    ack = []
                if tracker.observe(request.get("id"), response_id, ack[0] if ack else None,
                                   ack[1] if len(ack) > 1 else None, now):
                    self.write_timing(tracker)
                expired_id = watchdog.expired_id(request, response_id, now)
                if expired_id:
                    temp = self.directory / "timeout.tmp"
                    temp.write_text(expired_id + "\n", encoding="utf-8", newline="\n")
                    os.replace(temp, self.directory / "timeout.txt")
                    self.queue(expired_id, request.get("focus"))
                    self.log("wait_timeout", expired_id)
                with self.lock:
                    pending = self.pending
                if not pending:
                    continue
                request_id, expected_focus, deadline = pending
                try:
                    timeout_id = (self.directory / "timeout.txt").read_text(encoding="utf-8").strip()
                except FileNotFoundError:
                    timeout_id = None
                if timeout_id == request_id:
                    response_id = timeout_id
                expired = now > deadline
                if expired or focus != expected_focus or request.get("id") != request_id:
                    with self.lock:
                        if self.pending == pending:
                            self.pending = None
                    self.log("notification_discarded", request_id)
                    continue
                modifiers = any(self.api.GetAsyncKeyState(key) & 0x8000
                                for key in (0x10, 0x11, 0x12, 0x5B, 0x5C))
                if not may_notify(request_id, expected_focus, focus, request.get("id"),
                                  response_id, modifiers, expired):
                    continue
                # Consume exactly once and check focus again immediately before injection.
                with self.lock:
                    if self.pending != pending:
                        continue
                    self.pending = None
                if self.focus() != expected_focus:
                    self.log("focus_changed_before_notification", request_id)
                    continue
                events = (INPUT * 2)()
                events[0].type = events[1].type = 1
                events[0].data.ki = KEYBDINPUT(0x87, 0, 0, 0, 0x52494D45)
                events[1].data.ki = KEYBDINPUT(0x87, 0, 2, 0, 0x52494D45)
                sent = self.api.SendInput(2, events, ctypes.sizeof(INPUT))
                if sent == 2:
                    tracker.notified(request_id, time.monotonic())
                    self.write_timing(tracker)
                self.log("notification_sent" if sent == 2 else "notification_failed", request_id)
            except (OSError, ValueError, json.JSONDecodeError):
                # A disappearing window or an atomically replaced file is recoverable.
                continue
