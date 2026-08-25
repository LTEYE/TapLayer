"""Immutable configuration model and strict validation (Schema v2).

Breaking change: the old ``modifier + key`` action model is gone.
Every action is a Chord (``{"type": "chord", "keys": [...]}``);
a single key is a chord of length 1. ``{"type": "disabled"}`` means
the gesture is unbound. Old v1 configuration files are NOT migrated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .chord import (
    MAX_CHORD_KEYS,
    canonicalize_keys,
    chord_display,
)
from .key_names import (
    is_valid_key_name,
)

CONFIG_VERSION = 2

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

MAX_TAP_COUNT = 9

ACTION_FIELDS = {
    "type",
    "keys",
}

GESTURE_FIELDS = {
    "taps",
    "hold",
}

BINDING_FIELDS = {
    "trigger",
    "enabled",
    "gestures",
}

SETTINGS_FIELDS = {
    "double_tap_interval_ms",
    "hold_threshold_ms",
    "start_with_windows",
    "language",
    "enable_gesture_overlay",
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
    type: str  # "chord" | "disabled"
    keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GestureSpec:
    taps: tuple[
        tuple[int, ActionSpec],
        ...,
    ] = ()
    hold: ActionSpec = field(
        default_factory=lambda: ActionSpec(
            type="disabled"
        )
    )

    @property
    def max_taps(self) -> int:
        if not self.taps:
            return 0
        return max(
            count
            for count, _ in self.taps
        )


@dataclass(frozen=True, slots=True)
class Binding:
    trigger: tuple[str, ...]
    enabled: bool
    gestures: GestureSpec

    @property
    def trigger_display(self) -> str:
        return chord_display(
            self.trigger
        )


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    bindings: tuple[Binding, ...] = ()


@dataclass(frozen=True, slots=True)
class Settings:
    double_tap_interval_ms: int = 250
    hold_threshold_ms: int = 500
    start_with_windows: bool = False
    language: str = "system"
    enable_gesture_overlay: bool = False


@dataclass(frozen=True, slots=True)
class Config:
    version: int = CONFIG_VERSION
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
        "chord",
        "disabled",
    }:
        raise ConfigError(
            "invalid_type",
            field="action.type",
            expected="chord|disabled",
        )

    raw_keys = obj.get(
        "keys",
        [],
    )

    if not isinstance(
        raw_keys,
        list,
    ):
        raise ConfigError(
            "invalid_type",
            field="action.keys",
            expected="array",
        )

    if action_type == "disabled":
        if raw_keys:
            raise ConfigError(
                "invalid_type",
                field="action.keys",
                expected="empty",
            )

        return ActionSpec(
            type="disabled"
        )

    for key in raw_keys:
        if not is_valid_key_name(key):
            raise ConfigError(
                "invalid_key",
                key=key,
            )

    if not raw_keys:
        # 空 chord = 未设置（"选择热键"状态），合法占位；
        # 与 type="disabled"（用户明确禁用）语义不同。
        return ActionSpec(
            type="chord",
            keys=(),
        )

    if len(raw_keys) > MAX_CHORD_KEYS:
        raise ConfigError(
            "invalid_key",
            key="<chord too large>",
        )

    canonical = canonicalize_keys(
        raw_keys
    )

    return ActionSpec(
        type="chord",
        keys=canonical,
    )


def _validate_trigger(
    data: Any,
) -> tuple[str, ...]:
    """Trigger may be an unset chord (empty keys) — shown as 'Select Hotkey'.

    A non-empty trigger is canonicalized. Empty means 'not configured yet',
    and the engine skips such bindings until a trigger is recorded.
    """
    obj = _require_dict(
        data,
        "binding.trigger",
    )

    _require_exact_keys(
        obj,
        ACTION_FIELDS,
    )

    if obj.get("type") != "chord":
        raise ConfigError(
            "invalid_type",
            field="binding.trigger",
            expected="chord",
        )

    raw_keys = obj.get(
        "keys",
        [],
    )

    if not isinstance(
        raw_keys,
        list,
    ):
        raise ConfigError(
            "invalid_type",
            field="binding.trigger.keys",
            expected="array",
        )

    for key in raw_keys:
        if not is_valid_key_name(key):
            raise ConfigError(
                "invalid_key",
                key=key,
            )

    if len(raw_keys) > MAX_CHORD_KEYS:
        raise ConfigError(
            "invalid_key",
            key="<chord too large>",
        )

    if not raw_keys:
        return ()

    return canonicalize_keys(
        raw_keys
    )


def _validate_gestures(
    data: Any,
) -> GestureSpec:
    obj = _require_dict(
        data,
        "gestures",
    )

    _require_exact_keys(
        obj,
        GESTURE_FIELDS,
    )

    taps_obj = _require_dict(
        obj.get("taps"),
        "gestures.taps",
    )

    taps: list[
        tuple[int, ActionSpec]
    ] = []
    seen_counts: set[int] = set()

    for raw_count, raw_action in (
        taps_obj.items()
    ):
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            raise ConfigError(
                "invalid_type",
                field="gestures.taps",
                expected="integer keys",
            ) from None

        if not 1 <= count <= MAX_TAP_COUNT:
            raise ConfigError(
                "invalid_range",
                field="gestures.taps",
            )

        if count in seen_counts:
            raise ConfigError(
                "duplicate_key",
                key=str(count),
            )

        seen_counts.add(count)

        taps.append(
            (
                count,
                _validate_action(
                    raw_action
                ),
            )
        )

    if not taps:
        raise ConfigError(
            "invalid_type",
            field="gestures.taps",
            expected="at least one tap",
        )

    taps.sort(
        key=lambda item: item[0]
    )

    hold = _validate_action(
        obj.get("hold")
    )

    return GestureSpec(
        taps=tuple(taps),
        hold=hold,
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

    trigger = _validate_trigger(
        obj.get("trigger")
    )

    enabled = obj.get("enabled")

    if type(enabled) is not bool:
        raise ConfigError(
            "invalid_type",
            field="binding.enabled",
            expected="bool",
        )

    gestures = _validate_gestures(
        obj.get("gestures")
    )

    return Binding(
        trigger=trigger,
        enabled=enabled,
        gestures=gestures,
    )


def _validate_profile(
    name: str,
    data: Any,
) -> Profile:
    if (
        not isinstance(name, str)
        or not name.strip()
    ):
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
    seen_triggers: set[
        tuple[str, ...]
    ] = set()

    for raw_binding in raw_bindings:
        binding = _validate_binding(
            raw_binding
        )

        if (
            binding.trigger
            and binding.trigger
            in seen_triggers
        ):
            raise ConfigError(
                "duplicate_key",
                key=(
                    binding.trigger_display
                ),
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
        or version != CONFIG_VERSION
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
    enable_overlay = settings_obj.get(
        "enable_gesture_overlay"
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

    if type(enable_overlay) is not bool:
        raise ConfigError(
            "invalid_type",
            field="enable_gesture_overlay",
            expected="bool",
        )

    profiles_obj = _require_dict(
        data.get("profiles"),
        "profiles",
    )

    if not profiles_obj:
        raise ConfigError(
            "invalid_profile",
            profile="empty profile set",
        )

    if "default" not in profiles_obj:
        raise ConfigError(
            "invalid_profile",
            profile="missing default",
        )

    profiles = tuple(
        _validate_profile(
            name,
            profiles_obj[name],
        )
        for name in profiles_obj
    )

    return Config(
        version=CONFIG_VERSION,
        settings=Settings(
            double_tap_interval_ms=double_tap,
            hold_threshold_ms=hold_threshold,
            start_with_windows=start_with_windows,
            language=language,
            enable_gesture_overlay=enable_overlay,
        ),
        profiles=profiles,
    )


def _chord_action(
    *keys: str,
) -> ActionSpec:
    return ActionSpec(
        type="chord",
        keys=canonicalize_keys(keys),
    )


def _disabled_action() -> ActionSpec:
    return ActionSpec(
        type="disabled"
    )


def _default_binding() -> Binding:
    return Binding(
        trigger=(),
        enabled=True,
        gestures=GestureSpec(
            taps=(
                (1, _chord_action("F23")),
                (2, _chord_action("F24")),
                (3, _chord_action("F22")),
                (4, _chord_action("F21")),
            ),
            hold=_chord_action("F21"),
        ),
    )


def default_config() -> Config:
    binding = _default_binding()

    return Config(
        version=CONFIG_VERSION,
        settings=Settings(),
        profiles=(
            Profile(
                name="default",
                bindings=(binding,),
            ),
            Profile(
                name="Gaming",
                bindings=(binding,),
            ),
            Profile(
                name="Work",
                bindings=(binding,),
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
        "keys": list(action.keys),
    }


def _gestures_to_dict(
    gestures: GestureSpec,
) -> dict[str, Any]:
    return {
        "taps": {
            str(count): (
                _action_to_dict(action)
            )
            for count, action in (
                gestures.taps
            )
        },
        "hold": _action_to_dict(
            gestures.hold
        ),
    }


def _binding_to_dict(
    binding: Binding,
) -> dict[str, Any]:
    return {
        "trigger": _action_to_dict(
            ActionSpec(
                type="chord",
                keys=binding.trigger,
            )
        ),
        "enabled": binding.enabled,
        "gestures": _gestures_to_dict(
            binding.gestures
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
            "enable_gesture_overlay": (
                config.settings.enable_gesture_overlay
            ),
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
