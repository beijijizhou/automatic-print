import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.workbench_style import button_kind

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def test_workbench_action_hierarchy_and_icons(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'style.ini'), QSettings.IniFormat))
    assert window.size().width() >= 1440 and window.size().height() >= 900
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    window.show()
    APP.processEvents()
    for button in window.findChildren(QPushButton):
        assert not button.icon().isNull(), button.text()
    start = window.automation_home.start_layout_button
    assert start.property('importance') == 'primary'
    assert start.isVisible() and start.isEnabled()
    assert window.stop_generation_button.property('importance') == 'danger'
    assert not window.stop_generation_button.isEnabled()
    assert window.check_update_button.property('importance') == 'secondary'
    assert not window.settings_dialog.isVisible()
    assert window.grab().save('/private/tmp/automatic-print-ui-0.1.79.png')
    window.close()


def test_button_icon_categories():
    for text, kind in [('开始排版', 'play'), ('停止当前排版', 'stop'),
                       ('仅预览整批（不生成文件）', 'preview'),
                       ('选择图片文件夹…', 'folder'), ('添加日期', 'date'),
                       ('向左旋转', 'left'), ('打印参数设置…', 'settings')]:
        assert button_kind(text) == kind
