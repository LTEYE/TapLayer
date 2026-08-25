"""Canonical Chord model.

A Chord is an unordered set of simultaneously held canonical keys.
``A + S`` and ``S + A`` are the same chord.

Canonical rules:
- modifier keys keep a stable order: Ctrl, Shift, Alt, Win;
- non-modifier keys are sorted;
- left/right modifier variants are normalized;
- duplicate keys are removed;
- a single key is just a chord of length 1.
"""

from __future__ import annotations

from .key_names import (
    CANONICAL_KEYS,
    MODIFIER_NAMES,
    is_valid_key_name,
)

MODIFIER_ORDER = (
    "Ctrl",
    "Shift",
    "Alt",
    "Win",
)

_NORMALIZE_ALIASES = {
    "LCtrl": "Ctrl",
    "RCtrl": "Ctrl",
    "LeftCtrl": "Ctrl",
    "RightCtrl": "Ctrl",
    "LShift": "Shift",
    "RShift": "Shift",
    "LeftShift": "Shift",
    "RightShift": "Shift",
    "LAlt": "Alt",
    "RAlt": "Alt",
    "LeftAlt": "Alt",
    "RightAlt": "Alt",
    "LWin": "Win",
    "RWin": "Win",
    "LeftWin": "Win",
    "RightWin": "Win",
}

# 组合数量上限（规格：最多 8 个物理键）
MAX_CHORD_KEYS = 8


def normalize_key(
    name: str,
) -> str:
    return _NORMALIZE_ALIASES.get(
        name,
        name,
    )


def canonicalize_keys(
    keys,
) -> tuple[str, ...]:
    """Validate and canonicalize an iterable of key names."""
    normalized: list[str] = []

    for raw in keys:
        if not isinstance(raw, str):
            raise ValueError(
                f"invalid chord key: {raw!r}"
            )

        name = normalize_key(raw)

        if not is_valid_key_name(name):
            raise ValueError(
                f"invalid chord key: {raw!r}"
            )

        if name not in normalized:
            normalized.append(name)

    modifiers = [
        modifier
        for modifier in MODIFIER_ORDER
        if modifier in normalized
    ]

    non_modifiers = sorted(
        (
            key
            for key in normalized
            if key not in MODIFIER_NAMES
        )
    )

    return tuple(
        modifiers + non_modifiers
    )


def chord_display(
    keys,
) -> str:
    return " + ".join(
        canonicalize_keys(keys)
    )


def is_valid_chord(
    keys,
) -> bool:
    try:
        chord = canonicalize_keys(keys)
    except ValueError:
        return False

    return len(chord) > 0 and (
        len(chord) <= MAX_CHORD_KEYS
    )
