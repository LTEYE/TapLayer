import queue

from multitapkey.core.config_models import (
    default_config,
)
from multitapkey.core.engine import (
    Engine,
)
from multitapkey.platform.base import (
    RawKeyEvent,
)


class FakeKeyboardBackend:
    def __init__(self):
        self.events = queue.SimpleQueue()
        self.trigger_keys = frozenset()
        self.enabled = False
        self.started = False

    def start(self):
        self.started = True
        return True

    def stop(self):
        self.started = False
        self.enabled = False

    def begin_capture(self):
        pass

    def cancel_capture(self):
        pass

    def poll_capture_result(self):
        return None

    def set_trigger_keys(self, keys):
        self.trigger_keys = frozenset(keys)

    def set_enabled(self, enabled):
        self.enabled = enabled


class FakeInputBackend:
    def __init__(self):
        self.tap_calls = []
        self.combo_calls = []

    def tap_key(self, key):
        self.tap_calls.append(key)

    def tap_combo(
        self,
        modifier_keys,
        key,
    ):
        self.combo_calls.append(
            (
                modifier_keys,
                key,
            )
        )


def make_engine():
    keyboard = FakeKeyboardBackend()
    input_backend = FakeInputBackend()

    engine = Engine(
        keyboard_backend=keyboard,
        input_backend=input_backend,
    )

    engine.start()

    return (
        engine,
        keyboard,
        input_backend,
    )


def test_backend_starts_disabled():
    engine, keyboard, _ = (
        make_engine()
    )

    assert keyboard.started
    assert keyboard.enabled is False
    assert engine.active is False


def test_apply_config_activates_backend():
    engine, keyboard, _ = (
        make_engine()
    )

    engine.apply_config(
        default_config()
    )

    assert keyboard.enabled is True
    assert engine.active is True
    assert "F24" in keyboard.trigger_keys


def test_single_event_dispatches_f23():
    engine, _, input_backend = (
        make_engine()
    )

    engine.apply_config(
        default_config()
    )

    engine.backend.events.put(
        RawKeyEvent(
            key="F24",
            is_down=True,
            injected=False,
            timestamp=0.0,
        )
    )

    engine.backend.events.put(
        RawKeyEvent(
            key="F24",
            is_down=False,
            injected=False,
            timestamp=0.06,
        )
    )

    engine.pump()
    engine.pump()

    engine._machines[
        "F24"
    ].check_timeouts(
        0.4
    )

    assert input_backend.tap_calls == [
        "F23"
    ]


def test_pause_drains_queue():
    engine, keyboard, input_backend = (
        make_engine()
    )

    engine.apply_config(
        default_config()
    )

    keyboard.events.put(
        RawKeyEvent(
            key="F24",
            is_down=True,
            injected=False,
            timestamp=0,
        )
    )

    engine.pause()

    engine.pump()

    assert (
        input_backend.tap_calls
        == []
    )
    assert keyboard.enabled is False


def test_resume_reenables_backend():
    engine, keyboard, _ = (
        make_engine()
    )

    engine.apply_config(
        default_config()
    )

    engine.pause()

    engine.resume()

    assert keyboard.enabled is True
    assert engine.active is True


def test_profile_switch_changes_runtime():
    engine, keyboard, _ = (
        make_engine()
    )

    config = default_config()

    engine.apply_config(
        config,
        "Gaming",
    )

    assert (
        engine.profile_name
        == "Gaming"
    )

    assert keyboard.trigger_keys == frozenset()


def test_cancel_pending_drains_queue():
    engine, keyboard, _ = (
        make_engine()
    )

    engine.apply_config(
        default_config()
    )

    keyboard.events.put(
        RawKeyEvent(
            key="F24",
            is_down=True,
            injected=False,
            timestamp=0,
        )
    )

    engine.cancel_pending()

    with __import__(
        "pytest"
    ).raises(queue.Empty):
        keyboard.events.get_nowait()
