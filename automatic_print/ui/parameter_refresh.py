"""Coalesce linked UI parameter edits without starting batch analysis."""
from contextlib import contextmanager


@contextmanager
def defer_parameter_refresh(window):
    home = getattr(window, 'automation_home', None)
    preview = getattr(getattr(home, 'label_quick_panel', None), 'preview', None)
    if preview is None:
        # Settings are also applied while MainWindow is still being built.
        # There is no active preview to invalidate at that point.
        yield
        return
    depth = getattr(preview, 'parameter_refresh_deferred', 0)
    preview.parameter_refresh_deferred = depth + 1
    if depth == 0:
        preview.refresh_timer.stop()
        preview.loader.invalidate()
    try:
        yield
    finally:
        preview.parameter_refresh_deferred -= 1
        if preview.parameter_refresh_deferred == 0 and (
            preview.source_folder is not None or preview.batch_payload
        ):
            message = '参数已更新；点击单批次或多批次排版后重新计算。'
            preview.production_stage = message
            preview.loading_status.emit(message)
            preview.update()
