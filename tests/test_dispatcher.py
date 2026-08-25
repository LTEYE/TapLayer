from multitapkey.core.actions import (
    Action,
    ActionDispatcher,
)


def test_disabled_calls_nothing():
    calls = []

    dispatcher = ActionDispatcher(
        tap=lambda *args: calls.append(
            ("tap", args)
        ),
        combo=lambda *args: calls.append(
            ("combo", args)
        ),
    )

    dispatcher.execute(
        Action(
            kind="disabled"
        )
    )

    assert calls == []


def test_key_calls_tap():
    calls = []

    dispatcher = ActionDispatcher(
        tap=lambda *args: calls.append(
            ("tap", args)
        ),
        combo=lambda *args: calls.append(
            ("combo", args)
        ),
    )

    dispatcher.execute(
        Action(
            kind="key",
            key="F23",
        )
    )

    assert calls == [
        ("tap", ("F23",))
    ]


def test_combo_calls_combo():
    calls = []

    dispatcher = ActionDispatcher(
        tap=lambda *args: calls.append(
            ("tap", args)
        ),
        combo=lambda *args: calls.append(
            ("combo", args)
        ),
    )

    dispatcher.execute(
        Action(
            kind="key",
            key="S",
            modifiers=(
                "Ctrl",
                "Shift",
            ),
        )
    )

    assert calls == [
        (
            "combo",
            (
                (
                    "Ctrl",
                    "Shift",
                ),
                "S",
            ),
        )
    ]
