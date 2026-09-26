import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from automatic_print import __release_iteration__, __version__
from automatic_print.updates.source import SourceVersion
from automatic_print.ui.machine_status_board import MachineStatusPage


APP = QApplication.instance() or QApplication([])


def load_latest(page):
    page.update_panel._versions_loaded([SourceVersion(
        "a" * 40, __version__, "2026-09-26", __release_iteration__,
    )])


def test_signal_area_can_publish_latest_update_for_all_pending_machines():
    page = MachineStatusPage(fetch=lambda: [])
    load_latest(page)
    selected = []
    page.update_panel._select = selected.append
    started = []
    page.update_panel._selected_targets = lambda: [{"machine_name": "M2"}]
    page.update_panel.start_all = lambda: started.append(True) or True

    page.signal_update_button.click()

    assert page.signal_update_button.text() == "发布最新版本更新指令"
    assert page.sections.currentWidget() is page.update_section
    assert selected == [True]
    assert started == [True]
    assert not page.signal_update_button.isEnabled()
    assert "正在向 1 台电脑发布" in page.signal_result.text()


def test_signal_area_reports_when_every_machine_is_current():
    page = MachineStatusPage(fetch=lambda: [])
    load_latest(page)
    page.update_panel._select = lambda _checked: None
    page.update_panel._selected_targets = lambda: []

    page.signal_update_button.click()

    assert page.signal_update_button.isEnabled()
    assert page.signal_result.text() == "当前已登记电脑的版本与功能都已同步。"
    assert page.update_panel.summary.text() == page.signal_result.text()


def test_signal_area_loads_latest_once_then_continues_without_second_click():
    page = MachineStatusPage(fetch=lambda: [])
    starts = []
    page.update_panel.loader.start = lambda: starts.append(True) or True
    page.update_panel._selected_targets = lambda: [{"machine_name": "M2"}]
    submitted = []
    page.update_panel.start_all = lambda: submitted.append(True) or True

    page.signal_update_button.click()

    assert starts == [True]
    assert not page.signal_update_button.isEnabled()
    assert "无需再次点击" in page.signal_result.text()

    page.update_panel.loader.completed.emit([SourceVersion(
        "a" * 40, __version__, "2026-09-26", __release_iteration__,
    )])

    assert submitted == [True]
    assert "正在向 1 台电脑发布" in page.signal_result.text()


def test_completed_update_feedback_returns_to_signal_area():
    page = MachineStatusPage(fetch=lambda: [])
    page.update_panel.summary.setText("已下发 3 台 · 失败 0 台；正在等待目标机回执。")
    page.signal_update_button.setEnabled(False)

    page.update_panel.commands_submitted.emit()

    assert page.signal_update_button.isEnabled()
    assert page.signal_result.text() == page.update_panel.summary.text()
