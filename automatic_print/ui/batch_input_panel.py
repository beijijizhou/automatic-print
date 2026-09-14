"""One input hierarchy, with distinct single and rolling multi-batch cards."""
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QLabel
from .action_icons import action_icon


def build_batch_input(owner, panel):
    group = QGroupBox('批次输入')
    group.setObjectName('batchInput')
    row = QHBoxLayout(group)
    row.setSpacing(14)
    cards = (
        ('单批次', '选择图片文件夹后立即开始排版；取消选择不会启动任务。',
         'singleInput', [owner.start_layout_button, owner.window().stop_generation_button]),
        ('多批次', '选择上级目录；各批独立输出，完成一批立即补下一批。',
         'multiInput', [panel.bulk_generation_button]),
    )
    for title, description, name, buttons in cards:
        card = QGroupBox(title)
        card.setObjectName(name)
        body = QVBoxLayout(card)
        text = QLabel(description)
        text.setWordWrap(True)
        text.setStyleSheet('color: #475569; border: none; background: transparent;')
        body.addWidget(text)
        actions = QHBoxLayout()
        for button in buttons:
            button.setMinimumHeight(40)
            icon = 'stop' if button is owner.window().stop_generation_button else (
                'play' if button is owner.start_layout_button else 'folder')
            button.setIcon(action_icon(icon))
            actions.addWidget(button)
        body.addLayout(actions)
        row.addWidget(card, 1)
    owner.start_layout_button.setProperty('importance', 'primary')
    panel.bulk_generation_button.setText('打开多批次排版…')
    group.setStyleSheet('''
        QGroupBox#batchInput { border: none; padding-top: 24px; font-weight: bold; }
        QGroupBox#singleInput, QGroupBox#multiInput {
            border: 1px solid #93c5fd; border-radius: 10px; padding: 20px 12px 12px;
            margin-top: 8px; background: #eff6ff; font-weight: bold;
        }
        QGroupBox#multiInput { border-color: #99d5c1; background: #f0fdf8; }
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
