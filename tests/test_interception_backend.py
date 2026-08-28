"""InterceptionBackend / RoutingInputBackend / per-profile output_backend."""

import queue
from types import SimpleNamespace

import pytest

from multitapkey.core.config_models import (
    Config,
    Profile,
    validate_and_build,
)
from multitapkey.core.engine import Engine
from multitapkey.platform.base import InputBackend
from multitapkey.platform.windows import interception_backend as ib
from multitapkey.platform.windows.interception_backend import (
    InterceptionBackend,
    RoutingInputBackend,
)


# ---------------------------------------------------------------------------
# 协议契约
# ---------------------------------------------------------------------------


def test_interception_backend_protocol():
    assert isinstance(
        InterceptionBackend(),
        InputBackend,
    )


def test_routing_backend_protocol():
    assert isinstance(
        RoutingInputBackend(
            primary=InterceptionBackend(),
            driver=InterceptionBackend(),
        ),
        InputBackend,
    )


# ---------------------------------------------------------------------------
# 配置：Profile.output_backend 解析与序列化
# ---------------------------------------------------------------------------


def _config_with_backend(value) -> dict:
    return {
        "version": 2,
        "settings": {
            "double_tap_interval_ms": 250,
            "hold_threshold_ms": 500,
            "start_with_windows": False,
            "language": "system",
            "enable_gesture_overlay": False,
        },
        "profiles": {
            "default": {
                "output_backend": value,
                "bindings": [],
            }
        },
    }


def test_output_backend_roundtrip():
    config = validate_and_build(
        _config_with_backend("interception")
    )

    assert (
        config.profiles[0].output_backend
        == "interception"
    )

    data = validate_and_build(
        _config_with_backend("sendinput")
    )

    assert (
        data.profiles[0].output_backend
        == "sendinput"
    )


def test_output_backend_missing_defaults_sendinput():
    data = _config_with_backend("sendinput")
    del data["profiles"]["default"]["output_backend"]

    config = validate_and_build(data)

    assert (
        config.profiles[0].output_backend
        == "sendinput"
    )


def test_output_backend_unknown_clamped():
    config = validate_and_build(
        _config_with_backend("bogus")
    )

    assert (
        config.profiles[0].output_backend
        == "sendinput"
    )


# ---------------------------------------------------------------------------
# 路由选择
# ---------------------------------------------------------------------------


def test_routing_selects_driver_when_available(monkeypatch):
    monkeypatch.setattr(
        ib,
        "is_interception_available",
        lambda: True,
    )

    router = RoutingInputBackend(
        primary=object(),
        driver=InterceptionBackend(),
    )
    router.select_output_backend(
        SimpleNamespace(output_backend="interception")
    )

    assert (
        router.active_backend_name
        == "interception"
    )


def test_routing_falls_back_when_unavailable(monkeypatch):
    monkeypatch.setattr(
        ib,
        "is_interception_available",
        lambda: False,
    )

    router = RoutingInputBackend(
        primary=object(),
        driver=InterceptionBackend(),
    )
    router.select_output_backend(
        SimpleNamespace(output_backend="interception")
    )

    assert (
        router.active_backend_name
        == "sendinput"
    )
    assert (
        router.requested_backend
        == "interception"
    )


def test_routing_sendinput_ignores_driver():
    driver = InterceptionBackend()

    router = RoutingInputBackend(
        primary=object(),
        driver=driver,
    )
    router.select_output_backend(
        SimpleNamespace(output_backend="sendinput")
    )

    assert (
        router.active_backend_name
        == "sendinput"
    )


# ---------------------------------------------------------------------------
# 驱动不可达时整组回退标准后端
# ---------------------------------------------------------------------------


class _FallbackRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def tap_key(self, key):
        self.calls.append(("tap_key", key))

    def tap_chord(self, keys, hold_ms=None):
        self.calls.append(
            ("tap_chord", keys, hold_ms)
        )

    def hold_chord_until(self, keys):
        self.calls.append(("hold", keys))
        return lambda: None


