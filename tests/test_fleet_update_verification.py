from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from automatic_print import __release_iteration__, __version__
from automatic_print.updates.source import SourceVersion
from automatic_print.ui import fleet_update_support
from automatic_print.ui.fleet_update import FleetUpdatePanel
from automatic_print.ui.fleet_update_support import FleetCapabilityVerifier
from automatic_print.ui.fleet_update_verification import (
    automatic_verification_needed, machine_needs_update,
)


APP = QApplication.instance() or QApplication([])


def machine(number, version="0.1.1"):
    return {
        "machine_id": f"00000000-0000-0000-0000-0000000000{number:02d}",
        "machine_name": f"M{number}", "app_version": version,
    }


def test_completed_update_automatically_requests_realtime_probe_for_local_m11(monkeypatch):
    current = {**machine(11, "0.1.429"), "is_local": True}
    update = {
        "id": "update-m11", "action": "source_update",
        "target_machine_id": current["machine_id"], "status": "succeeded",
        "created_at": "2026-09-26T10:00:00Z",
        "payload": {"target_version": "0.1.429"},
    }
    submitted = []
    verifier = FleetCapabilityVerifier(
        submit=lambda machine_id: submitted.append(machine_id) or {},
    )
    monkeypatch.setattr(
        fleet_update_support, "Thread",
        lambda **options: SimpleNamespace(
            start=lambda: options["target"](*options.get("args", ())),
        ),
    )

    assert automatic_verification_needed(current, [update], target=None)
    assert verifier.start_needed([current], [update], target=None)
    assert submitted == [current["machine_id"]]


def test_completed_update_does_not_repeat_probe_after_matching_receipt():
    current = machine(3, "0.1.429")
    update = {
        "action": "source_update", "target_machine_id": current["machine_id"],
        "status": "succeeded", "created_at": "2026-09-26T10:00:00Z",
        "payload": {"target_version": "0.1.429"},
    }
    probe = {
        "action": "probe", "target_machine_id": current["machine_id"],
        "status": "succeeded", "created_at": "2026-09-26T10:00:05Z",
        "result": {"app_version": "0.1.429"},
    }

    assert not automatic_verification_needed(current, [update, probe], target=None)


def test_automatic_feature_probe_uses_realtime_without_udp(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        fleet_update_support, "submit_probe",
        lambda machine_id, **options: captured.update(
            machine_id=machine_id, **options,
        ) or {},
    )

    fleet_update_support._submit_realtime_probe("machine-11")

    assert captured == {
        "machine_id": "machine-11", "expires_minutes": 2,
        "realtime_only": True,
    }


def test_same_version_with_wrong_revision_is_selected_for_repair():
    target = SourceVersion(
        "a" * 40, __version__, "2026-09-26", __release_iteration__, (),
        1, ("probe", "source_update"),
    )
    current = machine(2, __version__)
    probe = {
        "action": "probe", "target_machine_id": current["machine_id"],
        "status": "succeeded", "created_at": "2026-09-26T11:00:00Z",
        "result": {
            "app_version": __version__, "source_revision": "b" * 40,
            "command_protocol": 1, "capabilities": ["probe", "source_update"],
        },
    }
    panel = FleetUpdatePanel(auto_load=False)
    panel._versions_loaded([target])
    panel.set_data([current], [probe])

    assert panel.table.item(1, 3).text() == "版本号一致，但提交号不一致"
    assert panel._selected_targets() == [current]


def test_same_version_without_feature_receipt_is_selected_for_sync():
    target = SourceVersion(
        "a" * 40, __version__, "2026-09-26", __release_iteration__, (),
        1, ("probe", "source_update"),
    )
    current = machine(4, __version__)

    assert fleet_update_support.verification_needed(current, [], target)
    assert fleet_update_support.automatic_verification_needed(current, [], target)
    assert machine_needs_update(current, [], target)
