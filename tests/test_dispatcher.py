from multitapkey.core.actions import (
    Action,
    ActionDispatcher,
)


def make():
    sent = []

    dispatcher = ActionDispatcher(
        chord=lambda keys: sent.append(keys)
    )

    return dispatcher, sent


def test_disabled_calls_nothing():
    dispatcher, sent = make()

    dispatcher.execute(
        Action(kind="disabled")
    )

    assert sent == []


def test_chord_calls_chord():
    dispatcher, sent = make()

    dispatcher.execute(
        Action(
            kind="chord",
            keys=("Ctrl", "A"),
        )
    )

    assert sent == [("Ctrl", "A")]


def test_empty_chord_calls_nothing():
    dispatcher, sent = make()

    dispatcher.execute(
        Action(kind="chord")
    )

    assert sent == []
