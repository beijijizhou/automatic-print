"""Regroup printed A00 multi-item orders from production into supplement batches."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ...api.erp.batches import list_batches
from ...api.erp.items import (
    generate_supplement_batch,
    list_batch_rules,
    list_order_items,
    list_production_items,
    production_item_payload,
)
from ...browser.session import connect_debug_chrome
from ...providers.longfeng import find_longfeng_page
from ...providers.registry import get_erp_platform
from ..received.received_sizes import SIZES


A00_ROUTE_ID = 741283


@dataclass(frozen=True)
class ProductionItem:
    item_id: str
    order_id: str
    source_batch: str
    size: str
    qty: int


@dataclass(frozen=True)
class ProductionGroup:
    label: str
    orders: tuple[tuple[ProductionItem, ...], ...]

    @property
    def items(self) -> tuple[ProductionItem, ...]:
        return tuple(item for order in self.orders for item in order)

    @property
    def piece_count(self) -> int:
        return sum(item.qty for item in self.items)


@dataclass(frozen=True)
class ProductionPlan:
    source_batches: tuple[str, ...]
    groups: tuple[ProductionGroup, ...]


def _all_rows(page) -> list[dict]:
    payload = production_item_payload(
        status=("5",), order_compositions=("3",), page_size=200
    )
    payload["process_route_ids"] = [A00_ROUTE_ID]
    first = list_production_items(page, payload)
    total = int(first.get("total") or 0)
    rows = list(first.get("list") or [])
    number = 1
    while len(rows) < total:
        number += 1
        rows.extend(list_production_items(page, {**payload, "page": number}).get("list") or [])
    if len(rows) != total or len({str(row.get("id")) for row in rows}) != total:
        raise RuntimeError("A00 生产中多项多件快照不完整或含重复项目。")
    return rows


def _item(row: dict) -> ProductionItem:
    if (str(row.get("status")) != "5" or
            str(row.get("process_route_code")) != "A00" or
            str(row.get("order_composition")) != "3" or
            int(row.get("view_count") or 0) < 1 or
            row.get("supplement_detail_list") or
            int(row.get("has_supplement") or 0)):
        raise RuntimeError("目标生产项不属于未补单的 A00 有图多项多件。")
    size = str(row.get("size") or "").upper().replace("2XL", "XXL")
    qty = int(row.get("qty") or 0)
    if (size not in SIZES or qty <= 0 or not row.get("id") or
            not row.get("order_id") or not row.get("production_batch_code")):
        raise RuntimeError("目标生产项缺少尺码、订单、数量或来源批次。")
    return ProductionItem(
        str(row["id"]), str(row["order_id"]),
        str(row["production_batch_code"]), size, qty,
    )


def preview_production_multi(page, source_batches: tuple[str, ...]) -> ProductionPlan:
    if not source_batches or len(set(source_batches)) != len(source_batches):
        raise ValueError("来源批次必须非空且互不重复。")
    rows = [row for row in _all_rows(page)
            if str(row.get("production_batch_code")) in source_batches]
    if {str(row.get("production_batch_code")) for row in rows} != set(source_batches):
        raise RuntimeError("部分来源批次已不在生产中，禁止生成不完整计划。")
    orders: dict[str, list[ProductionItem]] = defaultdict(list)
    for row in rows:
        item = _item(row)
        orders[item.order_id].append(item)
    grouped: dict[str, list[tuple[ProductionItem, ...]]] = defaultdict(list)
    for order in orders.values():
        sizes = {item.size for item in order}
        label = "跨尺码" if len(sizes) > 1 else next(iter(sizes))
        grouped[label].append(tuple(order))
    groups = tuple(ProductionGroup(
        label,
        tuple(sorted(grouped[label], key=lambda order: order[0].order_id)),
    ) for label in ("跨尺码", *SIZES) if grouped[label])
    if sum(len(group.items) for group in groups) != len(rows):
        raise RuntimeError("生产中补单计划未完整覆盖来源批次。")
    return ProductionPlan(source_batches, groups)


def _verify_orders(page, group: ProductionGroup, *, submitted: bool) -> tuple[str, ...]:
    codes = set()
    for order in group.orders:
        rows = list_order_items(page, order[0].order_id)
        if {str(row.get("id")) for row in rows} != {item.item_id for item in order}:
            raise RuntimeError(f"订单 {order[0].order_id} 的项目集合已变化。")
        expected = {item.item_id: item for item in order}
        order_codes = set()
        for row in rows:
            item = expected[str(row["id"])]
            if (str(row.get("status")) != "5" or
                    str(row.get("process_route_code")) != "A00" or
                    str(row.get("order_composition")) != "3" or
                    str(row.get("production_batch_code")) != item.source_batch or
                    str(row.get("size")).upper().replace("2XL", "XXL") != item.size or
                    int(row.get("qty") or 0) != item.qty):
                raise RuntimeError(f"订单 {item.order_id} 的状态或数据已变化。")
            details = row.get("supplement_detail_list") or []
            if submitted:
                if len(details) != 1 or int(details[0].get("supplement_qty") or 0) != item.qty:
                    raise RuntimeError(f"订单 {item.order_id} 的新增补单数量未确认。")
                code = str(details[0].get("production_batch_code") or "")
                if not code:
                    raise RuntimeError(f"订单 {item.order_id} 缺少新补单批次号。")
                order_codes.add(code)
            elif details or int(row.get("has_supplement") or 0):
                raise RuntimeError(f"订单 {item.order_id} 已有补单，禁止重复提交。")
        if submitted and len(order_codes) != 1:
            raise RuntimeError(f"订单 {order[0].order_id} 被拆散到不同补单批次。")
        codes.update(order_codes)
    return tuple(sorted(codes))


def _verify_batches(page, group: ProductionGroup, codes: tuple[str, ...]):
    batch_rows = {str(row.get("code")): row for row in list_batches(page, 200)}
    if not codes or any(code not in batch_rows for code in codes):
        raise RuntimeError("新补单批次未全部出现在批次管理。")
    if (sum(int(batch_rows[code].get("production_order_item_num") or 0)
            for code in codes) != len(group.items) or
            sum(int(batch_rows[code].get("production_piece_num") or 0)
                for code in codes) != group.piece_count):
        raise RuntimeError("新补单批次的项目数或件数与计划不一致。")


def run_production_multi(expected: ProductionPlan, progress=None):
    """Submit each exact size group once; report unexpected platform splits."""
    from playwright.sync_api import sync_playwright

    report = progress or (lambda _message: None)
    platform = get_erp_platform("隆丰")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(playwright, platform.production_items_url)
        page = find_longfeng_page(browser)
        if preview_production_multi(page, expected.source_batches) != expected:
            raise RuntimeError("生产中快照已变化，请重新读取计划。")
        defaults = [rule for rule in list_batch_rules(page) if rule.is_default]
        if len(defaults) != 1:
            raise RuntimeError("系统预设补单规则不唯一。")
        created, failed = [], []
        for group in expected.groups:
            report(f"核对 {group.label}：{len(group.orders)} 单、"
                   f"{len(group.items)} 项、{group.piece_count} 件")
            try:
                _verify_orders(page, group, submitted=False)
                try:
                    generate_supplement_batch(
                        page,
                        [(item.item_id, item.qty) for item in group.items],
                        defaults[0].id,
                    )
                except Exception as error:
                    raise RuntimeError("提交结果不确定，禁止重复提交。") from error
                codes = _verify_orders(page, group, submitted=True)
                _verify_batches(page, group, codes)
            except Exception as error:
                failed.append((group.label, str(error)))
                report(f"{group.label} 未确认：{error}")
                continue
            created.append((group.label, len(group.orders), len(group.items),
                            group.piece_count, codes))
            report(f"{group.label} 已确认批次：{'、'.join(codes)}")
        return tuple(created), tuple(failed)
