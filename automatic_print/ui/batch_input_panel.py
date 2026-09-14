"""A compact production action row; configuration belongs in print settings."""
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QPushButton
from .action_icons import action_icon


def build_batch_input(owner, panel):
    group = QGroupBox('批次排版')
    group.setObjectName('batchInput')
    row = QHBoxLayout(group)
    row.setSpacing(14)
    owner.preview_layout_button = QPushButton('仅预览排版')
    owner.preview_layout_button.clicked.connect(owner.window().choose_and_preview)
    owner.preview_layout_button.setToolTip('使用当前文件夹计算整批排版和用膜情况，不生成打印文件。')
    for button, text, icon in (
        (owner.start_layout_button, '单批次排版', 'batch_single'),
        (panel.bulk_generation_button, '多批次排版', 'batch_multiple'),
        (owner.preview_layout_button, '仅预览排版', 'preview'),
        (owner.window().stop_generation_button, '暂停批次', 'stop'),
    ):
        button.setText(text)
        button.setMinimumHeight(40)
        button.setIcon(action_icon(icon))
        row.addWidget(button, 1)
    owner.start_layout_button.setToolTip('选择图片文件夹后立即开始排版；取消不会启动任务。')
    panel.bulk_generation_button.setToolTip('选择上级目录中的批次；并发参数在打印设置中修改。')
    owner.window().stop_generation_button.setToolTip(
        '安全停止当前排版，保留已完成文件；暂不支持断点续跑。')
    owner.start_layout_button.setProperty('importance', 'primary')
    group.setStyleSheet('''
        QGroupBox#batchInput { border: none; padding-top: 24px; font-weight: bold; }
    ''')
    return group


def build_batch_tools(panel):
    """Secondary actions belong below the data, not alongside input choices."""
    row = QHBoxLayout()
    row.addStretch()
    row.addWidget(panel.details_button)
    for button in (panel.history_button, panel.bulk_analysis_button, panel.algorithm_costs_button):
        row.addWidget(button)
    panel.summary.layout().addLayout(row)
