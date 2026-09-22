"""A05 no-print supplement batches grouped by size, preserving mixed-size orders."""

from __future__ import annotations

from collections import defaultdict

from ...api.erp.items import (
    generate_supplement_batch,
    list_batch_rules,
    list_production_items,
    production_item_payload,
)
from ...browser.session import connect_debug_chrome
from ...providers.longfeng import find_longfeng_page
from ...providers.registry import get_erp_platform
from .models import SupplementGroup, SupplementItem, SupplementPlan


ROUTE_ID = 768786
STYLE_CODE = "T-LSJ-0"
SIZE_ORDER = ("S", "M", "L", "XL", "XXL", "3XL-5XL")


def _size_group(size: str) -> str:
    normalized = str(size).upper().replace("2XL", "XXL")
    if normalized in {"3XL", "4XL", "5XL"}:
        return "3XL-5XL"
    if normalized not in SIZE_ORDER:
        raise RuntimeError(f"无印花生产项存在未支持的尺码：{size}")
    return normalized


def _production_rows(page) -> list[dict]:
    payload = production_item_payload(status=("5",), page_size=200)
    payload["process_route_ids"] = [ROUTE_ID]
    first = list_production_items(page, payload)
    total = int(first.get("total") or 0)
    rows = list(first.get("list") or [])
    number = 1
    while len(rows) < total:
        number += 1
        current = list_production_items(page, {**payload, "page": number})
        part = list(current.get("list") or [])
        if not part:
            break
        rows.extend(part)
    if len(rows) != total:
        raise RuntimeError(f"A05 生产中接口应返回 {total} 项，实际 {len(rows)} 项。")
    return rows


def _selected_rows(page, source_batches: tuple[str, ...]) -> list[dict]:
    if not source_batches or len(set(source_batches)) != len(source_batches):
        raise ValueError("请提供互不重复的原始批次号。")
    rows = [row for row in _production_rows(page)
            if str(row.get("production_batch_code") or "") in source_batches]
    if {str(row.get("production_batch_code")) for row in rows} != set(source_batches):
        raise RuntimeError("部分原始批次不在 A05 生产中列表，无法完整补单。")
    if len({str(row.get("id")) for row in rows}) != len(rows):
        raise RuntimeError("A05 生产项接口返回重复 ID。")
    return rows


def _item(row: dict) -> SupplementItem:
    if int(row.get("status") or 0) != 5 or str(row.get("process_route_code")) != "A05" or str(
        row.get("style_code")
    ) != STYLE_CODE:
        raise RuntimeError("所选批次混入其他工艺路线或底款。")
    existing_codes = tuple(sorted({str(detail["production_batch_code"])
        for detail in row.get("supplement_detail_list") or []
        if detail.get("production_batch_code")}))
    if int(row.get("has_supplement") or 0) and not existing_codes:
        raise RuntimeError("生产项标记已有补单，但接口未给出补单批次号。")
    qty = int(row.get("qty") or 0)
    if qty <= 0 or not row.get("id") or not row.get("order_id"):
        raise RuntimeError("生产项缺少 ID、订单或正数件数。")
    _size_group(str(row.get("size") or ""))
    return SupplementItem(
        str(row["id"]), str(row["order_id"]),
        str(row["production_batch_code"]), str(row["size"]), qty,
        existing_codes,
    )


def preview_size_supplements(
    page, source_batches: tuple[str, ...], *, allow_existing_mixed: bool = False
) -> SupplementPlan:
    rows = _selected_rows(page, source_batches)
    items = tuple(_item(row) for row in rows)
    existing_ids = {item.item_id for item in items if item.existing_codes}
    order_sizes: dict[str, set[str]] = defaultdict(set)
    for item in items:
        order_sizes[item.order_id].add(str(item.size).upper().replace("2XL", "XXL"))
    mixed_orders = {order_id for order_id, sizes in order_sizes.items()
                    if len(sizes) > 1}
    partial_mixed = {item.order_id for item in items
                     if item.order_id in mixed_orders and item.item_id in existing_ids}
    pending = tuple(item for item in items if item.item_id not in existing_ids)
    groups = [SupplementGroup(
        size, tuple(item for item in pending
                    if item.order_id not in mixed_orders
                    and _size_group(item.size) == size),
    ) for size in SIZE_ORDER]
    groups = [group for group in groups if group.items]
    pending_mixed_orders = {item.order_id for item in pending
                            if item.order_id in mixed_orders}
    mixed = tuple(item for item in items if item.order_id in pending_mixed_orders
                  and (allow_existing_mixed or item.order_id not in partial_mixed))
    if mixed:
        groups.append(SupplementGroup("跨尺码整单", mixed))
    eligible_pending = {item.item_id for item in pending
                        if allow_existing_mixed or item.order_id not in partial_mixed}
    if {item.item_id for group in groups for item in group.items
        if not item.existing_codes} != eligible_pending:
        raise RuntimeError("补单分组未完整覆盖未补生产项。")
    return SupplementPlan(source_batches, tuple(groups), len(existing_ids),
                          tuple(sorted(partial_mixed)), allow_existing_mixed)


def run_size_supplements(
    expected: SupplementPlan, progress=None
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Submit once per group, then confirm every item and resulting batch code."""
    from playwright.sync_api import sync_playwright

    report = progress or (lambda _message: None)
    platform = get_erp_platform("隆丰")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(playwright, platform.production_items_url)
        page = find_longfeng_page(browser)
        if preview_size_supplements(
            page, expected.source_batches,
            allow_existing_mixed=expected.allow_existing_mixed,
        ) != expected:
            raise RuntimeError("生产项或已有补单已变化，请重新读取计划。")
        defaults = [rule for rule in list_batch_rules(page) if rule.is_default]
        if len(defaults) != 1:
            raise RuntimeError("系统预设补单规则不唯一。")
        created = []
        for number, group in enumerate(expected.groups, 1):
            report(f"[{number}/{len(expected.groups)}] 补单 {group.label}："
                   f"{len(group.items)} 项 / {group.piece_count} 件")
            current = {str(row["id"]): row for row in _selected_rows(
                page, expected.source_batches
            )}
            if any(item.item_id not in current or _item(current[item.item_id]) != item
                   for item in group.items):
                raise RuntimeError(f"{group.label} 项目或已有补单已变化，禁止重复提交。")
            generate_supplement_batch(
                page, [(item.item_id, item.qty) for item in group.items],
                defaults[0].id,
            )
            for _ in range(20):
                current = {str(row["id"]): row for row in _selected_rows(
                    page, expected.source_batches
                )}
                new_codes = [
                    {str(detail["production_batch_code"])
                     for detail in current[item.item_id].get("supplement_detail_list") or []
                     if detail.get("production_batch_code")}
                    - set(item.existing_codes)
                    for item in group.items
                ]
                if all(len(codes) == 1 for codes in new_codes):
                    codes = tuple(sorted({code for matches in new_codes
                                          for code in matches}))
                    created.append((group.label, codes))
                    report(f"{group.label} 已确认补单批次 {'、'.join(codes)}")
                    break
                page.wait_for_timeout(500)
            else:
                raise RuntimeError(
                    f"{group.label} 已提交但未能确认每项的新补单批次；禁止重试。"
                )
        return tuple(created)
