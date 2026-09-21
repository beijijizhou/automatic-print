"""Generate received Longfeng A00 multi-item orders with one ERP filter."""

from __future__ import annotations

from dataclasses import dataclass

from ..api.erp.batches import list_batches
from ..api.erp.items import (
    generate_filtered_batch,
    list_all_received_items,
    list_batch_rules,
    list_order_items,
    list_production_items,
    production_item_payload,
)
from ..browser.session import connect_debug_chrome
from ..providers.longfeng import find_longfeng_page
from ..providers.registry import get_erp_platform


ROUTE_CODE = "A00"
COMPOSITION = "3"


@dataclass(frozen=True)
class DefaultMultiPlan:
    route_id: str
    received_count: int
    item_quantities: tuple[tuple[str, int], ...]
    order_items: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def item_count(self) -> int:
        return len(self.item_quantities)

    @property
    def piece_count(self) -> int:
        return sum(qty for _item_id, qty in self.item_quantities)


@dataclass(frozen=True)
class DefaultMultiResult:
    plan: DefaultMultiPlan
    batch_codes: tuple[str, ...]
    batch_status: tuple[str, ...]


def _preview(page) -> DefaultMultiPlan:
    rows, total = list_all_received_items(page)
    default_rows = [row for row in rows
                    if str(row.get("process_route_code")) == ROUTE_CODE]
    if not default_rows:
        return DefaultMultiPlan("", total, ())
    route_ids = {str(row.get("process_route_id") or "") for row in default_rows}
    if len(route_ids) != 1 or "" in route_ids:
        raise RuntimeError("已接单默认工艺路线缺少唯一的路线 ID。")
    selected = [row for row in default_rows
                if str(row.get("order_composition")) == COMPOSITION]
    if any(not row.get("id") or not row.get("order_id") for row in selected):
        raise RuntimeError("默认路线多项多件缺少生产项或订单 ID。")
    if any(row.get("production_batch_id") or row.get("production_batch_code")
           for row in selected):
        raise RuntimeError("已接单多项多件混入已有批次的项目。")
    item_quantities = tuple(sorted(
        (str(row["id"]), int(row.get("qty") or 0)) for row in selected
    ))
    if (len({item_id for item_id, _qty in item_quantities}) != len(selected) or
            any(not item_id or qty <= 0 for item_id, qty in item_quantities)):
        raise RuntimeError("默认路线多项多件存在重复 ID 或无效件数。")
    by_order: dict[str, set[str]] = {}
    for row in selected:
        by_order.setdefault(str(row["order_id"]), set()).add(str(row["id"]))
    order_items = tuple(sorted(
        (order_id, tuple(sorted(item_ids)))
        for order_id, item_ids in by_order.items()
    ))
    return DefaultMultiPlan(route_ids.pop(), total, item_quantities, order_items)


def preview_default_multi() -> DefaultMultiPlan:
    from playwright.sync_api import sync_playwright

    platform = get_erp_platform("隆丰")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(playwright, platform.production_items_url)
        return _preview(find_longfeng_page(browser))


def _production_rows(page, route_id: str) -> list[dict]:
    payload = production_item_payload(
        status=("5",), order_compositions=(COMPOSITION,), page_size=200
    )
    payload["process_route_ids"] = [int(route_id)]
    first = list_production_items(page, payload)
    total = int(first.get("total") or 0)
    rows = list(first.get("list") or [])
    number = 1
    while len(rows) < total:
        number += 1
        rows.extend(list_production_items(page, {**payload, "page": number}).get("list") or [])
    if len(rows) != total:
        raise RuntimeError("生产中默认路线多项多件列表未完整返回。")
    return rows


