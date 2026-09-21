"""Fixed-canvas UV planning, isolated from DTF roll layout."""

from dataclasses import dataclass
from math import ceil
from pathlib import Path

from ..intake.discovery.discovery import discover_images
from ..intake.metadata.images import print_dimensions


CANVAS_WIDTH_MM = 2500
CANVAS_HEIGHT_MM = 1300


@dataclass(frozen=True)
class UvSheetSpec:
    key: str
    label: str
    width_mm: float
    length_mm: float
    source_sizes_mm: tuple[tuple[float, float], ...]
    landscape: bool = False

    @property
    def item_width_mm(self):
        return max(self.width_mm, self.length_mm) if self.landscape else self.width_mm

    @property
    def item_height_mm(self):
        return min(self.width_mm, self.length_mm) if self.landscape else self.length_mm


UV_MATERIALS = (
    UvSheetSpec("1040", "1040", 102, 402, ((100, 400), (102, 402))),
    UvSheetSpec("2030_iron", "2030铁", 202, 302, ((200, 300), (202, 302)), True),
    UvSheetSpec("2030_aluminum", "2030铝", 202, 302, ((200, 300), (202, 302)), True),
    UvSheetSpec("2030_wood", "2030木板", 202, 302, ((200, 300), (202, 302)), True),
    UvSheetSpec("round_iron", "圆铁", 201, 201, ((200, 200), (201, 201))),
    UvSheetSpec("raw_aluminum", "原铝", 199, 199, ((200, 200), (199, 199))),
    UvSheetSpec("3040", "3040", 302, 402, ((300, 400), (302, 402))),
    UvSheetSpec("clock_2525", "挂钟2525", 252, 252, ((250, 250), (252, 252))),
    UvSheetSpec("clock_3030", "挂钟3030", 302, 302, ((300, 300), (302, 302))),
    UvSheetSpec("license_plate", "车牌", 308, 157, ((300, 150), (308, 157))),
    UvSheetSpec("acrylic", "亚克力", 150, 220, ((150, 220),)),
)
UV_MATERIAL_BY_KEY = {item.key: item for item in UV_MATERIALS}
UV_2030_LANDSCAPE = UV_MATERIAL_BY_KEY["2030_iron"]


@dataclass(frozen=True)
class UvPlacement:
    source: Path
    x_px: int
    y_px: int
    width_px: int
    height_px: int
    rotation_degrees: int
    row: int
    column: int


@dataclass(frozen=True)
class UvSheetPlan:
    source_folder: Path
    spec: UvSheetSpec
    dpi: float
    canvas_width_px: int
    canvas_height_px: int
    columns: int
    rows: int
    capacity: int
    placements: tuple[UvPlacement, ...]


def plan_uv_sheet(folder, spec=UV_2030_LANDSCAPE, progress=None):
    spec = UV_MATERIAL_BY_KEY[spec] if isinstance(spec, str) else spec
    folder = Path(folder).resolve()
    paths = discover_images(folder)
    if not paths:
        raise ValueError(f"{folder} 没有可合成的图片。")
    measured = []
    for index, path in enumerate(paths, 1):
        dimensions = print_dimensions(path, 150)
        _validate_source(path, dimensions, spec)
        measured.append((path, dimensions))
        if progress:
            progress("检查UV源图", index, len(paths), path.name)
    dpi = measured[0][1].x_dpi
    mismatched = [path.name for path, value in measured if abs(value.x_dpi - dpi) > 0.1]
    if mismatched:
        raise ValueError(
            f"UV 批次包含不同 DPI；基准 {dpi:g}，不一致文件：{', '.join(mismatched[:5])}"
        )
    columns = int(CANVAS_WIDTH_MM // spec.item_width_mm)
    row_capacity = int(CANVAS_HEIGHT_MM // spec.item_height_mm)
    capacity = columns * row_capacity
    if len(paths) > capacity:
        raise ValueError(
            f"{spec.label} 单画布容量为 {capacity} 张，当前有 {len(paths)} 张；"
            "任务和源图保持不变，请选择修改规格或明确拆分方式。"
        )
    ppm = dpi / 25.4
    placements = []
    for index, (path, dimensions) in enumerate(measured):
        column, row = index % columns, index // columns
        right_mm = CANVAS_WIDTH_MM - column * spec.item_width_mm
        left_mm = right_mm - spec.item_width_mm
        bottom_mm = CANVAS_HEIGHT_MM - row * spec.item_height_mm
        top_mm = bottom_mm - spec.item_height_mm
        left, right = round(left_mm * ppm), round(right_mm * ppm)
        top, bottom = round(top_mm * ppm), round(bottom_mm * ppm)
        source_landscape = dimensions.width_mm > dimensions.height_mm
        target_landscape = spec.item_width_mm > spec.item_height_mm
        placements.append(UvPlacement(
            path, left, top, right-left, bottom-top,
            90 if source_landscape != target_landscape else 0,
            row, column,
        ))
    return UvSheetPlan(
        folder, spec, dpi,
        round(CANVAS_WIDTH_MM * ppm), round(CANVAS_HEIGHT_MM * ppm),
        columns, ceil(len(paths) / columns), capacity, tuple(placements),
    )


def _validate_source(path, dimensions, spec):
    if not dimensions.embedded_dpi:
        raise ValueError(f"{path.name} 没有可靠内嵌 DPI，不能确定 UV 生产尺寸。")
    if abs(dimensions.x_dpi - dimensions.y_dpi) > 0.1:
        raise ValueError(f"{path.name} 的横向和纵向 DPI 不一致，不能安全缩放。")
    actual = sorted((dimensions.width_mm, dimensions.height_mm))
    accepted = any(
        abs(actual[0] - min(width, height)) <= 1
        and abs(actual[1] - max(width, height)) <= 1
        for width, height in spec.source_sizes_mm
    )
    if not accepted:
        expected = " 或 ".join(f"{w:g}×{h:g}" for w, h in spec.source_sizes_mm)
        raise ValueError(
            f"{path.name} 原尺寸为 {dimensions.width_mm:.2f} × "
            f"{dimensions.height_mm:.2f} mm；{spec.label} 只接收约 {expected} mm 源图。"
        )
