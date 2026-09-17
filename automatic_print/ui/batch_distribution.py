"""Compact batch composition placed directly above the matching preview."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class BatchDistributionLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setStyleSheet(
            'QLabel { background: #f0f7ff; color: #1e3a8a; '
            'border: 1px solid #bfdbfe; border-radius: 6px; padding: 7px; '
            'font-weight: bold; }'
        )
        self.reset()

    def reset(self):
        self.setText('尺码群 / 订单群：等待批次分析')
        self.setToolTip('')

    def show_report(self, report):
        if not report:
            self.reset()
            return
        from ..layout_engine.orders.batch_analysis import (
            compact_distribution_text, distribution_text, group_distribution,
        )
        distribution = report.get('group_distribution') or group_distribution(report)
        title = '尺码群' if distribution['kind'] == 'sizes' else '订单群'
        self.setText(f'{title}：{compact_distribution_text(report)}')
        self.setToolTip(distribution_text(report))
