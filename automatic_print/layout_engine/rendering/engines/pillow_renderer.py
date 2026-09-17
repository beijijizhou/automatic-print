from __future__ import annotations

from contextlib import closing
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw

from automatic_print.layout_engine.intake.metadata.images import normalized_image
from automatic_print.layout_engine.labeling.base.dynamic_label import source_label_badge
from automatic_print.layout_engine.domain.models import LayoutSettings, Placement, ProgressCallback
from automatic_print.layout_engine.intake.preparation.image_pipeline import prepared_images
from automatic_print.layout_engine.labeling.platform.platform_label import placement_badge, platform_text


def _prepare(item: tuple[Path, Placement]):
    path, placement = item
    rotated = bool(placement.rotation_degrees % 180)
    size = (
        (placement.height_px, placement.width_px)
        if rotated
        else (placement.width_px, placement.height_px)
    )
    image = normalized_image(path, size)
    rotation = {90: Image.Transpose.ROTATE_90, -90: Image.Transpose.ROTATE_270,
                180: Image.Transpose.ROTATE_180}.get(placement.rotation_degrees)
    if rotation is not None:
        original = image
        try:
            image = original.transpose(rotation)
        finally:
            original.close()
    return image, placement


def build_pillow_canvas(
    planned: list[tuple[Path, Placement]],
    labels: dict[int, str],
    canvas_size: tuple[int, int],
    settings: LayoutSettings,
    progress: ProgressCallback | None,
) -> Image.Image:
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    workers = max(1, min(settings.worker_threads, len(planned)))
    try:
        return _compose(canvas, planned, labels, settings, progress, workers)
    except BaseException:
        canvas.close()
        raise


def _compose(canvas, planned, labels, settings, progress, workers):
    with closing(prepared_images(_prepare, planned, workers)) as images:
        for index, (image, placement) in enumerate(
            images, start=1
        ):
            canvas.paste(image, (placement.x_px, placement.y_px))
            if placement.platform_width_px:
                path = planned[index-1][0]
                badge = placement_badge(
                    platform_text(path, settings),
                    placement.platform_width_px,
                    placement.platform_height_px,
                    placement.rotation_degrees,
                )
                canvas.alpha_composite(badge, (placement.platform_x_px, placement.platform_y_px))
                badge.close()
            if settings.number_images:
                badge = source_label_badge(
                    labels[placement.sequence_number],
                    settings,
                    planned[index-1][0],
                    placement.rotation_degrees,
                )
                canvas.alpha_composite(
                    badge,
                    (placement.number_x_px, placement.number_y_px),
                )
                badge.close()
            if settings.color_block_enabled:
                ImageDraw.Draw(canvas).rectangle(
                    (
                        placement.color_block_x_px,
                        placement.color_block_y_px,
                        placement.color_block_x_px
                        + placement.color_block_width_px - 1,
                        placement.color_block_y_px
                        + placement.color_block_height_px - 1,
                    ),
                    fill=ImageColor.getrgb(settings.color_block_color)
                    + (255,),
                )
            if progress:
                progress(
                    "合成图片", index, len(planned), placement.source
                )
    return canvas
