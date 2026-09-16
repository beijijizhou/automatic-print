"""Folder and settings-window actions shared by the preferences mixin."""
from PySide6.QtWidgets import QFileDialog


class PreferenceActionsMixin:
    def choose_and_generate(self):
        if self.has_active_tasks():
            return
        if self.choose_folder():
            self.generate(preview_only=self.automation_home.preview_only.isChecked())

    def build_reset_button(self):
        from .settings_reset import reset_button
        return reset_button(self)

    def choose_folder(self) -> bool:
        from .folder_dialog_paths import image_dialog_start, remember_image_directory
        folder = QFileDialog.getExistingDirectory(
            self, "请选择包含图片的文件夹（无需选择单张图片）", image_dialog_start(self))
        if not folder:
            return False
        remember_image_directory(self, folder)
        from ..layout_engine.platform_detection import detect_selected_platform
        platform = detect_selected_platform(folder)
        if platform:
            self.label_settings.platform.setCurrentText(platform)
        unchanged = self.folder.text() == folder
        self.folder.setText(folder)
        from .quick_fields import show_selected_source
        show_selected_source(self.automation_home.label_quick_panel, folder, window=self)
        if unchanged:
            preview = self.generation_preview.preview
            (preview.stage_folder if self.cutter_settings.quick_mode.isChecked()
             else preview.use_folder)(folder)
        self.preferences.setValue("source_location", folder)
        status = ('已选择文件夹，点击开始排版统一读取和处理。'
                  if self.cutter_settings.quick_mode.isChecked()
                  else '已选择文件夹，正在后台读取图片名称和批次信息…')
        self.status.setText(status)
        return True

    def choose_output_location(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "请选择打印任务的保存位置", self.output_location.text().strip())
        if folder:
            self.output_location.setText(folder)
            self.preferences.setValue("output_location", folder)

    def open_settings_dialog(self) -> None:
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()
