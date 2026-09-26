from automatic_print.automation.api.machine_status import identity
from automatic_print.automation.api.printerexp.monitor import StatusProjector
from automatic_print.automation.api.printerexp.state import PrintExpSnapshot


def test_persisted_machine_number_is_shared_outside_registry(tmp_path, monkeypatch):
    target = tmp_path / "machine-slot-v2"
    monkeypatch.setattr(identity, "machine_slot_file", lambda: target)

    assert identity.bind_machine_slot("m11") == "M11"
    assert target.read_text(encoding="utf-8") == "M11"
    assert identity.bound_machine_number() == "M11"


def test_background_binding_is_not_overwritten_by_legacy_machine_name(tmp_path, monkeypatch):
    legacy = tmp_path / "machine-name"
    old_binding = tmp_path / "machine-binding"
    slot = tmp_path / "machine-slot-v2"
    monkeypatch.setattr(identity, "machine_name_file", lambda: legacy)
    monkeypatch.setattr(identity, "machine_slot_file", lambda: slot)
    identity.bind_machine_slot("M11")
    legacy.write_text("M1", encoding="utf-8")
    old_binding.write_text("M1", encoding="utf-8")

    assert identity.machine_name() == "M11"


def test_machine_name_requires_explicit_v2_binding(monkeypatch):
    monkeypatch.setattr(identity, "bound_machine_number", lambda: "")
    monkeypatch.setenv("AUTOMATIC_PRINT_MACHINE_NAME", "m9")
    assert identity.machine_name() == "未设置机器号"


def test_printerexp_projection_distinguishes_idle_and_offline():
    projector = StatusProjector()
    idle = projector.project(
        PrintExpSnapshot("job", 100, "DONE.prn", "0922", 1), True, clock=1
    )
    offline = projector.project(None, False, clock=2)

    assert idle["state"] == "idle"
    assert idle["progress_percent"] == 100
    assert offline["state"] == "stopped"
    assert offline["source_online"] is False


def test_printerexp_projection_prefers_new_load_receipt_over_stale_completed_snapshot():
    status = StatusProjector().project(
        PrintExpSnapshot("old", 100, "tangle.prn", "old", 100),
        True,
        printer_state="ready",
        loaded_task={
            "task_file": "609240119004.prn", "loaded_at": 101,
            "task_name_verified": False, "verification": "load_dialog_closed",
        },
        clock=1,
    )

    assert status["batch_name"] == "609240119004.prn"
    assert status["progress_percent"] == 0
    assert status["batch_info"]["task_name_verified"] is False
    assert status["batch_info"]["task_source"] == "load_receipt"
    assert "复核" in status["phase"]
