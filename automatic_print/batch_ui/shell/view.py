"""Construct the ERP workbench shell without owning its actions."""
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from ...automation.providers.registry import ERP_PLATFORMS


def build_controls(owner) -> None:
    owner.platform = QComboBox()
    for name in owner.platform_names:
        owner.platform.addItem(name, name)
    owner.platform.setCurrentText(owner.platform_names[0])
    if any(name in ERP_PLATFORMS for name in owner.platform_names):
        owner.open_playwright_button = QPushButton(
            '打开 Playwright 浏览器（提前登录）'
        )
        owner.open_playwright_button.setToolTip(
            "手动启动或显示本机唯一的 Playwright Chrome；"
            "可自行打开并提前登录所需网站，后续读取和下载会复用同一浏览器。"
        )
        owner.open_playwright_button.clicked.connect(owner.open_playwright_browser)
    default = (Path(QStandardPaths.writableLocation(
        QStandardPaths.DesktopLocation)) / 'AutomaticPrintDownloads')
    owner.output = QLineEdit(owner.preferences.value(
        'automation/output_location', str(default), str))
    browse = QPushButton('选择…')
    browse.clicked.connect(owner.choose_output)
    owner.output_row = QHBoxLayout()
    owner.output_row.addWidget(owner.output)
    owner.output_row.addWidget(browse)
    owner.settings_button = QPushButton('打印参数设置…')
    owner.settings_button.clicked.connect(owner.open_settings)
    owner.log = QPlainTextEdit()
    owner.log.setReadOnly(True)
    owner.log.setMaximumHeight(100)
    owner.loading_panel = QWidget()
    owner.loading_panel.setStyleSheet(
        'QWidget{background:#e8f1ff;border:1px solid #6f9ee8;'
        'border-radius:6px;} QLabel{border:none;color:#173f73;'
        'font-size:14px;font-weight:700;}')
    loading = QVBoxLayout(owner.loading_panel)
    owner.loading_label = QLabel('正在准备…')
    owner.loading_label.setWordWrap(True)
    owner.loading_bar = QProgressBar()
    owner.loading_bar.setRange(0, 0)
    owner.loading_bar.setTextVisible(False)
    owner.stop_button = QPushButton('停止当前处理')
    owner.stop_button.setEnabled(False)
    owner.stop_button.clicked.connect(owner.stop_current_task)
    for widget in (owner.loading_label, owner.loading_bar, owner.stop_button):
        loading.addWidget(widget)
    owner.loading_panel.hide()


def build_layout(owner) -> None:
    layout = QVBoxLayout(owner)
    if not owner.local_only:
        layout.addWidget(QLabel('生产平台'))
        layout.addWidget(owner.platform)
        if hasattr(owner, 'open_playwright_button'):
            layout.addWidget(owner.open_playwright_button)
    layout.addWidget(owner.loading_panel)
    if hasattr(owner, 'batch_tools'):
        layout.addWidget(owner.batch_tools)
    owner.workbench_scroll = QScrollArea()
    owner.workbench_scroll.setWidgetResizable(True)
    owner.workbench_scroll.setWidget(owner.main_tabs)
    layout.addWidget(owner.workbench_scroll)
    if owner.download_only:
        owner.settings_button.hide()
    elif not owner.local_only:
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(owner.settings_button)
        layout.addLayout(footer)
    for label in owner.findChildren(QLabel):
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
