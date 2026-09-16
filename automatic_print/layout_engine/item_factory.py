from __future__ import annotations
from pathlib import Path
from .labels import format_label, label_layout
from .decorations import combined_footprint
from .models import LayoutItem, LayoutSettings, mm_to_px
from .qr_detection import detect_qr_location
from .dynamic_label import source_label_badge
from .membrane_region import detect_membrane_region
from .platform_label import platform_geometry, numbered_template
from .marker_space import can_embed_marker, transparent_rect
from .rotated_marks import rotated_marks
from .qr_placement import rotated_qr as _rotated_qr, qr_label_layout as _qr_label_layout
from .item_block import block_position as _block_position
def read_items(paths, settings, progress):
    from .item_reader import read_items as read_source_items

    return read_source_items(
        paths, settings, progress, _make_item, detect_qr_location
    )
def _make_item(
    path, index, width, height, settings, labels,
    created_at, gap, offset_x, offset_y, rotation_degrees, qr_location,
):
    values = _label_values(
        path, index, width, height, settings, labels,
        created_at, gap, offset_x, offset_y,
        rotation_degrees, qr_location,
    )
    image_rx, image_ry, label_rx, label_ry = values[:4]
    label_width, label_height = values[4:6]
    label_x, label_y = label_rx - image_rx, label_ry - image_ry
    block_width = (
        mm_to_px(settings.color_block_width_mm, settings.dpi)
        if settings.color_block_enabled else 0
    )
    block_height = (
        mm_to_px(settings.color_block_height_mm, settings.dpi)
        if settings.color_block_enabled else 0
    )
    block_x, block_y = _block_position(
        (width, height), (block_width, block_height), settings
    )
    px, py, pw, ph = platform_geometry(path, settings, width, height, rotation_degrees)
    if pw and px < 0:
        # Reserve space outside the artwork, while retaining the left cutter marker.
        block_x = min(block_x, px-mm_to_px(settings.color_block_gap_mm, settings.dpi)-block_width)
    if settings.number_images and settings.cutter_mode != "free":
        label_x = block_x
        label_y = block_y + block_height + gap
    elif settings.number_images and (settings.label_detect_region or settings.label_fit_height):
        # Keep text outside the artwork and marker, inside the image's vertical span.
        label_x = min(-gap, block_x if block_width else -gap) - label_width - gap
        center = _rotated_qr(qr_location, rotation_degrees)[1] if qr_location else 0
        if settings.label_detect_region:
            region = detect_membrane_region(path).rotated(rotation_degrees)
            center = (region.top+region.bottom)/2
            if (region.left+region.right)/2 >= 0.5:
                label_x = width + gap
            # The original header's side is transformed with the artwork;
            # marker position remains independent and always on the left.
        label_y = min(max(0, round(center * height - label_height / 2)), height - label_height)
        if label_height > height:
            raise ValueError("膜标签高度超过图片高度，请调整膜标签实际高度。")
    elif settings.number_images and settings.label_position == "block_below":
        if not block_width:
            raise ValueError("标签放在色块下方时，必须启用色块。")
        label_x = block_x + block_width - label_width + min(0, offset_x)
        label_y = block_y + block_height + gap + max(0, offset_y)
    rotated = rotated_marks(path, width, height, rotation_degrees, settings,
        (block_x, block_y, block_width, block_height),
        (label_x, label_y, label_width, label_height), (px, py, pw, ph))
    if rotated:
        block_x, block_y, label_x, label_y = rotated
    elif settings.cutter_mode != 'free' and not settings.preserve_header_gap and can_embed_marker(
        path, width, height, rotation_degrees,
        (0, block_y, block_width, block_height),
        (0, label_y, label_width, label_height), (px, py, pw, ph),
    ):
        block_x = label_x = 0
    from .marker_stack import stacked_coordinates
    block_x, block_y, label_x, label_y, px, py = stacked_coordinates(settings,
        (block_x, block_y, block_width, block_height), (label_x, label_y, label_width, label_height), (px, py, pw, ph))
    if (settings.platform_reuse_qr and pw and ph and px < width and px+pw > 0
            and py < height and py+ph > 0):
        if not transparent_rect(path, width, height, rotation_degrees,
                                (px, py, pw, ph)):
            raise ValueError(f'{path.name}：平台文字没有可复用的二维码透明空位。')
    from .marker_stack import header_safe_coordinates
    block, label, platform = header_safe_coordinates(
        path, settings, (width, height), rotation_degrees,
        (block_x, block_y, block_width, block_height),
        (label_x, label_y, label_width, label_height),
        (px, py, pw, ph),
    )
    block_x, block_y, block_width, block_height = block
    label_x, label_y, label_width, label_height = label
    px, py, pw, ph = platform
    decorations = [
        (px, py, pw, ph),
        (label_x, label_y, label_width, label_height),
        (block_x, block_y, block_width, block_height),
    ]
    for x, y, decoration_width, decoration_height in decorations:
        overlaps = (
            decoration_width
            and decoration_height
            and x < width
            and x + decoration_width > 0
            and y < height
            and y + decoration_height > 0
        )
        if overlaps:
            transparent_rect(
                path,
                width,
                height,
                rotation_degrees,
                (x, y, decoration_width, decoration_height),
            )
    image_rx, image_ry, footprint_width, footprint_height = (
        combined_footprint((width, height), decorations)
    )
    return LayoutItem(
        path, index, width, height, image_rx, image_ry,
        label_x + image_rx, label_y + image_ry,
        label_width, label_height, footprint_width, footprint_height,
        rotation_degrees, block_x + image_rx, block_y + image_ry,
        block_width, block_height,
        px+image_rx, py+image_ry, pw, ph,
        max(1, mm_to_px(settings.color_block_gap_mm, settings.dpi))
        if settings.cutter_left_marker_external and settings.cutter_mode != 'free' else 0,
        mm_to_px(settings.cutter_left_marker_lift_mm, settings.dpi)
        if settings.cutter_left_marker_external and settings.cutter_mode != 'free' else 0,
        settings.preserve_header_gap,
        settings.platform_below_marker,
        settings.platform_reuse_qr,
    )
def _label_values(
    path, index, width, height, settings, labels,
    created_at, gap, offset_x, offset_y, rotation_degrees, qr_location,
):
    if not settings.number_images:
        return 0, 0, 0, 0, 0, 0, width, height
    text = format_label(
        numbered_template(settings),
        index,
        path,
        created_at,
        settings.label_date_format,
        settings.machine_number,
        settings.label_sequence_total,
        settings.label_batch_name,
    )
    labels[index] = text
    badge = source_label_badge(text, settings, path, rotation_degrees)
    label_width, label_height = badge.size
    badge.close()
    if qr_location is not None:
        layout = _qr_label_layout(
            (width, height),
            (label_width, label_height),
            qr_location,
            rotation_degrees,
            gap,
            offset_x,
            offset_y,
        )
    else:
        layout = label_layout(
            (width, height),
            (label_width, label_height),
            settings.label_position,
            gap,
            offset_x,
            offset_y,
        )
    return *layout[:4], label_width, label_height, *layout[4:]
