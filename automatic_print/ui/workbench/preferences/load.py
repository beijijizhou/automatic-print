"""Restore canonical print controls from persistent settings."""

import re

from ...spacing_settings import migrate_spacing


def load_layout_preferences(window) -> None:
    migrate_spacing(window.preferences)
    values = (
        (window.width, "layout/media_width_mm", 600, float),
        (window.spacing, "layout/spacing_mm", 8, float),
        (window.margin, "layout/margin_mm", 3, float),
        (window.dpi, "layout/dpi", 300, int),
        (window.worker_threads, "layout/worker_threads", 4, int),
    )
    for widget, key, default, value_type in values:
        widget.setValue(window.preferences.value(key, default, value_type))
    window.number_images.setChecked(
        window.preferences.value(
            "layout/number_images",
            window.preferences.value("label/enabled", True, bool),
            bool,
        )
    )
    window.allow_rotation.setChecked(
        window.preferences.value("layout/allow_rotation", True, bool)
    )
    _restore_combo(window.rotation_direction, window.preferences.value(
        "layout/rotation_direction", "left", str))
    _restore_combo(window.png_compression, window.preferences.value(
        "layout/png_compression_level", 1, int))
    _restore_combo(window.output_format, window.preferences.value(
        "layout/output_format", "png", str))
    _restore_combo(window.png_engine, window.preferences.value(
        "layout/png_engine", "pillow", str))
    _load_label(window)
    _load_color_block(window)


def _load_label(window) -> None:
    label = window.label_settings
    label.sequence.setChecked(
        window.preferences.value("label/sequence_enabled", True, bool)
    )
    version = window.preferences.value("label/source_order_default_version", 0, int)
    if version < 1:
        label.source_order.setChecked(True)
        window.preferences.setValue("label/source_order_enabled", True)
        window.preferences.setValue("label/source_order_default_version", 1)
    else:
        label.source_order.setChecked(
            window.preferences.value("label/source_order_enabled", True, bool)
        )
    label.platform_enabled.setChecked(
        window.preferences.value("label/platform_enabled", True, bool)
    )
    label.platform_font_height.setValue(
        window.preferences.value("label/platform_font_height_mm", 6, float)
    )
    platform = window.preferences.value("label/platform_name", "隆丰", str).strip()
    if not platform or platform.casefold() == "蜂鸟":
        platform = "隆丰"
    if label.platform.findText(platform) < 0:
        label.platform.addItem(platform)
    label.platform.setCurrentText(platform)
    label.detect_region.setChecked(
        window.preferences.value("label/detect_region", True, bool)
    )
    label.fit_height.setChecked(
        window.preferences.value("label/fit_height", True, bool)
    )
    label.reference_height.setValue(
        window.preferences.value("label/reference_height_mm", 10, float)
    )
    label._sync_fit()
    _restore_combo(label.machine, window.preferences.value(
        "layout/machine_number", "M1", str).upper())
    label.follow_qr.setChecked(
        window.preferences.value("label/follow_qr", True, bool)
    )
    template = window.preferences.value("label/text_template", "", str)
    for old, new in {
        "{number}": "{编号}",
        "{date}": "{日期}",
        "{filename}": "{完整文件名}",
        "{stem}": "{文件名}",
    }.items():
        template = template.replace(old, new)
    label.text_template.setText(re.sub(r"_{2,}", "", template))
    _restore_combo(label.position, window.preferences.value(
        "label/position", "block_below", str))
    _restore_combo(label.cutter_vertical, window.preferences.value(
        "label/cutter_vertical_align", "top", str))
    _restore_combo(label.cutter_rotated, window.preferences.value(
        "label/cutter_rotated_align", "left", str))
    label._sync_position()
    for widget, key, default in (
        (label.font_size, "label/font_size_mm", 7.5 * 25.4 / 72),
        (label.gap, "label/gap_mm", 5),
        (label.offset_x, "label/offset_x_mm", 0),
        (label.offset_y, "label/offset_y_mm", 0),
    ):
        widget.setValue(window.preferences.value(key, default, float))
    label.date_format.setText(
        window.preferences.value("label/date_format", "%Y-%m-%d", str)
    )


def _load_color_block(window) -> None:
    block = window.color_block_settings
    block.enabled.setChecked(
        window.preferences.value("color_block/enabled", True, bool)
    )
    block.set_color(
        window.preferences.value("color_block/color", "#ff0000", str)
    )
    position = window.preferences.value("color_block/position", "left_top", str)
    position = {
        "top_left": "left_top",
        "top": "left_top",
        "top_right": "left_top",
        "bottom_left": "left_bottom",
        "bottom": "left_bottom",
        "bottom_right": "left_bottom",
        "right_top": "left_top",
        "right": "left",
        "right_bottom": "left_bottom",
    }.get(position, position)
    _restore_combo(block.position, position)
    for widget, key, default in (
        (block.width, "color_block/width_mm", 10),
        (block.height, "color_block/height_mm", 10),
        (block.gap, "color_block/gap_mm", 5),
        (block.offset_x, "color_block/offset_x_mm", 0),
        (block.offset_y, "color_block/offset_y_mm", 0),
    ):
        widget.setValue(window.preferences.value(key, default, float))


def _restore_combo(combo, value) -> None:
    combo.setCurrentIndex(max(0, combo.findData(value)))
