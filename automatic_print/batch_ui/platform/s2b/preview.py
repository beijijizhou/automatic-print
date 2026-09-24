"""S2B read-only batch grouping preview page."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QPushButton, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..view.pages import table_widget
from ..view.strategy_editor import StrategyEditor
from ...task.reads import ReadWorker


class S2BPreviewPage(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        layout = QVBoxLayout(self)
        intro = QLabel(
            "读取 S2B 当前全部待排产生产项，并按下方组合模拟批次。"
            "本页仅预览，不调用创建批次接口，也不会修改 S2B 数据。"
        )
        intro.setWordWrap(True)
        self.strategy_editor = StrategyEditor(
            "S2B", getattr(owner, "preferences", None), self
        )
        self.read_button = QPushButton("读取待排产订单并模拟分组")
        self.read_button.clicked.connect(self.load)
        self.summary = QLabel("尚未读取。")
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.table = table_widget([
            "模拟组", "订单组成", "面别", "颜色", "尺码档", "底款",
            "物流", "订单数", "生产项", "件数", "订单号（可复制）",
        ], 10)
        warning = QLabel(
            "安全状态：仅使用待排产列表进行计算；页面没有生成按钮。"
            "规则变化后旧预览立即清空，整单始终进入同一个模拟组。"
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "padding:8px;background:#eef8ef;border:1px solid #79b77c;font-weight:600;"
        )
        for widget in (intro, self.strategy_editor, self.read_button,
                       self.summary, self.table, warning):
            layout.addWidget(widget)
        self.strategy_editor.changed.connect(self.invalidate)

    def invalidate(self, *_args) -> None:
        self.table.setRowCount(0)
        self.summary.setText("规则已变化，请重新读取并模拟分组。")

    def load(self) -> None:
        if self.owner.thread is not None:
            return
        self.table.setRowCount(0)
        self.summary.setText("正在读取 S2B 当前全部待排产生产项…")
        self.owner._start_worker(ReadWorker(
            "S2B", "s2b_preview", None,
            strategy=self.strategy_editor.strategy(),
        ))

    def show_result(self, result: dict) -> None:
        if (result.get("platform") != "S2B" or
                result.get("strategy") != self.strategy_editor.strategy()):
            return
        data = result["data"]
        groups = tuple(data.get("groups") or ())
        self.table.setRowCount(len(groups))
        for row, group in enumerate(groups):
            values = (
                str(row + 1), group.composition, group.face,
                group.color or "不分颜色", group.size_group or "不分尺码",
                group.style or "不按底款拆分", group.logistics or "不分物流",
                str(len(group.order_codes)), str(group.item_count),
                str(group.piece_count), ", ".join(group.order_codes),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        orders = sum(len(group.order_codes) for group in groups)
        items = sum(group.item_count for group in groups)
        pieces = sum(group.piece_count for group in groups)
        self.summary.setText(
            f"只读快照：{data['source_total']} 个待排产生产项；"
            f"按当前组合模拟 {len(groups)} 个批次，覆盖 {orders} 单 / "
            f"{items} 项 / {pieces} 件。未生成真实批次。"
        )

    def set_actions_enabled(self, enabled: bool) -> None:
        self.read_button.setEnabled(enabled)
        self.strategy_editor.setEnabled(enabled)
