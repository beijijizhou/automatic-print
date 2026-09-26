from automatic_print.automation.api.printerexp.monitor import StatusProjector
from automatic_print.automation.api.printerexp.state import PrintExpSnapshot


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


def test_projection_prefers_new_load_receipt_over_stale_completed_snapshot():
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
