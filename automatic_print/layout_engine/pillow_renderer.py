from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from .images import normalized_image
from .labels import label_badge
from .models import LayoutSettings, Placement, ProgressCallback


def _prepare(item: tuple[Path, Placement]):
    path, placement = item
    return normalized_image(
        path, (placement.width_px, placement.height_px)
    ), placement


def build_pillow_canvas(
    planned: list[tuple[Path, Placement]],
    labels: dict[int, str],
    canvas_size: tuple[int, int],
    settings: LayoutSettings,
    progress: ProgressCallback | None,
) -> Image.Image:
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    workers = max(1, min(settings.worker_threads, len(planned)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for index, (image, placement) in enumerate(
            executor.map(_prepare, planned), start=1
        ):
            canvas.paste(image, (placement.x_px, placement.y_px))
            image.close()
            if settings.number_images:
                badge = label_badge(
                    labels[placement.sequence_number],
                    settings.dpi,
                    settings.number_font_size_mm,
                )
                canvas.alpha_composite(
                    badge,
                    (placement.number_x_px, placement.number_y_px),
                )
                badge.close()
            if progress:
                progress(
                    "合成图片", index, len(planned), placement.source
                )
    return canvas
