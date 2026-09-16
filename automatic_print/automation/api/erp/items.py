"""Production-item queries and rule-based batch creation."""

from dataclasses import dataclass
from typing import Any

from .gateway import call_module

PRODUCT_ITEM_MODULE = "productItemManage-"
BATCH_RULE_MODULE = "index-tzXGOuzl.js"
GENERATE_BATCH_MODULE = "productOrderManage-B-Bfdh3C.js"


@dataclass(frozen=True)
class BatchRule:
    id: int | str
    name: str
    shipping_statuses: tuple[str, ...]


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
        page, PRODUCT_ITEM_MODULE, "a", payload, "productItemManage-BvTyos5U.js"
    )


def production_item_count(page, status: str) -> int:
    result = list_production_items(
        page, production_item_payload(status=(status,), page_size=1)
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
