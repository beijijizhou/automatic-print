"""Stable main-window methods delegating to separated generation UI flows."""

from PySide6.QtCore import Slot

from ....layout import LayoutSettings
from ...layout_values import settings_from_window
from .progress import refresh_timing, saving_detail, update_progress
from .results import generation_cancelled, generation_failed, generation_finished
from .start import start_generation


class GenerationActionsMixin:
    def _layout_settings(self) -> LayoutSettings:
        return settings_from_window(self)

    def generate(self, checked=False, *, preview_only=False) -> None:
        start_generation(self, preview_only=preview_only)

    @Slot(str, object, object, str)
    def update_progress(self, stage, current, total, filename) -> None:
        update_progress(self, stage, current, total, filename)

    @Slot()
    def refresh_timing(self) -> None:
        refresh_timing(self)

    def _saving_detail(self) -> str:
        return saving_detail(self)

    @Slot()
    def stop_generation(self) -> None:
        from ...stop_actions import stop_active_layout
        stop_active_layout(self)

    @Slot(str, object)
    def generation_finished(self, output, result) -> None:
        generation_finished(self, output, result)

    @Slot(str)
    def generation_failed(self, message) -> None:
        generation_failed(self, message)

    @Slot()
    def generation_cancelled(self) -> None:
        generation_cancelled(self)

    @Slot()
    def clear_worker(self) -> None:
        self.layout_generation.clear()
