from pathlib import Path

from automatic_print.automation.api.machine_status import client


ROOT = Path(__file__).parents[1]


def test_manual_availability_uses_shared_backend(monkeypatch):
    captured = {}
    monkeypatch.setattr(client, "_call", lambda payload, **options: captured.update(
        payload=payload, options=options,
    ) or {"machine": {"availability_override": payload["availability"]}})

    machine = client.set_machine_availability("machine-4", "unavailable")

    assert captured["payload"] == {
        "action": "set_availability",
        "target_machine_id": "machine-4",
        "availability": "unavailable",
    }
    assert machine["availability_override"] == "unavailable"


def test_event_availability_migration_is_part_of_backend_contract():
    migration = (
        ROOT / "supabase/migrations/202609240001_event_driven_machine_availability.sql"
    ).read_text(encoding="utf-8")

    assert "availability_override" in migration
    assert "auto_available" in migration
    assert "last_feedback_at" in migration
