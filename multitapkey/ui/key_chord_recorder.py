"""Reusable Key Chord Recorder dialog.

Used by BOTH the Trigger editor and the Action editor so the
recording logic only ever needs to be fixed in one place.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from multitapkey.core.chord import (
    MAX_CHORD_KEYS,
    canonicalize_keys,
    chord_display,
)
from multitapkey.i18n.manager import I18nManager


class KeyChordRecorder(QDialog):
    def __init__(
        self,
        backend,
        i18n: I18nManager,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._backend = backend
        self._i18n = i18n

        self.keys: tuple[str, ...] = ()
        self.cancelled = False

        self.setWindowTitle(
            i18n.tr("recorder.title")
        )

        layout = QVBoxLayout(
            self
        )

        self._prompt = QLabel(
            i18n.tr("recorder.prompt")
        )
        layout.addWidget(
            self._prompt
        )

        self._live = QLabel(
            i18n.tr("action.select")
        )
        self._live.setWordWrap(True)
        self._live.setStyleSheet(
            self._normal_style()
        )
        # 悬停检测：鼠标移入/移出蓝色按键显示区时更新后端标志，
        # 鼠标键只有悬停在这上面时才捕获（比坐标换算可靠，无 DPI 误差）。
        self._live.installEventFilter(
            self
        )
        layout.addWidget(
            self._live
        )

        button_row = QHBoxLayout()

        self._ok = QPushButton(
            i18n.tr("recorder.ok")
        )
        self._ok.setEnabled(False)
        self._ok.setDefault(True)
        self._ok.clicked.connect(
            self._finish
        )

        self._cancel = QPushButton(
            i18n.tr("recorder.cancel")
        )
        self._cancel.clicked.connect(
            self.reject
        )

        button_row.addStretch()
        button_row.addWidget(
            self._cancel
        )
        button_row.addWidget(
            self._ok
        )

        layout.addLayout(
            button_row
        )

        self._timer = QTimer(
            self
        )
        self._timer.setInterval(30)
        self._timer.timeout.connect(
            self._poll
        )

    @staticmethod
    def _normal_style() -> str:
        return (
            "font-size: 22px;"
            "font-weight: bold;"
            "padding: 12px;"
        )

    @staticmethod
    def _recording_style() -> str:
        # 录制中高亮：蓝色边框+淡蓝底，让用户一眼看到
        # 鼠标录制区域（鼠标键必须在这里点击才捕获）。
        return (
            "font-size: 22px;"
            "font-weight: bold;"
            "padding: 12px;"
            "border: 2px solid #1a6cff;"
            "border-radius: 8px;"
            "background: rgba(26, 108, 255, 0.10);"
        )

    def eventFilter(self, obj, event):
        if obj is self._live:
            if event.type() == QEvent.Type.Enter:
                self._backend.set_mouse_in_area(
                    True
                )
            elif event.type() == QEvent.Type.Leave:
                self._backend.set_mouse_in_area(
                    False
                )

        return super().eventFilter(
            obj,
            event,
        )

    def _set_mouse_area(
        self,
        inside: bool,
    ) -> None:
        try:
            self._backend.set_mouse_in_area(
                inside
            )
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)

        self.keys = ()
        self.cancelled = False

        self._update_live()

        # 录制中：按键显示区高亮，明确告知鼠标录制区域
        self._live.setStyleSheet(
            self._recording_style()
        )

        self._backend.begin_capture()
        self._set_mouse_area(False)
        self._timer.start()

    def _poll(self) -> None:
        result = (
            self._backend.poll_capture_result()
        )

        if result is None:
            return

        if result.kind == "cancel":
            self._timer.stop()
            self.cancelled = True
            self.reject()
            return

        if result.kind == "key" and (
            result.key is not None
        ):
            self._add_key(result.key)

    def _add_key(self, key: str) -> None:
        try:
            canonical = canonicalize_keys(
                [*self.keys, key]
            )
        except ValueError:
            return

        if canonical == self.keys:
            # 同一键重复按下 / 自动重复：不产生重复项
            return

        if len(canonical) > MAX_CHORD_KEYS:
            self._live.setText(
                self._i18n.tr(
                    "recorder.max"
                )
            )
            return

        self.keys = canonical
        self._update_live()

    def _update_live(self) -> None:
        if not self.keys:
            self._live.setText(
                self._i18n.tr(
                    "action.select"
                )
            )
        else:
            self._live.setText(
                chord_display(
                    self.keys
                )
            )

        self._ok.setEnabled(
            bool(self.keys)
        )

    def _finish(self) -> None:
        self._timer.stop()
        self._set_mouse_area(False)
        self._backend.cancel_capture()
        self._live.setStyleSheet(
            self._normal_style()
        )
        self.accept()

    def reject(self) -> None:
        self._timer.stop()
        self._set_mouse_area(False)
        self._backend.cancel_capture()
        self._live.setStyleSheet(
            self._normal_style()
        )
        super().reject()

    def focusOutEvent(self, event):
        # 用户已离开该窗口：不再死等绑定，取消录制并恢复正常输入
        if self.isVisible():
            self._timer.stop()
            self._set_mouse_area(False)
            self._backend.cancel_capture()
            self._live.setStyleSheet(
                self._normal_style()
            )
            self.reject()
            return

        super().focusOutEvent(event)

    def closeEvent(self, event):
        self._timer.stop()
        self._set_mouse_area(False)
        self._backend.cancel_capture()
        self._live.setStyleSheet(
            self._normal_style()
        )
        super().closeEvent(event)
