"""Load historical numeric data only when the user opens history."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QTableWidget, QTableWidgetItem, QAbstractItemView,
                              QHeaderView, QFileDialog, QPlainTextEdit)
from ..history.store import load_runs, history_path, export_csv
from ..layout_engine.planning.film.film_comparison import comparison_text
from .film_comparison_table import FilmComparisonTable
from .action_icons import action_icon


class FilmHistoryPage(QWidget):
    def __init__(self, parent=None, path=None):
        super().__init__(parent)
        self.path, self.records = path, []
        layout = QVBoxLayout(self)
        actions = QHBoxLayout()
        refresh = QPushButton('刷新历史')
        export = QPushButton('导出全部统计数据')
        summarize = QPushButton('汇总同组批次')
        summarize.setIcon(action_icon('more'))
        summarize.clicked.connect(self.summarize)
        refresh.setIcon(action_icon('refresh'))
        export.setIcon(action_icon('save'))
        refresh.clicked.connect(self.refresh)
        export.clicked.connect(self.export)
        actions.addWidget(refresh)
        actions.addWidget(export)
        actions.addWidget(summarize)
        layout.addLayout(actions)
        self.status = QLabel('打开历史时读取本地日志，不读取原始图片。')
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.runs = QTableWidget(0, 5)
        self.runs.setHorizontalHeaderLabels(['时间', '批次', '图片数', '生产膜宽', '状态'])
        self.runs.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.runs.setSelectionMode(QAbstractItemView.SingleSelection)
        self.runs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.runs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.runs.currentCellChanged.connect(self.select)
        layout.addWidget(self.runs)
        self.comparison = FilmComparisonTable()
        layout.addWidget(self.comparison)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details)

    def refresh(self):
        try:
            self.records = load_runs(self.path)
            self.runs.setRowCount(0)
            self.runs.setRowCount(len(self.records))
            for index, record in enumerate(self.records):
                settings = record['settings']
                film = settings['media_width_mm']+settings['riin_left_mm']+settings['riin_right_mm']
                timestamp = record['created_at'][:19].replace('T', ' ')
                for col, value in enumerate((timestamp, record['batch_name'],
                                             record['image_count'], f'{film/10:g}厘米', record['status'])):
                    self.runs.setItem(index, col, QTableWidgetItem(str(value)))
            self.status.setText(f'本地日志：{self.path or history_path()} · {len(self.records)}次记录')
            if self.records:
                self.runs.setCurrentCell(0, 0)
                self.select(0)
            else:
                self.comparison.reset_rows('没有历史数据')
                self.details.clear()
        except Exception as error:
            self.status.setText(f'历史读取失败：{error}')

    def select(self, row, *_):
        if not 0 <= row < len(self.records):
            return
        record = self.records[row]
        self.comparison.show_comparison(record['comparison'])
        self.details.setPlainText(f"来源：{record['source_folder']}\n输出：{record['output_folder']}\n"
                                  f"版本：{record['version_display']}\n"+
                                  comparison_text(record['comparison']))

    def export(self):
        filename, _ = QFileDialog.getSaveFileName(self, '导出统计数据', '用膜统计.csv', '统计文件 (*.csv)')
        if filename:
            try:
                export_csv(filename, self.records)
                self.status.setText(f'已导出：{filename}；每次记录、每套方案各一行。')
            except Exception as error:
                self.status.setText(f'导出失败：{error}')

    def summarize(self):
        row = self.runs.currentRow()
        if not 0 <= row < len(self.records):
            return
        group = self.records[row].get('group_id')
        if not group:
            self.status.setText('这条记录不属于批量分析组，请选择批量分析的记录。')
            return
        from ..history.bulk_analysis import summary_text
        self.details.setPlainText(summary_text([r for r in self.records if r.get('group_id') == group]))
