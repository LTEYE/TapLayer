"""Persistent configuration storage."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .config_models import (
    Config,
    ConfigError,
    default_config,
    to_dict,
    validate_and_build,
)


log = logging.getLogger(__name__)


def config_dir() -> Path:
    appdata = os.environ.get(
        "APPDATA"
    )

    if not appdata:
        raise RuntimeError(
            "APPDATA is not available"
        )

    path = Path(
        appdata
    ) / "TapLayer"

    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def config_path() -> Path:
    return (
        config_dir()
        / "config.json"
    )


def _serialize(
    config: Config,
) -> bytes:
    return (
        json.dumps(
            to_dict(config),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def save_config(
    config: Config,
) -> None:
    target = config_path()
    temp = target.with_suffix(
        ".json.tmp"
    )

    data = _serialize(config)

    with open(
        temp,
        "wb",
    ) as handle:
        handle.write(data)
        handle.flush()
        os.fsync(
            handle.fileno()
        )

    os.replace(
        temp,
        target,
    )


def load_config() -> Config:
    target = config_path()

    if not target.exists():
        config = default_config()
        save_config(config)
        return config

    try:
        raw = target.read_text(
            encoding="utf-8"
        )

        data = json.loads(
            raw
        )

        return validate_and_build(
            data
        )

    except json.JSONDecodeError as exc:
        log.exception(
            "configuration JSON is invalid"
        )
        raise ConfigError(
            "invalid_json"
        ) from exc

    except ConfigError:
        log.exception(
            "configuration schema is invalid"
        )
        raise


def load_config_file(
    path: Path,
) -> Config:
    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
        return validate_and_build(
            data
        )

    except FileNotFoundError as exc:
        raise ConfigError(
            "invalid_json"
        ) from exc

    except json.JSONDecodeError as exc:
        raise ConfigError(
            "invalid_json"
        ) from exc


def import_config(
    path: Path,
) -> Config:
    config = load_config_file(
        path
    )

    save_config(
        config
    )

    return config


def export_config(
    config: Config,
    path: Path,
) -> None:
    temp = path.with_name(
        path.name + ".tmp"
    )

    with open(
        temp,
        "wb",
    ) as handle:
        handle.write(
            _serialize(config)
        )
        handle.flush()
        os.fsync(
            handle.fileno()
        )

    os.replace(
        temp,
        path,
    )
