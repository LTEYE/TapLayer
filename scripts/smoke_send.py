import time

from multitapkey.platform.windows.send_input import (
    WindowsInputBackend,
)


def main():
    backend = (
        WindowsInputBackend()
    )

    print(
        "F23 injection starts in 3 seconds..."
    )

    for value in (
        3,
        2,
        1,
    ):
        print(value)
        time.sleep(1)

    backend.tap_key(
        "F23"
    )

    print(
        "F23 injection completed."
    )


if __name__ == "__main__":
    main()
