"""RIIN-owned margins reduce capacity; do not pad the exported canvas twice."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QDoubleSpinBox, QFormLayout, QLabel


class PrintableWidthPanel(QWidget):
    def __init__(self, preferences, film_width, knife, parent=None):
        super().__init__(parent)
        self.preferences, self.film_width, self.knife = preferences, film_width, knife
        self.left, self.right = QDoubleSpinBox(), QDoubleSpinBox()
        for control, key in ((self.left, 'left_mm'), (self.right, 'right_mm')):
            control.setRange(0, 600)
            control.setDecimals(1)
            control.setValue(preferences.value('riin/'+key, 10, float))
            control.setSuffix(' 毫米')
            control.valueChanged.connect(self.refresh)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow('左侧预留', self.left)
        layout.addRow('右侧预留', self.right)
        layout.addRow('可用排版宽度', self.description)
        film_width.valueChanged.connect(self.refresh)
        self.refresh()

    def usable_width(self):
        return self.film_width.value()-self.left.value()-self.right.value()

    def effective_width(self):
        width = self.usable_width()
        if width <= 0:
            raise ValueError('RIIN 左右预留之和必须小于膜实际宽度，请调整打印参数。')
        return width

    def refresh(self, *_args):
        width = self.usable_width()
        self.knife.setMaximum(max(1, width-1))
        self.description.setText(f'{self.film_width.value():g} − {self.left.value():g} − '
                                 f'{self.right.value():g} = {width:g} 毫米\n'
                                 '仅扣除可用宽度，不在输出图中重复加边距。刀位从排版左边起算。')
        self.description.setStyleSheet('color: #b91c1c' if width <= 0 else '')

    def save(self):
        self.preferences.setValue('riin/left_mm', self.left.value())
        self.preferences.setValue('riin/right_mm', self.right.value())
