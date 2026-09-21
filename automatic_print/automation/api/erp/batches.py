"""Production-batch list queries."""

from typing import Any

from .gateway import PROCESS_BATCH_MODULE, call_module

BATCH_MODULE_FALLBACK = "processBatchManage-Dv3c2kZY.js"


def batch_page_payload(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    return {
        "product_sale_type_list": [1],
        "order_compositions": [],
        "initial_status": 1,
        "page": page,
        "page_size": page_size,
        "sort": [{"sort_type": 2, "sort_by": "created"}],
    }


def list_batches(page, page_size: int = 20) -> list[dict[str, Any]]:
    result = call_module(
        page,
        PROCESS_BATCH_MODULE,
        "g",
        batch_page_payload(page_size=page_size),
        BATCH_MODULE_FALLBACK,
    )
    return list(result.get("list") or [])


def list_batches_between(
    page, start_code: str, end_code: str
) -> list[dict[str, Any]]:
    endpoint_payload = batch_page_payload(1, 20)
    endpoint_payload["codes"] = [start_code, end_code]
    endpoint_result = call_module(
        page,
        PROCESS_BATCH_MODULE,
        "g",
        endpoint_payload,
        BATCH_MODULE_FALLBACK,
    )
    endpoints = list(endpoint_result.get("list") or [])
    if not endpoints:
        return []
    if len(endpoints) == 1:
        return endpoints
    lower, upper = sorted(int(row["created"]) for row in endpoints)
    matched: list[dict[str, Any]] = []
    current_page = 1
    while True:
        payload = batch_page_payload(current_page, 200)
        payload["created_range"] = {"from": lower, "to": upper}
        result = call_module(
            page,
            PROCESS_BATCH_MODULE,
            "g",
            payload,
            BATCH_MODULE_FALLBACK,
        )
        rows = list(result.get("list") or [])
        matched.extend(
            row
            for row in rows
            if lower <= int(row.get("created") or 0) <= upper
        )
        if len(rows) < 200 or current_page * 200 >= int(
            result.get("total") or 0
        ):
            break
        current_page += 1
    codes = [str(row.get("code") or "") for row in matched]
    try:
        first = codes.index(start_code)
        second = codes.index(end_code)
    except ValueError:
        return endpoints
    lower_index, upper_index = sorted((first, second))
    return matched[lower_index : upper_index + 1]
