import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QProgressBar

from automatic_print.ui.machine_status_board import MachineStatusPage


APP = QApplication.instance() or QApplication([])


def test_board_keeps_eleven_slots_and_renders_live_machine():
    page = MachineStatusPage(fetch=lambda: [])
    page.apply_dashboard(
        {"machines": [
            {
                "machine_name": "DTF-01",
                "department": "DTF",
                "state": "running",
                "batch_name": "BATCH-88.prn",
                "progress_percent": 42,
                "remaining_seconds": 3720,
                "heartbeat_age_seconds": 7,
                "agent_online": True,
                "source_online": True,
                "online": True,
            }
        ], "commands": []}
    )

    assert page.table.rowCount() == 11
    assert page.summary.text() == "已接入 1 / 11 · 在线 1 · 打印中 1"
    assert page.table.item(0, 0).text() == "DTF-01"
    assert page.table.item(0, 2).text() == "打印中"
    assert page.table.item(0, 3).text() == "BATCH-88.prn"
    assert page.table.item(0, 5).text() == "1小时2分钟"
    assert page.table.item(0, 6).text() == "7秒前"
    assert page.table.item(1, 2).text() == "待接入"
    assert isinstance(page.table.cellWidget(0, 4), QProgressBar)
    assert page.table.cellWidget(0, 4).value() == 42
    assert page.command_panel.submit_button.isEnabled()


def test_board_distinguishes_monitor_and_printerexp_offline():
    page = MachineStatusPage(fetch=lambda: [])
    page.apply_dashboard(
        {"machines": [
            {"machine_name": "A", "state": "stopped", "agent_online": False},
            {
                "machine_name": "B",
                "state": "stopped",
                "agent_online": True,
                "source_online": False,
            },
        ], "commands": []}
    )

    assert page.table.item(0, 2).text() == "监控离线"
    assert page.table.item(1, 2).text() == "PrintExp 离线"
    assert page.command_panel.table.rowCount() == 0
