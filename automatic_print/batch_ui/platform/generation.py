from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QMessageBox,
    QTableWidgetItem,
)

from ...automation.providers.registry import get_erp_platform
from ...automation.batches.classification import (
    DOUBLE_FACE,
    detailed_compositions,
)
from ...automation.batches.received.rules import RuleBatchPlan
from ...automation.batches.received.routes import RouteBatchPlan
from ...automation.batches.received.default_multi import DefaultMultiPlan
from ..task.worker import AutomationWorker
from .view.generation_page import ask_generation_rule


class GenerationActionsMixin:
    def show_platform_batch_rules(self, name: str) -> None:
        platform = get_erp_platform(name)
        self.batch_rule_summary.setStyleSheet(
            "padding:8px;background:#eef4ff;border:1px solid #9bbcff;"
            "font-weight:600;"
        )
        shipping = platform.shipping_categories
        compositions = detailed_compositions(platform.order_compositions)
        if not shipping:
            self.batch_rule_summary.setText(
                f"{name}：尚未配置物流分类规则。"
            )
            self.generation_table.setRowCount(0)
            return
        self.batch_rule_summary.setText(
            f"{name} 专用批次规则\n"
            "分类优先级：① 先按物流分类 → ② 再按订单组成分类\n"
            f"物流：{' / '.join(shipping)}\n"
            f"订单组成：{' / '.join(compositions)}"
        )
        rows = [
            (method, composition)
            for method in shipping
            for composition in compositions
        ]
        rows.extend(
            (method, "不生成")
            for method in platform.excluded_shipping_categories
        )
        self.generation_table.setRowCount(len(rows))
        for row, (method, composition) in enumerate(rows):
            values = [
                method,
                "—",
                "—",
                composition,
                "物流无法生成—剔除"
                if composition == "不生成"
                else "等待读取",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if composition == "不生成":
                    item.setForeground(QColor("#c62828"))
                self.generation_table.setItem(row, column, item)

    def preview_generation_rules(self) -> None:
        self.pending_batch_plan = None
        self.generate_rules_button.setEnabled(False)
        self.show_platform_batch_rules(self.platform.currentData())
        self._start_worker(
            AutomationWorker(
                "preview_rules", self.platform.currentData()
            )
        )

    @Slot(object)
    def generation_plan_finished(self, plan: RuleBatchPlan) -> None:
        if isinstance(plan, DefaultMultiPlan):
            self.default_multi_plan_finished(plan)
            return
        if isinstance(plan, RouteBatchPlan):
            self.route_plan_finished(plan)
            return
        self.pending_batch_plan = plan
        counts = {
            (item.shipping_method, item.order_composition): item.item_count
            for item in plan.items
        }
        pieces = {
            (item.shipping_method, item.order_composition): item.piece_count
            for item in plan.items
        }
        excluded = {
            item.shipping_method: item.item_count
            for item in plan.excluded_items
        }
        for row in range(self.generation_table.rowCount()):
            method = self.generation_table.item(row, 0).text()
            composition = self.generation_table.item(row, 3).text()
            is_excluded = composition == "不生成"
            count = (
                excluded.get(method, 0)
                if is_excluded
                else counts.get((method, composition), 0)
            )
            self.generation_table.setItem(
                row, 1, QTableWidgetItem(str(count))
            )
            self.generation_table.setItem(
                row, 2, QTableWidgetItem(
                    "—" if is_excluded or (count and not pieces.get((method, composition)))
                    else str(pieces.get((method, composition), 0))
                )
            )
            status = QTableWidgetItem(
                "物流无法生成—已剔除"
                if is_excluded
                else ("可生成" if count else "无订单")
            )
            if is_excluded:
                status.setForeground(QColor("#c62828"))
            self.generation_table.setItem(row, 4, status)
        unmatched = (
            plan.received_count - plan.total_items - plan.excluded_count
        )
        matched = unmatched == 0
        double_face_count = sum(
            item.item_count
            for item in plan.items
            if item.order_composition == DOUBLE_FACE
        )
        self.generate_rules_button.setEnabled(
            bool(plan.nonempty_items) and matched
        )
        self.batch_rule_summary.setText(
            self.batch_rule_summary.text()
            + f"\n已接单：{plan.received_count} 项；"
            f"规则匹配：{plan.total_items} 项；"
            f"剔除：{plan.excluded_count} 项。"
            f"\n单项单件（双面）：{double_face_count} 项。"
            + (
                ""
                if matched
                else f"\n有 {abs(unmatched)} 项未完整覆盖，已禁止生成。"
            )
        )

    def confirm_generate_rules(self) -> None:
        plan = self.pending_batch_plan
        if plan is None or not plan.nonempty_items:
            QMessageBox.warning(
                self, "没有可生成内容", "请先读取分类数量。"
            )
            return
        if plan.total_items + plan.excluded_count != plan.received_count:
            QMessageBox.critical(
                self,
                "分类未完整覆盖",
                "规则匹配数量与已接单总数不一致，不能生成批次。",
            )
            return
        rule = ask_generation_rule(self, plan)
        if rule is None:
            return
        self._start_worker(
            AutomationWorker(
                "generate_rules",
                plan.platform_name,
                batch_plan=plan,
                generation_rule=rule,
            )
        )
