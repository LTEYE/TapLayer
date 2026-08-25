"""Windows 键盘钩子回调的真实行为测试（Chord 版）。"""

import ctypes
import time

import pytest

from multitapkey.platform.windows import keyboard_hook as kh


def _lparam(vk: int, flags: int = 0, extra: int = 0) -> int:
    kbd = kh.KBDLLHOOKSTRUCT()
    kbd.vkCode = vk
    kbd.scanCode = 0
    kbd.flags = flags
    kbd.time = 0
    kbd.dwExtraInfo = extra
    return ctypes.cast(
        ctypes.pointer(kbd),
        ctypes.c_void_p,
    ).value


def _down(backend, key: str, vk: int):
    return backend._proc_callback(
        0,
        kh.WM_KEYDOWN,
        _lparam(vk),
    )


def _up(backend, key: str, vk: int):
    return backend._proc_callback(
        0,
        kh.WM_KEYUP,
        _lparam(vk),
    )


def _next_event(backend):
    return backend.events.get_nowait()


# ----------------------------------------------------------------------
# Chord capture（录制器用）
# ----------------------------------------------------------------------

def test_capture_reads_multiple_keys():
    backend = kh.WindowsKeyboardBackend()
    backend.begin_capture()

    assert (
        _down(backend, "A", 0x41) == 1
    )
    assert (
        _down(backend, "S", 0x53) == 1
    )

    results = []
    while True:
        result = backend.poll_capture_result()
        if result is None:
            break
        results.append(result.key)

    assert sorted(results) == [
        "A",
        "S",
    ]


def test_capture_auto_repeat_ignored():
    backend = kh.WindowsKeyboardBackend()
    backend.begin_capture()

    _down(backend, "A", 0x41)
    # 按住期间自动重复：不再产生结果
    _down(backend, "A", 0x41)

    results = []
    while True:
        result = backend.poll_capture_result()
        if result is None:
            break
        results.append(result.key)

    assert results == ["A"]


def test_capture_esc_cancels():
    backend = kh.WindowsKeyboardBackend()
    backend.begin_capture()

    _down(backend, "Esc", 0x1B)

    result = backend.poll_capture_result()

    assert result is not None
    assert result.kind == "cancel"


def test_capture_cancel_clears_suppression():
    backend = kh.WindowsKeyboardBackend()
    backend.begin_capture()

    _down(backend, "A", 0x41)
    assert backend._suppressed_down_vks

    backend.cancel_capture()

    assert not backend._suppressed_down_vks


def test_capture_timeout_auto_cancels():
    backend = kh.WindowsKeyboardBackend()
    backend.begin_capture()
    backend._capture_start = (
        time.monotonic()
        - kh.CAPTURE_TIMEOUT_S
        - 1
    )

    result = _down(backend, "A", 0x41)

    assert result == 0  # 放行
    assert backend._capture_mode is False


# ----------------------------------------------------------------------
# Trigger chord matching（触发端）
# ----------------------------------------------------------------------

def test_single_key_trigger_suppressed():
    backend = kh.WindowsKeyboardBackend()
    backend.set_trigger_chords(
        frozenset({("F24",)})
    )
    backend.set_enabled(True)

    result = _down(backend, "F24", 0x87)

    assert result == 1  # 单键触发被拦截

    event = _next_event(backend)
    assert event.key == "F24"
    assert event.is_down is True

    result = _up(backend, "F24", 0x87)
    assert result == 1

    event = _next_event(backend)
    assert event.key == "F24"
    assert event.is_down is False


def test_multi_key_chord_matches():
    backend = kh.WindowsKeyboardBackend()
    backend.set_trigger_chords(
        frozenset({("A", "S")})
    )
    backend.set_enabled(True)

    # 按 A：未成组合，放行
    assert _down(backend, "A", 0x41) == 0

    # 按 S：组合完成，触发
    assert _down(backend, "S", 0x53) == 0

    event = _next_event(backend)
    assert event.key == "A + S"
    assert event.is_down is True

    # 松开 A：组合解除
    _up(backend, "A", 0x41)

    event = _next_event(backend)
    assert event.key == "A + S"
    assert event.is_down is False


def test_chord_order_does_not_matter():
    backend = kh.WindowsKeyboardBackend()
    backend.set_trigger_chords(
        frozenset({("A", "S")})
    )
    backend.set_enabled(True)

    # 反序按下：先 S 后 A
    assert _down(backend, "S", 0x53) == 0
    assert _down(backend, "A", 0x41) == 0

    event = _next_event(backend)
    assert event.key == "A + S"


def test_chord_auto_repeat_no_duplicate_trigger():
    backend = kh.WindowsKeyboardBackend()
    backend.set_trigger_chords(
        frozenset({("A", "S")})
    )
    backend.set_enabled(True)

    _down(backend, "A", 0x41)
    _down(backend, "S", 0x53)
    _down(backend, "S", 0x53)  # S 自动重复

    events = []
    while not backend.events.empty():
        events.append(
            backend.events.get_nowait()
        )

    downs = [
        e for e in events if e.is_down
    ]

    assert len(downs) == 1


def test_normal_key_passes_through():
    backend = kh.WindowsKeyboardBackend()
    backend.set_enabled(True)

    result = _down(backend, "B", 0x42)

    assert result == 0


def test_injected_key_never_interpreted():
    backend = kh.WindowsKeyboardBackend()
    backend.set_trigger_chords(
        frozenset({("F24",)})
    )
    backend.set_enabled(True)

    result = backend._proc_callback(
        0,
        kh.WM_KEYDOWN,
        _lparam(
            0x87,
            extra=kh.INJECTED_MARKER,
        ),
    )

    assert result == 0
    assert backend.events.empty()
