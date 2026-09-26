import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from automatic_print.ui.machine_status_board import MachineStatusPage


APP = QApplication.instance() or QApplication([])


def test_status_board_aligns_active_and_next_task_with_machine():
    page = MachineStatusPage(fetch=lambda: [])
    machine = {
        "machine_id": "m8-id", "machine_name": "M8", "state": "running",
        "batch_name": "current-40件.prn", "progress_percent": 25,
        "agent_online": True, "source_online": True, "online": True,
        "heartbeat_age_seconds": 2,
    }
    page.apply_dashboard({"machines": [machine], "commands": [
        _command("running", "609180000010", 18, "2026-09-23T01:00:00Z",
                 phase="正在下载生产图 · 37%"),
        _command("queued", "609180000011", 30, "2026-09-23T02:00:00Z"),
    ]})

    assert page.table.columnCount() == 9
    assert page.table.item(7, 2).text() == "current-40件.prn"
    assert "609180000010" in page.table.item(7, 8).text()
    assert "18件" in page.table.item(7, 8).text()
    assert "正在下载生产图 · 37%" in page.table.item(7, 8).text()
    assert page.table.item(7, 8).toolTip() == page.table.item(7, 8).text()
    assert "609180000011" in page.table.item(7, 8).text()
    assert "30件" in page.table.item(7, 8).text()
    assert page.update_timer.isActive()


def _command(status, batch, pieces, created_at, phase=""):
    return {
        "target_machine_id": "m8-id", "action": "download_layout",
        "status": status, "created_at": created_at, "phase": phase,
        "payload": {
            "platform": "隆丰", "batch_numbers": [batch],
            "batch_details": [{
                "batch_number": batch, "item_count": pieces, "piece_count": pieces,
            }],
        },
    }
