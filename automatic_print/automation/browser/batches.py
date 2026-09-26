from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from ..transfer.downloads import download_production_images
from ..transfer.exports import ready_production_image_codes
from .session import connect_debug_chrome, open_authenticated_page
from ..api.erp import (
    list_batches,
    list_batches_between,
    production_batch_frame,
    production_item_count,
)
from ..providers.registry import get_erp_platform
from ..api.erp import BatchRecord, records_from_rows
@dataclass(frozen=True)
class PlatformOrderStatus:
    accepted_count: int
def load_platform_order_status(
    platform_name: str, progress=None, check_cancel=None
) -> PlatformOrderStatus:
    from playwright.sync_api import sync_playwright
    platform = get_erp_platform(platform_name)
    if progress:
        progress(f"正在准备连接 {platform.name} 生产项页面…")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_items_url, check_cancel,
            progress,
        )
        page = _production_items_page(
            browser, platform.production_items_url, progress, check_cancel
        )
        if progress:
            progress("正在通过 ERP API 读取“已接单”数量…")
        count = production_item_count(page, "1")
        if check_cancel:
            check_cancel()
        if progress:
            progress(f"ERP 已接单数量读取完成：{count} 项。")
        return PlatformOrderStatus(accepted_count=count)
def load_batch_records(
    platform_name: str, progress=None, check_cancel=None
) -> list[BatchRecord]:
    if check_cancel:
        check_cancel()
    if platform_name == "S2B":
        from ..api.s2b.production.downloads import list_s2b_batches
        source = list_s2b_batches(progress)
        if progress:
            progress(f"正在解析 S2B 返回的 {len(source)} 条批次记录…")
        records = [
            BatchRecord(
                record.batch_number,
                record.item_count,
                record.piece_count,
                " · ".join(filter(None, (record.name, record.personnel_label))),
                record.created_at,
                True,
                record.name,
            )
            for record in source
        ]
        if check_cancel:
            check_cancel()
        return records
    from playwright.sync_api import sync_playwright
    platform = get_erp_platform(platform_name)
    if progress:
        progress(f"正在准备连接 {platform.name} 生产批次页面…")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_batches_url, check_cancel,
            progress,
        )
        page = _batch_page(
            browser, platform.production_batches_url, progress, check_cancel
        )
        rows = _parse_api_rows(page, progress)
        if check_cancel:
            check_cancel()
        return rows
def load_batch_records_between(
    platform_name: str, start_code: str, end_code: str,
    progress=None, check_cancel=None,
) -> list[BatchRecord]:
    from playwright.sync_api import sync_playwright
    platform = get_erp_platform(platform_name)
    if progress:
        progress(
            f"正在读取批次范围 {start_code} 至 {end_code}…"
        )
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_batches_url, check_cancel,
            progress,
        )
        page = _batch_page(
            browser, platform.production_batches_url, progress, check_cancel
        )
        if progress:
            progress("生产批次表格已就绪；正在通过 ERP API 读取范围记录…")
        rows = list_batches_between(page, start_code, end_code)
        if progress:
            progress(f"ERP 返回 {len(rows)} 条记录；正在核对生产图状态…")
        if check_cancel:
            check_cancel()
        ready_codes = ready_production_image_codes(page, rows)
        ready_codes.update(
            _search_batch_codes(
                page, [str(row.get("code") or "") for row in rows],
                check_cancel, progress,
            )
        )
        if check_cancel:
            check_cancel()
        return records_from_rows(page, rows, ready_codes)
