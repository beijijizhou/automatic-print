"""Always-visible current task information, separate from print settings."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QPlainTextEdit, QVBoxLayout, QPushButton
from ..layout_engine.output.output_sizes import cutting_report
from ..layout_engine.intake.metadata.image_anomalies import anomaly_text


class BatchSummaryPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__('本次批次 · 排版总结', parent)
        self.info = QLabel('请选择本地图片文件夹。')
        self.save_report = ''
        self.info.setTextFormat(Qt.PlainText)
        self.info.setStyleSheet('QLabel { background: #dbeafe; color: #1e3a8a; '
            'border: 2px solid #60a5fa; border-radius: 7px; padding: 9px; '
            'font-size: 17px; font-weight: bold; }')
        self.metrics = QLabel('排版后显示总长度、节省用膜和旋转数量。')
        self.metrics.hide()
        self.progress = QLabel('尚未开始')
        self.gap_loss = QLabel()
        self.gap_loss.setWordWrap(True)
        self.gap_loss.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.anomalies = QLabel()
        self.anomalies.setWordWrap(True)
        self.anomalies.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.anomalies.setStyleSheet('color: #a35400; background: #fff3d6; padding: 6px;')
        self.anomalies.hide()
        self.failure_message = ''
        from .failure_panel import FailurePanel
        self.failure_panel = FailurePanel(self)
        self.failure_details = self.failure_panel.open_button
        from .film_comparison_table import FilmComparisonTable
        self.film_table = FilmComparisonTable(self)
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
        layout.addWidget(self.gap_loss)
        layout.addWidget(self.anomalies)
        layout.addWidget(self.film_table)

    def start(self, folder, count=None):
        self.save_report = ''
        self.gap_loss.clear()
        self.film_table.reset_rows()
        self.cutting.clear()
        self.cutting.setMaximumHeight(110)
        self.anomalies.clear()
        self.anomalies.hide()
        self.failure_message = ''
        self.failure_panel.reset()
        self.cutting.hide()
        path = Path(folder)
        quantity = f'{count} 张图片' if count is not None else '正在读取图片名称'
        self.info.setText(f'文件夹：{path.name} · {quantity}\n来源：{path}')
        self.metrics.setText('正在计算本批次长度和省膜结果…')
        self.metrics.hide()
        self.progress.setText('正在读取本批次；旧预览已清除。')

    def show_plan(self, payload):
        planned = payload['planned']
        self.show_analysis(payload.get('analysis', {}))
        rotations = sum(bool(p.rotation_degrees) for _, p in planned)
        self.metrics.setText(self.metrics.text()+f' · 旋转 {rotations} 张'
                             f" · 可用宽度 {payload['settings'].media_width_mm:g} 毫米")
        self.metrics.show()
        self._show_quality(payload.get('dual_quality', {}))
        self.progress.setText(payload.get('warning') or '排版已确定，下面显示本批次真实预览。')

    def show_analysis(self, report):
        if not report:
            return
        from ..layout_engine.planning.zones.gap_loss import gap_loss_text
        self.gap_loss.setText(gap_loss_text(report.get('gap_loss')))
        folder = self.info.text().split('\n')[0]
        self.info.setText(f"{folder}\n{report['batch_type']} · {report['order_count']} 个订单组"
                          f" · {report['piece_count']} 件 / {report['image_count']} 张图"
                          f" · {report['double_pairs']} 组双面")
        if report.get('cache', {}).get('hit'):
            self.info.setText(self.info.text()+'\n本地缓存命中：已复用测量、刀位、排版与用膜方案')
        if 'height_m' in report:
            saved = report['saved_m']
            self.metrics.setText(f"排版长度 {report['height_m']:.3f} 米"
                                 f" · 常规基准 {report['height_m']+saved:.3f} 米"
                                 f" · 节省用膜 {saved:.3f} 米")
            self.metrics.show()
        self._show_comparison(report)
        self.anomalies.setText(anomaly_text(report))
        self.anomalies.setVisible(bool(self.anomalies.text()))

    def _show_comparison(self, report):
        self.film_table.show_comparison(report.get('film_comparison'), report)
        if report.get('stage') == '排版结果' and not report.get('film_comparison'):
            self.film_table.reset_rows('比较未启用')
        comparison = report.get('rotation_comparison')
        if comparison:
            normal = comparison['normal_m']
            normal_text = f'{normal:.3f} 米' if normal is not None else '无安全方案'
            saved = comparison['saved_m']
            saving = f'{saved:.3f} 米' if saved is not None else '无法比较'
            strategy = comparison.get('selected_strategy', '旋转区域')
            self.metrics.setText(self.metrics.text()+
                f"\n实际排版策略比较（分段前）：固定刀位不旋转 {normal_text} · {strategy} {comparison['rotation_m']:.3f} 米"
                f" · 省膜 {saving} · 实际旋转 {comparison['rotated_images']} 张"
                '\n可在打印参数取消旋转区，选择常规方案；仅预览不会生成文件。')

    def finished(self, output, result):
        self.anomalies.setText('\n'.join(filter(None, (
            anomaly_text(result.get('analysis', {})), result.get('history_warning', '')))))
        self.anomalies.setVisible(bool(self.anomalies.text()))
        if result.get('preview_only'):
            self.progress.setText('整批预览完成，未生成文件；完整排版报告已显示，可直接复制。')
            report = result.get('report_text')
            if not report and result.get('placements') and result.get('output_dpi'):
                report = cutting_report(result)
            self.cutting.setPlainText(report or '仅预览完成；本次未生成输出文件。')
            self.cutting.setMaximumHeight(260)
            self.cutting.show()
            return
        self.metrics.setText(f"排版长度 {result['height_mm']/1000:.3f} 米"
                             f" · 常规基准 {result['baseline_height_mm']/1000:.3f} 米"
                             f" · 节省用膜 {result['saved_length_m']:.3f} 米"
                             f"（{result['saved_percent']:.1f}%） · 旋转 {result['rotation_count']} 张")
        self.metrics.show()
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
        self._show_comparison(result.get('analysis', {}))
        from ..layout_engine.rendering.png.fast import timing_text
        from ..layout_engine.output.output_file_info import result_file_report
        self.save_report = result_file_report(result)
        self.metrics.setText(self.metrics.text()+'\n'+timing_text(result.get('png_save_details')))

    def _show_quality(self, quality):
        if quality:
            self.metrics.setText(self.metrics.text()+'\n'+quality['text'])

    def show_failure(self, message):
        self.failure_message = message
        self.failure_panel.show_message(message)

    def open_failure(self):
        from .failure_dialog import show_failure_dialog
        show_failure_dialog(self, self.failure_message)
