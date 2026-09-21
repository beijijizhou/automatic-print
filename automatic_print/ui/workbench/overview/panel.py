"""Compose the visible batch overview from its UI regions."""

from PySide6.QtWidgets import QMenu, QPushButton, QToolButton, QVBoxLayout, QWidget

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
        layout.addWidget(self.order_side_control)
        layout.addWidget(build_data_panel(window, self.summary, self.timings))
        layout.insertWidget(1, window.batch_status_board)
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
        self.bulk_generation_button = _tool_button(
            "多批次排版…", "", "folder", self.details_dialog.open_bulk_generation
        )
        self.test_tools_button = QToolButton(self)
        self.test_tools_button.setText('测试与诊断…')
        self.test_tools_button.setIcon(action_icon('more'))
        self.test_tools_button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.test_tools_button)
        for label, action in (
            ('标签位置安全短测…', self.details_dialog.open_label_position_test),
            ('DTF随机10批冷启动测试…', self.details_dialog.open_cold_benchmark),
            ('批量分析文件夹…', self.details_dialog.open_bulk_analysis),
            ('算法诊断', self.details_dialog.open_algorithm_costs),
        ):
            menu.addAction(label, action)
        self.test_tools_button.setMenu(menu)


def _tool_button(text, tooltip, icon, action):
    button = QPushButton(text)
    if tooltip:
        button.setToolTip(tooltip)
    button.setIcon(action_icon(icon))
    button.clicked.connect(action)
    return button
