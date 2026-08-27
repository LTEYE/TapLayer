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
WH_MOUSE_LL = 14

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

# 自定义消息：主线程请求钩子线程重装钩子（钩子被系统静默
# 移除后的自愈通道）
WM_USER = 0x0400
WM_REHOOK = WM_USER + 1

# 鼠标消息
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C

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


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wt.POINT),
        ("mouseData", wt.DWORD),
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
        # 录制时鼠标是否悬停在"热键区"（蓝色按键显示区）上。
        # 由 UI 侧 enter/leave 事件维护（跨线程读 bool 安全）——
        # 不依赖坐标换算，DPI/多屏/窗口拖动都无误差。
        self._mouse_in_area = False

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
        self._mouse_hook = None
        self._mouse_proc = None

        # 回调内错误计数（轻量自增，供外部诊断；不在回调内写日志）
        self._cb_errors = 0

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

    def set_mouse_in_area(
        self,
        inside: bool,
    ) -> None:
        """录制时 UI 同步"鼠标是否在热键区上"（enter/leave 事件维护）。"""
        self._mouse_in_area = bool(inside)

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

    def rehook(self) -> None:
        """请求钩子线程重装钩子（自愈：钩子可能被系统静默移除）。

        有按键按住 / 录制中时跳过，避免重装导致状态丢失。
        """
        if self._pressed or self._capture_mode:
            return

        thread_id = self._thread_id

        if thread_id:
            user32.PostThreadMessageW(
                thread_id,
                WM_REHOOK,
                0,
                0,
            )

    def _rehook_in_thread(self) -> None:
        try:
            if self._hook:
                user32.UnhookWindowsHookEx(
                    self._hook
                )
                self._hook = None

            if self._mouse_hook:
                user32.UnhookWindowsHookEx(
                    self._mouse_hook
                )
                self._mouse_hook = None

            self._hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                self._proc,
                None,
                0,
            )

            self._mouse_hook = (
                user32.SetWindowsHookExW(
                    WH_MOUSE_LL,
                    self._mouse_proc,
                    None,
                    0,
                )
            )

            if not (
                self._hook
                and self._mouse_hook
            ):
                log.warning(
                    "hook re-install failed; "
                    "will retry on next cycle"
                )
        except Exception:
            log.warning(
                "hook re-install error",
                exc_info=True,
            )

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

            # 鼠标钩子（WH_MOUSE_LL）：让鼠标键（侧键/中键）也能当触发键。
            # 与键盘钩子同一线程、同一消息循环；回调同样必须极快返回。
            self._mouse_proc = HOOKPROC(
                self._mouse_proc_callback
            )

            self._mouse_hook = (
                user32.SetWindowsHookExW(
                    WH_MOUSE_LL,
                    self._mouse_proc,
                    None,
                    0,
                )
            )

            if not self._mouse_hook:
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

                if (
                    msg.message == WM_REHOOK
                ):
                    # 自愈：钩子可能被系统静默移除（回调超时），
                    # 重新安装。有按键按住/录制中时跳过，避免状态丢失。
                    self._rehook_in_thread()
                    continue

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

            if self._mouse_hook:
                user32.UnhookWindowsHookEx(
                    self._mouse_hook
                )
                self._mouse_hook = None

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
            # 注意：这里绝不写日志——回调里 log.exception 会产生
            # traceback（很慢），超过 LowLevelHooksTimeout 会导致
            # 钩子被系统静默移除（间歇性失效的元凶）。
            self._cb_errors += 1
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
    # Mouse hook callback（WH_MOUSE_LL：鼠标键也可作触发键）
    # ------------------------------------------------------------------

    @staticmethod
    def _mouse_key(
        w_param,
        mouse_data: int,
    ) -> str | None:
        if w_param in (
            WM_LBUTTONDOWN,
            WM_LBUTTONUP,
        ):
            return "MouseLeft"

        if w_param in (
            WM_RBUTTONDOWN,
            WM_RBUTTONUP,
        ):
            return "MouseRight"

        if w_param in (
            WM_MBUTTONDOWN,
            WM_MBUTTONUP,
        ):
            return "MouseMiddle"

        if w_param in (
            WM_XBUTTONDOWN,
            WM_XBUTTONUP,
        ):
            # XBUTTON 标识在 mouseData 高位字：1 = X1，2 = X2
            button = (
                mouse_data >> 16
            ) & 0xFFFF

            if button == 1:
                return "MouseX1"

            if button == 2:
                return "MouseX2"

        return None

    def _mouse_proc_callback(
        self,
        n_code,
        w_param,
        l_param,
    ):
        try:
            if (
                n_code < 0
                or n_code != HC_ACTION
            ):
                return user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )

            info = ctypes.cast(
                l_param,
                ctypes.POINTER(
                    MSLLHOOKSTRUCT
                ),
            ).contents

            # 注入的输入放行（不解释、不拦截）
            if info.dwExtraInfo == INJECTED_MARKER:
                return user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )

            key = self._mouse_key(
                w_param,
                int(info.mouseData),
            )

            if key is None:
                return user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )

            is_down = w_param in (
                WM_LBUTTONDOWN,
                WM_RBUTTONDOWN,
                WM_MBUTTONDOWN,
                WM_XBUTTONDOWN,
            )

            vk = key_to_vk(key)

            # 2. Suppressed（单键触发键/录制捕获键被拦截后的按住与释放）
            if vk in self._suppressed_down_vks:
                if is_down:
                    return 1

                self._suppressed_down_vks.discard(vk)
                self._capture_held.discard(key)
                self._pressed.discard(key)
                self._deactivate_affected(key)
                return 1

            # 3. Chord capture（录制器：鼠标键也能录进去）
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

                    # 鼠标键只有在"热键区"（蓝色按键显示区）上
                    # 悬停时才捕获；否则放行，保证用户还能操作
                    # 录制弹窗的按钮（确认/取消）。
                    if (
                        key.startswith("Mouse")
                        and not self._mouse_in_area
                    ):
                        return user32.CallNextHookEx(
                            None,
                            n_code,
                            w_param,
                            l_param,
                        )

                    if key in self._capture_held:
                        return 1

                    if (
                        len(self._capture_held)
                        >= MAX_CHORD_KEYS
                    ):
                        return 1

                    self._capture_held.add(key)
                    self._suppressed_down_vks.add(vk)

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
                            # 单键触发：拦截该鼠标键，避免到达目标窗口
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
            # 任何意外都"放行"，绝不因报错而吞掉鼠标事件（失败开放原则）。
            # 回调内绝不写日志（同键盘回调：慢日志 → 超时 → 钩子被拔）。
            self._cb_errors += 1
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

    # 左右修饰键 → 统一名（旧配置 'Ctrl' 等触发键匹配任意侧）
    _SIDE_TO_BASE = {
        "LeftCtrl": "Ctrl",
        "RightCtrl": "Ctrl",
        "LeftShift": "Shift",
        "RightShift": "Shift",
        "LeftAlt": "Alt",
        "RightAlt": "Alt",
        "LeftWin": "Win",
        "RightWin": "Win",
    }

    @staticmethod
    def _chord_matches(
        chord_set: frozenset[str],
        pressed: frozenset[str],
    ) -> bool:
        # 精确匹配优先（触发键显式用了 LeftCtrl 等具体侧名）
        if chord_set == pressed:
            return True

        # 兼容：触发键用统一名（'Ctrl'）时，把实际按下的
        # 左右侧（'LeftCtrl'/'RightCtrl'）归一后比较。
        if any(
            key in WindowsKeyboardBackend._SIDE_TO_BASE
            for key in pressed
        ):
            norm = frozenset(
                WindowsKeyboardBackend._SIDE_TO_BASE.get(
                    key,
                    key,
                )
                for key in pressed
            )
            return set(chord_set) == norm

        return False

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
                display
                not in self._active
                and self._chord_matches(
                    chord_set,
                    pressed,
                )
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
        base = (
            self._SIDE_TO_BASE.get(
                released_key,
                released_key,
            )
        )

        for display, chord_set in (
            self._triggers
        ):
            if (
                display in self._active
                and (
                    base in chord_set
                    or released_key in chord_set
                )
            ):
                # pressed 也做左右归一后判断是否仍满足 chord
                pressed_norm = frozenset(
                    self._SIDE_TO_BASE.get(
                        k,
                        k,
                    )
                    for k in self._pressed
                )

                if not set(
                    chord_set
                ).issubset(
                    pressed_norm
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
