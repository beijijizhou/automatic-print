"""Existing and future film alternatives, separate from execution timings."""
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem
from ..layout_engine.film_specs import AVAILABLE_WIDTHS, COMPARISON_COUNT, comparison_widths


class FilmComparisonTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(COMPARISON_COUNT, 7, parent)
        self.include_references = True
        self.last_comparison = None
        self.setHorizontalHeaderLabels(
            ['用膜方案', '双排数量', '实际旋转', '长度 / 米', '面积 / ㎡', '图片占位', '可用区占位'])
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.verticalHeader().hide()
        self.setMinimumHeight(275)
        self.setMaximumHeight(290)
        self.reset_rows()

    def reset_rows(self, text='等待开始排版'):
        self.last_comparison = None
        widths = comparison_widths(self.include_references)
        self.setRowCount(len(widths)*2)
        self.clearContents()
        names = (f'{film/10:g}厘米 '+('允许旋转' if rotation else '常规')+
                 ('（参考）' if film not in AVAILABLE_WIDTHS else '')
                 for film in widths for rotation in (False, True))
        for row, name in enumerate(names):
            for col, value in enumerate((name, '—', '—', text, '—', '—', '—')):
                self.setItem(row, col, QTableWidgetItem(value))
        self.setToolTip(('开发者：40–80厘米每隔5厘米比较。' if self.include_references else
                         '普通模式：只比较45/60厘米。')+'不自动切换生产参数；图片占位不是油墨覆盖率。')

    def show_comparison(self, comparison):
        if not comparison:
            return
        self.last_comparison = comparison
        rows = [r for r in comparison['rows'] if self.include_references or r['film_mm'] in AVAILABLE_WIDTHS]
        valid = [r['film_area_m2'] for r in rows if not r['error']]
        best_area = min(valid) if valid else 0
        self.setRowCount(len(rows))
        for row, result in enumerate(rows):
            extra = result.get('film_area_m2', 0)-best_area
            if result['error']:
                values = (result['name'], '—', '—', '无安全方案', '—', '—', '—')
            else:
                name = result['name'] + ('（当前输出）' if result.get('production_selected') else '')
                values = (name,
                          f"{result.get('paired_rows', 0)}行 / {result.get('paired_images', 0)}张",
                          f"{result.get('rotated_images', 0)}张",
                          f"{result['length_m']:.3f}",
                          f"{result['film_area_m2']:.3f}",
                          f"{result['image_occupancy_percent']:.1f}%",
                          f"{result['usable_occupancy_percent']:.1f}%")
            for col, value in enumerate(values):
                if col == 0 and not result.get('available', True):
                    value += '（参考）'
                item = QTableWidgetItem(value)
                selected = '当前输出的真实排版数据；' if result.get('production_selected') else ''
                item.setToolTip(selected+result.get('availability', '现有规格')+'；不自动切换生产参数；'+(result['error'] or
                    f"实际旋转 {result['rotated_images']} 张；比当前显示最省方案多 {extra:.3f} 平方米")
                )
                if not result['error'] and extra < .000001:
                    item.setBackground(QColor('#dcfce7'))
                    item.setForeground(QColor('#166534'))
                self.setItem(row, col, item)

    def set_reference_mode(self, enabled):
        self.include_references = enabled
        self.setMinimumHeight(275 if enabled else 165)
        self.setMaximumHeight(290 if enabled else 180)
        cached = self.last_comparison
        if cached:
            self.show_comparison(cached)
        else:
            self.reset_rows()
