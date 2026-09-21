"""Entry points for choosing and starting a rolling multi-batch task."""
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from .folder_dialog_paths import image_dialog_start, remember_image_directory


def open_bulk(window):
    if window.has_active_tasks():
        return
    directory = QFileDialog.getExistingDirectory(
        window, '选择包含多个批次的上级目录', image_dialog_start(window),
    )
    if directory:
        start_bulk(window, Path(directory))


def start_bulk(window, directory, prepared_scan=None):
    directory = Path(directory)
    remember_image_directory(window, str(directory))
    from .quick_fields import show_selected_source
    show_selected_source(
        window.automation_home.label_quick_panel, str(directory), 'layout', window,
    )
    if not hasattr(window, 'bulk_controller'):
        from .bulk_workbench import BulkWorkbench
        window.bulk_controller = BulkWorkbench(window)
    if prepared_scan is None:
        window.bulk_controller.begin(directory)
    else:
        window.bulk_controller.begin(directory, prepared_scan)
