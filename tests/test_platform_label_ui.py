import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton
from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def test_platform_and_sequence_default_and_persist(tmp_path):
    prefs = QSettings(str(tmp_path/'platform.ini'), QSettings.IniFormat)
    prefs.setValue('label/text_template', '自定义标签')
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    panel = window.automation_home.label_quick_panel
    assert panel.platform.currentText() == '隆丰'
    assert panel.sequence.isChecked()
    assert window._layout_settings().platform_name == '隆丰'
    assert window._layout_settings().platform_reuse_qr
    assert panel.platform_font_height.value() == 6
    panel.platform_font_height.setValue(4.5)
    assert window.label_settings.platform_font_height.value() == 4.5
    assert window._layout_settings().label_sequence_enabled
    assert panel.text.text() == '自定义标签'
    assert panel.platform.findText('蜂鸟') == -1
    assert window._layout_settings().label_machine_enabled
    assert not any(b.text() == '添加机器号' for b in window.findChildren(QPushButton))
    panel.platform.setCurrentText('测试平台')
    panel.machine.setCurrentIndex(panel.machine.findText('M11'))
    panel.sequence.setChecked(False)
    window.close()
    reopened = MainWindow(prefs)
    WINDOWS.append(reopened)
    reopened.startup_update_timer.stop()
    assert reopened._layout_settings().platform_name == '测试平台'
    assert reopened._layout_settings().platform_font_height_mm == 4.5
    assert reopened._layout_settings().machine_number == 'M11'
    assert not reopened._layout_settings().label_sequence_enabled
    assert reopened.label_settings.text_template.text() == '自定义标签'
    reopened.close()


def test_gap_defaults_follow_platform_and_remain_editable(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'gap-platform.ini'), QSettings.IniFormat))
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    mode = window.cutter_settings.mode
    mode.setCurrentIndex(mode.findData('dual'))
    platform = window.automation_home.label_quick_panel.platform

    assert platform.currentText() == '隆丰'
    assert not window.quick_membrane_gap_enabled.isChecked()
    assert window._layout_settings().membrane_gap_mm == 0
    for name in ('S2B', 'Haloo', '测试平台'):
        platform.setCurrentText(name)
        assert window.quick_membrane_gap_enabled.isChecked()
        assert window.quick_membrane_gap.value() == 40
        assert window._layout_settings().membrane_gap_mm == 40
        if name == 'S2B':
            assert window.combine_bulk_batches.isChecked()

    window.quick_membrane_gap.setValue(45)
    assert window._layout_settings().membrane_gap_mm == 45
    window.quick_membrane_gap_enabled.setChecked(False)
    assert window._layout_settings().membrane_gap_mm == 0
    platform.setCurrentText('隆丰')
    assert not window.quick_membrane_gap_enabled.isChecked()
    assert window.quick_membrane_gap.value() == 40
    assert window._layout_settings().membrane_gap_mm == 0
    window.close()


def test_saved_longfeng_gap_override_is_not_replaced_by_default(tmp_path):
    prefs = QSettings(str(tmp_path/'longfeng-gap.ini'), QSettings.IniFormat)
    prefs.setValue('label/platform_name', '隆丰')
    prefs.setValue('layout/membrane_gap_enabled', True)
    prefs.setValue('layout/membrane_gap_mm', 45)
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    assert window.membrane_gap_enabled.isChecked()
    assert window.membrane_gap.value() == 45
    assert window._layout_settings().membrane_gap_mm == 45
    window.developer_mode_checkbox.setChecked(True)
    window.developer_mode_checkbox.setChecked(False)
    assert window.membrane_gap_enabled.isChecked()
    assert window._layout_settings().membrane_gap_mm == 45
    window.close()


def test_platform_label_can_be_disabled_without_disabling_cutter_marks(tmp_path):
    prefs = QSettings(str(tmp_path/'platform-toggle.ini'), QSettings.IniFormat)
    prefs.setValue('developer/enabled', True)
    prefs.setValue('department/current', 'dtf')
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    mode = window.cutter_settings.mode.findData('dual')
    window.cutter_settings.mode.setCurrentIndex(mode)

    panel = window.automation_home.label_quick_panel
    assert panel.platform_enabled.isVisibleTo(window)
    panel.platform_enabled.setChecked(False)
    settings = window._layout_settings()

    assert settings.platform_name == ''
    assert settings.color_block_enabled
    assert settings.cutter_left_marker_external
    window.close()


def test_cutter_marks_and_platform_labels_share_one_group_but_toggle_independently(tmp_path):
    prefs = QSettings(str(tmp_path/'marker-toggle.ini'), QSettings.IniFormat)
    prefs.setValue('developer/enabled', True)
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    panel = window.automation_home.label_quick_panel
    mode = window.cutter_settings.mode
    mode.setCurrentIndex(mode.findData('dual'))

    assert panel.cutter_marker_enabled.isChecked()
    assert panel.platform_enabled.isChecked()
    panel.cutter_marker_enabled.setChecked(False)
    assert mode.currentData() == 'free'
    assert window._layout_settings().platform_name == '隆丰'
    assert not window._layout_settings().color_block_enabled

    panel.cutter_marker_enabled.setChecked(True)
    assert mode.currentData() == 'dual'
    assert window._layout_settings().color_block_enabled
    window.close()


def test_old_erp_selection_is_corrected_and_new_manual_label_starts_empty(tmp_path):
    prefs = QSettings(str(tmp_path/'old.ini'), QSettings.IniFormat)
    prefs.setValue('label/platform_name', '蜂鸟')
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    assert window.label_settings.platform.currentText() == '隆丰'
    assert window.label_settings.text_template.text() == ''
    sample = window.label_settings.preview.sample_text()
    assert sample.endswith('M1')
    assert '正序 12/20' in sample and '倒序 9/20' in sample
    window.close()


def test_real_preview_includes_platform_and_size_in_separate_label(tmp_path):
    from test_platform_labels import separate_label_source, settings
    from automatic_print.layout_engine import generate_layout
    path = separate_label_source(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    payloads = []
    generate_layout([path], tmp_path/'out', settings(
        platform_reuse_qr=True, preserve_header_gap=True,
    ), plan_ready=payloads.append)
    window = MainWindow(QSettings(str(tmp_path/'preview.ini'), QSettings.IniFormat))
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    window.show()
    controller = window.generation_preview
    controller.start()
    controller.ready(payloads[0])
    APP.processEvents()
    preview = controller.preview
    preview.grab()
    p = preview.planned[0][1]
    assert p.platform_height_px == 0
    assert p.number_height_px > 0
    assert '隆丰 · M' in preview.batch_labels[p.sequence_number]
    preview.overview = False
    controller.show_pair(0)
    assert not preview.badges[path].isNull()
    assert not preview.platform_badges
    controller.end()
    window.close()
