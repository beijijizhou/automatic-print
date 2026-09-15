"""Normal-mode multi-batch generation with selectable real batch previews."""
from pathlib import Path
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QScrollArea
from .bulk_film_analysis import BulkFilmAnalysisDialog
from .bulk_generation_worker import BulkGenerationWorker
from .pair_preview import PairProductionPreview
from .preview_snapshot import install_snapshot


class BulkGenerationDialog(BulkFilmAnalysisDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('多批次排版 · 独立生成切膜机文件')
        self.layout().itemAt(0).widget().setText(
            '选择上级目录；每批独立读取和排版，最终PNG集中保存，报告单独进入排版日志。')
        self.start.setText('开始批量排版')
        self.stop.setText('暂停批次')
        self.stop.setToolTip('安全停止，不再启动后续批次；保留已完成文件，暂不支持断点续跑。')
        concurrency = self.layout().itemAt(2).layout()
        for index in range(concurrency.count()):
            widget = concurrency.itemAt(index).widget()
            if widget:
                widget.hide()
        self.status.setText('确认批次及打印参数后直接开始；“切膜机文件”内只保存最终PNG。')
        self.results.setMaximumHeight(180)
        self.payloads = {}
        self.preview = PairProductionPreview(parent._layout_settings, self)
        self.preview.overview = True
        self.preview.auto_refresh_enabled = False
        self.preview.detail = '选中批次后显示它的真实排版预览，不混用其他批次。'
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(300)
        scroll.setWidget(self.preview)
        from .preview_viewport import PreviewViewport
        self.layout().addWidget(PreviewViewport(self.preview, scroll))
        self.folders.currentRowChanged.connect(self.show_batch)

    def make_worker(self, folders, settings):
        self.payloads.clear()
        self.preview.clear_for_generation()
        parent = self.parent()
        custom = None if parent.output_beside_source.isChecked() else Path(parent.output_location.text().strip())
        if custom is not None and not custom.is_dir():
            raise ValueError('自定义保存位置不存在')
        worker = BulkGenerationWorker(folders, settings, self.parallelism.value(), custom)
        worker.preview.connect(self.receive_preview, Qt.QueuedConnection)
        return worker

    def begin(self):
        parent = self.parent()
        self.parallelism.setValue(parent.bulk_parallelism.value())
        if not parent.output_beside_source.isChecked() and not Path(parent.output_location.text().strip()).is_dir():
            self.status.setText('自定义保存位置不存在，请先在打印参数中修改。')
            return
        super().begin()
        if self.thread:
            self.status.setText(f'正在开始：同时生成{self.active_parallelism}批，后台读取图片…')

    @Slot(int, str, str, object, object, str)
    def progress(self, index, folder, stage, current, total, filename):
        super().progress(index, folder, stage, current, total, filename)

    @Slot(int, object)
    def receive_preview(self, index, payload):
        self.payloads[index] = payload
        if self.folders.currentRow() < 0:
            self.folders.setCurrentRow(index)
        if self.folders.currentRow() == index:
            self.show_batch(index)

    @Slot(int)
    def show_batch(self, index):
        self.preview.clear_for_generation()
        payload = self.payloads.get(index)
        if not payload:
            self.preview.detail = '此批尚未计算完成；等待本批预览，不显示旧批次。'
            return
        self.preview.batch_payload = payload
        install_snapshot(self.preview, payload['planned'], payload['labels'],
                         payload['settings'], payload.get('warning', ''))
        name = Path(self.folders.item(index).data(Qt.UserRole)).name
        self.preview.detail = f'{name} · 共{len(payload["planned"])}张 · 节省{payload.get("saved_meters", 0):.3f}米'
        self.preview.update()

    @Slot(object)
    def complete(self, result):
        lines = []
        for record in result['records']:
            data = record['result']
            from ..layout_engine.operation_timing import timing_report
            from ..layout_engine.output_sizes import cutting_report
            lines.append(f"{Path(record['folder']).name}：{data.get('filename', '')}\n"
                         f"输出：{record['output']}\n节省：{data.get('saved_meters', 0):.3f}米")
            lines.append(timing_report(data['operation_timings']))
            lines.append(cutting_report(data))
        lines += [f"失败 · {e['folder']}：{e['error']}" for e in result['errors']]
        self.results.setPlainText('\n\n'.join(lines))
        self.status.setText(f"{'已停止' if result['stopped'] else '已完成'} · "
                           f"已生成{len(result['records'])}批 · 失败{len(result['errors'])}批 · "
                           f"总耗时{result['seconds']:.2f}秒；排版报告保存在独立日志文件夹。")

    def set_busy(self, busy):
        super().set_busy(busy)
        self.folders.setEnabled(True)  # Selection reviews previews; queue editing remains disabled.
