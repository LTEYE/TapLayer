"""Application entry point."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import os
import sys

from PySide6.QtCore import (
    QAbstractNativeEventFilter,
    QLockFile,
    QTimer,
)
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

# 全局暂停热键：Alt+Ctrl+F9（紧急逃生口——万一触发键接管了
# 鼠标左键导致无法点击，用它立刻暂停/恢复）
HOTKEY_ID = 1
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_F9 = 0x78
WM_HOTKEY = 0x0312

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.RegisterHotKey.restype = wt.BOOL
user32.RegisterHotKey.argtypes = (
    wt.HWND,
    ctypes.c_int,
    wt.UINT,
    wt.UINT,
)


class _HotkeyFilter(QAbstractNativeEventFilter):
    """监听 WM_HOTKEY，触发暂停/恢复切换。"""

    def __init__(self, callback) -> None:
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        if event_type not in (
            b"windows_generic_MSG",
            "windows_generic_MSG",
        ):
            return False, 0

        try:
            msg = ctypes.cast(
                int(message),
                ctypes.POINTER(wt.MSG),
            ).contents
        except Exception:
            return False, 0

        if (
            msg.message == WM_HOTKEY
            and msg.wParam == HOTKEY_ID
        ):
            self._callback()
            return True, 0

        return False, 0


def main() -> int:
    if sys.platform != "win32":
        print(
            "TapLayer v1.0.0 "
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

    # Fusion 风格：对自定义样式表支持最稳（Windows 原生风格下
    # QSpinBox 箭头会失效/点击被吞），统一跨平台观感。
    app.setStyle(
        "Fusion"
    )

    app.setApplicationName(
        "TapLayer"
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
                "TapLayer",
                "Unable to create "
                "single-instance lock.",
            )

        elif error == QLockFile.UnknownError:
            QMessageBox.critical(
                None,
                "TapLayer",
                "Unknown single-instance "
                "lock error.",
            )

        else:
            QMessageBox.information(
                None,
                "TapLayer",
                "Another TapLayer instance "
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

    # 全局暂停热键 Alt+Ctrl+F9（注册失败不影响主功能）
    hotkey_filter = _HotkeyFilter(
        window.toggle_pause
    )
    app.installNativeEventFilter(
        hotkey_filter
    )

    if not user32.RegisterHotKey(
        None,
        HOTKEY_ID,
        MOD_ALT | MOD_CONTROL,
        VK_F9,
    ):
        log.warning(
            "failed to register global "
            "pause hotkey Alt+Ctrl+F9"
        )

    app.aboutToQuit.connect(
        engine.shutdown
    )

    # 退出前自动保存未应用的设置（修复：改完设置直接退出/托盘
    # 退出会导致下次启动回到旧配置）
    app.aboutToQuit.connect(
        window.save_if_dirty
    )

    # 退出前安装已下载的自动更新（bat 独立进程替换 exe 后重启）
    app.aboutToQuit.connect(
        window._install_pending_update
    )

    # 开机自启（任务计划带 --hidden）→ 启动后不显示主窗口，直接进托盘
    if "--hidden" not in sys.argv[1:]:
        window.show()

    return app.exec()
