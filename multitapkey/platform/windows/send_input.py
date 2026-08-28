"""Windows keyboard output using SendInput (Chord-based)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import threading
import time

from .keymap import key_to_vk

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

INJECTED_MARKER = 0x4D544B4B

_DEFAULT_HOLD_SECONDS = 0.015
# 组合键（2+ 键）整组点按的按住时长：比单键更长，
# 给目标应用足够的识别时间（修饰键+主键组合需要一起按住一小会儿）。
_DEFAULT_CHORD_HOLD_SECONDS = 0.05


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wt.DWORD),
        ("wParamL", wt.WORD),
        ("wParamH", wt.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wt.DWORD),
        ("_input", _INPUTUNION),
    ]


user32.SendInput.argtypes = (
    wt.UINT,
    ctypes.POINTER(INPUT),
    ctypes.c_int,
)
user32.SendInput.restype = wt.UINT

# keybd_event：老 API，某些外设驱动/安全软件只 Hook SendInput，
# 作为 SendInput 失败的兜底手段（void 返回，尽力而为）。
user32.keybd_event.argtypes = (
    wt.BYTE,
    wt.BYTE,
    wt.DWORD,
    ctypes.c_size_t,
)
user32.keybd_event.restype = None


def _send_vks(vks: tuple[int, ...], flags: int) -> int:
    """一次 SendInput 调用发送整组按键事件，返回实际发送数量。

    不抛异常：调用方根据返回数量决定是否降级为逐键发送。
    """
    count = len(vks)
    if count == 0:
        return 0

    # 调试用：实际发送的按键码与按下/松开标志
    log.info(
        "SendInput: vks=%s flags=%s",
        vks,
        flags,
    )

    inputs = (INPUT * count)()
    for i, vk in enumerate(vks):
        inputs[i].type = INPUT_KEYBOARD
        inputs[i].ki = KEYBDINPUT(
            wVk=vk,
            wScan=0,
            dwFlags=flags,
            time=0,
            dwExtraInfo=INJECTED_MARKER,
        )

    return int(
        user32.SendInput(
            count,
            ctypes.cast(
                inputs,
                ctypes.POINTER(INPUT),
            ),
            ctypes.sizeof(INPUT),
        )
    )


def _send_vks_checked(
    vks: tuple[int, ...],
    flags: int,
) -> None:
    """整组发送并要求全部成功；失败抛 OSError（由调用方降级）。"""
    sent = _send_vks(vks, flags)

    if sent != len(vks):
        raise OSError(
            f"SendInput failed, error={ctypes.get_last_error()}"
        )


def _try_batch(
    vks: tuple[int, ...],
    flags: int,
) -> bool:
    """尝试一次调用发送整组事件（原子送达）。

    组合键整组 keydown / keyup 若能在同一次 SendInput 中送达，
    修饰键（Alt/Ctrl/Shift/Win）与主键之间不存在任何可被目标应用
    单独响应的时间间隔——浏览器/应用的菜单栏不会把 Alt 单独抢走，
    "Alt+Q 只输出 Alt" 即源于此。

    本机（外设驱动/安全软件 Hook SendInput）实测批量数组返回 0，
    此时返回 False，调用方降级为逐键发送（零间隔，同样可靠）。
    仅对 2+ 键生效；单键直接返回 False 走逐键路径。
    """
    if len(vks) < 2:
        return False

    sent = _send_vks(vks, flags)

    if sent == len(vks):
        return True

    if sent > 0:
        log.warning(
            "SendInput batch partially sent %s/%s; "
            "falling back to per-key",
            sent,
            len(vks),
        )

    return False


def _send_key(
    vk: int,
    flags: int,
    retries: int = 2,
) -> None:
    """单键发送，带重试与 API 降级。

    部分环境（外设驱动/安全软件 Hook SendInput）会**间歇性**拦截
    单键调用（error=87，表现为"时灵时不灵"）。策略：
    1. SendInput 原样重试（重试之间有 1ms 间隔）；
    2. 仍失败则降级 keybd_event（老 API，通常不被同类 Hook 拦截，
       void 返回无法确认，尽力而为）；
    3. 兜底也不抛异常——由调用方保证任何情况下都会松开按键。
    """
    for attempt in range(retries):
        try:
            _send_vks_checked(
                (vk,),
                flags,
            )
            return
        except OSError:
            if attempt < retries - 1:
                time.sleep(0.001)
                continue

    log.warning(
        "SendInput failed for vk=%s flags=%s "
        "(error=%s); falling back to keybd_event",
        vk,
        flags,
        ctypes.get_last_error(),
    )

    user32.keybd_event(
        vk,
        0,
        flags,
        0,
    )


class WindowsInputBackend:
    """Implements InputBackend (tap_key / tap_chord)."""

    def __init__(
        self,
        hold_seconds: float = _DEFAULT_HOLD_SECONDS,
    ) -> None:
        self._hold_seconds = hold_seconds
        self._lock = threading.Lock()

    def tap_key(self, key: str) -> None:
        self.tap_chord((key,))

    def tap_chord(
        self,
        keys: tuple[str, ...],
        hold_ms: int | None = None,
    ) -> None:
        if not keys:
            return

        vks = tuple(
            key_to_vk(key)
            for key in keys
        )

        if hold_ms is not None:
            seconds = hold_ms / 1000.0
        else:
            # 组合键比单键多留一点按住时间，保证目标应用识别完整组合
            seconds = (
                _DEFAULT_CHORD_HOLD_SECONDS
                if len(vks) > 1
                else self._hold_seconds
            )

        with self._lock:
            # 记录实际按下的键；无论按下是否全部成功，
            # finally 里都必须把它们松开——否则失败后
            # 修饰键（Alt/Ctrl）会卡死在按住状态。
            pressed: list[int] = []
            batch_ok = False

            try:
                # 整组原子发送优先；被拦截（返回不足）时逐键发送。
                batch_ok = _try_batch(vks, 0)

                if batch_ok:
                    pressed = list(vks)
                else:
                    for vk in vks:
                        _send_key(vk, 0)
                        pressed.append(vk)

                time.sleep(seconds)
            finally:
                ups = tuple(reversed(pressed))

                if (
                    ups
                    and batch_ok
                    and _try_batch(ups, KEYEVENTF_KEYUP)
                ):
                    return

                for vk in ups:
                    try:
                        _send_key(vk, KEYEVENTF_KEYUP)
                    except Exception:
                        log.exception(
                            "failed to release injected chord: vk=%s",
                            vk,
                        )

    def hold_chord_until(
        self,
        keys: tuple[str, ...],
    ):
        """按住一个 chord 并保持，返回"释放"回调（幂等，可多次调用）。

        用于"长按触发 → 输出一直按住直到松开触发键"场景：
        按下并保持，由调用方在触发键松开时调用返回的 release()。
        """
        if not keys:
            raise ValueError(
                "empty chord"
            )

        vks = tuple(
            key_to_vk(key)
            for key in keys
        )

        released = threading.Event()

        with self._lock:
            batch_ok = _try_batch(vks, 0)

            if not batch_ok:
                for vk in vks:
                    _send_key(vk, 0)

        def release() -> None:
            if released.is_set():
                return

            released.set()

            with self._lock:
                ups = tuple(reversed(vks))

                if batch_ok and _try_batch(ups, KEYEVENTF_KEYUP):
                    return

                for vk in ups:
                    try:
                        _send_key(vk, KEYEVENTF_KEYUP)
                    except Exception:
                        log.exception(
                            "failed to release held chord: vks=%s",
                            vks,
                        )

        return release
