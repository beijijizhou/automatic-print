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
    label_x = item.label_rx+dx if item.rotation_degrees else 0
    width = max(image_x+item.width, item.block_width,
                label_x+item.label_width if item.label_width else 0,
                platform_x+item.platform_width if item.platform_width else 0)
    return replace(item, image_rx=image_x, block_rx=0, label_rx=label_x,
                   platform_rx=platform_x, footprint_width=width)
