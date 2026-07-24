from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PRODUCT_ITEM_MODULE = "productItemManage-"
PROCESS_BATCH_MODULE = "processBatchManage-"
BATCH_RULE_MODULE = "index-tzXGOuzl.js"
GENERATE_BATCH_MODULE = "productOrderManage-B-Bfdh3C.js"
CHUNK_ROOT = "https://fe-product.hihumbird.com/static/js/chunk/"


@dataclass(frozen=True)
class BatchRule:
    id: int | str
    name: str
    shipping_statuses: tuple[str, ...]


def production_api_frame(page):
    frames = [frame for frame in page.frames if frame.name == "fnsz-sale"]
    if len(frames) != 1:
        raise RuntimeError("ERP 生产模块尚未加载完成，请刷新后重试。")
    return frames[0]


def module_url(page, filename_prefix: str, fallback: str | None = None) -> str:
    frame = production_api_frame(page)
    resources = frame.evaluate(
        "() => performance.getEntriesByType('resource').map(x => x.name)"
    )
    matches = [
        url
        for url in resources
        if "/static/js/chunk/" in url
        and url.rsplit("/", 1)[-1].startswith(filename_prefix)
    ]
    if matches:
        return matches[-1]
    if fallback:
        return CHUNK_ROOT + fallback
    raise RuntimeError(f"ERP 前端模块未加载：{filename_prefix}")


def call_module(
    page,
    filename_prefix: str,
    export_name: str,
    argument: Any = None,
    fallback: str | None = None,
):
    frame = production_api_frame(page)
    url = module_url(page, filename_prefix, fallback)
    return frame.evaluate(
        """async ({url, exportName, argument}) => {
            const api = await import(url);
            const fn = api[exportName];
            if (typeof fn !== "function") {
                throw new Error(`ERP API export not found: ${exportName}`);
            }
            return await fn(argument);
        }""",
        {"url": url, "exportName": export_name, "argument": argument},
    )


def production_item_payload(
    *,
    status: tuple[str, ...] = ("1",),
    page: int = 1,
    page_size: int = 200,
    shipping_codes: tuple[str, ...] = (),
    order_compositions: tuple[str, ...] = (),
    shipping_statuses: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "page": page,
        "page_size": page_size,
        "sum_total_qty": True,
        "status": list(status),
        "order_compositions": list(order_compositions),
        "process_route_ids": [],
        "order_third_status_list": [],
        "performance_status_list": [],
        "system_performance_status_list": [],
        "shipping_status_list": list(shipping_statuses),
        "order_source_list": [],
        "logistics_sorting_code_list": list(shipping_codes),
        "styles": {"style_sku_ids": []},
        "sort": [{"sort_by": "created", "sort_type": 2}],
    }


def list_production_items(page, payload: dict[str, Any]) -> dict[str, Any]:
    return call_module(
        page,
        PRODUCT_ITEM_MODULE,
        "a",
        payload,
        "productItemManage-BvTyos5U.js",
    )


def production_item_count(page, status: str) -> int:
    result = list_production_items(
        page,
        production_item_payload(status=(status,), page_size=1),
    )
    return int(result.get("total") or 0)


def list_all_received_items(page) -> tuple[list[dict[str, Any]], int]:
    first = list_production_items(page, production_item_payload())
    total = int(first.get("total") or 0)
    rows = list(first.get("list") or [])
    current_page = 1
    while len(rows) < total:
        current_page += 1
        result = list_production_items(
            page, production_item_payload(page=current_page)
        )
        page_rows = list(result.get("list") or [])
        if not page_rows:
            break
        rows.extend(page_rows)
    if len(rows) != total:
        raise RuntimeError(
            f"ERP 接口返回 {len(rows)} 项，但总数为 {total}，已停止。"
        )
    return rows, total


def list_batch_rules(page) -> tuple[BatchRule, ...]:
    rows = call_module(
        page,
        "index-tzXGOuzl",
        "k",
        {"product_sale_type_list": 1},
        BATCH_RULE_MODULE,
    )
    result = []
    for row in rows or []:
        statuses: list[str] = []
        for condition in row.get("condition") or []:
            if condition.get("key") == "shipping_status":
                statuses = [str(value) for value in condition.get("value") or []]
        result.append(
            BatchRule(row["id"], str(row.get("name") or ""), tuple(statuses))
        )
    return tuple(result)


def find_batch_rule(page, name: str) -> BatchRule:
    matches = [rule for rule in list_batch_rules(page) if rule.name == name]
    if len(matches) != 1:
        raise RuntimeError(f"无法唯一找到批次规则“{name}”。")
    return matches[0]


def generate_filtered_batch(
    page, payload: dict[str, Any], batch_rule_id: int | str
) -> Any:
    request = dict(payload)
    request.pop("page", None)
    request.pop("page_size", None)
    request.pop("sum_total_qty", None)
    request["batch_creat_type"] = 1
    request["batch_rule_id"] = batch_rule_id
    return call_module(
        page,
        "productOrderManage-",
        "r",
        request,
        GENERATE_BATCH_MODULE,
    )


def batch_page_payload(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    return {
        "product_sale_type_list": [1],
        "order_compositions": [],
        "initial_status": 1,
        "page": page,
        "page_size": page_size,
        "sort": [{"sort_type": 2, "sort_by": "created"}],
    }


def list_batches(page) -> list[dict[str, Any]]:
    result = call_module(
        page,
        PROCESS_BATCH_MODULE,
        "g",
        batch_page_payload(),
        "processBatchManage-Dv3c2kZY.js",
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
        "processBatchManage-Dv3c2kZY.js",
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
            "processBatchManage-Dv3c2kZY.js",
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
