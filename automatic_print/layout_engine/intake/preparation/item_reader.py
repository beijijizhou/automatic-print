"""Read source metadata once and produce normal/rotated layout choices."""

from datetime import datetime
import sqlite3

from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.layout_engine.measurement.measurement_session import (
    SESSION,
    choice_source,
    measured_item,
    resolved_name,
)
from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.labeling.markers.qr_placement import signed_mm


def read_items(paths, settings, progress, make_item, detect_qr_location):
    from automatic_print.layout_engine.measurement.parallel_measurement import (
        preload_dimensions,
        read_parallel,
    )

    preload_dimensions(paths, settings)
    _preload_cached_items(paths, settings)

    def read_source(source_paths, source_settings, source_progress):
        return _read_items(
            source_paths,
            source_settings,
            source_progress,
            make_item,
            detect_qr_location,
        )

    return read_parallel(
        read_source, paths, settings, progress
    )


def _preload_cached_items(paths, settings):
    """Load only this batch's normal/rotated item records in one SQL query."""
    session = SESSION.get()
    if session is None:
        return
    from automatic_print.layout_engine.measurement.measurement_cache import (
        decode_item, item_key, item_settings,
    )
    from automatic_print.layout_engine.measurement.measurement_session import (
        identity, persistent_cache,
    )
    normalized = item_settings(settings)
    numbers = dict(settings.sequence_numbers)
    manual_rotations = dict(settings.manual_rotations)
    overrides = dict(settings.dimension_overrides)
    requested = []
    try:
        for position, path in enumerate(paths, 1):
            name = resolved_name(path)
            number = numbers.get(name, position)
            size = print_dimensions(path, settings.dpi)
            width_mm, height_mm = overrides.get(
                name, (size.width_mm, size.height_mm)
            )
            width = max(1, mm_to_px(width_mm, settings.dpi))
            height = max(1, mm_to_px(height_mm, settings.dpi))
            manual = manual_rotations.get(name, 0)
            if manual % 180:
                width, height = height, width
            variants = [(width, height, manual)]
            if settings.allow_rotation and not manual and width != height:
                degree = 90 if settings.rotation_direction == 'left' else -90
                variants.append((height, width, degree))
            file_identity = identity(path)
            for item_width, item_height, degree in variants:
                memory_key = (file_identity, number, item_width, item_height,
                              normalized, degree)
                if memory_key in session.items:
                    continue
                persistent_key = item_key(
                    file_identity, number, item_width, item_height,
                    normalized, degree, session.created_at,
                )
                requested.append((persistent_key, memory_key))
        values = persistent_cache().load_many(
            'item', [persistent_key for persistent_key, _ in requested]
        )
        for persistent_key, memory_key in requested:
            value = values.get(persistent_key)
            if value is not None:
                session.items[memory_key] = decode_item(value)
                session.timing.cache_item(True)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        return


def _read_items(paths, settings, progress, make_item, detect_qr_location):
    if not paths:
        raise ValueError("没有可供排版的图片。")
    if progress:
        progress("读取图片尺寸", 0, len(paths), "开始读取尺寸并测量标签占位")
    labels, items = {}, []
    session = SESSION.get()
    created_at = session.created_at if session else datetime.now().astimezone()
    gap = mm_to_px(settings.number_gap_mm, settings.dpi)
    offset_x = signed_mm(settings.label_offset_x_mm, settings.dpi)
    offset_y = signed_mm(settings.label_offset_y_mm, settings.dpi)
    qr_attempted = settings.number_images and settings.cutter_mode == "free" and (
        settings.label_detect_region
        or settings.label_fit_height
        or (settings.label_follow_qr and settings.label_position != "block_below")
    )
    qr_detected = 0
    for index, path in enumerate(paths, start=1):
        name = resolved_name(path)
        number = dict(settings.sequence_numbers).get(name, index)
        size = print_dimensions(path, settings.dpi)
        dimensions = dict(settings.dimension_overrides).get(
            name, (size.width_mm, size.height_mm)
        )
        width = max(1, mm_to_px(dimensions[0], settings.dpi))
        height = max(1, mm_to_px(dimensions[1], settings.dpi))
        manual = dict(settings.manual_rotations).get(name, 0)
        if manual % 180:
            width, height = height, width
        qr_location = detect_qr_location(path) if qr_attempted else None
        qr_detected += qr_location is not None
        if progress:
            progress(
                "读取图片尺寸",
                index,
                len(paths),
                f"{path.name} · {dimensions[0]:.1f} × {dimensions[1]:.1f} 毫米",
            )
            progress("测量标签与刀码", index - 1, len(paths), path.name)
        with choice_source(path, number, width, height, settings, manual):
            choices = [
                measured_item(
                    make_item, path, number, width, height, settings, labels,
                    created_at, gap, offset_x, offset_y, manual, qr_location,
                )
            ]
            if settings.allow_rotation and not manual and width != height:
                degrees = 90 if settings.rotation_direction == "left" else -90
                choices.append(
                    measured_item(
                        make_item, path, number, height, width, settings, labels,
                        created_at, gap, offset_x, offset_y, degrees, qr_location,
                    )
                )
        items.append(choices)
        if progress:
            source = "图片内嵌 DPI" if size.embedded_dpi else "缺少 DPI，按输出 DPI 估算"
            progress(
                "测量标签与刀码",
                index,
                len(paths),
                f"{path}\t{path.name} · {dimensions[0]:.1f} × {dimensions[1]:.1f} 毫米 · {source}",
            )
    if progress and qr_attempted:
        progress(
            "识别膜标签",
            len(paths),
            len(paths),
            f"识别成功 {qr_detected} 张，未识别 {len(paths) - qr_detected} 张",
        )
    return items, labels
