from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel


class TransitionSettings(QGroupBox):
    def __init__(self, preferences, parent=None):
        super().__init__('批次结束提示', parent)
        self.enabled = QCheckBox('在预览和输出中添加红色横向提示线')
        if not preferences.contains('cutter/end_line_disabled_pending_test_v1'):
            preferences.setValue('cutter/transition_lines', False)
            preferences.setValue('cutter/end_line_disabled_pending_test_v1', True)
        self.enabled.setChecked(preferences.value('cutter/transition_lines', False, bool))
        self.enabled.toggled.connect(lambda value: preferences.setValue('cutter/transition_lines', value))
        form = QFormLayout(self)
        form.addRow(self.enabled)
        if not preferences.contains('cutter/footer_disabled_pending_test_v1'):
            preferences.setValue('cutter/batch_footer_enabled', False)
            preferences.setValue('cutter/footer_disabled_pending_test_v1', True)
        self.footer = QCheckBox('在批次末尾打印批次、平台、机器、数量及各区刀位信息')
        self.footer.setChecked(preferences.value('cutter/batch_footer_enabled', False, bool))
        self.footer.toggled.connect(lambda value: preferences.setValue('cutter/batch_footer_enabled', value))
        form.addRow(self.footer)
        if not preferences.contains('cutter/footer_spacing_v1'):
            if preferences.value('cutter/transition_gap_mm', 3, float) == 3:
                preferences.setValue('cutter/transition_gap_mm', 10)
            preferences.setValue('cutter/footer_spacing_v1', True)
        for name, title, key, default, minimum, maximum in (
            ('gap', '内容、批次信息与结束线之间的剪切间距（毫米）', 'transition_gap_mm', 10, 0.1, 100),
            ('thickness', '红线粗细（毫米）', 'transition_line_mm', .3, .1, 2),
            ('footer_font', '批次信息文字大小（毫米）', 'batch_footer_font_mm', 4, 1, 20),
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
