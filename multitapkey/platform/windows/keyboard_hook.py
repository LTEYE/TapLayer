"""WH_KEYBOARD_LL backend for Windows."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import queue
import threading
import time

from multitapkey.platform.base import (
    CaptureResult,
    RawKeyEvent,
)

from .keymap import key_to_vk, vk_to_key
from .send_input import INJECTED_MARKER


log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

HC_ACTION = 0
LLKHF_INJECTED = 0x00000010

# 捕获模式最多持续这么久；超时自动取消，避免界面卡住时永久吞掉所有按键。
CAPTURE_TIMEOUT_S = 5.0

LRESULT = ctypes.c_ssize_t


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wt.DWORD),
        ("scanCode", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.c_int,
    wt.WPARAM,
    wt.LPARAM,
)


user32.SetWindowsHookExW.restype = wt.HHOOK
user32.SetWindowsHookExW.argtypes = (
    ctypes.c_int,
    HOOKPROC,
    wt.HINSTANCE,
    wt.DWORD,
)

user32.UnhookWindowsHookEx.restype = wt.BOOL
user32.UnhookWindowsHookEx.argtypes = (
    wt.HHOOK,
)

user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = (
    wt.HHOOK,
    ctypes.c_int,
    wt.WPARAM,
    wt.LPARAM,
)

user32.PostThreadMessageW.restype = wt.BOOL
user32.PostThreadMessageW.argtypes = (
    wt.DWORD,
    wt.UINT,
    wt.WPARAM,
    wt.LPARAM,
)

user32.GetMessageW.restype = wt.BOOL
user32.GetMessageW.argtypes = (
    ctypes.POINTER(wt.MSG),
    wt.HWND,
    wt.UINT,
    wt.UINT,
)

kernel32.GetCurrentThreadId.restype = wt.DWORD


class WindowsKeyboardBackend:
    def __init__(self) -> None:
        self.events: queue.SimpleQueue = queue.SimpleQueue()
        self.init_error: int | None = None

        self._trigger_vks: frozenset[int] = frozenset()
        self._enabled = False

        self._capture_mode = False
        self._capture_start = 0.0
        self._capture_results: queue.SimpleQueue = queue.SimpleQueue()

        self._suppressed_down_vks: set[int] = set()

        self._started = threading.Event()

        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook = None
        self._proc = None

    # ------------------------------------------------------------------
    # Public backend API
    # ------------------------------------------------------------------

    def set_trigger_keys(
        self,
        keys: frozenset[str],
    ) -> None:
        mapped = frozenset(
            key_to_vk(key)
            for key in keys
        )
        self._trigger_vks = mapped

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def begin_capture(self) -> None:
        self._capture_mode = True
        self._capture_start = time.monotonic()
        self._drain_capture_results()

    def cancel_capture(self) -> None:
        self._capture_mode = False
        self._suppressed_down_vks.clear()
        self._drain_capture_results()
        self._capture_results.put(
            CaptureResult(kind="cancel")
        )

    def poll_capture_result(
        self,
    ) -> CaptureResult | None:
        try:
            return self._capture_results.get_nowait()
        except queue.Empty:
            return None

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return self.init_error is None

        self.init_error = None
        self._started.clear()
        self._thread_id = 0
        self._hook = None
        self._proc = None

        self._thread = threading.Thread(
            target=self._run,
            name="mtk-keyboard-hook",
            daemon=True,
        )

        self._thread.start()

        if not self._started.wait(timeout=10):
            self.init_error = self.init_error or 1
            return False

        return self.init_error is None

    def stop(self) -> None:
        self._enabled = False

        thread_id = self._thread_id

        if thread_id:
            user32.PostThreadMessageW(
                thread_id,
                WM_QUIT,
                0,
                0,
            )

        thread = self._thread

        if thread:
            thread.join(timeout=5)

            if thread.is_alive():
                log.error(
                    "keyboard hook thread did not stop within timeout"
                )

        self._suppressed_down_vks.clear()
        self._capture_mode = False
        self._drain_capture_results()

    # ------------------------------------------------------------------
    # Thread / Hook
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            self._thread_id = (
                kernel32.GetCurrentThreadId()
            )

            self._proc = HOOKPROC(
                self._proc_callback
            )

            self._hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                self._proc,
                None,
                0,
            )

            if not self._hook:
                self.init_error = (
                    ctypes.get_last_error() or 1
                )
                return

            self._started.set()

            msg = wt.MSG()

            while True:
                result = user32.GetMessageW(
                    ctypes.byref(msg),
                    None,
                    0,
                    0,
                )

                if result == 0:
                    break

                if result == -1:
                    self.init_error = (
                        ctypes.get_last_error() or 1
                    )
                    break

        except Exception:
            self.init_error = (
                ctypes.get_last_error() or 1
            )
            log.exception(
                "keyboard hook thread failed"
            )

        finally:
            self._started.set()

            if self._hook:
                user32.UnhookWindowsHookEx(
                    self._hook
                )
                self._hook = None

            self._thread_id = 0

    # ------------------------------------------------------------------
    # Hook callback
    # ------------------------------------------------------------------

    def _proc_callback(
        self,
        n_code,
        w_param,
        l_param,
    ):
        try:
            if n_code < 0:
                return user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )

            if n_code != HC_ACTION:
                return user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )

            info = l_param.contents

            # 1. Own injected input: never interpret.
            if info.dwExtraInfo == INJECTED_MARKER:
                return user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )

            is_down = w_param in (
                WM_KEYDOWN,
                WM_SYSKEYDOWN,
            )

            is_up = w_param in (
                WM_KEYUP,
                WM_SYSKEYUP,
            )

            vk = int(info.vkCode)

            # 2. Existing suppression lifecycle takes priority
            # over capture and trigger configuration.
            if vk in self._suppressed_down_vks:
                if is_up:
                    self._suppressed_down_vks.discard(vk)

                    key = vk_to_key(vk)

                    if (
                        key is not None
                        and self._enabled
                        and vk in self._trigger_vks
                    ):
                        self.events.put(
                            RawKeyEvent(
                                key=key,
                                is_down=False,
                                injected=bool(
                                    info.flags
                                    & LLKHF_INJECTED
                                ),
                                timestamp=time.monotonic(),
                            )
                        )

                return 1

            # 3. Capture.
            if (
                self._capture_mode
                and is_down
                and not (
                    info.flags
                    & LLKHF_INJECTED
                )
            ):
                # 超时保护：捕获卡住超过上限就自动取消，
                # 绝不永久吞掉后续按键。
                if (
                    time.monotonic()
                    - self._capture_start
                    > CAPTURE_TIMEOUT_S
                ):
                    self.cancel_capture()
                    return user32.CallNextHookEx(
                        None,
                        n_code,
                        w_param,
                        l_param,
                    )

                key = vk_to_key(vk)

                if key is None:
                    # 不认识的键无法绑定：直接放行，继续等待有效键。
                    # 由上面的超时保护兜底，不会因无效键而永久卡死。
                    return user32.CallNextHookEx(
                        None,
                        n_code,
                        w_param,
                        l_param,
                    )

                self._suppressed_down_vks.add(vk)

                if key == "Esc":
                    self._capture_mode = False
                    self._capture_results.put(
                        CaptureResult(
                            kind="cancel"
                        )
                    )
                    return 1

                self._capture_mode = False
                self._capture_results.put(
                    CaptureResult(
                        kind="key",
                        key=key,
                    )
                )

                return 1

            # 4. Active trigger.
            if (
                self._enabled
                and vk in self._trigger_vks
                and is_down
            ):
                key = vk_to_key(vk)

                if key is not None:
                    self._suppressed_down_vks.add(vk)

                    self.events.put(
                        RawKeyEvent(
                            key=key,
                            is_down=True,
                            injected=bool(
                                info.flags
                                & LLKHF_INJECTED
                            ),
                            timestamp=time.monotonic(),
                        )
                    )

                    return 1

            # 5. Unhandled event.
            return user32.CallNextHookEx(
                None,
                n_code,
                w_param,
                l_param,
            )
        except Exception:
            # 任何意外都“放行”，绝不因报错而吞掉按键（失败开放原则）。
            log.exception(
                "keyboard hook callback error; passing event through"
            )
            try:
                return user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )
            except Exception:
                return 0

    def _drain_capture_results(self) -> None:
        try:
            while True:
                self._capture_results.get_nowait()
        except queue.Empty:
            return
