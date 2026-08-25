"""Cross-platform backend contracts."""

from __future__ import annotations

from dataclasses import dataclass
from queue import SimpleQueue
from typing import Protocol, runtime_checkable


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

    def set_trigger_keys(self, keys: frozenset[str]) -> None:
        ...

    def set_enabled(self, enabled: bool) -> None:
        ...


@runtime_checkable
class InputBackend(Protocol):
    def tap_key(self, key: str) -> None:
        ...

    def tap_combo(
        self,
        modifier_keys: tuple[str, ...],
        key: str,
    ) -> None:
        ...


@runtime_checkable
class StartupBackend(Protocol):
    def is_available(self) -> bool:
        ...

    def get_startup(self) -> bool:
        ...

    def set_startup(self, enabled: bool) -> None:
        ...
