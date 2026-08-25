import json

import pytest

from multitapkey.core.config_models import (
    ConfigError,
    default_config,
    to_dict,
    validate_and_build,
)
from multitapkey.core.config_store import (
    load_config_file,
)


def base_data():
    return to_dict(
        default_config()
    )


def test_valid_default():
    config = validate_and_build(
        base_data()
    )

    assert config.version == 1


@pytest.mark.parametrize(
    "version",
    [True, False, 0, 2, "1"],
)
def test_invalid_version(version):
    data = base_data()
    data["version"] = version

    with pytest.raises(ConfigError):
        validate_and_build(data)


def test_bool_rejected_as_double_tap():
    data = base_data()

    data["settings"][
        "double_tap_interval_ms"
    ] = True

    with pytest.raises(ConfigError):
        validate_and_build(data)


@pytest.mark.parametrize(
    "value",
    [49, 1001],
)
def test_double_tap_range(value):
    data = base_data()

    data["settings"][
        "double_tap_interval_ms"
    ] = value

    with pytest.raises(ConfigError):
        validate_and_build(data)


@pytest.mark.parametrize(
    "value",
    [99, 5001],
)
def test_hold_range(value):
    data = base_data()

    data["settings"][
        "hold_threshold_ms"
    ] = value

    with pytest.raises(ConfigError):
        validate_and_build(data)


def test_unknown_root_field():
    data = base_data()
    data["unexpected"] = 123

    with pytest.raises(ConfigError):
        validate_and_build(data)


def test_invalid_key():
    data = base_data()

    data["profiles"]["default"][
        "bindings"
    ][0]["trigger"] = "NOT_A_KEY"

    with pytest.raises(ConfigError):
        validate_and_build(data)


def test_duplicate_trigger():
    data = base_data()

    data["profiles"]["default"][
        "bindings"
    ].append(
        data["profiles"]["default"][
            "bindings"
        ][0]
    )

    with pytest.raises(ConfigError):
        validate_and_build(data)


def test_invalid_action_type():
    data = base_data()

    data["profiles"]["default"][
        "bindings"
    ][0]["single"]["type"] = "macro"

    with pytest.raises(ConfigError):
        validate_and_build(data)


def test_duplicate_modifier():
    data = base_data()

    data["profiles"]["default"][
        "bindings"
    ][0]["single"][
        "modifiers"
    ] = ["Ctrl", "Ctrl"]

    with pytest.raises(ConfigError):
        validate_and_build(data)


def test_invalid_profile_set():
    data = base_data()

    del data["profiles"]["Work"]

    with pytest.raises(ConfigError):
        validate_and_build(data)


def test_invalid_language():
    data = base_data()

    data["settings"]["language"] = "fr_FR"

    with pytest.raises(ConfigError):
        validate_and_build(data)


def test_corrupt_json(tmp_path):
    path = (
        tmp_path
        / "bad.json"
    )

    path.write_text(
        "{not valid json",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config_file(path)


def test_config_immutable():
    config = default_config()

    with pytest.raises(
        AttributeError
    ):
        config.version = 2

    with pytest.raises(
        AttributeError
    ):
        config.profiles = ()


def test_round_trip():
    data = base_data()

    config = validate_and_build(
        data
    )

    assert (
        to_dict(config)
        == data
    )


def test_import_data_has_no_shared_mutable_runtime():
    first = default_config()
    second = validate_and_build(
        to_dict(first)
    )

    assert first == second
