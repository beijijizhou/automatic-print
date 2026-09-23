"""Customer-visible grouping strategies for ERP supplement previews."""

from __future__ import annotations

from dataclasses import dataclass

from ..classification import (
    BACK_FACE,
    BASE_COMPOSITIONS,
    DOUBLE_FACE_DETAIL,
    FRONT_FACE,
    UNKNOWN_FACE_DETAIL,
    classify_production_face,
    size_band,
)


ALL_FACES = "不区分面别"
SINGLE_SIDE = "单面"


@dataclass(frozen=True)
class GroupingStrategy:
    by_logistics: bool
    by_face: bool
    by_color: bool
    by_size: bool
    by_style: bool
    by_composition: bool = True

    def enabled_labels(self) -> tuple[str, ...]:
        labels = (
            (self.by_composition, "订单组成"),
            (self.by_logistics, "物流"),
            (self.by_face, "单双面"),
            (self.by_color, "颜色"),
            (self.by_size, "尺码档"),
            (self.by_style, "底款"),
        )
        return tuple(label for enabled, label in labels if enabled)


def default_strategy(platform_name: str) -> GroupingStrategy:
    if platform_name == "隆丰":
        return GroupingStrategy(False, True, True, False, False)
    if platform_name in {"Haloo", "S2B"}:
        return GroupingStrategy(True, True, True, True, False)
    return GroupingStrategy(True, True, True, True, True)


def grouping_values(
    platform_name: str,
    order: list[dict],
    image_details: dict[str, dict],
    strategy: GroupingStrategy | None = None,
):
    selected = strategy or default_strategy(platform_name)
    composition = int(order[0]["order_composition"])
    if any(int(row["order_composition"]) != composition for row in order):
        raise RuntimeError("同订单的订单组成不一致，不能拆单或猜测分组。")
    if composition == 1 and len(order) != 1:
        raise RuntimeError("单项单件订单包含多个生产项，不能按单项拆开。")

    logistics_values = {
        str(row.get("logistics_sorting_code") or "") for row in order
    }
    if selected.by_logistics and len(logistics_values) != 1:
        raise RuntimeError("同订单的物流不一致，不能拆单或猜测分组。")
    logistics = next(iter(logistics_values)) if selected.by_logistics else ""
    composition_name = (
        BASE_COMPOSITIONS.get(str(composition), f"订单组成:{composition}")
        if selected.by_composition else "不分订单组成"
    )
    faces = {
        classify_production_face(image_details[str(row["id"])]) for row in order
    }

    if platform_name in {"隆丰", "Haloo", "S2B"}:
        return _confirmed_values(
            platform_name, order, logistics, composition, composition_name,
            faces, selected,
        )
    return _generic_values(
        order, logistics, composition, composition_name, faces, selected
    )


def _confirmed_values(
    platform_name, order, logistics, composition, composition_name, faces, strategy,
):
    if composition != 1:
        return logistics, composition_name, ALL_FACES, "", "", "", ""
    row = order[0]
    _validate_single_faces(faces)
    actual_face = DOUBLE_FACE_DETAIL if faces == {DOUBLE_FACE_DETAIL} else SINGLE_SIDE
    face = actual_face if strategy.by_face else ALL_FACES
    if actual_face == DOUBLE_FACE_DETAIL:
        return logistics, composition_name, face, "", "", "", ""
    color = str(row.get("color") or "")
    if (strategy.by_color or strategy.by_size) and not color:
        raise RuntimeError("单项单件缺少颜色，不能按所选规则分组。")
    color_group = _color_group(platform_name, color) if strategy.by_color else ""
    band = ""
    if strategy.by_size and (
        platform_name not in {"Haloo", "S2B"} or color in {"黑色", "白色"}
    ):
        band = size_band(str(row.get("size") or ""))
    style_id, style_name = _style_values(row, strategy.by_style)
    return logistics, composition_name, face, style_id, style_name, color_group, band


def _generic_values(order, logistics, composition, composition_name, faces, strategy):
    face = (
        next(iter(faces)) if len(faces) == 1 else "混合面别"
    ) if strategy.by_face else ALL_FACES
    if composition != 1:
        return logistics, composition_name, face, "", "", "", ""
    row = order[0]
    style_id, style_name = _style_values(row, strategy.by_style)
    return (
        logistics, composition_name, face, style_id, style_name,
        str(row.get("color") or "") if strategy.by_color else "",
        size_band(str(row.get("size") or "")) if strategy.by_size else "",
    )


def _validate_single_faces(faces) -> None:
    if faces == {UNKNOWN_FACE_DETAIL}:
        raise RuntimeError("单项单件缺少可识别的 A面/B面 生产图，不能猜测单双面。")
    if not faces <= {FRONT_FACE, BACK_FACE, DOUBLE_FACE_DETAIL}:
        raise RuntimeError("单项单件生产图面别冲突，不能猜测单双面。")


def _color_group(platform_name: str, color: str) -> str:
    if platform_name in {"Haloo", "S2B"} and color not in {"黑色", "白色"}:
        return "混色"
    return color


def _style_values(row: dict, enabled: bool) -> tuple[str, str]:
    if not enabled:
        return "", ""
    return str(row.get("style_id") or ""), str(row.get("style_name") or "")
