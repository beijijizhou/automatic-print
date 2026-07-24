from __future__ import annotations

from itertools import groupby
from pathlib import Path

from .labels import label_badge
from .models import LayoutSettings, Placement, ProgressCallback

try:
    import pyvips
except (ImportError, OSError):
    pyvips = None


def available() -> bool:
    return pyvips is not None


def _rgba(path: Path, width: int, height: int):
    image = pyvips.Image.new_from_file(str(path), access="sequential")
    if str(image.interpretation) not in {
        "srgb", "rgb", "b-w", "grey16", "multiband"
    }:
        image = image.colourspace("srgb")
    image = image.thumbnail_image(
        width, height=height, size="force", no_rotate=True
    )
    if image.format != "uchar":
        image = image.cast("uchar")
    if image.bands == 1:
        grey = image[0]
        image = grey.bandjoin([grey, grey, 255])
    elif image.bands == 2:
        grey = image[0]
        image = grey.bandjoin([grey, grey, image[1]])
    elif image.bands == 3:
        image = image.bandjoin(255)
    elif image.bands > 4:
        image = image.extract_band(0, n=4)
    return image.copy(interpretation="srgb")


def build_vips_canvas(
    planned: list[tuple[Path, Placement]],
    labels: dict[int, str],
    canvas_size: tuple[int, int],
    settings: LayoutSettings,
    progress: ProgressCallback | None,
):
    width, height = canvas_size
    margin = min(
        min(p.x_px, p.number_x_px if settings.number_images else p.x_px)
        for _, p in planned
    )
    rows = []
    completed = 0
    for row_y, items_iter in groupby(
        planned, key=lambda item: item[1].row_y_px
    ):
        items = list(items_iter)
        row_height = max(p.footprint_height_px for _, p in items)
        row_canvas = pyvips.Image.black(
            width - 2 * margin, row_height, bands=4
        ).copy(interpretation="srgb")
        layers, xs, ys = [], [], []
        for path, placement in items:
            layers.append(
                _rgba(path, placement.width_px, placement.height_px)
            )
            xs.append(placement.x_px - margin)
            ys.append(placement.y_px - row_y)
            if settings.number_images:
                badge = label_badge(
                    labels[placement.sequence_number],
                    settings.dpi,
                    settings.number_font_size_mm,
                )
                layers.append(
                    pyvips.Image.new_from_memory(
                        badge.tobytes(),
                        badge.width,
                        badge.height,
                        4,
                        "uchar",
                    ).copy(interpretation="srgb")
                )
                xs.append(placement.number_x_px - margin)
                ys.append(placement.number_y_px - row_y)
                badge.close()
            completed += 1
            if progress:
                progress(
                    "合成图片",
                    completed,
                    len(planned),
                    placement.source,
                )
        rows.append(
            (
                row_y,
                row_height,
                row_canvas.composite(
                    layers, ["over"] * len(layers), x=xs, y=ys
                ),
            )
        )
    _, previous_height, canvas = rows[0]
    previous_y = rows[0][0]
    for row_y, row_height, row_canvas in rows[1:]:
        canvas = canvas.join(
            row_canvas,
            "vertical",
            expand=True,
            shim=row_y - (previous_y + previous_height),
            background=[0, 0, 0, 0],
            align="low",
        )
        previous_y, previous_height = row_y, row_height
    pixels_per_mm = settings.dpi / 25.4
    return canvas.embed(
        margin,
        margin,
        width,
        height,
        extend="background",
        background=[0, 0, 0, 0],
    ).copy(xres=pixels_per_mm, yres=pixels_per_mm)
