from automatic_print.automation.api.machine_status import commands


def test_submit_command_keeps_batch_piece_counts(monkeypatch):
    captured = {}

    def call(payload, timeout):
        captured.update(payload=payload, timeout=timeout)
        return {"command": {"id": "command-1"}}

    monkeypatch.setattr(commands, "_call", call)
    monkeypatch.setattr(commands, "machine_id", lambda: "requester-id")
    monkeypatch.setattr(commands, "machine_name", lambda: "M11")
    details = [{
        "batch_number": "609180613013", "item_count": 12, "piece_count": 30,
    }]

    result = commands.submit_command(
        "target-id", "S2B", ["609180613013"], {"dpi": 300},
        batch_details=details,
    )

    assert result == {"id": "command-1"}
    assert captured["payload"]["payload"]["batch_details"] == details
    assert captured["payload"]["payload"]["batch_numbers"] == ["609180613013"]
