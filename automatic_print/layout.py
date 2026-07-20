from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable

from PIL import Image


SUPPORTED_EXTENSIONS = {".png", ".tif", ".tiff", ".jpg", ".jpeg", ".webp"}
ProgressCallback = Callable[[str, int, int, str], None]


@dataclass(frozen=True)
class LayoutSettings:
    media_width_mm: float = 600
    spacing_mm: float = 3
    margin_mm: float = 3
    dpi: int = 300
    fast_png: bool = True


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
    image_paths: Iterable[Path],
    output_dir: Path,
    settings: LayoutSettings,
    progress: ProgressCallback | None = None,
) -> dict:
    total_started = perf_counter()
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
    reading_started = perf_counter()
    total = len(paths)
    for index, path in enumerate(paths, start=1):
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
        if progress:
            progress("Reading image sizes", index, total, path.name)
    reading_seconds = perf_counter() - reading_started

    if not planned:
        raise ValueError("No images were provided.")

    canvas_height = y + row_height + margin
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

    # Second pass decodes one source image at a time, keeping peak memory lower.
    combining_started = perf_counter()
    for index, (path, placement) in enumerate(planned, start=1):
        image = _normalized_image(
            path, settings.dpi, (placement.width_px, placement.height_px)
        )
        canvas.alpha_composite(image, (placement.x_px, placement.y_px))
        image.close()
        if progress:
            progress("Combining images", index, total, path.name)
    combining_seconds = perf_counter() - combining_started

    filename = "print.png"
    if progress:
        progress("Saving PNG", 0, canvas_width * canvas_height, filename)
    saving_started = perf_counter()
    canvas.save(
        output_dir / filename,
        dpi=(settings.dpi, settings.dpi),
        compress_level=0 if settings.fast_png else 6,
    )
    saving_seconds = perf_counter() - saving_started
    canvas.close()
    return {
        "filename": filename,
        "width_px": canvas_width,
        "height_px": canvas_height,
        "placements": [asdict(item) for _, item in planned],
        "timings_seconds": {
            "reading": round(reading_seconds, 3),
            "combining": round(combining_seconds, 3),
            "saving_png": round(saving_seconds, 3),
            "total": round(perf_counter() - total_started, 3),
        },
    }
