"""Platform-specific grouping values for ERP supplement previews."""

from __future__ import annotations

from ..classification import (
    BASE_COMPOSITIONS,
    BACK_FACE,
    DOUBLE_FACE_DETAIL,
    FRONT_FACE,
    UNKNOWN_FACE_DETAIL,
    classify_production_face,
    size_band,
)


ALL_FACES = "不区分面别"
SINGLE_SIDE = "单面"


def grouping_values(platform_name: str, order: list[dict], image_details: dict[str, dict]):
    composition = int(order[0]["order_composition"])
    if any(int(row["order_composition"]) != composition for row in order):
        raise RuntimeError("同订单的订单组成不一致，不能拆单或猜测分组。")
    if composition == 1 and len(order) != 1:
        raise RuntimeError("单项单件订单包含多个生产项，不能按单项拆开。")

    logistics_values = {
        str(row.get("logistics_sorting_code") or "") for row in order
    }
    if platform_name != "隆丰" and len(logistics_values) != 1:
        raise RuntimeError("同订单的物流不一致，不能拆单或猜测分组。")
    logistics = "" if platform_name == "隆丰" else next(iter(logistics_values))
    composition_name = BASE_COMPOSITIONS.get(
        str(composition), f"订单组成:{composition}"
    )
    faces = {
        classify_production_face(image_details[str(row["id"])]) for row in order
    }

    if platform_name in {"隆丰", "Haloo"}:
        return _confirmed_values(
            platform_name, order, logistics, composition, composition_name, faces
        )
    face = next(iter(faces)) if len(faces) == 1 else "混合面别"
    if composition != 1:
        return logistics, composition_name, face, "", "", "", ""
    row = order[0]
    return (
        logistics,
        composition_name,
        face,
        str(row.get("style_id") or ""),
        str(row.get("style_name") or ""),
        str(row.get("color") or ""),
        size_band(str(row.get("size") or "")),
    )


def _confirmed_values(platform_name, order, logistics, composition, composition_name, faces):
    if composition != 1:
        return logistics, composition_name, ALL_FACES, "", "", "", ""
    row = order[0]
    if faces == {UNKNOWN_FACE_DETAIL}:
        raise RuntimeError("单项单件缺少可识别的 A面/B面 生产图，不能猜测单双面。")
    if not faces <= {FRONT_FACE, BACK_FACE, DOUBLE_FACE_DETAIL}:
        raise RuntimeError("单项单件生产图面别冲突，不能猜测单双面。")
    face = DOUBLE_FACE_DETAIL if faces == {DOUBLE_FACE_DETAIL} else SINGLE_SIDE
    if face == DOUBLE_FACE_DETAIL:
        return logistics, composition_name, face, "", "", "", ""
    color = str(row.get("color") or "")
    if not color:
        raise RuntimeError("单项单件缺少颜色，不能猜测分组。")
    if platform_name == "隆丰":
        return logistics, composition_name, face, "", "", color, ""
    color_group = color if color in {"黑色", "白色"} else "混色"
    band = size_band(str(row.get("size") or "")) if color_group in {"黑色", "白色"} else ""
    return logistics, composition_name, face, "", "", color_group, band
