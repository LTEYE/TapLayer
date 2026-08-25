"""In-app usage guide dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from multitapkey.i18n.manager import I18nManager


class HelpDialog(QDialog):
    """Step-by-step guide for common user workflows."""

    def __init__(
        self,
        i18n: I18nManager,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._i18n = i18n

        self.setWindowTitle(
            i18n.tr("help.title")
        )

        self.resize(
            660,
            560,
        )

        layout = QVBoxLayout(
            self
        )

        scroll = QScrollArea(
            self
        )
        scroll.setWidgetResizable(
            True
        )

        content = QWidget()
        content_layout = QVBoxLayout(
            content
        )

        def heading(
            key: str,
        ) -> QLabel:
            label = QLabel(
                self._i18n.tr(key)
            )
            label.setWordWrap(True)
            label.setStyleSheet(
                "font-weight: bold;"
                "margin-top: 14px;"
            )
            return label

        def body(
            key: str,
        ) -> QLabel:
            label = QLabel(
                self._i18n.tr(key)
            )
            label.setWordWrap(True)
            return label

        content_layout.addWidget(
            heading(
                "help.section.bind"
            )
        )

        for key in (
            "help.bind.step1",
            "help.bind.step2",
            "help.bind.step3",
            "help.bind.note",
        ):
            content_layout.addWidget(
                body(key)
            )

        content_layout.addWidget(
            heading(
                "help.section.mouse"
            )
        )

        for key in (
            "help.mouse.step1",
            "help.mouse.step2",
            "help.mouse.step3",
        ):
            content_layout.addWidget(
                body(key)
            )

        content_layout.addWidget(
            heading(
                "help.section.tips"
            )
        )

        content_layout.addWidget(
            body(
                "help.tips.text"
            )
        )

        content_layout.addStretch()

        scroll.setWidget(
            content
        )

        layout.addWidget(
            scroll
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
        )

        buttons.accepted.connect(
            self.accept
        )

        layout.addWidget(
            buttons
        )
