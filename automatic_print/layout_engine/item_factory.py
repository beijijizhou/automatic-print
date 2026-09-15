from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .images import print_dimensions
from .labels import format_label, settings_label_badge, label_layout
from .decorations import combined_footprint, outside_position
from .models import LayoutSettings, mm_to_px
from .qr_detection import QrLocation, detect_qr_location
from .dynamic_label import source_label_badge
from .membrane_region import detect_membrane_region
from .platform_label import platform_geometry, numbered_template
from .marker_space import can_embed_marker
from .rotated_marks import rotated_marks
from .qr_placement import signed_mm as _signed_mm, rotated_qr as _rotated_qr, qr_label_layout as _qr_label_layout
from .measurement_session import SESSION, measured_item, choice_source, resolved_name
from .item_block import block_position as _block_position


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
    platform_rx: int = 0
    platform_ry: int = 0
    platform_width: int = 0
    platform_height: int = 0
    left_marker_gap_px: int = 0
    left_marker_lift_px: int = 0
    preserve_header_gap: bool = False
    platform_below_marker: bool = False


def read_items(paths, settings, progress):
    from .parallel_measurement import read_parallel
    return read_parallel(_read_items, paths, settings, progress)


def _read_items(paths, settings, progress):
    if not paths:
        raise ValueError("没有可供排版的图片。")
    if progress:
        progress('读取图片尺寸', 0, len(paths), '开始读取尺寸并测量标签占位')
    labels, items = {}, []
    created_at = SESSION.get().created_at if SESSION.get() else datetime.now().astimezone()
    gap = mm_to_px(settings.number_gap_mm, settings.dpi)
    offset_x = _signed_mm(settings.label_offset_x_mm, settings.dpi)
    offset_y = _signed_mm(settings.label_offset_y_mm, settings.dpi)
    qr_attempted = (
        settings.number_images and settings.cutter_mode == "free" and (settings.label_detect_region or settings.label_fit_height or (
            settings.label_follow_qr and settings.label_position != "block_below"
        ))
    )
    qr_detected = 0
    for index, path in enumerate(paths, start=1):
        number = dict(settings.sequence_numbers).get(resolved_name(path), index)
        size = print_dimensions(path, settings.dpi)
        width = max(1, mm_to_px(size.width_mm, settings.dpi))
        height = max(1, mm_to_px(size.height_mm, settings.dpi))
        manual = dict(settings.manual_rotations).get(resolved_name(path), 0)
        if manual % 180:
            width, height = height, width
        qr_location = None
        if qr_attempted:
            qr_location = detect_qr_location(path)
            qr_detected += qr_location is not None
        if progress:
            progress('读取图片尺寸', index, len(paths),
                     f'{path.name} · {size.width_mm:.1f} × {size.height_mm:.1f} 毫米')
            progress('测量标签与刀码', index-1, len(paths), path.name)
        # Normal and rotated measurements share one decoded source, then close it.
        with choice_source(path, number, width, height, settings, manual):
            choices = [
                measured_item(
                    _make_item, path, number, width, height, settings, labels,
                    created_at, gap, offset_x, offset_y, manual, qr_location,
                )
            ]
            if settings.allow_rotation and not manual and width != height:
                degrees = 90 if settings.rotation_direction == "left" else -90
                choices.append(
                    measured_item(
                        _make_item, path, number, height, width, settings, labels,
                        created_at, gap, offset_x, offset_y, degrees, qr_location,
                    )
                )
        items.append(choices)
        if progress:
            source = "图片内嵌 DPI" if size.embedded_dpi else "缺少 DPI，按输出 DPI 估算"
            progress(
                "测量标签与刀码", index, len(paths),
                f"{path}\t{path.name} · {size.width_mm:.1f} × {size.height_mm:.1f} 毫米 · {source}",
            )
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
    decorations = [
        (px, py, pw, ph),
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
        px+image_rx, py+image_ry, pw, ph,
        max(1, mm_to_px(settings.color_block_gap_mm, settings.dpi))
        if settings.cutter_left_marker_external and settings.cutter_mode != 'free' else 0,
        mm_to_px(settings.cutter_left_marker_lift_mm, settings.dpi)
        if settings.cutter_left_marker_external and settings.cutter_mode != 'free' else 0,
        settings.preserve_header_gap,
        settings.platform_below_marker,
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
