from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ..automation.batch_browser import (
    download_selected_batches,
    load_batch_records,
    load_batch_records_between,
    load_platform_order_status,
)
from ..automation.rule_batches import (
    RuleBatchPlan,
    generate_rule_batches,
    preview_rule_batch_plan,
)
from ..layout import LayoutSettings, discover_images, generate_layout


class AutomationWorker(QObject):
    progress = Signal(str)
    batches_loaded = Signal(object)
    status_loaded = Signal(object)
    plan_loaded = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

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

    @Slot()
    def run(self) -> None:
        try:
            self._run_action()
        except Exception as error:
            self.failed.emit(str(error))

    def _run_action(self) -> None:
        if self.action == "list":
            self.progress.emit(
                f"正在读取 {self.platform_name} 已生成批次…"
            )
            self.batches_loaded.emit(
                load_batch_records(self.platform_name)
            )
        elif self.action == "list_range":
            self.progress.emit("正在读取指定范围内的生产批次…")
            self.batches_loaded.emit(
                load_batch_records_between(
                    self.platform_name,
                    self.range_start,
                    self.range_end,
                )
            )
        elif self.action in {"status", "status_and_list"}:
            self.progress.emit(
                f"正在刷新 {self.platform_name} 平台状态…"
            )
            self.status_loaded.emit(
                load_platform_order_status(
                    self.platform_name, self.progress.emit
                )
            )
            if self.action == "status_and_list":
                self.batches_loaded.emit(
                    load_batch_records(self.platform_name)
                )
        elif self.action == "preview_rules":
            self.plan_loaded.emit(
                preview_rule_batch_plan(
                    self.platform_name, self.progress.emit
                )
            )
        elif self.action == "generate_rules":
            if self.batch_plan is None:
                raise RuntimeError("请先读取并确认批次分类数量。")
            count = generate_rule_batches(
                self.batch_plan,
                self.generation_rule,
                self.progress.emit,
            )
            self.completed.emit(
                {
                    "type": "batches_generated",
                    "platform": self.platform_name,
                    "generated": count,
                }
            )
        elif self.action == "download":
            self._download_and_process()
        elif self.action == "process":
            self.completed.emit(self._process_batches())
        else:
            raise RuntimeError(f"未知操作：{self.action}")

    def _download_and_process(self) -> None:
        if self.output is None:
            raise RuntimeError("请选择下载保存位置。")
        files = download_selected_batches(
            self.platform_name,
            self.batch_numbers,
            self.output,
            self.progress.emit,
        )
        self.progress.emit("下载与解压完成，正在自动排版…")
        result = self._process_batches()
        result.update(type="downloaded_and_processed", files=files)
        self.completed.emit(result)

    def _process_batches(self) -> dict:
        if self.output is None or self.settings is None:
            raise RuntimeError("缺少排版位置或排版设置。")
        platform_root = self.output / self.platform_name
        folders = sorted(
            folder
            for folder in platform_root.rglob("*")
            if folder.is_dir()
            and len(folder.name) == 12
            and folder.name.isdigit()
            and not {"PROCESSED", "TEST_SAMPLE"}.intersection(folder.parts)
            and discover_images(folder)
        )
        if self.batch_numbers:
            selected = set(self.batch_numbers)
            folders = [
                folder for folder in folders if folder.name in selected
            ]
        if not folders:
            raise RuntimeError(
                f"没有找到 {self.platform_name} 已解压的生产批次文件夹。"
            )
        if self.sample_limit:
            folders = folders[:1]
        completed = []
        output_name = "TEST_SAMPLE" if self.sample_limit else "PROCESSED"
        for index, folder in enumerate(folders, start=1):
            images = discover_images(folder)
            if self.sample_limit:
                images = images[: self.sample_limit]
            destination = platform_root / output_name / folder.name
            self.progress.emit(
                f"[{index}/{len(folders)}] {folder.name}："
                f"正在排版 {len(images)} 张图片"
            )
            result = generate_layout(
                images,
                destination,
                self.settings,
                lambda stage, current, total, name: self.progress.emit(
                    f"{folder.name} · {stage} {current}/{total}"
                )
                if current == total or current % 50 == 0
                else None,
            )
            completed.append((folder.name, result))
        return {
            "type": "processed",
            "platform": self.platform_name,
            "batches": completed,
            "test": bool(self.sample_limit),
            "output_folder": str(platform_root / output_name),
        }
