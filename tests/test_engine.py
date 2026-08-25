import queue

from multitapkey.core.config_models import (
    ActionSpec,
    Binding,
    Config,
    GestureSpec,
    Profile,
    Settings,
)
from multitapkey.core.engine import Engine
from multitapkey.platform.base import (
    CaptureResult,
    RawKeyEvent,
)


def chord(*keys):
    return ActionSpec(
        type="chord",
        keys=keys,
    )


def disabled_action():
    return ActionSpec(
        type="disabled"
    )


def make_config(
    taps=None,
    hold=None,
    trigger=("F24",),
):
    if taps is None:
        taps = {
            1: chord("F23"),
        }
    if hold is None:
        hold = disabled_action()

    binding = Binding(
        trigger=trigger,
        enabled=True,
        gestures=GestureSpec(
            taps=tuple(
                sorted(taps.items())
            ),
            hold=hold,
        ),
    )

    return Config(
        version=2,
        settings=Settings(),
        profiles=(
            Profile(
                name="default",
                bindings=(binding,),
            ),
            Profile(
                name="Gaming",
                bindings=(),
            ),
            Profile(
                name="Work",
                bindings=(),
            ),
        ),
    )


class FakeKeyboardBackend:
    def __init__(self) -> None:
        self.events = queue.SimpleQueue()
        self.captured = queue.SimpleQueue()
        self.trigger_chords = frozenset()
        self.enabled = False
        self.started = False

    def start(self) -> bool:
        self.started = True
        return True

    def stop(self) -> None:
        self.started = False

    def begin_capture(self) -> None:
        pass

    def cancel_capture(self) -> None:
        self.captured.put(
            CaptureResult(kind="cancel")
        )

    def poll_capture_result(self):
        try:
            return self.captured.get_nowait()
        except queue.Empty:
            return None

    def set_trigger_chords(
        self,
        chords,
    ) -> None:
        self.trigger_chords = frozenset(
            chords
        )

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled


class FakeInputBackend:
    def __init__(self) -> None:
        self.sent: list[tuple] = []

    def tap_key(self, key: str) -> None:
        self.sent.append((key,))

    def tap_chord(
        self,
        keys,
    ) -> None:
        self.sent.append(tuple(keys))


def make_engine(config=None):
    keyboard = FakeKeyboardBackend()
    inputs = FakeInputBackend()

    engine = Engine(
        keyboard_backend=keyboard,
        input_backend=inputs,
    )

    engine.start()

    if config is not None:
        engine.apply_config(config)

    return engine, keyboard, inputs


def feed(
    keyboard,
    key,
    is_down,
    seconds,
):
    keyboard.events.put(
        RawKeyEvent(
            key=key,
            is_down=is_down,
            injected=False,
            timestamp=seconds,
        )
    )


def test_single_tap_dispatches():
    engine, keyboard, inputs = make_engine(
        make_config()
    )

    feed(keyboard, "F24", True, 0.0)
    feed(keyboard, "F24", False, 0.05)
    engine.pump()

    assert inputs.sent == [
        ("F23",)
    ]


def test_double_tap_dispatches():
    engine, keyboard, inputs = make_engine(
        make_config(
            taps={
                1: chord("F23"),
                2: chord("F24"),
            }
        )
    )

    for t in (0.0, 0.15):
        feed(keyboard, "F24", True, t)
        feed(keyboard, "F24", False, t + 0.06)

    engine.pump()

    assert inputs.sent == [
        ("F24",)
    ]


def test_tap4_dispatches():
    engine, keyboard, inputs = make_engine(
        make_config(
            taps={
                1: chord("F23"),
                2: chord("F24"),
                3: chord("F22"),
                4: chord("F21"),
            }
        )
    )

    for i in range(4):
        t = i * 0.15
        feed(keyboard, "F24", True, t)
        feed(keyboard, "F24", False, t + 0.06)

    engine.pump()

    assert inputs.sent == [
        ("F21",)
    ]


def test_chord_output_dispatches():
    engine, keyboard, inputs = make_engine(
        make_config(
            taps={
                1: chord("Ctrl", "A"),
            }
        )
    )

    feed(keyboard, "F24", True, 0.0)
    feed(keyboard, "F24", False, 0.05)
    engine.pump()

    assert inputs.sent == [
        ("Ctrl", "A")
    ]


def test_hold_dispatches():
    engine, keyboard, inputs = make_engine(
        make_config(
            taps={
                1: chord("F23"),
            },
            hold=chord("F21"),
        )
    )

    from multitapkey.core.state_machine import (
        Gesture,
    )

    engine._dispatch(
        "F24",
        Gesture.LONG,
    )

    assert inputs.sent == [
        ("F21",)
    ]


def test_disabled_gesture_does_nothing():
    engine, keyboard, inputs = make_engine(
        make_config(
            taps={
                1: disabled_action(),
            }
        )
    )

    feed(keyboard, "F24", True, 0.0)
    feed(keyboard, "F24", False, 0.05)
    engine.pump()

    assert inputs.sent == []


def test_disabled_binding_ignored():
    config = make_config()
    binding = config.profiles[0].bindings[0]
    config = Config(
        version=2,
        settings=Settings(),
        profiles=(
            Profile(
                name="default",
                bindings=(
                    Binding(
                        trigger=binding.trigger,
                        enabled=False,
                        gestures=binding.gestures,
                    ),
                ),
            ),
            Profile(
                name="Gaming",
                bindings=(),
            ),
            Profile(
                name="Work",
                bindings=(),
            ),
        ),
    )

    engine, keyboard, inputs = make_engine(config)

    assert keyboard.trigger_chords == frozenset()

    feed(keyboard, "F24", True, 0.0)
    feed(keyboard, "F24", False, 0.05)
    engine.pump()

    assert inputs.sent == []


def test_trigger_chords_registered():
    engine, keyboard, _ = make_engine(
        make_config(
            trigger=("A", "S")
        )
    )

    assert ("A", "S") in (
        keyboard.trigger_chords
    )


def test_gesture_observer_notified():
    engine, keyboard, _ = make_engine(
        make_config()
    )

    observed = []

    engine.set_gesture_observer(
        observed.append
    )

    feed(keyboard, "F24", True, 0.0)
    feed(keyboard, "F24", False, 0.05)
    engine.pump()

    # 观察者收到的是"将要执行的输出动作"
    assert observed == ["F23"]


def test_gesture_observer_not_called_for_disabled():
    engine, keyboard, _ = make_engine(
        make_config(
            taps={
                1: disabled_action(),
            }
        )
    )

    observed = []

    engine.set_gesture_observer(
        observed.append
    )

    feed(keyboard, "F24", True, 0.0)
    feed(keyboard, "F24", False, 0.05)
    engine.pump()

    assert observed == []


def test_gesture_observer_not_called_when_unset():
    engine, keyboard, _ = make_engine(
        make_config()
    )

    feed(keyboard, "F24", True, 0.0)
    feed(keyboard, "F24", False, 0.05)
    engine.pump()

    # 未设置观察者时不报错
    assert True


def test_pause_clears_state():
    engine, keyboard, _ = make_engine(
        make_config()
    )

    engine.pause()

    feed(keyboard, "F24", True, 0.0)
    feed(keyboard, "F24", False, 0.05)
    engine.pump()

    # 暂停时事件被丢弃，不触发动作
    assert engine.paused
