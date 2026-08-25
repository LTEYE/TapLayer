"""Main PySide6 window."""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from multitapkey.core.chord import (
    chord_display,
)
from multitapkey.core.config_models import (
    MAX_TAP_COUNT,
    Config,
    ConfigError,
    default_config,
    to_dict,
    validate_and_build,
)
from multitapkey.core.config_store import (
    export_config as export_config_file,
    import_config as import_config_file,
    save_config,
)
from multitapkey.i18n.manager import I18nManager
from .gesture_overlay import GestureOverlay
from .help_dialog import HelpDialog
from .key_chord_recorder import KeyChordRecorder


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

        self._build_ui()

        if config_error:
            self.show_config_error()

        self.refresh_all()

        self._sync_gesture_overlay(
            self._config.settings.enable_gesture_overlay
        )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle(
            self.i18n.tr(
                "app.title"
            )
        )

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

        self.statusLabel = QLabel()
        self.statusLabel.setObjectName(
            "statusLabel"
        )

        main_layout.addWidget(
            self.statusLabel
        )

        profile_row = QHBoxLayout()

        self._profile_label = QLabel(
            self.i18n.tr(
                "profile.label"
            )
        )

        profile_row.addWidget(
            self._profile_label
        )

        self.profileCombo = QComboBox()
        self.profileCombo.setObjectName(
            "profileCombo"
        )

        self.profileCombo.currentTextChanged.connect(
            self._profile_changed
        )

        profile_row.addWidget(
            self.profileCombo
        )

        main_layout.addLayout(
            profile_row
        )

        content = QHBoxLayout()

        left = QVBoxLayout()

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

        content.addWidget(
            self.editor_scroll,
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

        self._settings_group = settings

        self.settings_layout = QFormLayout(
            settings
        )

        self.spinDoubleTap = QSpinBox()
        self.spinDoubleTap.setObjectName(
            "spinDoubleTap"
        )
        self.spinDoubleTap.setRange(
            50,
            1000,
        )
        self.spinDoubleTap.setSingleStep(
            10,
        )

        self.spinHold = QSpinBox()
        self.spinHold.setObjectName(
            "spinHold"
        )
        self.spinHold.setRange(
            100,
            5000,
        )
        self.spinHold.setSingleStep(
            10,
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

        self.startupCheck = QCheckBox(
            self.i18n.tr(
                "startup.checkbox"
            )
        )

        self.startupCheck.stateChanged.connect(
            self._startup_changed
        )

        self.overlayCheck = QCheckBox(
            self.i18n.tr(
                "settings.overlay"
            )
        )

        self.overlayCheck.stateChanged.connect(
            self._mark_editor_changed
        )

        self.settings_layout.addRow(
            self.i18n.tr(
                "settings.double_tap"
            ),
            self.spinDoubleTap,
        )

        self.settings_layout.addRow(
            self.i18n.tr(
                "settings.hold"
            ),
            self.spinHold,
        )

        self.settings_layout.addRow(
            self.i18n.tr(
                "settings.language"
            ),
            self.languageCombo,
        )

        self.settings_layout.addRow(
            self.i18n.tr(
                "settings.startup"
            ),
            self.startupCheck,
        )

        self.settings_layout.addRow(
            self.i18n.tr(
                "settings.overlay"
            ),
            self.overlayCheck,
        )

        main_layout.addWidget(
            settings
        )

        action_row = QHBoxLayout()

        apply_button = QPushButton(
            self.i18n.tr(
                "button.apply"
            )
        )
        apply_button.clicked.connect(
            self._apply
        )
        self._tr_buttons[
            "button.apply"
        ] = apply_button
        action_row.addWidget(
            apply_button
        )

        self._test_row = QHBoxLayout()

        main_layout.addLayout(
            action_row
        )
        main_layout.addLayout(
            self._test_row
        )

        io_row = QHBoxLayout()

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
        ):
            button = QPushButton(
                self.i18n.tr(key)
            )
            button.clicked.connect(
                handler
            )
            self._tr_buttons[key] = button
            io_row.addWidget(
                button
            )

        main_layout.addLayout(
            io_row
        )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def show_and_activate(
        self,
    ) -> None:
        self.show()
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

    def refresh_status(
        self,
    ) -> None:
        if self.engine.hook_failed:
            text = self.i18n.tr(
                "status.hook_failed"
            )
        elif not self._config_valid:
            text = self.i18n.tr(
                "status.config_failed"
            )
        elif self.engine.paused:
            text = self.i18n.tr(
                "status.paused"
            )
        elif self.engine.active:
            text = self.i18n.tr(
                "status.running"
            )
        else:
            text = self.i18n.tr(
                "status.paused"
            )

        self.statusLabel.setText(
            text
        )

    def refresh_all(
        self,
    ) -> None:
        self._rebuild_profile_combo()
        self._reload_working_from_config(
            preserve_profile=True
        )
        self.refresh_status()

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
        profile_name = (
            self.profileCombo.currentData()
            or "default"
        )

        return self._working[
            "profiles"
        ][profile_name]

    def _is_dirty(
        self,
    ) -> bool:
        return self._working != self._saved

    def _sync_controls_to_working(
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
            "start_with_windows"
        ] = self.startupCheck.isChecked()

        settings[
            "enable_gesture_overlay"
        ] = self.overlayCheck.isChecked()

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

        self._rebuild_profile_combo(
            current_profile=current
        )

        self._refresh_binding_list()

        self._load_settings()

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

        for name in (
            "default",
            "Gaming",
            "Work",
        ):
            self.profileCombo.addItem(
                name,
                name,
            )

        target = (
            current_profile
            or self.engine.profile_name
        )

        index = self.profileCombo.findData(
            target
        )

        if index < 0:
            index = 0

        self.profileCombo.setCurrentIndex(
            index
        )

        self.profileCombo.blockSignals(
            False
        )

    def _profile_changed(
        self,
        name: str,
    ) -> None:
        if not name:
            return

        self._sync_controls_to_working()

        if self._is_dirty():
            result = QMessageBox.question(
                self,
                self.i18n.tr(
                    "profile.discard.title"
                ),
                self.i18n.tr(
                    "profile.discard.message"
                ),
            )

            if result != (
                QMessageBox.StandardButton.Yes
            ):
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
            item = QListWidgetItem(
                self._binding_summary(
                    binding
                )
            )
            self.bindingList.addItem(
                item
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

    def _binding_summary(
        self,
        binding: dict,
    ) -> str:
        trigger_action = binding[
            "trigger"
        ]

        trigger = chord_display(
            trigger_action.get(
                "keys",
                [],
            )
        )

        gestures = binding[
            "gestures"
        ]

        parts = []

        taps = gestures.get(
            "taps",
            {},
        )

        for raw_count in sorted(
            taps,
            key=int,
        ):
            parts.append(
                f"{raw_count}:"
                f"{self._action_summary(taps[raw_count])}"
            )

        parts.append(
            "H:"
            + self._action_summary(
                gestures.get(
                    "hold",
                    {},
                )
            )
        )

        return (
            f"{trigger} → {' '.join(parts)}"
        )

    def _action_summary(
        self,
        action: dict,
    ) -> str:
        if action.get("type") != "chord":
            return self.i18n.tr(
                "binding.disabled"
            )

        return chord_display(
            action.get(
                "keys",
                [],
            )
        )

    def _binding_selected(
        self,
        row: int,
    ) -> None:
        if row < 0:
            self._clear_editor()
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

    # ------------------------------------------------------------------
    # Binding editor
    # ------------------------------------------------------------------

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

        self.bindingEditor.setTitle(
            self.i18n.tr(
                "binding.editor"
            )
        )

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

        enabled = QCheckBox(
            self.i18n.tr(
                "binding.enabled"
            )
        )
        enabled.setChecked(
            binding["enabled"]
        )

        trigger_action = binding[
            "trigger"
        ]
        self._trigger_chord = tuple(
            trigger_action.get(
                "keys",
                [],
            )
        )

        self._trigger_button = QPushButton()
        self._trigger_button.clicked.connect(
            self._record_trigger
        )
        self._update_trigger_button()

        top = QFormLayout()

        top.addRow(
            self.i18n.tr(
                "binding.enabled"
            ),
            enabled,
        )

        top.addRow(
            self.i18n.tr(
                "binding.trigger"
            ),
            self._trigger_button,
        )

        self.editor_layout.addLayout(
            top
        )

        self._enabled_widget = enabled

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

        self._rebuild_test_buttons()

        self._mark_editor_changed()

    def _build_gesture_group(
        self,
        key: str,
        title: str,
        action: dict,
    ) -> QGroupBox:
        group = QGroupBox(
            title
        )

        layout = QVBoxLayout(
            group
        )

        disabled = QCheckBox(
            self.i18n.tr(
                "binding.disabled"
            )
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

        button = QPushButton()

        button.clicked.connect(
            lambda _checked=False,
            k=key:
            self._record_gesture(k)
        )

        self._gesture_widgets[key] = {
            "disabled": disabled,
            "button": button,
            "chord": chord,
        }

        if key != "hold":
            header = QHBoxLayout()

            delete_button = QPushButton(
                "✕"
            )
            delete_button.setToolTip(
                self.i18n.tr(
                    "binding.remove_tap"
                )
            )
            delete_button.setFixedWidth(
                28
            )
            delete_button.setStyleSheet(
                "background-color: #d33;"
                "color: #ffffff;"
                "font-weight: bold;"
                "border: none;"
            )
            delete_button.clicked.connect(
                lambda _checked=False,
                k=key:
                self._remove_tap_level(k)
            )

            header.addStretch()
            header.addWidget(
                delete_button
            )

            layout.addLayout(
                header
            )

        disabled.stateChanged.connect(
            self._toggle_gesture
        )
        disabled.stateChanged.connect(
            self._mark_editor_changed
        )

        layout.addWidget(
            disabled
        )
        layout.addWidget(
            button
        )

        self._update_gesture_widget_state(
            key
        )

        return group

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

        if disabled or not chord:
            button.setText(
                self.i18n.tr(
                    "action.select"
                )
            )
            button.setEnabled(
                not disabled
            )
        else:
            button.setText(
                chord_display(chord)
            )
            button.setEnabled(True)

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
        count = max(
            (
                int(raw)
                for raw in taps
            ),
            default=0,
        )

        self._add_tap_button.setEnabled(
            count < MAX_TAP_COUNT
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

        count = max(
            (
                int(raw)
                for raw in taps
            ),
            default=0,
        )

        if count >= MAX_TAP_COUNT:
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

        taps[str(count + 1)] = {
            "type": "disabled",
            "keys": [],
        }

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

    def _rebuild_test_buttons(
        self,
    ) -> None:
        while self._test_row.count():
            item = self._test_row.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        if (
            self._current_binding_index
            is None
        ):
            self._test_row.addStretch()
            return

        bindings = self._working_profile()[
            "bindings"
        ]

        if not (
            0
            <= self._current_binding_index
            < len(bindings)
        ):
            self._test_row.addStretch()
            return

        binding = bindings[
            self._current_binding_index
        ]

        taps = binding[
            "gestures"
        ].get(
            "taps",
            {},
        )

        for raw_count in sorted(
            taps,
            key=int,
        ):
            button = QPushButton(
                self.i18n.tr(
                    "gesture.tap",
                    count=raw_count,
                )
            )
            button.clicked.connect(
                lambda _checked=False,
                c=raw_count:
                self._test_gesture(c)
            )
            self._test_row.addWidget(
                button
            )

        hold_button = QPushButton(
            self.i18n.tr(
                "gesture.hold"
            )
        )
        hold_button.clicked.connect(
            lambda _checked=False:
            self._test_gesture("hold")
        )
        self._test_row.addWidget(
            hold_button
        )

        self._test_row.addStretch()

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
            self._trigger_button.setText(
                chord_display(
                    self._trigger_chord
                )
            )
        else:
            self._trigger_button.setText(
                self.i18n.tr(
                    "action.select"
                )
            )

    def _record_trigger(
        self,
    ) -> None:
        chord = self._record_chord()

        if chord is None:
            return

        self._trigger_chord = chord
        self._update_trigger_button()
        self._mark_editor_changed()

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
        return

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

        binding[
            "enabled"
        ] = self._enabled_widget.isChecked()

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

            if key == "hold":
                gestures["hold"] = action
            else:
                gestures["taps"][key] = action

        self.bindingList.blockSignals(
            True
        )

        if (
            0
            <= self._current_binding_index
            < self.bindingList.count()
        ):
            self.bindingList.item(
                self._current_binding_index
            ).setText(
                self._binding_summary(
                    binding
                )
            )

        self.bindingList.blockSignals(
            False
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

        used = {
            tuple(
                binding[
                    "trigger"
                ].get(
                    "keys",
                    [],
                )
            )
            for binding in profile[
                "bindings"
            ]
        }

        default_trigger = next(
            (
                key
                for key in (
                    "F24",
                    "F23",
                    "F22",
                    "F21",
                )
                if (key,) not in used
            ),
            None,
        )

        if default_trigger is None:
            QMessageBox.information(
                self,
                self.i18n.tr(
                    "binding.add.title"
                ),
                self.i18n.tr(
                    "binding.add.no_key"
                ),
            )
            return

        disabled = {
            "type": "disabled",
            "keys": [],
        }

        profile[
            "bindings"
        ].append(
            {
                "trigger": {
                    "type": "chord",
                    "keys": [
                        default_trigger
                    ],
                },
                "enabled": True,
                "gestures": {
                    "taps": {
                        "1": copy.deepcopy(
                            disabled
                        ),
                    },
                    "hold": copy.deepcopy(
                        disabled
                    ),
                },
            }
        )

        self._current_binding_index = (
            len(
                profile[
                    "bindings"
                ]
            )
            - 1
        )

        self._refresh_binding_list()
        self.bindingList.setCurrentRow(
            self._current_binding_index
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

        del profile[
            "bindings"
        ][
            self._current_binding_index
        ]

        if profile[
            "bindings"
        ]:
            self._current_binding_index = min(
                self._current_binding_index,
                len(
                    profile[
                        "bindings"
                    ]
                )
                - 1,
            )
        else:
            self._current_binding_index = None

        self._refresh_binding_list()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _load_settings(
        self,
    ) -> None:
        settings = self._working[
            "settings"
        ]

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

        self._refresh_binding_list()
        self._load_settings()
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
                self._gesture_overlay.show_gesture
            )
            return

        self.engine.set_gesture_observer(
            None
        )

        if self._gesture_overlay is not None:
            self._gesture_overlay.hide()
            self._gesture_overlay.deleteLater()
            self._gesture_overlay = None

    # ------------------------------------------------------------------
    # Language / help
    # ------------------------------------------------------------------

    def attach_tray(
        self,
        tray,
    ) -> None:
        self._tray = tray

    def _show_help(
        self,
    ) -> None:
        dialog = HelpDialog(
            self.i18n,
            self,
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

        self.refresh_status()

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
            self.startupCheck: (
                "settings.startup"
            ),
            self.overlayCheck: (
                "settings.overlay"
            ),
        }

        for i in range(
            self.settings_layout.rowCount()
        ):
            field_item = (
                self.settings_layout.itemAt(
                    i,
                    QFormLayout.FieldRole,
                )
            )

            label_item = (
                self.settings_layout.itemAt(
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
            # 最小化到托盘：窗口隐藏，程序继续在后台运行。
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
