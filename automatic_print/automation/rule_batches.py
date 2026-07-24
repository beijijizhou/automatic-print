from __future__ import annotations

from dataclasses import dataclass

from .chrome_session import connect_debug_chrome
from .longfeng import (
    _filtered_result_count,
    _run_search,
    _select_filter,
    _select_received,
    find_longfeng_page,
    production_frame,
)
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

    @property
    def total_items(self) -> int:
        return sum(item.item_count for item in self.items)

    @property
    def nonempty_items(self) -> tuple[RuleBatchItem, ...]:
        return tuple(item for item in self.items if item.item_count > 0)


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
        received_count = _all_received_count(page)
        items = []
        combinations = [
            (shipping, composition)
            for shipping in platform.shipping_categories
            for composition in platform.order_compositions
        ]
        for index, (shipping, composition) in enumerate(
            combinations, start=1
        ):
            report(
                f"[{index}/{len(combinations)}] 正在读取 "
                f"{shipping} / {composition}"
            )
            items.append(
                RuleBatchItem(
                    shipping,
                    composition,
                    _filtered_count(
                        page, shipping, composition, platform
                    ),
                )
            )
        return RuleBatchPlan(platform_name, tuple(items), received_count)


def generate_rule_batches(
    expected_plan: RuleBatchPlan, progress=None
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
        actual_items = tuple(
            RuleBatchItem(
                item.shipping_method,
                item.order_composition,
                _filtered_count(
                    page,
                    item.shipping_method,
                    item.order_composition,
                    platform,
                ),
            )
            for item in expected_plan.items
        )
        actual_plan = RuleBatchPlan(
            platform.name, actual_items, _all_received_count(page)
        )
        if actual_plan != expected_plan:
            raise RuntimeError(
                "ERP 页面数量已经变化，已停止生成批次。"
                "请重新读取分类数量并再次确认。"
            )

        generated = 0
        nonempty = expected_plan.nonempty_items
        for index, item in enumerate(nonempty, start=1):
            report(
                f"[{index}/{len(nonempty)}] 正在生成 "
                f"{item.shipping_method} / {item.order_composition} / "
                f"{item.item_count} 项"
            )
            _generate_filtered_batch(page, item, platform)
            generated += 1
        return generated


def _filtered_count(
    page, shipping_method: str, order_composition: str, platform
) -> int:
    _select_received(page)
    frame = production_frame(page)
    _select_filter(
        frame,
        "物流分拣",
        platform.shipping_filter_value(shipping_method),
    )
    _select_filter(frame, "订单组成", order_composition)
    _run_search(frame)
    if frame.locator(".ant-empty:visible").count():
        return 0
    return _filtered_result_count(frame)


def _all_received_count(page) -> int:
    _select_received(page)
    frame = production_frame(page)
    _select_filter(frame, "物流分拣", "全部")
    _select_filter(frame, "订单组成", "全部")
    _run_search(frame)
    if frame.locator(".ant-empty:visible").count():
        return 0
    return _filtered_result_count(frame)


def _generate_filtered_batch(page, item: RuleBatchItem, platform) -> None:
    actual_count = _filtered_count(
        page, item.shipping_method, item.order_composition, platform
    )
    if actual_count != item.item_count:
        raise RuntimeError(
            f"{item.shipping_method} / {item.order_composition} "
            f"确认时为 {item.item_count} 项，现在为 {actual_count} 项。"
        )
    frame = production_frame(page)
    button = frame.get_by_text("按筛选生成批次", exact=True)
    if button.count() != 1:
        raise RuntimeError("无法唯一定位“按筛选生成批次”按钮。")
    button.click()
    dialog = page.locator("[role=dialog]:visible")
    dialog.wait_for(state="visible", timeout=10_000)
    compact_text = dialog.inner_text().replace(" ", "")
    if f"共{item.item_count}项" not in compact_text:
        raise RuntimeError(f"确认窗口数量不一致：{dialog.inner_text()}")
    confirm = dialog.get_by_text("确 定", exact=True)
    if confirm.count() != 1:
        raise RuntimeError("无法唯一定位批次确认按钮。")
    confirm.click()
    dialog.wait_for(state="hidden", timeout=180_000)
