"""Lightweight JSON-based internationalization."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QLocale


log = logging.getLogger(__name__)

SUPPORTED = {
    "system",
    "zh_CN",
    "en_US",
}


class I18nManager:
    def __init__(
        self,
        language: str = "system",
        base_dir: Path | None = None,
    ) -> None:
        self._requested_language = language
        self._base_dir = (
            base_dir
            if base_dir is not None
            else (
                Path(__file__)
                .resolve()
                .parent
                / "translations"
            )
        )

        self._translations: dict[
            str,
            dict[str, str],
        ] = {}

        self._load_all()

        self._resolved_language = (
            self._resolve_language(
                language
            )
        )

    @staticmethod
    def _resolve_language(
        language: str,
    ) -> str:
        if language == "en_US":
            return "en_US"

        if language == "zh_CN":
            return "zh_CN"

        if language != "system":
            return "en_US"

        system_locale = (
            QLocale.system().name()
        )

        if system_locale.lower().startswith(
            "zh_"
        ):
            return "zh_CN"

        return "en_US"

    def _load_all(self) -> None:
        for language in (
            "en_US",
            "zh_CN",
        ):
            path = (
                self._base_dir
                / f"{language}.json"
            )

            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(
                data,
                dict,
            ):
                raise RuntimeError(
                    f"translation file must be object: {path}"
                )

            self._translations[
                language
            ] = data

        if set(
            self._translations[
                "en_US"
            ]
        ) != set(
            self._translations[
                "zh_CN"
            ]
        ):
            raise RuntimeError(
                "translation key sets differ"
            )

        for language, data in (
            self._translations.items()
        ):
            for key, value in data.items():
                if not isinstance(
                    value,
                    str,
                ) or not value.strip():
                    raise RuntimeError(
                        f"empty translation: "
                        f"{language}:{key}"
                    )

    def requested_language(
        self,
    ) -> str:
        return self._requested_language

    def current_language(
        self,
    ) -> str:
        return self._resolved_language

    def set_language(
        self,
        language: str,
    ) -> None:
        if language not in SUPPORTED:
            raise ValueError(
                f"unsupported language: {language}"
            )

        self._requested_language = (
            language
        )

        self._resolved_language = (
            self._resolve_language(
                language
            )
        )

    def tr(
        self,
        key: str,
        **params: object,
    ) -> str:
        current = self._translations.get(
            self._resolved_language,
            {},
        )

        value = current.get(key)

        if value is None:
            log.error(
                "missing translation key: %s",
                key,
            )

            fallback = self._translations[
                "en_US"
            ].get(key)

            if fallback is None:
                return key

            value = fallback

        try:
            return value.format(
                **params
            )
        except Exception:
            log.exception(
                "translation formatting failed: %s",
                key,
            )
            return value
