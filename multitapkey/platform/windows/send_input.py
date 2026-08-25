"""Windows keyboard output using SendInput."""

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

_INTER_KEY_DELAY_SECONDS = 0.005
_DEFAULT_HOLD_SECONDS = 0.015


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


def _send_vk(vk: int, flags: int) -> None:
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki = KEYBDINPUT(
        wVk=vk,
        wScan=0,
        dwFlags=flags,
        time=0,
        dwExtraInfo=INJECTED_MARKER,
    )

    sent = user32.SendInput(
        1,
        ctypes.byref(inp),
        ctypes.sizeof(INPUT),
    )

    if sent != 1:
        raise OSError(
            f"SendInput failed, error={ctypes.get_last_error()}"
        )


def _key_down_vk(vk: int) -> None:
    _send_vk(vk, 0)


def _key_up_vk(vk: int) -> None:
    _send_vk(vk, KEYEVENTF_KEYUP)


class WindowsInputBackend:
    """Implements InputBackend."""

    def __init__(
        self,
        down=_key_down_vk,
        up=_key_up_vk,
        hold_seconds: float = _DEFAULT_HOLD_SECONDS,
        inter_key_delay_seconds: float = _INTER_KEY_DELAY_SECONDS,
    ) -> None:
        self._down = down
        self._up = up
        self._hold_seconds = hold_seconds
        self._inter_key_delay_seconds = inter_key_delay_seconds
        self._lock = threading.Lock()

    def tap_key(self, key: str) -> None:
        vk = key_to_vk(key)

        with self._lock:
            down_sent = False

            try:
                self._down(vk)
                down_sent = True
                time.sleep(self._hold_seconds)
            finally:
                if down_sent:
                    try:
                        self._up(vk)
                    except Exception:
                        log.exception(
                            "failed to release injected key: key=%s",
                            key,
                        )

    def tap_combo(
        self,
        modifier_keys: tuple[str, ...],
        key: str,
    ) -> None:
        modifier_vks = tuple(
            key_to_vk(modifier)
            for modifier in modifier_keys
        )
        key_vk = key_to_vk(key)

        with self._lock:
            held_modifiers: list[int] = []
            main_down = False

            try:
                for modifier_vk in modifier_vks:
                    self._down(modifier_vk)
                    held_modifiers.append(modifier_vk)
                    time.sleep(self._inter_key_delay_seconds)

                self._down(key_vk)
                main_down = True

                time.sleep(self._hold_seconds)

            finally:
                if main_down:
                    try:
                        self._up(key_vk)
                    except Exception:
                        log.exception(
                            "failed to release combo main key: key=%s",
                            key,
                        )

                for modifier_vk in reversed(held_modifiers):
                    try:
                        self._up(modifier_vk)
                    except Exception:
                        log.exception(
                            "failed to release combo modifier: vk=%s",
                            modifier_vk,
                        )

                    time.sleep(
                        self._inter_key_delay_seconds
                    )
