"""Windows SendInput ctypes batch-call regression test.

修复过的 bug：批量发送时 `ctypes.byref(inputs)` 传数组导致
`expected LP_INPUT instance instead of pointer to INPUT_Array_2`，
所有输出静默失败。此测试在真实 SendInput 前用桩函数校验
参数类型可被正确解读，防止回归。
"""

import ctypes

from multitapkey.platform.windows import (
    send_input as si,
)


def _install_fake_sendinput(
    monkeypatch,
    captured: dict,
):
    def fake_sendinput(
        count,
        ptr,
        size,
    ):
        captured["count"] = count
        captured["ptr"] = ptr
        return count

    monkeypatch.setattr(
        si.user32,
        "SendInput",
        fake_sendinput,
    )


def test_send_vks_batch_single_key(
    monkeypatch,
):
    captured = {}
    _install_fake_sendinput(
        monkeypatch,
        captured,
    )

    si._send_vks(
        (0x7B,),
        0,
    )

    assert captured["count"] == 1

    arr = ctypes.cast(
        captured["ptr"],
        ctypes.POINTER(si.INPUT),
    )

    assert arr[0].ki.wVk == 0x7B
    assert arr[0].ki.dwExtraInfo == (
        si.INJECTED_MARKER
    )


def test_send_vks_batch_chord(
    monkeypatch,
):
    captured = {}
    _install_fake_sendinput(
        monkeypatch,
        captured,
    )

    # Alt(0x12) + Q(0x51) 整组按下：必须能通过 ctypes 类型检查
    si._send_vks(
        (0x12, 0x51),
        0,
    )

    assert captured["count"] == 2

    arr = ctypes.cast(
        captured["ptr"],
        ctypes.POINTER(si.INPUT),
    )

    assert arr[0].ki.wVk == 0x12
    assert arr[1].ki.wVk == 0x51


def test_send_vks_batch_release(
    monkeypatch,
):
    captured = {}
    _install_fake_sendinput(
        monkeypatch,
        captured,
    )

    # 反序松开（Q up, Alt up）也不能抛类型错误
    si._send_vks(
        (0x51, 0x12),
        si.KEYEVENTF_KEYUP,
    )

    assert captured["count"] == 2

    arr = ctypes.cast(
        captured["ptr"],
        ctypes.POINTER(si.INPUT),
    )

    assert arr[0].ki.dwFlags == (
        si.KEYEVENTF_KEYUP
    )


def test_tap_chord_releases_keys_when_send_fails(
    monkeypatch,
):
    """按下中途被拦截（外设驱动/安全软件间歇性 error=87）时，
    已按下的修饰键必须仍被松开——否则 Alt/Ctrl 会卡死在按住状态。"""
    calls: list[tuple[int, int]] = []
    kbd_calls: list[tuple[int, int]] = []

    def flaky_sendinput(count, ptr, size):
        arr = ctypes.cast(
            ptr,
            ctypes.POINTER(si.INPUT),
        )

        # 模拟本机现象：批量数组被拦截返回 0
        if count > 1:
            return 0

        # Q 键（0x51）按下被间歇性拦截返回 0
        if (
            arr[0].ki.wVk == 0x51
            and arr[0].ki.dwFlags == 0
        ):
            return 0

        calls.append(
            (arr[0].ki.wVk, arr[0].ki.dwFlags)
        )
        return count

    monkeypatch.setattr(
        si.user32,
        "SendInput",
        flaky_sendinput,
    )
    monkeypatch.setattr(
        si.user32,
        "keybd_event",
        lambda vk, scan, flags, extra: (
            kbd_calls.append((vk, flags))
        ),
    )

    backend = si.WindowsInputBackend()
    backend.tap_chord(
        ("LeftAlt", "Q")
    )

    # Alt（0xA4）必须被松开（keyup 尝试过）
    released = [
        vk
        for vk, flags in calls
        if flags & si.KEYEVENTF_KEYUP
    ]
    assert 0xA4 in released

    # Q 按下最终由 keybd_event 兜底发出
    assert (0x51, 0) in kbd_calls
