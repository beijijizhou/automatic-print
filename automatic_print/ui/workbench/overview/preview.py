"""Build the batch result, preview and inspection regions."""

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QFontDatabase

from ...batch_analysis_panel import BatchAnalysisPanel
from ...batch_details import BatchDetailsDialog
from ...batch_distribution import BatchDistributionLabel
from ...batch_summary import BatchSummaryPanel
from ...manual_rotation import ManualRotationPanel
from ...previews.markers import MarkerExamples
from ...operation_timing import OperationTimingPanel
from ...pair_preview import PairProductionPreview
from ...previews.runtime.viewport import PreviewViewport
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

    group = QGroupBox("预览检查 · 标签刀码与批次排版相互独立")
    panel.preview_group = group
    panel.preview_scroll = QScrollArea()
    panel.preview_scroll.setWidgetResizable(True)
    panel.preview_scroll.setWidget(panel.preview)
    panel.preview_scroll.setMinimumHeight(420)
    panel.preview_scroll.setMaximumHeight(460)
    panel.preview_viewport = PreviewViewport(panel.preview, panel.preview_scroll)
    preview_layout = QVBoxLayout(group)
    panel.preview_empty = QLabel(
        "尚未选择批次。选择图片文件夹后，这里再展开文字、标签刀码和批次排版预览。"
    )
    panel.preview_empty.setWordWrap(True)
    panel.marker_examples = MarkerExamples(window, panel)
    panel.preview_tabs = QTabWidget()
    panel.text_preview = QPlainTextEdit()
    panel.text_preview.setReadOnly(True)
    # The text layout uses fixed-width left/right columns. Wrapping turns a
    # genuine two-column plan into a misleading vertical size list.
    panel.text_preview.setLineWrapMode(QPlainTextEdit.NoWrap)
    text_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    text_font.setPointSize(max(12, text_font.pointSize()))
    panel.text_preview.setFont(text_font)
    panel.text_preview.setPlainText('等待读取批次文件名…')
    text_page = QWidget()
    text_layout = QVBoxLayout(text_page)
    copy_text = QPushButton('复制文字预览')
    copy_text.setMaximumWidth(160)
    copy_text.clicked.connect(
        lambda: QApplication.clipboard().setText(panel.text_preview.toPlainText()))
    text_layout.addWidget(copy_text)
    text_layout.addWidget(panel.text_preview)
    panel.actual_preview_page = QWidget()
    QVBoxLayout(panel.actual_preview_page).addWidget(panel.preview_viewport)
    panel.preview_tabs.addTab(text_page, '文字排版预览（默认）')
    panel.preview_tabs.addTab(panel.marker_examples, "标签与刀码位置")
    panel.preview_tabs.addTab(panel.actual_preview_page, "批次排版预览")
    panel.preview_tabs.setCurrentIndex(0)
    preview_layout.addWidget(panel.batch_distribution)
    preview_layout.addWidget(panel.preview_empty)
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
    def show_preview_content(visible=True):
        visible = bool(visible)
        group.setMaximumHeight(560 if visible else 96)
        panel.preview_empty.setVisible(not visible)
        panel.batch_distribution.setVisible(visible)
        panel.preview_tabs.setVisible(visible)
        overview.setVisible(
            visible and panel.preview_tabs.currentWidget() is panel.actual_preview_page
        )

    panel.show_preview_content = show_preview_content
    panel.preview.analysis_started.connect(show_preview_content)
    panel.preview.analysis_ready.connect(show_preview_content)
    panel.preview.plan_loaded.connect(show_preview_content)
    window.folder.textChanged.connect(
        lambda folder: show_preview_content(False) if not folder.strip() else None
    )
    panel.preview_tabs.currentChanged.connect(
        lambda *_: show_preview_content(panel.preview_tabs.isVisible()))
    show_preview_content(False)
    panel.read_folder_button = QPushButton("读取当前文件夹（使用上次路径）")
    panel.read_folder_button.clicked.connect(
        lambda: panel.preview.use_folder(window.folder.text())
    )
    stop_preview = QPushButton("停止后台预览计算")
    stop_preview.clicked.connect(panel.preview.stop_loading)
    panel.summary.inline_cutting = False
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