def _search_batch_codes(
    page, codes: list[str], check_cancel=None, progress=None
) -> set[str]:
    if not codes:
        return set()
    frame = production_batch_frame(page)
    search = frame.locator("input[placeholder*='批次号']")
    button = frame.get_by_text("搜 索", exact=True)
    if search.count() != 1 or button.count() != 1:
        return set()
    ready = set()
    for offset in range(0, len(codes), 3):
        if check_cancel:
            check_cancel()
        group = codes[offset : offset + 3]
        if progress:
            progress(
                f"[{min(offset + len(group), len(codes))}/{len(codes)}] "
                f"正在页面核对批次：{'、'.join(group)}"
            )
        search.fill(",".join(group))
        endpoint = "/production/v1/production/batch/page"
        with page.expect_response(
            lambda response: endpoint in response.url,
            timeout=30_000,
        ):
            button.click()
        frame.locator("tbody tr").filter(has_text=group[0]).first.wait_for(
            state="visible", timeout=10_000
        )
        if check_cancel:
            check_cancel()
        for text in frame.locator("tbody tr:visible").all_inner_texts():
            if text.count("下载") >= 3 and "生成成功" in text:
                ready.update(code for code in group if code in text)
    return ready
def _production_items_page(
    browser, url: str, progress=None, check_cancel=None
):
    return open_authenticated_page(
        browser,
        url,
        ".menu-item-title",
        progress=progress,
        check_cancel=check_cancel,
    )
def download_selected_batches(
    platform_name: str,
    batch_numbers: list[str],
    output_root: Path,
    progress=None,
    check_cancel=None,
) -> list[Path]:
    if check_cancel:
        check_cancel()
    if platform_name == "S2B":
        from ..api.s2b.production.downloads import download_s2b_exports
        files = download_s2b_exports(batch_numbers, output_root, progress)
        if check_cancel:
            check_cancel()
        return files
    from playwright.sync_api import sync_playwright
    if not batch_numbers:
        raise ValueError("请至少选择一个生产批次。")
    platform = get_erp_platform(platform_name)
    destination = output_root / platform.name
    if progress:
        progress(f"正在准备连接 {platform.name} 生产批次下载页面…")
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_batches_url, check_cancel,
            progress,
        )
        page = _batch_page(
            browser, platform.production_batches_url, progress, check_cancel
        )
        files = download_production_images(
            page,
            {"BATCHES": batch_numbers},
            destination,
            progress,
            extract=True,
        )
        if check_cancel:
            check_cancel()
        return files
def _batch_page(browser, url: str, progress=None, check_cancel=None):
    check = check_cancel or (lambda: None)
    check()
    host = urlsplit(url).netloc
    pages = [
        page
        for context in browser.contexts
        for page in context.pages
        if "/productionBatch/index" in page.url
        and host in page.url
    ]
    page = pages[-1] if pages else open_authenticated_page(
        browser, url, "iframe", progress=progress, ready_state="attached",
        check_cancel=check,
    )
    if pages and progress:
        progress(f"正在复用已打开的生产批次页面：{page.url}")
    check()
    if "/productionBatch/index" not in page.url:
        if progress: progress("当前不在生产批次页；正在打开生产批次…")
        production = page.get_by_text("生产", exact=True)
        if production.count():
            production.first.click()
        check()
        link = page.locator("a[href*='/productionBatch/index']")
        if link.count():
            link.first.click()
            if progress:
                progress("已点击“生产批次”；正在等待页面跳转…")
        else:
            if progress: progress("未显示侧栏入口；正在直接打开生产批次地址…")
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_url("**/productionBatch/index", timeout=30_000)
        check()
    if progress:
        progress("已进入生产批次页；正在等待批次表格加载…")
    for _ in range(60):
        check()
        try:
            frame = production_batch_frame(page)
            if frame.locator("th:visible").count():
                if progress:
                    progress("生产批次表格已加载。")
                return page
        except RuntimeError:
            pass
        page.wait_for_timeout(500)
    raise RuntimeError("ERP 生产批次表格在 30 秒内没有加载完成。")
def _parse_api_rows(page, progress=None) -> list[BatchRecord]:
    if progress:
        progress("正在通过 ERP API 读取生产批次列表…")
    rows = list_batches(page)
    if progress:
        progress(f"ERP 返回 {len(rows)} 条批次记录；正在读取生产图就绪状态…")
    ready_codes = ready_production_image_codes(page, rows)
    if progress:
        progress("生产图状态读取完成；正在整理批次列表…")
    records = records_from_rows(page, rows, ready_codes)
    if progress:
        progress(f"批次列表整理完成：{len(records)} 条。")
    return records
