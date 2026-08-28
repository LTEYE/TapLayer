"""Immutable configuration model and strict validation (Schema v2).

Breaking change: the old ``modifier + key`` action model is gone.
Every action is a Chord (``{"type": "chord", "keys": [...]}``);
a single key is a chord of length 1. ``{"type": "disabled"}`` means
the gesture is unbound. Old v1 configuration files are NOT migrated.
"""

from __future__ import annotations

import logging
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


log = logging.getLogger(__name__)

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

# 时间参数的最小值（2026-08-28 修复：滑杆/配置可被调到极端值，
# 导致"单击变长按""双击被吞"等识别混乱；超范围值在加载时钳制）。
MIN_DOUBLE_TAP_INTERVAL_MS = 200
MIN_HOLD_THRESHOLD_MS = 300
MAX_DOUBLE_TAP_INTERVAL_MS = 1000
MAX_HOLD_THRESHOLD_MS = 5000

ACTION_FIELDS = {
    "type",
    "keys",
    "interval_ms",
    "hold_ms",
    # 输出行为（v2.1+）：缺省 = 点一下；长按手势缺省 = 按住 1 秒
    "output_mode",
    "repeat",
    "output_hold_ms",
}

GESTURE_FIELDS = {
    "taps",
    "hold",
}

BINDING_FIELDS = {
    "trigger",
    "enabled",
    "gestures",
    # 绑定自定义名（v2.1+）：弹窗/卡片显示用，空 = 默认显示触发键
    "name",
}

SETTINGS_FIELDS = {
    "double_tap_interval_ms",
    "hold_threshold_ms",
    "start_with_windows",
    "language",
    "enable_gesture_overlay",
    "theme",
    # 更新（v2.2+）：启动自动检查 / 自动下载安装
    "auto_check_update",
    "auto_update",
    # 实验：驱动级输出不带 cookie 标记（dwExtraInfo=0）。
    # 用于验证按 dwExtraInfo 过滤模拟键的目标应用（如豆包 IME）。
    # 注意：此时 TapLayer 自身钩子不再认领驱动输出，输出键与触发键
    # 有重叠的配置会形成自触发循环——仅实验时开启。
    "driver_output_cookieless",
}

