"""Platform-independent runtime engine (Chord-based)."""

from __future__ import annotations

import logging
import queue
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
) -> Action:
    if spec.type != "chord":
        return Action(
            kind="disabled"
        )

    return Action(
        kind="chord",
        keys=spec.keys,
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
        )

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

        self._drain_queue()

    def pump(self) -> None:
        if not self._active:
            self._drain_queue()
            return

        try:
            while True:
                event = (
                    self.backend.events.get_nowait()
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
                binding.gestures.hold
            )
            self.execute_action_spec(
                binding.gestures.hold
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
                action_spec
            )
            self.execute_action_spec(
                action_spec
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
        action_spec: ActionSpec,
    ) -> None:
        if self._gesture_observer is None:
            return

        if action_spec.type != "chord":
            return

        try:
            self._gesture_observer(
                chord_display(
                    action_spec.keys
                )
            )
        except Exception:
            log.exception(
                "gesture observer failed"
            )

    def execute_action_spec(
        self,
        spec: ActionSpec,
    ) -> None:
        action = _action_from_spec(
            spec
        )

        try:
            self._dispatcher.execute(
                action
            )
        except Exception:
            log.exception(
                "action execution failed"
            )
