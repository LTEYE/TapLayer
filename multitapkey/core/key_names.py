"""Canonical, platform-independent key names."""

from __future__ import annotations

CANONICAL_KEYS = frozenset(
    {
        *[chr(code) for code in range(ord("A"), ord("Z") + 1)],
        *[str(number) for number in range(10)],
        *[f"F{i}" for i in range(1, 25)],
        # 鼠标键（作触发键；左/右键作触发键会吞掉正常点击，慎用）
        "MouseLeft",
        "MouseRight",
        "MouseMiddle",
        "MouseX1",
        "MouseX2",
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
        # 小键盘
        "NumPad0",
        "NumPad1",
        "NumPad2",
        "NumPad3",
        "NumPad4",
        "NumPad5",
        "NumPad6",
        "NumPad7",
        "NumPad8",
        "NumPad9",
        "NumPadMultiply",
        "NumPadAdd",
        "NumPadSubtract",
        "NumPadDecimal",
        "NumPadDivide",
        # 标点符号（OEM 键，用直观名）
        "Semicolon",
        "Equal",
        "Comma",
        "Minus",
        "Period",
        "Slash",
        "Backquote",
        "LeftBracket",
        "Backslash",
        "RightBracket",
        "Apostrophe",
        "Oem102",
        # 菜单键 / 系统键
        "AppMenu",
        "Sleep",
        # 浏览器键
        "BrowserBack",
        "BrowserForward",
        "BrowserRefresh",
        "BrowserStop",
        "BrowserSearch",
        "BrowserFavorites",
        "BrowserHome",
        # 启动键
        "LaunchMail",
        "LaunchMedia",
        "LaunchApp1",
        "LaunchApp2",
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
