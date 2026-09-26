"""Received-item process route controls for Longfeng."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from ...automation.batches.received.routes import RouteBatchPlan
from ...automation.batches.received.default_multi import DefaultMultiPlan
from ..task.worker import AutomationWorker
from .view.route_view import preview_row, show_orders


class RouteActionsMixin:
    def open_playwright_browser(self) -> None:
        self._start_worker(AutomationWorker(
            "open_browser", "",
        ))

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
        preview_row(self.route_preview_table, 0,
                     ("默认路线 A00 / 多项多件", "—", "—", "—", "尚未读取"))
        preview_row(self.route_preview_table, 1,
                     ("其他工艺路线 / 全部组成", "—", "—", "—", "尚未读取"))
        self.candidate_orders_table.setRowCount(0)
        self.candidate_orders_label.setText("候选订单明细：尚未读取。")
        if visible:
            self.route_summary.setText("读取全部工艺路线后，默认选择 A05-无印花。")

    def preview_default_multi(self) -> None:
        if self.platform.currentData() != "隆丰":
            return
        self.pending_default_multi_plan = None
        self.default_multi_generate_button.setEnabled(False)
        self.default_multi_summary.setText("正在读取默认工艺路线 / 多项多件…")
        preview_row(self.route_preview_table, 0,
                     ("默认路线 A00 / 多项多件", "—", "—", "—", "正在读取"))
        self.candidate_orders_table.setRowCount(0)
        self.candidate_orders_label.setText("正在读取默认路线的候选订单…")
        self._start_worker(AutomationWorker("preview_default_multi", "隆丰"))

    @Slot(object)
    def default_multi_plan_finished(self, plan: DefaultMultiPlan) -> None:
        self.pending_default_multi_plan = plan
        self.default_multi_generate_button.setEnabled(plan.item_count > 0)
        preview_row(self.route_preview_table, 0, (
            "默认路线 A00 / 多项多件", str(len(plan.order_items)),
            str(plan.item_count), str(plan.piece_count),
            "可生成" if plan.item_count else "无待生成项目",
        ))
        quantities = dict(plan.item_quantities)
        show_orders(self.candidate_orders_table, tuple(
            (order_id, len(item_ids), sum(quantities[item_id] for item_id in item_ids))
            for order_id, item_ids in plan.order_items
        ))
        self.candidate_orders_label.setText(
            f"默认路线 A00 / 多项多件：{len(plan.order_items)} 个候选订单"
        )
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
        preview_row(self.route_preview_table, 1,
                     (f"{label} / 全部组成", "—", "—", "—", "正在读取"))
        self.candidate_orders_table.setRowCount(0)
        self.candidate_orders_label.setText(f"正在读取 {label} 的候选订单…")
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
        preview_row(self.route_preview_table, 1, (
            f"{plan.selected_route} / 全部组成", str(plan.order_count),
            str(plan.item_count), str(plan.piece_count),
            "可生成" if plan.item_count else "无待生成项目",
        ))
        show_orders(self.candidate_orders_table, plan.order_details)
        self.candidate_orders_label.setText(
            f"{plan.selected_route}：{plan.order_count} 个候选订单"
        )
        self.route_summary.setText(
            f"已接单共 {plan.all_received_count} 项；"
            f"{plan.selected_route} 有 {plan.order_count} 单、"
            f"{plan.item_count} 项、{plan.piece_count} 件。"
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
