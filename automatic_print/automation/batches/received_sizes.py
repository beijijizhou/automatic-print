"""Create Longfeng A00 multi-item batches without splitting orders."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..api.erp.items import (
    generate_selected_batch,
    list_all_received_items,
    list_batch_rules,
    list_order_items,
)
from ..api.erp.batches import list_batches
from ..browser.session import connect_debug_chrome
from ..providers.longfeng import find_longfeng_page
from ..providers.registry import get_erp_platform


SIZES = ("S", "M", "L", "XL", "XXL", "3XL", "4XL", "5XL")
MAX_ITEMS_PER_REQUEST = 200


@dataclass(frozen=True)
class ReceivedItem:
    item_id: str
    order_id: str
    composition: str
    size: str
    qty: int


@dataclass(frozen=True)
class ReceivedGroup:
    label: str
    orders: tuple[tuple[ReceivedItem, ...], ...]

    @property
    def items(self) -> tuple[ReceivedItem, ...]:
        return tuple(item for order in self.orders for item in order)

    @property
    def piece_count(self) -> int:
        return sum(item.qty for item in self.items)


@dataclass(frozen=True)
class ReceivedPlan:
    received_count: int
    groups: tuple[ReceivedGroup, ...]


def _item(row: dict) -> ReceivedItem:
    if (str(row.get("status")) != "1" or
            str(row.get("process_route_code")) != "A00" or
            row.get("production_batch_id") or row.get("production_batch_code")):
        raise RuntimeError("所选生产项已离开 A00 已接单状态或已有批次。")
    composition = str(row.get("order_composition"))
    size = str(row.get("size") or "").upper().replace("2XL", "XXL")
    qty = int(row.get("qty") or 0)
    if (composition != "3" or size not in SIZES or qty <= 0 or
            not row.get("id") or not row.get("order_id")):
        raise RuntimeError("多件生产项缺少可核对的订单组成、尺码或数量。")
    return ReceivedItem(str(row["id"]), str(row["order_id"]), composition,
                        size, qty)


def plan_received_multi(rows: list[dict]) -> ReceivedPlan:
    if len({str(row.get("id")) for row in rows}) != len(rows):
        raise RuntimeError("已接单接口返回重复生产项。")
    order_rows: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if str(row.get("order_composition")) == "3":
            order_rows[str(row.get("order_id"))].append(row)
    grouped: dict[tuple[str, str], list[tuple[ReceivedItem, ...]]] = defaultdict(list)
    for source in order_rows.values():
        order = tuple(_item(row) for row in source)
        if len({item.composition for item in order}) != 1:
            raise RuntimeError("同一订单包含不同订单组成。")
        composition = order[0].composition
        sizes = {item.size for item in order}
        key = ("跨尺码", composition) if len(sizes) > 1 else (next(iter(sizes)), composition)
        grouped[key].append(order)
    keys = [("跨尺码", "3")] + [(size, "3") for size in SIZES]
    groups = tuple(ReceivedGroup(
        f"{size}·多项多件",
        tuple(sorted(grouped[(size, composition)], key=lambda order: order[0].order_id)),
    ) for size, composition in keys if grouped[(size, composition)])
    if sum(len(group.items) for group in groups) != sum(map(len, order_rows.values())):
        raise RuntimeError("多件订单分组未完整覆盖全部生产项。")
    return ReceivedPlan(len(rows), groups)


def preview_received_multi(page) -> ReceivedPlan:
    rows, total = list_all_received_items(page)
    if len(rows) != total or any(str(row.get("status")) != "1" for row in rows):
        raise RuntimeError("已接单快照不完整或混入其他状态。")
    return plan_received_multi(rows)


def _chunks(group: ReceivedGroup):
    chunk = []
    count = 0
    for order in group.orders:
        if len(order) > MAX_ITEMS_PER_REQUEST:
            raise RuntimeError("单个订单超过单次提交的生产项上限。")
        if chunk and count + len(order) > MAX_ITEMS_PER_REQUEST:
            yield tuple(chunk)
            chunk, count = [], 0
        chunk.append(order)
        count += len(order)
    if chunk:
        yield tuple(chunk)


def _verify_orders(page, orders, *, submitted: bool) -> tuple[str, ...]:
    codes = set()
    for order in orders:
        actual = list_order_items(page, order[0].order_id)
        if {str(row.get("id")) for row in actual} != {item.item_id for item in order}:
            raise RuntimeError(f"订单 {order[0].order_id} 的生产项集合已变化。")
        expected = {item.item_id: item for item in order}
        order_codes = set()
        for row in actual:
            item = expected[str(row["id"])]
            if (str(row.get("process_route_code")) != "A00" or
                    str(row.get("order_composition")) != item.composition or
                    str(row.get("size")).upper().replace("2XL", "XXL") != item.size or
                    int(row.get("qty") or 0) != item.qty):
                raise RuntimeError(f"订单 {item.order_id} 的路线、尺码或数量已变化。")
            if submitted:
                if str(row.get("status")) != "5" or not row.get("production_batch_code"):
                    raise RuntimeError(f"订单 {item.order_id} 提交后未确认完整入批。")
                order_codes.add(str(row["production_batch_code"]))
            elif str(row.get("status")) != "1" or row.get("production_batch_id"):
                raise RuntimeError(f"订单 {item.order_id} 已被其他操作接单，禁止重复提交。")
        if submitted and len(order_codes) != 1:
            raise RuntimeError(f"订单 {order[0].order_id} 被拆散到不同批次。")
        codes.update(order_codes)
    return tuple(sorted(codes))


def _verify_batch_totals(page, codes, items) -> None:
    found = {str(row.get("code")): row for row in list_batches(page, 200)}
    if not codes or any(code not in found for code in codes):
        raise RuntimeError("新批次未全部出现在批次管理。")
    item_count = sum(int(found[code].get("production_order_item_num") or 0)
                     for code in codes)
    piece_count = sum(int(found[code].get("production_piece_num") or 0)
                      for code in codes)
    if item_count != len(items) or piece_count != sum(item.qty for item in items):
        raise RuntimeError("批次管理的项目数或件数与提交整单不一致。")


def run_received_multi(expected: ReceivedPlan, progress=None):
    """Submit cross-size orders first, then exact same-size groups by composition."""
    from playwright.sync_api import sync_playwright

    report = progress or (lambda _message: None)
    platform = get_erp_platform("隆丰")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(playwright, platform.production_items_url)
        page = find_longfeng_page(browser)
        if preview_received_multi(page) != expected:
            raise RuntimeError("已接单快照发生变化，请重新制定批次计划。")
        defaults = [rule for rule in list_batch_rules(page) if rule.is_default]
        if len(defaults) != 1:
            raise RuntimeError("系统预设批次规则不唯一。")
        result = []
        failures = []
        for group in expected.groups:
            for part_number, orders in enumerate(_chunks(group), 1):
                label = f"{group.label} 第{part_number}组"
                items = tuple(item for order in orders for item in order)
                report(f"核对 {label}：{len(orders)} 单、{len(items)} 项")
                try:
                    _verify_orders(page, orders, submitted=False)
                    try:
                        generate_selected_batch(page, [item.item_id for item in items],
                                                defaults[0].id)
                    except Exception as error:
                        raise RuntimeError("提交结果不确定，先核对平台，禁止重试。") from error
                    codes = _verify_orders(page, orders, submitted=True)
                    _verify_batch_totals(page, codes, items)
                except Exception as error:
                    failures.append((label, str(error)))
                    report(f"{label} 未确认：{error}")
                    continue
                result.append((label, len(orders), len(items),
                               sum(item.qty for item in items), codes))
                report(f"{label} 已确认批次：{'、'.join(codes)}")
        return tuple(result), tuple(failures)
