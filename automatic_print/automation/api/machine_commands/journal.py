"""Durable mapping between cloud commands and local PrintExp execution facts."""

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
import sqlite3


TERMINAL_STAGES = {"prn_loaded", "physical_started", "physical_completed", "completed", "failed"}


def journal_path():
    override = os.environ.get("AUTOMATIC_PRINT_COMMAND_JOURNAL")
    if override:
        return Path(override)
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".automatic-print")
    return root / "AutomaticPrint" / "command-journal.sqlite3"


class ExecutionJournal:
    def __init__(self, path=None):
        self.path = Path(path) if path else journal_path()

    def claim(self, command_id, action, payload):
        with self._connect() as database:
            existing = self._row(database, command_id)
            if existing:
                return existing
            now = _now()
            database.execute(
                "INSERT INTO command_execution "
                "(command_id, action, payload_json, stage, created_at, updated_at) "
                "VALUES (?, ?, ?, 'running', ?, ?)",
                (str(command_id), str(action), _json(payload), now, now),
            )
            return None

    def success(self, command_id, action, payload, phase, result):
        result = dict(result or {})
        stage = _success_stage(action, result)
        batch_name = _batch_name(payload, result)
        task_id = str(result.get("printexp_task_id") or "")
        self._finish(
            command_id, stage, "succeeded", phase, result, "", batch_name,
            task_id, bool(result.get("physical_print_started")),
        )
        return self.get(command_id)

    def failure(self, command_id, action, payload, phase, error, result=None):
        current = self.get(command_id)
        if current and current.get("cloud_status") == "succeeded":
            return current
        self._finish(
            command_id, "failed", "failed", phase, dict(result or {}), str(error),
            _batch_name(payload, result or {}), "", False,
        )
        return self.get(command_id)

    def mark_reported(self, command_id):
        with self._connect() as database:
            database.execute(
                "UPDATE command_execution SET result_reported=1, updated_at=? WHERE command_id=?",
                (_now(), str(command_id)),
            )

    def get(self, command_id):
        with self._connect() as database:
            return self._row(database, command_id)

    def pending_receipts(self, limit=20):
        with self._connect() as database:
            rows = database.execute(
                "SELECT * FROM command_execution WHERE result_reported=0 "
                "AND cloud_status IN ('succeeded','failed') ORDER BY updated_at LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [_record(row) for row in rows]

    def reconcile(self, status):
        batch_name = _name(status.get("batch_name"))
        if not batch_name:
            return 0
        progress = status.get("progress_percent")
        task_id = str(status.get("batch_id") or "")
        completed = status.get("state") == "idle" and progress is not None and float(progress) >= 100
        with self._connect() as database:
            rows = database.execute(
                "SELECT command_id, batch_name, printexp_task_id FROM command_execution "
                "WHERE action='start_print' AND stage IN ('physical_started','physical_completed')"
            ).fetchall()
            matches = [
                row["command_id"] for row in rows
                if _name(row["batch_name"]) == batch_name
                and (not row["printexp_task_id"] or not task_id
                     or row["printexp_task_id"] == task_id)
            ]
            for command_id in matches:
                database.execute(
                    "UPDATE command_execution SET printexp_task_id=?, stage=?, updated_at=? "
                    "WHERE command_id=?",
                    (task_id, "physical_completed" if completed else "physical_started",
                     _now(), command_id),
                )
            return len(matches)

    def _finish(self, command_id, stage, cloud_status, phase, result, error,
                batch_name, task_id, physical_started):
        with self._connect() as database:
            database.execute(
                "UPDATE command_execution SET stage=?, cloud_status=?, phase=?, result_json=?, "
                "error_message=?, batch_name=?, prn_files_json=?, printexp_task_id=?, "
                "physical_print_started=?, result_reported=0, updated_at=? WHERE command_id=?",
                (stage, cloud_status, str(phase), _json(result), str(error), batch_name,
                 _json(result.get("prn_files") or []), task_id, int(physical_started),
                 _now(), str(command_id)),
            )

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        database = sqlite3.connect(self.path, timeout=5)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA busy_timeout=5000")
        database.execute(
            "CREATE TABLE IF NOT EXISTS command_execution ("
            "command_id TEXT PRIMARY KEY, action TEXT NOT NULL, payload_json TEXT NOT NULL, "
            "batch_name TEXT NOT NULL DEFAULT '', prn_files_json TEXT NOT NULL DEFAULT '[]', "
            "printexp_task_id TEXT NOT NULL DEFAULT '', stage TEXT NOT NULL, "
            "physical_print_started INTEGER NOT NULL DEFAULT 0, cloud_status TEXT, "
            "phase TEXT NOT NULL DEFAULT '', result_json TEXT NOT NULL DEFAULT '{}', "
            "error_message TEXT NOT NULL DEFAULT '', result_reported INTEGER NOT NULL DEFAULT 0, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        try:
            yield database
            database.commit()
        except Exception:
            database.rollback()
            raise
        finally:
            database.close()

    @staticmethod
    def _row(database, command_id):
        row = database.execute(
            "SELECT * FROM command_execution WHERE command_id=?", (str(command_id),)
        ).fetchone()
        return _record(row) if row else None


def _record(row):
    record = dict(row)
    record["payload"] = _decode(record.pop("payload_json"), {})
    record["result"] = _decode(record.pop("result_json"), {})
    record["prn_files"] = _decode(record.pop("prn_files_json"), [])
    record["physical_print_started"] = bool(record["physical_print_started"])
    record["result_reported"] = bool(record["result_reported"])
    return record


def _success_stage(action, result):
    if result.get("physical_print_started"):
        return "physical_started"
    if action == "download_layout" and result.get("prn_files"):
        return "prn_loaded"
    return "completed"


def _batch_name(payload, result):
    value = result.get("batch_name") or payload.get("expected_batch_name")
    if not value and result.get("prn_files"):
        value = result["prn_files"][0]
    return str(value or "")


def _name(value):
    return PureWindowsPath(str(value or "").replace("/", "\\")).name.casefold()


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _decode(value, fallback):
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _now():
    return datetime.now(timezone.utc).isoformat()
