from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ...runtime.cancellation import Cancellation, TaskCancelled
from ...automation.browser.batches import (
    download_selected_batches,
    load_batch_records,
    load_batch_records_between,
    load_platform_order_status,
)
from ...automation.batches.received.rules import RuleBatchPlan
from ...automation.batches.received.routes import RouteBatchPlan
from ...automation.batches.received.default_multi import DefaultMultiPlan
from ...layout_engine import LayoutSettings
from ..local.processing import process_local_batches
from .generation_actions import GENERATION_ACTIONS, run_generation_action


class AutomationWorker(QObject):
    progress = Signal(str)
    batches_loaded = Signal(object)
    status_loaded = Signal(object)
    plan_loaded = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        action: str,
        platform_name: str,
        output: Path | None = None,
        batch_numbers: list[str] | None = None,
        settings: LayoutSettings | None = None,
        sample_limit: int | None = None,
        batch_plan: RuleBatchPlan | None = None,
        route_plan: RouteBatchPlan | DefaultMultiPlan | None = None,
        route_label: str = "A05-无印花",
        generation_rule: str = "按有面单生成批次规则",
        range_start: str = "",
        range_end: str = "",
        batch_types: dict[str, str] | None = None,
        batch_labels: dict[str, str] | None = None,
        merge_batches: bool = False,
        preview_only: bool = False,
        auto_print: bool = False,
    ) -> None:
        super().__init__()
        self.action = action
        self.platform_name = platform_name
        self.output = output
        self.batch_numbers = batch_numbers or []
        self.settings = settings
        self.sample_limit = sample_limit
        self.batch_plan = batch_plan
        self.route_plan = route_plan
        self.route_label = route_label
        self.generation_rule = generation_rule
        self.range_start = range_start
        self.range_end = range_end
        self.batch_types = batch_types or {}
        self.batch_labels = batch_labels or {}
        self.merge_batches = merge_batches
        self.preview_only = preview_only
        self.auto_print = auto_print
        self.cancellation = Cancellation()

    def request_cancel(self) -> None:
        self.cancellation.request()

    @property
    def task_title(self) -> str:
        titles = {
            "list": "读取生产批次", "list_range": "读取批次范围",
            "status": "刷新平台状态", "status_and_list": "刷新状态和批次",
            "open_browser": "打开 Playwright 浏览器", "read": "读取数据",
            "preview_rules": "预览批次规则", "preview_route": "预览工艺路线",
            "preview_default_multi": "预览默认工艺多项多件",
            "generate_rules": "生成规则批次",
            "generate_route": "生成工艺路线批次",
            "generate_default_multi": "生成默认工艺批次",
            "generate_completed_erp": "生成已完成订单批次",
            "download": "下载生产图",
            "process": "生产图排版",
        }
        if self.action == "download" and self.auto_print is True:
            return "下载、排版并生成打印文件"
        return titles.get(self.action, self.action)

    @property
    def stop_pending_text(self) -> str:
        if self.action in {"list", "list_range", "status", "status_and_list"}:
            return "正在停止批次信息读取…"
        if self.action == "read":
            return "正在停止数据读取…"
        if self.action.startswith("preview_"):
            return "正在停止批次预览…"
        if self.action.startswith("generate_"):
            return "正在停止批次生成…"
        if self.action == "download" and self.auto_print is True:
            return (
                "正在安全停止；已提交的 RIIN 文件任务结束后收尾，"
                "后续批次不会启动…"
            )
        if self.action == "download":
            return "正在停止批次下载…"
        if self.action == "process":
            return "正在停止排版；已完成文件会保留…"
        return "正在停止当前处理…"

    @property
    def stopped_text(self) -> str:
        if self.action in {"list", "list_range", "status", "status_and_list"}:
            return "批次信息读取已停止。"
        if self.action == "read":
            return "数据读取已停止。"
        if self.action.startswith("preview_"):
            return "批次预览已停止。"
        if self.action.startswith("generate_"):
            return "批次生成已停止。"
        if self.action == "download" and self.auto_print is True:
            return "自动打印已安全停止，已经完成的文件会保留。"
        if self.action == "download":
            return "批次下载已停止，已经完成的文件会保留。"
        if self.action == "process":
            return "排版已停止，已经完成的文件会保留。"
        return "当前处理已停止，已经完成的结果会保留。"

    def _report(self, message: str) -> None:
        self.cancellation.check()
        self.progress.emit(message)

    def _deliver(self, signal, value) -> None:
        self.cancellation.check()
        signal.emit(value)

    @Slot()
    def run(self) -> None:
        try:
            self._run_action()
        except TaskCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))

    def _run_action(self) -> None:
        if self.action == "list":
            self._report(
                f"正在读取 {self.platform_name} 已生成批次…"
            )
            records = load_batch_records(
                self.platform_name,
                self._report,
                self.cancellation.check,
            )
            self._report(f"批次信息读取完成：共 {len(records)} 个批次。")
            self._deliver(self.batches_loaded, records)
        elif self.action == "list_range":
            self._report("正在读取指定范围内的生产批次…")
            records = load_batch_records_between(
                self.platform_name,
                self.range_start,
                self.range_end,
                self._report,
                self.cancellation.check,
            )
            self._report(f"批次范围读取完成：共 {len(records)} 个批次。")
            self._deliver(self.batches_loaded, records)
        elif self.action in {"status", "status_and_list"}:
            self._report(
                f"正在刷新 {self.platform_name} 平台状态…"
            )
            status = load_platform_order_status(
                self.platform_name,
                self._report,
                self.cancellation.check,
            )
            self._report(
                f"平台状态读取完成：已接单 {status.accepted_count} 项。"
            )
            self._deliver(self.status_loaded, status)
            if self.action == "status_and_list":
                self._report("平台状态已更新；继续读取生产批次…")
                records = load_batch_records(
                    self.platform_name,
                    self._report,
                    self.cancellation.check,
                )
                self._report(f"批次信息读取完成：共 {len(records)} 个批次。")
                self._deliver(self.batches_loaded, records)
        elif self.action == "open_browser":
            from ...automation.browser.session import open_managed_browser
            self._deliver(self.completed, open_managed_browser(
                self.cancellation.check, self._report,
            ))
        elif self.action in GENERATION_ACTIONS:
            run_generation_action(self)
        elif self.action == "download":
            self._download()
        elif self.action == "process":
            self._deliver(self.completed, self._process_batches())
        else:
            raise RuntimeError(f"未知操作：{self.action}")

    def _download(self) -> None:
        if self.output is None:
            raise RuntimeError("请选择下载保存位置。")
        files = download_selected_batches(
            self.platform_name,
            self.batch_numbers,
            self.output,
            self._report,
            self.cancellation.check,
        )
        self._report("生产图已准备完成；正在保存批次类型信息…")
        self._save_batch_types()
        self._report("批次类型信息已保存。")
        if self.auto_print:
            from .automatic_print import process_and_print
            processed = process_and_print(
                self._process_batches, files, self.progress.emit,
                self.cancellation.requested,
            )
            self.completed.emit(processed)
            return
        self._report("下载与解压完成；未启动排版。")
        self._deliver(
            self.completed,
            {
                "type": "downloaded",
                "platform": self.platform_name,
                "files": files,
                "output_folder": str(self.output / self.platform_name),
            },
        )

    def _process_batches(self) -> dict:
        if self.output is None or self.settings is None:
            raise RuntimeError("缺少排版位置或排版设置。")
        self._report("正在定位已解压的批次文件夹并读取生产图…")
        return process_local_batches(
            self.output,
            self.platform_name,
            self.batch_numbers,
            self.batch_types,
            self.settings,
            self.sample_limit,
            self.merge_batches,
            self._report,
            preview_only=self.preview_only,
            shared_knife=self.auto_print in ('shared_knife', 'shared_knife_order_side'),
            order_side=self.auto_print == 'shared_knife_order_side',
            batch_labels=self.batch_labels,
        )

    def _save_batch_types(self) -> None:
        from .automatic_print import save_downloaded_batch_types
        save_downloaded_batch_types(
            self.output, self.platform_name, self.batch_types
        )
