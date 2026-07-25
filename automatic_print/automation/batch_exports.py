from __future__ import annotations

import time

from .erp_api import PROCESS_BATCH_MODULE, call_module


PRODUCTION_IMAGE_EXPORT_TYPE = 3
EXPORT_READY_STATUS = 2


def ready_production_image_codes(page, rows: list[dict]) -> set[str]:
    codes = [str(row.get("code") or "") for row in rows if row.get("code")]
    if not codes:
        return set()
    created_values = [
        int(row.get("created") or 0) for row in rows if row.get("created")
    ]
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
    return {
        str(record.get("biz_no") or "")
        for record in records or []
        if int(record.get("export_type") or 0)
        == PRODUCTION_IMAGE_EXPORT_TYPE
        and int(record.get("status") or 0) == EXPORT_READY_STATUS
    }
