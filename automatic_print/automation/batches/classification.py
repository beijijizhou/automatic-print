from __future__ import annotations


BASE_COMPOSITIONS = {
    "1": "单项单件",
    "2": "单项多件",
    "3": "多项多件",
}
SINGLE_FACE = "单项单件（单面）"
DOUBLE_FACE = "单项单件（双面）"
UNKNOWN_FACE = "单项单件（单双面未知）"
FRONT_FACE = "正面"
BACK_FACE = "反面"
DOUBLE_FACE_DETAIL = "双面"
UNKNOWN_FACE_DETAIL = "面别未知"


def classify_production_face(detail: dict) -> str:
    names = {
        str(image.get("name") or "").strip()
        for image in detail.get("production_images") or []
    }
    names.discard("")
    if names == {"A面"}:
        return FRONT_FACE
    if names == {"B面"}:
        return BACK_FACE
    if names == {"A面", "B面"}:
        return DOUBLE_FACE_DETAIL
    return UNKNOWN_FACE_DETAIL


def size_band(size: str) -> str:
    normalized = str(size).strip().upper().replace("XXL", "2XL")
    if normalized in {"S", "M", "L", "XL"}:
        return "S-XL"
    if normalized in {"2XL", "3XL", "4XL", "5XL"}:
        return "2XL-5XL"
    return f"其他尺码:{normalized or '未知'}"


def detailed_compositions(compositions) -> tuple[str, ...]:
    result = []
    for composition in compositions:
        if composition == "单项单件":
            result.extend((SINGLE_FACE, DOUBLE_FACE))
        else:
            result.append(composition)
    return tuple(result)


def classify_order_composition(row: dict) -> str:
    base = BASE_COMPOSITIONS.get(
        str(row.get("order_composition") or ""),
        str(row.get("order_composition") or "未知"),
    )
    if base != "单项单件":
        return base
    view_count = str(row.get("view_count") or "")
    if view_count == "1":
        return SINGLE_FACE
    if view_count == "2":
        return DOUBLE_FACE
    return UNKNOWN_FACE


def composition_filter(composition: str) -> tuple[str, int | None]:
    filters = {
        SINGLE_FACE: ("1", 1),
        DOUBLE_FACE: ("1", 2),
        "单项多件": ("2", None),
        "多项多件": ("3", None),
    }
    if composition not in filters:
        raise ValueError(f"不支持的订单组成：{composition}")
    return filters[composition]
