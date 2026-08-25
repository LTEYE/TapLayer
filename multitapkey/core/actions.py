"""Core action model (Chord-based)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class Action:
    kind: str  # "chord" | "disabled"
    keys: tuple[str, ...] = ()


NO_ACTION = Action(
    kind="disabled"
)


class ActionDispatcher:
    def __init__(
        self,
        chord: Callable[
            [tuple[str, ...]],
            None,
        ],
    ) -> None:
        self._chord = chord

    def execute(
        self,
        action: Action,
    ) -> None:
        if action.kind != "chord":
            return

        if not action.keys:
            return

        self._chord(action.keys)
