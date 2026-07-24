from __future__ import annotations

import re
from dataclasses import dataclass

from .chrome_session import open_authenticated_page
from .platforms import get_erp_platform


LONGFENG_HOST = "longfeng.merchant.hihumbird.com"
PRODUCTION_ITEMS_URL = (
    "https://longfeng.merchant.hihumbird.com/factory/"
    "fnsz-sale/produceManage/produceItemsManage"
)
ORDER_COMPOSITIONS = ("单项单件", "单项多件", "多项多件")


@dataclass(frozen=True)
class BatchPreview:
    client: str
    shipping_method: str
    order_composition: str
    result_count: int
    page_url: str

    @property
    def confirmation_text(self) -> str:
        return (
            f"隆丰 / {self.shipping_method} / {self.order_composition} / "
            f"{self.result_count} 个生产项"
        )


@dataclass(frozen=True)
class ShippingBatchPlan:
    total_count: int
    cbt_count: int
    non_cbt_count: int
    client: str = "隆丰"

    @classmethod
    def from_counts(
        cls, total_count: int, cbt_count: int, client: str = "隆丰"
    ):
        if total_count < 0 or cbt_count < 0 or cbt_count > total_count:
            raise ValueError("CBT 数量不能大于全部已接单数量。")
        return cls(
            total_count=total_count,
            cbt_count=cbt_count,
            non_cbt_count=total_count - cbt_count,
            client=client,
        )

    @property
    def confirmation_text(self) -> str:
        return (
            f"{self.client}已接单共 {self.total_count} 个生产项："
            f"CBT {self.cbt_count} 个，非 CBT {self.non_cbt_count} 个"
        )


def find_longfeng_page(browser, platform_name: str = "隆丰"):
    platform = get_erp_platform(platform_name)
    return open_authenticated_page(
        browser,
        platform.production_items_url,
        ".search-container",
    )


def production_frame(page):
    if page.locator(".search-container").count():
        return page
    frames = [
        frame
        for frame in page.frames
        if "/fnsz-sale/produceManage/produceItemsManage" in frame.url
        and frame.parent_frame is not None
    ]
    if not frames:
        raise RuntimeError("没有找到隆丰生产项内容区域，请刷新页面后重试。")
    for frame in reversed(frames):
        if frame.locator(".title").count():
            return frame
    return frames[-1]


def select_batch_filters(
    page, shipping_method: str, order_composition: str
) -> None:
    if order_composition not in ORDER_COMPOSITIONS:
        raise ValueError(f"不支持的订单组成：{order_composition}")
    _select_received(page)
    frame = production_frame(page)
    _select_filter(frame, "物流分拣", shipping_method)
    _select_filter(frame, "订单组成", order_composition)
    _run_search(frame)


def preview_filtered_batch(
    page, shipping_method: str, order_composition: str
) -> BatchPreview:
    select_batch_filters(page, shipping_method, order_composition)
    frame = production_frame(page)
    count = _filtered_result_count(frame)
    return BatchPreview(
        client="隆丰",
        shipping_method=shipping_method,
        order_composition=order_composition,
        result_count=count,
        page_url=page.url,
    )


def preview_shipping_split(
    page, platform_name: str = "隆丰"
) -> ShippingBatchPlan:
    """Preview the two irreversible batches without creating either batch."""
    _select_received(page)
    frame = production_frame(page)
    _select_filter(frame, "物流分拣", "全部")
    _run_search(frame)
    total_count = _filtered_result_count(frame)

    _select_filter(frame, "物流分拣", "CBT")
    _run_search(frame)
    cbt_count = _filtered_result_count(frame)
    return ShippingBatchPlan.from_counts(
        total_count, cbt_count, client=platform_name
    )


def _select_received(frame) -> None:
    titles = frame.locator(".menu-item-title")
    matches = [
        titles.nth(index)
        for index in range(titles.count())
        if titles.nth(index).inner_text().strip().startswith("已接单")
    ]
    if len(matches) != 1:
        raise RuntimeError("无法唯一定位“已接单”区域。")
    title = matches[0]
    if "active" not in (title.get_attribute("class") or ""):
        title.click()
        frame.wait_for_timeout(300)


def _select_filter(frame, title: str, value: str) -> None:
    title_nodes = frame.locator(".title")
    matches = [
        title_nodes.nth(index)
        for index in range(title_nodes.count())
        if title_nodes.nth(index).inner_text().replace("\n", "").strip("： ")
        == title
    ]
    if len(matches) != 1:
        raise RuntimeError(f"无法唯一定位“{title}”筛选。")
    container = matches[0].locator("xpath=..")
    choices = container.get_by_text(value, exact=True)
    if choices.count() != 1:
        raise RuntimeError(f"“{title}”中没有唯一的“{value}”选项。")
    choices.click()


def _run_search(frame) -> None:
    buttons = frame.get_by_text("搜 索", exact=True)
    if buttons.count() != 1:
        raise RuntimeError("无法唯一定位搜索按钮。")
    buttons.click()
    frame.wait_for_timeout(500)


def _filtered_result_count(frame) -> int:
    candidates = frame.locator(
        ".ant-pagination-total-text, .el-pagination__total, "
        "[class*='pagination']"
    )
    texts = candidates.all_inner_texts()
    for text in texts:
        match = re.search(r"(?:共|总计)\s*(\d+)\s*(?:条|项)?", text)
        if match:
            return int(match.group(1))
    rows = frame.locator("tbody tr")
    count = rows.count()
    if count:
        return count
    raise RuntimeError("无法读取当前筛选结果数量，已停止以防误生成批次。")
