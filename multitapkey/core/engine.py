"""Platform-independent runtime engine (Chord-based)."""

from __future__ import annotations

import logging
import queue
import time
from typing import Callable

from multitapkey.platform.base import (
    InputBackend,
    KeyboardBackend,
)

from .actions import (
    Action,
    ActionDispatcher,
)
from .chord import (
    chord_display,
)
from .config_models import (
    ActionSpec,
    Binding,
    Config,
    GestureSpec,
    get_profile,
)
from .state_machine import (
    Gesture,
    TapStateMachine,
    gesture_for_count,
)


log = logging.getLogger(__name__)

# 长按手势未显式设置输出行为时，自动"按住输出键"的默认时长（毫秒）
_DEFAULT_HOLD_OUTPUT_MS = 1000

# Gesture -> tap count
_TAP_COUNT_FOR_GESTURE: dict[
    Gesture,
    int,
] = {
    Gesture.SINGLE: 1,
    Gesture.DOUBLE: 2,
    Gesture.TRIPLE: 3,
    Gesture.TAP4: 4,
    Gesture.TAP5: 5,
    Gesture.TAP6: 6,
    Gesture.TAP7: 7,
    Gesture.TAP8: 8,
    Gesture.TAP9: 9,
}


def _action_from_spec(
    spec: ActionSpec,
    *,
    is_long: bool = False,
) -> Action:
    if spec.type != "chord":
        return Action(
            kind="disabled"
        )

    # 输出行为未显式设置：长按手势自动变长按（按住 1 秒），
    # 其余手势点一下。
    output_mode = spec.output_mode

    if output_mode is None:
        output_mode = (
            "hold"
            if is_long
            else "tap"
        )

    hold_ms = spec.output_hold_ms

    if (
        output_mode == "hold"
        and hold_ms is None
    ):
        hold_ms = _DEFAULT_HOLD_OUTPUT_MS

    return Action(
        kind="chord",
        keys=spec.keys,
        output_mode=output_mode,
        repeat=(
            spec.repeat
            if spec.repeat
            else 1
        ),
        hold_ms=hold_ms,
    )


