"""Plan Haloo test batches from already-produced items."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..api.erp import (
    generate_supplement_batch,
    list_batch_rules,
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
    item_quantities: tuple[tuple[str, int], ...] = ()
    order_ids: tuple[str, ...] = ()


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
    grouped: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    order_rows: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        order_rows[str(row["order_id"])].append(row)

    for order in order_rows.values():
        composition = int(order[0]["order_composition"])
        logistics = str(order[0].get("logistics_sorting_code") or "")
        if any(int(row["order_composition"]) != composition or
               str(row.get("logistics_sorting_code") or "") != logistics
               for row in order):
            raise RuntimeError("同订单的物流或订单组成不一致，不能拆单或猜测分组。")
        if composition == 1 and len(order) != 1:
            raise RuntimeError("单项单件订单包含多个生产项，不能按单项拆开。")
        faces = {classify_production_face(image_details[str(row["id"])]) for row in order}
        face = next(iter(faces)) if len(faces) == 1 else "混合面别"
        if composition == 1:
            row = order[0]
            key = (logistics, "单项单件", face,
                   str(row.get("style_id") or ""), str(row.get("style_name") or ""),
                   str(row.get("color") or ""), size_band(str(row.get("size") or "")))
        else:
            key = (logistics,
                   BASE_COMPOSITIONS.get(str(composition), f"订单组成:{composition}"),
                   face, "", "", "", "")
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
            tuple(
                (str(row["id"]), int(row.get("qty") or 0))
                for row in members
            ),
            tuple(dict.fromkeys(str(row["order_id"]) for row in members)),
        )
        for key, members in sorted(grouped.items())
        if members
    )


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
        if not row.get("logistics_sorting_code"):
            raise RuntimeError("生产项缺少物流编码，不能按物流生成测试计划。")
        if int(row.get("qty") or 0) <= 0:
            raise RuntimeError("生产项缺少可核对的正数数量。")


def completed_batch_request(
    group: CompletedBatchGroup,
    batch_rule_id: int | str,
) -> dict:
    """Build the supplement request required by already-batched completed items."""
    if not group.item_quantities or any(qty <= 0 for _item_id, qty in group.item_quantities):
        raise ValueError("已完成生产项缺少可核对的补单数量。")
    return {"item_list": [{"item_id": item_id, "qty": qty}
                          for item_id, qty in group.item_quantities],
            "batch_rule_id": batch_rule_id}


def _whole_order(page, order_id: str) -> list[dict]:
    payload = production_item_payload(status=(), page_size=200)
    payload["order_id"] = order_id
    result = list_production_items(page, payload)
    rows = list(result.get("list") or [])
    if not rows or len(rows) != int(result.get("total") or 0):
        raise RuntimeError(f"订单 {order_id} 未完整返回，不能生成批次。")
    if any(str(row.get("order_id")) != order_id for row in rows):
        raise RuntimeError(f"订单 {order_id} 查询结果混入其他订单。")
    return rows

def _supplement_codes(row: dict) -> set[str]:
    return {str(detail["production_batch_code"])
            for detail in row.get("supplement_detail_list") or []
            if detail.get("production_batch_code")}


def verify_completed_group(page, expected: CompletedBatchGroup) -> list[dict]:
    if not expected.order_ids or not expected.item_quantities:
        raise RuntimeError("分组缺少订单或数量信息，请重新读取分类。")
    rows = [row for order_id in expected.order_ids for row in _whole_order(page, order_id)]
    if len({str(row["id"]) for row in rows}) != len(rows):
        raise RuntimeError("订单查询返回重复生产项。")
    details = {str(row["id"]): production_item_images(page, str(row["id"])) for row in rows}
    actual = plan_completed_haloo_batches(rows, details)
    fields = ("logistics_code", "order_composition", "face", "style_id", "style_name",
              "color", "size_group")
    if len(actual) != 1 or any(getattr(actual[0], field) != getattr(expected, field)
                               for field in fields) or any(
        set(getattr(actual[0], field)) != set(getattr(expected, field))
        for field in ("item_ids", "item_quantities", "order_ids", "source_batch_codes")
    ):
        raise RuntimeError("订单状态、整单范围、底款或数量已变化，请重新读取分类后再生成。")
    if any(row.get("supplement_detail_list") for row in rows):
        raise RuntimeError("该分组已有补单批次，禁止重复生成；请重新读取分类。")
    return rows


def generate_completed_groups(page, groups: tuple[CompletedBatchGroup, ...],
                              rule_id: int | str, progress=None) -> tuple[str, ...]:
    """One write per selected group; never retry an uncertain submission."""
    if not groups or len(groups) != len(set(groups)):
        raise ValueError("请选择互不重复的底款分组。")
    if len({item_id for group in groups for item_id in group.item_ids}) != sum(
            len(group.item_ids) for group in groups):
        raise ValueError("所选分组包含重复生产项。")
    if str(rule_id) not in {str(rule.id) for rule in list_batch_rules(page)}:
        raise RuntimeError("批次规则已变化，请重新读取。")
    created = []
    for index, group in enumerate(groups, 1):
        if progress:
            progress(f"[{index}/{len(groups)}] 核验 {group.style_name or group.style_id or '整单混合底款'}")
        verify_completed_group(page, group)
        generate_supplement_batch(page, list(group.item_quantities), rule_id)
        codes = set.intersection(*(_supplement_codes(row) for order_id in group.order_ids
                                   for row in _whole_order(page, order_id)))
        if len(codes) != 1:
            raise RuntimeError(
                f"第 {index} 组已提交，但未能唯一确认新批次。禁止重试；请到平台核对生产项补单记录。"
            )
        created.append(codes.pop())
    return tuple(created)
