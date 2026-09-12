from __future__ import annotations

from ..layout import LayoutSettings


def settings_from_window(window) -> LayoutSettings:
    label = window.label_settings
    block = window.color_block_settings
    return LayoutSettings(
        media_width_mm=window.width.value(),
        spacing_mm=window.spacing.value(),
        margin_mm=window.margin.value(),
        dpi=window.dpi.value(),
        png_compression_level=window.png_compression.currentData(),
        png_engine=window.png_engine.currentData(),
        worker_threads=window.worker_threads.value(),
        allow_rotation=window.allow_rotation.isChecked(),
        rotation_direction=window.rotation_direction.currentData(),
        number_images=window.number_images.isChecked(),
        number_gap_mm=label.gap.value(),
        number_font_size_mm=label.font_size.value(),
        label_text_template=label.text_template.text(),
        label_position=label.position.currentData(),
        label_offset_x_mm=label.offset_x.value(),
        label_offset_y_mm=label.offset_y.value(),
        label_date_format=label.date_format.text().strip() or "%Y-%m-%d",
        label_follow_qr=label.follow_qr.isChecked(),
        color_block_enabled=block.enabled.isChecked(),
        color_block_color=block.color,
        color_block_width_mm=block.width.value(),
        color_block_height_mm=block.height.value(),
        color_block_position=block.position.currentData(),
        color_block_gap_mm=block.gap.value(),
        color_block_offset_x_mm=block.offset_x.value(),
        color_block_offset_y_mm=block.offset_y.value(),
    )
