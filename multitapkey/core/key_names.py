"""Canonical, platform-independent key names."""

from __future__ import annotations

CANONICAL_KEYS = frozenset(
    {
        *[chr(code) for code in range(ord("A"), ord("Z") + 1)],
        *[str(number) for number in range(10)],
        *[f"F{i}" for i in range(1, 25)],
        "Space",
        "Enter",
        "Esc",
        "Backspace",
        "Tab",
        "CapsLock",
        "Insert",
        "Delete",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "Left",
        "Up",
        "Right",
        "Down",
        "PrintScreen",
        "ScrollLock",
        "Pause",
        "NumLock",
        "VolumeMute",
        "VolumeDown",
        "VolumeUp",
        "MediaNext",
        "MediaPrev",
        "MediaStop",
        "MediaPlayPause",
        "Ctrl",
        "Shift",
        "Alt",
        "Win",
    }
)

MODIFIER_NAMES = frozenset(
    {
        "Ctrl",
        "Shift",
        "Alt",
        "Win",
    }
)


def is_valid_key_name(name: object) -> bool:
    return isinstance(name, str) and name in CANONICAL_KEYS


def is_valid_modifier(name: object) -> bool:
    return isinstance(name, str) and name in MODIFIER_NAMES
