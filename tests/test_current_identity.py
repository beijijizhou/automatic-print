import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt
from test_developer_mode import window, APP


def test_selected_film_and_current_child_are_highlighted_without_reading(tmp_path, monkeypatch):
    owner = window(tmp_path/'prefs.ini')
    panel = owner.automation_home.label_quick_panel
    badge = panel.current_film
    calls = []
    monkeypatch.setattr(panel.preview, 'use_folder', lambda *a: calls.append(a))
    assert '580 毫米' in badge.text()
    assert '当前选用膜' not in badge.text()
    assert owner.automation_home.batch_input_panel.isAncestorOf(badge)
    assert owner.automation_home.batch_input_panel.isAncestorOf(panel.selected_source)
    badge.film.setCurrentIndex(badge.film.findData(450))
    assert owner.cutter_settings.film.currentData() == 450
    assert badge.film.currentText() == '45 厘米膜'
    assert not panel.preview.refresh_timer.isActive()
    assert '点击开始排版' in panel.preview.detail
    badge.mode.setCurrentIndex(badge.mode.findData('single'))
    assert owner.cutter_settings.mode.currentData() == 'single'
    assert '单列切膜' in badge.mode.currentText()
    badge.film.setCurrentIndex(badge.film.findData('custom'))
    badge.custom_width.setValue(52.5)
    assert owner.cutter_settings.width_control.value() == 525
    assert badge.custom_width.value() == 52.5
    owner.cutter_settings.film.setCurrentIndex(0)
    assert '430 毫米' in badge.text()
    assert '自动多列' in badge.mode.currentText()
    owner.cutter_settings.printable.left.setValue(15)
    assert '425 毫米' in badge.text()
    assert '#dce4ef' in badge.styleSheet()
    assert badge.textInteractionFlags() & Qt.TextSelectableByMouse
    from automatic_print.ui.quick_fields import show_selected_source
    show_selected_source(panel, tmp_path/'总目录', 'multiple')
    panel.summary.start(str(tmp_path/'总目录'/'黑色'/'当前子批次'), 111)
    assert '当前子批次' in panel.summary.info.text()
    assert '111 张图片' in panel.summary.info.text()
    assert '#dbeafe' in panel.summary.info.styleSheet()
    assert '当前批次' in panel.selected_source.text()
    assert '当前子批次' in panel.selected_source.text()
    assert calls == []
    owner.show()
    APP.processEvents()
    assert badge.isVisible()
    assert not panel.summary.info.isVisible()
    assert panel.selected_source.isVisible()
    assert owner.grab().save(str(tmp_path/'automatic-print-current-identity.png'))
    owner.cutter_settings.printable.right.setValue(450)
    assert '禁止生成' in badge.text()
    assert '#ef4444' in badge.styleSheet()
    owner.close()
