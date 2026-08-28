"""Persistent configuration storage."""

from __future__ import annotations

import json
import logging
import os
import shutil
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


def _backup_path() -> Path:
    return (
        config_dir()
        / "config.json.bak"
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


def _atomic_write(
    path: Path,
    data: bytes,
) -> None:
    """原子写：临时文件 + fsync + 原子替换，任何时刻主文件要么是
    完整的旧内容、要么是完整的新内容，绝不会是半个文件。"""
    temp = path.with_name(
        path.name + ".tmp"
    )

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
        path,
    )


def _try_restore_from_backup() -> Config | None:
    """主配置损坏时，尝试从最近一次成功保存的备份恢复。

    返回恢复出的配置；备份不存在/同样损坏时返回 None。
    恢复成功会把主文件重写回好内容（不再覆盖备份），并记录日志。
    """
    backup = _backup_path()

    if not backup.exists():
        return None

    try:
        raw = backup.read_text(
            encoding="utf-8"
        )

        data = json.loads(
            raw
        )

        config = validate_and_build(
            data
        )
    except Exception:
        log.exception(
            "config backup is also invalid; "
            "cannot restore"
        )
        return None

    try:
        _atomic_write(
            config_path(),
            _serialize(config),
        )
        log.warning(
            "restored config from backup after corruption"
        )
    except Exception:
        log.exception(
            "failed to rewrite main config from backup"
        )

    return config


def save_config(
    config: Config,
) -> None:
    target = config_path()

    _atomic_write(
        target,
        _serialize(config),
    )

    # 保存成功后再更新备份：.bak 始终 = 最近一次成功保存的完整配置。
    # 主文件损坏时用它无损恢复；备份失败不影响本次保存。
    try:
        shutil.copy2(
            target,
            _backup_path(),
        )
    except OSError:
        log.warning(
            "failed to update config backup"
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
        restored = _try_restore_from_backup()

        if restored is not None:
            return restored

        log.exception(
            "configuration JSON is invalid "
            "and no usable backup exists"
        )
        raise ConfigError(
            "invalid_json"
        ) from exc

    except ConfigError as exc:
        restored = _try_restore_from_backup()

        if restored is not None:
            return restored

        log.exception(
            "configuration schema is invalid "
            "and no usable backup exists"
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
    _atomic_write(
        path,
        _serialize(config),
    )
