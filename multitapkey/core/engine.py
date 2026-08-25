"""Platform-independent runtime engine."""

from __future__ import annotations

import logging
import queue

from multitapkey.platform.base import (
    InputBackend,
    KeyboardBackend,
)

from .actions import (
    Action,
    ActionDispatcher,
)
from .config_models import (
    ActionSpec,
    Config,
    Binding,
    get_profile,
)
from .state_machine import (
    Gesture,
    TapStateMachine,
)


log = logging.getLogger(__name__)

_GESTURE_ATTR = {
    Gesture.SINGLE: "single",
    Gesture.DOUBLE: "double",
    Gesture.TRIPLE: "triple",
    Gesture.LONG: "long",
}


def _action_from_spec(
    spec: ActionSpec,
) -> Action:
    if spec.type != "key":
        return Action(
            kind="disabled"
        )

    return Action(
        kind="key",
        key=spec.key,
        modifiers=spec.modifiers,
    )


class Engine:
    def __init__(
        self,
        keyboard_backend: KeyboardBackend,
        input_backend: InputBackend,
    ) -> None:
        self.backend = keyboard_backend

        self._dispatcher = ActionDispatcher(
            tap=input_backend.tap_key,
            combo=input_backend.tap_combo,
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

        self.backend.set_trigger_keys(
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

        for binding in profile.bindings:
            if not binding.enabled:
                continue

            key = binding.trigger

            new_machines[key] = (
                TapStateMachine(
                    trigger_key=key,
                    double_tap_interval_ms=interval,
                    hold_threshold_ms=hold,
                    on_gesture=(
                        lambda gesture,
                        trigger=key:
                        self._dispatch(
                            trigger,
                            gesture,
                        )
                    ),
                )
            )

            new_bindings[key] = binding

        new_trigger_keys = frozenset(
            new_machines
        )

        self.backend.set_trigger_keys(
            new_trigger_keys
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
        trigger_key: str,
        gesture: Gesture,
    ) -> None:
        binding = self._bindings.get(
            trigger_key
        )

        if binding is None:
            return

        action_spec = getattr(
            binding,
            _GESTURE_ATTR[gesture],
        )

        self.execute_action_spec(
            action_spec
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
