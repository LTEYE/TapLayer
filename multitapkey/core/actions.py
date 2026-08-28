"""Core action model (Chord-based)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

# 连点输出时每次点按之间的间隔（秒）：太短目标应用可能识别成一次，
# 太长又不像"连点"。
_REPEAT_INTERVAL_SECONDS = 0.08


@dataclass(frozen=True, slots=True)
class Action:
    kind: str  # "chord" | "disabled"
    keys: tuple[str, ...] = ()
    # 输出行为：tap（点一下）/ repeat（连点 N 下）/
    # hold（按住 hold_ms 毫秒）/ hold_until_release（按住直到松开触发键）
    output_mode: str = "tap"
    repeat: int = 1
    hold_ms: int | None = None


NO_ACTION = Action(
    kind="disabled"
)


class ActionDispatcher:
    def __init__(
        self,
        chord: Callable[
            [tuple[str, ...], int | None],
            None,
        ],
        hold_until: Callable[
            [tuple[str, ...]],
            Callable[[], None],
        ],
    ) -> None:
        self._chord = chord
        self._hold_until = hold_until

    def execute(
        self,
        action: Action,
    ) -> Callable[[], None] | None:
        """执行动作。

        hold_until_release 模式返回"释放"回调（调用方在触发键松开时调用），
        其余模式返回 None。
        """
        if action.kind != "chord":
            return None

        if not action.keys:
            return None

        if action.output_mode == "repeat":
            count = max(1, action.repeat)

            for index in range(count):
                self._chord(
                    action.keys,
                    None,
                )

                if index < count - 1:
                    time.sleep(
                        _REPEAT_INTERVAL_SECONDS
                    )

            return None

        if action.output_mode == "hold":
            self._chord(
                action.keys,
                action.hold_ms,
            )
            return None

        if action.output_mode == "hold_until_release":
            return self._hold_until(
                action.keys
            )

        # tap（默认）：点一下
        self._chord(
            action.keys,
            None,
        )
        return None
