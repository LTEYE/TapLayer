from multitapkey.core.state_machine import (
    Gesture,
    TapStateMachine,
)


def make(
    max_taps=3,
    tap_intervals=None,
    hold_override_ms=None,
    double_tap_interval_ms=250,
    hold_threshold_ms=500,
):
    fired = []

    machine = TapStateMachine(
        trigger_key="F24",
        double_tap_interval_ms=double_tap_interval_ms,
        hold_threshold_ms=hold_threshold_ms,
        max_taps=max_taps,
        on_gesture=fired.append,
        tap_intervals=tap_intervals,
        hold_override_ms=hold_override_ms,
    )

    return machine, fired


def press(
    machine,
    milliseconds,
):
    machine.on_key(
        "F24",
        True,
        milliseconds / 1000.0,
    )


def release(
    machine,
    milliseconds,
):
    machine.on_key(
        "F24",
        False,
        milliseconds / 1000.0,
    )


def tick(
    machine,
    milliseconds,
):
    machine.check_timeouts(
        milliseconds / 1000.0
    )


def test_single_tap():
    machine, fired = make()

    press(machine, 0)
    release(machine, 60)

    assert fired == []

    tick(machine, 400)

    assert fired == [
        Gesture.SINGLE
    ]


def test_double_tap():
    machine, fired = make()

    press(machine, 0)
    release(machine, 60)

    press(machine, 150)
    release(machine, 210)

    assert fired == []

    tick(machine, 500)

    assert fired == [
        Gesture.DOUBLE
    ]


def test_triple_fires_immediately():
    machine, fired = make()

    press(machine, 0)
    release(machine, 60)

    press(machine, 150)
    release(machine, 210)

    press(machine, 300)
    release(machine, 360)

    assert fired == [
        Gesture.TRIPLE
    ]


def test_fourth_tap_fires_immediately():
    machine, fired = make(max_taps=4)

    for t in (0, 150, 300, 450):
        press(machine, t)
        release(machine, t + 60)

    assert fired == [
        Gesture.TAP4
    ]


def test_fifth_tap_fires_immediately():
    machine, fired = make(max_taps=5)

    for t in (0, 150, 300, 450, 600):
        press(machine, t)
        release(machine, t + 60)

    assert fired == [
        Gesture.TAP5
    ]


def test_tap_beyond_max_starts_new_sequence():
    machine, fired = make(max_taps=3)

    for t in (0, 150, 300):
        press(machine, t)
        release(machine, t + 60)

    # 3 击已立即触发；第 4 击为新一轮
    press(machine, 800)
    release(machine, 850)

    tick(machine, 1200)

    assert fired == [
        Gesture.TRIPLE,
        Gesture.SINGLE,
    ]


def test_long_press_fires_once():
    machine, fired = make()

    press(machine, 0)
    tick(machine, 510)

    assert fired == [
        Gesture.LONG
    ]

    tick(machine, 700)

    release(machine, 800)

    assert fired == [
        Gesture.LONG
    ]


def test_long_press_detected_on_keyup():
    machine, fired = make()

    press(machine, 0)
    release(machine, 600)

    assert fired == [
        Gesture.LONG
    ]

    tick(machine, 700)

    assert fired == [
        Gesture.LONG
    ]


def test_release_before_threshold():
    machine, fired = make()

    press(machine, 0)
    release(machine, 300)

    tick(machine, 600)

    assert fired == [
        Gesture.SINGLE
    ]


def test_fourth_tap_starts_new_sequence_when_slow():
    machine, fired = make(max_taps=4)

    press(machine, 0)
    release(machine, 60)

    press(machine, 150)
    release(machine, 210)

    press(machine, 300)
    release(machine, 360)

    # 第 4 击来得太慢，超出双击窗口：前 3 击先结算
    press(machine, 800)
    release(machine, 850)

    tick(machine, 1200)

    assert fired == [
        Gesture.TRIPLE,
        Gesture.SINGLE,
    ]


def test_hardware_repeat_ignored():
    machine, fired = make()

    press(machine, 0)
    press(machine, 100)
    press(machine, 200)

    tick(machine, 510)

    assert fired == [
        Gesture.LONG
    ]


