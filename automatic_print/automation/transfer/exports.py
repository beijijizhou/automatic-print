from __future__ import annotations

import time

from ..api.erp import PROCESS_BATCH_MODULE, call_module


PRODUCTION_IMAGE_EXPORT_TYPE = 3
EXPORT_READY_STATUS = 2


def ready_production_image_codes(page, rows: list[dict]) -> set[str]:
    codes = [str(row.get("code") or "") for row in rows if row.get("code")]
    if not codes:
        return set()
    records = production_image_export_records(
        page, codes,
        [int(row.get("created") or 0) for row in rows if row.get("created")],
    )
    return set(records)


def production_image_export_records(
    page, codes: list[str], created_values: list[int] | None = None,
) -> dict[str, dict]:
    """Return the newest completed production-image export for each batch."""
    if not codes:
        return {}
    created_values = created_values or []
    day_ms = 86_400_000
    date_from = max(0, min(created_values, default=0) - day_ms)
    date_to = max(
        int(time.time() * 1000) + day_ms,
        max(created_values, default=0) + day_ms,
    )
    records = call_module(
        page,
        PROCESS_BATCH_MODULE,
        "k",
        {
            "export_type_list": [PRODUCTION_IMAGE_EXPORT_TYPE],
            "biz_no_list": codes,
            "export_time_range": {"from": date_from, "to": date_to},
            "page": 1,
            "page_size": max(200, len(codes)),
        },
        "processBatchManage-Dv3c2kZY.js",
    )
    completed = {}
    for record in records or []:
        code = str(record.get("biz_no") or "")
        if (code not in codes
                or int(record.get("export_type") or 0) != PRODUCTION_IMAGE_EXPORT_TYPE
                or int(record.get("status") or 0) != EXPORT_READY_STATUS
                or not str(record.get("file_path") or "").strip()):
            continue
        current = completed.get(code)
        stamp = int(record.get("finish_time") or record.get("created") or 0)
        current_stamp = int((current or {}).get("finish_time")
                            or (current or {}).get("created") or 0)
        if current is None or stamp >= current_stamp:
            completed[code] = record
    return completed
