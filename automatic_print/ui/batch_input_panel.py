"""A compact production action row; configuration belongs in print settings."""
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QCheckBox
from .action_icons import action_icon


def build_batch_input(owner, panel):
    group = QGroupBox('批次排版')
    group.setObjectName('batchInput')
    row = QHBoxLayout(group)
    row.setSpacing(14)
    owner.preview_only = QCheckBox('仅预览，不生成文件')
    owner.preview_only.setChecked(owner.window().preferences.value('layout/preview_only', False, bool))
    owner.preview_only.setToolTip('对单批次和多批次均生效；计算真实排版，不生成打印文件。')
    for button, text, icon in (
        (owner.start_layout_button, '单批次排版', 'batch_single'),
        (panel.bulk_generation_button, '多批次排版', 'batch_multiple'),
        (owner.window().stop_generation_button, '暂停批次', 'stop'),
    ):
        button.setText(text)
        button.setMinimumHeight(40)
        button.setIcon(action_icon(icon))
        row.addWidget(button, 1)
    row.addWidget(owner.preview_only)
    from .header_gap import build_quick_header_gap
    row.addWidget(build_quick_header_gap(owner.window()))
    owner.start_layout_button.setToolTip('选择图片文件夹后立即开始排版；取消不会启动任务。')
    panel.bulk_generation_button.setToolTip('选择上级目录中的批次；并发参数在打印设置中修改。')
    owner.window().stop_generation_button.setToolTip(
        '立即退出软件，不等待任务完成；未完成批次禁止打印，已完成批次保留。')
    owner.start_layout_button.setProperty('importance', 'primary')
    from .layout_activity import LayoutActivity
    owner.window().layout_activity = LayoutActivity(owner.start_layout_button, panel.bulk_generation_button, group)
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
