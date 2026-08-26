"""Pure tap-gesture state machine (dynamic tap counts + hold)."""

from __future__ import annotations

import logging
import time
from enum import Enum, auto
from typing import Callable

from .config_models import MAX_TAP_COUNT


log = logging.getLogger(__name__)


class Gesture(Enum):
    SINGLE = auto()
    DOUBLE = auto()
    TRIPLE = auto()
    TAP4 = auto()
    TAP5 = auto()
    TAP6 = auto()
    TAP7 = auto()
    TAP8 = auto()
    TAP9 = auto()
    LONG = auto()


_GESTURE_FOR_COUNT: dict[int, Gesture] = {
    1: Gesture.SINGLE,
    2: Gesture.DOUBLE,
    3: Gesture.TRIPLE,
    4: Gesture.TAP4,
    5: Gesture.TAP5,
    6: Gesture.TAP6,
    7: Gesture.TAP7,
    8: Gesture.TAP8,
    9: Gesture.TAP9,
}


def gesture_for_count(
    count: int,
) -> Gesture:
    return _GESTURE_FOR_COUNT[count]


class _State(Enum):
    IDLE = auto()
    PRESSED = auto()
    WAITING = auto()
    LONG_DONE = auto()


class TapStateMachine:
    def __init__(
        self,
        trigger_key: str,
        double_tap_interval_ms: int,
        hold_threshold_ms: int,
        max_taps: int,
        on_gesture: Callable[[Gesture], None],
        on_error: Callable[[Exception], None] | None = None,
        tap_intervals: dict[int, int] | None = None,
        hold_override_ms: int | None = None,
    ) -> None:
        self.trigger_key = trigger_key
        self.double_tap_interval_ms = (
            double_tap_interval_ms
        )
        self.hold_threshold_ms = (
            hold_threshold_ms
        )

        # 每级连击自定义窗口（count -> ms），缺省用全局
        self.tap_intervals = (
            dict(tap_intervals)
            if tap_intervals
            else {}
        )
        # 长按自定义触发时间（None 用全局）
        self.hold_override_ms = (
            hold_override_ms
        )

        if not 1 <= max_taps <= MAX_TAP_COUNT:
            raise ValueError(
                f"max_taps out of range: {max_taps}"
            )

        self.max_taps = max_taps

        self._on_gesture = on_gesture
        self._on_error = (
            on_error
            or self._default_error_handler
        )

        self.reset()

    def _window_ms(
        self,
        count: int,
    ) -> int:
        """第 count 击的连击窗口（多少毫秒内按出下一击）。"""
        return self.tap_intervals.get(
            count,
            self.double_tap_interval_ms,
        )

    def _hold_ms(
        self,
    ) -> int:
        return (
            self.hold_override_ms
            if self.hold_override_ms is not None
            else self.hold_threshold_ms
        )

    @staticmethod
    def _default_error_handler(
        error: Exception,
    ) -> None:
        log.exception(
            "gesture handler failed: %s",
            error,
        )

    def reset(self) -> None:
        self._state = _State.IDLE
        self._down = False
        self._count = 0
        self._press_t = 0.0
        self._up_t = 0.0
        self._long_fired = False

    def on_key(
        self,
        key: str,
        is_down: bool,
        timestamp: float,
    ) -> None:
        if key != self.trigger_key:
            return

        if is_down:
            if self._down:
                return

            self._down = True
            self._handle_down(timestamp)
            return

        if not self._down:
            return

        self._down = False
        self._handle_up(timestamp)

    def check_timeouts(
        self,
        now: float | None = None,
    ) -> None:
        if now is None:
            now = time.monotonic()

        if (
            self._state == _State.PRESSED
            and self._down
            and not self._long_fired
        ):
            elapsed_ms = (
                now - self._press_t
            ) * 1000.0

            if elapsed_ms >= self._hold_ms():
                self._long_fired = True
                self._state = _State.LONG_DONE
                self._fire(Gesture.LONG)

            return

        if self._state == _State.WAITING:
            elapsed_ms = (
                now - self._up_t
            ) * 1000.0

            if (
                elapsed_ms
                >= self._window_ms(
                    self._count + 1
                )
            ):
                self._resolve_waiting()

    def _handle_down(
        self,
        now: float,
    ) -> None:
        if self._state == _State.WAITING:
            elapsed_ms = (
                now - self._up_t
            ) * 1000.0

            if (
                elapsed_ms
                < self._window_ms(
                    self._count + 1
                )
            ):
                self._count += 1
            else:
                self._resolve_waiting()
                self._count = 1

        else:
            self._count = 1

        self._state = _State.PRESSED
        self._press_t = now
        self._long_fired = False

    def _handle_up(
        self,
        now: float,
    ) -> None:
        if self._state == _State.LONG_DONE:
            self._state = _State.IDLE
            self._count = 0
            return

        if self._state != _State.PRESSED:
            return

        elapsed_ms = (
            now - self._press_t
        ) * 1000.0

        if (
            not self._long_fired
            and elapsed_ms >= self._hold_ms()
        ):
            self._state = _State.IDLE
            self._count = 0
            self._fire(Gesture.LONG)
            return

        if self._count >= self.max_taps:
            self._fire(
                gesture_for_count(
                    self._count
                )
            )
            self._state = _State.IDLE
            self._count = 0
            return

        self._up_t = now
        self._state = _State.WAITING

    def _resolve_waiting(self) -> None:
        if self._count <= 0:
            self._state = _State.IDLE
            return

        self._fire(
            gesture_for_count(
                self._count
            )
        )

        self._state = _State.IDLE
        self._count = 0

    def _fire(
        self,
        gesture: Gesture,
    ) -> None:
        try:
            self._on_gesture(gesture)
        except Exception as exc:
            try:
                self._on_error(exc)
            except Exception:
                log.exception(
                    "gesture error handler failed"
                )
