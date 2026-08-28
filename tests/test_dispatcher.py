from multitapkey.core.actions import (
    Action,
    ActionDispatcher,
)


def make():
    sent = []
    held = []

    def chord(keys, hold_ms=None):
        entry = tuple(keys)

        if hold_ms is not None:
            entry = entry + (hold_ms,)

        sent.append(entry)

    def hold_until(keys):
        entry = tuple(keys)
        held.append(entry)

        state = {"done": False}

        def release():
            if state["done"]:
                return

            state["done"] = True

            try:
                held.remove(entry)
            except ValueError:
                pass

        return release

    dispatcher = ActionDispatcher(
        chord=chord,
        hold_until=hold_until,
    )

    return dispatcher, sent, held


def test_disabled_calls_nothing():
    dispatcher, sent, _ = make()

    dispatcher.execute(
        Action(kind="disabled")
    )

    assert sent == []


def test_chord_calls_chord():
    dispatcher, sent, _ = make()

    dispatcher.execute(
        Action(
            kind="chord",
            keys=("Ctrl", "A"),
        )
    )

    assert sent == [("Ctrl", "A")]


def test_empty_chord_calls_nothing():
    dispatcher, sent, _ = make()

    dispatcher.execute(
        Action(kind="chord")
    )

    assert sent == []


def test_repeat_calls_chord_n_times():
    dispatcher, sent, _ = make()

    dispatcher.execute(
        Action(
            kind="chord",
            keys=("F24",),
            output_mode="repeat",
            repeat=3,
        )
    )

    assert sent == [
        ("F24",),
        ("F24",),
        ("F24",),
    ]


def test_hold_calls_chord_with_ms():
    dispatcher, sent, _ = make()

    dispatcher.execute(
        Action(
            kind="chord",
            keys=("F24",),
            output_mode="hold",
            hold_ms=2000,
        )
    )

    assert sent == [("F24", 2000)]


def test_hold_until_release_returns_release():
    dispatcher, sent, held = make()

    release = dispatcher.execute(
        Action(
            kind="chord",
            keys=("F24",),
            output_mode="hold_until_release",
        )
    )

    assert held == [("F24",)]
    assert release is not None

    # 释放后 held 清空；重复释放幂等
    release()
    release()

    assert held == []
