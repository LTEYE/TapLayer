"""Driver-level keyboard output using the Interception filter driver.

InterceptionBackend implements InputBackend by injecting scan codes through
the Interception driver (services `keyboard`/`mouse`). Driver-level strokes
carry no LLKHF_INJECTED flag, so apps that filter SendInput/keybd_event
(such as Doubao IME's voice hotkey) accept them. RoutingInputBackend picks
per-profile between this and the standard SendInput backend.

All strokes carry INJECTED_MARKER in the driver's `information` field, which
arrives as dwExtraInfo at low-level hooks — the existing self-echo filter
in keyboard_hook.py recognizes it unchanged.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import threading
import time

from ..base import InputBackend
from .keymap import key_to_vk
from .send_input import (
    INJECTED_MARKER,
    WindowsInputBackend,
    _send_key,
)

KEYEVENTF_KEYUP = 0x0002

log = logging.getLogger(__name__)

try:  # 延迟依赖：未安装 interception-python 时仅禁用驱动级输出
    from interception import Interception, KeyStroke
except Exception:  # pragma: no cover - import guard
    Interception = None  # type: ignore[assignment]
    KeyStroke = None  # type: ignore[assignment]

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# Interception KeyState：KEY_UP=1（注意不是 2，2 是 KEY_E0）
_KEY_E0 = 0x02
_KEY_UP = 0x01

MAPVK_VK_TO_VSC = 0

# 通用修饰键 VK（Shift/Ctrl/Alt）按左侧物理键注入
_GENERIC_TO_PHYSICAL = {0x10: 0xA0, 0x11: 0xA2, 0x12: 0xA4}

# 需要 E0 前缀的扩展键（标准 Set 1 扫描码）
_EXTENDED_VKS = frozenset(
    {
        0x21, 0x22, 0x23, 0x24,  # PgUp/PgDn/Home/End
        0x25, 0x26, 0x27, 0x28,  # 方向键
        0x2C, 0x2D, 0x2E,  # PrintScreen/Insert/Delete
        0x5B, 0x5C, 0x5D,  # 左/右 Win、AppMenu
        0xA3, 0xA5,  # RightCtrl/RightAlt
        0x6F,  # 小键盘除号
    }
)

_DEFAULT_HOLD_SECONDS = 0.015
_DEFAULT_CHORD_HOLD_SECONDS = 0.05
# 相邻按键之间的注入间隔，给目标应用的热键钩子留出识别窗口
_INTER_STROKE_SECONDS = 0.005

_DEVICE_PATHS = ("\\\\.\\keyboard", "\\\\.\\mouse")

kernel32.CreateFileW.restype = ctypes.c_void_p
kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)


def _device_openable(path: str) -> bool:
    """控制通道能否打开：驱动加载后设备才存在（重启前的假象排除在外）。"""
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3

    handle = kernel32.CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        0,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if handle:
        kernel32.CloseHandle(handle)
        return True
    return False


def is_interception_available() -> bool:
    """驱动级输出可用性：设备可打开 + 驱动库可导入。

    注意 Interception() 构造函数会吞掉设备打开失败，单看它会有假阳性，
    因此以 keyboard / mouse 设备通道的实际打开结果为准。
    """
    if Interception is None:
        return False
    return all(_device_openable(path) for path in _DEVICE_PATHS)


def _vk_scan_flags(vk: int) -> tuple[int, int]:
    """VK -> (扫描码, 基础 KeyState)：E0 扩展标志放在 state 里而非扫描码。"""
    vk = _GENERIC_TO_PHYSICAL.get(vk, vk)
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    if not scan:
        raise ValueError(f"no scan code for vk=0x{vk:02X}")
    return scan, (_KEY_E0 if vk in _EXTENDED_VKS else 0)


class InterceptionBackend:
    """Driver-level InputBackend；发送失败整组回退标准 SendInput。"""

    def __init__(
        self,
        hold_seconds: float = _DEFAULT_HOLD_SECONDS,
        output_echo=None,
    ) -> None:
        self._hold_seconds = hold_seconds
        self._lock = threading.Lock()
        self._fallback = WindowsInputBackend(hold_seconds)
        self._ict = None
        self._device = None
        self._degraded = False
        # 回声登记：驱动输出不带 dwExtraInfo 标记（与物理键一致，
        # 目标应用无法按 extra info 过滤——豆包即按此拦截）。
        # 自身钩子改由 OutputEcho 按 扫描码+方向+时限 认领。
        self._echo = output_echo
        self._cookie = 0

    def set_cookie(self, cookie: int) -> None:
        if cookie != self._cookie:
            log.info(
                "Interception: cookie set to 0x%X",
                cookie,
            )
        self._cookie = cookie

    # -- 协议（与 WindowsInputBackend 对齐） --------------------------

    def tap_key(self, key: str) -> None:
        self.tap_chord((key,))

    def tap_chord(
        self,
        keys: tuple[str, ...],
        hold_ms: int | None = None,
    ) -> None:
        if not keys:
            return
        try:
            self._driver_tap_chord(keys, hold_ms)
            log.info(
                "Interception: chord sent keys=%s hold_ms=%s",
                keys,
                hold_ms,
            )
        except Exception:
            self._note_degraded()
            log.exception(
                "Interception chord failed; falling back keys=%s",
                keys,
            )
            self._fallback.tap_chord(keys, hold_ms)

    def hold_chord_until(
        self,
        keys: tuple[str, ...],
    ):
        if not keys:
            raise ValueError("empty chord")

        try:
            self._driver_press(keys)
            log.info(
                "Interception: hold pressed keys=%s",
                keys,
            )
        except Exception:
            self._note_degraded()
            log.exception(
                "Interception hold failed; "
                "falling back keys=%s",
                keys,
            )
            # 整组回退：由标准后端接管按下与释放
            return self._fallback.hold_chord_until(keys)

        released = threading.Event()

        def release() -> None:
            if released.is_set():
                return
            released.set()
            try:
                self._driver_release(keys)
            except Exception:
                self._note_degraded()
                # 驱动松开失败：用 SendInput 只发 KEYUP 补松，
                # 绝不能再按下去（否则修饰键永远卡住）
                for key in reversed(keys):
                    try:
                        _send_key(
                            key_to_vk(key),
                            KEYEVENTF_KEYUP,
                        )
                    except Exception:
                        log.exception(
                            "failed to release held "
                            "chord via keybd_event: %s",
                            key,
                        )

        return release

    # -- 驱动层 -------------------------------------------------------

    def _ensure(self) -> bool:
        if self._ict is not None:
            return True
        if Interception is None:
            log.warning("Interception: library not importable")
            return False
        try:
            ict = Interception()
            device = ict.keyboard
        except Exception:
            log.exception("Interception: device open failed")
            return False
        self._ict = ict
        self._device = device
        log.info("Interception: device ready (device=%s)", device)
        return True

    def _send(self, scan: int, base_flags: int, up: bool) -> None:
        if self._echo is not None:
            self._echo.record(
                scan,
                bool(base_flags & _KEY_E0),
                up,
            )
        stroke = KeyStroke(scan, base_flags | (_KEY_UP if up else 0))
        stroke.information = self._cookie
        self._ict.send(self._device, stroke)

    def _driver_tap_chord(
        self,
        keys: tuple[str, ...],
        hold_ms: int | None = None,
    ) -> None:
        downs = [_vk_scan_flags(key_to_vk(key)) for key in keys]
        seconds = (
            hold_ms / 1000.0
            if hold_ms is not None
            else (
                _DEFAULT_CHORD_HOLD_SECONDS
                if len(downs) > 1
                else self._hold_seconds
            )
        )

        with self._lock:
            if not self._ensure():
                raise OSError("interception device unavailable")
            pressed: list[tuple[int, int]] = []
            try:
                for scan, base_flags in downs:
                    self._send(scan, base_flags, up=False)
                    pressed.append((scan, base_flags))
                    time.sleep(_INTER_STROKE_SECONDS)
                time.sleep(seconds)
            finally:
                for scan, base_flags in reversed(pressed):
                    try:
                        self._send(scan, base_flags, up=True)
                    except Exception:
                        log.exception(
                            "failed to release driver chord: scan=0x%X",
                            scan,
                        )

    def _driver_press(self, keys: tuple[str, ...]) -> None:
        downs = [_vk_scan_flags(key_to_vk(key)) for key in keys]

        with self._lock:
            if not self._ensure():
                raise OSError("interception device unavailable")
            for scan, base_flags in downs:
                self._send(scan, base_flags, up=False)
                time.sleep(_INTER_STROKE_SECONDS)

    def _driver_release(self, keys: tuple[str, ...]) -> None:
        ups = [_vk_scan_flags(key_to_vk(key)) for key in reversed(keys)]

        with self._lock:
            for scan, base_flags in ups:
                self._send(scan, base_flags, up=True)

    def _note_degraded(self) -> None:
        if not self._degraded:
            self._degraded = True
            log.warning(
                "interception backend degraded; "
                "falling back to SendInput for output"
            )


class RoutingInputBackend:
    """按当前配置档在 标准SendInput / 驱动级Interception 之间路由。

    Engine 在 apply_config 时通过 select_output_backend(profile) 通知
    当前档位的选择（Profile.output_backend），之后所有输出调用
    委派给选中的后端。
    """

    def __init__(
        self,
        primary: InputBackend,
        driver: InterceptionBackend,
    ) -> None:
        self._primary = primary
        self._driver = driver
        self._current = primary
        self._requested = "sendinput"

    def select_output_backend(self, profile) -> None:
        requested = (
            getattr(profile, "output_backend", None)
            or "sendinput"
        )
        self._requested = requested

        if requested != "interception":
            self._current = self._primary
            return

        if is_interception_available():
            self._current = self._driver
            log.info("output backend: interception (driver-level)")
        else:
            self._current = self._primary
            log.warning(
                "output backend: interception requested "
                "but driver unavailable; using sendinput"
            )

    @property
    def requested_backend(self) -> str:
        return self._requested

    @property
    def active_backend_name(self) -> str:
        return (
            "interception"
            if self._current is self._driver
            else "sendinput"
        )

    def tap_key(self, key: str) -> None:
        self._current.tap_key(key)

    def tap_chord(
        self,
        keys: tuple[str, ...],
        hold_ms: int | None = None,
    ) -> None:
        log.info(
            "Routing: tap_chord keys=%s via %s",
            keys,
            self.active_backend_name,
        )
        self._current.tap_chord(keys, hold_ms)

    def hold_chord_until(
        self,
        keys: tuple[str, ...],
    ):
        log.info(
            "Routing: hold keys=%s via %s",
            keys,
            self.active_backend_name,
        )
        return self._current.hold_chord_until(keys)
