"""A compact production action row; configuration belongs in print settings."""
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QCheckBox, QLabel, QVBoxLayout, QWidget
from .action_icons import action_icon


def build_batch_input(owner, panel):
    group = QGroupBox('批次排版')
    group.setObjectName('batchInput')
    layout = QVBoxLayout(group)
    row = QHBoxLayout()
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
    layout.addLayout(row)
    options = QHBoxLayout()
    options.setSpacing(14)
    options.addWidget(owner.preview_only)
    options.addWidget(owner.window().combine_bulk_batches)
    from .header_gap import build_quick_force_pair, build_quick_header_gap
    options.addWidget(build_quick_header_gap(owner.window()))
    options.addWidget(build_quick_force_pair(owner.window()))
    options.addStretch()
    layout.addLayout(options)
    owner.start_layout_button.setToolTip('选择图片文件夹后立即开始排版；取消不会启动任务。')
    panel.bulk_generation_button.setToolTip('选择上级目录中的批次；并发参数在打印设置中修改。')
    owner.window().stop_generation_button.setToolTip(
        '停止当前单批次或多批次排版，保留已完成文件；不会关闭软件。')
    owner.start_layout_button.setProperty('importance', 'primary')
    from .layout_activity import LayoutActivity
    owner.window().layout_activity = LayoutActivity(owner.start_layout_button, panel.bulk_generation_button, group)
    group.setStyleSheet('''
        QGroupBox#batchInput { border: none; padding-top: 24px; font-weight: bold; }
    ''')
    return group


def build_batch_tools(panel):
    """Global inspection actions stay fixed above the scrolling workbench."""
    navigation = QWidget()
    navigation.setObjectName('pinnedWorkbenchNavigation')
    row = QHBoxLayout(navigation)
    row.setContentsMargins(0, 0, 0, 2)
    row.addStretch()
    panel.developer_tools_label = QLabel('开发者功能：')
    row.addWidget(panel.developer_tools_label)
    for button in (panel.history_button, panel.bulk_analysis_button, panel.algorithm_costs_button):
        row.addWidget(button)
    panel.source_order = QCheckBox('文件名＋正序/倒序', navigation)
    panel.source_order.setChecked(panel.label.source_order.isChecked())
    panel.source_order.toggled.connect(panel.label.source_order.setChecked)
    panel.label.source_order.toggled.connect(panel.source_order.setChecked)
    row.addWidget(panel.source_order)
    panel.reference_films_label = QLabel('45/60厘米膜')
    row.addWidget(panel.reference_films_label)
    navigation.setStyleSheet(
        'QWidget#pinnedWorkbenchNavigation { background: transparent; border: none; } '
        'QWidget#pinnedWorkbenchNavigation QPushButton { padding: 5px 10px; }')
    return navigation
