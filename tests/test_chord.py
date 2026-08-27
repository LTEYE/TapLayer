"""Chord canonicalization tests."""

import pytest

from multitapkey.core.chord import (
    MAX_CHORD_KEYS,
    canonicalize_keys,
    chord_display,
    is_valid_chord,
    normalize_key,
)


def test_single_key_chord():
    assert canonicalize_keys(
        ("F24",)
    ) == ("F24",)


def test_order_normalized():
    assert canonicalize_keys(
        ("S", "A")
    ) == ("A", "S")


def test_modifiers_keep_stable_order():
    assert canonicalize_keys(
        ("Shift", "Ctrl", "A")
    ) == ("Ctrl", "Shift", "A")


def test_modifiers_before_plain_keys():
    assert canonicalize_keys(
        ("B", "Ctrl", "A")
    ) == ("Ctrl", "A", "B")


def test_left_right_modifiers_distinct():
    # 左右修饰键保留独立（缩写归一到全称，但不合并左右）
    assert normalize_key("LCtrl") == "LeftCtrl"
    assert normalize_key("RShift") == "RightShift"
    assert normalize_key("LAlt") == "LeftAlt"
    assert normalize_key("RWin") == "RightWin"

    assert canonicalize_keys(
        ("LCtrl", "RShift", "A")
    ) == ("LeftCtrl", "RightShift", "A")

    # 统一名仍合法（表示任意侧，旧配置兼容）
    assert canonicalize_keys(
        ("Ctrl", "Shift", "A")
    ) == ("Ctrl", "Shift", "A")


def test_duplicates_removed():
    assert canonicalize_keys(
        ("A", "A")
    ) == ("A",)


def test_invalid_key_rejected():
    with pytest.raises(ValueError):
        canonicalize_keys(
            ("NOPE",)
        )


def test_empty_is_invalid_chord():
    assert is_valid_chord(()) is False


def test_too_large_invalid():
    keys = (
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
    )

    assert len(keys) > MAX_CHORD_KEYS
    assert is_valid_chord(keys) is False


def test_display_format():
    assert chord_display(
        ("S", "A")
    ) == "A + S"


def test_display_modifier_chord():
    assert chord_display(
        ("Shift", "Ctrl", "A")
    ) == "Ctrl + Shift + A"
