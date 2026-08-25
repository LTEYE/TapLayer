"""System tray controller."""

from __future__ import annotations

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

        self.tray = QSystemTrayIcon(
            self
        )

        icon = QApplication.style().standardIcon(
            QStyle.StandardPixmap.SP_ComputerIcon
        )

        self.tray.setIcon(
            QIcon(icon)
        )

        self.tray.activated.connect(
            self._activated
        )

        self.refresh()

        self.tray.show()

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

    def _resume(self) -> None:
        self.engine.resume()
        self.window.refresh_status()
        self.refresh()

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
