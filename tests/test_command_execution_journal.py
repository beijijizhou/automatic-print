from automatic_print.automation.api.machine_commands.journal import ExecutionJournal
from automatic_print.automation.api.machine_commands.lifecycle import (
    CommandLifecycle, recover_pending_receipts,
)
from automatic_print.automation.api.machine_commands import runner


def test_journal_maps_cloud_command_to_local_printer_fact(tmp_path):
    journal = ExecutionJournal(tmp_path / "journal.sqlite3")
    payload = {"expected_batch_name": "job.prn"}

    assert journal.claim("command-1", "start_print", payload) is None
    record = journal.success(
        "command-1", "start_print", payload, "PrintExp 已开始打印",
        {
            "batch_name": "job.prn", "printexp_task_id": "print-task-7",
            "physical_print_started": True,
        },
    )

    assert record["command_id"] == "command-1"
    assert record["batch_name"] == "job.prn"
    assert record["printexp_task_id"] == "print-task-7"
    assert record["stage"] == "physical_started"
    assert record["physical_print_started"] is True


def test_same_command_replays_receipt_without_printing_twice(monkeypatch):
    actions, updates = [], []
    monkeypatch.setattr(runner, "get_command", lambda _command_id: {
        "action": "start_print", "payload": {"expected_batch_name": "job.prn"},
    })
    monkeypatch.setattr(
        runner, "execute_printer_action",
        lambda *_args: actions.append("print") or {
            "batch_name": "job.prn", "printexp_task_id": "task-1",
            "physical_print_started": True,
        },
    )
    monkeypatch.setattr(
        runner, "update_command", lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    assert runner.run_command("same-command") == 0
    assert runner.run_command("same-command") == 0

    assert actions == ["print"]
    assert len(updates) == 2
    assert all(item[0][1] == "succeeded" for item in updates)


def test_lost_cloud_receipt_is_recovered_without_reexecution(tmp_path):
    journal = ExecutionJournal(tmp_path / "journal.sqlite3")
    lifecycle = CommandLifecycle(
        "command-2", "start_print", {"expected_batch_name": "job.prn"},
        journal=journal, publish=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()),
    )
    assert lifecycle.begin() is None
    lifecycle.succeed("PrintExp 已开始打印", {
        "batch_name": "job.prn", "physical_print_started": True,
    })
    assert journal.get("command-2")["result_reported"] is False

    sent = []
    assert recover_pending_receipts(
        journal=journal, publish=lambda *args, **kwargs: sent.append((args, kwargs)),
    ) == 1

    assert sent[0][0][:2] == ("command-2", "succeeded")
    assert journal.get("command-2")["result_reported"] is True


def test_status_reconciliation_marks_the_matching_print_complete(tmp_path):
    journal = ExecutionJournal(tmp_path / "journal.sqlite3")
    payload = {"expected_batch_name": "folder\\JOB.PRN"}
    journal.claim("command-3", "start_print", payload)
    journal.success(
        "command-3", "start_print", payload, "started",
        {"batch_name": "job.prn", "printexp_task_id": "history-9",
         "physical_print_started": True},
    )

    matched = journal.reconcile({
        "batch_name": "JOB.PRN", "batch_id": "history-9",
        "state": "idle", "progress_percent": 100,
    })

    record = journal.get("command-3")
    assert matched == 1
    assert record["stage"] == "physical_completed"
    assert record["printexp_task_id"] == "history-9"


def test_same_prn_name_does_not_merge_different_printer_task_ids(tmp_path):
    journal = ExecutionJournal(tmp_path / "journal.sqlite3")
    payload = {"expected_batch_name": "repeat.prn"}
    journal.claim("old-command", "start_print", payload)
    journal.success(
        "old-command", "start_print", payload, "started",
        {"batch_name": "repeat.prn", "printexp_task_id": "old-task",
         "physical_print_started": True},
    )

    assert journal.reconcile({
        "batch_name": "repeat.prn", "batch_id": "new-task",
        "state": "idle", "progress_percent": 100,
    }) == 0
    assert journal.get("old-command")["stage"] == "physical_started"
