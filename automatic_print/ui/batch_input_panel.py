"""Primary production actions and the small set of everyday parameters."""
from PySide6.QtWidgets import (
    QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)
from .action_icons import action_icon


def _parameter_group(title, *controls):
    group = QGroupBox(title)
    row = QHBoxLayout(group)
    row.setContentsMargins(10, 8, 10, 8)
    row.setSpacing(12)
    for control in controls:
        row.addWidget(control)
    row.addStretch()
    return group


def _copyable_toggle(checkbox, text):
    """Keep the switch compact while its caption remains directly selectable."""
    control = QWidget()
    row = QHBoxLayout(control)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    checkbox.setText('')
    checkbox.setAccessibleName(text)
    caption = QLabel(text)
    from .copyable_text import selectable
    selectable(caption)
    row.addWidget(checkbox)
    row.addWidget(caption)
    return control, caption


def build_batch_input(owner, panel):
    group = QGroupBox('批次排版')
    group.setObjectName('batchInput')
    layout = QVBoxLayout(group)
    row = QHBoxLayout()
    row.setSpacing(14)
    owner.preview_only = QCheckBox('仅计算排版（不生成文件）')
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
    parameters = QGridLayout()
    parameters.setHorizontalSpacing(12)
    parameters.setVerticalSpacing(8)
    batch = _parameter_group('批次', owner.window().combine_bulk_batches)
    output = _parameter_group('输出', owner.preview_only)
    from .header_gap import build_quick_force_pair, build_quick_header_gap
    gap = build_quick_header_gap(owner.window())
    force_pair = build_quick_force_pair(owner.window())
    panel.reference_films_label = QLabel('方案比较：45 / 60 厘米')
    layout_rules = _parameter_group('排版', gap, force_pair, panel.reference_films_label)
    panel.source_order = QCheckBox('文件名＋正序/倒序')
    panel.source_order.setChecked(panel.label.source_order.isChecked())
    panel.source_order.toggled.connect(panel.label.source_order.setChecked)
    panel.label.source_order.toggled.connect(panel.source_order.setChecked)
    source_order_control, panel.source_order_label = _copyable_toggle(
        panel.source_order, '文件名＋正序/倒序')
    panel.source_order_group = _parameter_group('标签', source_order_control)
    parameters.addWidget(batch, 0, 0)
    parameters.addWidget(output, 0, 1)
    parameters.addWidget(panel.source_order_group, 0, 2)
    parameters.addWidget(layout_rules, 1, 0, 1, 3)
    parameters.setColumnStretch(0, 1)
    parameters.setColumnStretch(1, 1)
    layout.addLayout(parameters)
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
    navigation.setStyleSheet(
        'QWidget#pinnedWorkbenchNavigation { background: transparent; border: none; } '
        'QWidget#pinnedWorkbenchNavigation QPushButton { padding: 5px 10px; }')
    return navigation
