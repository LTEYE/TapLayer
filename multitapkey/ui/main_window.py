"""Main PySide6 window."""

from __future__ import annotations

import copy
import logging
import os
import threading
import webbrowser

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from multitapkey.core.chord import (
    canonicalize_keys,
    chord_display,
)
from multitapkey.core.config_models import (
    MAX_TAP_COUNT,
    MIN_DOUBLE_TAP_INTERVAL_MS,
    MIN_HOLD_THRESHOLD_MS,
    PROFILE_NAMES,
    Config,
    ConfigError,
    default_config,
    to_dict,
    validate_and_build,
)
from multitapkey.core.config_store import (
    config_dir,
    export_config as export_config_file,
    import_config as import_config_file,
    save_config,
)
from multitapkey.i18n.manager import I18nManager
from .gesture_overlay import GestureOverlay
from .help_dialog import HelpDialog
from .key_chord_recorder import KeyChordRecorder


log = logging.getLogger(__name__)

# 内置配置档名 → i18n 键（显示汉化，数据/引擎仍用原名）
_PROFILE_NAME_KEYS = {
    "default": "profile.name.default",
    "Gaming": "profile.name.Gaming",
    "Work": "profile.name.Work",
}

_THEME_QSS = {
    "light": (
        "QMainWindow { background: #F0F0F0; }"
        "QDialog, QMessageBox, QInputDialog { background: #FFFFFF; }"
        "QLabel { color: #2C2C2A; background: transparent; }"
        "#toastLabel { background: #2C2C2A;"
        " color: #FFFFFF; border: 1px solid #1A1A18;"
        " border-radius: 8px;"
        " padding: 10px 18px; font-size: 14px;"
        " font-weight: 500; }"
        "#statusLabel, #dirtyLabel { font-weight: 500; }"
        "#bindingList { background: #FFFFFF; border: none; }"
        "#bindingList::item { border: none; background: #FFFFFF; }"
        "QScrollArea { border: none; background: #FFFFFF; }"
        "QScrollArea > QWidget > QWidget { background: #FFFFFF; }"
        "#bindingEditor, #settings_group, QGroupBox {"
        " background: #FFFFFF; color: #2C2C2A;"
        " border: 0.5px solid #D3D1C7;"
        " border-radius: 8px; margin-top: 6px;"
        " font-size: 14px; font-weight: 500; }"
        "#bindingCard { background: #FFFFFF;"
        " border: 0.5px solid #D3D1C7; border-radius: 8px; }"
        "#bindingCard[selected=\"true\"] { background: #E6F1FB;"
        " border: 0.5px solid #185FA5; }"
        "#bindingCardName { font-size: 14px; font-weight: 500;"
        " color: #2C2C2A; background: transparent; }"
        "#bindingCardSummary { font-size: 13px; color: #444441;"
        " background: transparent; }"
        "#gestureCard { background: #FFFFFF;"
        " border: 0.5px solid #D3D1C7; border-radius: 8px; }"
        "#gestureName { font-size: 13px; font-weight: 500;"
        " color: #2C2C2A; background: transparent; }"
        "#gestureValue { font-size: 14px; font-weight: 500;"
        " color: #2C2C2A; background: #E0DED6;"
        " border-radius: 6px; padding: 2px 10px; }"
        "#gestureParam { font-size: 12px; color: #5F5E5A;"
        " background: transparent; }"
        "#antiPiracy { color: #A32D2D; font-size: 12px;"
        " background: transparent; }"
        "QComboBox { background: #FFFFFF;"
        " color: #2C2C2A; border: 0.5px solid #D3D1C7;"
        " border-radius: 4px; }"
        "QComboBox QAbstractItemView { background: #FFFFFF;"
        " color: #2C2C2A; selection-background-color: #E6F1FB; }"
        "QSpinBox { background: #FFFFFF; color: #2C2C2A;"
        " border: 0.5px solid #D3D1C7; }"
        "QSpinBox:disabled { background: #F1EFE8; color: #B4B2A9;"
        " border: 0.5px solid #E0DED6; }"
        "QCheckBox { color: #2C2C2A; background: transparent;"
        " border: none; }"
        "QCheckBox::indicator { width: 16px; height: 16px;"
        " border-radius: 4px; border: 1px solid #9AA0A6;"
        " background: #E8E8E8; }"
        "QCheckBox::indicator:checked { background: #1a6cff;"
        " border-color: #1a6cff; }"
        "QCheckBox#dangerCheck::indicator:checked {"
        " background: #E24B4A; border-color: #E24B4A; }"
        "#leftTitle { font-size: 14px; font-weight: 500;"
        " color: #2C2C2A; }"
        "#editorTitle { font-size: 15px; font-weight: 500;"
        " color: #2C2C2A; }"
        "QPushButton { background: #FFFFFF; color: #2C2C2A;"
        " border: 0.5px solid #D3D1C7; border-radius: 6px;"
        " padding: 6px 14px; font-size: 13px;"
        " min-height: 26px; }"
        "QPushButton:hover { background: #F1EFE8; }"
        "#applyButton { font-size: 16px; min-height: 48px;"
        " border-radius: 8px; }"
        "#gestureDeleteBtn { background: #E24B4A; color: #FFFFFF;"
        " border: none; }"
        "#gestureDeleteBtn:hover { background: #A32D2D; }"
    ),
    "dark": (
        "QMainWindow { background: #1E1E1E; }"
        "QDialog, QMessageBox, QInputDialog { background: #1E1E1E; }"
        "QLabel { color: #E0E0E0; background: transparent; }"
        "#toastLabel { background: #E0E0E0;"
        " color: #1E1E1E; border: 1px solid #FFFFFF;"
        " border-radius: 8px;"
        " padding: 10px 18px; font-size: 14px;"
        " font-weight: 500; }"
        "#statusLabel, #dirtyLabel { font-weight: 500; }"
        "#bindingList { background: #1E1E1E; border: none; }"
        "#bindingList::item { border: none; background: #1E1E1E; }"
        "QScrollArea { border: none; background: #1E1E1E; }"
        "QScrollArea > QWidget > QWidget { background: #1E1E1E; }"
        "#bindingEditor, #settings_group, QGroupBox {"
        " background: #1E1E1E; color: #E0E0E0;"
        " border: 0.5px solid #3C3C3C;"
        " border-radius: 8px; margin-top: 6px;"
        " font-size: 14px; font-weight: 500; }"
        "#bindingCard { background: #2B2B2B;"
        " border: 0.5px solid #3C3C3C; border-radius: 8px; }"
        "#bindingCard[selected=\"true\"] { background: #1F3B57;"
        " border: 0.5px solid #378ADD; }"
        "#bindingCardName { font-size: 14px; font-weight: 500;"
        " color: #E0E0E0; background: transparent; }"
        "#bindingCardSummary { font-size: 13px; color: #B4B2A9;"
        " background: transparent; }"
        "#gestureCard { background: #2B2B2B;"
        " border: 0.5px solid #3C3C3C; border-radius: 8px; }"
        "#gestureName { font-size: 13px; font-weight: 500;"
        " color: #B4B2A9; background: transparent; }"
        "#gestureValue { font-size: 14px; font-weight: 500;"
        " color: #E0E0E0; background: #3C3C3C;"
        " border-radius: 6px; padding: 2px 10px; }"
        "#gestureParam { font-size: 12px; color: #9AA0A6;"
        " background: transparent; }"
        "#antiPiracy { color: #FF8A80; font-size: 12px;"
        " background: transparent; }"
        "QComboBox { background: #2B2B2B;"
        " color: #E0E0E0; border: 0.5px solid #3C3C3C;"
        " border-radius: 4px; }"
        "QComboBox QAbstractItemView { background: #2B2B2B;"
        " color: #E0E0E0; selection-background-color: #1F3B57; }"
        "QSpinBox { background: #2B2B2B; color: #E0E0E0;"
        " border: 0.5px solid #3C3C3C; }"
        "QSpinBox:disabled { background: #232323; color: #6A6A6A;"
        " border: 0.5px solid #333333; }"
        "QCheckBox { color: #E0E0E0; background: transparent;"
        " border: none; }"
        "QCheckBox::indicator { width: 16px; height: 16px;"
        " border-radius: 4px; border: 1px solid #888780;"
        " background: #3C3C3C; }"
        "QCheckBox::indicator:checked { background: #1a6cff;"
        " border-color: #1a6cff; }"
        "QCheckBox#dangerCheck::indicator:checked {"
        " background: #A32D2D; border-color: #A32D2D; }"
        "#leftTitle { font-size: 14px; font-weight: 500;"
        " color: #E0E0E0; }"
        "#editorTitle { font-size: 15px; font-weight: 500;"
        " color: #E0E0E0; }"
        "QPushButton { background: #2B2B2B; color: #E0E0E0;"
        " border: 0.5px solid #3C3C3C; border-radius: 6px;"
        " padding: 6px 14px; font-size: 13px;"
        " min-height: 26px; }"
        "QPushButton:hover { background: #3C3C3C; }"
        "#applyButton { font-size: 16px; min-height: 48px;"
        " border-radius: 8px; }"
        "#gestureDeleteBtn { background: #A32D2D; color: #FFFFFF;"
        " border: none; }"
        "#gestureDeleteBtn:hover { background: #501313; }"
        "QMenu { background: #2B2B2B; color: #E0E0E0;"
        " border: 0.5px solid #3C3C3C; }"
        "QMenu::item:selected { background: #1F3B57; }"
        "QListWidget { background: #1E1E1E; }"
    ),
}

_THEME_STATUS_COLORS = {
    "light": {
        "running": "#3B6D11",
        "paused": "#5F5E5A",
        "error": "#A32D2D",
        "unsaved": "#BA7517",
    },
    "dark": {
        "running": "#97C459",
        "paused": "#B4B2A9",
        "error": "#F09595",
        "unsaved": "#FAC775",
    },
}


def _system_dark_mode() -> bool:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(
                key,
                "AppsUseLightTheme",
            )
            return value == 0
    except Exception:
        return False


class _UpdateCheckWorker(QObject):
    """后台检查更新（网络请求不阻塞 UI 线程）。"""

    finished = Signal(
        bool,
        str,
        str,
        str,
    )  # ok, latest_version, exe_download_url, release_page_url

    def run(self) -> None:
        from multitapkey.core.updater import (
            check_for_update,
        )

        ok, latest, exe_url, page_url = (
            check_for_update()
        )
        self.finished.emit(
            ok,
            latest,
            exe_url,
            page_url,
        )


class _UpdateDownloadWorker(QObject):
    """后台下载最新版 exe（网络请求不阻塞 UI 线程）。"""

    finished = Signal(bool)  # 是否下载成功

    def __init__(
        self,
        url: str,
        dest_path: str,
    ) -> None:
        super().__init__()
        self._url = url
        self._dest = dest_path

    def run(self) -> None:
        from multitapkey.core.updater import (
            download_update,
        )

        try:
            download_update(
                self._url,
                self._dest,
            )
        except Exception:
            log.exception(
                "update download failed"
            )
            self.finished.emit(False)
            return

        self.finished.emit(True)


