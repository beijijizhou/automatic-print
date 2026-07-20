from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable

from PIL import Image


SUPPORTED_EXTENSIONS = {
    ".png",
    ".tif",
    ".tiff",
    ".jpg",
    ".jpeg",
    ".jfif",
    ".webp",
    ".bmp",
}
ProgressCallback = Callable[[str, int, int, str], None]


@dataclass(frozen=True)
class LayoutSettings:
    media_width_mm: float = 600
    spacing_mm: float = 3
    margin_mm: float = 3
    dpi: int = 300
    fast_png: bool = True
    worker_threads: int = 8


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
        path for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def discovered_extensions(folder: Path) -> list[str]:
    return sorted(
        {path.suffix.lower() or "(no extension)" for path in folder.rglob("*") if path.is_file()}
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


def _prepare_image(item: tuple[Path, Placement], dpi: int) -> tuple[Image.Image, Placement]:
    path, placement = item
    image = _normalized_image(path, dpi, (placement.width_px, placement.height_px))
    return image, placement


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
        raise ValueError("外边距过大，画布没有可打印区域。")

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
            raise ValueError(f"图片 {path.name} 的宽度超过了材料可打印宽度。")
        if x > margin and x + width > canvas_width - margin:
            x = margin
            y += row_height + spacing
            row_height = 0
        placement = Placement(path.name, x, y, width, height)
        planned.append((path, placement))
        x += width + spacing
        row_height = max(row_height, height)
        if progress:
            progress("读取图片尺寸", index, total, path.name)
    reading_seconds = perf_counter() - reading_started

    if not planned:
        raise ValueError("没有可供排版的图片。")

    canvas_height = y + row_height + margin
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

    # Decode and resize source images in parallel. Results are consumed in layout
    # order, so output remains deterministic.
    combining_started = perf_counter()
    workers = max(1, min(settings.worker_threads, total))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        prepared = executor.map(
            lambda item: _prepare_image(item, settings.dpi), planned
        )
        for index, (image, placement) in enumerate(prepared, start=1):
            # Placements never overlap, so a direct RGBA copy is equivalent to
            # alpha compositing here and avoids millions of needless blends.
            canvas.paste(image, (placement.x_px, placement.y_px))
            image.close()
            if progress:
                progress("合成图片", index, total, placement.source)
    combining_seconds = perf_counter() - combining_started

    filename = "print.png"
    if progress:
        progress("保存 PNG", 0, canvas_width * canvas_height, filename)
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
