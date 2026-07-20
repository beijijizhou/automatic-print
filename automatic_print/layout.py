from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image


SUPPORTED_EXTENSIONS = {".png", ".tif", ".tiff", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class LayoutSettings:
    media_width_mm: float = 600
    spacing_mm: float = 3
    margin_mm: float = 3
    dpi: int = 300


@dataclass(frozen=True)
class Placement:
    source: str
    x_px: int
    y_px: int
    width_px: int
    height_px: int


def mm_to_px(value: float, dpi: int) -> int:
    return max(0, round(value * dpi / 25.4))


def discover_images(folder: Path) -> list[Path]:
    return sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _target_size(path: Path, target_dpi: int) -> tuple[int, int]:
    with Image.open(path) as image:
        source_dpi = image.info.get("dpi", (target_dpi, target_dpi))
        x_dpi = float(source_dpi[0] or target_dpi)
        y_dpi = float(source_dpi[1] or target_dpi)
        return (
            max(1, round(image.width * target_dpi / x_dpi)),
            max(1, round(image.height * target_dpi / y_dpi)),
        )


def _normalized_image(
    path: Path, target_dpi: int, target_size: tuple[int, int]
) -> Image.Image:
    image = Image.open(path)
    image.load()
    image = image.convert("RGBA")
    if image.size != target_size:
        image = image.resize(target_size, Image.Resampling.LANCZOS)
    return image


def generate_layout(
    image_paths: Iterable[Path], output_dir: Path, settings: LayoutSettings
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    canvas_width = mm_to_px(settings.media_width_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    usable_width = canvas_width - (2 * margin)
    if usable_width <= 0:
        raise ValueError("Margins leave no printable canvas area.")

    paths = list(image_paths)
    planned: list[tuple[Path, Placement]] = []
    x = y = margin
    row_height = 0

    # First pass only reads metadata and calculates the exact required height.
    for path in paths:
        width, height = _target_size(path, settings.dpi)
        if width > usable_width:
            raise ValueError(f"{path.name} is wider than the printable media width.")
        if x > margin and x + width > canvas_width - margin:
            x = margin
            y += row_height + spacing
            row_height = 0
        placement = Placement(path.name, x, y, width, height)
        planned.append((path, placement))
        x += width + spacing
        row_height = max(row_height, height)

    if not planned:
        raise ValueError("No images were provided.")

    canvas_height = y + row_height + margin
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

    # Second pass decodes one source image at a time, keeping peak memory lower.
    for path, placement in planned:
        image = _normalized_image(
            path, settings.dpi, (placement.width_px, placement.height_px)
        )
        canvas.alpha_composite(image, (placement.x_px, placement.y_px))
        image.close()

    filename = "print.png"
    canvas.save(
        output_dir / filename,
        dpi=(settings.dpi, settings.dpi),
        compress_level=1,
    )
    canvas.close()
    return {
        "filename": filename,
        "width_px": canvas_width,
        "height_px": canvas_height,
        "placements": [asdict(item) for _, item in planned],
    }
