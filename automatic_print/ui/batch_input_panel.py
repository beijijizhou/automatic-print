"""Primary production actions and the small set of everyday parameters."""
from PySide6.QtWidgets import (
    QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
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
    identities = QHBoxLayout()
    identities.setSpacing(12)
    identities.addWidget(panel.selected_source, 3)
    identities.addWidget(panel.current_film, 2)
    layout.addLayout(identities)
    row = QHBoxLayout()
    row.setSpacing(14)
    owner.preview_only = QCheckBox('仅计算排版（不生成文件）')
    owner.preview_only.setChecked(owner.window().preferences.value('layout/preview_only', False, bool))
    owner.preview_only.setToolTip('对自动识别出的全部批次生效；计算真实排版，不生成打印文件。')
    for button, text, icon in (
        (owner.start_layout_button, '开始排版…', 'batch_multiple'),
        (owner.window().stop_generation_button, '暂停批次', 'stop'),
    ):
        button.setText(text)
        button.setMinimumHeight(40)
        button.setIcon(action_icon(icon))
        row.addWidget(button, 1)
    owner.recent_output_button = QPushButton('打开最近生成的批次')
    owner.recent_output_button.setObjectName('recentOutputButton')
    owner.recent_output_button.setMinimumHeight(40)
    owner.recent_output_button.setIcon(action_icon('folder'))
    from .recent_output import open_recent_output, refresh_recent_output_button
    owner.recent_output_button.clicked.connect(
        lambda: open_recent_output(owner.window()))
    row.addWidget(owner.recent_output_button, 1)
    refresh_recent_output_button(owner.window(), owner.recent_output_button)
    parameters = QGridLayout()
    parameters.setHorizontalSpacing(12)
    parameters.setVerticalSpacing(8)
    batch = _parameter_group('批次', owner.window().combine_bulk_batches)
    from .settings.output import build_quick_output_format
    from .printable_width import build_quick_output_width
    quick_format = build_quick_output_format(owner.window())
    output = _parameter_group('输出', owner.preview_only,
                              build_quick_output_width(owner.window()), quick_format)
    from .header_gap import build_quick_force_pair, build_quick_header_gap
    gap = build_quick_header_gap(owner.window())
    force_pair = build_quick_force_pair(owner.window())
    from .cutter_quick_settings import build_quick_cutter_settings
    cutter_controls = build_quick_cutter_settings(owner.window(), gap)
    panel.reference_films_label = QLabel('方案比较：45 / 60 厘米')
    panel.source_order = QCheckBox('批次文件夹名＋正序/倒序')
    panel.source_order.setChecked(panel.label.source_order.isChecked())
    panel.source_order.toggled.connect(panel.label.source_order.setChecked)
    panel.label.source_order.toggled.connect(panel.source_order.setChecked)
    panel.source_order_control, panel.source_order_label = _copyable_toggle(
        panel.source_order, '批次文件夹名＋正序/倒序')
    panel.cutter_group = _parameter_group(
        '切膜机 · 刀码与补距', cutter_controls)
    panel.cutter_marker_enabled.hide()
    panel.automatic_layout_group = _parameter_group(
        '自动排版', force_pair, panel.platform_enabled,
        panel.source_order_control, panel.reference_films_label)
    cutter_highlight = (
        'QGroupBox { background:#fff7ed; color:#9a3412; border:2px solid #fb923c; '
        'border-radius:7px; margin-top:10px; padding-top:10px; font-weight:700; } '
        'QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 4px; }'
    )
    panel.cutter_group.setStyleSheet(cutter_highlight)
    def sync_cutter_controls(*_args):
        enabled = owner.window().cutter_settings.mode.currentData() != 'free'
        force_pair.setVisible(enabled)
        panel.reference_films_label.setVisible(
            enabled and getattr(owner.window(), 'developer_mode_enabled', False))
    owner.window().cutter_settings.mode.currentIndexChanged.connect(
        sync_cutter_controls)
    sync_cutter_controls()
    parameters.addWidget(batch, 0, 0)
    parameters.addWidget(output, 0, 1)
    parameters.addWidget(panel.cutter_group, 1, 0, 1, 2)
    parameters.addWidget(panel.automatic_layout_group, 2, 0, 1, 2)
    parameters.setColumnStretch(0, 1)
    parameters.setColumnStretch(1, 1)
    layout.addLayout(parameters)
    layout.addLayout(row)
    owner.start_layout_button.setToolTip(
        '选择图片文件夹或上级目录，再勾选其中需要排版的批次；“切膜机文件”会自动跳过。')
    panel.bulk_generation_button.hide()  # Compatibility handle; the primary action now covers both modes.
    owner.window().stop_generation_button.setToolTip(
        '停止当前排版，保留已完成文件；不会关闭软件。')
    owner.start_layout_button.setProperty('importance', 'primary')
    from .layout_activity import LayoutActivity
    owner.window().layout_activity = LayoutActivity(owner.start_layout_button, owner.start_layout_button, group)
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
    for button in (panel.history_button, panel.test_tools_button):
        row.addWidget(button)
    navigation.setStyleSheet(
        'QWidget#pinnedWorkbenchNavigation { background: transparent; border: none; } '
        'QWidget#pinnedWorkbenchNavigation QPushButton, '
        'QWidget#pinnedWorkbenchNavigation QToolButton { padding: 5px 10px; }')
    return navigation
