"""Rolling batch jobs presented by the same main workbench as single jobs."""
from pathlib import Path
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog
from ..controllers import BulkGenerationController
from .batch_status_board import BatchStatusBoard
from .folder_dialog_paths import image_dialog_start, remember_image_directory
from .bulk_generation_worker import BulkGenerationWorker
from .busy_spinner import show_busy, show_progress
def open_bulk(window):
    if window.has_active_tasks():
        return
    directory = QFileDialog.getExistingDirectory(window, '选择包含多个批次的上级目录',
                                                 image_dialog_start(window))
    if not directory:
        return
    start_bulk(window,Path(directory))
def start_bulk(window,directory):
    directory = Path(directory)
    remember_image_directory(window, str(directory))
    from .quick_fields import show_selected_source
    show_selected_source(window.automation_home.label_quick_panel, str(directory), 'layout', window)
    if not hasattr(window, 'bulk_controller'):
        window.bulk_controller = BulkWorkbench(window)
    window.bulk_controller.begin(Path(directory))

class BulkWorkbench(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.panel = window.automation_home.label_quick_panel
        self.thread = self.worker = None
        self.task_control = BulkGenerationController(self)
        self.folders, self.inventory = [], {}
        self.selector = BatchStatusBoard()
        self.selector.setToolTip('切换当前批次，查看同一主界面的进度、耗时、预览与总结。')
        self.panel.summary.layout().insertWidget(0, self.selector)
        self.selector.currentIndexChanged.connect(self.select)
    def begin(self, parent):
        self.root, self.folders, self.inventory = parent, [], {}
        self.payloads, self.records, self.stages, self.timing_data = {}, {}, {}, {}
        self.window.run_log.clear()
        self.window.run_log.appendPlainText(f'多批次任务：{parent}')
        self.selector.reset(self.folders)
        self.selector.show()
        try:
            settings = self.window._layout_settings()
            custom = None if self.window.output_beside_source.isChecked() else Path(self.window.output_location.text())
            if custom is not None and not custom.is_dir() and not self.window.automation_home.preview_only.isChecked():
                raise ValueError('自定义保存位置不存在')
        except ValueError as error:
            self.window.status.setText(str(error))
            automated = getattr(self.window, 'automated_layout_page', None)
            if automated is not None:
                automated.local_layout_finished({
                    'records': [], 'errors': [{'error': str(error)}], 'stopped': False})
            return
        self.window.generation_preview.start('multiple')
        self.selector.show()
        self.panel.summary.start(str(parent), 0)
        self.panel.preview.sources_ready.emit([])
        self.window.stop_generation_button.setEnabled(True)
        grouped=settings.platform_name.casefold()=='s2b'
        merging=self.window.combine_bulk_batches.isChecked()
        self.window.status.setText('正在扫描所有子文件夹；随后合并为一个批次排版…' if merging else
                                   '正在扫描S2B尺码子文件夹；完成文件将集中保存…' if grouped else
                                   '正在后台扫描各层批次目录与图片文件名…')
        worker = BulkGenerationWorker(
            self.folders, settings, self.window.bulk_parallelism.value(), custom,
            self.window.automation_home.preview_only.isChecked(), parent,
            self.window.combine_bulk_batches.isChecked(),
            self.window.preferences.value('automation/output_location', '', str))
        bindings = ((worker.discovered, self.discovered),
                    (worker.progress, self.progress), (worker.preview, self.preview),
                    (worker.completed, self.completed), (worker.timings, self.timings),
                    (worker.source_progress, self.source_progress),
                    (worker.finished, self.complete))
        self.task_control.start(worker, bindings, self.cleanup)
    @Slot(object)
    def discovered(self, scan):
        if scan.get('platform'):
            self.window.label_settings.platform.setCurrentText(scan['platform'])
        self.inventory = {i: b for i, b in enumerate(scan['batches'])}
        self.folders = [b['folder'] for b in scan['batches']]
        self.selector.reset(self.folders, self.root, self.inventory)
        combined=scan.get('combined_batch_count',0)
        self.window.status.setText(
            f"已扫描{scan['directories']}个目录，合并{combined}个子文件夹为一个批次，开始排版" if combined else
            f"已扫描{scan['directories']}个目录，发现{len(self.folders)}个图片批次，开始滚动处理")
    @Slot(int)
    def select(self, index):
        if index < 0 or index >= len(self.folders):
            return
        view = self.window.generation_preview
        view.payload = None
        view.preview.clear_for_generation()
        view.preview.source_folder = self.folders[index]
        self.panel.analysis.clear()
        info = self.inventory.get(index, {})
        self.panel.summary.start(str(self.folders[index]), info.get('image_count', 0))
        view.preview.sources_ready.emit(info.get('images', []))
        self.panel.timings.reset()
        if index in self.payloads:
            self.panel.summary.start(str(self.folders[index]), len(self.payloads[index]['planned']))
            view.ready(self.payloads[index])
        if index in self.timing_data:
            self.panel.timings.receive(self.timing_data[index])
        if index in self.records:
            record = self.records[index]
            self.panel.summary.finished(record['output'], record['result'])
        if index in self.stages:
            self.show_stage(index)
    def show_stage(self, index):
        stage, current, total, filename = self.stages[index]
        if total:
            show_progress(self.window)
            self.window.progress.setRange(0, 100)
            self.window.progress.setValue(round(current / total * 100))
            self.window.progress.setFormat(stage+' · %p%')
        else:
            show_busy(self.window)
        amount = f'{current}/{total}' if total else '进行中'
        self.window.status.setText(f'{self.folders[index].name} · {stage} · {amount}')
        self.window.current_file.setText('当前文件：'+filename)
        self.window.generation_preview.progress(stage, current, total, filename)
    @Slot(int, str, str, object, object, str)
    def progress(self, index, folder, stage, current, total, filename):
        if index < 0:
            self.window.status.setText(f'{stage} · 已检查{current}个目录')
            self.window.current_file.setText('当前目录：'+filename)
            show_busy(self.window)
            return
        previous = self.stages.get(index)
        if previous is None or previous[0] != stage:
            self.window.run_log.appendPlainText(f'{Path(folder).name}：{stage}')
        self.stages[index] = stage, current, total, filename
        self.selector.update_batch(index, stage, current, total, filename)
        if index == self.selector.currentIndex():
            self.show_stage(index)
    @Slot(int, object)
    def preview(self, index, payload):
        self.payloads[index] = payload
        self.selector.update_distribution(index, payload.get('analysis', {}))
        if index == self.selector.currentIndex():
            self.panel.summary.start(str(self.folders[index]), len(payload['planned']))
            self.window.generation_preview.ready(payload)
    @Slot(int, object)
    def timings(self, index, data):
        self.timing_data[index] = data
        if index == self.selector.currentIndex():
            self.panel.timings.receive(data)
    @Slot(int,str,str,object,object,str)
    def source_progress(self,index,folder,stage,current,total,filename):
        self.selector.update_source(index,folder,stage,current,total,filename)
    @Slot(int, object)
    def completed(self, index, record):
        self.records[index] = record
        if not record['result'].get('preview_only'):
            self.window.job_path.setText(record['output'])
            from .recent_output import remember_recent_output
            remember_recent_output(self.window, record['output'])
        quality = record['result'].get('dual_quality', {}).get('text', '')
        result = '仅预览完成' if record['result'].get('preview_only') else '生成完成'
        self.window.run_log.appendPlainText(
            f"{self.folders[index].name}：{result}" + (f' · {quality}' if quality else '')
        )
        self.selector.update_batch(index, '批次预览完成' if record['result'].get('preview_only') else '批次生成完成')
        if index == self.selector.currentIndex():
            self.panel.summary.finished(record['output'], record['result'])
    @Slot(object)
    def complete(self, result):
        for index in self.selector.items:
            if index not in self.records:
                stage = self.stages.get(index, ('未执行', 0, 0, ''))
                self.selector.update_batch(index, *stage, group='未完成')
        self.window.generation_preview.end()
        show_progress(self.window)
        self.window.progress.setRange(0, 100)
        self.window.progress.setValue(100 if not result['stopped'] else 0)
        self.window.progress.setFormat('已停止' if result['stopped'] else '100% — 已完成')
        self.window.stop_generation_button.setEnabled(False)
        text = (f"{'已停止' if result['stopped'] else '已完成'} · 成功{len(result['records'])}批"
                f" · 失败{len(result['errors'])}批 · 总耗时{result['seconds']:.2f}秒")
        self.window.status.setText(text)
        self.window.run_log.appendPlainText(text)
        for error in result['errors']:
            self.window.run_log.appendPlainText(f"{error['folder']}：{error['error']}")
        if result['errors']:
            self.panel.summary.show_failure('\n'.join(
                f"{e['folder']}：{e['error']}" for e in result['errors']))
        automated = getattr(self.window, 'automated_layout_page', None)
        if automated is not None:
            automated.local_layout_finished(result)
    def cancel(self):
        if not self.task_control.request_cancel():
            return
        self.window.stop_generation_button.setEnabled(False)
        self.window.status.setText('正在停止多批次排版，保留已完成文件；软件不会退出…')
    @Slot()
    def cleanup(self):
        self.task_control.clear()
