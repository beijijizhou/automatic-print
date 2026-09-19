"""Production-item queries and rule-based batch creation."""

from dataclasses import dataclass
from typing import Any

from .gateway import call_module

PRODUCT_ITEM_MODULE = "productItemManage-"
BATCH_RULE_MODULE = "index-B6_UezUx.js"
GENERATE_BATCH_MODULE = "productOrderManage-B-Bfdh3C.js"
SUPPLEMENT_BATCH_MODULE = "productItemManage-ppzeq-54.js"


@dataclass(frozen=True)
class BatchRule:
    id: int | str
    name: str
    shipping_statuses: tuple[str, ...]
    is_default: bool = False


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

def production_item_images(page, item_id: str) -> dict[str, Any]:
    return call_module(
        page,
        PRODUCT_ITEM_MODULE,
        "g",
        {"production_order_item_id": str(item_id)},
        "productItemManage-BvTyos5U.js",
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
        "index-B6_UezUx",
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
            BatchRule(row["id"], str(row.get("name") or ""), tuple(statuses),
                      bool(row.get("is_default")))
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


def generate_selected_batch(
    page, production_order_item_ids, batch_rule_id: int | str
) -> Any:
    """Generate one batch from an exact, already-validated item-id set."""
    item_ids = [str(item_id) for item_id in production_order_item_ids if str(item_id)]
    if not item_ids:
        raise ValueError("生成批次必须包含至少一个生产项ID。")
    request = {
        "production_order_item_ids": item_ids,
        "batch_creat_type": 2,
        "batch_rule_id": batch_rule_id,
    }
    return call_module(
        page,
        "productOrderManage-",
        "r",
        request,
        GENERATE_BATCH_MODULE,
    )


def generate_supplement_batch(
    page,
    items: list[tuple[int | str, int]],
    batch_rule_id: int | str,
) -> Any:
    """Generate a supplement batch for exact, already-batched production items."""
    item_list = [
        {"item_id": str(item_id), "qty": int(qty)}
        for item_id, qty in items
        if str(item_id) and int(qty) > 0
    ]
    if not item_list:
        raise ValueError("补单批次必须包含至少一个数量大于0的生产项。")
    return call_module(
        page,
        PRODUCT_ITEM_MODULE,
        "v",
        {"item_list": item_list, "batch_rule_id": batch_rule_id},
        SUPPLEMENT_BATCH_MODULE,
    )
