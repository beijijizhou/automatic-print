import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from automatic_print.ui.main_window import MainWindow


def test_failure_is_separate_and_copies_every_line(tmp_path):
    app=QApplication.instance() or QApplication([])
    window=MainWindow(QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat))
    window.department_selector.setCurrentIndex(window.department_selector.findData('dtf'))
    window.startup_update_timer.stop()
    window.show()
    summary=window.generation_preview.panel.summary
    summary.metrics.setText('正常总结：15米')
    summary.anomalies.setText('正常提示：采用原尺寸旋转')
    message='失败原因：超宽\n订单：B1\n图片参数：563×234毫米\n允许：430毫米\n'+'完整详情\n'*200
    summary.show_failure(message)
    app.processEvents()
    errors=summary.failure_panel
    assert errors.isVisible()
    assert not summary.isAncestorOf(errors)
    assert summary.metrics.text()=='正常总结：15米'
    assert summary.anomalies.text()=='正常提示：采用原尺寸旋转'
    errors.copy_button.click()
    assert app.clipboard().text()==message
    assert errors.details.toPlainText()==message
    summary.start(tmp_path)
    assert errors.isHidden() and not errors.details.toPlainText()
    window.close()
