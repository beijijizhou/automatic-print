import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from automatic_print.ui.machine_status_board import MachineStatusPage


APP = QApplication.instance() or QApplication([])


def test_signal_area_can_publish_latest_update_for_all_pending_machines():
    page = MachineStatusPage(fetch=lambda: [])
    selected = []
    page.update_panel._select = selected.append
    started = []
    page.update_panel.start_all = lambda: started.append(True)

    page.signal_update_button.click()

    assert page.signal_update_button.text() == "发布最新版本更新指令"
    assert page.sections.currentWidget() is page.update_section
    assert selected == [True]
    assert started == [True]
