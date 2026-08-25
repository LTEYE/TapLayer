import queue
import sys
import time

from multitapkey.platform.windows.keyboard_hook import (
    WindowsKeyboardBackend,
)


def main():
    backend = (
        WindowsKeyboardBackend()
    )

    if not backend.start():
        print(
            "Hook initialization failed:",
            backend.init_error,
        )
        sys.exit(1)

    backend.set_trigger_keys(
        frozenset(
            {"F24"}
        )
    )

    backend.set_enabled(
        True
    )

    print(
        "Listening for F24 for 15 seconds."
    )

    print(
        "F24 is suppressed "
        "system-wide while this test runs."
    )

    deadline = (
        time.monotonic()
        + 15
    )

    try:
        while (
            time.monotonic()
            < deadline
        ):
            try:
                event = (
                    backend.events.get(
                        timeout=0.2
                    )
                )

            except queue.Empty:
                continue

            print(
                "DOWN"
                if event.is_down
                else "UP",
                event.key,
            )

    finally:
        backend.stop()


if __name__ == "__main__":
    main()
