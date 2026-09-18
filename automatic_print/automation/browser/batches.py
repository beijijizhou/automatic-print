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
    platform_name: str, progress=None
) -> PlatformOrderStatus:
    from playwright.sync_api import sync_playwright
    platform = get_erp_platform(platform_name)
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_items_url
        )
        page = _production_items_page(
            browser, platform.production_items_url, progress
        )
        if progress:
            progress("正在通过 ERP API 读取“已接单”数量…")
        return PlatformOrderStatus(
            accepted_count=production_item_count(page, "1"),
        )
def load_batch_records(platform_name: str, progress=None) -> list[BatchRecord]:
    if platform_name == "S2B":
        from ..api.s2b.production.downloads import list_s2b_batches
        return [
            BatchRecord(
                record.batch_number,
                record.item_count,
                record.piece_count,
                " · ".join(filter(None, (record.name, record.personnel_label))),
                record.created_at,
                True,
            )
            for record in list_s2b_batches(progress)
        ]
    from playwright.sync_api import sync_playwright
    platform = get_erp_platform(platform_name)
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_batches_url
        )
        page = _batch_page(browser, platform.production_batches_url)
        return _parse_api_rows(page)
def load_batch_records_between(
    platform_name: str, start_code: str, end_code: str
) -> list[BatchRecord]:
    from playwright.sync_api import sync_playwright
    platform = get_erp_platform(platform_name)
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_batches_url
        )
        page = _batch_page(browser, platform.production_batches_url)
        rows = list_batches_between(page, start_code, end_code)
        ready_codes = ready_production_image_codes(page, rows)
        ready_codes.update(
            _search_batch_codes(
                page, [str(row.get("code") or "") for row in rows]
            )
        )
        return records_from_rows(page, rows, ready_codes)
def _search_batch_codes(page, codes: list[str]) -> set[str]:
    if not codes:
        return set()
    frame = production_batch_frame(page)
    search = frame.locator("input[placeholder*='批次号']")
    button = frame.get_by_text("搜 索", exact=True)
    if search.count() != 1 or button.count() != 1:
        return set()
    ready = set()
    for offset in range(0, len(codes), 3):
        group = codes[offset : offset + 3]
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
        for text in frame.locator("tbody tr:visible").all_inner_texts():
            if text.count("下载") >= 3 and "生成成功" in text:
                ready.update(code for code in group if code in text)
    return ready
def _production_items_page(browser, url: str, progress=None):
    return open_authenticated_page(
        browser,
        url,
        ".menu-item-title",
        progress=progress,
    )
def download_selected_batches(
    platform_name: str,
    batch_numbers: list[str],
    output_root: Path,
    progress=None,
) -> list[Path]:
    if platform_name == "S2B":
        from ..api.s2b.production.downloads import download_s2b_exports
        return download_s2b_exports(batch_numbers, output_root, progress)
    from playwright.sync_api import sync_playwright
    if not batch_numbers:
        raise ValueError("请至少选择一个生产批次。")
    platform = get_erp_platform(platform_name)
    destination = output_root / platform.name
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(
            playwright, platform.production_batches_url
        )
        page = _batch_page(browser, platform.production_batches_url)
        return download_production_images(
            page,
            {"BATCHES": batch_numbers},
            destination,
            progress,
            extract=True,
        )
def _batch_page(browser, url: str):
    host = urlsplit(url).netloc
    pages = [
        page
        for context in browser.contexts
        for page in context.pages
        if "/productionBatch/index" in page.url
        and host in page.url
    ]
    page = pages[-1] if pages else open_authenticated_page(
        browser, url, "iframe", ready_state="attached"
    )
    if "/productionBatch/index" not in page.url:
        production = page.get_by_text("生产", exact=True)
        if production.count():
            production.first.click()
        link = page.locator("a[href*='/productionBatch/index']")
        link.first.wait_for(state="visible", timeout=10_000)
        link.first.click()
        page.wait_for_url("**/productionBatch/index", timeout=30_000)
    for _ in range(60):
        try:
            frame = production_batch_frame(page)
            if frame.locator("th:visible").count():
                return page
        except RuntimeError:
            pass
        page.wait_for_timeout(500)
    raise RuntimeError("ERP 生产批次表格在 30 秒内没有加载完成。")
def _parse_api_rows(page) -> list[BatchRecord]:
    rows = list_batches(page)
    ready_codes = ready_production_image_codes(page, rows)
    return records_from_rows(page, rows, ready_codes)
