"""Compose the visible batch overview from its UI regions."""

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from ...action_icons import action_icon
from ...generation_panel import build_data_panel
from .label_controls import build_label_controls
from .preview import build_preview


class LabelQuickPanel(QWidget):
    """Main-page editing mirrors canonical settings instead of copying state."""

    def __init__(self, label, block, parent=None, window=None):
        super().__init__(parent)
        self.label = label
        form = build_label_controls(self, label, block, window)
        preview_group = build_preview(self, window, label, block)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        layout.addWidget(build_data_panel(window, self.summary, self.timings))
        layout.addWidget(self.summary.failure_panel)
        layout.addWidget(preview_group)
        self._build_developer_tools()

    def _build_developer_tools(self) -> None:
        self.history_button = _tool_button(
            "排版历史",
            "查看以往批次的膜方案、面积、占位率和耗时。",
            "more",
            self.details_dialog.open_history,
        )
        self.bulk_analysis_button = _tool_button(
            "批量分析文件夹…",
            "并行比较多个批次的研究膜规格，不生成打印文件。",
            "folder",
            self.details_dialog.open_bulk_analysis,
        )
        self.bulk_generation_button = _tool_button(
            "多批次排版…", "", "folder", self.details_dialog.open_bulk_generation
        )
        self.algorithm_costs_button = _tool_button(
            "算法诊断",
            "查看排版步骤的复杂度和实际耗时，仅用于开发检查。",
            "more",
            self.details_dialog.open_algorithm_costs,
        )
        self.cold_benchmark_button = _tool_button(
            "DTF随机10批冷启动测试…",
            "从 DTF 盘随机抽取10个HL批次，逐批生成并记录全部分阶段耗时。",
            "folder",
            self.details_dialog.open_cold_benchmark,
        )


def _tool_button(text, tooltip, icon, action):
    button = QPushButton(text)
    if tooltip:
        button.setToolTip(tooltip)
    button.setIcon(action_icon(icon))
    button.clicked.connect(action)
    return button
