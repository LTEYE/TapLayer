import pytest

from multitapkey.core.chord import canonicalize_keys
from multitapkey.core.config_models import (
    ActionSpec,
    Binding,
    Config,
    ConfigError,
    GestureSpec,
    Profile,
    Settings,
    default_config,
    get_profile,
    to_dict,
    validate_and_build,
)


def chord(*keys):
    return {
        "type": "chord",
        "keys": list(keys),
    }


def disabled():
    return {
        "type": "disabled",
        "keys": [],
    }


def binding_dict(trigger=("F24",), enabled=True):
    return {
        "trigger": chord(*trigger),
        "enabled": enabled,
        "gestures": {
            "taps": {
                "1": chord("F23"),
                "2": chord("F24"),
                "3": chord("F22"),
                "4": chord("F21"),
            },
            "hold": chord("F21"),
        },
    }


def make_dict(**overrides):
    data = {
        "version": 2,
        "settings": {
            "double_tap_interval_ms": 250,
            "hold_threshold_ms": 500,
            "start_with_windows": False,
            "language": "system",
            "enable_gesture_overlay": False,
        },
        "profiles": {
            "default": {
                "bindings": [binding_dict()],
            },
            "Gaming": {
                "bindings": [],
            },
            "Work": {
                "bindings": [],
            },
        },
    }

    data.update(overrides)
    return data


def test_valid_default():
    config = validate_and_build(
        make_dict()
    )

    assert config.version == 2
    assert len(config.profiles) == 3


@pytest.mark.parametrize(
    "version",
    [1, 3, "2", None],
)
def test_invalid_version(version):
    with pytest.raises(ConfigError) as exc:
        validate_and_build(
            make_dict(version=version)
        )

    assert exc.value.code == (
        "unsupported_version"
    )


def test_bool_rejected_as_double_tap():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                settings={
                    "double_tap_interval_ms": True,
                    "hold_threshold_ms": 500,
                    "start_with_windows": False,
                    "language": "system",
                    "enable_gesture_overlay": False,
                }
            )
        )


def test_double_tap_range():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                settings={
                    "double_tap_interval_ms": 10,
                    "hold_threshold_ms": 500,
                    "start_with_windows": False,
                    "language": "system",
                    "enable_gesture_overlay": False,
                }
            )
        )


def test_hold_range():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                settings={
                    "double_tap_interval_ms": 250,
                    "hold_threshold_ms": 50,
                    "start_with_windows": False,
                    "language": "system",
                    "enable_gesture_overlay": False,
                }
            )
        )


def test_overlay_must_be_bool():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                settings={
                    "double_tap_interval_ms": 250,
                    "hold_threshold_ms": 500,
                    "start_with_windows": False,
                    "language": "system",
                    "enable_gesture_overlay": "yes",
                }
            )
        )


def test_unknown_root_field():
    with pytest.raises(ConfigError) as exc:
        validate_and_build(
            make_dict(mystery=True)
        )

    assert exc.value.code == (
        "unknown_field"
    )


def test_invalid_trigger_key():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                profiles={
                    "default": {
                        "bindings": [
                            binding_dict(
                                trigger=("NOPE",)
                            )
                        ],
                    },
                    "Gaming": {"bindings": []},
                    "Work": {"bindings": []},
                }
            )
        )


def test_empty_action_chord_allowed_as_unset():
    # 空 chord 动作 = "选择热键"未设置状态，合法放行（trigger 已配置时亦然）
    config = validate_and_build(
        make_dict(
            profiles={
                "default": {
                    "bindings": [
                        {
                            "trigger": chord("F24"),
                            "enabled": True,
                            "gestures": {
                                "taps": {
                                    "1": {
                                        "type": "chord",
                                        "keys": [],
                                    },
                                },
                                "hold": disabled(),
                            },
                        },
                    ],
                },
                "Gaming": {"bindings": []},
                "Work": {"bindings": []},
            }
        )
    )

    tap_action = config.profiles[0].bindings[0].gestures.taps[0][1]

    assert tap_action == ActionSpec(
        type="chord",
        keys=(),
    )


def test_duplicate_trigger_rejected():
    data = make_dict()

    data["profiles"]["default"] = {
        "bindings": [
            binding_dict(trigger=("A", "S")),
            binding_dict(trigger=("S", "A")),
        ],
    }

    with pytest.raises(ConfigError) as exc:
        validate_and_build(data)

    assert exc.value.code == (
        "duplicate_key"
    )


def test_single_key_and_chord_are_distinct():
    data = make_dict()

    data["profiles"]["default"] = {
        "bindings": [
            binding_dict(trigger=("A",)),
            binding_dict(trigger=("A", "S")),
        ],
    }

    config = validate_and_build(data)

    assert len(
        config.profiles[0].bindings
    ) == 2


