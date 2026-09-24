"""Plan Hummingbird ERP batches from already-produced items."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ...api.erp import (
    generate_supplement_batch,
    list_batch_rules,
    production_item_images,
)
from ...api.erp.items import list_order_items
from .source import COMPLETED_STATUS, SUPPLEMENT_SOURCES, special_strategy_issue
from .grouping.strategy import GroupingStrategy, default_strategy, grouping_values


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
    source_status: int = COMPLETED_STATUS
    platform_name: str = ""
    strategy: GroupingStrategy | None = None


def plan_completed_erp_batches(
    rows: list[dict], image_details: dict[str, dict], *,
    source_status: int = COMPLETED_STATUS,
    platform_name: str = "",
    strategy: GroupingStrategy | None = None,
) -> tuple[CompletedBatchGroup, ...]:
    """Apply one supplement grouping strategy to either order source."""
    selected_strategy = strategy or default_strategy(platform_name)
    _validate_completed_snapshot(
        rows, image_details, source_status, selected_strategy
    )
    grouped: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    order_rows: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        order_rows[str(row["order_id"])].append(row)

    for order in order_rows.values():
        key = grouping_values(
            platform_name, order, image_details, selected_strategy
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
            tuple(
                (str(row["id"]), int(row.get("qty") or 0))
                for row in members
            ),
            tuple(dict.fromkeys(str(row["order_id"]) for row in members)),
            source_status,
            platform_name,
            selected_strategy,
        )
        for key, members in sorted(grouped.items())
        if members
    )


def _validate_completed_snapshot(rows, image_details, source_status: int,
                                 strategy: GroupingStrategy) -> None:
    if not rows:
        raise RuntimeError("所选订单入口没有可测试的生产项。")
    if source_status not in SUPPLEMENT_SOURCES:
        raise ValueError("补单订单入口必须是生产中或已完成。")
    if len({str(row.get('id') or '') for row in rows}) != len(rows):
        raise RuntimeError("订单入口快照包含重复生产项，禁止生成测试计划。")
    for row in rows:
        if int(row.get("status") or 0) != source_status:
            raise RuntimeError("快照混入其他订单状态，禁止生成测试计划。")
        item_id = str(row.get("id") or "")
        if not item_id or item_id not in image_details:
            raise RuntimeError("生产项缺少实际生产图面别详情，禁止猜测。")
        if not row.get("order_id"):
            raise RuntimeError("生产项缺少订单身份，无法保证整单不拆。")
        if strategy.by_logistics and not row.get("logistics_sorting_code"):
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
    return list_order_items(page, order_id)

def _supplement_codes(row: dict) -> set[str]:
    return {str(detail["production_batch_code"])
            for detail in row.get("supplement_detail_list") or []
            if detail.get("production_batch_code")}


def _confirmed_group_codes(page, group: CompletedBatchGroup) -> tuple[str, ...]:
    """Confirm every order once while allowing the ERP to split one request."""
    codes = set()
    for order_id in group.order_ids:
        row_codes = [
            _supplement_codes(row) for row in _whole_order(page, order_id)
        ]
        if not row_codes or any(len(item_codes) != 1 for item_codes in row_codes):
            raise RuntimeError("订单中存在未确认或多重归属的生产项")
        order_codes = set().union(*row_codes)
        if len(order_codes) != 1:
            raise RuntimeError("订单未能唯一对应一个新补单批次")
        codes.update(order_codes)
    if not codes:
        raise RuntimeError("未读取到新补单批次")
    return tuple(sorted(codes))


def verify_completed_group(page, expected: CompletedBatchGroup) -> list[dict]:
    if not expected.order_ids or not expected.item_quantities:
        raise RuntimeError("分组缺少订单或数量信息，请重新读取分类。")
    rows = [row for order_id in expected.order_ids for row in _whole_order(page, order_id)]
    if len({str(row["id"]) for row in rows}) != len(rows):
        raise RuntimeError("订单查询返回重复生产项。")
    if issue := special_strategy_issue(rows, expected.platform_name):
        raise RuntimeError(issue)
    details = {str(row["id"]): production_item_images(page, str(row["id"])) for row in rows}
    actual = plan_completed_erp_batches(rows, details,
                                        source_status=expected.source_status,
                                        platform_name=expected.platform_name,
                                        strategy=expected.strategy)
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
        raise ValueError("请选择互不重复的批次分组。")
    if len({item_id for group in groups for item_id in group.item_ids}) != sum(
            len(group.item_ids) for group in groups):
        raise ValueError("所选分组包含重复生产项。")
    if len({group.source_status for group in groups}) != 1:
        raise ValueError("所选分组混入不同订单入口，不能一起提交。")
    if len({(group.platform_name, group.strategy) for group in groups}) != 1:
        raise ValueError("所选分组混入不同平台或分组组合，不能一起提交。")
    if str(rule_id) not in {str(rule.id) for rule in list_batch_rules(page)}:
        raise RuntimeError("批次规则已变化，请重新读取。")
    created = []
    for index, group in enumerate(groups, 1):
        if progress:
            progress(f"[{index}/{len(groups)}] 核验 {group.style_name or group.style_id or '整单混合底款'}")
        verify_completed_group(page, group)
        generate_supplement_batch(page, list(group.item_quantities), rule_id)
        try:
            codes = _confirmed_group_codes(page, group)
        except RuntimeError:
            raise RuntimeError(
                f"第 {index} 组已提交，但未能逐单确认新批次。禁止重试；请到平台核对生产项补单记录。"
            ) from None
        created.extend(code for code in codes if code not in created)
    return tuple(created)
