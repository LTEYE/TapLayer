"""WH_KEYBOARD_LL backend for Windows (Chord-based triggers)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import queue
import threading
import time

from multitapkey.core.chord import (
    MAX_CHORD_KEYS,
    chord_display,
)
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
CAPTURE_TIMEOUT_S = 30.0

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

        self._trigger_chords: frozenset[
            tuple[str, ...]
        ] = frozenset()
        # 预计算的 (display, frozenset) 列表，保证匹配顺序稳定
        self._triggers: list[
            tuple[str, frozenset[str]]
        ] = []

        self._enabled = False

        self._capture_mode = False
        self._capture_start = 0.0
        self._capture_held: set[str] = set()
        self._capture_results: queue.SimpleQueue = queue.SimpleQueue()

        self._suppressed_down_vks: set[int] = set()

        # 当前物理按下的键（规范名集合）
        self._pressed: set[str] = set()
        # 当前已激活的 trigger chord（display 集合）
        self._active: set[str] = set()

        self._started = threading.Event()

        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook = None
        self._proc = None

    # ------------------------------------------------------------------
    # Public backend API
    # ------------------------------------------------------------------

    def set_trigger_chords(
        self,
        chords: frozenset[tuple[str, ...]],
    ) -> None:
        self._trigger_chords = frozenset(
            chords
        )

        self._triggers = sorted(
            (
                (
                    chord_display(chord),
                    frozenset(chord),
                )
                for chord in self._trigger_chords
            ),
            key=lambda item: item[0],
        )

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def begin_capture(self) -> None:
        self._capture_mode = True
        self._capture_held.clear()
        self._capture_start = time.monotonic()
        self._drain_capture_results()

    def cancel_capture(self) -> None:
        self._capture_mode = False
        self._capture_held.clear()
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
        self._capture_held.clear()
        self._pressed.clear()
        self._active.clear()
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

            info = ctypes.cast(
                l_param,
                ctypes.POINTER(
                    KBDLLHOOKSTRUCT
                ),
            ).contents

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

            key = vk_to_key(vk)

            if key is None:
                return user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )

            # 2. Suppressed key lifecycle（单键触发键/录制捕获键）
            if vk in self._suppressed_down_vks:
                if is_down:
                    # 按住期间的自动重复：继续拦截
                    return 1

                # is_up：释放拦截并同步 chord 状态
                self._suppressed_down_vks.discard(vk)
                self._capture_held.discard(key)
                self._pressed.discard(key)
                self._deactivate_affected(key)
                return 1

            # 3. Chord capture（录制器）
            if self._capture_mode:
                if is_down:
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

                    if key in self._capture_held:
                        # 同一键重复按下 / 自动重复：不产生重复项
                        return 1

                    if (
                        len(self._capture_held)
                        >= MAX_CHORD_KEYS
                    ):
                        return 1

                    self._capture_held.add(key)
                    self._suppressed_down_vks.add(vk)

                    if key == "Esc":
                        self._capture_mode = False
                        self._capture_held.clear()
                        self._capture_results.put(
                            CaptureResult(
                                kind="cancel"
                            )
                        )
                        return 1

                    self._capture_results.put(
                        CaptureResult(
                            kind="key",
                            key=key,
                        )
                    )

                    return 1

                return user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )

            # 4. Trigger chord matching
            if self._enabled:
                if is_down:
                    if key in self._pressed:
                        # 自动重复：不产生重复 Trigger
                        return user32.CallNextHookEx(
                            None,
                            n_code,
                            w_param,
                            l_param,
                        )

                    self._pressed.add(key)

                    matched = (
                        self._match_trigger_chord()
                    )

                    if matched is not None:
                        display, chord_set = (
                            matched
                        )

                        self._active.add(display)

                        self.events.put(
                            RawKeyEvent(
                                key=display,
                                is_down=True,
                                injected=False,
                                timestamp=time.monotonic(),
                            )
                        )

                        if len(chord_set) == 1:
                            # 单键触发：拦截该键，避免其到达目标窗口
                            self._suppressed_down_vks.add(
                                key_to_vk(
                                    next(
                                        iter(
                                            chord_set
                                        )
                                    )
                                )
                            )
                            return 1

                    return user32.CallNextHookEx(
                        None,
                        n_code,
                        w_param,
                        l_param,
                    )

                # is_up
                self._pressed.discard(key)
                self._deactivate_affected(key)

                return user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )

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

    # ------------------------------------------------------------------
    # Chord helpers
    # ------------------------------------------------------------------

    def _match_trigger_chord(
        self,
    ) -> tuple[
        str,
        frozenset[str],
    ] | None:
        pressed = frozenset(
            self._pressed
        )

        for display, chord_set in (
            self._triggers
        ):
            if (
                chord_set == pressed
                and display
                not in self._active
            ):
                return (
                    display,
                    chord_set,
                )

        return None

    def _deactivate_affected(
        self,
        released_key: str,
    ) -> None:
        for display, chord_set in (
            self._triggers
        ):
            if (
                display in self._active
                and released_key
                in chord_set
                and not chord_set.issubset(
                    self._pressed
                )
            ):
                self._active.discard(display)

                self.events.put(
                    RawKeyEvent(
                        key=display,
                        is_down=False,
                        injected=False,
                        timestamp=time.monotonic(),
                    )
                )

    def _drain_capture_results(self) -> None:
        try:
            while True:
                self._capture_results.get_nowait()
        except queue.Empty:
            return
