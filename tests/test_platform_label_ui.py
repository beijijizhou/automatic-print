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


def test_real_preview_includes_platform_beside_qr(tmp_path):
    from test_platform_labels import qr_image, settings
    from automatic_print.layout import generate_layout
    path = qr_image(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    payloads = []
    generate_layout([path], tmp_path/'out', settings(), plan_ready=payloads.append)
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
    assert p.platform_height_px > 0
    assert ('隆丰', p.platform_height_px) in preview.platform_badges
    assert not preview.platform_badges[('隆丰', p.platform_height_px)].isNull()
    controller.end()
    window.close()
