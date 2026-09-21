"""Longfeng received-route generation controls and preview tables."""

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .pages import table_widget


def preview_row(table, index: int, values: tuple[str, ...]) -> None:
    for column, value in enumerate(values):
        table.setItem(index, column, QTableWidgetItem(value))


def show_orders(table, orders: tuple[tuple[str, int, int], ...]) -> None:
    table.setRowCount(len(orders))
    for index, (order_id, items, pieces) in enumerate(orders):
        preview_row(table, index, (order_id, str(items), str(pieces)))


def build_route_controls(owner) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    owner.route_summary = QLabel("隆丰：尚未读取工艺路线。")
    owner.route_summary.setWordWrap(True)
    owner.route_selector = QComboBox()
    owner.route_selector.setEnabled(False)
    owner.route_selector.currentIndexChanged.connect(
        owner.preview_process_route
    )
    owner.route_preview_button = QPushButton("读取工艺路线")
    owner.route_preview_button.clicked.connect(owner.preview_process_route)
    owner.route_generate_button = QPushButton("按筛选生成批次")
    owner.route_generate_button.setEnabled(False)
    owner.route_generate_button.clicked.connect(owner.confirm_process_route)
    route_actions = QHBoxLayout()
    route_actions.addWidget(owner.route_selector)
    route_actions.addWidget(owner.route_preview_button)
    route_actions.addWidget(owner.route_generate_button)
    layout.addWidget(owner.route_summary)
    layout.addLayout(route_actions)
    return panel


def build_route_page(owner) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    intro = QLabel("状态筛选：已接单。默认路线只选多项多件；其他工艺路线按所选路线读取。")
    intro.setWordWrap(True)
    layout.addWidget(intro)
    owner.default_multi_summary = QLabel("默认工艺路线 / 多项多件：尚未读取。")
    owner.default_multi_summary.setWordWrap(True)
    owner.default_multi_preview_button = QPushButton("读取默认路线多项多件")
    owner.default_multi_preview_button.clicked.connect(owner.preview_default_multi)
    owner.default_multi_generate_button = QPushButton("直接生成批次")
    owner.default_multi_generate_button.setEnabled(False)
    owner.default_multi_generate_button.clicked.connect(owner.confirm_default_multi)
    default_actions = QHBoxLayout()
    default_actions.addWidget(owner.default_multi_preview_button)
    default_actions.addWidget(owner.default_multi_generate_button)
    layout.addWidget(owner.default_multi_summary)
    layout.addLayout(default_actions)
    layout.addWidget(QLabel("其他工艺路线："))
    layout.addWidget(build_route_controls(owner))
    preview_note = QLabel(
        "候选批次预览：生成前可核对订单、项目和件数；平台可能自行拆批，"
        "实际批次号须在生成后从批次管理回查。"
    )
    preview_note.setWordWrap(True)
    owner.route_preview_table = table_widget(
        ["筛选条件", "订单", "项目", "件数", "状态"], 0
    )
    owner.route_preview_table.setRowCount(2)
    owner.route_preview_table.setMinimumHeight(118)
    preview_row(owner.route_preview_table, 0,
                ("默认路线 A00 / 多项多件", "—", "—", "—", "尚未读取"))
    preview_row(owner.route_preview_table, 1,
                ("其他工艺路线 / 全部组成", "—", "—", "—", "尚未读取"))
    layout.addWidget(preview_note)
    layout.addWidget(owner.route_preview_table)
    owner.candidate_orders_label = QLabel("候选订单明细：尚未读取。")
    owner.candidate_orders_table = table_widget(["订单 ID", "项目", "件数"], 0)
    owner.candidate_orders_table.setMaximumHeight(250)
    layout.addWidget(owner.candidate_orders_label)
    layout.addWidget(owner.candidate_orders_table)
    return page
