import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
OWNERS = []


def test_segment_settings_default_and_persistence(tmp_path):
    prefs = QSettings(str(tmp_path/'segments.ini'), QSettings.IniFormat)
    window = MainWindow(prefs)
    OWNERS.append(window)
    window.startup_update_timer.stop()
    assert window._layout_settings().output_parts == 1
    window.segmented_output.parts.setValue(3)
    window.segmented_output.workers.setValue(1)
    window.segmented_output.memory.setValue(1024)
    assert window._layout_settings().output_parts == 3
    window.close()
    restored = MainWindow(prefs)
    OWNERS.append(restored)
    restored.startup_update_timer.stop()
    assert restored._layout_settings().output_parts == 3
    assert restored._layout_settings().save_parallelism == 1
    assert restored._layout_settings().save_memory_mb == 1024
    restored.close()
