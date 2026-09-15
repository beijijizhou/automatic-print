import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def test_secondary_tools_live_in_one_nonmodal_dialog(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'details.ini'), QSettings.IniFormat))
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    window.show()
    APP.processEvents()
    panel = window.automation_home.label_quick_panel
    details = panel.details_dialog
    assert not details.isVisible()
    assert not details.isModal()
    for tool in (panel.analysis, panel.manual_rotation, panel.read_folder_button,
                 panel.summary.cutting, window.run_log, window.automation_home.log):
        assert details.isAncestorOf(tool)
        assert not tool.isVisible()
    for tool in (panel.summary, panel.timings, panel.preview_tabs):
        assert tool.isVisible()
        assert not details.isAncestorOf(tool)
    assert window.batch_record.document() is window.run_log.document()
    assert panel.marker_examples.isVisible()
    panel.preview_tabs.setCurrentIndex(0)
    assert panel.preview_scroll.isVisible()
    assert [details.tabs.tabText(i) for i in range(details.tabs.count())] == [
        '订单与尺码', '图片检查与旋转', '切割明细', '预览与处理日志',
    ]
    panel.details_button.click()
    APP.processEvents()
    assert details.isVisible()
    assert panel.analysis.isVisible()
    details.tabs.setCurrentIndex(3)
    panel.details_button.click()
    assert details.tabs.currentIndex() == 0
    details.tabs.setCurrentIndex(3)
    window.run_log.appendPlainText('正在保存本批次')
    assert window.run_log.isVisible()
    assert '正在保存本批次' in window.run_log.toPlainText()
    buttons = details.findChildren(QPushButton)
    assert any(button.text() == '仅预览整批（不生成文件）' for button in buttons)
    details.close()
    assert panel.summary.isVisible()
    assert panel.preview_scroll.isVisible()
    window.close()
