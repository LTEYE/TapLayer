"""Application entry point."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from multitapkey.core.config_models import (
    ConfigError,
    default_config,
)
from multitapkey.core.config_store import (
    config_dir,
    load_config,
    save_config,
)
from multitapkey.core.engine import Engine
from multitapkey.i18n.manager import I18nManager
from multitapkey.logging_setup import (
    setup_logging,
)
from multitapkey.platform.windows.keyboard_hook import (
    WindowsKeyboardBackend,
)
from multitapkey.platform.windows.send_input import (
    WindowsInputBackend,
)
from multitapkey.platform.windows.startup import (
    WindowsStartupBackend,
)
from multitapkey.ui.main_window import (
    MainWindow,
)
from multitapkey.ui.tray import (
    TrayController,
)


def main() -> int:
    if sys.platform != "win32":
        print(
            "MultiTapKey v0.1 "
            "supports Windows 10/11 only."
        )
        return 1

    setup_logging(
        debug=bool(
            os.environ.get(
                "MTK_DEBUG"
            )
        )
    )

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "MultiTapKey"
    )

    app.setQuitOnLastWindowClosed(
        False
    )

    lock = QLockFile(
        str(
            config_dir()
            / "single.lock"
        )
    )

    lock.setStaleLockTime(
        0
    )

    if not lock.tryLock(200):
        error = lock.error()

        if error == QLockFile.PermissionError:
            QMessageBox.critical(
                None,
                "MultiTapKey",
                "Unable to create "
                "single-instance lock.",
            )

        elif error == QLockFile.UnknownError:
            QMessageBox.critical(
                None,
                "MultiTapKey",
                "Unknown single-instance "
                "lock error.",
            )

        else:
            QMessageBox.information(
                None,
                "MultiTapKey",
                "Another MultiTapKey instance "
                "is already running.",
            )

        return 0

    config = None
    config_error = False

    try:
        config = load_config()
    except ConfigError:
        config_error = True

    language = (
        config.settings.language
        if config is not None
        else "system"
    )

    i18n = I18nManager(
        language
    )

    if config_error:
        # 旧版本或不支持的配置：明确提示后用 v2 默认配置替换，
        # 避免"加载失败→应用永远无法保存"的死锁。
        QMessageBox.warning(
            None,
            i18n.tr(
                "config.version_incompatible.title"
            ),
            i18n.tr(
                "config.version_incompatible.message"
            ),
        )

        config = default_config()
        save_config(config)
        config_error = False

    keyboard_backend = (
        WindowsKeyboardBackend()
    )

    input_backend = (
        WindowsInputBackend()
    )

    startup_backend = (
        WindowsStartupBackend()
    )

    engine = Engine(
        keyboard_backend=keyboard_backend,
        input_backend=input_backend,
    )

    window = MainWindow(
        engine=engine,
        i18n=i18n,
        config=config,
        config_error=config_error,
        startup_backend=startup_backend,
    )

    tray = TrayController(
        engine=engine,
        window=window,
        i18n=i18n,
    )

    window.attach_tray(
        tray
    )

    hook_ok = engine.start()

    if hook_ok and config is not None:
        engine.apply_config(
            config
        )

    window.refresh_status()
    tray.refresh()

    pump = QTimer(
        app
    )

    pump.setInterval(15)

    pump.timeout.connect(
        engine.pump
    )

    pump.start()

    app.aboutToQuit.connect(
        engine.shutdown
    )

    window.show()

    return app.exec()
