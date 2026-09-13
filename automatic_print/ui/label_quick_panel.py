from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .pair_preview import PairProductionPreview
from .batch_analysis_panel import BatchAnalysisPanel
from .batch_summary import BatchSummaryPanel
from .operation_timing import OperationTimingPanel
from .manual_rotation import ManualRotationPanel
from .batch_details import BatchDetailsDialog
from ..layout_engine.labels import compact_label_text


class LabelQuickPanel(QWidget):
    """Main-page editing mirrors the canonical print settings, never a copy."""

    def __init__(self, label, block, parent=None, window=None):
        super().__init__(parent)
        self.label = label
        self.text = QLineEdit(label.text_template.text())
        self.text.setPlaceholderText("手动输入标签文字；机器号和序号自动显示")
        self.text.textChanged.connect(label.text_template.setText)
        label.text_template.textChanged.connect(self.text.setText)
        self.text.editingFinished.connect(
            lambda: self.text.setText(compact_label_text(self.text.text()))
        )
        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(label.font_size.minimum(), label.font_size.maximum())
        self.font_size.setDecimals(1)
        self.font_size.setValue(label.font_size.value())
        self.font_size.valueChanged.connect(label.font_size.setValue)
        label.font_size.valueChanged.connect(self.font_size.setValue)
        self.fit_height = self._checkbox("限制整段高度，字号不超过手动设置", label.fit_height)
        self.detect_region = self._checkbox("识别膜标签并动态等高适配", label.detect_region)
        self.reference_height = QDoubleSpinBox()
        self.reference_height.setRange(2, 100)
        self.reference_height.setDecimals(1)
        self.reference_height.setValue(label.reference_height.value())
        self.reference_height.valueChanged.connect(label.reference_height.setValue)
        label.reference_height.valueChanged.connect(self.reference_height.setValue)
        label.detect_region.toggled.connect(lambda value: self.reference_height.setEnabled(not value))
        self.reference_height.setEnabled(not label.detect_region.isChecked())
        label.detect_region.toggled.connect(lambda value: self.fit_height.setEnabled(not value))
        self.fit_height.setEnabled(not label.detect_region.isChecked())
        label.detect_region.toggled.connect(lambda value: self.font_size.setEnabled(not value))
        self.font_size.setEnabled(not label.detect_region.isChecked())
        self.enabled = self._checkbox("添加标签", label.enabled)
        self.follow_qr = self._checkbox("自动与二维码水平对齐", label.follow_qr)
        self.follow_qr.setEnabled(label.follow_qr.isEnabled())
        self.machine = QComboBox()
        for index in range(label.machine.count()):
            self.machine.addItem(label.machine.itemText(index), label.machine.itemData(index))
        self.machine.setCurrentIndex(label.machine.currentIndex())
        self.machine.currentIndexChanged.connect(label.machine.setCurrentIndex)
        label.machine.currentIndexChanged.connect(self.machine.setCurrentIndex)
        label.machine.currentIndexChanged.connect(
            lambda *_args: window.preferences.setValue("layout/machine_number", label.machine.currentData())
        )
        self.position = QComboBox()
        for index in range(label.position.count()):
            self.position.addItem(label.position.itemText(index), label.position.itemData(index))
        self.position.setCurrentIndex(label.position.currentIndex())
        self.position.currentIndexChanged.connect(label.position.setCurrentIndex)
        label.position.currentIndexChanged.connect(self.position.setCurrentIndex)
        self.position.currentIndexChanged.connect(
            lambda *_args: self.follow_qr.setEnabled(label.follow_qr.isEnabled())
        )
        date_button = QPushButton("添加日期")
        date_button.clicked.connect(self._add_date)
        text_row = QHBoxLayout()
        text_row.addWidget(self.text)
        text_row.addWidget(date_button)
        form = QFormLayout()
        form.addRow("标签与文字", text_row)
        self.sequence = self._checkbox('序号从 1 到最后一张', label.sequence)
        self.platform = QComboBox()
        self.platform.setEditable(True)
        for index in range(label.platform.count()):
            self.platform.addItem(label.platform.itemText(index))
        self.platform.setCurrentText(label.platform.currentText())
        self.platform.currentTextChanged.connect(label.platform.setCurrentText)
        label.platform.currentTextChanged.connect(self.platform.setCurrentText)
        self.platform.setStyleSheet('QComboBox { font-size: 20px; font-weight: bold; }')
        platform_row = QHBoxLayout()
        platform_row.addWidget(self.platform, 1)
        platform_row.addWidget(self.sequence)
        form.addRow('生产平台', platform_row)
        form.addRow("当前机器号", self.machine)
        # Advanced controls live in the canonical print-parameter dialogs.
        # Retain these mirrored objects for compatibility, never show duplicates.
        for control in (
            self.font_size, self.fit_height, self.detect_region,
            self.reference_height, self.position, self.enabled, self.follow_qr,
        ):
            control.setParent(self)
            control.hide()
        self.preview = PairProductionPreview(window._layout_settings, self)
        self.preview.overview = True
        self.analysis = BatchAnalysisPanel(self)
        self.details_dialog = BatchDetailsDialog(window)
        self.summary = BatchSummaryPanel(self)
        self.timings = OperationTimingPanel(window.worker_bridge, self)
        self.preview.loading_status.connect(self.summary.progress.setText)
        self.preview.plan_loaded.connect(self.summary.show_plan)
        self.preview.analysis_ready.connect(self.analysis.show_report)
        self.preview.analysis_ready.connect(self.summary.show_analysis)
        self.preview.analysis_failed.connect(self.analysis.failed)
        self.preview.analysis_started.connect(self.analysis.clear)
        self.preview.analysis_started.connect(lambda: self.summary.start(window.folder.text()))
        self.analysis.source_selected.connect(self._select_analysis_source)
        label.settings_changed.connect(self.preview.schedule_refresh)
        block.settings_changed.connect(self.preview.schedule_refresh)
        def folder_changed(folder):
            if window.cutter_settings.quick_mode.isChecked():
                self.summary.start(folder)
                self.preview.stage_folder(folder)
            else:
                self.preview.use_folder(folder)
        window.folder.textChanged.connect(folder_changed)
        def mode_changed(*_args):
            self.preview.auto_refresh_enabled = not window.cutter_settings.quick_mode.isChecked()
            folder_changed(window.folder.text())
        window.cutter_settings.quick_mode.toggled.connect(mode_changed)
        self.preview.auto_refresh_enabled = not window.cutter_settings.quick_mode.isChecked()
        window.dpi.valueChanged.connect(self.preview.schedule_refresh)
        cutter = window.cutter_settings
        for signal in (cutter.film.currentIndexChanged, cutter.mode.currentIndexChanged,
                       cutter.auto_knife.toggled,
                       cutter.rotation_zone.toggled,
                       cutter.knife.valueChanged, cutter.safety.valueChanged,
                       cutter.marker_offset.valueChanged, window.spacing.valueChanged):
            signal.connect(self.preview.schedule_refresh)
        for control in (cutter.printable.left, cutter.printable.right):
            control.valueChanged.connect(self.preview.schedule_refresh)
        group = QGroupBox("本批次真实预览 · 分区、刀位、标签与色块")
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setWidget(self.preview)
        self.preview_scroll.setMinimumHeight(300)
        self.preview_scroll.setMaximumHeight(520)
        QVBoxLayout(group).addWidget(self.preview_scroll)
        self.preview.detail = '尚未读取批次。选择文件夹或点击“读取当前文件夹”后开始。'
        self.summary.progress.setText('软件已就绪，未读取上次批次。')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        layout.addWidget(self.summary)
        layout.addWidget(group)
        from .generation_panel import build_generation_panel
        layout.addWidget(build_generation_panel(window))
        layout.addWidget(self.timings)
        self.manual_rotation = ManualRotationPanel(window, self.preview, self)
        overview = QCheckBox("显示整批总览（向下滚动查看全部；取消勾选查看双图细节）")
        overview.setChecked(True)
        overview.toggled.connect(self.preview.set_overview)
        layout.addWidget(overview)
        self.read_folder_button = QPushButton('读取当前文件夹（使用上次路径）')
        self.read_folder_button.clicked.connect(lambda: self.preview.use_folder(window.folder.text()))
        stop_preview = QPushButton('停止后台预览计算')
        stop_preview.clicked.connect(self.preview.stop_loading)
        self.details_dialog.add_page('订单与尺码', [self.analysis])
        self.details_dialog.add_page('图片检查与旋转', [
            self.manual_rotation, self.read_folder_button, stop_preview,
        ])
        self.summary.layout().removeWidget(self.summary.cutting)
        self.summary.cutting.setMaximumHeight(16777215)
        self.details_dialog.add_page('切割明细', [self.summary.cutting])
        self.details_button = QPushButton('批次详情与检查…')
        self.details_button.clicked.connect(self.details_dialog.open_details)

    def _select_analysis_source(self, path):
        combo = self.manual_rotation.images
        index = combo.findData(str(Path(path).resolve()))
        if index >= 0:
            combo.setCurrentIndex(index)

    def _add_date(self):
        if "{日期}" not in self.text.text():
            self.text.setText(self.text.text().rstrip() + "－{日期}")

    @staticmethod
    def _checkbox(text, source):
        checkbox = QCheckBox(text)
        checkbox.setChecked(source.isChecked())
        checkbox.toggled.connect(source.setChecked)
        source.toggled.connect(checkbox.setChecked)
        return checkbox
