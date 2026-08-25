"""Optional on-screen gesture recognition overlay.

Independent of the core engine: it only displays what the engine
reports through the observer callback. Default off.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
)

_HIDE_AFTER_MS = 900


class GestureOverlay(QWidget):
    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating
        )

        self._label = QLabel(
            self
        )
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self._label.setStyleSheet(
            "color: #ffffff;"
            "font-size: 40px;"
            "font-weight: bold;"
            "background: rgba(0, 0, 0, 140);"
            "border-radius: 12px;"
            "padding: 14px 28px;"
        )

        self._hide_timer = QTimer(
            self
        )
        self._hide_timer.setSingleShot(
            True
        )
        self._hide_timer.timeout.connect(
            self.hide
        )

    def show_gesture(
        self,
        description: str,
    ) -> None:
        self._label.setText(
            description
        )
        self._label.adjustSize()
        self.adjustSize()

        screen = (
            QApplication.primaryScreen()
        )
        if screen is not None:
            geometry = (
                screen.availableGeometry()
            )
            self.move(
                geometry.center().x()
                - self.width() // 2,
                geometry.top() + 120,
            )

        self.show()
        self.raise_()

        self._hide_timer.start(
            _HIDE_AFTER_MS
        )
