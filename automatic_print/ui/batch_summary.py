"""Always-visible current task information, separate from print settings."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QPlainTextEdit, QVBoxLayout
from ..layout_engine.output_sizes import cutting_report


class BatchSummaryPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__('本次批次 · 排版总结', parent)
        self.info = QLabel('请选择本地图片文件夹。')
        self.metrics = QLabel('排版后显示总长度、节省用膜和旋转数量。')
        self.progress = QLabel('尚未开始')
        self.cutting = QPlainTextEdit()
        self.cutting.setReadOnly(True)
        self.cutting.setMaximumHeight(110)
        self.cutting.setMinimumHeight(65)
        self.cutting.hide()
        layout = QVBoxLayout(self)
        for label in (self.info, self.metrics, self.progress):
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(label)
        layout.addWidget(self.cutting)

    def start(self, folder, count=None):
        self.cutting.clear()
        self.cutting.hide()
        path = Path(folder)
        quantity = f'{count} 张图片' if count is not None else '正在读取图片名称'
        self.info.setText(f'批次 / 文件夹：{path.name} · {quantity}\n来源：{path}')
        self.metrics.setText('正在计算本批次长度和省膜结果…')
        self.progress.setText('正在读取本批次；旧预览已清除。')

    def show_plan(self, payload):
        planned = payload['planned']
        self.show_analysis(payload.get('analysis', {}))
        rotations = sum(bool(p.rotation_degrees) for _, p in planned)
        self.metrics.setText(self.metrics.text()+f' · 旋转 {rotations} 张'
                             f" · 可用宽度 {payload['settings'].media_width_mm:g} 毫米")
        self._show_quality(payload.get('dual_quality', {}))
        self.progress.setText(payload.get('warning') or '排版已确定，下面显示本批次真实预览。')

    def show_analysis(self, report):
        if not report:
            return
        folder = self.info.text().split('\n')[0]
        self.info.setText(f"{folder}\n{report['batch_type']} · {report['order_count']} 个订单组"
                          f" · {report['piece_count']} 件 / {report['image_count']} 张图"
                          f" · {report['double_pairs']} 组双面")
        if 'height_m' in report:
            saved = report['saved_m']
            self.metrics.setText(f"排版长度 {report['height_m']:.3f} 米"
                                 f" · 常规基准 {report['height_m']+saved:.3f} 米"
                                 f" · 节省用膜 {saved:.3f} 米")

    def finished(self, output, result):
        if result.get('preview_only'):
            self.progress.setText('整批预览完成，未生成文件；本批次预览和总结已保留。')
            return
        self.metrics.setText(f"排版长度 {result['height_mm']/1000:.3f} 米"
                             f" · 常规基准 {result['baseline_height_mm']/1000:.3f} 米"
                             f" · 节省用膜 {result['saved_length_m']:.3f} 米"
                             f"（{result['saved_percent']:.1f}%） · 旋转 {result['rotation_count']} 张")
        self.progress.setText(f"已完成 · 输出：{Path(output)/result['filename']}")
        if result.get('segment_count', 1) == 1:
            self.progress.setText(self.progress.text()+' · 单张输出，未启用多段并行')
        if result.get('segment_count', 1) > 1:
            self.progress.setText(f"已完成 · {result['segment_count']} 个连续文件"
                                 f" · 同时处理 {result['actual_save_parallelism']} 段"
                                 f" · {'不限制内存预算' if result.get('save_memory_unlimited') else '使用内存预算'} · {output}")
        if 'maximum_width_mm' in result:
            self.metrics.setText(self.metrics.text()+f" · 可用宽度 {result['maximum_width_mm']:g} 毫米")
        if 'output_dpi' in result:
            self.cutting.setPlainText(cutting_report(result))
            self.cutting.show()
        self._show_quality(result.get('dual_quality', {}))

    def _show_quality(self, quality):
        if quality:
            self.metrics.setText(self.metrics.text()+'\n'+quality['text'])