def _verify_whole_orders(page, plan: DefaultMultiPlan) -> None:
    quantities = dict(plan.item_quantities)
    if sum(len(item_ids) for _order_id, item_ids in plan.order_items) != plan.item_count:
        raise RuntimeError("计划缺少完整订单清单，禁止生成批次。")
    for order_id, item_ids in plan.order_items:
        rows = list_order_items(page, order_id)
        if {str(row.get("id")) for row in rows} != set(item_ids):
            raise RuntimeError(f"订单 {order_id} 不完整，禁止拆单。")
        if any(
            str(row.get("status")) != "1" or
            str(row.get("process_route_code")) != ROUTE_CODE or
            str(row.get("order_composition")) != COMPOSITION or
            int(row.get("qty") or 0) != quantities[str(row["id"])]
            for row in rows
        ):
            raise RuntimeError(f"订单 {order_id} 的状态或数量已变化。")


def generate_default_multi(expected: DefaultMultiPlan, progress=None) -> DefaultMultiResult:
    """Use filter generation once and verify exact item and batch membership."""
    from playwright.sync_api import sync_playwright

    report = progress or (lambda _message: None)
    platform = get_erp_platform("隆丰")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(playwright, platform.production_items_url)
        page = find_longfeng_page(browser)
        if _preview(page) != expected or not expected.item_count:
            raise RuntimeError("已接单默认路线多项多件已变化或为空，请重新读取。")
        rules = [rule for rule in list_batch_rules(page) if rule.is_default]
        if len(rules) != 1:
            raise RuntimeError("系统预设批次规则不唯一。")
        payload = production_item_payload(
            status=("1",), order_compositions=(COMPOSITION,)
        )
        payload["process_route_ids"] = [int(expected.route_id)]
        filtered = list_production_items(page, {**payload, "page_size": 1})
        if int(filtered.get("total") or 0) != expected.item_count:
            raise RuntimeError("提交前筛选数量已变化，请重新读取。")
        _verify_whole_orders(page, expected)
        existing = {str(row.get("code")) for row in list_batches(page, 200)}
        report(f"按默认工艺路线 / 多项多件直接生成："
               f"{expected.item_count} 项、{expected.piece_count} 件")
        try:
            generate_filtered_batch(page, payload, rules[0].id)
        except Exception as error:
            raise RuntimeError("批次提交结果不确定，禁止直接重试。") from error
        new_rows = []
        for _ in range(30):
            new_rows = [row for row in list_batches(page, 200)
                        if str(row.get("code")) not in existing
                        and str(row.get("order_composition")) == COMPOSITION
                        and any(route.get("code") == ROUTE_CODE
                                for route in row.get("process_route_list") or [])]
            if (sum(int(row.get("production_order_item_num") or 0)
                    for row in new_rows) == expected.item_count and
                    sum(int(row.get("production_piece_num") or 0)
                        for row in new_rows) == expected.piece_count):
                break
            page.wait_for_timeout(1000)
        else:
            raise RuntimeError("批次已提交，但批次管理数量尚未确认；禁止重试。")
        codes = {str(row["code"]) for row in new_rows}
        expected_qty = dict(expected.item_quantities)
        expected_ids = set(expected_qty)
        actual = [row for row in _production_rows(page, expected.route_id)
                  if str(row.get("id")) in expected_ids]
        if len(actual) != expected.item_count or any(
            str(row.get("production_batch_code")) not in codes
            or int(row.get("qty") or 0) != expected_qty[str(row.get("id"))]
            for row in actual
        ):
            raise RuntimeError("批次已提交，但未确认全部目标项目入新批次；禁止重试。")
        orders: dict[str, set[str]] = {}
        for row in actual:
            orders.setdefault(str(row.get("order_id")), set()).add(
                str(row.get("production_batch_code"))
            )
        if any(len(order_codes) != 1 for order_codes in orders.values()):
            raise RuntimeError("平台把同一订单拆到不同批次；请暂停后续生产核对。")
        status = tuple(
            f"{row['code']}：{row['production_order_item_num']} 项 / "
            f"{row['production_piece_num']} 件，生产进度 "
            f"{float(row.get('progress') or 0):.0%}"
            for row in new_rows
        )
        report(f"批次管理已确认 {len(new_rows)} 个新批次。")
        return DefaultMultiResult(expected, tuple(sorted(codes)), status)
