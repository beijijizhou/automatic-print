"""RIIN-owned margins reduce capacity; do not pad the exported canvas twice."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QDoubleSpinBox, QFormLayout, QLabel, QHBoxLayout

from .spinbox_style import double_spinbox


class PrintableWidthPanel(QWidget):
    def __init__(self, preferences, film_width, knife, parent=None):
        super().__init__(parent)
        self.preferences, self.film_width, self.knife = preferences, film_width, knife
        self.left, self.right = QDoubleSpinBox(), QDoubleSpinBox()
        migrate_centered = (
            not preferences.value('riin/centered_15mm_default_v1', False, bool)
            and all(preferences.value('riin/'+key, 10, float) == 10
                    for key in ('left_mm', 'right_mm'))
        )
        for control, key in ((self.left, 'left_mm'), (self.right, 'right_mm')):
            control.setRange(0, 600)
            control.setDecimals(2)
            saved = preferences.value('riin/'+key, 15, float)
            if migrate_centered:
                saved = 15
            control.setValue(saved)
            control.setSuffix(' 毫米')
            control.valueChanged.connect(self.refresh)
        preferences.setValue('riin/centered_15mm_default_v1', True)
        self.output_width = double_spinbox(self.usable_width(), 1, 1000, decimals=1)
        self.output_width.setSuffix(' 毫米')
        self.output_width.setToolTip('最终输出画布宽度；修改后左右预留各占剩余膜宽的一半。')
        self._syncing_output_width = False
        self.output_width.valueChanged.connect(self._output_width_requested)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow('左侧预留', self.left)
        layout.addRow('右侧预留', self.right)
        layout.addRow('输出画布宽度', self.output_width)
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
        self._syncing_output_width = True
        self.output_width.setMaximum(max(1, self.film_width.value()))
        self.output_width.setValue(max(1, width))
        self._syncing_output_width = False
        self.knife.setMaximum(max(1, width-1))
        self.description.setText(f'{self.film_width.value():g} − {self.left.value():g} − '
                                 f'{self.right.value():g} = {width:g} 毫米\n'
                                 '预留不印入输出图。刀位从画布左边起算。')
        self.description.setStyleSheet('color: #b91c1c' if width <= 0 else '')

    def _output_width_requested(self, value):
        if self._syncing_output_width:
            return
        margin = max(0, (self.film_width.value()-value)/2)
        self.left.setValue(margin)
        self.right.setValue(margin)

    def save(self):
        self.preferences.setValue('riin/left_mm', self.left.value())
        self.preferences.setValue('riin/right_mm', self.right.value())


def build_quick_output_width(window):
    """Mirror the canonical canvas limit in the main output parameter group."""
    control = QWidget()
    row = QHBoxLayout(control)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    row.addWidget(QLabel('画布宽度'))
    canonical = window.cutter_settings.printable.output_width
    quick = double_spinbox(canonical.value(), 1, 1000, decimals=1)
    quick.setSuffix(' 毫米')
    quick.setToolTip(canonical.toolTip())
    def request_width(value):
        canonical.setValue(value)
        quick.setValue(canonical.value())

    quick.valueChanged.connect(request_width)
    canonical.valueChanged.connect(quick.setValue)
    row.addWidget(quick)
    window.quick_output_width = quick
    return control
