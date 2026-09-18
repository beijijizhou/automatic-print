"""Final-canvas bounds for one streamed rendering row."""


def streamed_row_bounds(plan_row_y, items):
    """Include decorations lifted above the packing baseline."""
    tops = [plan_row_y]
    bottoms = [
        plan_row_y + max(placement.footprint_height_px
                         for _path, placement in items)
    ]
    for _path, placement in items:
        for y, height in (
            (placement.y_px, placement.height_px),
            (placement.platform_y_px, placement.platform_height_px),
            (placement.number_y_px, placement.number_height_px),
            (placement.color_block_y_px, placement.color_block_height_px),
        ):
            if height:
                tops.append(y)
                bottoms.append(y + height)
    top = min(tops)
    return top, max(bottoms) - top
