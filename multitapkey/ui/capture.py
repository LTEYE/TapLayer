"""Key capture dialog."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
)

from multitapkey.i18n.manager import I18nManager


class CaptureKeyDialog(QDialog):
    def __init__(
        self,
        backend,
        i18n: I18nManager,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._backend = backend
        self._i18n = i18n
        self.result_key: str | None = None
        self.cancelled = False

        self.setWindowTitle(
            i18n.tr("capture.title")
        )

        label = QLabel(
            i18n.tr("capture.prompt")
        )

        layout = QVBoxLayout(
            self
        )
        layout.addWidget(label)

        self._timer = QTimer(
            self
        )
        self._timer.setInterval(30)
        self._timer.timeout.connect(
            self._poll
        )

    def showEvent(self, event):
        super().showEvent(event)

        self.cancelled = False
        self.result_key = None

        self._backend.begin_capture()
        self._timer.start()

    def _poll(self) -> None:
        result = (
            self._backend.poll_capture_result()
        )

        if result is None:
            return

        self._timer.stop()

        if result.kind == "key":
            self.result_key = result.key
            self.accept()
            return

        if result.kind == "cancel":
            self.cancelled = True
            self.reject()
            return

    def reject(self) -> None:
        self._timer.stop()
        self._backend.cancel_capture()
        super().reject()

    def closeEvent(self, event):
        self._timer.stop()
        self._backend.cancel_capture()
        super().closeEvent(event)
