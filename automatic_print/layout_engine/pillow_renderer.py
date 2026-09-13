from __future__ import annotations

from contextlib import closing
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw

from .images import normalized_image
from .dynamic_label import source_label_badge
from .models import LayoutSettings, Placement, ProgressCallback
from .image_pipeline import prepared_images


def _prepare(item: tuple[Path, Placement]):
    path, placement = item
    rotated = bool(placement.rotation_degrees % 180)
    size = (
        (placement.height_px, placement.width_px)
        if rotated
        else (placement.width_px, placement.height_px)
    )
    image = normalized_image(path, size)
    if placement.rotation_degrees == 90:
        image = image.transpose(Image.Transpose.ROTATE_90)
    elif placement.rotation_degrees == -90:
        image = image.transpose(Image.Transpose.ROTATE_270)
    elif placement.rotation_degrees == 180:
        image = image.transpose(Image.Transpose.ROTATE_180)
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
    with closing(prepared_images(_prepare, planned, workers)) as images:
        for index, (image, placement) in enumerate(
            images, start=1
        ):
            canvas.paste(image, (placement.x_px, placement.y_px))
            image.close()
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
