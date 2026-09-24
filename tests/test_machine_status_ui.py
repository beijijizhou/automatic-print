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
                "machine_name": "M4",
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
    assert page.summary.text() == "已接入 1 / 11 · 可用 1 · 打印中 1"
    assert page.table.item(0, 0).text() == "M1"
    assert page.table.item(0, 2).text() == "待接入"
    assert page.table.item(3, 0).text() == "M4"
    assert page.table.item(3, 2).text() == "打印中"
    assert page.table.item(3, 3).text() == "BATCH-88.prn"
    assert page.table.item(3, 5).text() == "1小时2分钟"
    assert page.table.item(3, 6).text() == "7秒前"
    assert isinstance(page.table.cellWidget(3, 4), QProgressBar)
    assert page.table.cellWidget(3, 4).value() == 42
    assert page.command_panel.submit_button.isEnabled()
    assert not page.control_panel.start_button.isEnabled()
    assert page.control_panel.pause_button.isEnabled()
    assert page.control_panel.clean_button.text() == "清洗后自动启动"
    assert "会先暂停打印" in page.control_panel.status.text()
    assert "8 个喷头全部、强度中" in page.control_panel.status.text()
    assert page.control_panel.target.currentText() == "M4"


def test_board_distinguishes_no_feedback_and_printerexp_offline():
    page = MachineStatusPage(fetch=lambda: [])
    page.apply_dashboard(
        {"machines": [
            {"machine_name": "M1", "state": "stopped", "agent_online": False},
            {
                "machine_name": "M2",
                "state": "stopped",
                "agent_online": True,
                "source_online": False,
            },
        ], "commands": []}
    )

    assert page.table.item(0, 2).text() == "无反馈，不可用"
    assert page.table.item(1, 2).text() == "PrintExp 离线"
    assert page.command_panel.table.rowCount() == 0


def test_board_ignores_legacy_names_and_blocks_duplicate_machine_number():
    page = MachineStatusPage(fetch=lambda: [])
    page.apply_dashboard({"machines": [
        {
            "machine_id": "legacy", "machine_name": "DTF7", "state": "running",
            "agent_online": True, "source_online": True, "online": True,
            "heartbeat_age_seconds": 1,
        },
        {
            "machine_id": "m4-a", "machine_name": "M4", "state": "running",
            "agent_online": True, "source_online": True, "online": True,
            "heartbeat_age_seconds": 1,
        },
        {
            "machine_id": "m4-b", "machine_name": "m4", "state": "running",
            "agent_online": True, "source_online": True, "online": True,
            "heartbeat_age_seconds": 2,
        },
    ], "commands": []})

    assert page.summary.text() == (
        "已接入 1 / 11 · 可用 0 · 打印中 0 · 机器号冲突 1"
    )
    assert page.table.item(0, 0).text() == "M1"
    assert page.table.item(0, 2).text() == "待接入"
    assert page.table.item(3, 0).text() == "M4"
    assert page.table.item(3, 2).text() == "机器号冲突"
    assert not page.control_panel.pause_button.isEnabled()
    assert not page.control_panel.start_button.isEnabled()
    assert not page.command_panel.submit_button.isEnabled()


def test_board_only_enables_start_for_exact_ready_batch():
    page = MachineStatusPage(fetch=lambda: [])
    page.apply_dashboard({"machines": [{
        "machine_id": "ready-4", "machine_name": "M4", "state": "idle",
        "progress_percent": 0,
        "batch_name": "tangle.prn", "batch_info": {
            "printer_state": "ready", "task_name_verified": True,
        },
        "agent_online": True, "source_online": True, "online": True,
        "heartbeat_age_seconds": 1,
    }], "commands": []})

    assert page.table.item(3, 2).text() == "待打印"
    assert page.control_panel.start_button.isEnabled()
    assert not page.control_panel.pause_button.isEnabled()
    assert not page.control_panel.clean_button.isEnabled()


def test_board_stops_supabase_refresh_when_automation_is_closed():
    page = MachineStatusPage(fetch=lambda: {"machines": [], "commands": []})
    page.automation_toggle.enabled = True
    page.set_active(True)
    assert page.timer.isActive()
    assert page.timer.interval() == 60_000

    page._automation_changed(False)

    assert not page.timer.isActive()
    assert "不再访问 Supabase" in page.message.text()


def test_board_blocks_start_when_loaded_task_name_is_unverified():
    page = MachineStatusPage(fetch=lambda: [])
    page.apply_dashboard({"machines": [{
        "machine_id": "ready-4", "machine_name": "M4", "state": "idle",
        "batch_name": "609240119004.prn", "batch_info": {
            "printer_state": "ready", "task_name_verified": False,
        },
        "agent_online": True, "source_online": True, "online": True,
        "heartbeat_age_seconds": 1,
    }], "commands": []})

    assert page.table.item(3, 2).text() == "待打印（待复核）"
    assert not page.control_panel.start_button.isEnabled()


def test_board_allows_the_same_start_action_to_resume_a_paused_batch():
    page = MachineStatusPage(fetch=lambda: [])
    page.apply_dashboard({"machines": [{
        "machine_id": "paused-4", "machine_name": "M4", "state": "running",
        "progress_percent": 42, "batch_name": "tangle.prn", "batch_info": {
            "printer_state": "paused", "task_name_verified": True,
        },
        "agent_online": True, "source_online": True, "online": True,
        "heartbeat_age_seconds": 1,
    }], "commands": []})

    assert page.control_panel.start_button.text() == "继续打印"
    assert page.control_panel.start_button.isEnabled()


def test_board_exposes_shared_manual_availability_setting():
    page = MachineStatusPage(fetch=lambda: [])
    page.apply_dashboard({"machines": [{
        "machine_id": "machine-4", "machine_name": "M4", "state": "idle",
        "available": False, "source_online": True,
        "availability_override": "unavailable", "feedback_age_seconds": 99,
    }], "commands": []})

    assert page.table.item(3, 2).text() == "无反馈，不可用"
    assert page.table.horizontalHeaderItem(6).text() == "最后反馈"
    assert page.availability_control.target.currentText() == "M4"
    assert page.availability_control.availability.currentData() == "unavailable"
