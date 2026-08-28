"""UI 层触发键冲突即时检查（offscreen）。"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from multitapkey.core.config_models import default_config
from multitapkey.i18n.manager import I18nManager
from multitapkey.ui.main_window import MainWindow


class FakeEngine:
    profile_name = "default"

    def __init__(self):
        self.backend = object()
        self._paused = False
        self._started = True

    @property
    def hook_failed(self):
        return not self._started

    @property
    def paused(self):
        return self._paused

    @property
    def active(self):
        return not self._paused

    def set_profile(self, name):
        self.profile_name = name

    def apply_config(self, *a, **k):
        pass

    def set_gesture_observer(self, *a, **k):
        pass

    def execute_action_spec(self, *a, **k):
        pass

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False


@pytest.fixture(scope="module")
def window():
    app = QApplication.instance() or QApplication([])
    win = MainWindow(
        engine=FakeEngine(),
        i18n=I18nManager("zh_CN"),
        config=default_config(),
        config_error=False,
        startup_backend=object(),
    )
    win.show()
    app.processEvents()
    return win


def test_trigger_conflicts_detected(window):
    window._current_binding_index = 0
    window._trigger_chord = ("F24",)
    window._sync_current_binding()

    # 第二条绑定：检测与第一条的 F24 冲突
    window._current_binding_index = 1

    assert window._trigger_conflicts(("F24",)) is True
    assert window._trigger_conflicts(("F23",)) is False
    assert window._trigger_conflicts(()) is False


def test_record_trigger_rejects_conflict(window):
    window._current_binding_index = 1
    window._trigger_chord = ()

    warned = []

    orig_warn = QMessageBox.warning
    QMessageBox.warning = staticmethod(
        lambda *a, **k: warned.append(1)
    )

    # 模拟录制器返回与已有绑定相同的 F24
    window._record_chord = lambda: ("F24",)
    window._record_trigger()

    QMessageBox.warning = orig_warn

    assert len(warned) == 1
    # 冲突被拒绝：触发键保持未设置
    assert window._trigger_chord == ()


def test_record_trigger_accepts_unique(window):
    window._current_binding_index = 1

    warned = []

    orig_warn = QMessageBox.warning
    QMessageBox.warning = staticmethod(
        lambda *a, **k: warned.append(1)
    )

    window._record_chord = lambda: ("F23",)
    window._record_trigger()

    QMessageBox.warning = orig_warn

    assert len(warned) == 0
    assert window._trigger_chord == ("F23",)


def _settings_row_labels(window):
    """字段控件 → 行标签文本（与 _retranslate_ui 同一取法）。"""
    from PySide6.QtWidgets import QFormLayout

    labels = {}

    for i in range(window._settings_form.rowCount()):
        field_item = window._settings_form.itemAt(
            i, QFormLayout.FieldRole
        )
        label_item = window._settings_form.itemAt(
            i, QFormLayout.LabelRole
        )

        if field_item is None or label_item is None:
            continue

        field = field_item.widget()
        label = label_item.widget()

        if field is not None and label is not None:
            labels[field] = label.text()

    return labels


def test_language_switch_retranslates_update_widgets(window):
    """切语言后，自动更新相关行标签与按钮必须跟着翻译（回归：漏登记导致残留中文）。"""
    i18n = window.i18n

    i18n.set_language("en_US")
    window._retranslate_ui()

    try:
        labels = _settings_row_labels(window)

        assert labels[window.autoCheckUpdate] == (
            "Check for updates on startup"
        )
        assert labels[window.autoUpdate] == "Auto-update"
        assert labels[window.update_row] == "Version"
        assert window.update_button.text() == "Check for updates"
    finally:
        # 还原语言，避免影响同 fixture 的其它用例
        i18n.set_language("zh_CN")
        window._retranslate_ui()
