from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from ..layout import discover_images


class PreferencesMixin:
    def choose_folder(self) -> None:
        start = self.folder.text().strip()
        if not Path(start).is_dir():
            start = self.preferences.value("source_location", "", str)
        folder = QFileDialog.getExistingDirectory(
            self, "请选择包含图片的文件夹（无需选择单张图片）", start
        )
        if folder:
            self.folder.setText(folder)
            self.preferences.setValue("source_location", folder)
            count = len(discover_images(Path(folder)))
            self.status.setText(f"已找到 {count} 张图片，可以开始生成。")

    def choose_output_location(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "请选择打印任务的保存位置",
            self.output_location.text().strip(),
        )
        if folder:
            self.output_location.setText(folder)
            self.preferences.setValue("output_location", folder)

    def open_settings_dialog(self) -> None:
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def load_layout_preferences(self) -> None:
        values = (
            (self.width, "layout/media_width_mm", 600, float),
            (self.spacing, "layout/spacing_mm", 3, float),
            (self.margin, "layout/margin_mm", 3, float),
            (self.dpi, "layout/dpi", 300, int),
            (self.worker_threads, "layout/worker_threads", 8, int),
        )
        for widget, key, default, value_type in values:
            widget.setValue(self.preferences.value(key, default, value_type))
        self.number_images.setChecked(
            self.preferences.value("layout/number_images", True, bool)
        )
        compression = self.preferences.value(
            "layout/png_compression_level", 1, int
        )
        self.png_compression.setCurrentIndex(
            max(0, self.png_compression.findData(compression))
        )
        engine = self.preferences.value(
            "layout/png_engine", "pillow", str
        )
        self.png_engine.setCurrentIndex(
            max(0, self.png_engine.findData(engine))
        )
        label = self.label_settings
        template = self.preferences.value(
            "label/text_template", "{编号}", str
        )
        aliases = {
            "{number}": "{编号}",
            "{date}": "{日期}",
            "{filename}": "{完整文件名}",
            "{stem}": "{文件名}",
        }
        for old, new in aliases.items():
            template = template.replace(old, new)
        label.text_template.setText(template)
        position = self.preferences.value(
            "label/position", "bottom", str
        )
        label.position.setCurrentIndex(
            max(0, label.position.findData(position))
        )
        for widget, key, default in (
            (label.font_size, "label/font_size_mm", 10),
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

    def save_layout_preferences(self) -> None:
        label = self.label_settings
        values = {
            "layout/media_width_mm": self.width.value(),
            "layout/spacing_mm": self.spacing.value(),
            "layout/margin_mm": self.margin.value(),
            "layout/dpi": self.dpi.value(),
            "layout/worker_threads": self.worker_threads.value(),
            "layout/number_images": self.number_images.isChecked(),
            "layout/png_compression_level": self.png_compression.currentData(),
            "layout/png_engine": self.png_engine.currentData(),
            "label/text_template": label.text_template.text(),
            "label/position": label.position.currentData(),
            "label/font_size_mm": label.font_size.value(),
            "label/gap_mm": label.gap.value(),
            "label/offset_x_mm": label.offset_x.value(),
            "label/offset_y_mm": label.offset_y.value(),
            "label/date_format": label.date_format.text().strip()
            or "%Y-%m-%d",
        }
        for key, value in values.items():
            self.preferences.setValue(key, value)
        self.preferences.sync()
        QMessageBox.information(
            self,
            "参数已保存",
            "以后下载生产批次后，会自动使用这些参数排版。",
        )
