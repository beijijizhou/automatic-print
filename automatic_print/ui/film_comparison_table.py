"""Always-visible four alternatives, separate from execution phase timings."""
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


class FilmComparisonTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(4, 5, parent)
        self.setHorizontalHeaderLabels(['用膜方案', '长度 / 米', '面积 / ㎡', '图片占位', '可用区占位'])
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.verticalHeader().hide()
        self.setMinimumHeight(165)
        self.setMaximumHeight(180)
        self.reset()

    def reset(self, text='等待开始排版'):
        self.clearContents()
        for row, name in enumerate(('60厘米 常规', '60厘米 允许旋转', '45厘米 常规', '45厘米 允许旋转')):
            for col, value in enumerate((name, text, '—', '—', '—')):
                self.setItem(row, col, QTableWidgetItem(value))
        self.setToolTip('分段前整批比较；面积使用物理膜宽，图片占位包含原图透明部分，不是油墨覆盖率。')

    def show_comparison(self, comparison):
        if not comparison:
            return
        for row, result in enumerate(comparison['rows']):
            if result['error']:
                values = (result['name'], '无安全方案', '—', '—', '—')
            else:
                values = (result['name'], f"{result['length_m']:.3f}",
                          f"{result['film_area_m2']:.3f}",
                          f"{result['image_occupancy_percent']:.1f}%",
                          f"{result['usable_occupancy_percent']:.1f}%")
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(result['error'] or
                    f"实际旋转 {result['rotated_images']} 张；比最省方案多 {result['extra_area_vs_best_m2']:.3f} 平方米")
                if not result['error'] and result['extra_area_vs_best_m2'] < .000001:
                    item.setBackground(QColor('#dcfce7'))
                    item.setForeground(QColor('#166534'))
                self.setItem(row, col, item)
