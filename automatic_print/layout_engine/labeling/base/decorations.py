from __future__ import annotations


def outside_position(
    image_size: tuple[int, int],
    element_size: tuple[int, int],
    position: str,
    gap: int,
    offset_x: int,
    offset_y: int,
) -> tuple[int, int]:
    width, height = image_size
    box_width, box_height = element_size
    positions = {
        "top_left": (0, -gap - box_height),
        "top": ((width - box_width) // 2, -gap - box_height),
        "top_right": (width - box_width, -gap - box_height),
        "left": (-gap - box_width, (height - box_height) // 2),
        "left_top": (-gap - box_width, 0),
        "left_bottom": (-gap - box_width, height - box_height),
        "right": (width + gap, (height - box_height) // 2),
        "right_top": (width + gap, 0),
        "right_bottom": (width + gap, height - box_height),
        "bottom_left": (0, height + gap),
        "bottom": ((width - box_width) // 2, height + gap),
        "bottom_right": (width - box_width, height + gap),
    }
    x, y = positions.get(position, positions["bottom"])
    return x + offset_x, y + offset_y


def combined_footprint(image_size, decorations):
    width, height = image_size
    boxes = [(0, 0, width, height)] + [
        (x, y, x + box_width, y + box_height)
        for x, y, box_width, box_height in decorations
        if box_width and box_height
    ]
    min_x = min(box[0] for box in boxes)
    min_y = min(box[1] for box in boxes)
    max_x = max(box[2] for box in boxes)
    max_y = max(box[3] for box in boxes)
    return -min_x, -min_y, max_x - min_x, max_y - min_y
