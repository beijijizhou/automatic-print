import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from automatic_print import __release_iteration__, __version__
from automatic_print.updates.source import SourceVersion
from automatic_print.automation.api.machine_commands import runner, source_update
from automatic_print.automation.api.machine_status import commands
from automatic_print.ui.fleet_update import FleetUpdatePanel, update_state
from automatic_print.ui.fleet_update_support import verification_needed


APP = QApplication.instance() or QApplication([])


def load_versions(panel):
    panel._versions_loaded([
        SourceVersion(
            "b" * 40, __version__, "2026-09-25", __release_iteration__,
            ("新增中文版本说明。",),
        ),
        SourceVersion("a" * 40, "0.1.393", "2026-09-24", 14),
    ])


def machine(number, version="0.1.1"):
    return {
        "machine_id": f"00000000-0000-0000-0000-0000000000{number:02d}",
        "machine_name": f"M{number}", "app_version": version,
    }


def test_submit_source_update_reuses_command_and_udp_channels(monkeypatch):
    captured, notified = {}, {}
    monkeypatch.setattr(commands, "machine_id", lambda: machine(11)["machine_id"])
    monkeypatch.setattr(commands, "machine_name", lambda: "M11")
    monkeypatch.setattr(
        commands, "_call",
        lambda payload, **_options: captured.update(payload) or {"command": {"id": "update-1"}},
    )
    monkeypatch.setattr(
        commands, "notify_machine",
        lambda target, **options: notified.update(target=target, **options),
    )

    result = commands.submit_source_update(machine(1)["machine_id"], "a" * 40, "0.1.390")

    assert result["id"] == "update-1"
    assert captured["action"] == "enqueue_update"
    assert captured["payload"] == {
        "target_revision": "a" * 40, "target_version": "0.1.390",
    }
    assert notified["command_id"] == "update-1"


def test_update_panel_shows_all_eleven_version_receipts():
    panel = FleetUpdatePanel()
    load_versions(panel)
    machines = [machine(1, __version__), {**machine(2, "0.1.1"), "is_local": True}]
    command = {
        "action": "source_update", "target_machine_id": machine(2)["machine_id"],
        "status": "running", "phase": "正在安装依赖", "created_at": "2026-09-24T10:00:00Z",
    }

    panel.set_data(machines, [command])

    assert panel.table.rowCount() == 11
    assert panel.table.columnCount() == 4
    assert panel.table.item(0, 2).text() == __version__
    assert panel.table.item(0, 3).text() == "已是目标版本"
    assert panel.table.item(1, 1).text() == "M2（本机）"
    assert panel.table.item(1, 2).text() == "0.1.1"
    assert panel.table.item(1, 3).text() == "更新中 · 正在安装依赖"
    assert panel.table.item(2, 3).text() == "未接入"
    assert "已匹配 1/11" in panel.summary.text()
    assert "新增中文版本说明" in panel.release_notes.text()
    assert panel.has_active_updates()


def test_update_panel_selects_only_requested_pending_machines():
    panel = FleetUpdatePanel()
    load_versions(panel)
    panel.set_data([machine(1, __version__), machine(2), machine(3)], [])

    assert panel.table.item(0, 0).checkState() == Qt.Unchecked
    assert panel.table.item(1, 0).checkState() == Qt.Checked
    assert panel.table.item(2, 0).checkState() == Qt.Checked
    panel.table.item(1, 0).setCheckState(Qt.Unchecked)

    assert [item["machine_name"] for item in panel._selected_targets()] == ["M3"]
    assert panel.button.text() == "切换已选电脑（1）"
    panel.clear_button.click()
    assert panel._selected_targets() == []


def test_terminal_receipt_waits_for_restarted_version_report():
    target = machine(3, "0.1.1")
    command = {
        "action": "source_update", "target_machine_id": target["machine_id"],
        "status": "succeeded", "phase": "源码更新完成", "created_at": "2",
    }
    assert update_state(target, [command], "0.1.390").startswith(
        "源码已切换，等待重启回报"
    )


def test_current_version_requires_exact_capability_probe_before_acceptance():
    target = SourceVersion(
        "d" * 40, "0.1.410", "2026-09-25", 13, (), 1,
        ("probe", "source_update"),
    )
    current = machine(3, "0.1.410")

    assert verification_needed(current, [], target)
    assert update_state(
        current, [], target.version, target.revision,
        target.command_protocol, target.command_capabilities,
    ) == "版本已回报，等待功能检测"

    probe = {
        "action": "probe", "target_machine_id": current["machine_id"],
        "status": "succeeded", "created_at": "2026-09-25T10:00:00Z",
        "result": {
            "app_version": target.version,
            "source_revision": target.revision,
            "command_protocol": 1,
            "capabilities": ["probe", "source_update"],
        },
    }
    assert update_state(
        current, [probe], target.version, target.revision,
        target.command_protocol, target.command_capabilities,
    ) == "功能已确认"
    assert not verification_needed(current, [probe], target)


