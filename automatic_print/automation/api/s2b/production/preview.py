"""Read-only S2B unbatched-order grouping preview."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ....batches.classification import size_band
from ....batches.supplements.strategies import GroupingStrategy, default_strategy
from .gateway import preview_items


@dataclass(frozen=True)
class S2BPreviewGroup:
    logistics: str
    composition: str
    face: str
    color: str
    size_group: str
    style: str
    production_ids: tuple[str, ...]
    order_codes: tuple[str, ...]
    item_count: int
    piece_count: int


def load_s2b_preview(strategy: GroupingStrategy | None = None, progress=None) -> dict:
    selected = strategy or default_strategy("S2B")
    _report(progress, "正在通过共享 S2B 服务读取全部待排产生产项…")
    payload = preview_items()
    rows = payload.get("records") or []
    groups = plan_s2b_preview(rows, selected)
    _report(progress, f"S2B 仅读取完成：{len(rows)} 项，模拟分为 {len(groups)} 组；未生成批次。")
    return {"source_total": int(payload.get("total") or len(rows)),
            "groups": groups, "strategy": selected}


def plan_s2b_preview(rows: list[dict], strategy: GroupingStrategy) -> tuple[S2BPreviewGroup, ...]:
    ids = [str(row.get("production_id") or "") for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise RuntimeError("S2B 待排产快照存在空或重复生产项 ID，不能可靠预览。")
    by_order: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        order = str(row.get("order_code") or "").strip()
        if not order:
            raise RuntimeError("S2B 待排产生产项缺少订单号，不能保证整单不拆。")
        if int(row.get("quantity") or 0) <= 0:
            raise RuntimeError(f"S2B 订单 {order} 的数量无效，不能可靠预览。")
        by_order[order].append(row)

    for order, order_rows in by_order.items():
        expected = {int(row.get("order_total_count") or 0) for row in order_rows}
        pieces = sum(int(row["quantity"]) for row in order_rows)
        if len(expected) != 1 or next(iter(expected)) != pieces:
            raise RuntimeError(
                f"S2B 订单 {order} 返回不完整：接口订单总件数与当前生产项数量不一致。"
            )

    grouped: dict[tuple[str, ...], list[list[dict]]] = defaultdict(list)
    for order_rows in by_order.values():
        grouped[_group_key(order_rows, strategy)].append(order_rows)
    result = []
    for key, orders in sorted(grouped.items()):
        members = [row for order_rows in orders for row in order_rows]
        result.append(S2BPreviewGroup(
            *key, tuple(str(row["production_id"]) for row in members),
            tuple(str(order_rows[0]["order_code"]) for order_rows in orders),
            len(members), sum(int(row["quantity"]) for row in members),
        ))
    return tuple(result)


def _group_key(order: list[dict], strategy: GroupingStrategy) -> tuple[str, ...]:
    item_count = len({str(row.get("item_id") or row["production_id"]) for row in order})
    pieces = sum(int(row["quantity"]) for row in order)
    composition = ("单项单件" if item_count == 1 and pieces == 1 else
                   "单项多件" if item_count == 1 else "多项多件")
    logistics = _single_value(order, "logistics", "物流") if strategy.by_logistics else ""
    composition_key = composition if strategy.by_composition else "不分订单组成"
    if composition != "单项单件":
        return logistics, composition_key, "不区分面别", "", "", ""
    row = order[0]
    actual_face = "双面" if _is_double_sided(row) else "单面"
    face = actual_face if strategy.by_face else "不区分面别"
    if actual_face == "双面":
        return logistics, composition_key, face, "", "", ""
    color = str(row.get("color") or "").strip()
    if (strategy.by_color or strategy.by_size) and not color:
        raise RuntimeError(f"S2B 订单 {row['order_code']} 缺少颜色，不能按所选规则预览。")
    color_group = color if color in {"黑色", "白色"} else "混色"
    selected_size = (size_band(str(row.get("size") or ""))
                     if strategy.by_size and color in {"黑色", "白色"} else "")
    return (logistics, composition_key, face,
            color_group if strategy.by_color else "", selected_size,
            str(row.get("style_name") or "").strip() if strategy.by_style else "")


def _single_value(rows: list[dict], field: str, label: str) -> str:
    values = {str(row.get(field) or "").strip() for row in rows}
    if len(values) != 1 or not next(iter(values)):
        order = str(rows[0].get("order_code") or "")
        raise RuntimeError(f"S2B 订单 {order} 的{label}不一致或缺失，不能拆单或猜测。")
    return next(iter(values))


def _is_double_sided(row: dict) -> bool:
    text = " ".join((str(row.get("product_name") or ""),
                     str(row.get("style_name") or "")))
    return "双面" in text


def _report(progress, message: str) -> None:
    if progress:
        progress(message)
