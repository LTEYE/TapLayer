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
            580,
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
            body("help.intro")
        )

        content_layout.addWidget(
            heading(
                "help.section.bind"
            )
        )

        content_layout.addWidget(
            heading(
                "help.bind.how1_title"
            )
        )

        for key in (
            "help.bind.how1_step1",
            "help.bind.how1_step2",
            "help.bind.how1_step3",
            "help.bind.how1_tip",
        ):
            content_layout.addWidget(
                body(key)
            )

        content_layout.addWidget(
            heading(
                "help.bind.how2_title"
            )
        )

        content_layout.addWidget(
            body(
                "help.bind.how2_text"
            )
        )

        content_layout.addWidget(
            body(
                "help.bind.note"
            )
        )

        content_layout.addWidget(
            body(
                "help.bind.limit"
            )
        )

        content_layout.addWidget(
            heading(
                "help.section.settings"
            )
        )

        for key in (
            "help.settings.trigger",
            "help.settings.pause",
        ):
            content_layout.addWidget(
                body(key)
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
