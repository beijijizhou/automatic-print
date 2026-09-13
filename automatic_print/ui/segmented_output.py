from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QSpinBox


class SegmentedOutputSettings(QGroupBox):
    def __init__(self, preferences, parent=None):
        super().__init__('分段输出（可选）', parent)
        self.parts = QSpinBox()
        self.parts.setRange(1, 32)
        self.parts.setValue(preferences.value('output/parts', 1, int))
        self.workers = QSpinBox()
        self.workers.setRange(1, 2)
        self.workers.setValue(preferences.value('output/save_workers', 2, int))
        self.memory = QSpinBox()
        self.memory.setRange(128, 16384)
        self.memory.setSingleStep(256)
        self.memory.setValue(preferences.value('output/save_memory_mb', 512, int))
        for widget, key in ((self.parts, 'output/parts'), (self.workers, 'output/save_workers'),
                            (self.memory, 'output/save_memory_mb')):
            widget.valueChanged.connect(lambda value, key=key: preferences.setValue(key, value))
        note = QLabel('1 表示完整长图。按完整订单和整行边界分段，沿用整批刀位；可分段数不足时减少文件数。大段超过内存预算时自动串行，完成全部检查后才能打印。')
        note.setWordWrap(True)
        layout = QFormLayout(self)
        layout.addRow('期望输出文件数', self.parts)
        layout.addRow('最多同时处理段数', self.workers)
        layout.addRow('并行内存预算（兆字节）', self.memory)
        layout.addRow(note)