def test_invalid_action_type():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                profiles={
                    "default": {
                        "bindings": [
                            {
                                "trigger": chord("F24"),
                                "enabled": True,
                                "gestures": {
                                    "taps": {
                                        "1": {
                                            "type": "key",
                                            "keys": ["A"],
                                        },
                                    },
                                    "hold": disabled(),
                                },
                            },
                        ],
                    },
                    "Gaming": {"bindings": []},
                    "Work": {"bindings": []},
                }
            )
        )


def test_disabled_action_with_keys_rejected():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                profiles={
                    "default": {
                        "bindings": [
                            {
                                "trigger": chord("F24"),
                                "enabled": True,
                                "gestures": {
                                    "taps": {
                                        "1": {
                                            "type": "disabled",
                                            "keys": ["A"],
                                        },
                                    },
                                    "hold": disabled(),
                                },
                            },
                        ],
                    },
                    "Gaming": {"bindings": []},
                    "Work": {"bindings": []},
                }
            )
        )


def test_chord_too_large_rejected():
    keys = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]

    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                profiles={
                    "default": {
                        "bindings": [
                            binding_dict(trigger=keys),
                        ],
                    },
                    "Gaming": {"bindings": []},
                    "Work": {"bindings": []},
                }
            )
        )


def test_tap_count_range():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                profiles={
                    "default": {
                        "bindings": [
                            {
                                "trigger": chord("F24"),
                                "enabled": True,
                                "gestures": {
                                    "taps": {
                                        "10": chord("F23"),
                                    },
                                    "hold": disabled(),
                                },
                            },
                        ],
                    },
                    "Gaming": {"bindings": []},
                    "Work": {"bindings": []},
                }
            )
        )


def test_missing_default_profile_rejected():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                profiles={
                    "Gaming": {"bindings": []},
                    "Work": {"bindings": []},
                }
            )
        )


def test_empty_profile_set_rejected():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                profiles={}
            )
        )


def test_arbitrary_profile_name_allowed():
    data = make_dict()

    data["profiles"]["MyProfile"] = {
        "bindings": [binding_dict()],
    }

    config = validate_and_build(data)

    names = {
        profile.name
        for profile in config.profiles
    }

    assert "MyProfile" in names


def test_invalid_language():
    with pytest.raises(ConfigError):
        validate_and_build(
            make_dict(
                settings={
                    "double_tap_interval_ms": 250,
                    "hold_threshold_ms": 500,
                    "start_with_windows": False,
                    "language": "fr_FR",
                    "enable_gesture_overlay": False,
                }
            )
        )


def test_config_immutable():
    config = validate_and_build(
        make_dict()
    )

    with pytest.raises(Exception):
        config.settings.double_tap_interval_ms = 999


def test_round_trip():
    config = validate_and_build(
        make_dict()
    )

    rebuilt = validate_and_build(
        to_dict(config)
    )

    assert config == rebuilt


def test_import_data_has_no_shared_mutable_runtime():
    config = validate_and_build(
        make_dict()
    )

    rebuilt = validate_and_build(
        to_dict(config)
    )

    assert config is not rebuilt
    assert config.profiles[0] is not (
        rebuilt.profiles[0]
    )


def test_chord_keys_are_canonicalized():
    config = validate_and_build(
        make_dict(
            profiles={
                "default": {
                    "bindings": [
                        binding_dict(
                            trigger=("S", "A")
                        ),
                    ],
                },
                "Gaming": {"bindings": []},
                "Work": {"bindings": []},
            }
        )
    )

    binding = config.profiles[0].bindings[0]

    assert binding.trigger == (
        "A",
        "S",
    )


def test_default_config_profiles_populated():
    config = default_config()

    for profile in config.profiles:
        assert len(profile.bindings) > 0


def test_default_trigger_unset():
    config = default_config()

    binding = config.profiles[0].bindings[0]

    # 默认模板触发键未设置（"选择热键"状态），由用户录制
    assert binding.trigger == ()


def test_empty_trigger_allowed_as_unset():
    data = make_dict(
        profiles={
            "default": {
                "bindings": [
                    binding_dict(
                        trigger=()
                    ),
                ],
            },
            "Gaming": {"bindings": []},
            "Work": {"bindings": []},
        }
    )

    config = validate_and_build(data)

    assert (
        config.profiles[0].bindings[0].trigger
        == ()
    )


def test_empty_chord_action_allowed_as_unset():
    """空 chord 动作（\"选择热键\"未设置状态）必须放行，与 disabled 区分。"""
    data = make_dict(
        profiles={
            "default": {
                "bindings": [
                    {
                        "trigger": chord(),
                        "enabled": True,
                        "gestures": {
                            "taps": {
                                "1": chord(),
                            },
                            "hold": chord(),
                        },
                    },
                ],
            },
            "Gaming": {"bindings": []},
            "Work": {"bindings": []},
        }
    )

    config = validate_and_build(data)

    binding = config.profiles[0].bindings[0]

    assert binding.trigger == ()

    assert binding.gestures.taps == (
        (1, ActionSpec(type="chord", keys=())),
    )

    assert binding.gestures.hold == ActionSpec(
        type="chord",
        keys=(),
    )
