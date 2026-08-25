"""Cross-platform backend protocol contracts (Chord-based)."""

from multitapkey.platform.base import (
    InputBackend,
    KeyboardBackend,
    StartupBackend,
)
from multitapkey.platform.windows.keyboard_hook import (
    WindowsKeyboardBackend,
)
from multitapkey.platform.windows.send_input import (
    WindowsInputBackend,
)
from multitapkey.platform.windows.startup import (
    WindowsStartupBackend,
)


def test_keyboard_backend_protocol():
    assert isinstance(
        WindowsKeyboardBackend(),
        KeyboardBackend,
    )


def test_input_backend_protocol():
    assert isinstance(
        WindowsInputBackend(),
        InputBackend,
    )


def test_startup_backend_protocol():
    assert isinstance(
        WindowsStartupBackend(),
        StartupBackend,
    )
