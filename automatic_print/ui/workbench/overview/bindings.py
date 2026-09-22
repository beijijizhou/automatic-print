"""Signal wiring between overview widgets and canonical workbench state."""

from pathlib import Path
from PySide6.QtCore import QTimer


def bind_overview(panel, window, label, block) -> None:
    preview = panel.preview
    from ...previews.text_layout import inventory_text, layout_text
    preview.analysis_ready.connect(
        lambda report: panel.text_preview.setPlainText(inventory_text(report)))
    preview.plan_loaded.connect(
        lambda payload: panel.text_preview.setPlainText(layout_text(payload)))
    preview.analysis_started.connect(
        lambda: panel.text_preview.setPlainText('正在读取文件名并准备文字预览…'))
    preview.loading_status.connect(panel.summary.progress.setText)
    preview.plan_loaded.connect(panel.summary.show_plan)
    preview.analysis_ready.connect(panel.analysis.show_report)
    preview.analysis_ready.connect(panel.summary.show_analysis)
    preview.analysis_ready.connect(panel.batch_distribution.show_report)
    preview.analysis_failed.connect(panel.analysis.failed)
    preview.analysis_failed.connect(panel.summary.show_failure)
    preview.analysis_started.connect(panel.analysis.clear)
    preview.analysis_started.connect(panel.batch_distribution.reset)
    preview.analysis_started.connect(lambda: panel.summary.start(window.folder.text()))
    panel.analysis.source_selected.connect(
        lambda path: _select_analysis_source(panel, path)
    )
    label.settings_changed.connect(preview.invalidate_parameters)

    def refresh_platform_font(*_args):
        if preview.batch_payload and not preview.production_active:
            preview.invalidate_parameters()

    label.platform_font_height.valueChanged.connect(refresh_platform_font)
    window.cutter_settings.left_marker_lift.valueChanged.connect(refresh_platform_font)
    transitions = window.cutter_settings.transitions
    for signal in (
        transitions.enabled.toggled,
        transitions.end_block.toggled,
        transitions.footer.toggled,
        transitions.gap.valueChanged,
        transitions.thickness.valueChanged,
        transitions.footer_font.valueChanged,
    ):
        signal.connect(refresh_platform_font)
    block.settings_changed.connect(preview.invalidate_parameters)

    def folder_changed(folder):
        if window.cutter_settings.quick_mode.isChecked():
            panel.summary.start(folder)
            preview.stage_folder(folder)
        else:
            preview.use_folder(folder)

    window.folder.textChanged.connect(folder_changed)
    saved_folder = window.folder.text()
    QTimer.singleShot(
        0, lambda: preview.stage_folder(saved_folder)
        if saved_folder.strip() and window.folder.text() == saved_folder else None)

    def mode_changed(*_args):
        preview.auto_refresh_enabled = not window.cutter_settings.quick_mode.isChecked()
        if not getattr(preview, "parameter_refresh_deferred", 0):
            folder_changed(window.folder.text())

    window.cutter_settings.quick_mode.toggled.connect(mode_changed)
    preview.auto_refresh_enabled = not window.cutter_settings.quick_mode.isChecked()
    for signal in (
        window.dpi.valueChanged,
        window.follow_source_dpi.toggled,
        window.membrane_gap_enabled.toggled,
        window.membrane_gap.valueChanged,
        window.auto_fit_width.toggled,
    ):
        signal.connect(preview.invalidate_parameters)
    cutter = window.cutter_settings
    for signal in (
        cutter.film.currentIndexChanged,
        cutter.mode.currentIndexChanged,
        cutter.auto_knife.toggled,
        cutter.rotation_zone.toggled,
        cutter.two_zone.toggled,
        cutter.knife.valueChanged,
        cutter.safety.valueChanged,
        cutter.marker_offset.valueChanged,
        cutter.left_marker_lift.valueChanged,
        window.spacing.valueChanged,
    ):
        signal.connect(preview.invalidate_parameters)
    for control in (cutter.printable.left, cutter.printable.right):
        control.valueChanged.connect(preview.invalidate_parameters)


def _select_analysis_source(panel, path) -> None:
    combo = panel.manual_rotation.images
    index = combo.findData(str(Path(path).resolve()))
    if index >= 0:
        combo.setCurrentIndex(index)
