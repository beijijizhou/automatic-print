import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from automatic_print.batch_ui.platform.remote_machine_dialog import RemoteMachineDialog
from automatic_print.batch_ui.platform.remote_queue import (
    compact_machine_text,
    machine_workload,
    selected_batch_details,
    selection_text,
)


APP = QApplication.instance() or QApplication([])


def test_selected_batches_keep_platform_piece_counts():
    records = [
        SimpleNamespace(batch_number="100000000001", item_count=12, piece_count=30),
        SimpleNamespace(batch_number="100000000002", item_count=8, piece_count=16),
    ]
    details = selected_batch_details(records, ["100000000002"])

    assert details == [{
        "batch_number": "100000000002", "item_count": 8, "piece_count": 16,
    }]
    assert selection_text(details, ["100000000002"]) == "1批 · 8项目 · 16件"


def test_machine_workload_aligns_current_active_and_next_queue():
    machine = {
        "machine_id": "m8-id", "machine_name": "M8", "state": "running",
        "batch_name": "609180000001-48件.prn", "progress_percent": 35,
        "remaining_seconds": 600, "agent_online": True, "source_online": True,
    }
    commands = [
        _command("queued", "609180000003", 20, "2026-09-23T02:00:00Z"),
        _command("running", "609180000002", 18, "2026-09-23T01:00:00Z"),
    ]

    view = machine_workload(machine, commands)

    assert view["machine"] == "M8"
    assert "609180000001-48件.prn · 48件 · 35% · 剩余10分钟" == view["current_print"]
    assert "609180000002" in view["active_task"] and "18件" in view["active_task"]
    assert "609180000003" in view["next_task"] and "20件" in view["next_task"]
    assert "接下来" in compact_machine_text(machine, commands)


def test_machine_picker_updates_full_workload_for_selected_machine():
    machines = [
        {"machine_id": "m7-id", "machine_name": "M7", "state": "idle"},
        {"machine_id": "m8-id", "machine_name": "M8", "state": "running",
         "batch_name": "current-60件.prn", "progress_percent": 50},
    ]
    dialog = RemoteMachineDialog(machines, [
        _command("queued", "609180000004", 24, "2026-09-23T03:00:00Z"),
    ], "1批 · 10件")
    dialog.target.setCurrentIndex(1)

    assert "M8" in dialog.target.currentText()
    assert "当前打印：current-60件.prn · 60件 · 50%" in dialog.detail.text()
    assert "接下来：S2B · 609180000004 · 1批 · 2项目 · 24件" in dialog.detail.text()


def _command(status, batch, pieces, created_at):
    return {
        "target_machine_id": "m8-id", "action": "download_layout",
        "status": status, "created_at": created_at,
        "payload": {
            "platform": "S2B", "batch_numbers": [batch],
            "batch_details": [{
                "batch_number": batch, "item_count": 2, "piece_count": pieces,
            }],
        },
    }
