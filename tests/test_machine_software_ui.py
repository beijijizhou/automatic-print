import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from automatic_print.ui.machine_status_board import MachineStatusPage


APP = QApplication.instance() or QApplication([])


def test_automatic_print_columns_and_controls_are_developer_only():
    page = MachineStatusPage(fetch=lambda: [])
    page.update_panel.loader.start = lambda: False

    assert all(page.table.isColumnHidden(column) for column in (6, 7, 8))
    assert not page.update_panel.isVisibleTo(page)
    assert not page.signal_update_button.isVisibleTo(page)
    assert not page.software_launch_panel.isVisibleTo(page)

    page.set_developer_mode(True)

    assert all(not page.table.isColumnHidden(column) for column in (6, 7, 8))
    assert not page.update_panel.isHidden()
    assert not page.signal_update_button.isHidden()
    assert not page.software_launch_panel.isHidden()
    assert page.table.horizontalHeaderItem(1).text() == "机器｜PrintExp"
    assert page.table.horizontalHeaderItem(6).text() == "软件｜AutomaticPrint"