class Engine:
    def __init__(
        self,
        keyboard_backend: KeyboardBackend,
        input_backend: InputBackend,
    ) -> None:
        self.backend = keyboard_backend

        self._dispatcher = ActionDispatcher(
            chord=input_backend.tap_chord,
            hold_until=(
                input_backend.hold_chord_until
            ),
        )

        # "按住直到松开触发键"的活动输出：trigger_display -> release()
        self._hold_map: dict[
            str,
            Callable[[], None],
        ] = {}

        self._machines: dict[
            str,
            TapStateMachine,
        ] = {}

        self._bindings: dict[
            str,
            Binding,
        ] = {}

        self._config: Config | None = None

        self._profile_name = "default"

        self._backend_started = False
        # 钩子自愈检查计时（每 60 秒请求重装一次，防系统静默拔钩）
        self._last_rehook_check = 0.0
        self._config_loaded = False
        self._paused = False
        self._active = False

        # OSD 观察者（独立于核心识别逻辑；默认 None）
        self._gesture_observer: (
            Callable[
                [str, str],
                None,
            ]
            | None
        ) = None

    def start(self) -> bool:
        if self._backend_started:
            return True

        ok = self.backend.start()

        if not ok:
            log.error(
                "keyboard backend initialization failed: %s",
                getattr(
                    self.backend,
                    "init_error",
                    "unknown",
                ),
            )
            self._backend_started = False
            self._active = False
            return False

        self._backend_started = True
        self.backend.set_enabled(False)
        self._active = False

        return True

    def shutdown(self) -> None:
        self._active = False
        self.backend.set_enabled(False)

        self._release_all_holds()

        for machine in self._machines.values():
            machine.reset()

        self._machines = {}
        self._bindings = {}

        self.backend.set_trigger_chords(
            frozenset()
        )

        self.backend.stop()

        self._backend_started = False
        self._config_loaded = False

    @property
    def config(
        self,
    ) -> Config | None:
        return self._config

    @property
    def profile_name(
        self,
    ) -> str:
        return self._profile_name

    @property
    def backend_started(
        self,
    ) -> bool:
        return self._backend_started

    @property
    def config_loaded(
        self,
    ) -> bool:
        return self._config_loaded

    @property
    def paused(
        self,
    ) -> bool:
        return self._paused

    @property
    def active(
        self,
    ) -> bool:
        return self._active

    @property
    def hook_failed(
        self,
    ) -> bool:
        return not self._backend_started

    def set_gesture_observer(
        self,
        observer: Callable[
            [str, str],
            None,
        ]
        | None,
    ) -> None:
        self._gesture_observer = observer

    def apply_config(
        self,
        config: Config,
        profile_name: str | None = None,
    ) -> None:
        name = (
            profile_name
            if profile_name is not None
            else self._profile_name
        )

        profile = get_profile(
            config,
            name,
        )

        interval = (
            config.settings.double_tap_interval_ms
        )

        hold = (
            config.settings.hold_threshold_ms
        )

        new_machines: dict[
            str,
            TapStateMachine,
        ] = {}

        new_bindings: dict[
            str,
            Binding,
        ] = {}

        trigger_chords: set[
            tuple[str, ...]
        ] = set()

        self._release_all_holds()

        for binding in profile.bindings:
            if not binding.enabled:
                continue

            if not binding.trigger:
                # 触发键未设置（"选择热键"状态）：跳过
                continue

            display = (
                binding.trigger_display
            )

            max_taps = (
                binding.gestures.max_taps
            )

            if max_taps < 1:
                continue

            # 每级连击自定义窗口（缺省用全局）
            tap_intervals: dict[int, int] = {}

            for tap_count, tap_action in (
                binding.gestures.taps
            ):
                if (
                    tap_action.interval_ms
                    is not None
                ):
                    tap_intervals[tap_count] = (
                        tap_action.interval_ms
                    )

            hold_override = (
                binding.gestures.hold.hold_ms
            )

            new_machines[display] = (
                TapStateMachine(
                    trigger_key=display,
                    double_tap_interval_ms=interval,
                    hold_threshold_ms=hold,
                    max_taps=max_taps,
                    on_gesture=(
                        lambda gesture,
                        trig=display:
                        self._dispatch(
                            trig,
                            gesture,
                        )
                    ),
                    tap_intervals=(
                        tap_intervals
                        or None
                    ),
                    hold_override_ms=(
                        hold_override
                    ),
                )
            )

            new_bindings[display] = binding

            trigger_chords.add(
                binding.trigger
            )

        self.backend.set_trigger_chords(
            frozenset(trigger_chords)
        )

        for machine in self._machines.values():
            machine.reset()

        self._machines = new_machines
        self._bindings = new_bindings
        self._config = config
        self._profile_name = name
        self._config_loaded = True

        if (
            self._backend_started
            and not self._paused
        ):
            self.backend.set_enabled(
                True
            )
            self._active = True
        else:
            self.backend.set_enabled(
                False
            )
            self._active = False

    def set_profile(
        self,
        name: str,
    ) -> None:
        if self._config is None:
            return

        self.apply_config(
            self._config,
            name,
        )

    def pause(self) -> None:
        self._paused = True
        self._active = False

        self.backend.set_enabled(
            False
        )

        self._release_all_holds()

        for machine in self._machines.values():
            machine.reset()

        self._drain_queue()

    def resume(self) -> None:
        if not (
            self._backend_started
            and self._config_loaded
        ):
            self._active = False
            return

        self._paused = False
        self.backend.set_enabled(
            True
        )
        self._active = True

    def cancel_pending(self) -> None:
        for machine in self._machines.values():
            machine.reset()

        self._release_all_holds()

        self._drain_queue()

    def _release_all_holds(self) -> None:
        for release in self._hold_map.values():
            try:
                release()
            except Exception:
                log.exception(
                    "failed to release held output"
                )

        self._hold_map.clear()

    def pump(self) -> None:
        if not self._active:
            self._drain_queue()
            return

        try:
            while True:
                event = (
                    self.backend.events.get_nowait()
                )

                # 触发键松开：释放"按住直到松开触发键"的输出
                if not event.is_down:
                    release = (
                        self._hold_map.pop(
                            event.key,
                            None,
                        )
                    )

                    if release is not None:
                        try:
                            release()
                        except Exception:
                            log.exception(
                                "failed to release held output"
                            )

                machine = (
                    self._machines.get(
                        event.key
                    )
                )

                if machine is not None:
                    machine.on_key(
                        event.key,
                        event.is_down,
                        event.timestamp,
                    )

        except queue.Empty:
            pass

        for machine in self._machines.values():
            machine.check_timeouts()

        # 钩子自愈：Windows 可能因回调超时静默移除低层钩子
        # （间歇性失效），定期请求重装。有按键按住时 backend 会跳过。
        now = time.monotonic()

        if (
            now - self._last_rehook_check
            >= 60.0
        ):
            self._last_rehook_check = now

            rehook = getattr(
                self.backend,
                "rehook",
                None,
            )

            if rehook is not None:
                try:
                    rehook()
                except Exception:
                    pass

    def _drain_queue(self) -> None:
        try:
            while True:
                self.backend.events.get_nowait()
        except queue.Empty:
            return

    def _dispatch(
        self,
        trigger_display: str,
        gesture: Gesture,
    ) -> None:
        binding = self._bindings.get(
            trigger_display
        )

        if binding is None:
            return

        if gesture == Gesture.LONG:
            self._notify_observer(
                binding,
                binding.gestures.hold,
            )
            self.execute_action_spec(
                binding.gestures.hold,
                is_long=True,
                trigger_display=(
                    trigger_display
                ),
            )
            return

        count = _TAP_COUNT_FOR_GESTURE.get(
            gesture
        )

        if count is None:
            return

        action_spec = self._tap_action(
            binding.gestures,
            count,
        )

        if action_spec is not None:
            self._notify_observer(
                binding,
                action_spec,
            )
            self.execute_action_spec(
                action_spec,
                is_long=False,
                trigger_display=(
                    trigger_display
                ),
            )

    @staticmethod
    def _tap_action(
        gestures: GestureSpec,
        count: int,
    ) -> ActionSpec | None:
        for tap_count, action in (
            gestures.taps
        ):
            if tap_count == count:
                return action

        return None

    def _notify_observer(
        self,
        binding: Binding,
        action_spec: ActionSpec,
    ) -> None:
        if self._gesture_observer is None:
            return

        if action_spec.type != "chord":
            return

        try:
            # 弹窗内容 = "绑定显示名: 输出动作"
            # 绑定显示名 = 自定义名（有则用），否则触发键
            self._gesture_observer(
                f"{binding.display_name}: "
                f"{chord_display(action_spec.keys)}"
            )
        except Exception:
            log.exception(
                "gesture observer failed"
            )

    def execute_action_spec(
        self,
        spec: ActionSpec,
        *,
        is_long: bool = False,
        trigger_display: str | None = None,
    ) -> None:
        action = _action_from_spec(
            spec,
            is_long=is_long,
        )

        # 调试用：触发键、手势、输出模式、输出键、按住时长
        log.info(
            "dispatch: trigger=%s gesture=%s "
            "mode=%s keys=%s hold_ms=%s",
            trigger_display,
            "long" if is_long else "tap",
            action.output_mode,
            action.keys,
            action.hold_ms,
        )

        try:
            if (
                action.output_mode
                == "hold_until_release"
                and trigger_display
            ):
                # 按住直到松开触发键：记录释放回调，触发键松开时释放
                release = (
                    self._dispatcher.execute(
                        action
                    )
                )

                if release is not None:
                    self._hold_map[
                        trigger_display
                    ] = release
            else:
                self._dispatcher.execute(
                    action
                )
        except Exception:
            log.exception(
                "action execution failed"
            )
