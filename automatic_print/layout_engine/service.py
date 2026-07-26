from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Iterable

from .models import LayoutSettings, ProgressCallback
from .metrics import saving_metrics
from .pillow_renderer import build_pillow_canvas
from .planner import plan_layout
from .save_progress import monitor_save
from .vips_renderer import available, build_vips_canvas


def png_engine_name() -> str:
    return "大图节省内存模式" if available() else "标准兼容模式"


def generate_layout(
    image_paths: Iterable[Path],
    output_dir: Path,
    settings: LayoutSettings,
    progress: ProgressCallback | None = None,
) -> dict:
    total_started = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    reading_started = perf_counter()
    planned, labels, width, height, baseline_height = plan_layout(
        list(image_paths), settings, progress
    )
    reading_seconds = perf_counter() - reading_started

    combining_started = perf_counter()
    use_vips = settings.png_engine == "libvips" and available()
    builder = build_vips_canvas if use_vips else build_pillow_canvas
    canvas = builder(
        planned, labels, (width, height), settings, progress
    )
    combining_seconds = perf_counter() - combining_started

    filename = "print.png"
    saving_started = perf_counter()
    output_path = output_dir / filename
    with monitor_save(output_path, progress):
        if use_vips:
            canvas.pngsave(
                str(output_path),
                compression=settings.png_compression_level,
                interlace=False,
            )
        else:
            canvas.save(
                output_path,
                dpi=(settings.dpi, settings.dpi),
                compress_level=settings.png_compression_level,
            )
            canvas.close()
    saving_seconds = perf_counter() - saving_started
    size = output_path.stat().st_size
    result = {
        "filename": filename,
        "width_px": width,
        "height_px": height,
        "width_mm": round(width * 25.4 / settings.dpi, 1),
        "height_mm": round(height * 25.4 / settings.dpi, 1),
        "file_size_bytes": size,
        "png_compression_level": settings.png_compression_level,
        "png_engine": "libvips" if use_vips else "Pillow",
        "output_megabytes_per_second": round(
            size / 1_000_000 / max(saving_seconds, 0.001), 1
        ),
        "output_megapixels_per_second": round(
            width * height / 1_000_000 / max(saving_seconds, 0.001), 1
        ),
        "placements": [asdict(item) for _, item in planned],
        "rotation_count": sum(
            bool(item.rotation_degrees) for _, item in planned
        ),
        "timings_seconds": {
            "reading": round(reading_seconds, 3),
            "combining": round(combining_seconds, 3),
            "saving_png": round(saving_seconds, 3),
            "total": round(perf_counter() - total_started, 3),
        },
    }
    result.update(saving_metrics(baseline_height, height, settings.dpi))
    return result
