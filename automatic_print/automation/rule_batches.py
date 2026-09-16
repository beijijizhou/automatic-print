from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

from .chrome_session import connect_debug_chrome
from .batch_classification import (
    classify_order_composition,
    composition_filter,
    detailed_compositions,
)
from .erp_api import (
    find_batch_rule,
    generate_filtered_batch,
    list_all_received_items,
    list_production_items,
    production_item_payload,
)
from .longfeng import find_longfeng_page
from .platforms import get_erp_platform


@dataclass(frozen=True)
class RuleBatchItem:
    shipping_method: str
    order_composition: str
    item_count: int


@dataclass(frozen=True)
class RuleBatchPlan:
    platform_name: str
    items: tuple[RuleBatchItem, ...]
    received_count: int
    excluded_items: tuple[RuleBatchItem, ...] = ()

    @property
    def total_items(self) -> int:
        return sum(item.item_count for item in self.items)

    @property
    def nonempty_items(self) -> tuple[RuleBatchItem, ...]:
        return tuple(item for item in self.items if item.item_count > 0)

    @property
    def excluded_count(self) -> int:
        return sum(item.item_count for item in self.excluded_items)


def preview_rule_batch_plan(
    platform_name: str, progress=None
) -> RuleBatchPlan:
    from playwright.sync_api import sync_playwright

    report = progress or (lambda _message: None)
    platform = get_erp_platform(platform_name)
    if not platform.shipping_categories:
        raise RuntimeError(f"{platform_name} 尚未配置物流分类规则。")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_items_url
        )
        page = find_longfeng_page(browser, platform_name)
        return _preview_plan_from_api(page, platform, report)


def generate_rule_batches(
    expected_plan: RuleBatchPlan,
    generation_rule: str,
    progress=None,
) -> int:
    from playwright.sync_api import sync_playwright

    report = progress or (lambda _message: None)
    platform = get_erp_platform(expected_plan.platform_name)
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_items_url
        )
        page = find_longfeng_page(browser, platform.name)
        report("生成前正在重新核对全部分类数量…")
        actual_plan = _preview_plan_from_api(page, platform, report)
        if actual_plan != expected_plan:
            raise RuntimeError(
                "ERP 页面数量已经变化，已停止生成批次。"
                "请重新读取分类数量并再次确认。"
            )

        rule = find_batch_rule(page, generation_rule)
        generated = 0
        nonempty = expected_plan.nonempty_items
        for index, item in enumerate(nonempty, start=1):
            report(
                f"[{index}/{len(nonempty)}] 正在生成 "
                f"{item.shipping_method} / {item.order_composition} / "
                f"{item.item_count} 项"
            )
            _generate_filtered_batch_api(page, item, platform, rule.id)
            generated += 1
        return generated


def _preview_plan_from_api(page, platform, report) -> RuleBatchPlan:
    report("正在通过 ERP 列表接口一次读取全部已接单生产项…")
    rows, received_count = _load_all_received_rows(page)
    reverse_shipping = {
        platform.shipping_filter_value(name): name
        for name in platform.shipping_categories
    }
    grouped = Counter()
    for row in rows:
        shipping_code = str(row.get("logistics_sorting_code") or "")
        shipping_name = reverse_shipping.get(shipping_code, shipping_code)
        composition = classify_order_composition(row)
        grouped[(shipping_name, composition)] += 1
    items = tuple(
        RuleBatchItem(
            shipping,
            composition,
            grouped[(shipping, composition)],
        )
        for shipping in platform.shipping_categories
        for composition in detailed_compositions(
            platform.order_compositions
        )
    )
    report(
        f"接口读取完成：{received_count} 项，"
        f"{sum(1 for item in items if item.item_count)} 个非空分类。"
    )
    return RuleBatchPlan(platform.name, items, received_count)


def _load_all_received_rows(page) -> tuple[list[dict], int]:
    return list_all_received_items(page)


def _generate_filtered_batch_api(
    page, item: RuleBatchItem, platform, batch_rule_id: int | str
) -> None:
    composition_code, view_count = composition_filter(
        item.order_composition
    )
    payload = production_item_payload(
        shipping_codes=(
            platform.shipping_filter_value(item.shipping_method),
        ),
        order_compositions=(composition_code,),
    )
    if view_count is not None:
        payload["view_count"] = view_count
    current = list_production_items(page, {**payload, "page_size": 1})
    actual_count = int(current.get("total") or 0)
    if actual_count != item.item_count:
        raise RuntimeError(
            f"{item.shipping_method} / {item.order_composition} "
            f"确认时为 {item.item_count} 项，现在为 {actual_count} 项。"
        )
    try:
        generate_filtered_batch(page, payload, batch_rule_id)
    except Exception as error:
        raise RuntimeError(
            f"{item.shipping_method} / {item.order_composition} "
            "API 返回不确定结果。为避免重复生成，程序不会自动重试；"
            "请先刷新批次管理确认结果。"
        ) from error
