from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .batch_downloads import download_production_images
from .chrome_session import connect_debug_chrome
from .longfeng import (
    PRODUCTION_ITEMS_URL,
    ShippingBatchPlan,
    _filtered_result_count,
    _run_search,
    _select_filter,
    _select_received,
    find_longfeng_page,
    preview_shipping_split,
    production_frame,
)
from .platforms import get_erp_platform


@dataclass(frozen=True)
class WorkflowResult:
    plan: ShippingBatchPlan
    batch_groups: dict[str, list[str]]
    downloaded: list[Path]


def run_shipping_workflow(
    expected_plan: ShippingBatchPlan,
    output_root: Path,
    progress=None,
) -> WorkflowResult:
    from playwright.sync_api import sync_playwright

    report = progress or (lambda _message: None)
    platform = get_erp_platform(expected_plan.client)
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_items_url
        )
        page = find_longfeng_page(browser, platform.name)
        report("重新核对 CBT / 非 CBT 数量")
        actual = preview_shipping_split(page, platform.name)
        if actual != expected_plan:
            raise RuntimeError(
                "页面数量已变化，已停止生成。\n"
                f"确认时：{expected_plan.confirmation_text}\n"
                f"现在：{actual.confirmation_text}"
            )

        batch_page = _open_batch_page(
            page, platform.production_batches_url
        )
        original_ids = set(_batch_rows(batch_page))

        report(f"正在生成 CBT 批次：{actual.cbt_count} 项")
        _generate_batch(page, "CBT", actual.cbt_count)
        remaining = _received_count(page, "全部")
        if remaining != actual.non_cbt_count:
            raise RuntimeError(
                f"CBT 生成后应剩 {actual.non_cbt_count} 项，实际为 {remaining} 项。"
            )
        cbt_batches = _wait_for_new_batches(
            batch_page, original_ids, actual.cbt_count
        )

        report(f"正在生成非 CBT 批次：{actual.non_cbt_count} 项")
        _generate_batch(page, "全部", actual.non_cbt_count)
        if _received_count(page, "全部") != 0:
            raise RuntimeError("非 CBT 生成后仍有已接单生产项，已停止下载。")
        known_ids = original_ids | set(cbt_batches)
        non_cbt_batches = _wait_for_new_batches(
            batch_page, known_ids, actual.non_cbt_count
        )

        groups = {"CBT": cbt_batches, "NON_CBT": non_cbt_batches}
        report(
            f"批次生成完成：CBT {len(cbt_batches)} 个，"
            f"非 CBT {len(non_cbt_batches)} 个"
        )
        downloaded = download_production_images(
            batch_page, groups, output_root, report, extract=True
        )
        return WorkflowResult(actual, groups, downloaded)


def _generate_batch(page, shipping_method: str, expected_count: int) -> None:
    if expected_count <= 0:
        return
    count = _received_count(page, shipping_method)
    if count != expected_count:
        raise RuntimeError(
            f"{shipping_method} 预期 {expected_count} 项，实际 {count} 项。"
        )
    frame = production_frame(page)
    button = frame.get_by_text("按筛选生成批次", exact=True)
    if button.count() != 1:
        raise RuntimeError("无法唯一定位“按筛选生成批次”。")
    button.click()
    dialog = page.locator("[role=dialog]:visible")
    dialog.wait_for(state="visible", timeout=10_000)
    text = dialog.inner_text().replace(" ", "")
    if f"共{expected_count}项" not in text:
        raise RuntimeError(f"确认窗口数量不一致：{dialog.inner_text()}")
    confirm = dialog.get_by_text("确 定", exact=True)
    if confirm.count() != 1:
        raise RuntimeError("无法唯一定位批次确认按钮。")
    confirm.click()
    dialog.wait_for(state="hidden", timeout=180_000)


def _received_count(page, shipping_method: str) -> int:
    _select_received(page)
    frame = production_frame(page)
    _select_filter(frame, "物流分拣", shipping_method)
    _run_search(frame)
    if frame.locator(".ant-empty:visible").count():
        return 0
    return _filtered_result_count(frame)


def _open_batch_page(source_page, batch_page_url: str):
    pages = [
        page
        for page in source_page.context.pages
        if "/productionBatch/index" in page.url
        and page.locator("th:visible").count()
    ]
    page = pages[-1] if pages else source_page.context.new_page()
    if "/productionBatch/index" not in page.url:
        page.goto(batch_page_url, wait_until="domcontentloaded")
    page.locator("th:visible").first.wait_for(state="visible", timeout=30_000)
    return page


def _batch_rows(page) -> dict[str, int]:
    page.reload(wait_until="domcontentloaded")
    page.locator("tbody tr:visible").first.wait_for(
        state="visible", timeout=30_000
    )
    result: dict[str, int] = {}
    rows = page.locator("tbody tr:visible")
    for text in rows.all_inner_texts():
        batch = re.search(r"\b(\d{12})\b", text)
        count = re.search(r"(\d+)项\d+件", text.replace(" ", ""))
        if batch and count:
            result[batch.group(1)] = int(count.group(1))
    return result


def _wait_for_new_batches(
    page, existing_ids: set[str], expected_items: int
) -> list[str]:
    for _ in range(60):
        rows = _batch_rows(page)
        new_ids = [batch for batch in rows if batch not in existing_ids]
        if sum(rows[batch] for batch in new_ids) == expected_items:
            return new_ids
        page.wait_for_timeout(1000)
    raise RuntimeError(
        f"一分钟内没有找到合计 {expected_items} 项的新生产批次。"
    )
