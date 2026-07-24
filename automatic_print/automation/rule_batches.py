from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

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

        generated = 0
        nonempty = expected_plan.nonempty_items
        for index, item in enumerate(nonempty, start=1):
            report(
                f"[{index}/{len(nonempty)}] 正在生成 "
                f"{item.shipping_method} / {item.order_composition} / "
                f"{item.item_count} 项"
            )
            _generate_filtered_batch(
                page, item, platform, generation_rule
            )
            generated += 1
        return generated


def _preview_plan_from_api(page, platform, report) -> RuleBatchPlan:
    report("正在通过 ERP 列表接口一次读取全部已接单生产项…")
    rows, received_count = _load_all_received_rows(page)
    composition_names = {
        "1": "单项单件",
        "2": "单项多件",
        "3": "多项多件",
    }
    reverse_shipping = {
        platform.shipping_filter_value(name): name
        for name in platform.shipping_categories
    }
    grouped = Counter()
    for row in rows:
        shipping_code = str(row.get("logistics_sorting_code") or "")
        shipping_name = reverse_shipping.get(shipping_code, shipping_code)
        composition = composition_names.get(
            str(row.get("order_composition") or ""),
            str(row.get("order_composition") or "未知"),
        )
        grouped[(shipping_name, composition)] += 1
    items = tuple(
        RuleBatchItem(
            shipping,
            composition,
            grouped[(shipping, composition)],
        )
        for shipping in platform.shipping_categories
        for composition in platform.order_compositions
    )
    report(
        f"接口读取完成：{received_count} 项，"
        f"{sum(1 for item in items if item.item_count)} 个非空分类。"
    )
    return RuleBatchPlan(platform.name, items, received_count)


def _load_all_received_rows(page) -> tuple[list[dict], int]:
    _select_received(page)
    frame = production_frame(page)
    _select_filter(frame, "物流分拣", "全部")
    _select_filter(frame, "订单组成", "全部")
    endpoint = "/production/v1/production/order/item/page"
    with page.expect_response(
        lambda response: endpoint in response.url,
        timeout=15_000,
    ) as response_info:
        _run_search(frame)
    data = response_info.value.json()["data"]
    rows = data["list"]
    total = int(data["total"])
    if len(rows) < total:
        size_selector = frame.locator(
            ".ant-pagination-options .ant-select"
        ).first
        if size_selector.count() != 1:
            raise RuntimeError("无法切换 ERP 列表为每页 200 条。")
        size_selector.click()
        option = page.locator(".ant-select-item-option:visible").filter(
            has_text="200 条/页"
        )
        if option.count() != 1:
            raise RuntimeError("ERP 列表中没有“200 条/页”选项。")
        with page.expect_response(
            lambda response: endpoint in response.url,
            timeout=15_000,
        ) as response_info:
            option.click()
        data = response_info.value.json()["data"]
        rows = data["list"]
        total = int(data["total"])
    if len(rows) != total:
        raise RuntimeError(
            f"ERP 接口返回 {len(rows)} 项，但总数为 {total}，已停止。"
        )
    return rows, total


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


def _generate_filtered_batch(
    page, item: RuleBatchItem, platform, generation_rule: str
) -> None:
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
    selector = dialog.locator(".ant-select").first
    if selector.count() != 1:
        raise RuntimeError("无法定位批次生成规则选择框。")
    selector.click()
    option = page.locator(".ant-select-item-option:visible").filter(
        has_text=generation_rule
    )
    if option.count() != 1:
        raise RuntimeError(f"无法选择“{generation_rule}”。")
    option.click()
    if generation_rule not in dialog.inner_text():
        raise RuntimeError(f"批次生成规则没有成功选择为“{generation_rule}”。")
    confirm = dialog.get_by_text("确 定", exact=True)
    if confirm.count() != 1:
        raise RuntimeError("无法唯一定位批次确认按钮。")
    confirm.click()
    dialog.wait_for(state="hidden", timeout=180_000)
