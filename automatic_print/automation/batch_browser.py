from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .batch_downloads import download_production_images
from .chrome_session import connect_debug_chrome, open_authenticated_page
from .erp_api import list_batches, production_item_count
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
    production_count: int

    @property
    def cleared(self) -> bool:
        return self.production_count == 0


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
            progress("正在通过 ERP API 读取“已接单”和“生产中”数量…")
        return PlatformOrderStatus(
            accepted_count=production_item_count(page, "1"),
            production_count=production_item_count(page, "5"),
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


def _production_items_page(browser, url: str, progress=None):
    return open_authenticated_page(
        browser,
        url,
        ".menu-item-title",
        progress=progress,
    )


def _menu_count(texts: list[str], label: str) -> int:
    matches = [
        re.search(rf"^{re.escape(label)}\s*[（(](\d+)[）)]", text.strip())
        for text in texts
    ]
    counts = [int(match.group(1)) for match in matches if match]
    if len(counts) != 1:
        raise RuntimeError(f"无法读取 ERP 平台“{label}”数量。")
    return counts[0]


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


def _parse_visible_rows(page) -> list[BatchRecord]:
    records: list[BatchRecord] = []
    rows = page.locator("tbody tr:visible")
    for text in rows.all_inner_texts():
        compact = text.replace(" ", "")
        batch = re.search(r"\b(\d{12})\b", text)
        quantities = re.search(r"(\d+)项(\d+)件", compact)
        created = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text)
        if not batch or not quantities:
            continue
        batch_type = next(
            (
                value
                for value in ("单项单件", "单项多件", "多项多件")
                if value in text
            ),
            "其他",
        )
        records.append(
            BatchRecord(
                batch_number=batch.group(1),
                item_count=int(quantities.group(1)),
                piece_count=int(quantities.group(2)),
                batch_type=batch_type,
                created_at=created.group(0) if created else "",
                production_images_ready=(
                    text.count("下载") >= 3 and "生成成功" in text
                ),
            )
        )
    return records


def _parse_api_rows(page) -> list[BatchRecord]:
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
    for row in list_batches(page):
        created = row.get("created")
        created_text = (
            datetime.fromtimestamp(int(created) / 1000).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if created
            else ""
        )
        row_text = visible_text.get(str(row.get("code") or ""), "")
        records.append(
            BatchRecord(
                batch_number=str(row.get("code") or ""),
                item_count=int(row.get("production_order_item_num") or 0),
                piece_count=int(row.get("production_piece_num") or 0),
                batch_type=composition_names.get(
                    str(row.get("order_composition") or ""), "其他"
                ),
                created_at=created_text,
                production_images_ready=(
                    row_text.count("下载") >= 3 and "生成成功" in row_text
                ),
            )
        )
    return records
