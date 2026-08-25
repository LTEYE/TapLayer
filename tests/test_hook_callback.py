"""Windows 键盘钩子回调的真实行为测试。

防复发背景：回调内曾用 `l_param.contents` 直接取按键信息，
但该参数在真实运行时是整数，导致每次按键都抛 AttributeError——
旧版因此锁死键盘，修复后因异常被兜住而表现为“捕获没反应”。
本测试直接调用真实回调逻辑，防止此类问题再次漏网。
"""

import ctypes
import time

from multitapkey.platform.windows import keyboard_hook as kh


def _lparam(vk: int, flags: int = 0, extra: int = 0) -> int:
    """构造与真实 Windows 回调一致的整数地址参数。"""
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


def test_capture_reads_key_info() -> None:
    backend = kh.WindowsKeyboardBackend()
    backend.begin_capture()

    result = backend._proc_callback(
        0,
        kh.WM_KEYDOWN,
        _lparam(0x41),
    )

    # 捕获模式下按下 A：应拦截（返回 1）、退出捕获、产出 key='A'
    assert result == 1
    assert backend._capture_mode is False

    captured = backend.poll_capture_result()
    assert captured is not None
    assert captured.kind == "key"
    assert captured.key == "A"


def test_capture_releases_on_keyup() -> None:
    backend = kh.WindowsKeyboardBackend()
    backend.begin_capture()
    backend._proc_callback(
        0,
        kh.WM_KEYDOWN,
        _lparam(0x41),
    )
    assert backend._suppressed_down_vks

    result = backend._proc_callback(
        0,
        kh.WM_KEYUP,
        _lparam(0x41),
    )

    # 松开被拦截的键：仍拦截且必须从集合中释放
    assert result == 1
    assert backend._suppressed_down_vks == set()


def test_capture_timeout_auto_cancels() -> None:
    backend = kh.WindowsKeyboardBackend()
    backend.begin_capture()
    backend._capture_start = (
        time.monotonic()
        - kh.CAPTURE_TIMEOUT_S
        - 1
    )

    result = backend._proc_callback(
        0,
        kh.WM_KEYDOWN,
        _lparam(0x41),
    )

    # 超时后：放行（返回 0）且自动退出捕获，绝不永久吞键
    assert result == 0
    assert backend._capture_mode is False


def test_normal_key_passes_through() -> None:
    backend = kh.WindowsKeyboardBackend()
    result = backend._proc_callback(
        0,
        kh.WM_KEYDOWN,
        _lparam(0x42),
    )

    # 非捕获、非触发状态的普通按键：必须放行
    assert result == 0
