"""Build the batch result, preview and inspection regions."""

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...batch_analysis_panel import BatchAnalysisPanel
from ...batch_details import BatchDetailsDialog
from ...batch_distribution import BatchDistributionLabel
from ...batch_summary import BatchSummaryPanel
from ...manual_rotation import ManualRotationPanel
from ...previews.markers import MarkerExamples
from ...operation_timing import OperationTimingPanel
from ...pair_preview import PairProductionPreview
from ...preview_viewport import PreviewViewport
from .bindings import bind_overview


def build_preview(panel, window, label, block):
    panel.preview = PairProductionPreview(window._layout_settings, panel)
    panel.preview.overview = True
    panel.analysis = BatchAnalysisPanel(panel)
    panel.details_dialog = BatchDetailsDialog(window)
    panel.summary = BatchSummaryPanel(panel)
    panel.timings = OperationTimingPanel(window.worker_bridge, panel)
    panel.timings.save_report_provider = lambda: panel.summary.save_report
    panel.batch_distribution = BatchDistributionLabel(panel)

    group = QGroupBox("本批次排版预览 · 默认显示轻量订单结构")
    panel.preview_scroll = QScrollArea()
    panel.preview_scroll.setWidgetResizable(True)
    panel.preview_scroll.setWidget(panel.preview)
    panel.preview_scroll.setMinimumHeight(420)
    panel.preview_scroll.setMaximumHeight(720)
    panel.preview_viewport = PreviewViewport(panel.preview, panel.preview_scroll)
    preview_layout = QVBoxLayout(group)
    panel.marker_examples = MarkerExamples(window, panel)
    panel.preview_tabs = QTabWidget()
    panel.actual_preview_page = QWidget()
    QVBoxLayout(panel.actual_preview_page).addWidget(panel.preview_viewport)
    panel.preview_tabs.addTab(panel.actual_preview_page, "排版结构 / 真实图片")
    panel.preview_tabs.addTab(panel.marker_examples, "刀码四种情况")
    panel.preview_tabs.setCurrentIndex(0)
    preview_layout.addWidget(panel.batch_distribution)
    preview_layout.addWidget(panel.preview_tabs)
    panel.preview.detail = "尚未读取批次。选择文件夹或点击“读取当前文件夹”后开始。"
    panel.summary.progress.setText("软件已就绪，未读取上次批次。")

    panel.manual_rotation = ManualRotationPanel(window, panel.preview, panel)
    overview = QCheckBox(
        "显示整批轻量结构图（不读取缩略图；取消后查看当前订单真实图片）"
    )
    overview.toggled.connect(panel.preview.set_overview)
    overview.setChecked(True)
    preview_layout.addWidget(overview)
    panel.read_folder_button = QPushButton("读取当前文件夹（使用上次路径）")
    panel.read_folder_button.clicked.connect(
        lambda: panel.preview.use_folder(window.folder.text())
    )
    stop_preview = QPushButton("停止后台预览计算")
    stop_preview.clicked.connect(panel.preview.stop_loading)
    panel.summary.layout().removeWidget(panel.summary.cutting)
    panel.summary.cutting.setMaximumHeight(16777215)
    for internal in (
        panel.analysis,
        panel.manual_rotation,
        panel.read_folder_button,
        stop_preview,
        panel.summary.cutting,
    ):
        internal.hide()
    bind_overview(panel, window, label, block)
    return group
