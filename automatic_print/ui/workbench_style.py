"""One reusable visual hierarchy for the workbench and its settings dialogs."""
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel, QPushButton

from .action_icons import action_icon


BUTTON_STYLE = '''
QPushButton { background: #ffffff; color: #334155; border: 1px solid #cbd5e1;
    border-radius: 7px; padding: 7px 12px; min-height: 20px; font-weight: 500; }
QPushButton:hover { background: #eff6ff; border-color: #60a5fa; color: #1d4ed8; }
QPushButton:pressed { background: #dbeafe; }
QPushButton:focus { border: 2px solid #2563eb; padding: 6px 11px; }
QPushButton[importance="primary"] { background: #2563eb; color: white;
    border-color: #2563eb; font-weight: 700; }
QPushButton[importance="primary"]:hover { background: #1d4ed8; border-color: #1d4ed8; }
QPushButton[importance="primary"]:pressed { background: #1e40af; }
QPushButton[importance="danger"] { background: #fff1f2; color: #be123c; border-color: #fda4af; }
QPushButton[importance="danger"]:hover { background: #ffe4e6; border-color: #e11d48; }
QPushButton:disabled { background: #f1f5f9; color: #94a3b8; border-color: #e2e8f0; }
'''

WORKBENCH_STYLE = '''
QMainWindow, QDialog { background: #f4f7fb; }
QWidget { color: #1e293b; font-size: 13px; }
QScrollArea, QTabWidget::pane { border: none; background: transparent; }
QGroupBox { background: white; border: 1px solid #dce4ef; border-radius: 9px;
    margin-top: 15px; padding: 14px 10px 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 13px; padding: 0 5px; color: #334155; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: white; color: #1e293b;
    border: 1px solid #cbd5e1; border-radius: 5px; padding: 5px; min-height: 20px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #2563eb; }
QLineEdit:read-only { background: #f8fafc; color: #64748b; }
QPlainTextEdit, QTableWidget, QTreeWidget { background: white; border: 1px solid #dce4ef;
    border-radius: 7px; selection-background-color: #dbeafe; selection-color: #1e40af; }
QHeaderView::section { background: #f1f5f9; color: #475569; padding: 7px;
    border: none; border-bottom: 1px solid #dce4ef; font-weight: 600; }
QProgressBar { background: #e8eef7; border: none; border-radius: 5px;
    min-height: 18px; text-align: center; color: #0f172a; }
QProgressBar::chunk { background: #60a5fa; border-radius: 5px; }
QLabel[heading="true"] { font-size: 20px; font-weight: 700; color: #0f172a; padding: 4px 0; }
QCheckBox { spacing: 7px; }
'''


def button_kind(text):
    for words, kind in (
        (('单批次排版',), 'batch_single'), (('多批次排版',), 'batch_multiple'),
        (('放大',), 'zoom_in'), (('缩小',), 'zoom_out'),
        (('适合宽度', '最大化查看', '返回主界面'), 'expand'),
        (('停止', '暂停批次'), 'stop'), (('预览',), 'preview'),
        (('开始排版', '生成最终', '确认并生成'), 'play'),
        (('色块',), 'color'), (('标签', '文字'), 'text'),
        (('参数', '设置'), 'settings'), (('保存',), 'save'),
        (('文件夹', '选择…', '保存位置'), 'folder'),
        (('更新', '刷新', '读取'), 'refresh'), (('复制',), 'copy'),
        (('日期',), 'date'), (('机器',), 'machine'),
        (('向左',), 'left'), (('向右',), 'right'), (('还原',), 'refresh'),
    ):
        if any(word in text for word in words):
            return kind
    return 'more'


def apply_workbench_style(window):
    from .copyable_text import install_text_copying
    install_text_copying()
    from .spinbox_style import spinbox_style
    window.setStyleSheet(WORKBENCH_STYLE + BUTTON_STYLE + spinbox_style())
    for button in window.findChildren(QPushButton):
        kind = button_kind(button.text())
        importance = 'primary' if kind in {'play', 'batch_single'} else 'danger' if kind == 'stop' else 'secondary'
        button.setProperty('importance', importance)
        button.setIcon(action_icon(kind, '#ffffff' if importance == 'primary' else
                                   '#be123c' if importance == 'danger' else '#475569'))
        button.setIconSize(QSize(18, 18))
        # Explicit button rules also work inside locally styled loading panels.
        if button is not window.color_block_settings.color_button:
            button.setStyleSheet(BUTTON_STYLE)
    for label in window.findChildren(QLabel):
        if label.text() == '本地图片排版':
            label.setProperty('heading', True)
            label.style().unpolish(label)
            label.style().polish(label)