THEMES = {
    "system",
    "dark",
    "light",
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
    # 触发参数（None = 使用全局值，旧配置向后兼容）：
    interval_ms: int | None = None  # 连击窗口：多少毫秒内按出下一击
    hold_ms: int | None = None  # 长按触发时间（仅 hold 手势使用）
    # 输出行为（v2.1+；None = 未显式设置）：
    #   tap                点一下（默认）
    #   repeat             触发后连点 N 下
    #   hold               按住 output_hold_ms 毫秒再松开
    #   hold_until_release 按住直到松开触发键
    # 长按手势在 output_mode 未设置时自动按 hold(1 秒) 处理。
    output_mode: str | None = None
    repeat: int = 1  # repeat 模式：连点次数
    output_hold_ms: int | None = None  # hold 模式：按住毫秒数（None = 默认 1000）


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
    # 自定义名（可空）：输出弹窗/绑定卡片显示用；空则回退触发键
    name: str = ""

    @property
    def trigger_display(self) -> str:
        return chord_display(
            self.trigger
        )

    @property
    def display_name(self) -> str:
        return (
            self.name
            or self.trigger_display
        )


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    bindings: tuple[Binding, ...] = ()
    # 输出后端：sendinput=标准注入；interception=驱动级注入（需已装 Interception）
    output_backend: str = "sendinput"


@dataclass(frozen=True, slots=True)
class Settings:
    double_tap_interval_ms: int = 250
    hold_threshold_ms: int = 500
    start_with_windows: bool = False
    language: str = "system"
    enable_gesture_overlay: bool = False
    theme: str = "system"
    # 更新（v2.2+）：启动自动检查 / 自动下载安装
    auto_check_update: bool = False
    auto_update: bool = False
    # 实验：驱动级输出不带 cookie 标记（默认关闭，见 SETTINGS_FIELDS 注释）
    driver_output_cookieless: bool = False


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


def _parse_optional_int(
    obj: dict[str, Any],
    field: str,
    lo: int,
    hi: int,
) -> int | None:
    value = obj.get(field)

    if value is None:
        return None

    if type(value) is not int:
        raise ConfigError(
            "invalid_type",
            field=field,
            expected="int",
        )

    if not lo <= value <= hi:
        # 超范围值不再拒绝（拒绝会让旧配置整个加载失败），
        # 而是钳制到边界并警告——识别参数必须落在合理区间，
        # 否则"单击变长按/双击被吞"会反复出现。
        clamped = max(lo, min(hi, value))

        log.warning(
            "config field %s=%s out of range [%s, %s]; "
            "clamped to %s",
            field,
            value,
            lo,
            hi,
            clamped,
        )

        return clamped

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

    interval_ms = _parse_optional_int(
        obj,
        "interval_ms",
        MIN_DOUBLE_TAP_INTERVAL_MS,
        MAX_DOUBLE_TAP_INTERVAL_MS,
    )
    hold_ms = _parse_optional_int(
        obj,
        "hold_ms",
        MIN_HOLD_THRESHOLD_MS,
        MAX_HOLD_THRESHOLD_MS,
    )

    # v2.1+：输出行为（缺省 None = 未显式设置）
    output_mode = obj.get("output_mode")

    if (
        output_mode is not None
        and output_mode
        not in {
            "tap",
            "repeat",
            "hold",
            "hold_until_release",
        }
    ):
        raise ConfigError(
            "invalid_type",
            field="action.output_mode",
            expected=(
                "tap|repeat|hold|hold_until_release"
            ),
        )

    repeat = _parse_optional_int(
        obj,
        "repeat",
        1,
        99,
    )

    output_hold_ms = _parse_optional_int(
        obj,
        "output_hold_ms",
        50,
        60000,
    )

    return ActionSpec(
        type="chord",
        keys=canonical,
        interval_ms=interval_ms,
        hold_ms=hold_ms,
        output_mode=output_mode,
        repeat=(
            repeat
            if repeat is not None
            else 1
        ),
        output_hold_ms=output_hold_ms,
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

    name = obj.get(
        "name",
        "",
    )

    if name is None:
        name = ""

    if not isinstance(
        name,
        str,
    ):
        raise ConfigError(
            "invalid_type",
            field="binding.name",
            expected="string",
        )

    if len(name) > 60:
        raise ConfigError(
            "invalid_type",
            field="binding.name",
            expected="<=60 chars",
        )

    return Binding(
        trigger=trigger,
        enabled=enabled,
        gestures=gestures,
        name=name.strip(),
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
        {"bindings", "output_backend"},
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

    # 输出后端：未知值不拒绝（拒绝会让旧配置整个加载失败），钳到默认并警告
    output_backend = obj.get("output_backend", "sendinput")

    if output_backend is None:
        output_backend = "sendinput"

    if output_backend not in ("sendinput", "interception"):
        log.warning(
            "profile %s: unknown output_backend %r; "
            "falling back to sendinput",
            name,
            output_backend,
        )
        output_backend = "sendinput"

    return Profile(
        name=name,
        bindings=tuple(bindings),
        output_backend=output_backend,
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
    theme = settings_obj.get(
        "theme"
    )
    # v2.2+：更新设置；旧配置没有时默认关闭
    auto_check_update = settings_obj.get(
        "auto_check_update"
    )
    auto_update = settings_obj.get(
        "auto_update"
    )

    if theme is None:
        # 旧配置没有 theme 字段：默认 system，向后兼容
        theme = "system"

    if auto_check_update is None:
        auto_check_update = False

    if auto_update is None:
        auto_update = False

    # 实验字段：旧配置没有时默认关闭；类型错误不拒绝整个配置
    driver_output_cookieless = settings_obj.get(
        "driver_output_cookieless"
    )

    if driver_output_cookieless is None:
        driver_output_cookieless = False

    if type(driver_output_cookieless) is not bool:
        log.warning(
            "settings.driver_output_cookieless "
            "must be bool; got %r, using False",
            driver_output_cookieless,
        )
        driver_output_cookieless = False

    if type(double_tap) is not int:
        raise ConfigError(
            "invalid_type",
            field="double_tap_interval_ms",
            expected="int",
        )

    if double_tap < MIN_DOUBLE_TAP_INTERVAL_MS or (
        double_tap > MAX_DOUBLE_TAP_INTERVAL_MS
    ):
        double_tap = max(
            MIN_DOUBLE_TAP_INTERVAL_MS,
            min(MAX_DOUBLE_TAP_INTERVAL_MS, double_tap),
        )

        log.warning(
            "double_tap_interval_ms clamped to %s",
            double_tap,
        )

    if type(hold_threshold) is not int:
        raise ConfigError(
            "invalid_type",
            field="hold_threshold_ms",
            expected="int",
        )

    if hold_threshold < MIN_HOLD_THRESHOLD_MS or (
        hold_threshold > MAX_HOLD_THRESHOLD_MS
    ):
        hold_threshold = max(
            MIN_HOLD_THRESHOLD_MS,
            min(MAX_HOLD_THRESHOLD_MS, hold_threshold),
        )

        log.warning(
            "hold_threshold_ms clamped to %s",
            hold_threshold,
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

    if type(auto_check_update) is not bool:
        raise ConfigError(
            "invalid_type",
            field="auto_check_update",
            expected="bool",
        )

    if type(auto_update) is not bool:
        raise ConfigError(
            "invalid_type",
            field="auto_update",
            expected="bool",
        )

    if theme not in THEMES:
        raise ConfigError(
            "invalid_type",
            field="theme",
            expected="system|dark|light",
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
            theme=theme,
            auto_check_update=auto_check_update,
            auto_update=auto_update,
            driver_output_cookieless=driver_output_cookieless,
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


def _default_binding(
    trigger: tuple[str, ...],
    tap2: tuple[str, ...] | None = None,
    hold: tuple[str, ...] | None = None,
) -> Binding:
    """默认绑定：低频键触发，单击停用（无动作），双击/长按映射输出。

    触发键必须是低频键（ScrollLock/Pause/Insert 等）——触发键按下
    会被程序接管（等待单击/双击/长按判定），不能透传给系统，因此
    Ctrl/Alt/Shift 这类高频键当触发键会导致其组合键全部失效。
    """
    taps: list[tuple[int, ActionSpec]] = [
        (
            1,
            _disabled_action(),
        ),
    ]

    if tap2 is not None:
        taps.append(
            (
                2,
                _chord_action(
                    *tap2
                ),
            )
        )

    gestures = GestureSpec(
        taps=tuple(taps),
        hold=(
            _chord_action(
                *hold
            )
            if hold is not None
            else _disabled_action()
        ),
    )

    return Binding(
        trigger=canonicalize_keys(
            trigger
        ),
        enabled=True,
        gestures=gestures,
    )


def default_config() -> Config:
    # 出厂默认：三档实用配置（低频键触发，零干扰）。
    return Config(
        version=CONFIG_VERSION,
        settings=Settings(),
        profiles=(
            Profile(
                name="default",
                bindings=(
                    # 日常：复制粘贴
                    _default_binding(
                        ("ScrollLock",),
                        tap2=(
                            "Ctrl",
                            "C",
                        ),
                        hold=(
                            "Ctrl",
                            "V",
                        ),
                    ),
                    # 日常：撤销重做
                    _default_binding(
                        ("Insert",),
                        tap2=(
                            "Ctrl",
                            "Z",
                        ),
                        hold=(
                            "Ctrl",
                            "Y",
                        ),
                    ),
                ),
            ),
            Profile(
                name="Gaming",
                bindings=(
                    # 游戏：背包 / 地图
                    _default_binding(
                        ("ScrollLock",),
                        tap2=("B",),
                        hold=("M",),
                    ),
                    # 游戏：换弹 / 交互
                    _default_binding(
                        ("Pause",),
                        tap2=("R",),
                        hold=("F",),
                    ),
                ),
            ),
            Profile(
                name="Work",
                bindings=(
                    # 工作：保存 / 关闭
                    _default_binding(
                        ("Pause",),
                        tap2=(
                            "Ctrl",
                            "S",
                        ),
                        hold=(
                            "Ctrl",
                            "W",
                        ),
                    ),
                    # 工作：查找 / 继续查找
                    _default_binding(
                        ("Insert",),
                        tap2=(
                            "Ctrl",
                            "F",
                        ),
                        hold=(
                            "Ctrl",
                            "G",
                        ),
                    ),
                ),
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
    data: dict[str, Any] = {
        "type": action.type,
        "keys": list(action.keys),
    }

    if action.interval_ms is not None:
        data["interval_ms"] = (
            action.interval_ms
        )

    if action.hold_ms is not None:
        data["hold_ms"] = (
            action.hold_ms
        )

    if action.output_mode is not None:
        data["output_mode"] = (
            action.output_mode
        )

        if (
            action.output_mode == "repeat"
            and action.repeat > 1
        ):
            data["repeat"] = (
                action.repeat
            )

        if (
            action.output_mode == "hold"
            and action.output_hold_ms is not None
        ):
            data["output_hold_ms"] = (
                action.output_hold_ms
            )

    return data


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
    data: dict[str, Any] = {
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

    if binding.name:
        data["name"] = binding.name

    return data


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
            "theme": config.settings.theme,
            "auto_check_update": (
                config.settings.auto_check_update
            ),
            "auto_update": (
                config.settings.auto_update
            ),
            "driver_output_cookieless": (
                config.settings.driver_output_cookieless
            ),
        },
        "profiles": {
            profile.name: {
                "output_backend": profile.output_backend,
                "bindings": [
                    _binding_to_dict(binding)
                    for binding in profile.bindings
                ]
            }
            for profile in config.profiles
        },
    }
