from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ..cancellation import Cancellation, TaskCancelled
from ..layout import LayoutSettings, generate_layout
from ..updater import fetch_latest_release


class GenerateWorker(QObject):
    progress = Signal(str, int, object, str)
    finished = Signal(str, object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        images: list[Path],
        source: Path,
        output: Path,
        job_id: str,
        settings: LayoutSettings,
    ) -> None:
        super().__init__()
        self.images = images
        self.source = source
        self.output = output
        self.job_id = job_id
        self.settings = settings
        self.cancellation = Cancellation()

    def request_cancel(self) -> None:
        self.cancellation.request()

    def _progress(self, stage, current, total, filename) -> None:
        self.cancellation.check()
        self.progress.emit(stage, current, total, filename)

    @Slot()
    def run(self) -> None:
        try:
            result = generate_layout(
                self.images, self.output, self.settings, self._progress
            )
            self.cancellation.check()
            manifest = {
                "job_id": self.job_id,
                "created_at": datetime.now().astimezone().isoformat(),
                "source_folder": str(self.source),
                "settings": asdict(self.settings),
                "source_count": len(self.images),
                "print_image": result,
            }
            (self.output / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
        except TaskCancelled:
            self.cancelled.emit()
            return
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.finished.emit(str(self.output), result)


class UpdateWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(fetch_latest_release())
        except Exception as error:
            self.failed.emit(str(error))
