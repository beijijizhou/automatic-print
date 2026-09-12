from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .images import target_size
from .labels import format_label, label_badge, label_layout
from .decorations import combined_footprint, outside_position
from .models import LayoutSettings, mm_to_px
from .qr_detection import QrLocation, detect_qr_location


@dataclass(frozen=True)
class LayoutItem:
    path: Path
    index: int
    width: int
    height: int
    image_rx: int
    image_ry: int
    label_rx: int
    label_ry: int
    label_width: int
    label_height: int
    footprint_width: int
    footprint_height: int
    rotation_degrees: int
    block_rx: int
    block_ry: int
    block_width: int
    block_height: int


def read_items(paths, settings, progress):
    if not paths:
        raise ValueError("没有可供排版的图片。")
    labels, items = {}, []
    created_at = datetime.now().astimezone()
    gap = mm_to_px(settings.number_gap_mm, settings.dpi)
    offset_x = _signed_mm(settings.label_offset_x_mm, settings.dpi)
    offset_y = _signed_mm(settings.label_offset_y_mm, settings.dpi)
    qr_attempted = settings.number_images and settings.label_follow_qr
    qr_detected = 0
    for index, path in enumerate(paths, start=1):
        width, height = target_size(path, settings.dpi)
        qr_location = None
        if qr_attempted:
            qr_location = detect_qr_location(path)
            qr_detected += qr_location is not None
        choices = [
            _make_item(
                path, index, width, height, settings, labels,
                created_at, gap, offset_x, offset_y, 0, qr_location,
            )
        ]
        if settings.allow_rotation and width != height:
            degrees = 90 if settings.rotation_direction == "left" else -90
            choices.append(
                _make_item(
                    path, index, height, width, settings, labels,
                    created_at, gap, offset_x, offset_y, degrees,
                    qr_location,
                )
            )
        items.append(choices)
        if progress:
            progress("读取图片尺寸", index, len(paths), path.name)
    if progress and qr_attempted:
        progress(
            "识别膜标签",
            len(paths),
            len(paths),
            f"识别成功 {qr_detected} 张，未识别 {len(paths) - qr_detected} 张",
        )
    return items, labels


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
    decorations = [
        (label_x, label_y, label_width, label_height),
        (block_x, block_y, block_width, block_height),
    ]
    image_rx, image_ry, footprint_width, footprint_height = (
        combined_footprint((width, height), decorations)
    )
    return LayoutItem(
        path, index, width, height, image_rx, image_ry,
        label_x + image_rx, label_y + image_ry,
        label_width, label_height, footprint_width, footprint_height,
        rotation_degrees, block_x + image_rx, block_y + image_ry,
        block_width, block_height,
    )


def _block_position(image_size, block_size, settings):
    if not settings.color_block_enabled:
        return 0, 0
    left_positions = {
        "right_top": "left_top",
        "right": "left",
        "right_bottom": "left_bottom",
    }
    position = left_positions.get(
        settings.color_block_position, settings.color_block_position
    )
    if position not in {"left_top", "left", "left_bottom"}:
        position = "left_top"
    x, y = outside_position(
        image_size,
        block_size,
        position,
        mm_to_px(settings.color_block_gap_mm, settings.dpi),
        _signed_mm(settings.color_block_offset_x_mm, settings.dpi),
        _signed_mm(settings.color_block_offset_y_mm, settings.dpi),
    )
    return min(x, -block_size[0]), y


def _label_values(
    path, index, width, height, settings, labels,
    created_at, gap, offset_x, offset_y, rotation_degrees, qr_location,
):
    if not settings.number_images:
        return 0, 0, 0, 0, 0, 0, width, height
    text = format_label(
        settings.label_text_template,
        index,
        path,
        created_at,
        settings.label_date_format,
    )
    labels[index] = text
    badge = label_badge(
        text, settings.dpi, settings.number_font_size_mm
    )
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


def _qr_label_layout(
    image_size, label_size, location, rotation_degrees,
    gap, offset_x, offset_y,
):
    width, height = image_size
    label_width, label_height = label_size
    x_ratio, y_ratio = _rotated_qr(location, rotation_degrees)
    if x_ratio < 0.5:
        label_x = -gap - label_width
    else:
        label_x = width + gap
    label_y = round(y_ratio * height - label_height / 2)
    label_y = min(max(0, label_y), max(0, height - label_height))
    label_x += offset_x
    label_y += offset_y
    image_rx, image_ry, footprint_width, footprint_height = (
        combined_footprint(
            image_size,
            [(label_x, label_y, label_width, label_height)],
        )
    )
    return (
        image_rx,
        image_ry,
        label_x + image_rx,
        label_y + image_ry,
        footprint_width,
        footprint_height,
    )


def _rotated_qr(location: QrLocation, rotation_degrees: int):
    x_ratio, y_ratio = location.x_ratio, location.y_ratio
    if rotation_degrees == 90:
        return y_ratio, 1 - x_ratio
    if rotation_degrees == -90:
        return 1 - y_ratio, x_ratio
    return x_ratio, y_ratio


def _signed_mm(value: float, dpi: int) -> int:
    pixels = mm_to_px(abs(value), dpi)
    return -pixels if value < 0 else pixels
