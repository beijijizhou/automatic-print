from __future__ import annotations
import atexit
from itertools import groupby
from pathlib import Path
from threading import RLock
from PIL import ImageColor
from automatic_print.layout_engine.labeling.base.dynamic_label import source_label_badge
from automatic_print.layout_engine.domain.models import LayoutSettings, Placement, ProgressCallback
from automatic_print.layout_engine.labeling.platform.platform_label import placement_badge, platform_text
from .vips_join import balanced_vertical_join as _balanced_vertical_join
from .row_bounds import streamed_row_bounds
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
# Gate outer evaluations; libvips still uses its own native worker threads.
demand_lock = RLock()
def available() -> bool:
    return pyvips is not None
def _rgba(path: Path, width: int, height: int, rotation_degrees: int, settings):
    image = pyvips.Image.new_from_file(str(path), access="random")
    from automatic_print.layout_engine.labeling.gap.virtual import expand_vips
    image = expand_vips(image, path, settings, pyvips)
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
def build_vips_rows(
    planned: list[tuple[Path, Placement]],
    labels: dict[int, str],
    width: int,
    settings: LayoutSettings,
    progress: ProgressCallback | None,
):
    rows = []
    completed = 0
    for plan_row_y, items_iter in groupby(
        planned, key=lambda item: item[1].row_y_px
    ):
        items = list(items_iter)
        # Keep final-canvas decorations lifted above the packing baseline.
        row_y, row_height = streamed_row_bounds(plan_row_y, items)
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
                    settings,
                )
            )
            xs.append(placement.x_px)
            ys.append(placement.y_px - row_y)
            if placement.platform_width_px:
                badge = placement_badge(
                    platform_text(path, settings),
                    placement.platform_width_px,
                    placement.platform_height_px,
                    placement.rotation_degrees,
                )
                layers.append(pyvips.Image.new_from_memory(badge.tobytes(), badge.width,
                    badge.height, 4, 'uchar').copy(interpretation='srgb'))
                xs.append(placement.platform_x_px)
                ys.append(placement.platform_y_px-row_y)
                badge.close()
            if placement.number_width_px and placement.number_height_px:
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
    return rows
def build_vips_canvas(
    planned: list[tuple[Path, Placement]],
    labels: dict[int, str],
    canvas_size: tuple[int, int],
    settings: LayoutSettings,
    progress: ProgressCallback | None,
):
    width, height = canvas_size
    rows = build_vips_rows(planned, labels, width, settings, progress)
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
        rows[0][0],
        width,
        height,
        extend="background",
        background=[0, 0, 0, 0],
    ).copy(xres=pixels_per_mm, yres=pixels_per_mm)
