"""Core action model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class Action:
    kind: str
    key: str | None = None
    modifiers: tuple[str, ...] = ()


NO_ACTION = Action(
    kind="disabled"
)


class ActionDispatcher:
    def __init__(
        self,
        tap: Callable[[str], None],
        combo: Callable[
            [tuple[str, ...], str],
            None,
        ],
    ) -> None:
        self._tap = tap
        self._combo = combo

    def execute(
        self,
        action: Action,
    ) -> None:
        if action.kind != "key":
            return

        if action.key is None:
            return

        if action.modifiers:
            self._combo(
                action.modifiers,
                action.key,
            )
        else:
            self._tap(action.key)
