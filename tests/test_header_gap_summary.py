from types import SimpleNamespace

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.layout_engine.labeling.base import header_gap
from automatic_print.ui.header_gap import build_header_gap


def test_gap_summary_shows_total_changed_existing_and_failed_counts():
    records = [
        {'minimum_mm': 40, 'added_px': 226, 'added_mm': 31.89, 'warning': ''},
        {'minimum_mm': 40, 'added_px': 227, 'added_mm': 32.04, 'warning': ''},
        {'minimum_mm': 40, 'added_px': 0, 'warning': ''},
        {'minimum_mm': 40, 'added_px': 0, 'warning': '未找到可靠分界'},
    ]
    text = header_gap.gap_summary(records)
    for expected in ('目标 40 毫米', '共 4 张', '实际扩充 2 张',
                     '原本已满足 1 张', '未能扩充 1 张',
                     '31.89–32.04 毫米'):
        assert expected in text


def test_setting_default_and_persistence(tmp_path):
    app = QApplication.instance() or QApplication([])
    prefs = QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat)
    window = SimpleNamespace(preferences=prefs)
    field = build_header_gap(window)
    assert field.value() == 40
    field.setValue(35)
    assert build_header_gap(window).value() == 35
    assert app
