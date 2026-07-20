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
    max_length_mm: float = 2000


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


def _normalized_image(path: Path, target_dpi: int) -> Image.Image:
    image = Image.open(path)
    image.load()
    source_dpi = image.info.get("dpi", (target_dpi, target_dpi))
    x_dpi = float(source_dpi[0] or target_dpi)
    y_dpi = float(source_dpi[1] or target_dpi)
    width = max(1, round(image.width * target_dpi / x_dpi))
    height = max(1, round(image.height * target_dpi / y_dpi))
    image = image.convert("RGBA")
    if image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    return image


def generate_layouts(
    image_paths: Iterable[Path], output_dir: Path, settings: LayoutSettings
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    canvas_width = mm_to_px(settings.media_width_mm, settings.dpi)
    max_height = mm_to_px(settings.max_length_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    usable_width = canvas_width - (2 * margin)
    if usable_width <= 0 or max_height <= 2 * margin:
        raise ValueError("Margins leave no printable canvas area.")

    pages: list[dict] = []
    canvas = Image.new("RGBA", (canvas_width, max_height), (0, 0, 0, 0))
    placements: list[Placement] = []
    x = y = margin
    row_height = 0

    def save_page() -> None:
        nonlocal canvas, placements, x, y, row_height
        if not placements:
            return
        used_height = min(max_height, y + row_height + margin)
        page_number = len(pages) + 1
        filename = f"print_{page_number:03d}.png"
        canvas.crop((0, 0, canvas_width, used_height)).save(
            output_dir / filename, dpi=(settings.dpi, settings.dpi)
        )
        pages.append({
            "filename": filename,
            "width_px": canvas_width,
            "height_px": used_height,
            "placements": [asdict(item) for item in placements],
        })
        canvas = Image.new("RGBA", (canvas_width, max_height), (0, 0, 0, 0))
        placements = []
        x = y = margin
        row_height = 0

    for path in image_paths:
        image = _normalized_image(path, settings.dpi)
        if image.width > usable_width:
            raise ValueError(f"{path.name} is wider than the printable media width.")
        if x > margin and x + image.width > canvas_width - margin:
            x = margin
            y += row_height + spacing
            row_height = 0
        if y + image.height + margin > max_height:
            save_page()
        if image.height + 2 * margin > max_height:
            raise ValueError(f"{path.name} is taller than the maximum output length.")
        canvas.alpha_composite(image, (x, y))
        placements.append(Placement(path.name, x, y, image.width, image.height))
        x += image.width + spacing
        row_height = max(row_height, image.height)

    save_page()
    return pages
