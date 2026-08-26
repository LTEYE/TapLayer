"""System tray controller."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QStyle,
    QSystemTrayIcon,
    QMessageBox,
)

from multitapkey.core.config_models import ConfigError
from multitapkey.core.config_store import (
    export_config,
    load_config,
    load_config_file,
)
from multitapkey.i18n.manager import I18nManager


def _logo_icon_path(theme: str) -> str | None:
    """Return absolute path to the v2 logo PNG for the given theme,
    or None if the asset is missing (caller should fall back)."""
    suffix = "dark" if theme == "dark" else "light"
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[2]
    candidate = (
        base
        / "assets"
        / "logo"
        / f"taplayer-logo-v2-{suffix}-512.png"
    )
    if candidate.exists():
        return str(candidate)
    return None


class TrayController(QObject):
    def __init__(
        self,
        engine,
        window,
        i18n: I18nManager,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.engine = engine
        self.window = window
        self.i18n = i18n

        # 当前主题（light/dark），由 window._apply_theme 同步
        self._theme = "light"

        self.tray = QSystemTrayIcon(
            self
        )

        self._apply_icon()

        self.tray.activated.connect(
            self._activated
        )

        self.tray.setToolTip(
            self.i18n.tr(
                "tray.tooltip"
            )
        )

        self.refresh()

        self.tray.show()

    def _apply_icon(self) -> None:
        """根据当前主题设置托盘图标，找不到资产时兜底用系统默认图标。"""
        path = _logo_icon_path(self._theme)
        if path is not None:
            self.tray.setIcon(QIcon(path))
        else:
            self.tray.setIcon(
                QIcon(
                    QApplication.style().standardIcon(
                        QStyle.StandardPixmap.SP_ComputerIcon
                    )
                )
            )

    def set_theme(self, theme: str) -> None:
        """window._apply_theme 时调用，同步托盘图标主题。"""
        if theme not in ("light", "dark"):
            return
        if theme == self._theme:
            return
        self._theme = theme
        self._apply_icon()

    def refresh(self) -> None:
        menu = QMenu()

        open_action = QAction(
            self.i18n.tr(
                "tray.open"
            ),
            menu,
        )

        open_action.triggered.connect(
            self.window.show_and_activate
        )

        menu.addAction(
            open_action
        )

        if self.engine.active:
            pause_action = QAction(
                self.i18n.tr(
                    "tray.pause"
                ),
                menu,
            )
            pause_action.triggered.connect(
                self._pause
            )
            menu.addAction(
                pause_action
            )
        else:
            resume_action = QAction(
                self.i18n.tr(
                    "tray.resume"
                ),
                menu,
            )
            resume_action.triggered.connect(
                self._resume
            )
            menu.addAction(
                resume_action
            )

        reload_action = QAction(
            self.i18n.tr(
                "tray.reload"
            ),
            menu,
        )
        reload_action.triggered.connect(
            self._reload
        )
        menu.addAction(
            reload_action
        )

        import_action = QAction(
            self.i18n.tr(
                "tray.import"
            ),
            menu,
        )
        import_action.triggered.connect(
            self.window.import_config
        )
        menu.addAction(
            import_action
        )

        export_action = QAction(
            self.i18n.tr(
                "tray.export"
            ),
            menu,
        )
        export_action.triggered.connect(
            self.window.export_config
        )
        menu.addAction(
            export_action
        )

        support_action = QAction(
            self.i18n.tr(
                "tray.support"
            ),
            menu,
        )
        support_action.triggered.connect(
            self.window._show_support_dialog
        )
        menu.addAction(
            support_action
        )

        menu.addSeparator()

        exit_action = QAction(
            self.i18n.tr(
                "tray.exit"
            ),
            menu,
        )
        exit_action.triggered.connect(
            self._exit
        )

        menu.addAction(
            exit_action
        )

        self.tray.setContextMenu(
            menu
        )

    def _pause(self) -> None:
        self.engine.pause()
        self.window.refresh_status()
        self.refresh()

        # 暂停/恢复用系统托盘气泡通知（程序暂停时主窗口可能
        # 已隐藏，顶部弹窗不可见，通知栏最合理）。
        self._balloon(
            "toast.pause"
        )

    def _resume(self) -> None:
        self.engine.resume()
        self.window.refresh_status()
        self.refresh()

        self._balloon(
            "toast.resume"
        )

    def _balloon(self, text_key: str) -> None:
        """系统托盘气泡（仅暂停/恢复使用）。失败不影响功能。"""
        try:
            self.tray.showMessage(
                self.i18n.tr(
                    "tray.tooltip"
                ),
                self.i18n.tr(
                    text_key
                ),
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
        except Exception:
            pass

    def _reload(self) -> None:
        try:
            config = load_config()
            self.engine.apply_config(
                config,
                self.engine.profile_name,
            )
            self.window.replace_config(
                config
            )
            self.window.refresh_status()
            self.refresh()

        except ConfigError:
            QMessageBox.critical(
                self.window,
                self.i18n.tr(
                    "config.load_failed.title"
                ),
                self.i18n.tr(
                    "config.load_failed.message"
                ),
            )

    def _exit(self) -> None:
        self.window.force_exit = True
        self.window.close()
        QApplication.quit()

    def _activated(
        self,
        reason,
    ) -> None:
        if (
            reason
            == QSystemTrayIcon.ActivationReason.DoubleClick
        ):
            self.window.show_and_activate()
