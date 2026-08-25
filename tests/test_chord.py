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


def test_left_right_modifiers_normalized():
    assert normalize_key("LCtrl") == "Ctrl"
    assert normalize_key("RShift") == "Shift"
    assert normalize_key("LAlt") == "Alt"
    assert normalize_key("RWin") == "Win"

    assert canonicalize_keys(
        ("LCtrl", "RShift", "A")
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
