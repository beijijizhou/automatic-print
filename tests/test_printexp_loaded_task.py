from automatic_print.automation.api.printerexp.loaded_task import (
    read_loaded_task, record_loaded_task,
)


def test_loaded_task_receipt_round_trip(tmp_path):
    task = tmp_path / "609240119004.prn"
    task.write_bytes(b"prn")
    receipt_file = tmp_path / "receipt.json"

    saved = record_loaded_task(task, verified=False, now=100, target=receipt_file)
    loaded = read_loaded_task(now=101, target=receipt_file)

    assert saved["task_file"] == task.name
    assert loaded["task_file"] == task.name
    assert loaded["task_name_verified"] is False
    assert loaded["verification"] == "load_dialog_closed_ready"


def test_loaded_task_receipt_expires_and_requires_existing_prn(tmp_path):
    task = tmp_path / "batch.prn"
    task.write_bytes(b"prn")
    receipt_file = tmp_path / "receipt.json"
    record_loaded_task(task, now=100, target=receipt_file)

    assert read_loaded_task(now=100 + 8 * 60 * 60 + 1, target=receipt_file) is None
    task.unlink()
    assert read_loaded_task(now=101, target=receipt_file) is None
