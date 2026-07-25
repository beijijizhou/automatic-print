from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from ..automation.batch_browser import BatchRecord


def save_batch_cache(settings, platform: str, records) -> str:
    saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "saved_at": saved_at,
        "records": [asdict(record) for record in records],
    }
    settings.setValue(
        _key(platform),
        json.dumps(payload, ensure_ascii=False),
    )
    return saved_at


def load_batch_cache(settings, platform: str):
    raw = settings.value(_key(platform), "", str)
    if not raw:
        return [], ""
    try:
        payload = json.loads(raw)
        records = [BatchRecord(**row) for row in payload["records"]]
        return records, str(payload.get("saved_at") or "")
    except (KeyError, TypeError, ValueError):
        return [], ""


def _key(platform: str) -> str:
    return f"automation/batch_cache/{platform}"