def test_tap_chord_falls_back_without_driver():
    fallback = _FallbackRecorder()
    backend = InterceptionBackend()
    backend._fallback = fallback
    backend._ensure = lambda: False

    backend.tap_chord(("X",))

    assert fallback.calls == [
        ("tap_chord", ("X",), None)
    ]


def test_hold_falls_back_without_driver():
    fallback = _FallbackRecorder()
    backend = InterceptionBackend()
    backend._fallback = fallback
    backend._ensure = lambda: False

    release = backend.hold_chord_until(
        ("Alt", "X")
    )
    release()

    assert fallback.calls == [
        ("hold", ("Alt", "X"))
    ]


def test_release_fallback_sends_keyup_only(monkeypatch):
    """驱动松开失败时只发 KEYUP，不能再按下去（否则修饰键卡死）。"""
    ups: list[int] = []

    monkeypatch.setattr(
        ib,
        "_send_key",
        lambda vk, flags: ups.append((vk, flags)),
    )

    backend = InterceptionBackend()
    backend._ensure = lambda: True

    def boom(scan, base_flags, up):
        if up:
            raise OSError("driver dead")

    backend._send = boom

    release = backend.hold_chord_until(
        ("LeftAlt", "X")
    )
    release()

    assert len(ups) == 2
    assert all(
        flags == ib.KEYEVENTF_KEYUP
        for _, flags in ups
    )
    # 松开顺序必须反序：X 先于 LeftAlt
    assert ups[0][0] == 0x58 and ups[1][0] == 0xA4


# ---------------------------------------------------------------------------
# Engine 按配置档通知后端选择
# ---------------------------------------------------------------------------


class _FakeKeyboardBackend:
    def __init__(self) -> None:
        self.events = queue.SimpleQueue()

    def start(self):
        return True

    def stop(self):
        pass

    def begin_capture(self):
        pass

    def cancel_capture(self):
        pass

    def poll_capture_result(self):
        return None

    def set_trigger_chords(self, chords):
        pass

    def set_enabled(self, enabled):
        pass


def test_engine_notifies_profile_backend_selection():
    selected: list = []

    class _SelectableBackend:
        def tap_key(self, key):
            pass

        def tap_chord(self, keys, hold_ms=None):
            pass

        def hold_chord_until(self, keys):
            return lambda: None

        def select_output_backend(self, profile):
            selected.append(profile)

    engine = Engine(
        keyboard_backend=_FakeKeyboardBackend(),
        input_backend=_SelectableBackend(),
    )
    engine.apply_config(validate_and_build(
        _config_with_backend("interception")
    ))

    assert len(selected) == 1
    assert (
        selected[0].output_backend
        == "interception"
    )


def test_driver_output_is_cookieless_and_records_echo():
    """驱动输出必须无 dwExtraInfo 标记（豆包按它过滤），
    并向回声登记表记录每次击键。"""
    from multitapkey.platform.windows.output_echo import (
        OutputEcho,
    )

    echo = OutputEcho()
    backend = InterceptionBackend(output_echo=echo)
    backend._ensure = lambda: True
    sent: list = []
    backend._ict = SimpleNamespace(
        send=lambda dev, stroke: sent.append(stroke)
    )
    backend._device = 1

    backend.tap_chord(("X",))

    assert backend._cookie == 0
    assert [
        (s.code, s.flags, s.information)
        for s in sent
    ] == [(0x2D, 0, 0), (0x2D, 1, 0)]
    assert echo.claim(0x2D, False, False) is True
    assert echo.claim(0x2D, False, True) is True
    assert echo.claim(0x2D, False, False) is False


def test_output_echo_window_expiry():
    from multitapkey.platform.windows.output_echo import (
        OutputEcho,
    )

    echo = OutputEcho()
    echo.record(0x2D, False, False)

    # 直接把登记时间改老，模拟超时
    with echo._lock:
        scan, e0, up, _ts = echo._items[0]
        echo._items[0] = (scan, e0, up, 0.0)

    assert echo.claim(0x2D, False, False) is False
