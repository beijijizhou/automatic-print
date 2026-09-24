"""Persist the canonical print controls as one settings transaction."""

from PySide6.QtWidgets import QMessageBox

def save_layout_preferences(window, *, notify=True) -> None:
    window.cutter_settings.save()
    label = window.label_settings
    values = {
        "source_location": window.folder.text().strip(),
        "output_location": window.output_location.text().strip(),
        "output/beside_source": window.output_beside_source.isChecked(),
        "output/custom_location": window.custom_output_location,
        "automation/output_location": window.automation_home.output.text().strip(),
        "local/test_mode": window.automation_home.local_test_mode.isChecked(),
        "local/merge_batches": window.automation_home.local_merge_batches.isChecked(),
        "layout/media_width_mm": window.width.value(),
        "layout/spacing_mm": window.spacing.value(),
        "layout/margin_mm": window.margin.value(),
        "layout/dpi": window.dpi.value(),
        "layout/worker_threads": window.worker_threads.value(),
        "layout/preview_only": window.automation_home.preview_only.isChecked(),
        "layout/combine_bulk_batches": window.combine_bulk_batches.isChecked(),
        "developer/bulk_parallelism": window.bulk_parallelism.value(),
        "layout/number_images": window.number_images.isChecked(),
        "layout/allow_rotation": window.allow_rotation.isChecked(),
        "layout/rotation_direction": window.rotation_direction.currentData(),
        "layout/png_compression_level": window.png_compression.currentData(),
        "layout/output_format": window.output_format.currentData(),
        "layout/png_engine": window.png_engine.currentData(),
        "label/text_template": label.text_template.text(),
        "label/sequence_enabled": label.sequence.isChecked(),
        "label/source_order_enabled": label.source_order.isChecked(),
        "label/platform_name": label.platform.currentText(),
        "label/platform_enabled": label.platform_enabled.isChecked(),
        "label/platform_font_height_mm": label.platform_font_height.value(),
        "layout/machine_number": label.machine.currentData(),
        "label/follow_qr": label.follow_qr.isChecked(),
        "label/position": label.position.currentData(),
        "label/font_size_mm": label.font_size.value(),
        "label/fit_height": label.fit_height.isChecked(),
        "label/detect_region": label.detect_region.isChecked(),
        "label/reference_height_mm": label.reference_height.value(),
        "label/gap_mm": label.gap.value(),
        "label/offset_x_mm": label.offset_x.value(),
        "label/offset_y_mm": label.offset_y.value(),
        "label/date_format": label.date_format.text().strip() or "%Y-%m-%d",
        "color_block/enabled": window.color_block_settings.enabled.isChecked(),
        "color_block/color": window.color_block_settings.color,
        "color_block/width_mm": window.color_block_settings.width.value(),
        "color_block/height_mm": window.color_block_settings.height.value(),
        "color_block/position": window.color_block_settings.position.currentData(),
        "color_block/gap_mm": window.color_block_settings.gap.value(),
        "color_block/offset_x_mm": window.color_block_settings.offset_x.value(),
        "color_block/offset_y_mm": window.color_block_settings.offset_y.value(),
    }
    for key, value in values.items():
        window.preferences.setValue(key, value)
    window.preferences.sync()
    if notify:
        QMessageBox.information(
            window,
            "参数已保存",
            "参数已立即生效，可以继续排版，无需重启；下次打开也会自动恢复。",
        )
