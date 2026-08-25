from multitapkey.platform.base import (
    InputBackend,
    KeyboardBackend,
    StartupBackend,
)


class FakeKeyboardBackend:
    events = None

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

    def set_trigger_keys(self, keys):
        pass

    def set_enabled(self, enabled):
        pass


class FakeInputBackend:
    def tap_key(self, key):
        pass

    def tap_combo(
        self,
        modifier_keys,
        key,
    ):
        pass


class FakeStartupBackend:
    def is_available(self):
        return True

    def get_startup(self):
        return False

    def set_startup(self, enabled):
        pass


def test_keyboard_contract():
    assert isinstance(
        FakeKeyboardBackend(),
        KeyboardBackend,
    )


def test_input_contract():
    assert isinstance(
        FakeInputBackend(),
        InputBackend,
    )


def test_startup_contract():
    assert isinstance(
        FakeStartupBackend(),
        StartupBackend,
    )
