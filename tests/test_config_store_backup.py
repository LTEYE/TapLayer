"""Config persistence backup & auto-restore tests."""

import dataclasses

import pytest

from multitapkey.core import config_store
from multitapkey.core.config_models import (
    ConfigError,
    default_config,
)


@pytest.fixture
def appdata(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "APPDATA",
        str(tmp_path),
    )
    return tmp_path


def test_save_creates_backup(
    appdata,
):
    config = default_config()
    config_store.save_config(config)

    target = config_store.config_path()
    backup = config_store._backup_path()

    assert target.exists()
    assert backup.exists()
    assert (
        target.read_text(encoding="utf-8")
        == backup.read_text(encoding="utf-8")
    )


def test_load_restores_from_backup(
    appdata,
):
    base = default_config()
    config = dataclasses.replace(
        base,
        settings=dataclasses.replace(
            base.settings,
            language="en_US",
        ),
    )
    config_store.save_config(config)

    target = config_store.config_path()
    # 人为损坏主配置文件
    target.write_text(
        "{ this is not valid json !!!",
        encoding="utf-8",
    )

    restored = config_store.load_config()

    assert restored.settings.language == "en_US"


def test_load_raises_when_backup_also_corrupt(
    appdata,
):
    config = default_config()
    config_store.save_config(config)

    target = config_store.config_path()
    target.write_text(
        "{ corrupt",
        encoding="utf-8",
    )
    config_store._backup_path().write_text(
        "{ also corrupt",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        config_store.load_config()
