"""Optional on-screen gesture recognition overlay.

Independent of the core engine: it only displays what the engine
reports through the observer callback. Default off.
"""

from __future__ import annotations

import ctypes

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
)

_HIDE_AFTER_MS = 900

# 让 OSD 弹窗在截图/录屏中完全隐身（Win10 2004+ 支持）。
# WDA_EXCLUDEFROMCAPTURE：窗口仅显示在显示器上；任何捕获（PrintScreen、
# 系统截图工具、以及走 DWM 合成路径的第三方截图/录屏工具）中都完全不出现。
# 微软官方文档的典型用例就是"录像控制按钮不被录进画面"，与 OSD 弹窗同场景。
_WDA_EXCLUDEFROMCAPTURE = 0x00000011


def _exclude_from_capture(window: QWidget) -> None:
    """把 OSD 弹窗从截图/录屏中排除；失败静默（老系统/非 DWM 场景不影响功能）。"""
    try:
        user32 = ctypes.WinDLL(
            "user32",
            use_last_error=True,
        )
        user32.SetWindowDisplayAffinity.argtypes = (
            ctypes.c_void_p,
            ctypes.c_uint,
        )
        user32.SetWindowDisplayAffinity.restype = (
            ctypes.c_bool
        )
        user32.SetWindowDisplayAffinity(
            int(window.winId()),
            _WDA_EXCLUDEFROMCAPTURE,
        )
    except Exception:
        pass


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

    def showEvent(
        self,
        event,
    ) -> None:
        super().showEvent(event)
        # 每次显示前确保"截图隐身"生效（幂等，句柄在窗口显示后才有效）。
        _exclude_from_capture(self)

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
