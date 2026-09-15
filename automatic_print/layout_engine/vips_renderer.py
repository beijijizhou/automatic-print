from __future__ import annotations

import atexit
from itertools import groupby
from pathlib import Path
from threading import RLock

from PIL import ImageColor

from .dynamic_label import source_label_badge
from .models import LayoutSettings, Placement, ProgressCallback, mm_to_px
from .platform_label import platform_badge

try:
    import pyvips
except (ImportError, OSError):
    pyvips = None
else:
    # libvips owns native worker threads.  Let it join those workers before
    # Python starts destroying extension modules during a normal/restart exit.
    def _shutdown_vips():
        pyvips.cache_set_max(0)
        pyvips.shutdown()

    atexit.register(_shutdown_vips)


# This Homebrew libvips build can crash when independent Python worker pools
# start several demand evaluations at once. libvips still uses its own native
# worker threads inside each evaluation; only the outer evaluations are gated.
demand_lock = RLock()


def available() -> bool:
    return pyvips is not None

def _rgba(path: Path, width: int, height: int, rotation_degrees: int):
    # Pixel validation can evaluate a source before PNG saving re-reads it.
    # A forward-only decoder fails on that second pass, especially after rotation.
    image = pyvips.Image.new_from_file(str(path), access="random")
    if str(image.interpretation) not in {
        "srgb", "rgb", "b-w", "grey16", "multiband"
    }:
        image = image.colourspace("srgb")
    target_width, target_height = (
        (height, width) if rotation_degrees % 180 else (width, height)
    )
    if image.width != target_width or image.height != target_height:
        image = image.thumbnail_image(
            target_width, height=target_height, size="force", no_rotate=True
        )
    if rotation_degrees == 90:
        image = image.rot("d270")
    elif rotation_degrees == -90:
        image = image.rot("d90")
    elif rotation_degrees == 180:
        image = image.rot("d180")
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
    top_margin = mm_to_px(settings.margin_mm, settings.dpi)
    rows = []
    completed = 0
    for row_y, items_iter in groupby(
        planned, key=lambda item: item[1].row_y_px
    ):
        items = list(items_iter)
        row_height = max(p.footprint_height_px for _, p in items)
        row_canvas = pyvips.Image.black(
            width, row_height, bands=4
        ).copy(interpretation="srgb")
        layers, xs, ys = [], [], []
        for path, placement in items:
            layers.append(
                _rgba(
                    path,
                    placement.width_px,
                    placement.height_px,
                    placement.rotation_degrees,
                )
            )
            xs.append(placement.x_px)
            ys.append(placement.y_px - row_y)
            if placement.platform_width_px:
                badge = platform_badge(settings.platform_name, placement.platform_height_px)
                layers.append(pyvips.Image.new_from_memory(badge.tobytes(), badge.width,
                    badge.height, 4, 'uchar').copy(interpretation='srgb'))
                xs.append(placement.platform_x_px)
                ys.append(placement.platform_y_px-row_y)
                badge.close()
            if settings.number_images:
                badge = source_label_badge(
                    labels[placement.sequence_number],
                    settings,
                    path, placement.rotation_degrees,
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
                xs.append(placement.number_x_px)
                ys.append(placement.number_y_px - row_y)
                badge.close()
            if settings.color_block_enabled:
                red, green, blue = ImageColor.getrgb(
                    settings.color_block_color
                )
                layers.append(
                    pyvips.Image.black(
                        placement.color_block_width_px,
                        placement.color_block_height_px,
                        bands=4,
                    ).new_from_image([red, green, blue, 255]).copy(
                        interpretation="srgb"
                    )
                )
                xs.append(placement.color_block_x_px)
                ys.append(placement.color_block_y_px - row_y)
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
    pieces = [rows[0][2]]
    previous_y, previous_height = rows[0][:2]
    for row_y, row_height, row_canvas in rows[1:]:
        gap = row_y - (previous_y + previous_height)
        if gap < 0:
            raise ValueError("排版行发生垂直重叠，禁止生成输出。")
        if gap:
            pieces.append(pyvips.Image.black(width, gap, bands=4).copy(
                interpretation="srgb"
            ))
        pieces.append(row_canvas)
        previous_y, previous_height = row_y, row_height
    canvas = _balanced_vertical_join(pieces)
    pixels_per_mm = settings.dpi / 25.4
    return canvas.embed(
        0,
        top_margin,
        width,
        height,
        extend="background",
        background=[0, 0, 0, 0],
    ).copy(xres=pixels_per_mm, yres=pixels_per_mm)


def _balanced_vertical_join(images):
    """Build a shallow demand graph instead of an O(rows)-deep join chain."""
    level = list(images)
    while len(level) > 1:
        joined = []
        for index in range(0, len(level), 2):
            if index + 1 == len(level):
                joined.append(level[index])
            else:
                joined.append(level[index].join(
                    level[index + 1], "vertical", expand=True,
                    background=[0, 0, 0, 0], align="low",
                ))
        level = joined
    return level[0]
