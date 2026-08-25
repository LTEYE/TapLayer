"""Main PySide6 window."""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from multitapkey.core.config_models import (
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
from .capture import CaptureKeyDialog
from .help_dialog import HelpDialog


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

        self._build_ui()

        if config_error:
            self.show_config_error()

        self.refresh_all()

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

        main_layout.addWidget(
            settings
        )

        action_row = QHBoxLayout()

        for key, handler in (
            (
                "button.apply",
                self._apply,
            ),
            (
                "button.test_single",
                lambda: self._test_gesture(
                    "single"
                ),
            ),
            (
                "button.test_double",
                lambda: self._test_gesture(
                    "double"
                ),
            ),
            (
                "button.test_triple",
                lambda: self._test_gesture(
                    "triple"
                ),
            ),
            (
                "button.test_long",
                lambda: self._test_gesture(
                    "long"
                ),
            ),
        ):
            button = QPushButton(
                self.i18n.tr(key)
            )
            button.clicked.connect(
                handler
            )
            self._tr_buttons[key] = button
            action_row.addWidget(
                button
            )

        main_layout.addLayout(
            action_row
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
        return self.i18n.tr(
            "binding.summary",
            trigger=binding[
                "trigger"
            ],
            single=self._action_summary(
                binding["single"]
            ),
            double=self._action_summary(
                binding["double"]
            ),
            triple=self._action_summary(
                binding["triple"]
            ),
            long=self._action_summary(
                binding["long"]
            ),
        )

    def _action_summary(
        self,
        action: dict,
    ) -> str:
        if action["type"] == "disabled":
            return self.i18n.tr(
                "binding.disabled"
            )

        modifiers = action[
            "modifiers"
        ]

        if modifiers:
            return (
                "+".join(
                    modifiers
                    + [
                        action[
                            "key"
                        ]
                    ]
                )
            )

        return action["key"]

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

        self._trigger_button = QPushButton(
            binding["trigger"]
        )

        self._trigger_button.clicked.connect(
            self._capture_trigger
        )

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

        self._action_widgets = {}

        for gesture in (
            "single",
            "double",
            "triple",
            "long",
        ):
            group = self._build_action_editor(
                gesture,
                binding[gesture],
            )
            self.editor_layout.addWidget(
                group
            )

        self._mark_editor_changed()

    def _build_action_editor(
        self,
        gesture: str,
        action: dict,
    ) -> QGroupBox:
        group = QGroupBox(
            self.i18n.tr(
                f"gesture.{gesture}"
            )
        )

        layout = QVBoxLayout(
            group
        )

        type_combo = QComboBox()

        type_combo.addItem(
            self.i18n.tr(
                "action.disabled"
            ),
            "disabled",
        )

        type_combo.addItem(
            self.i18n.tr(
                "action.key"
            ),
            "key",
        )

        index = type_combo.findData(
            action["type"]
        )

        type_combo.setCurrentIndex(
            max(index, 0)
        )

        key_button = QPushButton()

        key_button.setProperty(
            "key_name",
            action.get("key")
        )

        key_button.setText(
            action.get("key")
            or self.i18n.tr(
                "action.capture"
            )
        )

        modifier_checks = {}

        modifier_row = QHBoxLayout()

        for modifier in (
            "Ctrl",
            "Shift",
            "Alt",
            "Win",
        ):
            check = QCheckBox(
                modifier
            )

            check.setChecked(
                modifier
                in action.get(
                    "modifiers",
                    [],
                )
            )

            modifier_checks[
                modifier
            ] = check

            modifier_row.addWidget(
                check
            )

        layout.addWidget(
            type_combo
        )
        layout.addWidget(
            key_button
        )
        layout.addLayout(
            modifier_row
        )

        self._action_widgets[
            gesture
        ] = {
            "type": type_combo,
            "key": key_button,
            "modifiers": modifier_checks,
        }

        type_combo.currentIndexChanged.connect(
            self._action_type_changed
        )

        key_button.clicked.connect(
            lambda _checked=False,
            g=gesture:
            self._capture_action(
                g
            )
        )

        for check in modifier_checks.values():
            check.stateChanged.connect(
                self._mark_editor_changed
            )

        type_combo.currentIndexChanged.connect(
            self._mark_editor_changed
        )

        self._update_action_editor_state(
            gesture
        )

        return group

    def _action_type_changed(
        self,
        _index: int,
    ) -> None:
        for gesture in self._action_widgets:
            self._update_action_editor_state(
                gesture
            )

        self._mark_editor_changed()

    def _update_action_editor_state(
        self,
        gesture: str,
    ) -> None:
        widgets = self._action_widgets[
            gesture
        ]

        enabled = (
            widgets["type"].currentData()
            == "key"
        )

        widgets["key"].setEnabled(
            enabled
        )

        for check in widgets[
            "modifiers"
        ].values():
            check.setEnabled(
                enabled
            )

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
            or not self._action_widgets
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

        binding[
            "trigger"
        ] = self._trigger_button.text()

        for gesture, widgets in (
            self._action_widgets.items()
        ):
            action_type = widgets[
                "type"
            ].currentData()

            if action_type == "disabled":
                binding[gesture] = {
                    "type": "disabled",
                    "key": None,
                    "modifiers": [],
                }
                continue

            key = widgets[
                "key"
            ].property(
                "key_name"
            )

            modifiers = [
                modifier
                for modifier, check
                in widgets[
                    "modifiers"
                ].items()
                if check.isChecked()
            ]

            binding[gesture] = {
                "type": "key",
                "key": key,
                "modifiers": modifiers,
            }

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
    # Capture
    # ------------------------------------------------------------------

    def _capture_with_dialog(
        self,
    ) -> str | None:
        dialog = CaptureKeyDialog(
            self.engine.backend,
            self.i18n,
            self,
        )

        if (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        ):
            return dialog.result_key

        return None

    def _capture_trigger(
        self,
    ) -> None:
        key = self._capture_with_dialog()

        if key is None:
            return

        self._trigger_button.setText(
            key
        )

    def _capture_action(
        self,
        gesture: str,
    ) -> None:
        key = self._capture_with_dialog()

        if key is None:
            return

        button = self._action_widgets[
            gesture
        ]["key"]

        button.setProperty(
            "key_name",
            key,
        )

        button.setText(
            key
        )

    # ------------------------------------------------------------------
    # Binding operations
    # ------------------------------------------------------------------

    def _add_binding(
        self,
    ) -> None:
        self._sync_controls_to_working()

        profile = self._working_profile()

        used = {
            binding[
                "trigger"
            ]
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
                if key not in used
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
            "key": None,
            "modifiers": [],
        }

        profile[
            "bindings"
        ].append(
            {
                "trigger": default_trigger,
                "enabled": True,
                "single": copy.deepcopy(
                    disabled
                ),
                "double": copy.deepcopy(
                    disabled
                ),
                "triple": copy.deepcopy(
                    disabled
                ),
                "long": copy.deepcopy(
                    disabled
                ),
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

        self.engine.execute_action_spec(
            self._action_from_dict(
                binding[gesture]
            )
        )

    @staticmethod
    def _action_from_dict(
        data: dict,
    ):
        from multitapkey.core.config_models import (
            ActionSpec,
        )

        return ActionSpec(
            type=data["type"],
            key=data["key"],
            modifiers=tuple(
                data["modifiers"]
            ),
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

        event.ignore()
        self.hide()

    def showEvent(
        self,
        event,
    ) -> None:
        super().showEvent(
            event
        )
        self.refresh_status()