class MainWindow(QMainWindow):
    def __init__(
        self,
        engine,
        i18n: I18nManager,
        config: Config | None,
        config_error: bool,
        startup_backend,
    ) -> None:
        super().__init__()

        self.engine = engine
        self.i18n = i18n
        self.startup_backend = startup_backend

        self.force_exit = False
        self._config_valid = (
            config is not None
        )

        self._config = (
            config
            if config is not None
            else default_config()
        )

        self._working = copy.deepcopy(
            to_dict(self._config)
        )

        self._saved = copy.deepcopy(
            self._working
        )

        # 界面加载/重建守卫：构建控件期间产生的信号不视为用户改动
        # （否则启动时会把控件默认状态污染进工作副本，误报"未保存"）
        self._loading_ui = False

        self._current_binding_index: int | None = None

        self._profile_label = None
        self._tr_buttons: dict = {}
        self._tray = None

        # Chord 编辑器状态
        self._trigger_chord: tuple[str, ...] = ()
        self._gesture_widgets: dict = {}
        self._add_tap_button = None

        # OSD 浮层（默认关闭）
        self._gesture_overlay = None

        # 编辑器脏标记（区别于 working!=saved，控件变更立即置位）
        self._editor_dirty = False

        # 当前生效主题（light/dark），由 _apply_theme 维护
        self._theme_resolved = "light"

        # toast 提示窗口引用（防止局部变量被 GC 回收导致一闪即逝）
        self._toast = None

        # 设置即时生效的防抖定时器（spin 连续变化时合并写入）
        self._settings_timer = QTimer(
            self
        )
        self._settings_timer.setSingleShot(
            True
        )
        self._settings_timer.setInterval(
            250
        )
        self._settings_timer.timeout.connect(
            self._commit_settings
        )

        self._build_ui()

        if config_error:
            self.show_config_error()

        self.refresh_all()

        self._sync_gesture_overlay(
            self._config.settings.enable_gesture_overlay
        )

        # v2.2+：自动更新——已下载待安装的新版 exe 路径（None=无）
        self._pending_update_path: str | None = None

        # 首次启动引导（触发键机制说明 + 高亮引导设置）
        self._show_onboarding_if_needed()

        # 启动自动检查更新（设置开启时后台执行，不阻塞界面）
        self._maybe_auto_check_update()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle(
            self.i18n.tr(
                "app.title"
            )
        )

        self._apply_theme()

        self.resize(
            900,
            700,
        )

        root = QWidget(
            self
        )

        self.setCentralWidget(
            root
        )

        main_layout = QVBoxLayout(
            root
        )

        self._title_label = QLabel(
            self.i18n.tr(
                "app.title"
            )
        )

        self.statusLabel = QLabel()
        self.statusLabel.setObjectName(
            "statusLabel"
        )

        self._dirty_label = QLabel()
        self._dirty_label.setObjectName(
            "dirtyLabel"
        )
        self._dirty_label.hide()

        self._pause_button = QPushButton()
        self._pause_button.clicked.connect(
            self._toggle_pause
        )

        top_bar = QHBoxLayout()

        top_bar.addWidget(
            self._title_label
        )
        top_bar.addStretch()

        self._profile_label = QLabel(
            self.i18n.tr(
                "profile.label"
            )
        )

        top_bar.addWidget(
            self._profile_label
        )

        self.profileCombo = QComboBox()
        self.profileCombo.setObjectName(
            "profileCombo"
        )
        self.profileCombo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.profileCombo.setMinimumContentsLength(
            6
        )
        self.profileCombo.setMinimumWidth(
            120
        )

        self.profileCombo.currentIndexChanged.connect(
            self._profile_changed
        )

        top_bar.addWidget(
            self.profileCombo
        )

        self._add_profile_button = QPushButton(
            self.i18n.tr(
                "profile.add"
            )
        )
        self._add_profile_button.clicked.connect(
            self._add_profile
        )
        top_bar.addWidget(
            self._add_profile_button
        )

        top_bar.addWidget(
            self._dirty_label
        )
        top_bar.addWidget(
            self.statusLabel
        )
        top_bar.addWidget(
            self._pause_button
        )

        main_layout.addLayout(
            top_bar
        )

        content = QHBoxLayout()

        left = QVBoxLayout()

        self._left_title = QLabel(
            self.i18n.tr(
                "left.title"
            )
        )
        self._left_title.setObjectName(
            "leftTitle"
        )
        left.addWidget(
            self._left_title
        )

        self.bindingList = QListWidget()
        self.bindingList.setObjectName(
            "bindingList"
        )

        self.bindingList.currentRowChanged.connect(
            self._binding_selected
        )

        left.addWidget(
            self.bindingList
        )

        button_row = QHBoxLayout()

        for key, handler in (
            (
                "button.add",
                self._add_binding,
            ),
            (
                "button.delete",
                self._delete_binding,
            ),
        ):
            button = QPushButton(
                self.i18n.tr(key)
            )
            button.clicked.connect(
                handler
            )
            self._tr_buttons[key] = button
            button_row.addWidget(
                button
            )

        left.addLayout(
            button_row
        )

        content.addLayout(
            left,
            1,
        )

        self.bindingEditor = QGroupBox()
        self.bindingEditor.setObjectName(
            "bindingEditor"
        )

        self.editor_layout = QVBoxLayout(
            self.bindingEditor
        )

        # 编辑器包一层滚动区：内容再高也不会把窗口撑大、
        # 把底部按钮挤出屏幕（小屏幕友好）。
        self.editor_scroll = QScrollArea()
        self.editor_scroll.setWidgetResizable(
            True
        )
        self.editor_scroll.setWidget(
            self.bindingEditor
        )

        right_column = QVBoxLayout()
        right_column.setSpacing(
            4
        )

        self._editor_title = QLabel(
            self.i18n.tr(
                "binding.editor"
            )
        )
        self._editor_title.setObjectName(
            "editorTitle"
        )
        right_column.addWidget(
            self._editor_title
        )

        right_column.addWidget(
            self.editor_scroll,
            1,
        )

        content.addLayout(
            right_column,
            2,
        )

        main_layout.addLayout(
            content,
            1,
        )

        settings = QGroupBox(
            self.i18n.tr(
                "settings.group"
            )
        )
        settings.setObjectName(
            "settings_group"
        )

        self._settings_group = settings

        # 设置面板 = 左（设置项表单） + 右（保存配置大按钮区）
        self.settings_layout = QHBoxLayout(
            settings
        )
        self.settings_layout.setContentsMargins(
            6,
            10,
            10,
            10,
        )
        self.settings_layout.setSpacing(
            16
        )

        self._settings_form = QFormLayout()
        self._settings_form.setVerticalSpacing(
            4
        )
        self._settings_form.setHorizontalSpacing(
            12
        )
        self.settings_layout.addLayout(
            self._settings_form,
            1,
        )

        right_panel = QVBoxLayout()
        right_panel.setSpacing(
            8
        )
        right_panel.addStretch()

        self._apply_button = QPushButton(
            self.i18n.tr(
                "button.apply"
            )
        )
        self._apply_button.setObjectName(
            "applyButton"
        )
        self._apply_button.setMinimumWidth(
            280
        )
        self._apply_button.clicked.connect(
            self._apply
        )
        self._tr_buttons[
            "button.apply"
        ] = self._apply_button
        right_panel.addWidget(
            self._apply_button
        )

        op_row = QHBoxLayout()
        op_row.setSpacing(
            8
        )

        for key, handler in (
            (
                "button.import",
                self.import_config,
            ),
            (
                "button.export",
                self.export_config,
            ),
            (
                "button.restore_default",
                self._restore_default,
            ),
            (
                "button.help",
                self._show_help,
            ),
            (
                "button.support",
                self._show_support_dialog,
            ),
        ):
            button = QPushButton(
                self.i18n.tr(key)
            )
            button.clicked.connect(
                handler
            )
            self._tr_buttons[key] = button
            op_row.addWidget(
                button
            )

        right_panel.addLayout(
            op_row
        )
        right_panel.addStretch()

        self.settings_layout.addLayout(
            right_panel,
            2,
        )

        self.spinDoubleTap = QSpinBox()
        self.spinDoubleTap.setObjectName(
            "spinDoubleTap"
        )
        self.spinDoubleTap.setRange(
            MIN_DOUBLE_TAP_INTERVAL_MS,
            1000,
        )
        self.spinDoubleTap.setSingleStep(
            10,
        )
        self.spinDoubleTap.valueChanged.connect(
            self._settings_changed
        )

        self.spinHold = QSpinBox()
        self.spinHold.setObjectName(
            "spinHold"
        )
        self.spinHold.setRange(
            MIN_HOLD_THRESHOLD_MS,
            5000,
        )
        self.spinHold.setSingleStep(
            10,
        )
        self.spinHold.valueChanged.connect(
            self._settings_changed
        )

        self.languageCombo = QComboBox()
        self.languageCombo.addItem(
            self.i18n.tr(
                "language.system"
            ),
            "system",
        )
        self.languageCombo.addItem(
            self.i18n.tr(
                "language.zh_CN"
            ),
            "zh_CN",
        )
        self.languageCombo.addItem(
            self.i18n.tr(
                "language.en_US"
            ),
            "en_US",
        )
        self.languageCombo.currentIndexChanged.connect(
            self._settings_changed
        )

        self.themeCombo = QComboBox()
        self.themeCombo.addItem(
            self.i18n.tr(
                "theme.system"
            ),
            "system",
        )
        self.themeCombo.addItem(
            self.i18n.tr(
                "theme.dark"
            ),
            "dark",
        )
        self.themeCombo.addItem(
            self.i18n.tr(
                "theme.light"
            ),
            "light",
        )
        self.themeCombo.currentIndexChanged.connect(
            self._settings_changed
        )

        self.startupCheck = QCheckBox()

        self.startupCheck.stateChanged.connect(
            self._startup_changed
        )

        self.startupCheck.stateChanged.connect(
            self._settings_changed
        )

        self.overlayCheck = QCheckBox()

        self.overlayCheck.stateChanged.connect(
            self._settings_changed
        )

        # v2.2+：更新设置（样式与上方勾选框一致）
        self.autoCheckUpdate = QCheckBox()
        self.autoCheckUpdate.stateChanged.connect(
            self._settings_changed
        )

        self.autoUpdate = QCheckBox()
        self.autoUpdate.stateChanged.connect(
            self._settings_changed
        )

        self._settings_form.addRow(
            self.i18n.tr(
                "settings.double_tap"
            ),
            self.spinDoubleTap,
        )

        self._settings_form.addRow(
            self.i18n.tr(
                "settings.hold"
            ),
            self.spinHold,
        )

        self._settings_form.addRow(
            self.i18n.tr(
                "settings.language"
            ),
            self.languageCombo,
        )

        self._settings_form.addRow(
            self.i18n.tr(
                "settings.theme"
            ),
            self.themeCombo,
        )

        self._settings_form.addRow(
            self.i18n.tr(
                "settings.startup"
            ),
            self.startupCheck,
        )

        self._settings_form.addRow(
            self.i18n.tr(
                "settings.overlay"
            ),
            self.overlayCheck,
        )

        self._settings_form.addRow(
            self.i18n.tr(
                "settings.auto_check_update"
            ),
            self.autoCheckUpdate,
        )

        self._settings_form.addRow(
            self.i18n.tr(
                "settings.auto_update"
            ),
            self.autoUpdate,
        )

        self.update_button = QPushButton(
            self.i18n.tr(
                "settings.update"
            )
        )
        self.update_button.clicked.connect(
            self._check_update
        )

        self.update_status = QLabel("")
        self.update_status.setObjectName(
            "gestureParam"
        )

        update_row = QWidget()
        update_layout = QHBoxLayout(
            update_row
        )
        update_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        update_layout.setSpacing(
            8
        )
        update_layout.addWidget(
            self.update_button
        )
        update_layout.addWidget(
            self.update_status,
            1,
        )

        self._settings_form.addRow(
            self.i18n.tr(
                "settings.update_label"
            ),
            update_row,
        )

        main_layout.addWidget(
            settings
        )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def show_and_activate(
        self,
    ) -> None:
        # showNormal：从托盘恢复时明确取消最小化状态
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def show_hook_failed(
        self,
    ) -> None:
        self.refresh_status()

    def show_config_error(
        self,
    ) -> None:
        self._config_valid = False
        self.refresh_status()

    def _resolved_theme(
        self,
    ) -> str:
        theme = self._working.get(
            "settings",
            {},
        ).get(
            "theme",
            "system",
        )

        if theme == "dark":
            return "dark"

        if theme == "light":
            return "light"

        return (
            "dark"
            if _system_dark_mode()
            else "light"
        )

    def _apply_theme(
        self,
    ) -> None:
        resolved = self._resolved_theme()

        self._theme_resolved = resolved

        # 应用级样式：主窗口与所有弹窗（消息框/输入框/录制器/引导）
        # 统一跟随主题，避免弹窗停留在系统深色样式。
        app = QApplication.instance()

        if app is not None:
            app.setStyleSheet(
                _THEME_QSS[resolved]
            )
        else:
            self.setStyleSheet(
                _THEME_QSS[resolved]
            )

        # 强制刷新全部子控件，避免样式表切换后一半控件
        # 停留在旧主题（黑底白字/白底浅字混排）
        style = self.style()

        for widget in self.findChildren(
            QWidget
        ):
            style.unpolish(
                widget
            )
            style.polish(
                widget
            )

        # 控件未建完时（_build_ui 早期调用）跳过状态刷新
        if (
            hasattr(
                self,
                "statusLabel",
            )
            and self.statusLabel is not None
        ):
            self.refresh_status()

        if (
            hasattr(
                self,
                "_apply_button",
            )
            and self._apply_button is not None
        ):
            self._update_apply_highlight()

        # 同步刷新窗口图标与托盘图标（v2 logo 跟随主题切换）
        self._apply_logo_icons(
            resolved
        )

    def _logo_path_for_theme(
        self,
        theme: str,
    ) -> str | None:
        """返回 v2 logo PNG 在当前主题下的绝对路径，资产缺失时返回 None。"""
        from pathlib import Path
        import sys

        if getattr(
            sys,
            "frozen",
            False,
        ):
            base = Path(
                sys._MEIPASS
            )
        else:
            base = Path(
                __file__
            ).resolve().parents[2]

        suffix = "dark" if theme == "dark" else "light"
        candidate = (
            base
            / "assets"
            / "logo"
            / f"taplayer-logo-v2-{suffix}-512.png"
        )
        if candidate.exists():
            return str(candidate)
        return None

    def _apply_logo_icons(
        self,
        theme: str,
    ) -> None:
        """主题切换时同步刷新窗口图标与托盘图标。"""
        icon_path = self._logo_path_for_theme(theme)
        if icon_path is not None:
            self.setWindowIcon(
                QIcon(icon_path)
            )
        if (
            self._tray is not None
            and hasattr(
                self._tray,
                "set_theme",
            )
        ):
            self._tray.set_theme(theme)

    def _theme_color(
        self,
        kind: str,
    ) -> str:
        return _THEME_STATUS_COLORS[
            self._theme_resolved
        ].get(
            kind,
            "#5F5E5A",
        )

    def _show_toast(
        self,
        text: str,
    ) -> None:
        if not text:
            return

        # 反馈提示用主窗口内部悬浮层（不用独立顶层窗口）：
        # 顶层 QLabel 窗口在真实桌面上存在不可见的问题（多屏/
        # 合成/置顶时机），主窗口内控件渲染绝对可靠、必定可见。
        parent = (
            self.centralWidget()
            or self
        )

        if self._toast is None:
            toast = QLabel(
                parent
            )
            toast.setObjectName(
                "toastLabel"
            )
            toast.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            toast.setWordWrap(
                True
            )
            toast.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )
            toast.hide()
            self._toast = toast
        else:
            toast = self._toast
            toast.setParent(
                parent
            )

        toast.setText(
            text
        )
        toast.adjustSize()

        # 定位在主窗口中央上方（跟随窗口移动/缩放）
        parent_w = parent.width()
        toast.move(
            max(
                (parent_w - toast.width()) // 2,
                8,
            ),
            24,
        )

        toast.show()
        toast.raise_()

        # 取消旧的隐藏定时器，重新计时
        timer = getattr(
            self,
            "_toast_timer",
            None,
        )

        if timer is not None:
            timer.stop()
        else:
            timer = QTimer(
                self
            )
            timer.setSingleShot(
                True
            )
            timer.timeout.connect(
                self._toast.hide
            )
            self._toast_timer = timer

        timer.start(
            2500
        )

    # ------------------------------------------------------------------
    # First-run onboarding（首次启动引导）
    # ------------------------------------------------------------------

    def _show_onboarding_if_needed(self) -> None:
        """首次启动时弹引导：说明触发键机制 + 推荐玩法 + 高亮触发键。"""
        try:
            flag = (
                config_dir()
                / "onboarded.flag"
            )
        except Exception:
            return

        if flag.exists():
            return

        try:
            flag.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            flag.write_text(
                "1",
                encoding="utf-8",
            )
        except Exception:
            log.exception(
                "onboarding flag write failed"
            )

        self._show_onboarding()

    def _show_onboarding(self) -> None:
        from PySide6.QtWidgets import (
            QDialog,
            QHBoxLayout,
            QPushButton,
            QTextBrowser,
            QVBoxLayout,
        )

        dialog = QDialog(
            self
        )
        dialog.setWindowTitle(
            self.i18n.tr(
                "onboarding.title"
            )
        )
        dialog.setMinimumWidth(
            560
        )

        layout = QVBoxLayout(
            dialog
        )

        body = QTextBrowser()
        body.setOpenExternalLinks(
            True
        )
        body.setHtml(
            "<div style='line-height:1.7;'>"
            + self.i18n.tr(
                "onboarding.body"
            )
            + "</div>"
        )
        layout.addWidget(
            body
        )

        row = QHBoxLayout()

        later_button = QPushButton(
            self.i18n.tr(
                "onboarding.later"
            )
        )
        later_button.clicked.connect(
            dialog.accept
        )
        row.addWidget(
            later_button
        )

        row.addStretch()

        set_button = QPushButton(
            self.i18n.tr(
                "onboarding.set_now"
            )
        )
        set_button.setDefault(
            True
        )
        set_button.clicked.connect(
            dialog.accept
        )
        set_button.clicked.connect(
            self._onboarding_highlight_trigger
        )
        row.addWidget(
            set_button
        )

        layout.addLayout(
            row
        )

        dialog.exec()

    def _onboarding_highlight_trigger(self) -> None:
        """高亮触发键卡片并提示用户点「录制热键」。"""
        self._highlight_trigger_card()

        self._show_toast(
            self.i18n.tr(
                "onboarding.hint"
            )
        )

    def _highlight_trigger_card(self) -> None:
        card = getattr(
            self,
            "_trigger_card",
            None,
        )

        if card is None:
            return

        self._flash_ticks = 0

        timer = QTimer(
            self
        )
        timer.setInterval(
            400
        )

        def tick() -> None:
            self._flash_ticks += 1

            if self._flash_ticks > 6:
                timer.stop()
                card.setStyleSheet(
                    ""
                )
                return

            card.setStyleSheet(
                (
                    "QFrame#gestureCard {"
                    " border: 2px solid #1a6cff;"
                    " border-radius: 8px;"
                    " background: #E6F1FB;"
                    " }"
                    if self._flash_ticks % 2 == 1
                    else ""
                )
            )

        timer.timeout.connect(
            tick
        )
        timer.start()

    def _show_settings_toast(
        self,
        old_settings,
        new_settings,
    ) -> None:
        messages = []

        if (
            old_settings.start_with_windows
            != new_settings.start_with_windows
        ):
            messages.append(
                self.i18n.tr(
                    "toast.startup"
                    + (
                        ".on"
                        if new_settings.start_with_windows
                        else ".off"
                    )
                )
            )

        if (
            old_settings.enable_gesture_overlay
            != new_settings.enable_gesture_overlay
        ):
            messages.append(
                self.i18n.tr(
                    "toast.overlay"
                    + (
                        ".on"
                        if new_settings.enable_gesture_overlay
                        else ".off"
                    )
                )
            )

        if (
            old_settings.theme
            != new_settings.theme
        ):
            theme_names = {
                "system": self.i18n.tr(
                    "theme.system"
                ),
                "dark": self.i18n.tr(
                    "theme.dark"
                ),
                "light": self.i18n.tr(
                    "theme.light"
                ),
            }
            messages.append(
                self.i18n.tr(
                    "toast.theme",
                    name=theme_names.get(
                        new_settings.theme,
                        new_settings.theme,
                    ),
                )
            )

        if (
            old_settings.language
            != new_settings.language
        ):
            language_names = {
                "system": self.i18n.tr(
                    "language.system"
                ),
                "zh_CN": self.i18n.tr(
                    "language.zh_CN"
                ),
                "en_US": self.i18n.tr(
                    "language.en_US"
                ),
            }
            messages.append(
                self.i18n.tr(
                    "toast.language",
                    name=language_names.get(
                        new_settings.language,
                        new_settings.language,
                    ),
                )
            )

        if (
            old_settings.double_tap_interval_ms
            != new_settings.double_tap_interval_ms
        ):
            messages.append(
                self.i18n.tr(
                    "toast.interval",
                    value=(
                        new_settings.double_tap_interval_ms
                    ),
                )
            )

        if (
            old_settings.hold_threshold_ms
            != new_settings.hold_threshold_ms
        ):
            messages.append(
                self.i18n.tr(
                    "toast.hold",
                    value=(
                        new_settings.hold_threshold_ms
                    ),
                )
            )

        self._show_toast(
            " · ".join(messages)
        )

    def refresh_status(
        self,
    ) -> None:
        if self.engine.hook_failed:
            text = self.i18n.tr(
                "status.hook_failed"
            )
            color = self._theme_color(
                "error"
            )
        elif not self._config_valid:
            text = self.i18n.tr(
                "status.config_failed"
            )
            color = self._theme_color(
                "error"
            )
        elif self.engine.paused:
            text = self.i18n.tr(
                "status.paused"
            )
            color = self._theme_color(
                "paused"
            )
        elif self.engine.active:
            text = self.i18n.tr(
                "status.running"
            )
            color = self._theme_color(
                "running"
            )
        else:
            text = self.i18n.tr(
                "status.paused"
            )
            color = self._theme_color(
                "paused"
            )

        self.statusLabel.setText(
            "● " + text
        )
        self.statusLabel.setStyleSheet(
            f"color: {color};"
        )

        self._update_pause_button()

    def _toggle_pause(
        self,
    ) -> None:
        if self.engine.paused:
            self.engine.resume()
        else:
            self.engine.pause()

        self.refresh_status()

    def _update_pause_button(
        self,
    ) -> None:
        if self.engine.paused:
            self._pause_button.setText(
                self.i18n.tr(
                    "button.resume"
                )
            )
        else:
            self._pause_button.setText(
                self.i18n.tr(
                    "button.pause"
                )
            )

    def refresh_all(
        self,
    ) -> None:
        self._editor_dirty = False
        self._rebuild_profile_combo()
        self._reload_working_from_config(
            preserve_profile=True
        )
        self.refresh_status()
        self._update_apply_highlight()

    def replace_config(
        self,
        config: Config,
    ) -> None:
        self._config = config
        self._config_valid = True

        self._working = copy.deepcopy(
            to_dict(config)
        )
        self._saved = copy.deepcopy(
            self._working
        )

        self._current_binding_index = None

        self.refresh_all()

    # ------------------------------------------------------------------
    # Working tree
    # ------------------------------------------------------------------

    def _working_profile(
        self,
    ) -> dict:
        # 必须按 engine 当前真实档取档，不能按下拉框当前项：
        # 切档瞬间下拉框已指向新档、但界面内容还是旧档，
        # 若按下拉框取档会把旧档界面内容写进新档（数据污染）。
        profile_name = (
            self.engine.profile_name
            or "default"
        )

        return self._working[
            "profiles"
        ][profile_name]

    def _is_dirty(
        self,
    ) -> bool:
        return self._working != self._saved

    def save_if_dirty(self) -> None:
        """退出前自动保存未应用更改（静默；失败仅记日志）。

        修复：以前只有点"应用"才落盘，改了设置直接退出/托盘退出
        会导致下次启动回到旧配置。进程退出前兜底保存一次。
        """
        if not self._config_valid:
            return

        if not self._is_dirty():
            return

        self._sync_controls_to_working()

        try:
            new_config = validate_and_build(
                self._working
            )
        except ConfigError as exc:
            log.warning(
                "unsaved config invalid on exit; discarded: %s",
                exc,
            )
            return

        try:
            save_config(new_config)
        except Exception:
            log.exception(
                "failed to auto-save config on exit"
            )
            return

        self._config = new_config
        self._config_valid = True
        self._working = copy.deepcopy(
            to_dict(new_config)
        )
        self._saved = copy.deepcopy(
            self._working
        )
        self._editor_dirty = False

    def _sync_controls_to_working(
        self,
    ) -> None:
        self._sync_settings_to_working()
        self._sync_current_binding()

    def _reload_working_from_config(
        self,
        preserve_profile: bool = False,
    ) -> None:
        current = (
            self.profileCombo.currentData()
            if preserve_profile
            and self.profileCombo.count()
            else "default"
        )

        self._working = copy.deepcopy(
            to_dict(self._config)
        )

        self._saved = copy.deepcopy(
            self._working
        )

        # 构建控件期间屏蔽"用户改动"信号，防止把控件默认状态
        # 污染进工作副本（否则启动即误报"有未保存修改"）。
        self._loading_ui = True

        try:
            self._rebuild_profile_combo(
                current_profile=current
            )

            self._refresh_binding_list()

            self._load_settings()
        finally:
            self._loading_ui = False

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------

    def _rebuild_profile_combo(
        self,
        current_profile: str | None = None,
    ) -> None:
        self.profileCombo.blockSignals(
            True
        )

        self.profileCombo.clear()

        names = list(
            self._working.get(
                "profiles",
                {},
            ).keys()
        )

        if not names:
            names = list(PROFILE_NAMES)

        active = (
            current_profile
            or self.engine.profile_name
        )

        for name in names:
            self.profileCombo.addItem(
                self._profile_display_name(
                    name
                ),
                name,
            )

        index = self.profileCombo.findData(
            active
        )

        if index < 0:
            index = 0

        self.profileCombo.setCurrentIndex(
            index
        )

        self.profileCombo.blockSignals(
            False
        )

    def _profile_display_name(
        self,
        name: str,
    ) -> str:
        key = _PROFILE_NAME_KEYS.get(
            name
        )

        if key is not None:
            return self.i18n.tr(
                key
            )

        return name

    def _add_profile(
        self,
    ) -> None:
        from PySide6.QtWidgets import (
            QDialogButtonBox,
            QInputDialog,
        )

        dialog = QInputDialog(
            self
        )
        dialog.setWindowTitle(
            self.i18n.tr(
                "profile.add.title"
            )
        )
        dialog.setLabelText(
            self.i18n.tr(
                "profile.add.prompt"
            )
        )
        dialog.setTextValue("")

        # QInputDialog 没有 button()，需从其内部的 QDialogButtonBox 取按钮
        button_box = dialog.findChild(
            QDialogButtonBox
        )

        if button_box is not None:
            ok_button = button_box.button(
                QDialogButtonBox.StandardButton.Ok
            )
            if ok_button is not None:
                ok_button.setText(
                    self.i18n.tr(
                        "recorder.ok"
                    )
                )

            cancel_button = button_box.button(
                QDialogButtonBox.StandardButton.Cancel
            )
            if cancel_button is not None:
                cancel_button.setText(
                    self.i18n.tr(
                        "recorder.cancel"
                    )
                )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        name = dialog.textValue().strip()

        if not name:
            QMessageBox.information(
                self,
                self.i18n.tr(
                    "profile.add.title"
                ),
                self.i18n.tr(
                    "profile.add.invalid"
                ),
            )
            return

        profiles = self._working.get(
            "profiles",
            {},
        )

        if name in profiles:
            QMessageBox.information(
                self,
                self.i18n.tr(
                    "profile.add.title"
                ),
                self.i18n.tr(
                    "profile.add.exists"
                ),
            )
            return

        # 新配置档 = 空档，不预装任何热键
        profiles[name] = {
            "bindings": [],
        }

        self._rebuild_profile_combo(
            current_profile=name
        )

        self._current_binding_index = None
        self._refresh_binding_list()
        self._clear_editor()

        self._mark_editor_changed()

    @staticmethod
    def _template_binding_dict() -> dict:
        unset = {
            "type": "chord",
            "keys": [],
        }

        return {
            "trigger": {
                "type": "chord",
                "keys": [],
            },
            "enabled": True,
            "gestures": {
                "taps": {
                    "1": copy.deepcopy(unset),
                },
                "hold": copy.deepcopy(unset),
            },
        }

    def _profile_changed(
        self,
        index: int,
    ) -> None:
        name = self.profileCombo.itemData(
            index
        )

        if not name:
            return

        self._sync_controls_to_working()

        if self._is_dirty():
            box = QMessageBox(
                self
            )
            box.setWindowTitle(
                self.i18n.tr(
                    "profile.discard.title"
                )
            )
            box.setText(
                self.i18n.tr(
                    "profile.discard.message"
                )
            )
            box.setIcon(
                QMessageBox.Icon.Question
            )

            switch_button = box.addButton(
                self.i18n.tr(
                    "profile.discard.switch"
                ),
                QMessageBox.ButtonRole.AcceptRole,
            )
            cancel_button = box.addButton(
                self.i18n.tr(
                    "profile.discard.cancel"
                ),
                QMessageBox.ButtonRole.RejectRole,
            )
            box.setDefaultButton(
                cancel_button
            )

            box.exec()

            if (
                box.clickedButton()
                != switch_button
            ):
                # 取消切换：回退组合框，仍留在当前配置档
                self.profileCombo.blockSignals(
                    True
                )
                old_index = (
                    self.profileCombo.findData(
                        self.engine.profile_name
                    )
                )
                self.profileCombo.setCurrentIndex(
                    max(old_index, 0)
                )
                self.profileCombo.blockSignals(
                    False
                )
                QMessageBox.information(
                    self,
                    self.i18n.tr(
                        "profile.label"
                    ),
                    self.i18n.tr(
                        "profile.keep.message"
                    ),
                )
                return

            self._working = copy.deepcopy(
                self._saved
            )
            self._editor_dirty = False

        try:
            self.engine.set_profile(
                name
            )
        except Exception:
            QMessageBox.critical(
                self,
                self.i18n.tr(
                    "error.title"
                ),
                self.i18n.tr(
                    "profile.switch_failed"
                ),
            )
            return

        self._current_binding_index = None
        self._refresh_binding_list()
        self._load_settings()

        self._show_toast(
            self.i18n.tr(
                "toast.profile",
                name=self._profile_display_name(
                    name
                ),
            )
        )

    # ------------------------------------------------------------------
    # Binding list
    # ------------------------------------------------------------------

    def _refresh_binding_list(
        self,
    ) -> None:
        self.bindingList.blockSignals(
            True
        )

        self.bindingList.clear()

        profile = self._working_profile()

        for binding in profile[
            "bindings"
        ]:
            item = QListWidgetItem()
            self.bindingList.addItem(
                item
            )
            self._set_binding_row(
                item,
                binding,
            )

        self.bindingList.blockSignals(
            False
        )

        if (
            self.bindingList.count()
            > 0
        ):
            row = (
                self._current_binding_index
                if self._current_binding_index
                is not None
                else 0
            )

            row = min(
                row,
                self.bindingList.count()
                - 1,
            )

            self.bindingList.setCurrentRow(
                row
            )
        else:
            self._current_binding_index = None
            self._clear_editor()
            self._show_editor_hint()

    def _set_binding_row(
        self,
        item,
        binding: dict,
    ) -> None:
        container = QFrame()
        container.setObjectName(
            "bindingCard"
        )

        card_layout = QVBoxLayout(
            container
        )
        card_layout.setContentsMargins(
            8,
            6,
            8,
            6,
        )
        card_layout.setSpacing(
            4
        )

        head = QHBoxLayout()

        trigger_action = binding[
            "trigger"
        ]
        trigger_keys = (
            trigger_action.get(
                "keys",
                [],
            )
        )

        trigger = (
            chord_display(
                trigger_keys
            )
            if trigger_keys
            else self.i18n.tr(
                "binding.no_trigger"
            )
        )

        name_label = QLabel(
            (
                binding.get(
                    "name",
                    "",
                )
                or trigger
            )
        )
        name_label.setObjectName(
            "bindingCardName"
        )
        name_label.setToolTip(
            trigger
        )
        head.addWidget(
            name_label
        )
        head.addStretch()

        rename_button = QPushButton(
            self.i18n.tr(
                "binding.rename"
            )
        )
        # 自适应宽度：最小 80px，文字（改名/Rename）多长按钮多宽
        rename_button.setMinimumWidth(
            80
        )
        rename_button.clicked.connect(
            lambda _checked=False,
            b=binding:
            self._rename_binding(
                b
            )
        )
        head.addWidget(
            rename_button
        )

        enabled_check = QCheckBox()
        enabled_check.setChecked(
            binding["enabled"]
        )
        enabled_check.setText(
            self.i18n.tr(
                "binding.enabled"
            )
            if binding["enabled"]
            else self.i18n.tr(
                "gesture.off"
            )
        )
        enabled_check.setToolTip(
            self.i18n.tr(
                "binding.enabled"
            )
        )
        enabled_check.stateChanged.connect(
            lambda _state,
            b=binding,
            c=enabled_check:
            self._binding_enabled_toggled(
                b,
                c,
            )
        )
        head.addWidget(
            enabled_check
        )

        card_layout.addLayout(
            head
        )

        summary = QLabel(
            self._binding_summary(
                binding
            )
        )
        summary.setObjectName(
            "bindingCardSummary"
        )
        card_layout.addWidget(
            summary
        )

        item.setSizeHint(
            container.sizeHint()
        )

        self.bindingList.setItemWidget(
            item,
            container,
        )

        # setItemWidget 之后再算一次尺寸，避免 item 高度不足把
        # 卡片第二行（手势摘要）裁掉，只剩顶部勾选框。
        container.adjustSize()
        item.setSizeHint(
            container.sizeHint()
        )

    def _binding_enabled_toggled(
        self,
        binding: dict,
        check,
    ) -> None:
        binding["enabled"] = (
            check.isChecked()
        )

        check.setText(
            self.i18n.tr(
                "binding.enabled"
            )
            if check.isChecked()
            else self.i18n.tr(
                "gesture.off"
            )
        )

        self._mark_editor_changed()

    def _rename_binding(
        self,
        binding: dict,
    ) -> None:
        from PySide6.QtWidgets import (
            QInputDialog,
        )

        text, ok = QInputDialog.getText(
            self,
            self.i18n.tr(
                "binding.rename_title"
            ),
            self.i18n.tr(
                "binding.rename_prompt"
            ),
            text=(
                binding.get(
                    "name",
                    "",
                )
                or ""
            ),
        )

        if not ok:
            return

        binding["name"] = (
            text.strip()
        )

        self._mark_editor_changed()

        # 重建卡片显示新名字（保留当前选中行）
        self._refresh_binding_list()

    def _update_binding_row(
        self,
        item,
        binding: dict,
    ) -> None:
        # 卡片结构下直接重建整行（触发键名/摘要/启用勾选一起刷新）
        self._set_binding_row(
            item,
            binding,
        )

    def _binding_summary(
        self,
        binding: dict,
    ) -> str:
        gestures = binding[
            "gestures"
        ]

        taps = gestures.get(
            "taps",
            {},
        )

        lines = []

        for raw_count in sorted(
            taps,
            key=int,
        ):
            lines.append(
                f"{self.i18n.tr('gesture.tap', count=raw_count)}"
                f"  {self._action_summary(taps[raw_count])}"
            )

        lines.append(
            f"{self.i18n.tr('gesture.hold')}"
            f"  {self._action_summary(gestures.get('hold', {}))}"
        )

        return "\n".join(lines)

    def _action_summary(
        self,
        action: dict,
    ) -> str:
        if action.get("type") != "chord":
            return self.i18n.tr(
                "gesture.off"
            )

        keys = action.get(
            "keys",
            [],
        )

        if not keys:
            return self.i18n.tr(
                "gesture.unset"
            )

        return chord_display(
            keys
        )

    def _binding_selected(
        self,
        row: int,
    ) -> None:
        if row < 0:
            self._clear_editor()
            self._show_editor_hint()
            return

        if (
            row
            == self._current_binding_index
        ):
            return

        self._sync_current_binding()

        self._current_binding_index = row

        binding = (
            self._working_profile()[
                "bindings"
            ][row]
        )

        self._load_binding_editor(
            binding
        )

        self._update_card_selection(
            row
        )

    def _update_card_selection(
        self,
        row: int,
    ) -> None:
        for i in range(
            self.bindingList.count()
        ):
            item = self.bindingList.item(
                i
            )

            widget = (
                self.bindingList.itemWidget(
                    item
                )
            )

            if widget is None:
                continue

            widget.setProperty(
                "selected",
                i == row,
            )

            style = widget.style()
            style.unpolish(
                widget
            )
            style.polish(
                widget
            )

    # ------------------------------------------------------------------
    # Binding editor
    # ------------------------------------------------------------------

    def _show_editor_hint(
        self,
    ) -> None:
        hint = QLabel(
            self.i18n.tr(
                "editor.empty"
            )
        )
        hint.setObjectName(
            "gestureParam"
        )
        hint.setWordWrap(
            True
        )
        self.editor_layout.addWidget(
            hint
        )
        self.editor_layout.addStretch()

    def _clear_editor(
        self,
    ) -> None:
        self._clear_layout(
            self.editor_layout
        )

        # 双保险：布局条目清完后，再把面板下所有残留子控件
        # 一次性删除（Qt 删除控件时自动将其从布局移除）。
        # 防复发：QFormLayout 的行条目用 widget()/layout()
        # 都取不到内容，只靠布局递归会漏掉，导致编辑器叠层。
        for widget in (
            self.bindingEditor.findChildren(
                QWidget
            )
        ):
            widget.deleteLater()

        # 标题改由右栏外部 _editor_title 显示（滚动区外，不被遮挡）

        self._gesture_widgets = {}
        self._trigger_chord = ()

    def _clear_layout(
        self,
        layout,
    ) -> None:
        while layout.count():
            item = layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
                continue

            sub_layout = item.layout()

            if sub_layout is not None:
                self._clear_layout(sub_layout)

    def _load_binding_editor(
        self,
        binding: dict,
    ) -> None:
        self._clear_editor()

        trigger_action = binding[
            "trigger"
        ]
        self._trigger_chord = tuple(
            trigger_action.get(
                "keys",
                [],
            )
        )

        # 触发键卡片
        trigger_card = QFrame()
        trigger_card.setObjectName(
            "gestureCard"
        )
        self._trigger_card = trigger_card
        trigger_row = QHBoxLayout(
            trigger_card
        )
        trigger_row.setContentsMargins(
            10,
            8,
            10,
            8,
        )

        trigger_label = QLabel(
            self.i18n.tr(
                "binding.trigger"
            )
        )
        trigger_label.setObjectName(
            "gestureName"
        )
        trigger_row.addWidget(
            trigger_label
        )

        self._trigger_value = QLabel()
        self._trigger_value.setObjectName(
            "gestureValue"
        )
        trigger_row.addWidget(
            self._trigger_value,
            1,
        )

        self._trigger_button = QPushButton()
        self._trigger_button.setObjectName(
            "gestureEditBtn"
        )
        self._trigger_button.clicked.connect(
            self._record_trigger
        )
        trigger_row.addWidget(
            self._trigger_button
        )

        self._update_trigger_button()

        self.editor_layout.addWidget(
            trigger_card
        )

        self._gesture_widgets = {}

        gestures = binding["gestures"]

        taps = gestures.get(
            "taps",
            {},
        )

        for raw_count in sorted(
            taps,
            key=int,
        ):
            group = self._build_gesture_group(
                raw_count,
                self.i18n.tr(
                    "gesture.tap",
                    count=raw_count,
                ),
                taps[raw_count],
            )
            self.editor_layout.addWidget(
                group
            )

        hold_group = self._build_gesture_group(
            "hold",
            self.i18n.tr(
                "gesture.hold"
            ),
            gestures.get(
                "hold",
                {
                    "type": "disabled",
                    "keys": [],
                },
            ),
        )
        self.editor_layout.addWidget(
            hold_group
        )

        self._add_tap_button = QPushButton(
            self.i18n.tr(
                "binding.add_tap"
            )
        )
        self._add_tap_button.clicked.connect(
            self._add_tap_level
        )
        self._update_add_tap_state(
            taps
        )
        self.editor_layout.addWidget(
            self._add_tap_button
        )

        self._update_gesture_param_labels()

        self._update_monotonic_warnings()

    def _build_gesture_group(
        self,
        key: str,
        title: str,
        action: dict,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName(
            "gestureCard"
        )

        layout = QVBoxLayout(
            card
        )
        layout.setContentsMargins(
            10,
            8,
            10,
            8,
        )
        layout.setSpacing(
            6
        )

        disabled = QCheckBox(
            self.i18n.tr(
                "binding.disabled"
            )
        )
        disabled.setObjectName(
            "dangerCheck"
        )

        disabled.setChecked(
            action.get("type")
            != "chord"
        )

        chord = tuple(
            action.get(
                "keys",
                [],
            )
        ) if (
            action.get("type")
            == "chord"
        ) else ()

        head = QHBoxLayout()

        name_label = QLabel(
            f"{title}:"
        )
        name_label.setObjectName(
            "gestureName"
        )
        head.addWidget(
            name_label
        )

        value_label = QLabel()
        value_label.setObjectName(
            "gestureValue"
        )
        head.addWidget(
            value_label,
            1,
        )

        edit_button = QPushButton()
        edit_button.setObjectName(
            "gestureEditBtn"
        )
        edit_button.clicked.connect(
            lambda _checked=False,
            k=key:
            self._record_gesture(k)
        )
        head.addWidget(
            edit_button
        )

        test_button = QPushButton(
            self.i18n.tr(
                "button.test"
            )
        )
        test_button.setFixedWidth(
            68
        )
        test_button.clicked.connect(
            lambda _checked=False,
            k=key:
            self._test_gesture(k)
        )
        head.addWidget(
            test_button
        )

        if key != "hold":
            delete_button = QPushButton(
                self.i18n.tr(
                    "gesture.delete"
                )
            )
            delete_button.setObjectName(
                "gestureDeleteBtn"
            )
            delete_button.clicked.connect(
                lambda _checked=False,
                k=key:
                self._remove_tap_level(k)
            )

            head.addWidget(
                delete_button
            )

        layout.addLayout(
            head
        )

        param_row = QHBoxLayout()

        param_label = QLabel()
        param_label.setObjectName(
            "gestureParam"
        )
        param_row.addWidget(
            param_label
        )

        param_spin = QSpinBox()
        param_spin.setObjectName(
            "gestureParamSpin"
        )

        if key == "hold":
            param_label.setText(
                self.i18n.tr(
                    "binding.hold_label"
                )
            )
            param_spin.setRange(
                MIN_HOLD_THRESHOLD_MS,
                5000,
            )
        else:
            param_label.setText(
                self.i18n.tr(
                    "binding.tap1_window"
                    if key == "1"
                    else "binding.window_label"
                )
            )
            param_spin.setRange(
                MIN_DOUBLE_TAP_INTERVAL_MS,
                1000,
            )

        param_spin.setSingleStep(
            10
        )
        param_row.addWidget(
            param_spin
        )

        # 1 击（单击判定）是独立的：没有"用默认值"概念，
        # 它的数值始终由自己决定（初始值取全局默认作为起点）。
        is_tap1 = key == "1"

        global_check = None

        if not is_tap1:
            global_check = QCheckBox(
                self.i18n.tr(
                    "binding.global"
                )
            )
            global_check.setToolTip(
                self.i18n.tr(
                    "binding.global_tip"
                )
            )
            param_row.addWidget(
                global_check
            )

        param_row.addStretch()

        param_row.addWidget(
            disabled
        )

        layout.addLayout(
            param_row
        )

        # 输出行为（v2.1+）：点一下 / 连点 N 下 / 按住 N 毫秒 /
        # 按住直到松开。选"默认"不写字段（tap 手势=点一下，
        # 长按手势=按住 1 秒）。
        output_row = QHBoxLayout()

        output_label = QLabel(
            self.i18n.tr(
                "binding.output_label"
            )
        )
        output_label.setObjectName(
            "gestureParam"
        )
        output_row.addWidget(
            output_label
        )

        output_combo = QComboBox()
        output_combo.addItem(
            self.i18n.tr(
                "binding.output_default"
            ),
            "default",
        )
        output_combo.addItem(
            self.i18n.tr(
                "binding.output_tap"
            ),
            "tap",
        )
        output_combo.addItem(
            self.i18n.tr(
                "binding.output_repeat"
            ),
            "repeat",
        )
        output_combo.addItem(
            self.i18n.tr(
                "binding.output_hold"
            ),
            "hold",
        )
        output_combo.addItem(
            self.i18n.tr(
                "binding.output_hold_until"
            ),
            "hold_until_release",
        )

        repeat_spin = QSpinBox()
        repeat_spin.setRange(
            2,
            9,
        )
        repeat_spin.setValue(
            2
        )
        repeat_spin.setSuffix(
            self.i18n.tr(
                "binding.output_times"
            )
        )

        hold_output_spin = QSpinBox()
        hold_output_spin.setRange(
            100,
            60000,
        )
        hold_output_spin.setValue(
            1000
        )
        hold_output_spin.setSingleStep(
            100
        )
        hold_output_spin.setSuffix(
            self.i18n.tr(
                "unit.ms"
            )
        )

        output_row.addWidget(
            output_combo
        )
        output_row.addWidget(
            repeat_spin
        )
        output_row.addWidget(
            hold_output_spin
        )
        output_row.addStretch()

        layout.addLayout(
            output_row
        )

        def _sync_output_controls(
            index,
            combo=output_combo,
            rspin=repeat_spin,
            hspin=hold_output_spin,
        ) -> None:
            mode = combo.itemData(
                index
            )
            rspin.setVisible(
                mode == "repeat"
            )
            hspin.setVisible(
                mode == "hold"
            )

        output_combo.currentIndexChanged.connect(
            _sync_output_controls
        )
        output_combo.currentIndexChanged.connect(
            self._mark_editor_changed
        )
        repeat_spin.valueChanged.connect(
            self._mark_editor_changed
        )
        hold_output_spin.valueChanged.connect(
            self._mark_editor_changed
        )

        # 从配置恢复输出行为
        output_mode = action.get(
            "output_mode"
        )

        output_combo.setCurrentIndex(
            {
                None: 0,
                "tap": 1,
                "repeat": 2,
                "hold": 3,
                "hold_until_release": 4,
            }.get(
                output_mode,
                0,
            )
        )

        if output_mode == "repeat":
            repeat_spin.setValue(
                action.get(
                    "repeat",
                    2,
                )
            )
        elif output_mode == "hold":
            hold_output_spin.setValue(
                action.get(
                    "output_hold_ms",
                    1000,
                )
            )

        _sync_output_controls(
            output_combo.currentIndex()
        )

        # 初始值：自定义或全局
        custom = (
            action.get("hold_ms")
            if key == "hold"
            else action.get("interval_ms")
        )

        if custom is not None:
            param_spin.setValue(
                custom
            )
        else:
            settings = self._working[
                "settings"
            ]
            default_value = (
                settings["hold_threshold_ms"]
                if key == "hold"
                else settings[
                    "double_tap_interval_ms"
                ]
            )
            param_spin.setValue(
                default_value
            )

        if global_check is not None:
            global_check.setChecked(
                custom is None
            )

            def _sync_global_lock(
                checked,
                s=param_spin,
            ) -> None:
                s.setEnabled(
                    not checked
                )
                s.setToolTip(
                    (
                        self.i18n.tr(
                            "binding.global_spin_tip"
                        )
                        if checked
                        else ""
                    )
                )

            _sync_global_lock(
                global_check.isChecked()
            )

            global_check.toggled.connect(
                _sync_global_lock
            )
            global_check.toggled.connect(
                self._mark_editor_changed
            )
            global_check.toggled.connect(
                self._update_monotonic_warnings
            )

        param_spin.valueChanged.connect(
            self._mark_editor_changed
        )
        param_spin.valueChanged.connect(
            self._update_monotonic_warnings
        )

        self._gesture_widgets[key] = {
            "disabled": disabled,
            "button": edit_button,
            "value": value_label,
            "param": param_label,
            "spin": param_spin,
            "global": global_check,
            "chord": chord,
            "output_combo": output_combo,
            "repeat_spin": repeat_spin,
            "hold_output_spin": hold_output_spin,
        }

        disabled.stateChanged.connect(
            self._toggle_gesture
        )
        disabled.stateChanged.connect(
            self._mark_editor_changed
        )

        self._update_gesture_widget_state(
            key
        )

        return card

    def _update_gesture_widget_state(
        self,
        key: str,
    ) -> None:
        widgets = self._gesture_widgets[
            key
        ]

        chord = widgets["chord"]
        disabled = (
            widgets["disabled"].isChecked()
        )
        button = widgets["button"]
        value = widgets["value"]

        if disabled:
            value.setText(
                self.i18n.tr(
                    "gesture.off"
                )
            )
            button.setText(
                self.i18n.tr(
                    "gesture.edit"
                )
            )
            button.setEnabled(True)
        elif chord:
            value.setText(
                chord_display(chord)
            )
            button.setText(
                self.i18n.tr(
                    "gesture.edit"
                )
            )
            button.setEnabled(True)
        else:
            value.setText(
                self.i18n.tr(
                    "gesture.unset"
                )
            )
            button.setText(
                self.i18n.tr(
                    "gesture.set"
                )
            )
            button.setEnabled(True)

    def _update_gesture_param_labels(
        self,
    ) -> None:
        if not self._gesture_widgets:
            return

        settings = self._working[
            "settings"
        ]

        interval = settings.get(
            "double_tap_interval_ms",
            250,
        )
        hold_time = settings.get(
            "hold_threshold_ms",
            500,
        )

        for key, widgets in (
            self._gesture_widgets.items()
        ):
            g = widgets.get("global")

            # 仅"使用全局"模式下手势卡片数值跟随全局设置变化；
            # 1 击（单击判定）无全局选项，始终用自身数值。
            if g is None or not g.isChecked():
                continue

            value = (
                hold_time
                if key == "hold"
                else interval
            )

            widgets["spin"].blockSignals(
                True
            )
            widgets["spin"].setValue(
                value
            )
            widgets["spin"].blockSignals(
                False
            )

    def _update_monotonic_warnings(
        self,
    ) -> None:
        """非单调窗口仅提示不阻断：后级窗口大于前级时在卡片参数行标红。"""
        if not self._gesture_widgets:
            return

        levels = [
            (int(key), key)
            for key in self._gesture_widgets
            if key != "hold"
        ]
        levels.sort()

        warning = self.i18n.tr(
            "warning.monotonic"
        )

        prev_effective: int | None = None

        for _count, key in levels:
            widgets = self._gesture_widgets[
                key
            ]
            effective = (
                widgets["spin"].value()
            )
            param = widgets["param"]

            label_key = self.i18n.tr(
                "binding.tap1_window"
                if key == "1"
                else "binding.window_label"
            )

            if (
                prev_effective is not None
                and effective > prev_effective
            ):
                param.setText(
                    f"{label_key}  {warning}"
                )
                param.setStyleSheet(
                    "color: #E24B4A;"
                )
            else:
                param.setText(
                    label_key
                )
                param.setStyleSheet(
                    ""
                )

            prev_effective = effective

        hold = self._gesture_widgets.get(
            "hold"
        )

        if hold is not None:
            hold["param"].setText(
                self.i18n.tr(
                    "binding.hold_label"
                )
            )
            hold["param"].setStyleSheet(
                ""
            )

    def _toggle_gesture(
        self,
        *_args,
    ) -> None:
        for key in self._gesture_widgets:
            self._update_gesture_widget_state(
                key
            )

    def _update_add_tap_state(
        self,
        taps: dict,
    ) -> None:
        existing = {
            int(raw)
            for raw in taps
        }

        has_gap = any(
            candidate not in existing
            for candidate in range(
                1,
                MAX_TAP_COUNT + 1,
            )
        )

        self._add_tap_button.setEnabled(
            has_gap
        )

    def _add_tap_level(
        self,
    ) -> None:
        self._sync_controls_to_working()

        if (
            self._current_binding_index
            is None
        ):
            return

        binding = self._working_profile()[
            "bindings"
        ][
            self._current_binding_index
        ]

        taps = binding[
            "gestures"
        ]["taps"]

        existing = {
            int(raw)
            for raw in taps
        }

        for candidate in range(
            1,
            MAX_TAP_COUNT + 1,
        ):
            if candidate in existing:
                continue

            # 新连击级别 = 未设置状态（"选择热键"），不预绑任何热键
            taps[str(candidate)] = {
                "type": "chord",
                "keys": [],
            }
            break
        else:
            QMessageBox.information(
                self,
                self.i18n.tr(
                    "binding.editor"
                ),
                self.i18n.tr(
                    "binding.max_taps"
                ),
            )
            return

        self._load_binding_editor(
            binding
        )

        self._mark_editor_changed()

    def _remove_tap_level(
        self,
        key: str,
    ) -> None:
        self._sync_controls_to_working()

        if (
            self._current_binding_index
            is None
        ):
            return

        binding = self._working_profile()[
            "bindings"
        ][
            self._current_binding_index
        ]

        taps = binding[
            "gestures"
        ]["taps"]

        if len(taps) <= 1:
            QMessageBox.information(
                self,
                self.i18n.tr(
                    "binding.editor"
                ),
                self.i18n.tr(
                    "binding.min_taps"
                ),
            )
            return

        taps.pop(key, None)

        self._load_binding_editor(
            binding
        )

        self._mark_editor_changed()

    def _record_chord(
        self,
    ):
        dialog = KeyChordRecorder(
            self.engine.backend,
            self.i18n,
            self,
        )

        if (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        ):
            return dialog.keys

        return None

    def _update_trigger_button(
        self,
    ) -> None:
        if self._trigger_chord:
            self._trigger_value.setText(
                chord_display(
                    self._trigger_chord
                )
            )
            self._trigger_button.setText(
                self.i18n.tr(
                    "gesture.edit"
                )
            )
        else:
            self._trigger_value.setText(
                self.i18n.tr(
                    "gesture.unset"
                )
            )
            self._trigger_button.setText(
                self.i18n.tr(
                    "gesture.set"
                )
            )

    def _record_trigger(
        self,
    ) -> None:
        chord = self._record_chord()

        if chord is None:
            return

        canonical = canonicalize_keys(
            chord
        )

        if self._trigger_conflicts(
            canonical
        ):
            QMessageBox.warning(
                self,
                self.i18n.tr(
                    "conflict.title"
                ),
                self.i18n.tr(
                    "conflict.trigger"
                ),
            )
            return

        # 鼠标左/右键作触发键会被完全接管（点击无法到达任何程序，
        # 包括本软件自己）——确认时警告，并提示 Alt+Ctrl+F9 逃生。
        if (
            "MouseLeft" in canonical
            or "MouseRight" in canonical
        ):
            choice = QMessageBox.warning(
                self,
                self.i18n.tr(
                    "trigger.warn_mouse.title"
                ),
                self.i18n.tr(
                    "trigger.warn_mouse.message"
                ),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if (
                choice
                != QMessageBox.StandardButton.Yes
            ):
                return

        self._trigger_chord = canonical
        self._update_trigger_button()
        self._mark_editor_changed()

    def _trigger_conflicts(
        self,
        canonical: tuple[str, ...],
    ) -> bool:
        if not canonical:
            return False

        profile = self._working_profile()

        for index, other in enumerate(
            profile["bindings"]
        ):
            if (
                index
                == self._current_binding_index
            ):
                continue

            other_keys = other[
                "trigger"
            ].get(
                "keys",
                [],
            )

            if (
                other_keys
                and canonicalize_keys(
                    other_keys
                )
                == canonical
            ):
                return True

        return False

    def _record_gesture(
        self,
        key: str,
    ) -> None:
        chord = self._record_chord()

        if chord is None:
            return

        widgets = self._gesture_widgets[
            key
        ]

        widgets["chord"] = chord
        widgets["disabled"].setChecked(
            False
        )

        self._update_gesture_widget_state(
            key
        )

        self._mark_editor_changed()

    def _mark_editor_changed(
        self,
        *_args,
    ) -> None:
        # 界面加载/重建期间，控件赋值触发的信号不算用户改动——
        # 否则启动时会把控件默认状态（如"显示启动动作"未勾选）污染进
        # 工作副本，导致刚打开就误报"有未保存修改"、退出时把设置写坏。
        if getattr(
            self,
            "_loading_ui",
            False,
        ):
            return

        # 先把界面状态同步到工作副本，再与后端配置真实对比：
        # 只有真正存在差异才显示"未保存"（改回去/取消操作不应误报）。
        self._sync_controls_to_working()
        self._update_apply_highlight()

    def _update_apply_highlight(
        self,
    ) -> None:
        if (
            not hasattr(
                self,
                "_apply_button",
            )
            or self._apply_button is None
        ):
            return

        dirty = (
            self._is_dirty()
        )

        if dirty:
            self._apply_button.setEnabled(
                True
            )
            self._apply_button.setStyleSheet(
                "background-color: #1a6cff;"
                "color: #ffffff;"
                "font-weight: bold;"
            )

            self._dirty_label.setText(
                "● "
                + self.i18n.tr(
                    "status.unsaved"
                )
            )
            self._dirty_label.setStyleSheet(
                f"color: {self._theme_color('unsaved')};"
            )
            self._dirty_label.show()
        else:
            self._apply_button.setEnabled(
                False
            )
            self._apply_button.setStyleSheet(
                ""
            )
            self._dirty_label.hide()

    def _settings_changed(
        self,
        *_args,
    ) -> None:
        if getattr(
            self,
            "_loading_ui",
            False,
        ):
            return

        # 设置即时生效：防抖后提交（落盘 + 引擎即时应用）
        self._settings_timer.start()

    def _commit_settings(
        self,
    ) -> None:
        if not self._config_valid:
            return

        self._sync_settings_to_working()

        base = to_dict(
            self._config
        )

        base["settings"] = copy.deepcopy(
            self._working["settings"]
        )

        try:
            new_config = (
                validate_and_build(
                    base
                )
            )
        except ConfigError:
            return

        try:
            save_config(
                new_config
            )

            self.engine.apply_config(
                new_config,
                self.engine.profile_name,
            )
        except Exception:
            log.exception(
                "settings commit failed"
            )
            return

        old_settings = (
            self._config.settings
        )
        new_settings = (
            new_config.settings
        )

        self._show_settings_toast(
            old_settings,
            new_settings,
        )

        self._config = new_config
        self._saved = copy.deepcopy(
            to_dict(new_config)
        )

        self._sync_gesture_overlay(
            new_config.settings.enable_gesture_overlay
        )

        self._update_gesture_param_labels()

        self._apply_theme()

        new_language = (
            new_config.settings.language
        )

        if (
            self.i18n.requested_language()
            != new_language
        ):
            self.i18n.set_language(
                new_language
            )
            self._retranslate_ui()

            if self._tray is not None:
                self._tray.refresh()

        self._update_apply_highlight()

    def _sync_settings_to_working(
        self,
    ) -> None:
        settings = self._working[
            "settings"
        ]

        settings[
            "double_tap_interval_ms"
        ] = self.spinDoubleTap.value()

        settings[
            "hold_threshold_ms"
        ] = self.spinHold.value()

        settings[
            "language"
        ] = self.languageCombo.currentData()

        settings[
            "theme"
        ] = self.themeCombo.currentData()

        settings[
            "start_with_windows"
        ] = self.startupCheck.isChecked()

        settings[
            "enable_gesture_overlay"
        ] = self.overlayCheck.isChecked()

        settings[
            "auto_check_update"
        ] = self.autoCheckUpdate.isChecked()

        settings[
            "auto_update"
        ] = self.autoUpdate.isChecked()

    def _sync_current_binding(
        self,
    ) -> None:
        if (
            self._current_binding_index
            is None
            or not self._gesture_widgets
        ):
            return

        profile = self._working_profile()

        bindings = profile[
            "bindings"
        ]

        if not (
            0
            <= self._current_binding_index
            < len(bindings)
        ):
            return

        binding = bindings[
            self._current_binding_index
        ]

        # 绑定启用状态由左侧卡片勾选直接管理（_binding_enabled_toggled）

        binding["trigger"] = {
            "type": "chord",
            "keys": list(
                self._trigger_chord
            ),
        }

        gestures = binding[
            "gestures"
        ]

        for key, widgets in (
            self._gesture_widgets.items()
        ):
            chord = widgets["chord"]
            disabled = (
                widgets["disabled"].isChecked()
            )

            if disabled or not chord:
                action = {
                    "type": "disabled",
                    "keys": [],
                }
            else:
                action = {
                    "type": "chord",
                    "keys": list(chord),
                }

                # 输出行为：默认（不写字段）＝点一下/长按自动按住 1 秒
                output_mode = (
                    widgets[
                        "output_combo"
                    ].currentData()
                )

                if (
                    output_mode == "tap"
                ):
                    action[
                        "output_mode"
                    ] = "tap"
                elif (
                    output_mode == "repeat"
                ):
                    action[
                        "output_mode"
                    ] = "repeat"

                    repeat_val = (
                        widgets[
                            "repeat_spin"
                        ].value()
                    )

                    if repeat_val > 1:
                        action[
                            "repeat"
                        ] = repeat_val
                elif (
                    output_mode == "hold"
                ):
                    action[
                        "output_mode"
                    ] = "hold"
                    action[
                        "output_hold_ms"
                    ] = (
                        widgets[
                            "hold_output_spin"
                        ].value()
                    )
                elif (
                    output_mode
                    == "hold_until_release"
                ):
                    action[
                        "output_mode"
                    ] = "hold_until_release"

                if key == "hold":
                    if not widgets[
                        "global"
                    ].isChecked():
                        hold_val = (
                            widgets[
                                "spin"
                            ].value()
                        )

                        # 数值等于全局默认时不落 hold_ms，
                        # 避免"取消用默认值但没改数值"被误判为未保存修改。
                        if (
                            hold_val
                            != self._working[
                                "settings"
                            ][
                                "hold_threshold_ms"
                            ]
                        ):
                            action["hold_ms"] = (
                                hold_val
                            )
                elif (
                    widgets["global"] is None
                    or not widgets[
                        "global"
                    ].isChecked()
                ):
                    spin_val = (
                        widgets["spin"].value()
                    )

                    # 数值等于全局默认时不落 interval_ms：
                    # ① 1 击（单击判定）始终由自己决定；
                    # ② 取消"用默认值"但数值没改 → 不算改动。
                    if (
                        spin_val
                        != self._working[
                            "settings"
                        ][
                            "double_tap_interval_ms"
                        ]
                    ):
                        action["interval_ms"] = (
                            spin_val
                        )

            if key == "hold":
                gestures["hold"] = action
            else:
                gestures["taps"][key] = action

        item = self.bindingList.item(
            self._current_binding_index
        )

        if item is not None:
            self._update_binding_row(
                item,
                binding,
            )

    # ------------------------------------------------------------------
    # Chord recording (KeyChordRecorder, shared by trigger & action)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Binding operations
    # ------------------------------------------------------------------

    def _add_binding(
        self,
    ) -> None:
        self._sync_controls_to_working()

        profile = self._working_profile()

        # 新绑定 = 模板：手势默认启用（禁用改由用户手动勾选），
        # 触发键未设置（"选择热键"），由用户录制。
        profile[
            "bindings"
        ].append(
            copy.deepcopy(
                self._template_binding_dict()
            )
        )

        new_index = (
            len(
                profile[
                    "bindings"
                ]
            )
            - 1
        )

        # 注意：不能在这里手动设置 _current_binding_index = new_index。
        # _refresh_binding_list 内部的 setCurrentRow 会触发
        # _binding_selected；若索引已等于新行，选中事件被短路，
        # 新绑定编辑器永远不会加载（表现为"右边还是旧的"）。
        # 正确的顺序：先刷新列表（选中旧行，sync 写回旧绑定），
        # 再 setCurrentRow 新行 → _binding_selected 完成
        # sync(旧)→index=新→load 新绑定。
        self._refresh_binding_list()
        self.bindingList.setCurrentRow(
            new_index
        )

    def _delete_binding(
        self,
    ) -> None:
        self._sync_controls_to_working()

        if (
            self._current_binding_index
            is None
        ):
            return

        profile = self._working_profile()

        binding = profile[
            "bindings"
        ][
            self._current_binding_index
        ]

        trigger_action = binding[
            "trigger"
        ]
        trigger_keys = (
            trigger_action.get(
                "keys",
                [],
            )
        )

        trigger = (
            chord_display(
                trigger_keys
            )
            if trigger_keys
            else self.i18n.tr(
                "binding.no_trigger"
            )
        )

        box = QMessageBox(
            self
        )
        box.setWindowTitle(
            self.i18n.tr(
                "binding.delete.title"
            )
        )
        box.setText(
            self.i18n.tr(
                "binding.delete.message",
                trigger=trigger,
            )
        )
        box.setIcon(
            QMessageBox.Icon.Warning
        )

        delete_button = box.addButton(
            self.i18n.tr(
                "binding.delete.confirm"
            ),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = box.addButton(
            self.i18n.tr(
                "recorder.cancel"
            ),
            QMessageBox.ButtonRole.RejectRole,
        )
        box.setDefaultButton(
            cancel_button
        )

        box.exec()

        if (
            box.clickedButton()
            != delete_button
        ):
            return

        del profile[
            "bindings"
        ][
            self._current_binding_index
        ]

        target = (
            self._current_binding_index
        )

        # 同样先置 None 再刷新：让 setCurrentRow → _binding_selected
        # 走完整流程重载编辑器，避免短路导致残留已删除绑定的内容。
        self._current_binding_index = None

        if profile[
            "bindings"
        ]:
            target = min(
                target,
                len(
                    profile[
                        "bindings"
                    ]
                )
                - 1,
            )
        else:
            target = -1

        self._refresh_binding_list()

        if target >= 0:
            self.bindingList.setCurrentRow(
                target
            )

        # 删除后立即刷新保存按钮状态：绑定已从工作副本移除，
        # 必须高亮「保存配置」并允许点击，否则切档会被"未保存"
        # 拦截且无法保存 → 死锁。
        self._mark_editor_changed()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _load_settings(
        self,
    ) -> None:
        settings = self._working[
            "settings"
        ]

        self.spinDoubleTap.blockSignals(
            True
        )
        self.spinHold.blockSignals(
            True
        )
        self.languageCombo.blockSignals(
            True
        )
        self.themeCombo.blockSignals(
            True
        )

        self.spinDoubleTap.setValue(
            settings[
                "double_tap_interval_ms"
            ]
        )

        self.spinHold.setValue(
            settings[
                "hold_threshold_ms"
            ]
        )

        index = (
            self.languageCombo.findData(
                settings["language"]
            )
        )

        if index >= 0:
            self.languageCombo.setCurrentIndex(
                index
            )

        theme_index = (
            self.themeCombo.findData(
                settings.get(
                    "theme",
                    "system",
                )
            )
        )

        if theme_index >= 0:
            self.themeCombo.setCurrentIndex(
                theme_index
            )

        self.spinDoubleTap.blockSignals(
            False
        )
        self.spinHold.blockSignals(
            False
        )
        self.languageCombo.blockSignals(
            False
        )
        self.themeCombo.blockSignals(
            False
        )

        self.startupCheck.blockSignals(
            True
        )

        self.startupCheck.setChecked(
            settings[
                "start_with_windows"
            ]
        )

        self.startupCheck.blockSignals(
            False
        )

        self.overlayCheck.blockSignals(
            True
        )

        self.overlayCheck.setChecked(
            settings[
                "enable_gesture_overlay"
            ]
        )

        self.overlayCheck.blockSignals(
            False
        )

        self.autoCheckUpdate.blockSignals(
            True
        )

        self.autoCheckUpdate.setChecked(
            settings.get(
                "auto_check_update",
                False,
            )
        )

        self.autoCheckUpdate.blockSignals(
            False
        )

        self.autoUpdate.blockSignals(
            True
        )

        self.autoUpdate.setChecked(
            settings.get(
                "auto_update",
                False,
            )
        )

        self.autoUpdate.blockSignals(
            False
        )

    # ------------------------------------------------------------------
    # Apply / import / export
    # ------------------------------------------------------------------

    def _apply(
        self,
    ) -> None:
        if not self._config_valid:
            return

        self._sync_controls_to_working()

        try:
            new_config = validate_and_build(
                self._working
            )
        except ConfigError as exc:
            QMessageBox.critical(
                self,
                self.i18n.tr(
                    "config.invalid.title"
                ),
                self._config_error_message(
                    exc
                ),
            )
            return

        self._commit_config(
            new_config
        )

    def _commit_config(
        self,
        new_config: Config,
    ) -> None:
        old_config = (
            self._config
        )

        try:
            save_config(
                new_config
            )

            try:
                self.engine.apply_config(
                    new_config,
                    self.engine.profile_name,
                )
            except Exception:
                if old_config is not None:
                    save_config(
                        old_config
                    )
                raise

        except Exception:
            QMessageBox.critical(
                self,
                self.i18n.tr(
                    "error.title"
                ),
                self.i18n.tr(
                    "config.commit_failed"
                ),
            )
            return

        self._config = new_config
        self._config_valid = True

        self._working = copy.deepcopy(
            to_dict(
                new_config
            )
        )

        self._saved = copy.deepcopy(
            self._working
        )

        # 应用后重建控件同样屏蔽信号，避免误报"有未保存修改"
        self._loading_ui = True

        try:
            self._refresh_binding_list()
            self._load_settings()
        finally:
            self._loading_ui = False

        self.refresh_status()

        new_language = (
            new_config.settings.language
        )

        if (
            self.i18n.requested_language()
            != new_language
        ):
            self.i18n.set_language(
                new_language
            )
            self._retranslate_ui()

            if self._tray is not None:
                self._tray.refresh()

        self._sync_gesture_overlay(
            new_config.settings.enable_gesture_overlay
        )

        self.statusLabel.setText(
            "✓ "
            + self.i18n.tr(
                "status.saved"
            )
        )

        self._editor_dirty = False
        self._update_apply_highlight()

    # ------------------------------------------------------------------
    # Gesture overlay (OSD)
    # ------------------------------------------------------------------

    def _sync_gesture_overlay(
        self,
        enabled: bool,
    ) -> None:
        if enabled:
            if self._gesture_overlay is None:
                self._gesture_overlay = (
                    GestureOverlay()
                )

            self.engine.set_gesture_observer(
                self._overlay_observer
            )
            return

        self.engine.set_gesture_observer(
            None
        )

        if self._gesture_overlay is not None:
            self._gesture_overlay.hide()
            self._gesture_overlay.deleteLater()
            self._gesture_overlay = None

    def _overlay_observer(
        self,
        description: str,
    ) -> None:
        """输出弹窗内容由引擎拼好："绑定显示名: 输出动作"。"""
        if self._gesture_overlay is None:
            return

        self._gesture_overlay.show_gesture(
            description
        )

    # ------------------------------------------------------------------
    # Language / help
    # ------------------------------------------------------------------

    def attach_tray(
        self,
        tray,
    ) -> None:
        self._tray = tray
        # 同步当前主题到托盘图标，避免首帧仍是系统默认图标
        if hasattr(
            self,
            "_theme_resolved",
        ):
            tray.set_theme(
                self._theme_resolved
            )

    def toggle_pause(self) -> None:
        """全局热键 Alt+Ctrl+F9 触发：暂停/恢复切换。

        紧急逃生口——万一触发键是鼠标左键把点击全接管了，
        用户还能靠这个快捷键立刻恢复鼠标。
        """
        tray = self._tray

        if tray is None:
            return

        if self.engine.paused:
            tray._resume()
        else:
            tray._pause()

    def _show_help(
        self,
    ) -> None:
        dialog = HelpDialog(
            self.i18n,
            self,
        )

        dialog.exec()

    @staticmethod
    def _resource_path(name: str) -> str:
        import sys
        from pathlib import Path

        if getattr(
            sys,
            "frozen",
            False,
        ):
            base = Path(
                sys._MEIPASS
            )
        else:
            base = Path(
                __file__
            ).resolve().parents[2]

        return str(
            base / name
        )

    def _show_support_dialog(
        self,
    ) -> None:
        from pathlib import Path

        from PySide6.QtWidgets import (
            QDialog,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QVBoxLayout,
        )
        from PySide6.QtGui import (
            QPixmap,
        )

        dialog = QDialog(
            self
        )
        dialog.setWindowTitle(
            self.i18n.tr(
                "support.title"
            )
        )
        dialog.setObjectName(
            "supportDialog"
        )
        dialog.setFixedWidth(
            420
        )

        layout = QVBoxLayout(
            dialog
        )
        layout.setSpacing(
            10
        )
        layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        # 顶部 logo（v2 标志图，96px，随主题切换深/浅版）
        logo_path = self._logo_path_for_theme(
            self._theme_resolved
        )
        if logo_path is not None:
            logo_pixmap = QPixmap(
                logo_path
            ).scaled(
                96,
                96,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_label = QLabel()
            logo_label.setPixmap(
                logo_pixmap
            )
            logo_label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            layout.addWidget(
                logo_label
            )

        version_label = QLabel(
            self.i18n.tr(
                "support.version"
            )
        )
        version_label.setObjectName(
            "editorTitle"
        )
        version_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(
            version_label
        )

        copyright_label = QLabel(
            "Copyright (C) 2026 XKDMW"
        )
        copyright_label.setObjectName(
            "gestureParam"
        )
        copyright_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(
            copyright_label
        )

        email_label = QLabel(
            '<a href="mailto:XKDMW404@gmail.com" '
            'style="color:#1a6cff;text-decoration:none;">'
            "XKDMW404@gmail.com</a>"
        )
        email_label.setObjectName(
            "gestureParam"
        )
        email_label.setOpenExternalLinks(
            True
        )
        email_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(
            email_label
        )

        anti_piracy = QLabel(
            self.i18n.tr(
                "support.anti_piracy"
            )
        )
        anti_piracy.setObjectName(
            "antiPiracy"
        )
        anti_piracy.setWordWrap(
            True
        )
        anti_piracy.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(
            anti_piracy
        )

        intro = QLabel(
            self.i18n.tr(
                "support.text"
            )
        )
        intro.setWordWrap(
            True
        )
        intro.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(
            intro
        )

        qr_path = (
            self._resource_path(
                "assets/support_qr.jpg"
            )
        )

        if Path(
            qr_path
        ).exists():
            pixmap = QPixmap(
                qr_path
            )

            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    280,
                    280,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                qr_label = QLabel()
                qr_label.setPixmap(
                    pixmap
                )
                qr_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )
                layout.addWidget(
                    qr_label
                )

        kofi = QLabel(
            '<a href="https://ko-fi.com/xkdmw" '
            'style="color:#1a6cff;text-decoration:none;">'
            f"{self.i18n.tr('support.kofi')}</a>"
        )
        kofi.setObjectName(
            "gestureParam"
        )
        kofi.setOpenExternalLinks(
            True
        )
        kofi.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(
            kofi
        )

        close_row = QHBoxLayout()
        close_row.addStretch()

        close_button = QPushButton(
            self.i18n.tr(
                "support.close"
            )
        )
        close_button.clicked.connect(
            dialog.accept
        )
        close_row.addWidget(
            close_button
        )
        close_row.addStretch()

        layout.addLayout(
            close_row
        )

        dialog.exec()

    def _retranslate_ui(
        self,
    ) -> None:
        self.setWindowTitle(
            self.i18n.tr(
                "app.title"
            )
        )

        self._title_label.setText(
            self.i18n.tr(
                "app.title"
            )
        )

        self._left_title.setText(
            self.i18n.tr(
                "left.title"
            )
        )

        self._editor_title.setText(
            self.i18n.tr(
                "binding.editor"
            )
        )

        self._rebuild_profile_combo()

        self.refresh_status()

        self._update_apply_highlight()

        if self._profile_label is not None:
            self._profile_label.setText(
                self.i18n.tr(
                    "profile.label"
                )
            )

        for key, button in (
            self._tr_buttons.items()
        ):
            button.setText(
                self.i18n.tr(key)
            )

        self.languageCombo.setItemText(
            0,
            self.i18n.tr(
                "language.system"
            ),
        )
        self.languageCombo.setItemText(
            1,
            self.i18n.tr(
                "language.zh_CN"
            ),
        )
        self.languageCombo.setItemText(
            2,
            self.i18n.tr(
                "language.en_US"
            ),
        )

        self.themeCombo.setItemText(
            0,
            self.i18n.tr(
                "theme.system"
            ),
        )
        self.themeCombo.setItemText(
            1,
            self.i18n.tr(
                "theme.dark"
            ),
        )
        self.themeCombo.setItemText(
            2,
            self.i18n.tr(
                "theme.light"
            ),
        )

        self.startupCheck.setText(
            self.i18n.tr(
                "startup.checkbox"
            )
        )

        field_keys = {
            self.spinDoubleTap: (
                "settings.double_tap"
            ),
            self.spinHold: (
                "settings.hold"
            ),
            self.languageCombo: (
                "settings.language"
            ),
            self.themeCombo: (
                "settings.theme"
            ),
            self.startupCheck: (
                "settings.startup"
            ),
            self.overlayCheck: (
                "settings.overlay"
            ),
        }

        for i in range(
            self._settings_form.rowCount()
        ):
            field_item = (
                self._settings_form.itemAt(
                    i,
                    QFormLayout.FieldRole,
                )
            )

            label_item = (
                self._settings_form.itemAt(
                    i,
                    QFormLayout.LabelRole,
                )
            )

            if (
                field_item is None
                or label_item is None
            ):
                continue

            key = field_keys.get(
                field_item.widget()
            )

            label = label_item.widget()

            if (
                key is not None
                and label is not None
            ):
                label.setText(
                    self.i18n.tr(key)
                )

        self._add_profile_button.setText(
            self.i18n.tr(
                "profile.add"
            )
        )

        if self._settings_group is not None:
            self._settings_group.setTitle(
                self.i18n.tr(
                    "settings.group"
                )
            )

        self._refresh_binding_list()

        if (
            self._current_binding_index
            is not None
        ):
            bindings = (
                self._working_profile()[
                    "bindings"
                ]
            )

            if (
                0
                <= self._current_binding_index
                < len(bindings)
            ):
                self._load_binding_editor(
                    bindings[
                        self._current_binding_index
                    ]
                )
            else:
                self._clear_editor()
        else:
            self._clear_editor()

    def import_config(
        self,
    ) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.i18n.tr(
                "config.import.title"
            ),
            "",
            self.i18n.tr(
                "config.file_filter"
            ),
        )

        if not path:
            return

        from pathlib import Path

        try:
            config = import_config_file(
                Path(path)
            )
        except ConfigError as exc:
            QMessageBox.critical(
                self,
                self.i18n.tr(
                    "config.import.failed"
                ),
                self._config_error_message(
                    exc
                ),
            )
            return

        self._commit_config(
            config
        )

    def export_config(
        self,
    ) -> None:
        if not self._config_valid:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.tr(
                "config.export.title"
            ),
            "config.json",
            self.i18n.tr(
                "config.file_filter"
            ),
        )

        if not path:
            return

        try:
            export_config_file(
                self._config,
                __import__(
                    "pathlib"
                ).Path(path),
            )
        except Exception:
            QMessageBox.critical(
                self,
                self.i18n.tr(
                    "error.title"
                ),
                self.i18n.tr(
                    "config.export.failed"
                ),
            )

    def _restore_default(
        self,
    ) -> None:
        result = QMessageBox.question(
            self,
            self.i18n.tr(
                "config.restore.title"
            ),
            self.i18n.tr(
                "config.restore.message"
            ),
        )

        if result != (
            QMessageBox.StandardButton.Yes
        ):
            return

        self._commit_config(
            default_config()
        )

    def _test_gesture(
        self,
        gesture: str,
    ) -> None:
        self._sync_controls_to_working()

        if (
            self._current_binding_index
            is None
        ):
            return

        binding = self._working_profile()[
            "bindings"
        ][
            self._current_binding_index
        ]

        gestures = binding[
            "gestures"
        ]

        if gesture == "hold":
            action = gestures.get(
                "hold"
            )
        else:
            action = gestures.get(
                "taps",
                {},
            ).get(
                gesture
            )

        if action is None:
            return

        from multitapkey.core.config_models import (
            ActionSpec,
        )

        self.engine.execute_action_spec(
            ActionSpec(
                type=action["type"],
                keys=tuple(
                    action.get(
                        "keys",
                        [],
                    )
                ),
            )
        )

    # ------------------------------------------------------------------
    # Update check
    # ------------------------------------------------------------------

    def _check_update(
        self,
    ) -> None:
        self.update_button.setEnabled(
            False
        )
        self.update_status.setText(
            self.i18n.tr(
                "update.checking"
            )
        )

        worker = _UpdateCheckWorker()
        worker.finished.connect(
            self._on_update_done
        )

        self._update_worker = worker

        thread = threading.Thread(
            target=worker.run,
            daemon=True,
        )
        thread.start()

    def _on_update_done(
        self,
        ok: bool,
        latest: str,
        exe_url: str,
        page_url: str,
    ) -> None:
        self.update_button.setEnabled(
            True
        )

        if not ok:
            self.update_status.setText(
                self.i18n.tr(
                    "update.check_failed"
                )
            )
            return

        from multitapkey import __version__
        from multitapkey.core.updater import (
            compare_versions,
        )

        if (
            compare_versions(
                latest,
                __version__,
            )
            > 0
        ):
            self.update_status.setText(
                self.i18n.tr(
                    "update.available",
                    version=latest,
                )
            )

            box = QMessageBox(
                self
            )
            box.setWindowTitle(
                self.i18n.tr(
                    "update.title"
                )
            )
            box.setText(
                self.i18n.tr(
                    "update.available_message",
                    version=latest,
                )
            )
            box.setIcon(
                QMessageBox.Icon.Information
            )

            download_button = box.addButton(
                self.i18n.tr(
                    "update.download"
                ),
                QMessageBox.ButtonRole.AcceptRole,
            )
            box.addButton(
                QMessageBox.StandardButton.Close
            )

            box.exec()

            if (
                box.clickedButton()
                == download_button
                and page_url
            ):
                webbrowser.open(page_url)

            return

        self.update_status.setText(
            self.i18n.tr(
                "update.latest"
            )
        )

    # ------------------------------------------------------------------
    # Auto update (v2.2+)
    # ------------------------------------------------------------------

    def _maybe_auto_check_update(self) -> None:
        """启动时自动检查更新（设置「每次启动检查更新」开启才执行）。"""
        if not self._config_valid:
            return

        if not (
            self._config.settings.auto_check_update
        ):
            return

        worker = _UpdateCheckWorker()
        worker.finished.connect(
            self._on_auto_check_done
        )

        self._update_worker = worker

        thread = threading.Thread(
            target=worker.run,
            daemon=True,
        )
        thread.start()

    def _on_auto_check_done(
        self,
        ok: bool,
        latest: str,
        exe_url: str,
        page_url: str,
    ) -> None:
        from multitapkey import __version__
        from multitapkey.core.updater import (
            compare_versions,
        )

        if not ok:
            self.update_status.setText(
                self.i18n.tr(
                    "update.check_failed"
                )
            )
            return

        if (
            compare_versions(
                latest,
                __version__
            )
            <= 0
        ):
            # 已是最新：启动时不打扰用户
            return

        if (
            self._config.settings.auto_update
            and exe_url
        ):
            self.update_status.setText(
                self.i18n.tr(
                    "update.downloading"
                )
            )
            self._download_update_in_background(
                exe_url
            )
        else:
            self.update_status.setText(
                self.i18n.tr(
                    "update.available",
                    version=latest,
                )
            )

    def _download_update_in_background(
        self,
        url: str,
    ) -> None:
        """后台下载新版 exe；下载成功则退出时自动安装。"""
        import sys

        from multitapkey.core.config_store import (
            config_dir,
        )

        # 源码运行时 sys.executable 是 python.exe，不能替换——
        # 只提示有新版，回退为手动去发布页。
        if not getattr(
            sys,
            "frozen",
            False,
        ):
            self.update_status.setText(
                self.i18n.tr(
                    "update.available"
                )
            )
            return

        update_dir = (
            config_dir() / "update"
        )
        update_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        dest = (
            update_dir / "TapLayer.exe.new"
        )

        worker = _UpdateDownloadWorker(
            url,
            str(dest),
        )
        worker.finished.connect(
            self._on_update_downloaded
        )

        self._download_worker = worker
        self._pending_update_path = str(
            dest
        )

        thread = threading.Thread(
            target=worker.run,
            daemon=True,
        )
        thread.start()

    def _on_update_downloaded(
        self,
        ok: bool,
    ) -> None:
        if not ok:
            self._pending_update_path = None
            self.update_status.setText(
                self.i18n.tr(
                    "update.download_failed"
                )
            )
            return

        self.update_status.setText(
            self.i18n.tr(
                "update.downloaded"
            )
        )

    def _install_pending_update(self) -> None:
        """退出前安装已下载的更新（bat 独立进程替换 exe）。

        挂在 app.aboutToQuit：无论走关闭窗口退出还是托盘退出，
        只要有待安装的更新都会执行。
        """
        import sys

        from multitapkey.core.config_store import (
            config_dir,
        )

        path = getattr(
            self,
            "_pending_update_path",
            None,
        )

        if not path:
            return

        if not os.path.exists(path):
            return

        if not getattr(
            sys,
            "frozen",
            False,
        ):
            return

        current = sys.executable

        update_dir = (
            config_dir() / "update"
        )
        update_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        bat_path = (
            update_dir / "apply_update.bat"
        )

        # 路径需为 ASCII（cmd 使用 OEM 编码，非 ASCII 会乱码）。
        # 等 5 秒让主进程完全退出，再替换 exe，替换成功后重新启动。
        bat_content = (
            "@echo off\r\n"
            "timeout /t 5 /nobreak >nul\r\n"
            f'move /y "{current}" "{current}.old"\r\n'
            f'move /y "{path}" "{current}"\r\n'
            f'del /q "{current}.old"\r\n'
            f'start "" "{current}"\r\n'
            'del /q "%~f0"\r\n'
        )

        try:
            bat_path.write_text(
                bat_content,
                encoding="ascii",
            )
            os.startfile(str(bat_path))
        except Exception:
            log.exception(
                "failed to schedule update install"
            )

    # ------------------------------------------------------------------
    # Startup / error text
    # ------------------------------------------------------------------

    def _startup_changed(
        self,
        state: int,
    ) -> None:
        enabled = bool(state)

        backend = (
            self.startup_backend
        )

        if backend is None:
            return

        try:
            backend.set_startup(
                enabled
            )
        except Exception:
            self.startupCheck.blockSignals(
                True
            )
            self.startupCheck.setChecked(
                False
            )
            self.startupCheck.blockSignals(
                False
            )

            QMessageBox.critical(
                self,
                self.i18n.tr(
                    "startup.failed.title"
                ),
                self.i18n.tr(
                    "startup.failed.message"
                ),
            )
            return

        self._working[
            "settings"
        ][
            "start_with_windows"
        ] = enabled

    def _config_error_message(
        self,
        error: ConfigError,
    ) -> str:
        return self.i18n.tr(
            f"config.error.{error.code}",
            **error.params,
        )

    # ------------------------------------------------------------------
    # Close handling
    # ------------------------------------------------------------------

    def changeEvent(
        self,
        event,
    ) -> None:
        # 点最小化（-）→ 正常最小化到任务栏（不进托盘）
        super().changeEvent(
            event
        )

    def closeEvent(
        self,
        event,
    ) -> None:
        if self.force_exit:
            event.accept()
            return

        box = QMessageBox(
            self
        )
        box.setWindowTitle(
            self.i18n.tr(
                "close.title"
            )
        )
        box.setText(
            self.i18n.tr(
                "close.message"
            )
        )
        box.setIcon(
            QMessageBox.Icon.Question
        )

        quit_button = box.addButton(
            self.i18n.tr(
                "close.quit"
            ),
            QMessageBox.ButtonRole.AcceptRole,
        )
        tray_button = box.addButton(
            self.i18n.tr(
                "close.to_tray"
            ),
            QMessageBox.ButtonRole.RejectRole,
        )
        cancel_button = box.addButton(
            self.i18n.tr(
                "close.cancel"
            ),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        box.setDefaultButton(
            tray_button
        )

        box.exec()

        clicked = box.clickedButton()

        if clicked == quit_button:
            # 彻底退出：进程必须真正结束，不留后台残留。
            self.force_exit = True
            self.hide()
            QApplication.quit()
            event.accept()
            return

        if clicked == tray_button:
            # 点 × 选择隐藏到托盘：窗口隐藏，程序继续在后台运行。
            event.ignore()
            self.hide()
            return

        # 取消（含点弹窗右上角叉）：什么都不做，窗口保持原样。
        event.ignore()

    def showEvent(
        self,
        event,
    ) -> None:
        super().showEvent(
            event
        )
        self.refresh_status()
