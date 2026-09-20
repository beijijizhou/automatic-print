import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from automatic_print.ui.main_window import MainWindow


def test_custom_film_updates_once_and_restores(tmp_path):
    app=QApplication.instance() or QApplication([])
    prefs=QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat)
    window=MainWindow(prefs)
    window.startup_update_timer.stop()
    cutter=window.cutter_settings
    cutter.film.setCurrentIndex(cutter.film.findData('custom'))
    cutter.custom_film.value.setValue(52.5)
    cutter.mode.setCurrentIndex(cutter.mode.findData('single'))
    assert cutter.width_control.value()==525
    assert window._layout_settings().media_width_mm==495
    assert window.generation_preview.panel.current_film.custom_width.value()==52.5
    assert not cutter.custom_film.isHidden()
    cutter.save()
    window.close()
    restored=MainWindow(prefs)
    restored.startup_update_timer.stop()
    assert restored.cutter_settings.film.currentData()=='custom'
    assert restored.cutter_settings.custom_film.value.value()==52.5
    assert restored._layout_settings().media_width_mm==495
    restored.cutter_settings.film.setCurrentIndex(restored.cutter_settings.film.findData(600))
    assert restored.cutter_settings.width_control.value()==600
    assert restored.cutter_settings.custom_film.isHidden()
    restored.cutter_settings.film.setCurrentIndex(restored.cutter_settings.film.findData('custom'))
    assert restored.cutter_settings.width_control.value()==525
    restored.close()


def test_settings_classification_matches_operation(tmp_path):
    app=QApplication.instance() or QApplication([])
    window=MainWindow(QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat))
    window.startup_update_timer.stop()
    tabs=window.print_settings_tabs
    pages={tabs.tabText(i):tabs.widget(i) for i in range(tabs.count())}
    cutter=window.cutter_settings
    assert cutter.safety.value() == 0
    assert not cutter.safety.isEnabled()
    assert window._layout_settings().cutter_safety_mm == 0
    for field in (cutter.film,cutter.custom_film,cutter.printable,cutter.knife,cutter.safety,cutter.auto_knife):
        assert pages['膜的设置'].isAncestorOf(field)
    for field in (cutter.mode,cutter.rotation_zone,cutter.quick_mode,window.spacing,window.auto_fit_width):
        assert pages['排版规则'].isAncestorOf(field)
    assert pages['标签与文字'].isAncestorOf(cutter.left_marker_lift)
    window.close()
