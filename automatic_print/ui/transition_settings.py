from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel


class TransitionSettings(QGroupBox):
    def __init__(self, preferences, parent=None):
        super().__init__('批次结束提示', parent)
        self.enabled = QCheckBox('在预览和输出中添加红色横向提示线')
        self.enabled.setChecked(preferences.value('cutter/transition_lines', True, bool))
        self.enabled.toggled.connect(lambda value: preferences.setValue('cutter/transition_lines', value))
        form = QFormLayout(self)
        form.addRow(self.enabled)
        for name, title, key, default, minimum, maximum in (
            ('gap', '距批次最后一张图下方（毫米）', 'transition_gap_mm', 3, 0.1, 30),
            ('thickness', '红线粗细（毫米）', 'transition_line_mm', .3, .1, 2),
        ):
            widget = QDoubleSpinBox()
            widget.setRange(minimum, maximum)
            widget.setDecimals(1)
            widget.setValue(preferences.value('cutter/'+key, default, float))
            widget.valueChanged.connect(lambda value, key=key: preferences.setValue('cutter/'+key, value))
            setattr(self, name, widget)
            form.addRow(title, widget)
        note = QLabel('刀码保持左侧固定识别基准。红线仅在批次或输出分段结束处，双排区与旋转区之间不加红线。')
        note.setWordWrap(True)
        form.addRow(note)
