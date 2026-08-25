"""Immutable configuration model and strict validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .key_names import (
    is_valid_key_name,
    is_valid_modifier,
)


PROFILE_NAMES = (
    "default",
    "Gaming",
    "Work",
)

SUPPORTED_LANGUAGES = (
    "system",
    "zh_CN",
    "en_US",
)

ACTION_FIELDS = {
    "type",
    "key",
    "modifiers",
}

BINDING_FIELDS = {
    "trigger",
    "enabled",
    "single",
    "double",
    "triple",
    "long",
}

SETTINGS_FIELDS = {
    "double_tap_interval_ms",
    "hold_threshold_ms",
    "start_with_windows",
    "language",
}

ROOT_FIELDS = {
    "version",
    "settings",
    "profiles",
}


class ConfigError(ValueError):
    def __init__(
        self,
        code: str,
        **params: Any,
    ) -> None:
        self.code = code
        self.params = params

        super().__init__(
            f"{code}: {params}"
        )


@dataclass(frozen=True, slots=True)
class ActionSpec:
    type: str
    key: str | None = None
    modifiers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Binding:
    trigger: str
    enabled: bool
    single: ActionSpec
    double: ActionSpec
    triple: ActionSpec
    long: ActionSpec


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    bindings: tuple[Binding, ...]


@dataclass(frozen=True, slots=True)
class Settings:
    double_tap_interval_ms: int = 250
    hold_threshold_ms: int = 500
    start_with_windows: bool = False
    language: str = "system"


@dataclass(frozen=True, slots=True)
class Config:
    version: int = 1
    settings: Settings = field(
        default_factory=Settings
    )
    profiles: tuple[Profile, ...] = ()


def _require_exact_keys(
    data: dict[str, Any],
    allowed: set[str],
) -> None:
    unknown = set(data) - allowed

    if unknown:
        raise ConfigError(
            "unknown_field",
            fields=sorted(unknown),
        )


def _require_dict(
    value: Any,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(
            "invalid_type",
            field=field_name,
            expected="object",
        )

    return value


def _require_list(
    value: Any,
    field_name: str,
) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigError(
            "invalid_type",
            field=field_name,
            expected="array",
        )

    return value


def _validate_action(
    data: Any,
) -> ActionSpec:
    obj = _require_dict(
        data,
        "action",
    )

    _require_exact_keys(
        obj,
        ACTION_FIELDS,
    )

    action_type = obj.get("type")

    if action_type not in {
        "key",
        "disabled",
    }:
        raise ConfigError(
            "invalid_type",
            field="action.type",
            expected="key|disabled",
        )

    modifiers_raw = obj.get(
        "modifiers",
        [],
    )

    if not isinstance(
        modifiers_raw,
        list,
    ):
        raise ConfigError(
            "invalid_type",
            field="action.modifiers",
            expected="array",
        )

    modifiers: list[str] = []

    for modifier in modifiers_raw:
        if not is_valid_modifier(
            modifier
        ):
            raise ConfigError(
                "invalid_key",
                key=modifier,
            )

        if modifier in modifiers:
            raise ConfigError(
                "duplicate_key",
                key=modifier,
            )

        modifiers.append(modifier)

    key = obj.get("key")

    if action_type == "disabled":
        if key is not None:
            raise ConfigError(
                "invalid_type",
                field="action.key",
                expected="null",
            )

        if modifiers:
            raise ConfigError(
                "invalid_type",
                field="action.modifiers",
                expected="empty",
            )

        return ActionSpec(
            type="disabled"
        )

    if not is_valid_key_name(key):
        raise ConfigError(
            "invalid_key",
            key=key,
        )

    return ActionSpec(
        type="key",
        key=key,
        modifiers=tuple(modifiers),
    )


def _validate_binding(
    data: Any,
) -> Binding:
    obj = _require_dict(
        data,
        "binding",
    )

    _require_exact_keys(
        obj,
        BINDING_FIELDS,
    )

    trigger = obj.get("trigger")

    if not is_valid_key_name(trigger):
        raise ConfigError(
            "invalid_key",
            key=trigger,
        )

    enabled = obj.get("enabled")

    if type(enabled) is not bool:
        raise ConfigError(
            "invalid_type",
            field="binding.enabled",
            expected="bool",
        )

    return Binding(
        trigger=trigger,
        enabled=enabled,
        single=_validate_action(
            obj.get("single")
        ),
        double=_validate_action(
            obj.get("double")
        ),
        triple=_validate_action(
            obj.get("triple")
        ),
        long=_validate_action(
            obj.get("long")
        ),
    )


def _validate_profile(
    name: str,
    data: Any,
) -> Profile:
    if name not in PROFILE_NAMES:
        raise ConfigError(
            "invalid_profile",
            profile=name,
        )

    obj = _require_dict(
        data,
        "profile",
    )

    _require_exact_keys(
        obj,
        {"bindings"},
    )

    raw_bindings = _require_list(
        obj.get("bindings"),
        "profile.bindings",
    )

    bindings: list[Binding] = []
    seen_triggers: set[str] = set()

    for raw_binding in raw_bindings:
        binding = _validate_binding(
            raw_binding
        )

        if binding.trigger in seen_triggers:
            raise ConfigError(
                "duplicate_key",
                key=binding.trigger,
            )

        seen_triggers.add(
            binding.trigger
        )

        bindings.append(binding)

    return Profile(
        name=name,
        bindings=tuple(bindings),
    )


def validate_and_build(
    data: dict[str, Any],
) -> Config:
    if not isinstance(data, dict):
        raise ConfigError(
            "invalid_type",
            field="root",
            expected="object",
        )

    _require_exact_keys(
        data,
        ROOT_FIELDS,
    )

    version = data.get("version")

    if (
        type(version) is not int
        or version != 1
    ):
        raise ConfigError(
            "unsupported_version",
            version=version,
        )

    settings_obj = _require_dict(
        data.get("settings"),
        "settings",
    )

    _require_exact_keys(
        settings_obj,
        SETTINGS_FIELDS,
    )

    double_tap = settings_obj.get(
        "double_tap_interval_ms"
    )
    hold_threshold = settings_obj.get(
        "hold_threshold_ms"
    )
    start_with_windows = settings_obj.get(
        "start_with_windows"
    )
    language = settings_obj.get(
        "language"
    )

    if type(double_tap) is not int:
        raise ConfigError(
            "invalid_type",
            field="double_tap_interval_ms",
            expected="int",
        )

    if not 50 <= double_tap <= 1000:
        raise ConfigError(
            "invalid_range",
            field="double_tap_interval_ms",
        )

    if type(hold_threshold) is not int:
        raise ConfigError(
            "invalid_type",
            field="hold_threshold_ms",
            expected="int",
        )

    if not 100 <= hold_threshold <= 5000:
        raise ConfigError(
            "invalid_range",
            field="hold_threshold_ms",
        )

    if type(start_with_windows) is not bool:
        raise ConfigError(
            "invalid_type",
            field="start_with_windows",
            expected="bool",
        )

    if language not in SUPPORTED_LANGUAGES:
        raise ConfigError(
            "invalid_language",
            language=language,
        )

    profiles_obj = _require_dict(
        data.get("profiles"),
        "profiles",
    )

    if set(profiles_obj) != set(
        PROFILE_NAMES
    ):
        raise ConfigError(
            "invalid_profile",
            profile="profile set",
        )

    profiles = tuple(
        _validate_profile(
            name,
            profiles_obj[name],
        )
        for name in PROFILE_NAMES
    )

    return Config(
        version=1,
        settings=Settings(
            double_tap_interval_ms=double_tap,
            hold_threshold_ms=hold_threshold,
            start_with_windows=start_with_windows,
            language=language,
        ),
        profiles=profiles,
    )


def default_config() -> Config:
    key_action = lambda key: ActionSpec(
        type="key",
        key=key,
        modifiers=(),
    )

    disabled = ActionSpec(
        type="disabled"
    )

    default_binding = Binding(
        trigger="F24",
        enabled=True,
        single=key_action("F23"),
        double=key_action("F24"),
        triple=key_action("F22"),
        long=key_action("F21"),
    )

    return Config(
        version=1,
        settings=Settings(),
        profiles=(
            Profile(
                name="default",
                bindings=(default_binding,),
            ),
            Profile(
                name="Gaming",
                bindings=(),
            ),
            Profile(
                name="Work",
                bindings=(),
            ),
        ),
    )


def get_profile(
    config: Config,
    name: str,
) -> Profile:
    for profile in config.profiles:
        if profile.name == name:
            return profile

    raise ConfigError(
        "invalid_profile",
        profile=name,
    )


def _action_to_dict(
    action: ActionSpec,
) -> dict[str, Any]:
    return {
        "type": action.type,
        "key": action.key,
        "modifiers": list(
            action.modifiers
        ),
    }


def _binding_to_dict(
    binding: Binding,
) -> dict[str, Any]:
    return {
        "trigger": binding.trigger,
        "enabled": binding.enabled,
        "single": _action_to_dict(
            binding.single
        ),
        "double": _action_to_dict(
            binding.double
        ),
        "triple": _action_to_dict(
            binding.triple
        ),
        "long": _action_to_dict(
            binding.long
        ),
    }


def to_dict(
    config: Config,
) -> dict[str, Any]:
    return {
        "version": config.version,
        "settings": {
            "double_tap_interval_ms": (
                config.settings.double_tap_interval_ms
            ),
            "hold_threshold_ms": (
                config.settings.hold_threshold_ms
            ),
            "start_with_windows": (
                config.settings.start_with_windows
            ),
            "language": config.settings.language,
        },
        "profiles": {
            profile.name: {
                "bindings": [
                    _binding_to_dict(binding)
                    for binding in profile.bindings
                ]
            }
            for profile in config.profiles
        },
    }
