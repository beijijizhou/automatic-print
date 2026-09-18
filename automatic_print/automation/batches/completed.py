"""Plan Haloo test batches from already-produced items without reopening them."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from ..api.erp import (
    list_production_items,
    production_item_images,
    production_item_payload,
)
from .classification import (
    BASE_COMPOSITIONS,
    classify_production_face,
    size_band,
)

COMPLETED_STATUS = 9


@dataclass(frozen=True)
class CompletedBatchGroup:
    logistics_code: str
    order_composition: str
    face: str
    item_ids: tuple[str, ...]
    style_id: str = ""
    style_name: str = ""
    color: str = ""
    size_group: str = ""
    source_batch_codes: tuple[str, ...] = ()


def load_completed_haloo_snapshot(
    page, *, page_size: int = 200, progress=None
) -> tuple[list[dict], dict[str, dict]]:
    """Read a bounded, newest-first completed snapshot plus exact face data."""
    if page_size < 1 or page_size > 200:
        raise ValueError("已生产测试快照每次只允许读取 1–200 项。")
    payload = production_item_payload(status=("9",), page_size=page_size)
    rows = list(list_production_items(page, payload).get("list") or [])
    details = {}
    for index, row in enumerate(rows, start=1):
        if progress:
            progress(f"[{index}/{len(rows)}] 正在读取实际生产图面别")
        details[str(row["id"])] = production_item_images(page, str(row["id"]))
    return rows, details


def plan_completed_haloo_batches(
    rows: list[dict], image_details: dict[str, dict]
) -> tuple[CompletedBatchGroup, ...]:
    """Group an immutable completed snapshot; never calls a write endpoint."""
    _validate_completed_snapshot(rows, image_details)
    singles = [row for row in rows if int(row["order_composition"]) == 1]
    dominant_style = _dominant_style(singles) if singles else ""
    grouped: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    order_rows: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        order_rows[str(row["order_id"])].append(row)

    for order in order_rows.values():
        composition = int(order[0]["order_composition"])
        logistics = str(order[0].get("logistics_sorting_code") or "")
        faces = {classify_production_face(image_details[str(row["id"])]) for row in order}
        face = next(iter(faces)) if len(faces) == 1 else "混合面别"
        if composition == 1:
            row = order[0]
            if str(row.get("style_id") or "") != dominant_style:
                continue
            color = str(row.get("color") or "")
            if color not in {"黑色", "白色"}:
                continue
            key = (
                logistics, "单项单件", face, dominant_style,
                str(row.get("style_name") or ""), color,
                size_band(str(row.get("size") or "")),
            )
        else:
            key = (
                logistics,
                BASE_COMPOSITIONS.get(str(composition), f"订单组成:{composition}"),
                face, "", "", "", "",
            )
        grouped[key].extend(order)
    return tuple(
        CompletedBatchGroup(
            *key[:3],
            tuple(str(row["id"]) for row in members),
            *key[3:],
            tuple(sorted({
                str(row.get("production_batch_code") or "")
                for row in members
                if row.get("production_batch_code")
            })),
        )
        for key, members in sorted(grouped.items())
        if members
    )


def _dominant_style(rows: list[dict]) -> str:
    counts = Counter(str(row.get("style_id") or "") for row in rows)
    counts.pop("", None)
    if not counts:
        raise RuntimeError("已生产单项单件中没有可核对的底款。")
    return min(counts, key=lambda value: (-counts[value], value))


def _validate_completed_snapshot(rows, image_details) -> None:
    if not rows:
        raise RuntimeError("没有已生产测试数据。")
    for row in rows:
        if int(row.get("status") or 0) != COMPLETED_STATUS:
            raise RuntimeError("快照包含非“已生产”生产项，禁止生成测试计划。")
        item_id = str(row.get("id") or "")
        if not item_id or item_id not in image_details:
            raise RuntimeError("生产项缺少实际生产图面别详情，禁止猜测。")
        if not row.get("order_id"):
            raise RuntimeError("生产项缺少订单身份，无法保证整单不拆。")


def completed_batch_request(
    group: CompletedBatchGroup,
    batch_rule_id: int | str,
    *,
    verified_non_reopening: bool = False,
) -> dict:
    """Build the observed selected-item request, gated against unsafe writes."""
    if not verified_non_reopening:
        raise RuntimeError(
            "Haloo 未提供预演参数，且尚未证明对“已生产”项目生成批次不会"
            "重开生产或改变队列；已保留计划但禁止提交。"
        )
    return {
        "production_order_item_ids": list(group.item_ids),
        "batch_creat_type": 2,
        "batch_rule_id": batch_rule_id,
    }
