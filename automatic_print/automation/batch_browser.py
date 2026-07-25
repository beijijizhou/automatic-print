from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .batch_downloads import download_production_images
from .batch_exports import ready_production_image_codes
from .chrome_session import connect_debug_chrome, open_authenticated_page
from .erp_api import (
    list_batches,
    list_batches_between,
    production_item_count,
)
from .platforms import get_erp_platform


@dataclass(frozen=True)
class BatchRecord:
    batch_number: str
    item_count: int
    piece_count: int
    batch_type: str
    created_at: str
    production_images_ready: bool


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


def load_batch_records(platform_name: str) -> list[BatchRecord]:
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
        return _records_from_rows(page, rows, ready_codes)


def _search_batch_codes(page, codes: list[str]) -> set[str]:
    if not codes:
        return set()
    search = page.locator("input[placeholder*='批次号']")
    button = page.get_by_text("搜 索", exact=True)
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
        page.locator("tbody tr").filter(has_text=group[0]).first.wait_for(
            state="visible", timeout=10_000
        )
        for text in page.locator("tbody tr:visible").all_inner_texts():
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
        and page.locator("th:visible").count()
    ]
    if pages:
        return pages[-1]
    return open_authenticated_page(browser, url, "th:visible")


def _parse_api_rows(page) -> list[BatchRecord]:
    rows = list_batches(page)
    ready_codes = ready_production_image_codes(page, rows)
    return _records_from_rows(page, rows, ready_codes)


def _records_from_rows(page, api_rows, ready_codes=None) -> list[BatchRecord]:
    ready_codes = ready_codes or set()
    records = []
    visible_text = {
        match.group(1): text
        for text in page.locator("tbody tr:visible").all_inner_texts()
        if (match := re.search(r"\b(\d{12})\b", text))
    }
    composition_names = {
        "1": "单项单件",
        "2": "单项多件",
        "3": "多项多件",
    }
    for row in api_rows:
        created = row.get("created")
        created_text = (
            datetime.fromtimestamp(int(created) / 1000).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if created
            else ""
        )
        row_text = visible_text.get(str(row.get("code") or ""), "")
        ready = (
            row_text.count("下载") >= 3 and "生成成功" in row_text
        ) or str(row.get("code") or "") in ready_codes
        records.append(
            BatchRecord(
                batch_number=str(row.get("code") or ""),
                item_count=int(row.get("production_order_item_num") or 0),
                piece_count=int(row.get("production_piece_num") or 0),
                batch_type=composition_names.get(
                    str(row.get("order_composition") or ""), "其他"
                ),
                created_at=created_text,
                production_images_ready=ready,
            )
        )
    return records
