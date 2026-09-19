from __future__ import annotations
import json
import os

from ..layout_engine import LayoutSettings


def effective_worker_threads(configured):
    """Treat the legacy value 1 as automatic instead of accidental serial mode."""
    if configured > 1:
        return configured
    return max(1, min(4, os.cpu_count() or 4))


def settings_from_window(window) -> LayoutSettings:
    label = window.label_settings
    block = window.color_block_settings
    cutting=window.cutter_settings.mode.currentData()!='free'
    platform = label.platform.currentText().strip()
    if label.enabled.isChecked() and label.platform_enabled.isChecked():
        if not platform:
            raise ValueError('请填写实际生产平台名称。')
        if platform.casefold() == '蜂鸟':
            raise ValueError('蜂鸟是 ERP，不是生产平台；请填写实际平台名称。')
    return LayoutSettings(
        media_width_mm=window.cutter_settings.printable.effective_width(),
        compare_film_sizes=window.cutter_settings.compare_films.isChecked(),
        compare_reference_films=getattr(window, 'developer_mode_enabled', False),
        riin_left_mm=window.cutter_settings.printable.left.value(),
        riin_right_mm=window.cutter_settings.printable.right.value(),
        spacing_mm=window.spacing.value(),
        margin_mm=window.margin.value(),
        dpi=window.dpi.value(),
        follow_source_dpi=window.follow_source_dpi.isChecked(),
        output_format=(window.output_format.currentData()
                       if getattr(window, 'developer_mode_enabled', False)
                       and not cutting else 'png'),
        png_compression_level=window.png_compression.currentData(),
        png_engine=window.png_engine.currentData(),
        png_fast_encoding=False,
        png_streaming=window.segmented_output.fast_png.isChecked(),
        worker_threads=effective_worker_threads(window.worker_threads.value()),
        output_parts=window.segmented_output.parts.value(),
        save_parallelism=window.segmented_output.workers.value(),
        save_memory_mb=window.segmented_output.memory.value(),
        # The production UI no longer applies the legacy 512 MB concurrency budget.
        save_memory_unlimited=True,
        transition_lines=cutting and window.cutter_settings.transitions.enabled.isChecked(),
        batch_end_block=cutting and window.cutter_settings.transitions.end_block.isChecked(),
        transition_gap_mm=window.cutter_settings.transitions.gap.value(),
        transition_line_mm=window.cutter_settings.transitions.thickness.value(),
        batch_footer_enabled=window.cutter_settings.transitions.footer.isChecked(),
        batch_footer_font_mm=window.cutter_settings.transitions.footer_font.value(),
        rotation_marker_shift_mm=0,
        cutter_left_marker_external=cutting,
        cutter_compare_whole_rotation=True,
        cutter_knife_dots=False,
        cutter_single_row_rotation=True,
        preserve_header_gap=True,
        auto_fit_width=window.auto_fit_width.isChecked(),
        force_small_pair_width=window.cutter_settings.force_small_pair.isChecked(),
        force_small_pair_source_limit_mm=window.cutter_settings.force_small_pair_limit.value(),
        developer_gap_loss=True,
        developer_compact_cutter_layout=getattr(window, 'developer_mode_enabled', False),
        platform_below_marker=True,
        # Platform text belongs to the source label/QR card, never the cutter mark.
        # Preview and final output therefore always share the same embedded geometry.
        platform_reuse_qr=True,
        membrane_gap_mm=(window.membrane_gap.value() if cutting
                         and window.membrane_gap_enabled.isChecked() else 0),
        cutter_left_marker_lift_mm=window.cutter_settings.left_marker_lift.value(),
        cutter_knife_change_gap_mm=(window.cutter_settings.knife_change_gap.value()
                                    if getattr(window, 'developer_mode_enabled', False)
                                    and cutting else 0),
        allow_rotation=window.allow_rotation.isChecked() and not window.cutter_settings.quick_mode.isChecked(),
        rotation_direction=window.rotation_direction.currentData(),
        number_images=window.number_images.isChecked(),
        number_gap_mm=label.gap.value(),
        number_font_size_mm=label.font_size.value(),
        label_fit_height=label.fit_height.isChecked(),
        label_detect_region=label.detect_region.isChecked(),
        manual_rotations=tuple(json.loads(window.preferences.value("layout/manual_rotations", "{}", str)).items()),
        label_reference_height_mm=label.reference_height.value(),
        label_text_template=label.text_template.text(),
        label_sequence_enabled=label.sequence.isChecked(),
        label_source_order_enabled=(getattr(window, 'developer_mode_enabled', False)
                                    and label.source_order.isChecked()),
        label_machine_enabled=True,
        platform_name=platform if label.enabled.isChecked() and label.platform_enabled.isChecked() else '',
        # S2B is detected from its batch folder; order/color lookup is mandatory.
        s2b_batch_api_enabled=True,
        platform_font_height_mm=label.platform_font_height.value(),
        label_position='top_left' if not cutting and label.position.currentData()=='block_below' else label.position.currentData(),
        label_offset_x_mm=label.offset_x.value(),
        label_offset_y_mm=label.offset_y.value(),
        label_date_format=label.date_format.text().strip() or "%Y-%m-%d",
        label_follow_qr=label.follow_qr.isChecked(),
        color_block_enabled=cutting and block.enabled.isChecked(),
        color_block_color=block.color,
        color_block_width_mm=block.width.value(),
        color_block_height_mm=block.height.value(),
        color_block_position=block.position.currentData(),
        color_block_gap_mm=block.gap.value(),
        color_block_offset_x_mm=block.offset_x.value(),
        color_block_offset_y_mm=block.offset_y.value(),
        cutter_mode=window.cutter_settings.mode.currentData(),
        cutter_knife_mm=window.cutter_settings.knife.value(),
        cutter_auto_knife=window.cutter_settings.auto_knife.isChecked(),
        cutter_rotation_zone=window.cutter_settings.rotation_zone.isChecked() and not window.cutter_settings.quick_mode.isChecked(),
        cutter_majority_two_zone=window.cutter_settings.two_zone.isChecked(),
        cutter_tail_rotation=window.cutter_settings.tail_rotation.isChecked() and window.cutter_settings.mode.currentData() == 'dual',
        cutter_safety_mm=window.cutter_settings.safety.value(),
        cutter_marker_offset_mm=window.cutter_settings.marker_offset.value(),
        machine_number=label.machine.currentData(),
    )
