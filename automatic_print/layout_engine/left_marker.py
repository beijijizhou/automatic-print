"""Left-lane artwork clearance; right-lane embedding remains unchanged."""
from dataclasses import replace
from functools import lru_cache


@lru_cache(maxsize=4096)
def external_left_item(item):
    gap = item.left_marker_gap_px
    if not gap or not item.block_width:
        return item
    dx = max(0, item.block_width+gap-item.image_rx)
    image_x = item.image_rx+dx
    platform_x = item.platform_rx+dx
    # Rotated text follows the membrane card; upright text stays under the mark.
    label_x = item.label_rx+dx if item.rotation_degrees and not item.preserve_header_gap else 0
    width = max(image_x+item.width, item.block_width,
                label_x+item.label_width if item.label_width else 0,
                platform_x+item.platform_width if item.platform_width else 0)
    return replace(item, image_rx=image_x, block_rx=0, label_rx=label_x,
                   block_ry=item.image_ry-item.left_marker_lift_px,
                   label_ry=item.label_ry-item.left_marker_lift_px
                   if not item.rotation_degrees and item.block_ry != item.image_ry-item.left_marker_lift_px
                   else item.label_ry,
                   platform_rx=platform_x, footprint_width=width)


def head_margin(settings):
    from .models import mm_to_px
    lift = settings.cutter_left_marker_lift_mm if settings.cutter_left_marker_external else 0
    if lift < 0 or lift > settings.spacing_mm:
        raise ValueError('左图刀码抬高量必须在0与图片垂直间距之间，请调整打印设置。')
    return mm_to_px(max(settings.margin_mm, lift), settings.dpi)
