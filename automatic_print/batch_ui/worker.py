from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ..cancellation import Cancellation, TaskCancelled
from ..automation.batch_browser import (
    download_selected_batches,
    load_batch_records,
    load_batch_records_between,
    load_platform_order_status,
)
from ..automation.batch_naming import save_batch_type
from ..automation.rule_batches import (
    RuleBatchPlan,
    generate_rule_batches,
    preview_rule_batch_plan,
)
from ..layout import LayoutSettings
from .processing import process_local_batches


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
        generation_rule: str = "按有面单生成批次规则",
        range_start: str = "",
        range_end: str = "",
        batch_types: dict[str, str] | None = None,
        merge_batches: bool = False,
    ) -> None:
        super().__init__()
        self.action = action
        self.platform_name = platform_name
        self.output = output
        self.batch_numbers = batch_numbers or []
        self.settings = settings
        self.sample_limit = sample_limit
        self.batch_plan = batch_plan
        self.generation_rule = generation_rule
        self.range_start = range_start
        self.range_end = range_end
        self.batch_types = batch_types or {}
        self.merge_batches = merge_batches
        self.cancellation = Cancellation()

    def request_cancel(self) -> None:
        self.cancellation.request()

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
            self._deliver(
                self.batches_loaded,
                load_batch_records(self.platform_name)
            )
        elif self.action == "list_range":
            self._report("正在读取指定范围内的生产批次…")
            self._deliver(
                self.batches_loaded,
                load_batch_records_between(
                    self.platform_name,
                    self.range_start,
                    self.range_end,
                )
            )
        elif self.action in {"status", "status_and_list"}:
            self._report(
                f"正在刷新 {self.platform_name} 平台状态…"
            )
            self._deliver(
                self.status_loaded,
                load_platform_order_status(
                    self.platform_name, self._report
                )
            )
            if self.action == "status_and_list":
                self._deliver(
                    self.batches_loaded,
                    load_batch_records(self.platform_name)
                )
        elif self.action == "preview_rules":
            self._deliver(
                self.plan_loaded,
                preview_rule_batch_plan(
                    self.platform_name, self._report
                )
            )
        elif self.action == "generate_rules":
            if self.batch_plan is None:
                raise RuntimeError("请先读取并确认批次分类数量。")
            count = generate_rule_batches(
                self.batch_plan,
                self.generation_rule,
                self._report,
            )
            self._deliver(
                self.completed,
                {
                    "type": "batches_generated",
                    "platform": self.platform_name,
                    "generated": count,
                }
            )
        elif self.action == "download":
            self._download_and_process()
        elif self.action == "process":
            self._deliver(self.completed, self._process_batches())
        else:
            raise RuntimeError(f"未知操作：{self.action}")

    def _download_and_process(self) -> None:
        if self.output is None:
            raise RuntimeError("请选择下载保存位置。")
        files = download_selected_batches(
            self.platform_name,
            self.batch_numbers,
            self.output,
            self._report,
        )
        self._save_batch_types()
        self._report("下载与解压完成，正在自动排版…")
        result = self._process_batches()
        result.update(type="downloaded_and_processed", files=files)
        self._deliver(self.completed, result)

    def _process_batches(self) -> dict:
        if self.output is None or self.settings is None:
            raise RuntimeError("缺少排版位置或排版设置。")
        return process_local_batches(
            self.output,
            self.platform_name,
            self.batch_numbers,
            self.batch_types,
            self.settings,
            self.sample_limit,
            self.merge_batches,
            self._report,
        )

    def _save_batch_types(self) -> None:
        platform_root = self.output / self.platform_name
        for batch_number, batch_type in self.batch_types.items():
            standard_folder = platform_root / "BATCHES" / batch_number
            if standard_folder.is_dir():
                save_batch_type(standard_folder, batch_type)
                continue
            folders = [
                folder
                for folder in platform_root.rglob(batch_number)
                if folder.is_dir() and folder.name == batch_number
            ]
            if len(folders) == 1:
                save_batch_type(folders[0], batch_type)
