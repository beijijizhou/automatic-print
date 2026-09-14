"""Physical marker placement before transparent-space embedding."""
from .decorations import outside_position
from .models import mm_to_px
from .qr_placement import signed_mm


def block_position(image_size, block_size, settings):
    if not settings.color_block_enabled:
        return 0, 0
    position = {'right_top': 'left_top', 'right': 'left',
                'right_bottom': 'left_bottom'}.get(settings.color_block_position,
                                                 settings.color_block_position)
    if position not in {'left_top', 'left', 'left_bottom'}:
        position = 'left_top'
    x, y = outside_position(image_size, block_size, position,
        mm_to_px(settings.color_block_gap_mm, settings.dpi),
        signed_mm(settings.color_block_offset_x_mm, settings.dpi),
        signed_mm(settings.color_block_offset_y_mm, settings.dpi))
    return min(x, -block_size[0]), y