def test_slow_second_tap():
    machine, fired = make()

    press(machine, 0)
    release(machine, 50)

    press(machine, 400)

    assert fired == [
        Gesture.SINGLE
    ]

    release(machine, 450)
    tick(machine, 800)

    assert fired == [
        Gesture.SINGLE,
        Gesture.SINGLE,
    ]


def test_reset_discards_pending():
    machine, fired = make()

    press(machine, 0)
    release(machine, 50)

    machine.reset()

    tick(machine, 400)

    assert fired == []


def test_stray_release():
    machine, fired = make()

    machine.on_key(
        "F24",
        False,
        0.1,
    )

    tick(machine, 500)

    assert fired == []


def test_other_key():
    machine, fired = make()

    machine.on_key(
        "A",
        True,
        0.0,
    )

    machine.on_key(
        "A",
        False,
        0.05,
    )

    tick(machine, 500)

    assert fired == []


def test_long_then_quick_new_press():
    machine, fired = make()

    press(machine, 0)
    tick(machine, 510)
    release(machine, 600)

    press(machine, 700)
    release(machine, 740)

    tick(machine, 1100)

    assert fired == [
        Gesture.LONG,
        Gesture.SINGLE,
    ]


def test_second_tap_long_is_long():
    machine, fired = make()

    press(machine, 0)
    release(machine, 60)

    press(machine, 150)
    release(machine, 800)

    tick(machine, 1000)

    assert fired == [
        Gesture.LONG
    ]


def test_per_level_window_slow_third_tap():
    machine, fired = make(
        tap_intervals={2: 200},
    )

    machine.on_key("F24", True, 0.0)
    machine.on_key("F24", False, 0.05)
    machine.on_key("F24", True, 0.30)
    machine.on_key("F24", False, 0.35)
    machine.check_timeouts(0.90)

    assert fired == [
        Gesture.SINGLE,
        Gesture.SINGLE,
    ]


def test_per_level_window_fast_second_tap():
    machine, fired = make(
        tap_intervals={2: 200},
    )

    machine.on_key("F24", True, 0.0)
    machine.on_key("F24", False, 0.05)
    machine.on_key("F24", True, 0.15)
    machine.on_key("F24", False, 0.20)
    # 第 2 击的窗口 = tap_intervals[2] = 200ms：
    # 200ms 内没有第 3 击 → 以双击收尾
    machine.check_timeouts(0.35)

    assert fired == []

    machine.check_timeouts(0.45)

    assert fired == [Gesture.DOUBLE]


def test_hold_override():
    machine, fired = make(
        hold_override_ms=300,
    )

    machine.on_key("F24", True, 0.0)
    machine.check_timeouts(0.35)

    assert fired == [Gesture.LONG]


def test_boss_scenario_double_uses_level1_window():
    """老板场景回归：全局窗口 50ms + "1 击"行自定义窗口 600ms。

    双击（两次点击间隔 200ms）必须识别为 DOUBLE——
    等待第 2 击的窗口取"第 1 击行"的 600ms，而不是回落到
    全局 50ms（旧语义：tap_intervals 错位导致双击被拆成两次单击）。
    """
    machine, fired = make(
        tap_intervals={1: 600},
        double_tap_interval_ms=50,
    )

    machine.on_key("F24", True, 0.0)
    machine.on_key("F24", False, 0.05)
    machine.on_key("F24", True, 0.25)
    machine.on_key("F24", False, 0.30)
    machine.check_timeouts(0.90)

    assert fired == [Gesture.DOUBLE]


def test_hold_threshold_100_quick_tap_stays_single():
    """极端阈值（100ms）下，快速单击（60ms）仍是单击，不是长按。"""
    machine, fired = make(
        hold_threshold_ms=100,
    )

    machine.on_key("F24", True, 0.0)
    machine.on_key("F24", False, 0.06)
    # 松开后等双击窗口（250ms）超时 → 收尾为单击
    machine.check_timeouts(0.40)

    assert fired == [Gesture.SINGLE]


def test_hold_threshold_100_slow_press_is_long():
    """极端阈值（100ms）下，按住超过 100ms 判定为长按。"""
    machine, fired = make(
        hold_threshold_ms=100,
    )

    machine.on_key("F24", True, 0.0)
    machine.check_timeouts(0.15)

    assert fired == [Gesture.LONG]
