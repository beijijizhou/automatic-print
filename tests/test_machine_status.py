import json
from threading import Event

from automatic_print.automation.api.machine_status import client
from automatic_print.automation.api.machine_status import commands
from automatic_print.automation.api.machine_status import identity
from automatic_print.automation.api.machine_status.reporter import MachineStatusReporter
from automatic_print.automation.api.printerexp.monitor import StatusProjector
from automatic_print.automation.api.printerexp.state import read_snapshot


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, *_args):
        return json.dumps(self.body).encode("utf-8")


def test_report_uses_stable_identity_and_restricted_header(monkeypatch):
    captured = {}

    def open_request(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response({"machine": {"online": True}})

    monkeypatch.setattr(client, "machine_id", lambda: "d9428888-122b-4c26-a127-3eafad1f5270")
    monkeypatch.setattr(client, "machine_name", lambda: "DTF-01")
    monkeypatch.setattr(client, "urlopen", open_request)
    result = client.report_machine(
        {"state": "running", "department": "DTF", "progress_percent": 42},
        endpoint="https://example.test/machine-status",
        access_key="factory-key",
        timeout=3,
    )

    assert result["machine"]["online"] is True
    assert captured["payload"]["machine_name"] == "DTF-01"
    assert captured["payload"]["progress_percent"] == 42
    assert captured["headers"]["X-automatic-print-key"] == "factory-key"
    assert captured["timeout"] == 3


def test_reporter_sends_without_blocking_caller():
    delivered = Event()
    snapshots = []

    def send(snapshot):
        snapshots.append(snapshot)
        delivered.set()

    reporter = MachineStatusReporter(send=send, minimum_interval=0)
    reporter.publish(state="running", progress_percent=15)

    assert delivered.wait(2)
    assert snapshots == [{"state": "running", "progress_percent": 15}]
    assert reporter.last_error == ""
    reporter.close()


def test_backend_contract_keeps_unknown_eta_nullable():
    migration = (
        __import__("pathlib").Path(__file__).parents[1]
        / "supabase/migrations/202609220001_machine_status.sql"
    ).read_text(encoding="utf-8")
    function = (
        __import__("pathlib").Path(__file__).parents[1]
        / "supabase/functions/machine-status/index.ts"
    ).read_text(encoding="utf-8")
    printerexp_migration = (
        __import__("pathlib").Path(__file__).parents[1]
        / "supabase/migrations/202609220002_printerexp_status.sql"
    ).read_text(encoding="utf-8")
    command_migration = (
        __import__("pathlib").Path(__file__).parents[1]
        / "supabase/migrations/202609230001_machine_commands.sql"
    ).read_text(encoding="utf-8")
    control_migration = (
        __import__("pathlib").Path(__file__).parents[1]
        / "supabase/migrations/202609230002_printer_controls.sql"
    ).read_text(encoding="utf-8")
    urgent_control_migration = (
        __import__("pathlib").Path(__file__).parents[1]
        / "supabase/migrations/202609230003_urgent_printer_controls.sql"
    ).read_text(encoding="utf-8")

    assert "remaining_seconds integer" in migration
    assert "progress_percent smallint" in migration
    assert 'action === "report"' in function
    assert 'action === "list"' in function
    assert "stale_after_seconds" in function
    assert "source_online boolean" in printerexp_migration
    assert "agent_online" in function
    assert 'action === "enqueue_command"' in function
    assert 'action === "claim_command"' in function
    assert "create table if not exists public.machine_commands" in command_migration
    assert "for update skip locked" in command_migration
    assert "pause_print" in function and "clean_resume" in function
    assert "pause_print" in control_migration and "clean_resume" in control_migration
    assert 'action === "send_control"' in function
    assert 'action === "claim_control"' in function
    assert '"S2B"' in function
    assert "claim_machine_control" in urgent_control_migration
    assert "action = 'download_layout'" in urgent_control_migration


def test_submit_command_sends_target_batches_and_settings(monkeypatch):
    captured = {}
    monkeypatch.setattr(commands, "machine_id", lambda: "d9428888-122b-4c26-a127-3eafad1f5270")
    monkeypatch.setattr(commands, "machine_name", lambda: "CONTROL-01")

    def call(payload, **options):
        captured.update(payload)
        captured["options"] = options
        return {"command": {"id": "command-1"}}

    monkeypatch.setattr(commands, "_call", call)
    result = commands.submit_command(
        "b9428888-122b-4c26-a127-3eafad1f5271",
        "Haloo",
        ["609231234567"],
        {"dpi": 300},
        generate_prn=True,
    )

    assert result["id"] == "command-1"
    assert captured["action"] == "enqueue_command"
    assert captured["target_machine_id"].startswith("b942")
    assert captured["payload"]["batch_numbers"] == ["609231234567"]
    assert captured["payload"]["layout_settings"] == {"dpi": 300}


def test_submit_printer_action_is_explicit_and_has_no_layout_payload(monkeypatch):
    captured = {}
    monkeypatch.setattr(commands, "machine_id", lambda: "d9428888-122b-4c26-a127-3eafad1f5270")
    monkeypatch.setattr(commands, "machine_name", lambda: "M4")
    monkeypatch.setattr(commands, "_call", lambda payload, **_options: captured.update(payload) or {
        "command": {"id": "control-1"}
    })

    result = commands.submit_printer_action(
        "b9428888-122b-4c26-a127-3eafad1f5271", "clean_resume"
    )

    assert result["id"] == "control-1"
    assert captured["action"] == "send_control"
    assert captured["command_action"] == "clean_resume"
    assert captured["payload"] == {}


def test_printerexp_snapshot_reads_real_progress_and_task(tmp_path):
    data = tmp_path / "Data"
    data.mkdir()
    (data / "PrintInfo.ini").write_text(
        "[PRINT_INFO]\nTASK_GUID=job-123\nPRINT_PROGRESS=37.6\n",
        encoding="utf-8",
    )
    (data / "Temp.ini").write_text(
        "[PRINT_FILE]\nTASK_FOLDER=C:\\production\\BATCH-88\\\n",
        encoding="utf-8",
    )
    (data / "printTask.tf").write_bytes(
        "JOB-88.prn\0C:\\production\\BATCH-88\\JOB-88.prn\0".encode("utf-16le")
    )

    snapshot = read_snapshot(tmp_path)

    assert snapshot.task_id == "job-123"
    assert snapshot.progress == 37.6
    assert snapshot.task_file == "JOB-88.prn"
    assert snapshot.task_folder == "BATCH-88"


def test_printerexp_projection_uses_progress_speed_for_batch_eta():
    from automatic_print.automation.api.printerexp.state import PrintExpSnapshot

    projector = StatusProjector()
    first = PrintExpSnapshot("job", 20, "BATCH.prn", "0922", 1)
    second = PrintExpSnapshot("job", 30, "BATCH.prn", "0922", 2)

    assert projector.project(first, True, clock=100, timestamp="start")["remaining_seconds"] is None
    status = projector.project(second, True, clock=160, timestamp="later")

    assert status["state"] == "running"
    assert status["progress_percent"] == 30
    assert status["remaining_seconds"] == 420
    assert status["estimate_scope"] == "batch"
    assert status["source_online"] is True


def test_printerexp_projection_uses_fractional_progress_for_eta():
    from automatic_print.automation.api.printerexp.state import PrintExpSnapshot

    projector = StatusProjector()
    first = PrintExpSnapshot("job", 20.1, "BATCH.prn", "0922", 1)
    second = PrintExpSnapshot("job", 20.6, "BATCH.prn", "0922", 2)

    projector.project(first, True, clock=100, timestamp="start")
    status = projector.project(second, True, clock=130, timestamp="later")

    assert status["progress_percent"] == 21
    assert status["remaining_seconds"] == 4764


def test_machine_name_prefers_saved_machine_number(monkeypatch):
    monkeypatch.setenv("AUTOMATIC_PRINT_MACHINE_NAME", "DTF7")
    monkeypatch.setattr(identity, "saved_machine_number", lambda: "M7")

    assert identity.machine_name() == "M7"


def test_persisted_machine_number_is_shared_outside_registry(tmp_path, monkeypatch):
    target = tmp_path / "machine-name"
    monkeypatch.setattr(identity, "machine_name_file", lambda: target)

    assert identity.persist_machine_number("m11") == "M11"
    assert target.read_text(encoding="utf-8") == "M11"
    assert identity.saved_machine_number() == "M11"


def test_machine_name_only_accepts_m1_to_m11_fallback(monkeypatch):
    monkeypatch.setattr(identity, "saved_machine_number", lambda: "")
    monkeypatch.setenv("AUTOMATIC_PRINT_MACHINE_NAME", "m9")
    assert identity.machine_name() == "M9"

    monkeypatch.setenv("AUTOMATIC_PRINT_MACHINE_NAME", "Printer3")
    assert identity.machine_name() == "未设置机器号"


def test_printerexp_projection_distinguishes_idle_and_offline():
    from automatic_print.automation.api.printerexp.state import PrintExpSnapshot

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
    from automatic_print.automation.api.printerexp.state import PrintExpSnapshot

    status = StatusProjector().project(
        PrintExpSnapshot("old", 100, "tangle.prn", "old", 100),
        True,
        printer_state="ready",
        loaded_task={
            "task_file": "609240119004.prn", "loaded_at": 101,
            "task_name_verified": False, "verification": "load_dialog_closed_ready",
        },
        clock=1,
    )

    assert status["batch_name"] == "609240119004.prn"
    assert status["progress_percent"] == 0
    assert status["batch_info"]["task_name_verified"] is False
    assert status["batch_info"]["task_source"] == "load_receipt"
    assert "复核" in status["phase"]
