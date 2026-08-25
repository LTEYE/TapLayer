import json

from pathlib import Path

from PySide6.QtCore import QLocale

from multitapkey.i18n.manager import (
    I18nManager,
)


def test_translation_keys_match():
    base = (
        Path(__file__).parents[1]
        / "multitapkey"
        / "i18n"
        / "translations"
    )

    en = json.loads(
        (
            base
            / "en_US.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    zh = json.loads(
        (
            base
            / "zh_CN.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert set(en) == set(zh)


def test_translations_are_non_empty():
    base = (
        Path(__file__).parents[1]
        / "multitapkey"
        / "i18n"
        / "translations"
    )

    for language in (
        "en_US",
        "zh_CN",
    ):
        data = json.loads(
            (
                base
                / f"{language}.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        assert all(
            isinstance(value, str)
            and value.strip()
            for value in data.values()
        )


def test_explicit_language():
    manager = I18nManager(
        "en_US"
    )

    assert (
        manager.current_language()
        == "en_US"
    )

    manager.set_language(
        "zh_CN"
    )

    assert (
        manager.current_language()
        == "zh_CN"
    )


def test_translation_lookup():
    manager = I18nManager(
        "en_US"
    )

    assert (
        manager.tr(
            "status.running"
        )
        == "● Running"
    )


def test_missing_key_falls_back_to_key():
    manager = I18nManager(
        "en_US"
    )

    assert (
        manager.tr(
            "not.existing"
        )
        == "not.existing"
    )
