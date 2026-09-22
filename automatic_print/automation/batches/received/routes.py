"""Generate received Longfeng items by one exact process route."""

from __future__ import annotations

from dataclasses import dataclass

from ...api.erp.items import list_all_received_items
from ...api.erp.gateway import production_batch_frame
from ...api.erp.batches import list_batches
from ...browser.session import connect_debug_chrome
from ...providers.longfeng import (
    _filtered_result_count,
    _run_search,
    _select_filter,
    _select_received,
    find_longfeng_page,
    production_frame,
)
from ...providers.registry import get_erp_platform
from ...workflows.shipping import (
    _generate_batch,
    _open_batch_page,
)


@dataclass(frozen=True)
class RouteBatchPlan:
    routes: tuple[str, ...]
    selected_route: str
    route_id: str
    item_count: int
    all_received_count: int
    order_count: int = 0
    piece_count: int = 0
    order_details: tuple[tuple[str, int, int], ...] = ()


@dataclass(frozen=True)
class RouteBatchResult:
    plan: RouteBatchPlan
    batch_codes: tuple[str, ...]
    batch_status: tuple[str, ...]


def _preview(page, route_label: str) -> RouteBatchPlan:
    _select_received(page)
    frame = production_frame(page)
    routes = tuple(frame.locator('[label="工艺路线"] .item span').all_inner_texts())
    if not routes or len(routes) != len(set(routes)) or route_label not in routes:
        raise RuntimeError(f"无法唯一找到工艺路线 {route_label}。")
    code = route_label.partition("-")[0]
    rows, total = list_all_received_items(page)
    matching = [row for row in rows if row.get("process_route_code") == code]
    ids = {str(row.get("process_route_id") or "") for row in matching}
    if matching and (len(ids) != 1 or "" in ids):
        raise RuntimeError(f"工艺路线 {route_label} 没有唯一的待生成路线 ID。")
    if any(row.get("production_batch_id") for row in matching):
        raise RuntimeError("已接单列表包含已有批次的项目，不能重复生成。")
    _select_filter(frame, "工艺路线", route_label)
    _run_search(frame)
    visible_count = (
        0 if frame.locator(".ant-empty:visible").count()
        else _filtered_result_count(frame)
    )
    if visible_count != len(matching):
        raise RuntimeError(
            f"{route_label} 列表显示 {visible_count} 项，接口返回 {len(matching)} 项。"
        )
    if any(not row.get("order_id") or int(row.get("qty") or 0) <= 0
           for row in matching):
        raise RuntimeError(f"{route_label} 缺少订单身份或有效件数，不能预览批次。")
    by_order: dict[str, tuple[int, int]] = {}
    for row in matching:
        order_id = str(row["order_id"])
        count, pieces = by_order.get(order_id, (0, 0))
        by_order[order_id] = (count + 1, pieces + int(row["qty"]))
    return RouteBatchPlan(
        routes, route_label, ids.pop() if ids else "", len(matching), total,
        len(by_order),
        sum(int(row["qty"]) for row in matching),
        tuple(sorted((order_id, count, pieces)
                     for order_id, (count, pieces) in by_order.items())),
    )


def preview_route_batch(route_label: str = "A05-无印花") -> RouteBatchPlan:
    from playwright.sync_api import sync_playwright

    platform = get_erp_platform("隆丰")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(playwright, platform.production_items_url)
        page = find_longfeng_page(browser)
        page.reload(wait_until="domcontentloaded")
        page.locator(".menu-item-title").first.wait_for(state="visible", timeout=30_000)
        return _preview(page, route_label)


def generate_route_batch(
    expected: RouteBatchPlan, progress=None
) -> RouteBatchResult:
    from playwright.sync_api import sync_playwright

    report = progress or (lambda _message: None)
    platform = get_erp_platform("隆丰")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(playwright, platform.production_items_url)
        page = find_longfeng_page(browser)
        page.reload(wait_until="domcontentloaded")
        page.locator(".menu-item-title").first.wait_for(state="visible", timeout=30_000)
        actual = _preview(page, expected.selected_route)
        if actual != expected:
            raise RuntimeError("已接单或工艺路线列表已变化，请重新读取后再生成。")
        batch_page = _open_batch_page(page, platform.production_batches_url)
        existing = {str(row.get("code")) for row in list_batches(batch_page, 200)}
        report(f"正在按筛选生成 {actual.selected_route}：{actual.item_count} 项")
        try:
            _generate_batch(page, "全部", actual.item_count)
        except Exception as error:
            raise RuntimeError(
                "批次提交结果不确定。请先到批次管理核对，不能直接重试。"
            ) from error
        new_rows = []
        for _ in range(60):
            new_rows = [
                row for row in list_batches(batch_page, 200)
                if str(row.get("code")) not in existing
                and any(
                    route.get("code") == actual.selected_route.partition("-")[0]
                    for route in row.get("process_route_list") or []
                )
            ]
            if sum(int(row.get("production_order_item_num") or 0)
                   for row in new_rows) == actual.item_count:
                break
            batch_page.wait_for_timeout(1000)
        else:
            raise RuntimeError(
                "批次已提交，但批次管理未在一分钟内显示完整项目数；"
                "请核对后再决定是否重试。"
            )
        new_codes = tuple(str(row["code"]) for row in new_rows)
        batch_page.reload(wait_until="domcontentloaded")
        for _ in range(60):
            try:
                frame = production_batch_frame(batch_page)
                if frame.locator("th:visible").count():
                    break
            except RuntimeError:
                pass
            batch_page.wait_for_timeout(500)
        else:
            raise RuntimeError(
                "批次已生成，但批次管理表格尚未加载；请按批次号核对状态："
                + "、".join(new_codes)
            )
        status = tuple(
            f"{code}：生产进度 {float(row.get('progress') or 0):.0%}，"
            + ("导出栏显示生成成功" if "生成成功" in frame.locator(
                "tbody tr:visible"
            ).filter(has_text=code).first.inner_text() else "导出栏待确认")
            for code, row in ((str(item["code"]), item) for item in new_rows)
        )
        report(f"批次管理已找到 {len(new_codes)} 个新批次。")
        return RouteBatchResult(actual, new_codes, status)
