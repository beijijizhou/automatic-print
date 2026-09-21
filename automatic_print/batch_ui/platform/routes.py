"""Received-item process route controls for Longfeng."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
    QWidget,
)

from ...automation.batches.routes import RouteBatchPlan
from ...automation.batches.default_multi import DefaultMultiPlan
from ..task.worker import AutomationWorker


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
    intro = QLabel("隆丰已接单可按默认工艺路线＋多项多件直接生成批次。")
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
    layout.addStretch()
    return page


class RouteActionsMixin:
    def show_route_controls(self, platform_name: str) -> None:
        visible = platform_name == "隆丰"
        for widget in (
            self.route_summary, self.route_selector,
            self.route_preview_button, self.route_generate_button,
            self.default_multi_summary, self.default_multi_preview_button,
            self.default_multi_generate_button,
        ):
            widget.setVisible(visible)
        self.pending_route_plan = None
        self.pending_default_multi_plan = None
        self.route_generate_button.setEnabled(False)
        self.default_multi_generate_button.setEnabled(False)
        self.default_multi_summary.setText("默认工艺路线 / 多项多件：尚未读取。")
        self.route_selector.blockSignals(True)
        self.route_selector.clear()
        self.route_selector.setEnabled(False)
        self.route_selector.blockSignals(False)
        if visible:
            self.route_summary.setText("读取全部工艺路线后，默认选择 A05-无印花。")

    def preview_default_multi(self) -> None:
        if self.platform.currentData() != "隆丰":
            return
        self.pending_default_multi_plan = None
        self.default_multi_generate_button.setEnabled(False)
        self.default_multi_summary.setText("正在读取默认工艺路线 / 多项多件…")
        self._start_worker(AutomationWorker("preview_default_multi", "隆丰"))

    @Slot(object)
    def default_multi_plan_finished(self, plan: DefaultMultiPlan) -> None:
        self.pending_default_multi_plan = plan
        self.default_multi_generate_button.setEnabled(plan.item_count > 0)
        self.default_multi_summary.setText(
            f"已接单共 {plan.received_count} 项；默认工艺路线 / 多项多件 "
            f"{plan.item_count} 项、{plan.piece_count} 件。"
            "直接按接口筛选生成，不按尺码或颜色预拆。"
        )

    def confirm_default_multi(self) -> None:
        plan = self.pending_default_multi_plan
        if plan is None or not plan.item_count:
            QMessageBox.warning(self, "没有可生成内容", "请先读取默认路线多项多件。")
            return
        answer = QMessageBox.question(
            self, "确认生成批次",
            f"隆丰 / 已接单 / 默认工艺路线 / 多项多件："
            f"{plan.item_count} 项、{plan.piece_count} 件。\n"
            "将按接口筛选直接生成，生成后无法撤销。继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._start_worker(AutomationWorker(
                "generate_default_multi", "隆丰", route_plan=plan,
            ))

    def preview_process_route(self, *_args) -> None:
        if self.platform.currentData() != "隆丰":
            return
        self.pending_route_plan = None
        self.route_generate_button.setEnabled(False)
        label = self.route_selector.currentText() or "A05-无印花"
        self.route_summary.setText(f"正在读取 {label}…")
        self._start_worker(AutomationWorker(
            "preview_route", "隆丰", route_label=label,
        ))

    @Slot(object)
    def route_plan_finished(self, plan: RouteBatchPlan) -> None:
        self.pending_route_plan = plan
        self.route_selector.blockSignals(True)
        self.route_selector.clear()
        self.route_selector.addItems(plan.routes)
        self.route_selector.setCurrentText(plan.selected_route)
        self.route_selector.setEnabled(True)
        self.route_selector.blockSignals(False)
        self.route_generate_button.setEnabled(plan.item_count > 0)
        self.route_summary.setText(
            f"已接单共 {plan.all_received_count} 项；"
            f"{plan.selected_route} 有 {plan.item_count} 项。"
            "按筛选直接生成，不按底款、物流或面别拆分。"
        )

    def confirm_process_route(self) -> None:
        plan = self.pending_route_plan
        if plan is None or not plan.item_count:
            QMessageBox.warning(self, "没有可生成内容", "请先读取工艺路线。")
            return
        answer = QMessageBox.question(
            self, "确认生成批次",
            f"隆丰 / 已接单 / {plan.selected_route}：{plan.item_count} 项。\n"
            "将点击“按筛选生成批次”，生成后无法撤销。继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._start_worker(AutomationWorker(
                "generate_route", "隆丰", route_plan=plan,
            ))
