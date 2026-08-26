"""Canonical key names <-> Windows virtual-key codes."""

from __future__ import annotations


VK_BY_NAME: dict[str, int] = {
    **{chr(code): code for code in range(0x41, 0x5B)},
    **{str(number): 0x30 + number for number in range(10)},
    **{f"F{i}": 0x70 + i - 1 for i in range(1, 25)},
    # 鼠标键（作触发键用；注意左/右键作触发键会吞掉点击）
    "MouseLeft": 0x01,
    "MouseRight": 0x02,
    "MouseMiddle": 0x04,
    "MouseX1": 0x05,
    "MouseX2": 0x06,
    "Space": 0x20,
    "Enter": 0x0D,
    "Esc": 0x1B,
    "Backspace": 0x08,
    "Tab": 0x09,
    "CapsLock": 0x14,
    "Insert": 0x2D,
    "Delete": 0x2E,
    "Home": 0x24,
    "End": 0x23,
    "PageUp": 0x21,
    "PageDown": 0x22,
    "Left": 0x25,
    "Up": 0x26,
    "Right": 0x27,
    "Down": 0x28,
    "PrintScreen": 0x2C,
    "ScrollLock": 0x91,
    "Pause": 0x13,
    "NumLock": 0x90,
    "VolumeMute": 0xAD,
    "VolumeDown": 0xAE,
    "VolumeUp": 0xAF,
    "MediaNext": 0xB0,
    "MediaPrev": 0xB1,
    "MediaStop": 0xB2,
    "MediaPlayPause": 0xB3,
    # 小键盘
    "NumPad0": 0x60,
    "NumPad1": 0x61,
    "NumPad2": 0x62,
    "NumPad3": 0x63,
    "NumPad4": 0x64,
    "NumPad5": 0x65,
    "NumPad6": 0x66,
    "NumPad7": 0x67,
    "NumPad8": 0x68,
    "NumPad9": 0x69,
    "NumPadMultiply": 0x6A,
    "NumPadAdd": 0x6B,
    "NumPadSubtract": 0x6D,
    "NumPadDecimal": 0x6E,
    "NumPadDivide": 0x6F,
    # 标点符号（OEM 键，用直观名）
    "Semicolon": 0xBA,
    "Equal": 0xBB,
    "Comma": 0xBC,
    "Minus": 0xBD,
    "Period": 0xBE,
    "Slash": 0xBF,
    "Backquote": 0xC0,
    "LeftBracket": 0xDB,
    "Backslash": 0xDC,
    "RightBracket": 0xDD,
    "Apostrophe": 0xDE,
    "Oem102": 0xE2,
    # 菜单键 / 系统键
    "AppMenu": 0x5D,
    "Sleep": 0x5F,
    # 浏览器键
    "BrowserBack": 0xA6,
    "BrowserForward": 0xA7,
    "BrowserRefresh": 0xA8,
    "BrowserStop": 0xA9,
    "BrowserSearch": 0xAA,
    "BrowserFavorites": 0xAB,
    "BrowserHome": 0xAC,
    # 启动键
    "LaunchMail": 0xB4,
    "LaunchMedia": 0xB5,
    "LaunchApp1": 0xB6,
    "LaunchApp2": 0xB7,
    "Shift": 0x10,
    "Ctrl": 0x11,
    "Alt": 0x12,
    "Win": 0x5B,
}

_PHYSICAL_MODIFIERS: dict[int, str] = {
    0xA0: "Shift",
    0xA1: "Shift",
    0xA2: "Ctrl",
    0xA3: "Ctrl",
    0xA4: "Alt",
    0xA5: "Alt",
    0x5B: "Win",
    0x5C: "Win",
}

NAME_BY_VK: dict[int, str] = {
    value: key for key, value in VK_BY_NAME.items()
}


def key_to_vk(key: str) -> int:
    try:
        return VK_BY_NAME[key]
    except KeyError:
        raise ValueError(f"unsupported Windows key: {key!r}") from None


def vk_to_key(vk: int) -> str | None:
    if vk in _PHYSICAL_MODIFIERS:
        return _PHYSICAL_MODIFIERS[vk]
    return NAME_BY_VK.get(vk)
