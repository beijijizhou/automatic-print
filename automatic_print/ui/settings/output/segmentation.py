from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QLabel, QSpinBox
from ....layout_engine.domain.models import MAX_SAVE_PARALLELISM


class SegmentedOutputSettings(QGroupBox):
    def __init__(self, preferences, parent=None):
        super().__init__('分段输出（可选）', parent)
        self.parts = QSpinBox()
        self.parts.setRange(1, 32)
        self.parts.setValue(preferences.value('output/parts', 1, int))
        self.workers = QSpinBox()
        self.workers.setRange(1, MAX_SAVE_PARALLELISM)
        self.workers.setToolTip('可选择 1–8 段，实际并行不超过实际输出文件数；选择的上限自动保存。')
        self.workers.setValue(preferences.value('output/save_workers', 4, int))
        self.memory = QSpinBox()
        self.memory.setRange(128, 16384)
        self.memory.setSingleStep(256)
        self.memory.setValue(preferences.value('output/save_memory_mb', 512, int))
        self.unlimited = QCheckBox('不限制并行内存预算（按设定段数运行）')
        self.unlimited.setChecked(preferences.value('output/save_memory_unlimited', True, bool))
        self.memory.setEnabled(not self.unlimited.isChecked())
        self.unlimited.toggled.connect(lambda value: preferences.setValue('output/save_memory_unlimited', value))
        self.unlimited.toggled.connect(lambda value: self.memory.setEnabled(not value))
        self.fast_png = QCheckBox('大图分块流式合成与保存（无损，不复制整张像素）')
        self.fast_png.setChecked(preferences.value('output/stream_png', True, bool))
        self.fast_png.toggled.connect(lambda value: preferences.setValue('output/stream_png', value))
        self.fast_png.setToolTip('大图使用原生分块流水线；检查最终画布全部刀位通道，不再保存后重新解压整图。保留透明度和打印尺寸。')
        for widget, key in ((self.parts, 'output/parts'), (self.workers, 'output/save_workers'),
                            (self.memory, 'output/save_memory_mb')):
            widget.valueChanged.connect(lambda value, key=key: preferences.setValue(key, value))
        note = QLabel('文件数 1 表示完整长图，不启用多段并行。并行可选 1–8 段，实际不超过输出段数；例如同时处理 4 段，需输出至少 4 个文件。按完整订单和整行边界分段，沿用整批刀位。勾选不限制后不因预算改为串行；内存不足仍可能失败，并行更多不一定更快。完成全部检查后才能打印。')
        note.setWordWrap(True)
        layout = QFormLayout(self)
        layout.addRow('期望输出文件数', self.parts)
        layout.addRow('最多同时处理段数', self.workers)
        layout.addRow(self.unlimited)
        layout.addRow(self.fast_png)
        layout.addRow('并行内存预算（兆字节）', self.memory)
        layout.addRow(note)
