"""Existing and future film alternatives, separate from execution timings."""
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem
from ..layout_engine.film_specs import FILM_WIDTHS, AVAILABLE_WIDTHS, COMPARISON_COUNT


class FilmComparisonTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(COMPARISON_COUNT, 5, parent)
        self.setHorizontalHeaderLabels(['用膜方案', '长度 / 米', '面积 / ㎡', '图片占位', '可用区占位'])
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.verticalHeader().hide()
        self.setMinimumHeight(275)
        self.setMaximumHeight(290)
        self.reset_rows()

    def reset_rows(self, text='等待开始排版'):
        self.setRowCount(COMPARISON_COUNT)
        self.clearContents()
        names = (f'{film/10:g}厘米 '+('允许旋转' if rotation else '常规')+
                 ('（参考）' if film not in AVAILABLE_WIDTHS else '')
                 for film in FILM_WIDTHS for rotation in (False, True))
        for row, name in enumerate(names):
            for col, value in enumerate((name, text, '—', '—', '—')):
                self.setItem(row, col, QTableWidgetItem(value))
        self.setToolTip('40–80厘米每隔5厘米比较；仅45/60为现有规格；参考结果不会切换生产参数。图片占位不是油墨覆盖率。')

    def show_comparison(self, comparison):
        if not comparison:
            return
        self.setRowCount(len(comparison['rows']))
        for row, result in enumerate(comparison['rows']):
            if result['error']:
                values = (result['name'], '无安全方案', '—', '—', '—')
            else:
                values = (result['name'], f"{result['length_m']:.3f}",
                          f"{result['film_area_m2']:.3f}",
                          f"{result['image_occupancy_percent']:.1f}%",
                          f"{result['usable_occupancy_percent']:.1f}%")
            for col, value in enumerate(values):
                if col == 0 and not result.get('available', True):
                    value += '（参考）'
                item = QTableWidgetItem(value)
                item.setToolTip(result.get('availability', '现有规格')+'；不自动切换生产参数；'+(result['error'] or
                    f"实际旋转 {result['rotated_images']} 张；比最省方案多 {result['extra_area_vs_best_m2']:.3f} 平方米")
                )
                if not result['error'] and result['extra_area_vs_best_m2'] < .000001:
                    item.setBackground(QColor('#dcfce7'))
                    item.setForeground(QColor('#166534'))
                self.setItem(row, col, item)