def test_matching_version_rejects_wrong_revision_or_missing_capability():
    current = machine(3, "0.1.410")
    base = {
        "action": "probe", "target_machine_id": current["machine_id"],
        "status": "succeeded", "created_at": "2026-09-25T10:00:00Z",
        "result": {
            "app_version": "0.1.410", "source_revision": "e" * 40,
            "command_protocol": 1, "capabilities": ["probe"],
        },
    }
    assert "提交号不一致" in update_state(
        current, [base], "0.1.410", "d" * 40, 1, ("probe",),
    )
    base["result"]["source_revision"] = "d" * 40
    assert "source_update" in update_state(
        current, [base], "0.1.410", "d" * 40, 1,
        ("probe", "source_update"),
    )


def test_panel_selects_a_published_rollback_target():
    panel = FleetUpdatePanel()
    load_versions(panel)
    panel.versions.setCurrentIndex(1)
    panel.set_data([machine(1, __version__)], [])

    assert panel.target().version == "0.1.393"
    assert panel.table.item(0, 3).text() == "待回滚"
    assert panel.button.text() == "回滚已选电脑（1）"


def test_state_ignores_receipt_for_a_different_selected_version():
    target = machine(3, __version__)
    old_command = {
        "action": "source_update", "target_machine_id": target["machine_id"],
        "status": "succeeded", "created_at": "2",
        "payload": {"target_version": __version__},
    }

    assert update_state(target, [old_command], "0.1.393") == "待回滚"


def test_update_executor_checks_pinned_revision_before_applying(monkeypatch):
    events = []
    info = SimpleNamespace(
        target="b" * 40, version="0.1.390", needs_update=True, rollback=True,
    )

    class Updater:
        def __init__(self, progress): events.append("init")
        def check(self, revision):
            events.append(("check", revision))
            return info
        def apply(self, selected): events.append(("apply", selected.target))

    monkeypatch.setattr(source_update, "SourceUpdater", Updater)
    result = source_update.execute_source_update(
        {"target_revision": "b" * 40, "target_version": "0.1.390"},
        lambda *_args, **_kwargs: None,
    )

    assert events == ["init", ("check", "b" * 40), ("apply", "b" * 40)]
    assert result["restart_pending"] is True
    assert result["rollback"] is True


def test_runner_reports_source_update_before_scheduling_restart(monkeypatch):
    events = []
    monkeypatch.setattr(runner, "get_command", lambda _command_id: {
        "action": "source_update", "payload": {"target_revision": "c" * 40},
    })
    monkeypatch.setattr(
        source_update, "execute_source_update",
        lambda *_args: events.append("apply") or {"target_version": "0.1.390"},
    )
    monkeypatch.setattr(
        runner, "update_command",
        lambda *_args, **_kwargs: events.append("receipt"),
    )
    monkeypatch.setattr(
        source_update, "schedule_monitor_restart",
        lambda: events.append("restart"),
    )

    assert runner.run_command("update-1") == 0
    assert events == ["apply", "receipt", "restart"]


def test_monitor_restart_helper_breaks_away_from_the_task_job(monkeypatch):
    if source_update.os.name != "nt":
        return
    captured = {}
    monkeypatch.setattr(
        source_update.subprocess, "Popen",
        lambda command, **options: captured.update(command=command, **options),
    )

    assert source_update.schedule_monitor_restart() is True
    flags = captured["creationflags"]
    assert flags & source_update.subprocess.DETACHED_PROCESS
    assert flags & source_update.subprocess.CREATE_BREAKAWAY_FROM_JOB
    assert captured["close_fds"] is True


def test_backend_allows_and_claims_source_update_commands():
    from pathlib import Path
    root = Path(__file__).parents[1]
    function = (root / "supabase/functions/machine-status/index.ts").read_text("utf-8")
    migration = (root / "supabase/migrations/202609240003_source_update_commands.sql").read_text("utf-8")

    assert 'action === "enqueue_update"' in function
    assert 'action: "source_update"' in function
    assert "'download_layout', 'source_update'" in migration


def test_backend_allows_short_lived_application_launch_without_printer_state():
    from pathlib import Path
    root = Path(__file__).parents[1]
    function = (root / "supabase/functions/machine-status/index.ts").read_text("utf-8")
    migration = (
        root / "supabase/migrations/202609250001_launch_application_control.sql"
    ).read_text("utf-8")

    assert '"launch_app"' in function
    assert "if (printerControl && !isAvailable(machine))" in function
    assert "action === \"launch_app\"" in function
    assert "'launch_app'" in migration
    assert "claim_machine_control" in migration
