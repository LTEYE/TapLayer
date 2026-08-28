"""Cross-platform backend contracts (Chord-based)."""

from __future__ import annotations

from dataclasses import dataclass
from queue import SimpleQueue
from typing import Callable, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RawKeyEvent:
    key: str
    is_down: bool
    injected: bool
    timestamp: float


@dataclass(frozen=True, slots=True)
class CaptureResult:
    kind: str
    key: str | None = None


@runtime_checkable
class KeyboardBackend(Protocol):
    events: SimpleQueue

    def start(self) -> bool:
        ...

    def stop(self) -> None:
        ...

    def begin_capture(self) -> None:
        ...

    def cancel_capture(self) -> None:
        ...

    def poll_capture_result(self) -> CaptureResult | None:
        ...

    def set_trigger_chords(
        self,
        chords: frozenset[tuple[str, ...]],
    ) -> None:
        ...

    def set_enabled(self, enabled: bool) -> None:
        ...


@runtime_checkable
class InputBackend(Protocol):
    def tap_key(self, key: str) -> None:
        ...

    def tap_chord(
        self,
        keys: tuple[str, ...],
        hold_ms: int | None = None,
    ) -> None:
        """输出一个 chord。hold_ms=None 为正常点按；
        hold_ms=N 为按住 N 毫秒后再松开。"""

    def hold_chord_until(
        self,
        keys: tuple[str, ...],
    ) -> Callable[[], None]:
        """按住一个 chord 并保持，返回"释放"回调（幂等，可多次调用）。"""


@runtime_checkable
class StartupBackend(Protocol):
    def is_available(self) -> bool:
        ...

    def get_startup(self) -> bool:
        ...

    def set_startup(self, enabled: bool) -> None:
        ...
