import re
from PySide6.QtWidgets import QMessageBox
from .preference_actions import PreferenceActionsMixin

class PreferencesMixin(PreferenceActionsMixin):
    def load_layout_preferences(self) -> None:
        from .spacing_settings import migrate_spacing
        migrate_spacing(self.preferences)
        values = (
            (self.width, "layout/media_width_mm", 600, float),
            (self.spacing, "layout/spacing_mm", 8, float),
            (self.margin, "layout/margin_mm", 3, float),
            (self.dpi, "layout/dpi", 300, int),
            (self.worker_threads, "layout/worker_threads", 4, int),
        )
        for widget, key, default, value_type in values:
            widget.setValue(self.preferences.value(key, default, value_type))
        self.number_images.setChecked(
            self.preferences.value("layout/number_images",
                self.preferences.value('label/enabled', True, bool), bool)
        )
        self.allow_rotation.setChecked(
            self.preferences.value("layout/allow_rotation", True, bool)
        )
        direction = self.preferences.value(
            "layout/rotation_direction", "left", str
        )
        self.rotation_direction.setCurrentIndex(
            max(0, self.rotation_direction.findData(direction))
        )
        compression = self.preferences.value(
            "layout/png_compression_level", 1, int
        )
        self.png_compression.setCurrentIndex(
            max(0, self.png_compression.findData(compression))
        )
        output_format = self.preferences.value(
            "layout/output_format", "png", str
        )
        self.output_format.setCurrentIndex(
            max(0, self.output_format.findData(output_format))
        )
        engine = self.preferences.value(
            "layout/png_engine", "pillow", str
        )
        self.png_engine.setCurrentIndex(
            max(0, self.png_engine.findData(engine))
        )
        label = self.label_settings
        label.sequence.setChecked(self.preferences.value('label/sequence_enabled', True, bool))
        source_order_default = self.preferences.value(
            'label/source_order_default_version', 0, int)
        if source_order_default < 1:
            label.source_order.setChecked(True)
            self.preferences.setValue('label/source_order_enabled', True)
            self.preferences.setValue('label/source_order_default_version', 1)
        else:
            label.source_order.setChecked(
                self.preferences.value('label/source_order_enabled', True, bool))
        label.platform_enabled.setChecked(self.preferences.value('label/platform_enabled', True, bool))
        label.platform_font_height.setValue(self.preferences.value('label/platform_font_height_mm', 6, float))
        platform = self.preferences.value('label/platform_name', '隆丰', str).strip()
        if not platform or platform.casefold() in {'蜂鸟', 'haloo'}:
            platform = '隆丰'
        if label.platform.findText(platform) < 0:
            label.platform.addItem(platform)
        label.platform.setCurrentText(platform)
        label.detect_region.setChecked(self.preferences.value("label/detect_region", True, bool))
        label.fit_height.setChecked(self.preferences.value("label/fit_height", True, bool))
        label.reference_height.setValue(self.preferences.value("label/reference_height_mm", 10, float))
        label._sync_fit()
        label.machine.setCurrentIndex(max(0, label.machine.findData(
            self.preferences.value("layout/machine_number", "M1", str).upper()
        )))
        label.follow_qr.setChecked(
            self.preferences.value("label/follow_qr", True, bool)
        )
        template = self.preferences.value(
            "label/text_template", "", str
        )
        aliases = {
            "{number}": "{编号}",
            "{date}": "{日期}",
            "{filename}": "{完整文件名}",
            "{stem}": "{文件名}",
        }
        for old, new in aliases.items():
            template = template.replace(old, new)
        template = re.sub(r"_{2,}", "", template)
        label.text_template.setText(template)
        position = self.preferences.value(
            "label/position", "block_below", str
        )
        label.position.setCurrentIndex(
            max(0, label.position.findData(position))
        )
        label._sync_position()
        for widget, key, default in (
            (label.font_size, "label/font_size_mm", 7.5 * 25.4 / 72),
            (label.gap, "label/gap_mm", 5),
            (label.offset_x, "label/offset_x_mm", 0),
            (label.offset_y, "label/offset_y_mm", 0),
        ):
            widget.setValue(self.preferences.value(key, default, float))
        label.date_format.setText(
            self.preferences.value(
                "label/date_format", "%Y-%m-%d", str
            )
        )
        block = self.color_block_settings
        block.enabled.setChecked(
            self.preferences.value("color_block/enabled", True, bool)
        )
        block.set_color(
            self.preferences.value("color_block/color", "#ff0000", str)
        )
        position = self.preferences.value(
            "color_block/position", "left_top", str
        )
        legacy_positions = {
            "top_left": "left_top",
            "top": "left_top",
            "top_right": "left_top",
            "bottom_left": "left_bottom",
            "bottom": "left_bottom",
            "bottom_right": "left_bottom",
            "right_top": "left_top",
            "right": "left",
            "right_bottom": "left_bottom",
        }
        position = legacy_positions.get(position, position)
        block.position.setCurrentIndex(
            max(0, block.position.findData(position))
        )
        for widget, key, default in (
            (block.width, "color_block/width_mm", 10),
            (block.height, "color_block/height_mm", 10),
            (block.gap, "color_block/gap_mm", 5),
            (block.offset_x, "color_block/offset_x_mm", 0),
            (block.offset_y, "color_block/offset_y_mm", 0),
        ):
            widget.setValue(self.preferences.value(key, default, float))

    def save_layout_preferences(self, *_args, notify=True) -> None:
        self.cutter_settings.save()
        label = self.label_settings
        values = {
            "source_location": self.folder.text().strip(),
            "output_location": self.output_location.text().strip(),
            "output/beside_source": self.output_beside_source.isChecked(),
            "output/custom_location": self.custom_output_location,
            "automation/output_location": self.automation_home.output.text().strip(),
            "local/test_mode": self.automation_home.local_test_mode.isChecked(),
            "local/merge_batches": self.automation_home.local_merge_batches.isChecked(),
            "layout/media_width_mm": self.width.value(),
            "layout/spacing_mm": self.spacing.value(),
            "layout/margin_mm": self.margin.value(),
            "layout/dpi": self.dpi.value(),
            "layout/worker_threads": self.worker_threads.value(),
            "layout/preview_only": self.automation_home.preview_only.isChecked(),
            "layout/combine_bulk_batches": self.combine_bulk_batches.isChecked(),
            "developer/bulk_parallelism": self.bulk_parallelism.value(),
            "layout/number_images": self.number_images.isChecked(),
            "layout/allow_rotation": self.allow_rotation.isChecked(),
            "layout/rotation_direction":
                self.rotation_direction.currentData(),
            "layout/png_compression_level": self.png_compression.currentData(),
            "layout/output_format": self.output_format.currentData(),
            "layout/png_engine": self.png_engine.currentData(),
            "label/text_template": label.text_template.text(),
            'label/sequence_enabled': label.sequence.isChecked(),
            'label/source_order_enabled': label.source_order.isChecked(),
            'label/platform_name': label.platform.currentText(),
            'label/platform_enabled': label.platform_enabled.isChecked(),
            'label/platform_font_height_mm': label.platform_font_height.value(),
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
            "label/date_format": label.date_format.text().strip()
            or "%Y-%m-%d",
            "color_block/enabled":
                self.color_block_settings.enabled.isChecked(),
            "color_block/color": self.color_block_settings.color,
            "color_block/width_mm": self.color_block_settings.width.value(),
            "color_block/height_mm": self.color_block_settings.height.value(),
            "color_block/position":
                self.color_block_settings.position.currentData(),
            "color_block/gap_mm": self.color_block_settings.gap.value(),
            "color_block/offset_x_mm":
                self.color_block_settings.offset_x.value(),
            "color_block/offset_y_mm":
                self.color_block_settings.offset_y.value(),
        }
        for key, value in values.items():
            self.preferences.setValue(key, value)
        self.preferences.sync()
        if notify:
            QMessageBox.information(self, "参数已保存",
                "参数已立即生效，可以继续排版，无需重启；下次打开也会自动恢复。")
