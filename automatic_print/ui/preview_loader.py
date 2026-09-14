"""Coalesced, cancellable preview requests with GUI-thread result delivery."""
from PySide6.QtCore import QObject, QThreadPool, Qt, Slot

from .preview_task import PreviewTask
from .preview_snapshot import install_snapshot
from ..layout_engine.order_groups import detail_members


class PreviewLoader(QObject):
    def __init__(self, preview):
        super().__init__(preview)
        self.preview = preview
        self.token, self.active, self.pending, self.closed = 0, None, None, False

    def invalidate(self):
        self.token += 1
        self.pending = None
        if self.active:
            self.active.cancel.request()

    def request(self, folder, settings):
        self.invalidate()
        if self.closed:
            return
        self.pending = (self.token, folder, settings)
        self.preview.analysis_started.emit()
        self.status('正在后台读取文件夹；界面可继续操作…')
        self.launch()

    def status(self, text):
        self.preview.production_stage = text
        self.preview.loading_status.emit(text)
        self.preview.update()

    def launch(self):
        if self.closed or self.active or not self.pending:
            return
        self.active = PreviewTask(*self.pending)
        self.pending = None
        task = self.active
        task.signals.progress.connect(self.progress, Qt.QueuedConnection)
        task.signals.sources.connect(self.sources, Qt.QueuedConnection)
        task.signals.analysis.connect(self.analysis, Qt.QueuedConnection)
        task.signals.finished.connect(self.finished, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(task)

    @Slot(object, str)
    def progress(self, token, text):
        if token == self.token and not self.closed:
            self.status(text)

    @Slot(object, object)
    def sources(self, token, paths):
        if token == self.token and not self.closed:
            if self.preview.path not in paths:
                self.preview.path = paths[0] if paths else None
            self.preview.sources_ready.emit(paths)

    @Slot(object, object)
    def analysis(self, token, report):
        if token == self.token and not self.closed:
            self.preview.analysis_ready.emit(report)

    @Slot(object, object, str)
    def finished(self, token, payload, error):
        self.active = None
        if token == self.token and not self.closed:
            p = self.preview
            if error:
                p.warning = f'新预览未生成，保留上次预览（旧参数）：{error}'
                p.analysis_failed.emit(error)
                self.status(p.warning)
            else:
                try:
                    shown = payload['planned'] if p.overview else detail_members(payload['planned'], p.path)
                    install_snapshot(p, shown, payload['labels'], payload['settings'],
                                     payload['warning'], payload['overflow'])
                    p.batch_payload = payload
                    settings = payload['settings']
                    from .knife_caption import knife_caption
                    knives = knife_caption(payload['planned'], settings.dpi, ' / ')
                    p.detail = f"{'整批总览' if p.overview else '双图细节'} · 整批 {len(payload['planned'])} 张 · 节省 {payload['saved_meters']:.3f} 米 · {knives}"
                    p.plan_loaded.emit(payload)
                    self.status(payload['warning'] or '整批预览完成 · 尚未生成输出文件')
                except (ValueError, OSError) as exc:
                    p.analysis_failed.emit(str(exc))
                    self.status(f'预览图片读取失败：{exc}')
        self.launch()

    def stop(self):
        self.invalidate()
        self.status('预览已请求停止；界面仍可操作。')

    def shutdown(self):
        self.closed = True
        self.invalidate()
